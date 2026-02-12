# Test Refactor Notes (Phase 5)

Inventory of test anti-patterns to address in Phases 5.2-5.5.
Created as part of REFACTOR-04: LLM-First Coverage Analysis.

---

## 1. Duplicate `_make_item()` Methods

**9 near-identical `_make_item()` methods** in `test_coverage_analyzer.py` alone,
each on a different test class. Most share ~90% of the same defaults with minor
variations in `match_method`, `match_confidence`, or `item_code`.

| File | Line | Class | Key differences from canonical |
|------|------|-------|-------------------------------|
| `test_coverage_analyzer.py` | 708 | `TestValidateLLMCoverageDecision` | `match_method=LLM`, `match_confidence=0.75` |
| `test_coverage_analyzer.py` | 1249 | `TestDeterminePrimaryRepair` | `match_method=KEYWORD`, `match_confidence=0.90` |
| `test_coverage_analyzer.py` | 1426 | `TestLLMPrimaryOverride` | Same as line 1249 |
| `test_coverage_analyzer.py` | 1726 | `TestLaborDemotion` | Same as line 1249 |
| `test_coverage_analyzer.py` | 1831 | `TestPrimaryRepairIsCoveredOverride` | Same as line 1249 |
| `test_coverage_analyzer.py` | 2130 | `TestRepairContext*` | `item_code=None`, `matched_component="motor"` |
| `test_coverage_analyzer.py` | 2489 | `TestPromotionModes` | `status=NOT_COVERED`, `method=LLM`, `confidence=0.60` |
| `test_coverage_analyzer.py` | 2747 | `TestProportionateLaborPromotion` | `status=NOT_COVERED`, `method=KEYWORD`, `confidence=0.85` |
| `test_coverage_analyzer.py` | 2835 | `TestNominalPriceLaborFlagging` | Specific item code + labor defaults |

**Additional `_make_keyword_item()`:**
| File | Line | Class | Notes |
|------|------|-------|-------|
| `test_coverage_analyzer.py` | 2597 | `TestKeywordComponentValidation` | `total_price=200.0`, `confidence=0.85` |

**Fix (Phase 5.2):** Replace all with `make_line_item_coverage()` from
`coverage_test_helpers.py`. Each test overrides only the fields it cares about.

---

## 2. Duplicate Screening Helpers

Same screening helper functions are defined in multiple files:

| Helper | Files |
|--------|-------|
| `_make_screening_check()` | `test_assessment_processor_screening.py:31` |
| `_make_screening_payout()` | `test_assessment_processor_screening.py:52` |
| `_make_auto_reject_screening()` | `test_assessment_processor_screening.py:94` |
| `_make_non_auto_reject_screening()` | `test_assessment_processor_screening.py:130` |
| `_make_facts()` | `test_screening.py:45`, `test_nsa_screener.py:27`, `test_screening_payout.py:60` |
| `_make_coverage_result()` | `test_screening.py:581`, `test_screening_payout.py:64` |
| `_make_screening_check()` / `_make_payout()` | `test_screening_schema.py:22,38` |

**Fix (Phase 5.2):** Consolidate into `coverage_test_helpers.py` (already done for
screening helpers) and a new `screening_test_helpers.py` for screener-specific ones.

---

## 3. Magic Number Assertions

Hard-coded confidence thresholds and amounts that should reference constants or
be expressed as relative assertions:

| File | Line(s) | Example | Issue |
|------|---------|---------|-------|
| `test_coverage_keyword_matcher.py` | 305 | `assert result.match_confidence == 0.88` | Should reference `KeywordConfig` default |
| `test_coverage_rule_engine.py` | 502, 588 | `assert result.match_confidence == 0.45` | Fastener threshold hardcoded |
| `test_coverage_analyzer.py` | 222-223 | `assert item.covered_amount == 800.0` | 80% of 1000, should be `1000.0 * 0.80` |
| `test_coverage_analyzer.py` | 1316 | `assert result.confidence == 0.80` | Primary repair confidence threshold |
| `test_coverage_analyzer.py` | 2673 | `assert keyword_matched[0].match_confidence == 0.80` | Keyword min confidence threshold |
| `test_coverage_analyzer.py` | 2859 | `assert item.match_confidence == 0.30` | Demotion confidence constant |
| `test_llm_matcher_parallel.py` | 998 | `assert result["confidence"] == 0.75` | Default LLM confidence |

**Fix (Phase 5.3):** Extract threshold constants into a test constants module,
or reference the actual config defaults.

---

## 4. Trivial/Tautological Assertions

Tests that assert a constant equals itself or test only that construction works:

| File | Line(s) | Test | Issue |
|------|---------|------|-------|
| `test_coverage_analyzer.py` | 107-111 | `test_analyzer_creation` | Only asserts `is not None` on attributes |
| `test_coverage_trace.py` | 20-26 | `test_all_values_exist` | Asserts TraceAction values == hardcoded set (fragile) |

These are not harmful but add no regression protection. Consider removing or
replacing with more meaningful assertions.

---

## 5. Mock Screener Implementations in Test Files

Each test file defines its own mock/fake implementation instead of sharing:

| File | Line | Class/Function | Notes |
|------|------|----------------|-------|
| `test_screening_stage.py` | 281 | `_MockScreener` | Full mock screener class |
| `test_api_services.py` | 7 | `FakeStorage` | Generic fake storage |
| `test_api_services.py` | 168 | `FakeAggregator` | Inline fake aggregator |
| `test_compliance_interfaces.py` | 43-119 | `MockDecisionAppender`, etc. | 7 mock classes |
| `test_pipeline_providers.py` | 11-59 | `FakeClassifier`, `FakeExtractor`, etc. | 4 fake classes |
| `test_ingestion_envelope.py` | 8 | `FakeIngestion` | Ingestion base mock |

**Fix (Phase 5.4):** Create shared fixtures in `conftest.py` or a
`test_fixtures/` module for commonly-used mocks.

---

## 6. NSA Config Dependencies in Unit Tests

Several "unit" tests depend on NSA workspace config files being present:

| File | Fixture | Config file needed |
|------|---------|-------------------|
| `test_coverage_analyzer.py` | `nsa_component_config` | `nsa_component_config.yaml` |
| `test_coverage_analyzer.py` | `nsa_rule_config` | `nsa_coverage_config.yaml` |
| `test_coverage_keyword_matcher.py` | `nsa_keyword_config` | `nsa_keyword_mappings.yaml` |
| `test_coverage_rule_engine.py` | `nsa_rule_config` | `nsa_coverage_config.yaml` |

These tests skip when config files are absent, which means they don't run in CI
without the customer config repo. This is acceptable for integration-style tests
but the pure unit tests (e.g., `TestRuleEngineDefaults`) should not depend on
external config.

**Fix (Phase 5.5):** Split into true unit tests (using inline config) and
integration tests (using NSA config). Mark integration tests with
`@pytest.mark.nsa_config`.

---

## 7. Covered Components Duplication

The `covered_components` fixture is defined independently in at least 5 test
classes within `test_coverage_analyzer.py`, each with slightly different
component lists. Use `make_covered_components()` from helpers instead.

---

## Summary of Actions by Phase

| Phase | Action |
|-------|--------|
| 5.1 | Create test helpers (this file + `coverage_test_helpers.py`) -- DONE |
| 5.2 | Replace duplicate `_make_item()` + screening helpers with shared factories |
| 5.3 | Replace magic number assertions with constants/relative assertions |
| 5.4 | Consolidate mock/fake implementations into shared fixtures |
| 5.5 | Split NSA-dependent tests, add property-based tests |
