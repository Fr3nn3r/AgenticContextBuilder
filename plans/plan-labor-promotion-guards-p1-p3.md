# Plan: P1 + P3 — Labor Promotion Guards

## Problem

All 5 labor promotion entry points in `analyzer.py` can flip labor items from NOT_COVERED to COVERED without checking:

- **P1**: Whether the labor matches `non_covered_labor_patterns` (diagnostic, inspection, calibration, etc.)
- **P3**: Whether the labor references a part that was explicitly excluded

This causes overpayment on 9 of 15 amount_mismatch claims (total impact ~4,600 CHF).

## Approach

Add two guard methods to `CoverageAnalyzer` and insert them at all 5 promotion entry points.

### Guard 1 — `_is_non_covered_labor(description)` (P1)

Delegates to existing `self.rule_engine.check_non_covered_labor(description)`. Returns `True` if the description matches any `non_covered_labor_patterns` regex (DIAGNOSE, KONTROLLE, RECHERCHE.*PANNE, etc.). Already compiled and fast.

### Guard 2 — `_labor_references_excluded_part(description, items)` (P3)

Tokenizes the labor description and compares against all NOT_COVERED parts items (those with `exclusion_reason` set). If any significant token (>=4 chars, excluding stopwords) overlaps, the labor is "for" that excluded part and should not be promoted.

### Where guards are inserted

| Promotion Method | Lines | P1 Guard | P3 Guard | Notes |
|---|---|---|---|---|
| Strategy 1: Part-number matching | ~1250 | Yes | No | Part-number match is explicit enough |
| Strategy 2: Simple invoice rule | ~1288 | Yes (defense-in-depth) | No | Generic "Arbeit" won't match patterns |
| Strategy 3: Repair-context keywords | ~1326 | Yes | **Yes** | Main P3 fix — stops timing chain labor |
| Mode 1: Zero-payout rescue | ~1585 | Yes (labor only) | No | Last resort, no covered parts to compare |
| Mode 2: Labor-follows-parts | ~1646 | Yes | **Yes** | After existing `_EXPLICIT_EXCLUSION_PHRASES` check |

## Files to modify

1. **`src/context_builder/coverage/analyzer.py`**
   - Add `_is_non_covered_labor()` (~15 lines) after `_is_generic_labor_description` (line ~1199)
   - Add `_labor_references_excluded_part()` (~35 lines) after the above
   - Insert guard checks at 5 promotion points (~3 lines each, ~15 lines total)

2. **`tests/unit/test_coverage_analyzer.py`**
   - Add `TestLaborPromotionGuards` class with ~8 tests:
     - P1: diagnostic labor blocked in Strategy 1, Strategy 3, Mode 1, Mode 2
     - P1: generic "Arbeit" still promoted (no false positive)
     - P3: labor for excluded part blocked in Strategy 3 and Mode 2
     - P3: labor for covered part still promoted (no false positive)

No changes to customer config or rule_engine.py.

## Verification

1. `python -m pytest tests/unit/ --no-cov -q` — all tests pass
2. Re-run pipeline on affected claims (64535, 64792, 65055, 65040) and verify diagnostic/excluded-part labor stays NOT_COVERED
