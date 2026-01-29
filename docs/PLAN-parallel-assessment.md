# Plan: Parallelize Claim Assessment

**Status:** Proposed (Pending Review Fixes)
**Created:** 2026-01-29
**Updated:** 2026-01-29
**Author:** Claude

---

## Review Findings

The initial plan has critical issues that must be fixed before implementation.

### CRITICAL: Compliance JSONL Writes Not Thread-Safe

**Files:**
- `src/context_builder/services/compliance/file/llm_storage.py`
- `src/context_builder/services/compliance/file/decision_storage.py`

**Problem:** The file-based LLM/decision logs rewrite the entire JSONL file on each append (read-all → write temp → rename). With multiple threads, writes will race and records will be lost. For decisions, the hash chain will also break.

```python
# Current pattern in log_call() - NOT thread-safe
existing_content = ""
if self._path.exists():
    with open(self._path, "r", encoding="utf-8") as f:
        existing_content = f.read()  # Thread A reads
                                      # Thread B reads same content
with open(tmp_file, "w", encoding="utf-8") as f:
    f.write(existing_content)         # Thread A writes
    f.write(line)                     # Thread B overwrites, Thread A's record lost
```

**Fix Options:**
1. **Global writer lock** - Single lock per log file, serialize all writes
2. **Writer queue** - Background thread processes writes from queue
3. **True append with file locking** - Use `fcntl.flock()` / `msvcrt.locking()`
4. **For decisions** - Must enforce serialized order for hash chain integrity

**Recommended Fix:** Add `threading.Lock` per storage instance, acquired during entire read-write-rename cycle.

---

### HIGH: Shared ClaimAssessmentService Caches Not Thread-Safe

**Files:**
- `src/context_builder/api/services/claim_assessment.py`
- `src/context_builder/pipeline/claim_stages/processing.py`

**Problem:** `ClaimAssessmentService` keeps a cached `ProcessingStage` which mutates `_discovered_configs` on each `_discover_processors()` call. This is shared across threads in the proposed design.

```python
# claim_assessment.py line 54
self._processing_stage: Optional[ProcessingStage] = None

# line 278-284 - mutates shared state
if self._processing_stage is None:
    self._processing_stage = ProcessingStage()
self._processing_stage._discover_processors(self.storage.output_root)  # Mutates _discovered_configs
config = self._processing_stage._discovered_configs.get("assessment")
```

**Fix Options:**
1. **Create new service per thread** - Each thread gets its own `ClaimAssessmentService`
2. **Lock around cache access** - Guard `_load_assessment_config` with a lock
3. **Make stateless** - Create new `ProcessingStage` per call, don't cache

**Recommended Fix:** Create new `ClaimAssessmentService` instance per thread (cleanest isolation).

---

### MEDIUM: Progress Updates Can Desync

**Files:**
- `src/context_builder/utils/progress.py`
- `src/context_builder/cli.py`

**Problem:**
1. The plan locks `write()`, but `update_detail()` and `tqdm.update()` aren't protected
2. Exception handler doesn't call `progress.complete_claim()`, so progress bar won't advance

**Fix:**
- Lock all progress mutations (`update_detail`, `update_stage`, `complete_claim`)
- Ensure exceptions still call `complete_claim` and update the main bar

---

### MEDIUM: Rate-Limit Handling

**Problem:** Parallel calls will amplify 429 errors. No centralized backoff/limiting exists.

**Fix Options:**
1. **Token bucket rate limiter** - Shared limiter controls request rate
2. **Retry with exponential backoff** - Add to LLM call layer
3. **Adaptive parallelism** - Reduce workers on 429s

**Recommended Fix:** Start conservative (2-3 workers), add rate limiter in future iteration.

---

### LOW: Argument Validation

**Problem:** `--parallel` should validate `>=1` and cap to sane max to prevent accidental overuse.

**Fix:** Add validation in argparse or early in handler:
```python
parallel_workers = max(1, min(args.parallel, 8))  # Clamp to 1-8
```

---

## Implementation Order

Given the findings, implementation should proceed in this order:

1. **Phase 1: Thread-safe compliance logging** (CRITICAL)
2. **Phase 2: Thread-safe service instantiation** (HIGH)
3. **Phase 3: Thread-safe progress reporter** (MEDIUM)
4. **Phase 4: CLI changes and executor** (after above are safe)
5. **Phase 5: Rate limiting** (future enhancement)

---

## Phase 1: Thread-Safe Compliance Logging

### File: `src/context_builder/services/compliance/file/llm_storage.py`

Add class-level lock and protect the entire write cycle:

```python
import threading

class FileLLMCallSink(LLMCallSink):
    _write_lock = threading.Lock()  # Class-level lock shared across instances

    def __init__(self, storage_path: Path):
        self._path = Path(storage_path)
        self._ensure_parent_dir()

    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        self._ensure_parent_dir()

        if not record.call_id:
            record.call_id = self.generate_call_id()

        line = json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n"

        # Thread-safe write with lock
        with self._write_lock:
            tmp_file = self._path.with_suffix(".jsonl.tmp")
            try:
                existing_content = ""
                if self._path.exists():
                    with open(self._path, "r", encoding="utf-8") as f:
                        existing_content = f.read()

                with open(tmp_file, "w", encoding="utf-8") as f:
                    f.write(existing_content)
                    f.write(line)
                    f.flush()
                    os.fsync(f.fileno())

                tmp_file.replace(self._path)
                logger.debug(f"Logged LLM call {record.call_id}")
            except IOError as e:
                logger.warning(f"Failed to log LLM call: {e}")
                if tmp_file.exists():
                    tmp_file.unlink()

        return record
```

### File: `src/context_builder/services/compliance/file/decision_storage.py`

Same pattern, but CRITICAL for hash chain - must be strictly serialized:

```python
import threading

class FileDecisionAppender(DecisionAppender):
    _write_lock = threading.Lock()  # Ensures hash chain integrity

    def append(self, record: DecisionRecord) -> DecisionRecord:
        # Entire hash-chain operation must be atomic
        with self._write_lock:
            # Get previous hash
            prev_hash = self.get_last_hash()
            record.previous_hash = prev_hash

            # Compute and set record hash
            record.record_hash = self.compute_hash(record)

            # Write atomically
            # ... existing write logic ...

        return record
```

---

## Phase 2: Thread-Safe Service Instantiation

### File: `src/context_builder/cli.py` (assess command)

Create new service instances per thread instead of sharing:

```python
def assess_single_claim(claim_id: str) -> None:
    """Assess a single claim with its own service instance."""
    # Create thread-local services (no shared mutable state)
    thread_storage = FileStorage(workspace_root)
    thread_aggregation = AggregationService(thread_storage)
    thread_reconciliation = ReconciliationService(thread_storage, thread_aggregation)
    thread_assessment_service = ClaimAssessmentService(thread_storage, thread_reconciliation)

    # Now safe to call without locks
    result = thread_assessment_service.assess(
        claim_id=claim_id,
        force_reconcile=args.force_reconcile,
        on_stage_update=on_stage_update,
        on_llm_start=on_llm_start,
        on_llm_progress=on_llm_progress,
        run_context=run_context,
    )
    # ... rest of handler
```

**Alternative:** If creating services is expensive, use a lock instead:

```python
# At module level or in CLI
_assessment_lock = threading.Lock()

def assess_single_claim(claim_id: str) -> None:
    # Only lock around the cache-mutating part
    with _assessment_lock:
        result = assessment_service.assess(...)
```

But this defeats parallelism - recommend per-thread services.

---

## Phase 3: Thread-Safe Progress Reporter

### File: `src/context_builder/utils/progress.py`

Lock ALL mutations, not just write:

```python
import threading

class ProgressReporter:
    def __init__(self, mode: ProgressMode = ProgressMode.PROGRESS, parallel: int = 1):
        self.mode = mode
        self.parallel = parallel
        self._lock = threading.Lock()
        # ... rest of init

    def write(self, msg: str) -> None:
        with self._lock:
            # ... existing write logic

    def start_claims(self, claim_ids: List[str]) -> None:
        with self._lock:
            # ... existing logic

    def start_stage(self, claim_id: str, stage: str, total_steps: int = 0) -> None:
        if self.parallel > 1:
            return  # Skip in parallel mode
        with self._lock:
            # ... existing logic

    def start_detail(self, total: int, desc: str = "LLM calls", unit: str = "call") -> None:
        if self.parallel > 1:
            return
        with self._lock:
            # ... existing logic

    def update_detail(self, n: int = 1) -> None:
        if self.parallel > 1:
            return
        with self._lock:
            if self._detail_bar:
                self._detail_bar.update(n)

    def update_stage(self, n: int = 1) -> None:
        if self.parallel > 1:
            return
        with self._lock:
            if self._stage_bar:
                self._stage_bar.update(n)

    def complete_claim(self, claim_id: str, decision: str, ...) -> None:
        if self.parallel <= 1:
            self.complete_stage()

        # Build message outside lock
        msg = self._build_result_message(claim_id, decision, ...)

        with self._lock:
            if self._claims_bar:
                self._claims_bar.update(1)

        self.write(msg)  # write() has its own lock
```

### File: `src/context_builder/cli.py`

Fix exception handler to update progress:

```python
for future in as_completed(futures):
    claim_id = futures[future]
    try:
        future.result()
    except Exception as e:
        with results_lock:
            if claim_id not in results["failed"]:
                results["failed"].append(claim_id)
        # FIX: Call complete_claim for exceptions too
        progress.complete_claim(
            claim_id=claim_id,
            decision="FAILED",
            error=str(e),
        )
```

---

## Phase 4: CLI Changes

See original plan sections below for:
- `--parallel N` argument
- ThreadPoolExecutor loop
- Argument validation (clamp 1-8)

---

## Phase 5: Rate Limiting (Future)

Add token bucket or semaphore-based rate limiter:

```python
# In src/context_builder/services/rate_limiter.py
import threading
import time

class RateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.rate = requests_per_minute / 60.0  # requests per second
        self.tokens = requests_per_minute
        self.max_tokens = requests_per_minute
        self.last_update = time.time()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """Block until a token is available."""
        deadline = time.time() + timeout
        while True:
            with self._lock:
                now = time.time()
                # Refill tokens
                elapsed = now - self.last_update
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

            if time.time() >= deadline:
                return False
            time.sleep(0.1)
```

Integrate in LLM client layer for automatic throttling.

---

## Goal

Reduce assessment time from ~2-3 min/claim to ~1 min/claim by processing multiple claims concurrently.

## Current State

The CLI assess command processes claims sequentially in a simple for loop:

```python
# cli.py line 2248
for claim_id in claim_ids:
    result = assessment_service.assess(claim_id, ...)
```

Each claim must complete before the next starts. For 10 claims at ~2.5 min each, total time is ~25 minutes.

### LLM Calls Per Claim

| Stage | LLM Calls | Notes |
|-------|-----------|-------|
| Reconciliation | 0 | Pure aggregation, deterministic |
| Screening/Coverage | N | 1 call per line item needing LLM matching |
| Assessment | 1 | Main GPT-4o assessment call |

## Proposed Changes

### 1. Add `--parallel N` CLI Argument

**File:** `src/context_builder/cli.py` (around line 866)

```python
assess_parser.add_argument(
    "--parallel",
    type=int,
    default=1,
    metavar="N",
    help="Process N claims in parallel (default: 1). Use 2-4 for faster processing.",
)
```

### 2. Update Progress Reporter for Thread-Safety

**File:** `src/context_builder/utils/progress.py`

Changes needed:
- Add `threading.Lock` for thread-safe output
- Add `parallel` parameter to constructor
- Skip nested stage/detail bars in parallel mode (they conflict across threads)
- Keep main claims progress bar with thread-safe updates

Key code changes:

```python
import threading

class ProgressReporter:
    def __init__(self, mode, parallel=1):
        self._lock = threading.Lock()
        self.parallel = parallel

    def write(self, msg):
        with self._lock:  # Thread-safe output
            if TQDM_AVAILABLE and self.mode == ProgressMode.PROGRESS:
                tqdm.write(msg, file=sys.stderr)
            elif self.mode != ProgressMode.QUIET:
                print(msg, file=sys.stderr)

    def start_stage(self, claim_id, stage, total_steps=0):
        if self.parallel > 1:
            return  # Skip nested bars in parallel mode
        # ... existing code

    def start_detail(self, total, desc="LLM calls", unit="call"):
        if self.parallel > 1:
            return  # Skip nested bars in parallel mode
        # ... existing code

    def complete_claim(self, claim_id, decision, ...):
        # Thread-safe update
        with self._lock:
            if self._claims_bar:
                self._claims_bar.update(1)
        self.write(msg)  # Already thread-safe
```

Update helper function:

```python
def create_progress_reporter(verbose=False, quiet=False, logs=False, parallel=1):
    # ... determine mode
    return ProgressReporter(mode=mode, parallel=parallel)
```

### 3. Replace Sequential Loop with ThreadPoolExecutor

**File:** `src/context_builder/cli.py` (around line 2248)

```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Get parallel workers from args
parallel_workers = getattr(args, "parallel", 1)

# Thread-safe results tracking
results = {"success": [], "failed": []}
results_lock = threading.Lock()

def assess_single_claim(claim_id: str) -> None:
    """Assess a single claim (can be run in parallel)."""
    # Define progress callbacks
    def on_stage_update(stage_name, status, cid=claim_id):
        progress.start_stage(cid, stage_name)

    def on_llm_start(total):
        progress.start_detail(total, desc="LLM calls", unit="call")

    def on_llm_progress(n):
        progress.update_detail(n)

    # Run assessment
    result = assessment_service.assess(
        claim_id=claim_id,
        force_reconcile=args.force_reconcile,
        on_stage_update=on_stage_update,
        on_llm_start=on_llm_start,
        on_llm_progress=on_llm_progress,
        run_context=run_context,
    )

    # Thread-safe results update
    with results_lock:
        if result.success:
            results["success"].append(claim_id)
        else:
            results["failed"].append(claim_id)

    # Progress reporting (already thread-safe)
    if result.success:
        progress.complete_claim(
            claim_id=claim_id,
            decision=result.decision,
            confidence=result.confidence_score,
            payout=result.final_payout,
            gate=result.gate_status,
        )
    else:
        progress.complete_claim(
            claim_id=claim_id,
            decision="FAILED",
            error=result.error,
        )

# Execute claims
if parallel_workers > 1:
    # Parallel execution
    with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        futures = {
            executor.submit(assess_single_claim, claim_id): claim_id
            for claim_id in claim_ids
        }
        for future in as_completed(futures):
            claim_id = futures[future]
            try:
                future.result()
            except Exception as e:
                with results_lock:
                    if claim_id not in results["failed"]:
                        results["failed"].append(claim_id)
                progress.write(f"[X] {claim_id}: EXCEPTION - {e}")
else:
    # Sequential execution (original behavior)
    for claim_id in claim_ids:
        assess_single_claim(claim_id)
```

## Usage

```bash
# Sequential (default, same as before)
python -m context_builder.cli assess --input-folder data/claims

# 2 claims in parallel (conservative)
python -m context_builder.cli assess --input-folder data/claims --parallel 2

# 3 claims in parallel (balanced)
python -m context_builder.cli assess --all --parallel 3

# 4 claims in parallel (aggressive, check rate limits first)
python -m context_builder.cli assess --all --parallel 4
```

## Expected Performance

| Claims | Sequential (~2.5 min/claim) | Parallel (3 workers) | Speedup |
|--------|----------------------------|----------------------|---------|
| 10 | ~25 min | ~10 min | 2.5x |
| 20 | ~50 min | ~18 min | 2.8x |
| 50 | ~125 min | ~45 min | 2.8x |

Speedup is less than 3x due to:
- API rate limit throttling
- Shared I/O for file writes
- Thread coordination overhead

## OpenAI Rate Limits

GPT-4o rate limits vary by organization tier:

| Tier | Requests/min | Tokens/min |
|------|--------------|------------|
| Tier 1 | 500 | 30,000 |
| Tier 2 | 5,000 | 450,000 |
| Tier 3+ | 10,000+ | 800,000+ |

Check your limits: https://platform.openai.com/account/limits

**Recommendation:** Start with `--parallel 2`, increase if no 429 errors.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| API rate limits (429 errors) | Start conservative (2-3), increase gradually |
| Thread safety bugs | Use locks for shared state, thread-safe progress |
| Resource exhaustion | Cap at reasonable max (e.g., 8 workers) |
| Debugging difficulty | Default to sequential, parallel opt-in |

## Files Modified

| File | Changes |
|------|---------|
| `src/context_builder/cli.py` | Add `--parallel` argument, refactor loop to ThreadPoolExecutor |
| `src/context_builder/utils/progress.py` | Add thread-safety with locks, parallel mode flag |

## Backward Compatibility

- Default is `--parallel 1` (sequential) - existing behavior unchanged
- No changes to assessment logic, only orchestration
- Progress output simplified in parallel mode (no nested bars)

## Future Enhancements

1. **Async LLM calls within coverage analysis** - parallelize line item matching
2. **Adaptive rate limiting** - auto-adjust parallelism based on 429 responses
3. **Progress persistence** - resume interrupted parallel runs
