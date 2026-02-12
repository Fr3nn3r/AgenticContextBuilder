# Batch Coverage Classification — Replace Per-Item LLM Calls

**Date:** 2026-02-12
**Status:** Implemented
**Depends on:** REFACTOR-04 (completed)

## Context

After REFACTOR-04, `classify_items()` delegates to `batch_match()` which makes **1 LLM call per item** via `_match_single()`. For 100 items, that's 100 API calls — each redundantly including the full policy matrix (~1000 tokens). The 35-item hard cap (`llm_max_items`) drops excess items to `REVIEW_NEEDED` without ever classifying them.

**Goal:** Batch multiple items into a single LLM call (15 items per call), following the same pattern already proven by `classify_labor_linkage()`. For 100 items, this means ~7 calls instead of 100.

### Why batch size 15?

- **Accuracy**: LLMs lose precision on structured list tasks beyond ~20 items ("lost in the middle"). 15 stays in the comfort zone.
- **Cross-item context**: Related items (part + labor + fasteners) cluster within 5-10 lines on an invoice. 15 captures these clusters.
- **Real-world fit**: Most claims have 6-27 items after rule filtering. At batch size 15, most fit in 1-2 batches.
- **Retry cost**: If a batch fails to parse, you retry 15 items — not 30.
- **Token budget**: ~3,500 input + ~1,500 output = ~5,000 tokens per batch. Well within limits.

| Items after rules | Batches (size 15) | API calls today |
|-------------------|-------------------|-----------------|
| 6 (typical small) | 1 | 6 |
| 10 (typical medium) | 1 | 10 |
| 24 (large) | 2 | 24 |
| 27 (largest seen) | 2 | 27 |

---

## Changes

### 1. `src/context_builder/coverage/llm_matcher.py`

**Config changes (`LLMMatcherConfig`):**
- Add `classification_batch_size: int = 15` — items per LLM call
- Add `batch_classify_prompt_name: str = "coverage_classify_batch"` — prompt for multi-item classification
- Update `from_dict()` to load both

**New method: `_build_batch_classify_prompt()`**
- Follows the same pattern as `_build_labor_linkage_prompt()` (lines 933-1028)
- System message: policy matrix (categories, components, exclusions, rules) — sent once per batch
- User message: numbered list of items with index, description, type, price, hints
- Expected response: JSON `{"items": [{"index": 0, "is_covered": true, "category": "...", ...}, ...]}`
- Falls back to inline prompt if workspace prompt file not found

**New method: `_parse_batch_classify_response()`**
- Follows the same pattern as `_parse_labor_linkage_response()` (lines 1030-1094)
- Parse JSON array, match results back to items by index
- Missing items get `REVIEW_NEEDED` with confidence 0.0 (conservative default)
- JSON parse failures return all items as `REVIEW_NEEDED`

**Rewrite `classify_items()`:**
- Chunk items into batches of `classification_batch_size`
- For each batch: build hints per item, build prompt, make single LLM call, parse batch response
- Post-process: apply vague description confidence capping (reuse `_detect_vague_description()`)
- Post-process: apply asymmetric thresholds (reuse logic from `_match_single()` lines 391-401)
- Build `LineItemCoverage` + `TraceBuilder` per item from batch results
- Parallelize batches with ThreadPoolExecutor (max_concurrent controls concurrency)
- Return merged results in original order

**Keep intact:** `_match_single()`, `batch_match()`, `match()` — still used by deprecated per-item flow and tests

### 2. `src/context_builder/coverage/analyzer.py`

**Config changes (`AnalyzerConfig`):**
- Replace `llm_max_items: int = 35` with `llm_classification_batch_size: int = 15`
- Update `from_dict()` accordingly
- Pass `classification_batch_size` to `LLMMatcherConfig` when creating the matcher

**Simplify Stage 3 block (lines 1547-1640):**
- Remove truncation: pass ALL remaining items to `classify_items()` (no more `skipped` list)
- Remove the "mark skipped as REVIEW_NEEDED" block (~25 lines)
- The batching is now handled inside `classify_items()`, not the analyzer

### 3. New prompt template: `workspaces/nsa/config/prompts/nsa_coverage_classify_batch.md`

Multi-item version of `nsa_coverage_classify.md`:
- System section: identical policy matrix, rules, terminology (copy from existing single-item prompt)
- User section: numbered item list instead of single item, with per-item hints inline
- Response format: JSON object with `items` array, each entry has `index` + same fields as single-item response
- `max_tokens`: 2048 (15 items × ~100 tokens output each = ~1,500, with headroom)

### 4. Tests

**Modify: `tests/unit/test_llm_classify.py`**
- Update `classify_items()` tests to expect batch calls instead of per-item delegation
- Test: batch of 5 items returns 5 results in single call
- Test: 40 items split into 3 batches of 15/15/10
- Test: parse failure returns REVIEW_NEEDED for all items in batch
- Test: vague description confidence capping still applied
- Test: hints correctly included per item in batch prompt

**Modify: `tests/unit/test_coverage_analyzer.py`**
- Remove/update tests that reference `llm_max_items` hard cap
- Add test: >35 items all get classified (no truncation)

---

## Files Modified

| File | Change |
|------|--------|
| `src/context_builder/coverage/llm_matcher.py` | New batch methods, rewrite classify_items() |
| `src/context_builder/coverage/analyzer.py` | Remove hard cap, rename config field |
| `workspaces/nsa/config/prompts/nsa_coverage_classify_batch.md` | New prompt template |
| `tests/unit/test_llm_classify.py` | Update for batch behavior |
| `tests/unit/test_coverage_analyzer.py` | Remove hard cap tests |

## Key References

- Existing batch pattern to follow: `classify_labor_linkage()` in `llm_matcher.py:836-932`
- Prompt builder pattern: `_build_labor_linkage_prompt()` in `llm_matcher.py:933-1028`
- Response parser pattern: `_parse_labor_linkage_response()` in `llm_matcher.py:1030-1094`
- Single-item prompt to adapt: `workspaces/nsa/config/prompts/nsa_coverage_classify.md`
- Current truncation to remove: `analyzer.py:1547-1640`

## Verification

1. `python -m pytest tests/unit/test_llm_classify.py tests/unit/test_coverage_analyzer.py --no-cov -q` — all tests pass
2. `python -m pytest tests/unit/test_coverage*.py --no-cov -q` — full coverage suite passes
3. Verify: items > batch_size are chunked into multiple batches, not dropped
4. Verify: each batch prompt contains policy matrix + item list + per-item hints
5. Run on 2-3 test claims — compare results before/after, verify `match_method=LLM` and trace includes batch info
