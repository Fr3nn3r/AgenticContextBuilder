# Coverage & Assessment Code Review

**Date:** 2026-02-12
**Scope:** Core coverage analyzer, assessment/decision logic, NSA customer config, test suite
**Goal:** Identify over-complexity, overfitting to test data, and opportunities to lean on LLM judgment

---

## The Big Picture Problem

There are ~7,000 lines of deterministic rules acting as guardrails around LLM calls, but the guardrails have become more complex than the thing they're guarding. The pattern is:

1. LLM makes a judgment call
2. A hardcoded rule overrides it for a specific edge case
3. A fallback catches the cases the rule missed
4. Another rule patches the fallback
5. Repeat

The result is a layered onion of heuristics where no single person can trace why a claim took a specific path.

---

## Top 5 Complexity Hotspots

### 1. `coverage/analyzer.py` -- 3,000+ lines, the core problem

**The fallback chain pattern** repeats everywhere:

- **Policy list checking** (161 lines): direct match -> synonyms -> description substring -> None
- **Labor promotion** (238 lines): 3 separate algorithms (part-number matching, simple invoice rule, repair-context keywords)
- **Primary repair boost** (268 lines): Mode 1 (zero-payout rescue) and Mode 2 (LLM labor relevance) -- both exist because earlier stages produce incomplete results

**Specific overfitting examples:**

- **Proportionality guard** (`labor > 2.0x parts value` -> reject): This almost certainly came from one bad claim. It blocks legitimate scenarios like full engine disassembly where labor dominates.
- **Gasket/seal special-casing** in part number lookup: Defers keyword matches to LLM specifically for gaskets, but not for other consumables (oil, plugs). One-off fix.
- **CULASSE removal** from keyword mappings: Substring match falsely covered "couvre-culasse" (valve cover), so the keyword was removed and handled via a completely different code path (part number synonyms). Two mechanisms for the same domain.

### 2. `coverage/llm_matcher.py` -- Asymmetric thresholds without rationale

```
min_confidence_for_coverage: 0.60  (approvals)
review_needed_threshold_not_covered: 0.40  (denials)
```

These are asymmetric on purpose ("be careful about paying out"), but there's no documented justification for these specific numbers. The vague description confidence cap of 0.50 is similarly arbitrary. Why not 0.45 or 0.55?

**Worse:** The LLM prompt duplicates rules that also exist in Python code (e.g., "Don't pick consumables as primary repair" appears both in the prompt AND in deterministic fallback logic). If one is updated, the other silently diverges.

### 3. NSA `screener.py` -- 2,034 lines, 7 levels of service interval fallback

The service interval resolution has 27 levels of fallback:

- Exact electric/hybrid match
- VW Group dual systems (hardcoded 15,000km/12mo)
- Mercedes service_a (hardcoded 25,000km/12mo)
- Ford-specific
- Fuel key lookup
- Flexible system max
- First available
- Global fallback (30,000km/24mo)

Each tier was clearly added when a test claim fell through the previous tier. The 30K/24mo fallback and the VW 15K values smell like frozen test values.

### 4. NSA `decision/engine.py` -- Hardcoded fee caps with no config source

```python
max_diag_fee = 250.0   # Where does this come from?
max_towing = 500.0      # Why this number?
```

These are business rules masquerading as constants. Plus the service modules are loaded by hardcoded filenames containing "mock" -- test infrastructure leaked into production config.

### 5. `assessment_processor.py` -- Screening always overrides LLM

```python
result["llm_payout"] = result.get("payout")  # Save LLM's opinion
result["payout"] = screening_payout            # But screening always wins
```

No variance check, no confidence comparison. If screening has a bug, the LLM's correct answer is silently discarded.

---

## Where LLM Could Replace Brittle Rules

Candidates ordered by impact:

| Current Rule-Based Logic | Lines | Why LLM Would Be Better |
|---|---|---|
| **Labor-to-parts linkage** (3 algorithms) | analyzer.py:1405-1643 | One LLM call: "Which labor items relate to which parts?" handles all edge cases |
| **Policy list verification** (4 fallback paths) | analyzer.py:684-845 | "Is this component covered under this policy?" -- LLM handles synonyms, translations, context |
| **Primary repair identification** (5-tier fallback) | analyzer.py:2272-2440 | Already partially LLM-based, but deterministic fallback adds 170 lines. Trust the LLM more. |
| **Proportionality guard** (2x multiplier) | analyzer.py:1502-1515 | "Is this labor-to-parts ratio reasonable?" -- LLM understands repair context |
| **Keyword/substring matching** (gasket, culasse workarounds) | keyword_mappings.yaml + analyzer.py | Stop fighting substring collisions. LLM call: "What system/component is this?" |
| **Fee classification** (diagnostic, towing keywords) | engine.py:57-69, 707-738 | "Is this a diagnostic fee, towing charge, or repair cost?" |

**The pattern:** Anywhere you see a substring match followed by an exclusion list followed by a special case, that's a candidate for a single LLM call.

---

## Where Rules ARE Appropriate (Don't Over-LLM)

Not everything should go to the LLM. Keep deterministic rules for:

- **Hard policy checks**: VIN matching, date validity, mileage limits -- these are binary, no judgment needed
- **Fee/exclusion patterns**: Zero-price items, explicit exclusion lists -- clear-cut
- **Payout math**: VAT calculation, deductible application -- arithmetic, not judgment
- **Format validation**: Check completeness, schema validation

---

## Test Suite Overfitting

The 440 tests show a clear pattern: tests define behavior, then code is written to match.

- Same magic numbers everywhere: `4500.0`, `450.0`, `80.0`, `4050.0` repeated across 15+ tests
- `MIN_EXPECTED_CHECKS = 7` is tested with `assert MIN_EXPECTED_CHECKS == 7` -- circular
- Expected check numbers `["1", "1b", "2", "2b", "3", "4a", "4b", "5", "5b", "6", "7"]` hardcoded in both code and tests
- Regression tests for specific `None` values suggest past production bugs were patched with targeted fixes

**The risk:** Every business rule change requires updating 10-15 tests with matching magic numbers.

---

## Pragmatic Recommendations

### Short-term (reduce complexity without rewriting)

1. **Externalize all thresholds to config YAML** -- confidence multipliers, proportionality guards, fee caps, service interval fallbacks. One file per concern. This alone makes the system auditable.

2. **Unify keyword lists** -- `ASSISTANCE_KEYWORDS` in screener.py vs `_TOWING_KEYWORDS` in engine.py have different terms for the same domain. Single source.

3. **Add decision audit trail** -- For every coverage determination, log which path was taken (keyword match? LLM? synonym? fallback?). You can't simplify what you can't measure.

4. **Replace assumption question strings with clause IDs** -- `_ASSUMPTION_STATEMENTS` keyed by exact question text is fragile. Key by clause reference ID.

### Medium-term (shift complexity to LLM)

5. **Replace the 4-path policy list check with one LLM call** -- The biggest single simplification. Currently 161 lines of fallback chains. Could be: "Given this policy's covered components list, is [component] covered? Respond YES/NO with reasoning."

6. **Replace labor linkage heuristics with one LLM call** -- "Here are the parts and labor items on this invoice. Which labor items are associated with which parts?" Deletes 238 lines.

7. **Make primary repair identification LLM-first, not LLM-fallback** -- Currently the LLM result is one of 5 tiers. Make it the primary path and use deterministic logic only as a sanity check.

### Longer-term (architecture)

8. **Separate "match" from "decide"** -- Currently the analyzer both identifies what something is AND decides if it's covered, interleaved. Split into: Stage A (classify every line item via LLM), Stage B (apply coverage rules to classified items). Much easier to test and debug.

9. **Property-based tests instead of magic numbers** -- Test "coverage percent is 0-100" not "coverage percent is 80.0". Test "at least 7 checks exist" not "exactly these 11 check IDs".

---

## Detailed File Analysis

### Core Product (`src/context_builder/`)

| File | Lines | Complexity | Key Issues |
|---|---|---|---|
| `coverage/analyzer.py` | ~3,000 | Very High | Fallback chains, hardcoded vocabulary, proportionality guard |
| `coverage/llm_matcher.py` | ~720 | High | Arbitrary thresholds, prompt/code duplication |
| `coverage/keyword_matcher.py` | ~299 | Moderate | Arbitrary confidence penalties (0.7x, 0.9x) |
| `coverage/rule_engine.py` | ~460 | Moderate | Hardcoded rule ordering, component override special cases |
| `coverage/part_number_lookup.py` | ~320 | Moderate | Substring matching fragility |
| `pipeline/claim_stages/assessment_processor.py` | ~739 | High | Payout override, field mappings, synthetic checks |
| `pipeline/claim_stages/decision.py` | ~571 | Medium-High | Hardcoded verdict logic (6 priority levels) |
| `pipeline/claim_stages/processing.py` | ~357 | Medium | Config discovery fragility |
| `schemas/assessment_response.py` | ~279 | Low | Hardcoded expected check numbers |
| `schemas/claim_assessment.py` | ~116 | Low | Silent fallbacks between data sources |
| `api/services/assessment.py` | ~889 | High | Multiple discovery paths, silent normalizations |
| `api/services/assessment_runner.py` | ~164 | Low-Medium | Hardcoded stage list |
| `api/services/claim_assessment.py` | ~445 | High | Auto coverage override load, stage orchestration |

### NSA Customer Config (`context-builder-nsa/`)

| File | Lines | Complexity | Key Issues |
|---|---|---|---|
| `screening/screener.py` | ~2,034 | High | 27-level service interval fallback, hardcoded brand normalization |
| `decision/engine.py` | ~1,170 | Medium-High | Hardcoded fee caps (250/500), mock service filenames |
| `nsa_keyword_mappings.yaml` | ~340 | Medium | Confidence scores tuned to beat collisions (oil cooler 0.95 vs cooling 0.90) |
| `nsa_coverage_config.yaml` | ~80 | Low | Regex exclusion patterns patching false positives |
| `assumptions.json` | ~2,466 | Medium | 100+ part number mappings added incrementally from test failures |
| `denial_clauses.json` | ~278 | Low | Assumption questions as string keys (fragile) |
| `service_requirements.json` | ~2,000 | Low | Well-structured, but screener assumes fallback values |

### Test Suite

| File | Tests | Overfitting Risk |
|---|---|---|
| `test_coverage_analyzer.py` | 141 | Medium -- tests general behavior |
| `test_assessment_processor_screening.py` | 51 | High -- magic numbers, field-by-field mapping tests |
| `test_decision_stage.py` | 31 | Medium-High -- exact branching path tests |
| `test_assessment_response.py` | 34 | High -- schema enumeration, circular constant assertions |
| `test_assessment_service.py` | 45 | Medium -- multiple discovery path tests |
| `test_nsa_decision_engine.py` | 62 | Medium -- good clause coverage but coupled to JSON keys |
| `test_screening_schema.py` | 34 | Medium -- schema constraint tests |
| `test_assessment_orchestration.py` | 9 | Low -- integration-level |
| `test_claim_assessment_result.py` | 19 | Medium -- fallback chain tests |
| `test_assessment_flow.py` | 14 | High -- mock screener defines reference implementation |

---

## Summary

The system works well for known scenarios but is accumulating complexity faster than value. Each edge case fix adds a fallback, each fallback adds a special case, and each special case needs its own test. The LLM is used as a last resort when it should be used as the primary judgment engine, with deterministic rules as guardrails for clear-cut cases only.

The core question is: **do you trust the LLM to make coverage decisions?** If yes (and the labor relevance and primary repair features suggest you're moving that way), then lean into it -- replace the substring/synonym/fallback chains with direct LLM calls and use the deterministic code only for hard policy checks and math.
