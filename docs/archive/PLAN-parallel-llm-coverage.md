# Plan: Parallelize LLM Calls in Coverage Analyzer

## Problem

The coverage analyzer's LLM stage (`llm_matcher.py:412`) runs one API call per unmatched item **sequentially**. With 10-20 items hitting the LLM and ~1-2s per call, this stage takes 10-40 seconds serially. The system prompt (~1200 tokens) is identical across all calls for a given claim — only the user message varies. These calls are independent and can run concurrently.

## Current Architecture

```
analyzer.py:analyze()
  └─ llm_matcher.batch_match()          # llm_matcher.py:412 — sequential for loop
       └─ llm_matcher.match()            # One call per item
            ├─ client.set_context(...)    # Sets instance state (NOT thread-safe)
            └─ client.chat_completions_create(...)
                 └─ _sink.log_call(...)   # File write (has module-level lock, IS thread-safe)
```

### Thread-Safety Constraints

| Component | Thread-safe? | Details |
|-----------|-------------|---------|
| `AuditedOpenAIClient` | **NO** | `set_context()` stores state in instance vars (`_claim_id`, `_doc_id`, etc.) used by `chat_completions_create()`. Two threads sharing one client would corrupt each other's audit context. (`llm_audit.py:217-232`) |
| `LLMMatcher._llm_calls` counter | **NO** | Plain `int` incremented at `llm_matcher.py:326`. Race condition under threads. |
| `FileLLMCallStorage` (log sink) | **YES** | Module-level `_llm_write_lock = threading.Lock()` protects all file writes. (`llm_storage.py:33`) |
| `on_progress` callback | **Depends** | CLI uses simple `tqdm.update()` which is thread-safe. WebSocket callbacks use `asyncio.run_coroutine_threadsafe()` which is also safe. |
| OpenAI Python SDK `client.chat.completions.create()` | **YES** | The underlying `httpx` client is thread-safe for concurrent requests. |

### Existing Concurrency Patterns in Codebase

- **CLI claim-level parallelism** (`cli.py:2414`): Uses `ThreadPoolExecutor` with **per-thread service instances** — each worker creates its own `ClaimAssessmentService`, `FileStorage`, and by extension its own `AuditedOpenAIClient`.
- **FastAPI pipeline** (`api/services/pipeline.py:310`): Uses `asyncio.to_thread()` to offload blocking pipeline code, with `asyncio.run_coroutine_threadsafe()` for callbacks from worker threads.

## Approach: `ThreadPoolExecutor` in `batch_match()`

Use `concurrent.futures.ThreadPoolExecutor` to fire LLM calls in parallel within `batch_match()`. This is the simplest change — stays synchronous from the caller's perspective, no async infection up the call stack.

### Why ThreadPoolExecutor over asyncio

- `batch_match()` is called from synchronous code in `analyzer.py:1723`, which is called from synchronous pipeline code. Converting to async would require changes propagating up through `analyze()` → `ClaimAssessmentService.assess()` → `ScreeningStage.run()` → CLI entrypoints.
- The existing codebase already uses `ThreadPoolExecutor` for the same pattern (parallel OpenAI calls across claims in `cli.py:2414`).
- The OpenAI SDK's sync `client.chat.completions.create()` is backed by `httpx` which handles connection pooling internally.

### Key Design Decisions

1. **Per-thread `AuditedOpenAIClient` instances.** Each worker thread gets its own client so `set_context()` state doesn't collide. The underlying OpenAI SDK client (and its HTTP connection pool) can be shared — only the audit wrapper needs isolation.

2. **Thread-safe call counter.** Replace `self._llm_calls += 1` with `threading.Lock` protection or use `itertools.count` / `threading.local`.

3. **Thread-safe progress callback.** Wrap `on_progress(1)` in a lock to prevent interleaved calls (even though current consumers are safe, this is defensive).

4. **Concurrency limit via `max_workers`.** Default to 5 concurrent calls. OpenAI rate limits are per-account, and 5 concurrent calls is conservative. Make this configurable via `LLMMatcherConfig`.

5. **Preserve result ordering.** `executor.map()` returns results in submission order, maintaining the original item sequence.

## Implementation Steps

### Step 1: Add config field to `LLMMatcherConfig`

File: `llm_matcher.py:28-52`

Add `max_concurrent: int = 5` to `LLMMatcherConfig`. This controls the thread pool size. Setting to `1` disables parallelism (sequential fallback).

### Step 2: Create per-call match function

File: `llm_matcher.py`

Extract the core of `match()` into a self-contained function that accepts its own client instance (or creates one per thread). The function should:
- Accept all item data + shared immutable state (categories, components, config)
- Create or reuse a thread-local `AuditedOpenAIClient`
- Call `set_context()` and `chat_completions_create()` on its own client
- Return the `LineItemCoverage` result

### Step 3: Rewrite `batch_match()` to use ThreadPoolExecutor

File: `llm_matcher.py:383-432`

```python
def batch_match(self, items, ..., on_progress=None, ...):
    if self.config.max_concurrent <= 1 or len(items) <= 1:
        # Sequential fallback (existing behavior)
        return self._batch_match_sequential(items, ...)

    return self._batch_match_parallel(items, ..., on_progress=on_progress, ...)

def _batch_match_parallel(self, items, ..., on_progress=None, ...):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    progress_lock = threading.Lock()
    call_count_lock = threading.Lock()

    # Shared immutable OpenAI client (httpx is thread-safe)
    base_client = self._get_client().client

    def match_one(index_and_item):
        index, item = index_and_item
        # Per-thread audited client wrapping the shared base client
        thread_client = AuditedOpenAIClient(base_client, self._get_client()._sink)
        thread_client.set_context(claim_id=claim_id, call_purpose="coverage_analysis")

        result = self._match_single(item, thread_client, ...)

        with call_count_lock:
            self._llm_calls += 1
        if on_progress:
            with progress_lock:
                on_progress(1)

        return (index, result)

    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=self.config.max_concurrent) as executor:
        futures = [executor.submit(match_one, (i, item)) for i, item in enumerate(items)]
        for future in as_completed(futures):
            index, result = future.result()
            results[index] = result

    return results
```

### Step 4: Extract `_match_single()` from `match()`

File: `llm_matcher.py`

Extract the prompt-build + API-call + parse + confidence-cap logic from `match()` into a `_match_single()` method that accepts a client as a parameter instead of using `self._get_client()`. The existing `match()` method becomes a thin wrapper calling `_match_single(item, self._get_client(), ...)`.

### Step 5: Update `AnalyzerConfig` to pass through concurrency setting

File: `analyzer.py`

Add `llm_max_concurrent: int = 5` to `AnalyzerConfig` (line ~230). Pass this through when constructing `LLMMatcherConfig`.

### Step 6: Update tests

- Add unit test for parallel `batch_match()` with mocked client
- Add test verifying result ordering is preserved
- Add test verifying call count is correct under parallelism
- Add test verifying `max_concurrent=1` falls back to sequential

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| OpenAI rate limits (RPM/TPM) | Default `max_concurrent=5` is conservative. Configurable. OpenAI gpt-4o tier typically allows 500+ RPM. |
| Audit log corruption | Each thread gets its own `AuditedOpenAIClient` instance. File sink has module-level lock. |
| Result ordering | Use indexed submission + collect by index, not `executor.map()` (which blocks on first result). |
| Progress callback races | Lock around `on_progress()` calls. |
| Exception in one thread | `future.result()` re-raises per-item. Catch and return `REVIEW_NEEDED` (matching existing error handling in `match()` at line 366). |
| Regression | `max_concurrent=1` gives bit-for-bit identical behavior to current code. Use as config-level kill switch. |

## Estimated Impact

- **Latency**: 15 items @ 1.5s each: 22.5s serial → ~4.5s parallel (5 workers, 3 rounds). ~5x speedup on the LLM stage.
- **Cost**: No change — same number of API calls, same tokens.
- **Accuracy**: No change — same per-item prompts, same parsing, same validation.

## Future Enhancement: Two-Pass Parts-Then-Labor

Currently, `covered_parts_in_claim` (injected at `analyzer.py:1686-1696`) only contains parts matched by rules/keywords/part-lookup — not parts resolved by the LLM itself. This means if both a part and its labor item fall through to the LLM stage, the labor call won't have context that the part was covered.

**After** parallelization is stable, a follow-up improvement would split LLM items into two groups:
1. **Pass 1 (parallel):** All parts items → get LLM coverage decisions
2. **Update context:** Add LLM-covered parts to `covered_parts_in_claim`
3. **Pass 2 (parallel):** All labor items → now with full parts context

This is a separate change and should not be mixed into the parallelization work.

## Files Changed

| File | Change |
|------|--------|
| `src/context_builder/coverage/llm_matcher.py` | Add `max_concurrent` config, parallel `batch_match()`, extract `_match_single()` |
| `src/context_builder/coverage/analyzer.py` | Add `llm_max_concurrent` to `AnalyzerConfig`, pass through to LLM matcher |
| `tests/unit/test_llm_matcher.py` | Add parallel batch tests |
| `workspaces/nsa/config/coverage/nsa_coverage_config.yaml` | Add `max_concurrent: 5` (optional, has default) |
