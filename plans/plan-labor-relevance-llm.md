# Plan: Replace Blanket Labor Promotion with LLM Labor Relevance Check

## Context

Deep eval of claims 64535 and 65196 revealed that `_promote_items_for_covered_primary_repair()` Mode 2 in the coverage analyzer blindly promotes ALL uncovered labor when a primary repair is covered. This causes overpayments:
- **65196**: Battery charging (+24), lane assist calibration (+120), and diagnostic (+360) all wrongly promoted for a valve replacement — **+504 CHF excess labor**
- **64535**: Diagnostic labor (+562.50) wrongly promoted for an oil separator replacement

The current approach (reject all labor via LLM → blanket promote → guard with exclusion heuristics) is complex and fragile. The root cause: the LLM evaluates labor without knowing what the primary repair is.

**Fix**: After determining the primary repair, make ONE batch LLM call asking "which of these labor items are mechanically necessary for this specific repair?" This replaces ~130 lines of boost/guard logic with a single context-aware LLM decision.

## Changes

### 1. Add `classify_labor_for_primary_repair()` to `LLMMatcher`

**File**: `src/context_builder/coverage/llm_matcher.py`

New method signature:
```python
def classify_labor_for_primary_repair(
    self,
    labor_items: List[Dict[str, Any]],   # [{index, description, item_code, total_price}]
    primary_component: str,
    primary_category: str,
    covered_parts_in_claim: List[Dict[str, str]],
    claim_id: Optional[str] = None,
) -> List[Dict[str, Any]]:  # [{index, is_relevant, confidence, reasoning}]
```

- Loads prompt via `load_prompt(self.config.labor_relevance_prompt_name, ...)`
- Falls back to inline prompt if file not found (existing pattern from `_build_prompt_messages`)
- ONE LLM call with `response_format={"type": "json_object"}`
- Retry logic (3 attempts with exponential backoff, same as `_match_single`)
- Increments `self._llm_calls`
- New helper `_parse_labor_relevance_response()` to parse `{"labor_items": [{index, is_relevant, confidence, reasoning}]}`
- Missing indices default to `is_relevant=False` (conservative)

Add `labor_relevance_prompt_name: str = "labor_relevance"` to `LLMMatcherConfig` dataclass + `from_dict()`.

### 2. Create prompt templates

**Customer prompt**: `workspaces/nsa/config/coverage/prompts/nsa_labor_relevance.md`

```
system: You are an automotive repair labor analyst for NSA warranty claims.
Given the primary repair being performed, determine which labor items are
mechanically necessary to complete that repair.

NECESSARY labor (promote):
- Removing/reinstalling components to access the repair area (bumper, wheels, panels)
- Draining/refilling fluids required by the disassembly
- The repair labor itself (removal/installation of the covered part)

NOT NECESSARY labor (do not promote):
- Diagnostic/investigative labor (Diagnose, GFS/Geführte Funktion, recherche de panne)
- Battery charging
- Calibration/programming of unrelated systems (ADAS, lane assist, parking sensors)
- Cleaning (Reinigung, Bronze)
- Environmental/disposal fees

user: Primary repair, covered parts list, uncovered labor items to evaluate.
Return JSON: {"labor_items": [{index, is_relevant, confidence, reasoning}]}
```

**Core fallback**: `src/context_builder/prompts/labor_relevance.md` — generic version without NSA-specific terminology.

### 3. Rewrite Mode 2 of `_promote_items_for_covered_primary_repair()`

**File**: `src/context_builder/coverage/analyzer.py` (lines 1770-1901)

Replace the current Mode 2 block with:

1. Collect candidate labor items (same pre-filters: LLM-classified, NOT_COVERED, no exclusion_reason)
2. Build covered parts context from covered items
3. Call `self.llm_matcher.classify_labor_for_primary_repair()`
4. Apply verdicts: promote only items the LLM says `is_relevant=True`
5. Record trace for both promoted and not-promoted items (`primary_repair_boost_llm` stage)
6. On LLM failure: log warning, leave all candidates as NOT_COVERED, record failure in trace

**Remove**: `_EXPLICIT_EXCLUSION_PHRASES` tuple and all Mode 2 guard logic (~90 lines of item_code matching, description matching, exclusion phrase checking).

**Keep**: Mode 1 (zero-payout rescue) unchanged. Pre-filter conditions (`match_method != LLM`, `exclusion_reason` check) stay as scope limiters.

**Thread `claim_id`**: Add to method signature, pass from `analyze()` call site.

### 4. Update customer config

**File**: `workspaces/nsa/config/coverage/nsa_coverage_config.yaml`

Add under `llm:` section:
```yaml
labor_relevance_prompt_name: nsa_labor_relevance
```

### 5. Update tests

**File**: `tests/unit/test_coverage_analyzer.py`

**Remove** 3 obsolete guard tests from `TestExcludedPartGuard`:
- `test_primary_repair_boost_blocked_when_labor_code_matches_excluded`
- `test_primary_repair_boost_blocked_when_description_references_excluded`
- `test_primary_repair_boost_still_promotes_generic_labor`

**Add** new tests (mock `llm_matcher.classify_labor_for_primary_repair`):
- `test_mode2_promotes_only_llm_approved_labor` — mock LLM approves item A, denies B; verify only A promoted
- `test_mode2_skips_non_llm_classified_labor` — KEYWORD/RULE items not sent to batch LLM
- `test_mode2_skips_labor_with_exclusion_reason` — items with exclusion_reason not sent
- `test_mode2_conservative_on_llm_failure` — LLM raises exception; all candidates stay NOT_COVERED
- `test_mode2_no_llm_call_when_no_candidates` — no LLM call when all labor already covered/excluded
- `test_mode2_trace_records_llm_verdict` — promoted items have `primary_repair_boost_llm` trace

**Add** LLM matcher tests:
- `test_classify_labor_for_primary_repair_happy_path` — mock OpenAI, verify prompt construction + response parsing
- `test_classify_labor_for_primary_repair_missing_indices` — missing indices → not relevant
- `test_classify_labor_for_primary_repair_invalid_json` — parse failure → all not relevant

## Key files

| File | Change |
|------|--------|
| `src/context_builder/coverage/llm_matcher.py` | Add `classify_labor_for_primary_repair()`, `_parse_labor_relevance_response()`, config field |
| `src/context_builder/coverage/analyzer.py` | Rewrite Mode 2 (~1770-1901), thread claim_id |
| `workspaces/nsa/config/coverage/prompts/nsa_labor_relevance.md` | New customer prompt |
| `src/context_builder/prompts/labor_relevance.md` | New core fallback prompt |
| `workspaces/nsa/config/coverage/nsa_coverage_config.yaml` | Add `labor_relevance_prompt_name` |
| `tests/unit/test_coverage_analyzer.py` | Remove 3 old tests, add 9 new tests |

## Verification

1. `python -m pytest tests/unit/test_coverage_analyzer.py -v --tb=short --no-cov` — all new + existing tests pass
2. `python -m pytest tests/unit/ --no-cov -q` — full suite, no regressions
3. Re-run pipeline on claims 65196 and 64535 individually to verify the LLM correctly distinguishes:
   - 65196: promote valve R&I, fluid, bumper/wheel access labor; reject diagnostic, battery, lane assist
   - 64535: promote replacement labor; reject diagnostic labor
4. Sync customer config and commit prompt to customer repo
