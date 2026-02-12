# REFACTOR-04: LLM-First Coverage Analysis

**Date:** 2026-02-12
**Status:** Planned
**Review:** Based on `docs/REVIEW-coverage-assessment-complexity.md`

## Context

The coverage analysis system has accumulated ~7,000 lines of deterministic heuristics (substring matching, synonym fallbacks, proportionality guards, multi-tier fallbacks) that were added incrementally to handle edge cases. Each fix adds a fallback, each fallback adds a special case, and each special case needs its own test. The result is brittle code that overfits to the test dataset and is difficult to maintain.

**This refactoring shifts to an LLM-first architecture:** the LLM becomes the primary decision-maker for coverage classification, labor linkage, and primary repair identification. Deterministic rules are kept only for clear-cut binary decisions (fees, explicit exclusions, zero-price items) and math (payout calculation). Every decision gets a `decision_source` tag for full traceability.

**Key design decisions:**
- Keywords become prompt hints only -- ALL non-rule items go through LLM classification
- Clean break: new analyses use new pipeline, old files remain as-is
- Customer config changes (NSA) included in this plan
- Part number lookup is optional (production may not have it)

---

## Agent Team Implementation Strategy

This refactoring is well-suited for a **2-3 agent team** using git worktrees for parallel execution.

### Recommended Team Layout

| Agent | Worktree | Branch | Phases | Why |
|-------|----------|--------|--------|-----|
| **Lead** | main | `refactor/04-llm-first` | Phases 1, 2, 3 | Sequential core pipeline changes -- each phase depends on the previous |
| **Config Agent** | wt1 | `refactor/04-customer-config` | Phase 4 | Independent: customer config cleanup has no dependency on core changes |
| **Test Agent** | wt2 | `refactor/04-test-refactor` | Phase 5 | Can start test factories early, but full refactoring needs Phases 1-3 merged first |

### Execution Timeline

```
Week 1:  Lead starts Phase 1 (Foundation)
         Config Agent starts Phase 4 (Customer Config) -- in parallel
         Test Agent creates test helpers/factories (Phase 5.1) -- in parallel

Week 2:  Lead does Phase 2 (LLM Classification)
         Config Agent finishes Phase 4, merges
         Test Agent waits or assists with Phase 2 test updates

Week 3:  Lead does Phase 3 (LLM Labor/Primary)
         Test Agent does Phase 5 (property tests, magic number cleanup)

Week 4:  Lead does Phase 6 (Cleanup) after all merges
         Final integration testing
```

### Merge Order

1. Phase 4 (customer config) -> merge to main first (no conflicts with core)
2. Phase 1 (foundation) -> merge to main
3. Phase 2 (LLM classification) -> merge to main
4. Phase 3 (LLM labor/primary) -> merge to main
5. Phase 5 (test refactoring) -> merge to main (rebased on phases 1-3)
6. Phase 6 (cleanup) -> merge to main last

### When NOT to Use a Team

If doing this solo, execute phases strictly in order: 1 -> 4 -> 2 -> 3 -> 5 -> 6. Phase 4 can slot in anywhere before Phase 5.

---

## Phase 1: Foundation -- Traceability & Config Externalization

**Goal:** Every coverage decision is auditable with a clear `decision_source`. All hardcoded vocabulary and thresholds move to config. No behavior changes.

**Size: M**

### 1.1 Add `DecisionSource` enum to schemas

**File: `src/context_builder/coverage/schemas.py`**

Add new enum after `TraceAction`:
```python
class DecisionSource(str, Enum):
    """Source of a coverage decision for audit trail."""
    RULE = "rule"
    PART_NUMBER = "part_number"
    KEYWORD = "keyword"
    LLM = "llm"
    PROMOTION = "promotion"
    DEMOTION = "demotion"
    VALIDATION = "validation"
```

Add field to `TraceStep`:
```python
decision_source: Optional[DecisionSource] = Field(
    None, description="Source of this decision (rule, llm, promotion, etc.)"
)
```

### 1.2 Add `decision_source` parameter to TraceBuilder

**File: `src/context_builder/coverage/trace.py`**

Add `decision_source: Optional[DecisionSource] = None` to `add()` method. Pass through to `TraceStep` constructor.

### 1.3 Tag all existing trace calls with decision_source

**Files to update:**
- `src/context_builder/coverage/rule_engine.py` -- all `tb.add()` -> `decision_source=DecisionSource.RULE`
- `src/context_builder/coverage/keyword_matcher.py` -- all `tb.add()` -> `DecisionSource.KEYWORD`
- `src/context_builder/coverage/llm_matcher.py` -- all `tb.add()` -> `DecisionSource.LLM`
- `src/context_builder/coverage/part_number_lookup.py` -- all `tb.add()` -> `DecisionSource.PART_NUMBER`
- `src/context_builder/coverage/analyzer.py` -- post-processing `tb.add()`:
  - labor_follows_parts, ancillary_promotion, parts_for_repair, primary_repair_boost -> `DecisionSource.PROMOTION`
  - labor_demotion, nominal_price_audit -> `DecisionSource.DEMOTION`
  - policy_list_check, llm_validation -> `DecisionSource.VALIDATION`

### 1.4 Externalize hardcoded vocabulary to config

**File: `src/context_builder/coverage/analyzer.py`**
- Move `_GENERIC_LABOR_DESCRIPTIONS` (line ~1361) to `AnalyzerConfig.generic_labor_descriptions: Set[str]` with current values as default
- Load from YAML key `analyzer.generic_labor_descriptions`

**File: `src/context_builder/coverage/llm_matcher.py`**
- Move `vague_terms` (line ~271 in `_detect_vague_description()`) to `LLMMatcherConfig.vague_description_terms: Set[str]`
- Load from YAML key `llm.vague_description_terms`

### 1.5 Externalize hardcoded thresholds to config

**File: `src/context_builder/coverage/analyzer.py`**
- `2.0` proportionality guard -> `AnalyzerConfig.labor_proportionality_max_ratio: float = 2.0`
- Promotion confidence values scattered in post-processing -> `AnalyzerConfig.promotion_min_confidence: float = 0.75`

**File: `src/context_builder/coverage/keyword_matcher.py`**
- `0.7` consumable penalty -> `KeywordConfig.consumable_confidence_penalty: float = 0.7`
- `0.05` context hint boost -> `KeywordConfig.context_confidence_boost: float = 0.05`

**File: `src/context_builder/coverage/rule_engine.py`**
- `0.45` review_needed confidence -> `RuleConfig.review_needed_confidence: float = 0.45`

### 1.6 Update NSA customer config YAML

**File: `workspaces/nsa/config/coverage/nsa_coverage_config.yaml`** (and copy to customer repo)
- Add `generic_labor_descriptions`, `vague_description_terms` lists
- Add threshold values under their respective sections

### 1.7 Tests

**New: `tests/unit/test_coverage_decision_source.py`**
- Property test: every TraceStep in a completed analysis has non-None decision_source
- Test backward compat: old traces (without decision_source) deserialize correctly

**Modify: existing coverage test files**
- Update trace assertions to include decision_source where applicable

### Verification
- `python -m pytest tests/unit/test_coverage*.py --no-cov -q` -- all existing tests pass
- Run `python -m context_builder.cli coverage --claim-id CLM-001` on a test claim -- verify `decision_source` appears in coverage_analysis.json trace steps

---

## Phase 2: LLM-First Coverage Classification

**Goal:** Replace keyword matcher + policy list verification + LLM fallback with a single LLM-first stage. Keywords become hints in the prompt.

**Size: L** | **Depends on: Phase 1**

### 2.1 Add `generate_hints()` to keyword matcher

**File: `src/context_builder/coverage/keyword_matcher.py`**

New method that returns advisory data without making coverage decisions:
```python
def generate_hints(self, items: List[Dict]) -> List[Optional[Dict]]:
    """Return keyword match hints per item (category, confidence) without deciding coverage."""
    # Returns: [{"keyword": str, "category": str, "component": Optional[str], "confidence": float} | None]
```

Reuses existing matching logic but returns raw matches instead of `LineItemCoverage`. Existing `match()` / `batch_match()` remain but will no longer be called from the analyzer.

### 2.2 Add `classify_items()` to LLM matcher

**File: `src/context_builder/coverage/llm_matcher.py`**

New method that classifies ALL items (not just leftovers):
```python
def classify_items(
    self,
    items: List[Dict[str, Any]],
    covered_components: Dict[str, List[str]],
    excluded_components: Dict[str, List[str]],
    keyword_hints: Optional[List[Optional[Dict]]] = None,
    part_number_context: Optional[List[Optional[Dict]]] = None,
    claim_id: Optional[str] = None,
    on_progress: Optional[Callable] = None,
) -> List[LineItemCoverage]:
```

- Uses existing `_match_single()` internally but with enriched prompt
- Keyword hints and part number context injected into each item's prompt
- Policy list (covered_components + exclusions) included in system prompt as the source of truth
- Reuses existing retry logic, confidence thresholds, vague description detection, and audit trail
- New prompt loaded from workspace config (`llm.prompt_name_classify`, default: `"coverage_classify"`)

### 2.3 Create new prompt template

**New file: `workspaces/nsa/config/coverage/prompts/nsa_coverage_classify.md`**

Prompt structure:
- System: "You are a coverage analyst. Determine if each invoice item is covered under this warranty policy."
- Policy matrix: categories + components + exclusions (structured)
- For each item: description, type, price, keyword hint (if any), part number info (if any)
- Response: `{is_covered, category, matched_component, confidence, reasoning}`

This replaces the current generic coverage prompt with one that has full policy context.

### 2.4 Restructure analyzer pipeline

**File: `src/context_builder/coverage/analyzer.py`**

Replace Stages 2-5 in `analyze()` with:

```
Stage 1: Rule engine (UNCHANGED -- deterministic exclusions)
Stage 2: Part number lookup (OPTIONAL -- provides hints, not decisions)
Stage 3: Keyword hints (generate_hints() -- advisory only, not decisions)
Stage 4: LLM classification (ALL remaining items, with hints from stages 2+3)
```

**Specific changes:**
- After rule engine, collect remaining items
- Run `part_number_lookup` if available -> produce hints (not LineItemCoverage)
- Run `keyword_matcher.generate_hints()` -> produce hints
- Call `llm_matcher.classify_items()` with all remaining items + both hint sets
- Keep `_validate_llm_coverage_decision()` as a safety net (checks against exclusion list)

**Remove from analyze():**
- Stage 2.5 policy list verification block (~85 lines) -- policy list is now in the LLM prompt
- `_match_labor_by_component_extraction()` call -- LLM handles labor context

**Remove methods (mark as deprecated, delete in Phase 6):**
- `_is_component_in_policy_list()` and its 4 fallback paths (~163 lines)
- `_match_labor_by_component_extraction()` (~240 lines)
- The keyword batch_match integration code

### 2.5 Update part_number_lookup for hint mode

**File: `src/context_builder/coverage/part_number_lookup.py`**

Add `lookup_as_hint()` method that returns hint dicts instead of `LineItemCoverage`. If part number found, returns `{"part_number": str, "system": str, "component": str, "source": "assumptions"}`. If not found, returns `None`.

Existing `lookup()` remains for backward compatibility.

### 2.6 Update CoverageMetadata

**File: `src/context_builder/coverage/schemas.py`**

- `keywords_applied` field will now always be 0 (hints don't count as "applied"). Keep field for backward compat but update description.
- Add `keyword_hints_generated: int = 0` field
- Add `part_number_hints_generated: int = 0` field

### 2.7 Tests

**Modify: `tests/unit/test_coverage_analyzer.py`**
- Update tests that expected keyword-matched items -> now LLM-matched (mock LLM to return same category)
- Add: keyword hints passed to LLM classify call
- Add: part number hints passed to LLM classify call
- Add: graceful degradation when no part number lookup available

**New: `tests/unit/test_keyword_hints.py`**
- Test `generate_hints()` returns advisory dicts (not LineItemCoverage)
- Test hints include category, component, confidence

**New: `tests/unit/test_llm_classify.py`**
- Test `classify_items()` with keyword hints
- Test `classify_items()` without hints (still works)
- Test exclusion validation still catches excluded items

### Verification
- `python -m pytest tests/unit/ --no-cov -q` -- all tests pass
- Run coverage analysis on 2-3 test claims and compare results before/after
- Verify every non-rule item now has `match_method=LLM` and `decision_source=LLM`
- Verify `decision_trace` includes keyword hint info

---

## Phase 3: LLM-First Labor & Primary Repair

**Goal:** Replace 3-algorithm labor linkage and 5-tier primary repair with LLM-first. Remove proportionality guard and zero-payout rescue.

**Size: L** | **Depends on: Phase 2**

### 3.1 Add `classify_labor_linkage()` to LLM matcher

**File: `src/context_builder/coverage/llm_matcher.py`**

New method:
```python
def classify_labor_linkage(
    self,
    labor_items: List[Dict],
    parts_items: List[Dict],  # With coverage status from Stage 4
    primary_repair: Optional[Dict] = None,
    claim_id: Optional[str] = None,
) -> List[Dict]:
    """Link labor items to parts. Returns: [{index, linked_part_indices, is_covered, confidence, reasoning}]"""
```

- Single LLM call that sees ALL labor and ALL parts together
- Prompt: "Which labor items are mechanically necessary for which covered parts?"
- Result: per-labor-item verdict with linked part references
- New prompt: `llm.prompt_name_labor_linkage` (default: `"labor_linkage"`)

### 3.2 Simplify primary repair determination

**File: `src/context_builder/coverage/analyzer.py`**

Replace `_determine_primary_repair()` (~170 lines, 5 tiers):

**New flow (2 tiers only):**
1. **LLM primary** (existing `_llm_determine_primary()`) -- always attempted first
2. **Deterministic fallback**: highest-value covered part (simple, one line) -- sanity check only

Remove:
- Tier 1b (highest covered any type)
- Tier 1c (highest uncovered with component)
- Tier 2 (repair context keyword detection)
- Set `use_llm_primary_repair=True` as default in AnalyzerConfig

### 3.3 Replace labor-follows-parts

**File: `src/context_builder/coverage/analyzer.py`**

Replace `_apply_labor_follows_parts()` (238 lines, 3 algorithms):

**New flow:**
1. **Part-number matching** (Strategy 1 -- keep, deterministic pre-check): if labor description contains a covered part's code, link them
2. **LLM labor linkage** (new): for all remaining labor, call `classify_labor_linkage()`
3. Apply results: promote labor items linked to covered parts

Remove:
- Strategy 2 (simple invoice rule)
- Strategy 3 (repair-context keyword matching)
- Proportionality guard (2x multiplier)

### 3.4 Simplify primary repair boost

**File: `src/context_builder/coverage/analyzer.py`**

Replace `_promote_items_for_covered_primary_repair()` (235 lines, Mode 1 + Mode 2):

Remove:
- Mode 1 (zero-payout rescue) -- unnecessary when LLM is primary classifier
- Mode 2 wrapper -- merge with new labor linkage from 3.3

What remains: if primary repair is covered and LLM labor linkage identified relevant labor, apply promotion trace.

### 3.5 Remove redundant post-processing

**File: `src/context_builder/coverage/analyzer.py`**

Remove:
- `_promote_ancillary_parts()` (~62 lines) -- LLM already considers ancillary parts in context
- `_promote_parts_for_covered_repair()` (~85 lines) -- absorbed by LLM labor linkage

Keep:
- `_demote_labor_without_covered_parts()` -- pure logic safety net
- `_flag_nominal_price_labor()` -- deterministic audit rule
- `_validate_llm_coverage_decision()` -- exclusion list safety net

### 3.6 New simplified post-processing pipeline

```
1. Primary repair determination (LLM-first, deterministic fallback)
2. LLM labor linkage (links labor to parts, determines labor coverage)
3. Orphan labor demotion (safety net -- demote labor with no covered parts)
4. Nominal-price labor flagging (audit rule)
5. LLM validation (exclusion list safety net)
```

### 3.7 Create new prompt templates

**New: `workspaces/nsa/config/coverage/prompts/nsa_labor_linkage.md`**
- "Here are parts and labor from an invoice. Which labor items relate to which parts? Is each labor item necessary for the repair?"

### 3.8 Tests

**Remove/simplify in `tests/unit/test_coverage_analyzer.py`:**
- Proportionality guard tests
- Multi-strategy labor linkage tests
- Tier 1b, 1c, Tier 2 primary repair tests
- Mode 1 zero-payout rescue tests
- `_promote_ancillary_parts` tests
- `_promote_parts_for_covered_repair` tests

**Add:**
- Tests for `classify_labor_linkage()` (mocked LLM)
- Tests for simplified 2-tier primary repair
- Property test: every labor item is either linked to a part or NOT_COVERED
- End-to-end: LLM labor linkage + primary repair in sequence

### Estimated lines removed from analyzer.py: ~700

### Verification
- `python -m pytest tests/unit/ --no-cov -q` -- all tests pass
- Run coverage on 2-3 test claims, compare labor classification before/after
- Verify `decision_trace` shows clear LLM labor linkage reasoning

---

## Phase 4: Customer Config Cleanup (NSA)

**Goal:** Move all remaining hardcoded business constants to customer config. Fix fragile patterns.

**Size: S** | **Depends on: None (can run in parallel with Phase 2/3)**

### 4.1 Move fee caps to config YAML

**File: `C:/Users/fbrun/Documents/GitHub/context-builder-nsa/decision/engine.py`**
- Extract `max_diag_fee = 250.0` and `max_towing = 500.0` to decision config YAML
- Load from `{workspace}/config/decision/fee_caps.yaml` or add to existing decision config

### 4.2 Move service interval fallbacks to config

**File: `C:/Users/fbrun/Documents/GitHub/context-builder-nsa/screening/screener.py`**
- Extract `_FALLBACK_INTERVAL = {"km_max": 30000, "months_max": 24}` to screener config
- Extract VW Group (15,000km/12mo), Mercedes (25,000km/12mo) hardcoded intervals to config
- Load from `{workspace}/config/screening/service_interval_fallbacks.yaml`

### 4.3 Replace assumption question strings with clause IDs

**File: `C:/Users/fbrun/Documents/GitHub/context-builder-nsa/decision/engine.py`**
- `_ASSUMPTION_STATEMENTS` dict: change keys from question strings to clause reference IDs (e.g., `"2.2.A"`)
- Update `denial_clauses.json` to include an `assumption_id` field on each clause
- Lookup by `assumption_id` instead of matching exact question text

### 4.4 Unify keyword lists

- `ASSISTANCE_KEYWORDS` in screener.py and `_TOWING_KEYWORDS` / `_DIAGNOSTIC_KEYWORDS` in engine.py have overlapping but inconsistent terms
- Create single `{workspace}/config/keyword_lists.yaml` with sections:
  - `assistance_keywords`, `diagnostic_keywords`, `towing_keywords`
- Both screener and decision engine load from this file

### 4.5 Rename mock service files

**Files in customer repo:**
- Rename `labor_rate_mock.py` -> `labor_rate_service.py`
- Rename `parts_classifier_mock.py` -> `parts_classifier_service.py`
- Update all import references in engine.py

### 4.6 Document all thresholds

**New file: `docs/THRESHOLDS.md`**
- Catalog every threshold with: current value, config location, rationale, origin date

### Tests
- Update customer-specific tests that reference old file names or hardcoded values
- Add test: changing a threshold in YAML changes behavior

### Verification
- Run `python -m context_builder.cli assess --claim-id CLM-001` -- same results with externalized config
- Verify no hardcoded business constants remain in Python files (grep for magic numbers)

---

## Phase 5: Test Refactoring

**Goal:** Replace magic numbers with property-based assertions. Remove circular tests. Add trace validation.

**Size: M** | **Depends on: Phases 1-3**

### 5.1 Create test data factories

**New file: `tests/unit/coverage_test_helpers.py`**
- `make_line_item(**overrides)` -- valid line item dict with sensible defaults
- `make_coverage_result(**overrides)` -- valid LineItemCoverage
- `make_policy(categories=...)` -- policy coverage dict
- Replace the 6+ `_make_item()` methods scattered across test files

### 5.2 Replace magic numbers in coverage tests

**File: `tests/unit/test_coverage_analyzer.py`**
- Replace `assert item.covered_amount == 800.0` with relative assertions: `assert item.covered_amount == item.total_price * (coverage_percent / 100)`
- Replace `assert item.match_confidence == 0.85` with range: `assert item.match_confidence >= 0.80`
- Replace fixed price fixtures with factory-generated values

### 5.3 Replace magic numbers in assessment tests

**Files:**
- `tests/unit/test_assessment_processor_screening.py` -- replace `4500.0, 450.0, 80.0, 4050.0` with factory defaults
- `tests/unit/test_assessment_response.py` -- remove `assert MIN_EXPECTED_CHECKS == 7` (circular)
- `tests/unit/test_decision_stage.py` -- replace verdict string tuples with enum references

### 5.4 Add property-based tests

**New file: `tests/unit/test_coverage_properties.py`**

Coverage invariants:
- `0.0 <= item.match_confidence <= 1.0` for all items
- `item.covered_amount + item.not_covered_amount == item.total_price` (float tolerance)
- `item.covered_amount >= 0` and `item.not_covered_amount >= 0`
- If `COVERED` then `covered_amount > 0` (unless zero-price item)
- If `NOT_COVERED` then `covered_amount == 0`
- `items_covered + items_not_covered + items_review_needed == len(line_items)`

Trace invariants:
- Every item has at least one trace step
- Every trace step has `decision_source` (not None)
- Last decisive trace step verdict matches item's `coverage_status`

### 5.5 Remove test anti-patterns

- Remove tests that assert a constant equals itself
- Remove single-field mapping tests (consolidate into integrated transformation tests)
- Remove mock screener implementations from test files -> move to `tests/fixtures/`

### Verification
- `python -m pytest tests/unit/ --no-cov -q` -- all tests pass
- Coverage report shows no decrease in meaningful coverage

---

## Phase 6: Simplification & Cleanup

**Goal:** Delete dead code, extract post-processing to its own module, consolidate analyzer.py.

**Size: M** | **Depends on: All previous phases**

### 6.1 Delete dead code from analyzer.py

Remove methods no longer called:
- `_is_component_in_policy_list()` and all 4 fallback paths (~163 lines)
- `_match_labor_by_component_extraction()` (~240 lines)
- `_promote_ancillary_parts()` (~62 lines)
- `_promote_parts_for_covered_repair()` (~85 lines)
- Mode 1 zero-payout rescue in `_promote_items_for_covered_primary_repair()` (~70 lines)
- Tier 1b, 1c, Tier 2 primary repair fallbacks (~100 lines)
- `_is_generic_labor_description()` static method
- `_GENERIC_LABOR_DESCRIPTIONS` class constant (moved to config)
- Keyword batch_match integration block in `analyze()`

### 6.2 Extract post-processing to separate module

**New file: `src/context_builder/coverage/post_processing.py`**

Move remaining post-processing from analyzer.py as standalone functions:
- `apply_labor_linkage(items, labor_verdicts)` -- applies LLM labor linkage results
- `demote_orphan_labor(items)` -- demotes labor without covered parts
- `flag_nominal_price_labor(items, threshold)` -- flags suspiciously cheap labor
- `validate_against_exclusions(items, excluded_components)` -- safety net

Analyzer calls these functions instead of internal methods.

### 6.3 Consolidate analyzer.py

**Target: ~1,400 lines** (from ~3,100)

What remains in analyzer.py:
- `CoverageAnalyzer.__init__()` and `from_config_path()`
- `analyze()` -- the simplified 4-stage pipeline + post-processing calls
- `_determine_coverage_percent()` -- pure math
- `_extract_covered_categories()` -- simple helper
- `_calculate_summary()` -- pure math
- Config dataclasses (AnalyzerConfig, ComponentConfig)

### 6.4 Update keyword_matcher.py

- Mark `match()` and `batch_match()` as deprecated with `warnings.warn()`
- Primary public method is now `generate_hints()`
- Keep module name (no rename -- too disruptive)

### 6.5 Update PrimaryRepairResult docstring

**File: `src/context_builder/coverage/schemas.py`**

Update the docstring from "three-tier approach" to reflect new 2-tier (LLM-first + deterministic fallback).

### 6.6 Update documentation

**Update: `docs/REVIEW-coverage-assessment-complexity.md`**
- Add "Resolution" section documenting what was done

**Update: `CLAUDE.md`**
- Remove tech debt note about COMPONENT_SYNONYMS/CATEGORY_ALIASES (resolved in Phase 1)
- Update architecture section to reflect simplified pipeline

**New: `docs/ARCHITECTURE-coverage-pipeline.md`**
- Document the new 4-stage pipeline
- Document decision_source audit trail
- Document config externalization pattern
- Include migration notes

### 6.7 Delete dead test code

- Remove test classes for deleted methods
- Remove test fixtures no longer needed
- Consolidate scattered helper methods into `coverage_test_helpers.py`

### Verification
- `python -m pytest tests/unit/ --no-cov -q` -- all tests pass
- `python -m pytest tests/unit/ -v --tb=short` -- verify no import errors from moved functions
- Run full coverage analysis on 3 test claims -- verify identical or improved results
- Manual review: no method in analyzer.py is >50 lines

---

## Line Count Budget

| File | Before | After | Change |
|------|--------|-------|--------|
| `coverage/analyzer.py` | ~3,100 | ~1,400 | **-1,700** |
| `coverage/llm_matcher.py` | ~1,180 | ~1,500 | +320 (new methods) |
| `coverage/keyword_matcher.py` | ~300 | ~380 | +80 (generate_hints) |
| `coverage/rule_engine.py` | ~460 | ~460 | 0 (unchanged) |
| `coverage/part_number_lookup.py` | ~320 | ~350 | +30 (hint mode) |
| `coverage/schemas.py` | ~296 | ~320 | +24 (DecisionSource) |
| `coverage/trace.py` | ~53 | ~60 | +7 |
| `coverage/post_processing.py` | 0 | ~300 | +300 (new) |
| **Core total** | **~5,709** | **~4,770** | **-939 (-16%)** |
| Test files | ~4,300 | ~3,200 | **-1,100 (-26%)** |

The real win is not line count but **branching complexity**: 4-path policy list check, 3-algorithm labor linkage, 5-tier primary repair, Mode 1+2 boost all become single LLM calls with simple deterministic fallbacks.

---

## Execution Order & Dependencies

```
Phase 1 (Foundation) -----> Phase 2 (LLM Classification) -----> Phase 3 (LLM Labor/Primary)
                                                                         |
Phase 4 (Customer Config) -- runs in parallel with 2/3 -----------------+
                                                                         v
                                                              Phase 5 (Test Refactoring)
                                                                         |
                                                                         v
                                                              Phase 6 (Cleanup)
```

Each phase is independently deployable and testable. Phase 4 can run in parallel with Phases 2-3.

---

## Risk Mitigation

- **LLM cost increase**: More items go to LLM, but keyword hints in prompt improve accuracy (fewer retries/reviews). Monitor token usage. `llm_max_items` config cap remains.
- **Behavioral changes**: Some items will get different classifications. Run before/after comparison on full test dataset after each phase.
- **Regression risk**: Each phase keeps existing tests green. Property-based tests (Phase 5) catch invariant violations.
- **Rollback**: Each phase is a separate commit/PR. Config flag `use_llm_first: true` (default) can be set to `false` to revert to keyword-first pipeline if needed (keep old code paths through Phase 5, delete in Phase 6 only).
