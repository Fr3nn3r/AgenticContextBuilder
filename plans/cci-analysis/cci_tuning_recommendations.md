# CCI Tuning Recommendations

**Date:** 2026-02-11
**Based on:** 54-claim eval dataset (eval #48), 94.4% decision accuracy, 47.6% mean payout error
**Analysis by:** 3-agent team (data collection, decision analysis, payout analysis)

---

## Executive Summary

The CCI has **two distinct accuracy dimensions** that require different tuning:

1. **Decision accuracy (94.4%)** -- The CCI band system is directionally correct (100% accuracy in HIGH band, 89.3% in MODERATE). But the composite score gap between correct and incorrect claims is too narrow (0.770 vs 0.724) and 3 signals are dead weight.

2. **Payout accuracy (47.6% mean error)** -- This is the bigger problem. The CCI's highest-weighted component (`coverage_reliability` at 0.35) is **actively inverted** -- higher scores correlate with *worse* payout accuracy (r = +0.16). The `line_item_complexity` sub-signal is the primary culprit.

### The Core Insight

The CCI currently answers: *"How confident are we in the data quality?"* But it doesn't answer: *"How confident are we in the dollar amount?"* These are different questions that need different signals.

---

## Finding 1: Three Dead-Weight Signals

Three signals are **identical across all 54 claims** and contribute zero discriminative power:

| Signal | Value (all claims) | Component |
|--------|-------------------|-----------|
| `assumption_reliance` | 1.000 | decision_clarity |
| `review_needed_rate` | 1.000 | coverage_reliability |
| `tier1_ratio` | 0.565 | decision_clarity |

**Root cause:** These signals are computed from data that doesn't vary in the current pipeline configuration. Either the computation is broken (always returning a constant) or the underlying data lacks variance.

**Action:** Remove from composite OR fix the computation to produce variance. These waste weight budget and dilute the score.

---

## Finding 2: `line_item_complexity` Is Inverted

This signal inside `coverage_reliability` (weight 0.35) is the **single biggest problem**:

| Line Items | Complexity Score | Payout Error |
|-----------|-----------------|-------------|
| <= 3 items | 1.00 (max) | 280.8% mean error |
| 4-7 items | 0.85 | 25.4% |
| 8+ items | 0.55 | 28.2% |

The signal rewards simplicity, but simple claims have *worse* outcomes. Claims with 30 items (score ~0.15) average only 7.4% error. The signal's decay curve:
- n <= 10: score = 1.0
- 10 < n <= 20: score decays to 0.5
- n > 20: score decays to 0.15

This is backwards. More line items provide more cross-validation data and reduce the impact of any single misclassification.

**Action:** Invert the curve or replace with `assumption_density` (assumptions_per_item, inverted). The current implementation at `src/context_builder/confidence/collector.py:310-326` needs to be reversed.

---

## Finding 3: Two Distinct Error Modes Need Different Signals

### Error Mode A: False Rejects (2 claims: 64358, 65040)

**Pattern:** Coverage matching completely failed -- zero items covered out of 5-11 line items. This cascaded into clause failures and automatic denial.

**Distinguishing signals:**
- `num_items_covered` = 0 (vs 3.51 mean)
- `num_clauses_fail` = 4-5 (vs 1.96 mean)
- `hard_fail_clarity` = 0.0 (vs 0.47 mean)
- `gate_status_score` = 0.0 (vs 0.38 mean)
- `consistency` < 0.55

**Best detection rule:** `low_consistency + high_clause_fail_rate` catches both at 66.7% error rate (12x baseline).

### Error Mode B: False Approve (1 claim: 65113)

**Pattern:** System found 2 trivially small covered items (CHF 157 out of CHF 11,900 total = 1.3%) and auto-approved for CHF 20. No materiality check exists.

**Distinguishing signals:**
- `line_item_complexity` = 0.15 (lowest in dataset)
- `coverage_reliability` = 0.13 (lowest in dataset)
- 28 of 30 items not covered
- Payout/claimed ratio = 1.3%

**Best detection rule:** `payout_materiality < 5%` catches this error mode.

### Error Mode C: Payout Miscalculation (top 5 error claims)

**Pattern:** Decision is correct but the dollar amount is wrong by 50-548%.

**Sub-patterns:**
- **Parts dropped (3/5 worst):** `pred_parts_total = 0` when GT has parts
- **No post-coverage math (2/5 worst):** `pred_net_payout == coverage_total_covered_gross` (no deductible/VAT applied)
- **Reimbursement rate ignored:** 40-60% rates not applied

**No existing CCI signal detects any of these patterns.** The CCI scored 4/5 of these claims as "high" band.

---

## Finding 4: Strongest Predictive Signals

### For Decision Accuracy (correct/incorrect separation)

| Rank | Signal | Mean Diff | Type |
|------|--------|-----------|------|
| 1 | `gate_status_score` | 0.216 | CCI signal |
| 2 | `line_item_complexity` | 0.144 | CCI signal |
| 3 | `hard_fail_clarity` | 0.137 | CCI signal |
| 4 | `num_items_covered` | 2.84 items | Structural |
| 5 | `num_clauses_fail` | 1.37 clauses | Structural |
| 6 | `consistency` (component) | 0.099 | CCI component |
| 7 | `coverage_reliability` (component) | 0.080 | CCI component |

### For Payout Accuracy (error correlation)

| Rank | Signal | Pearson r | Direction |
|------|--------|-----------|-----------|
| 1 | **assumption_density** (NEW) | +0.48 | More assumptions = more error |
| 2 | **method_diversity** | -0.40 | More diverse methods = less error |
| 3 | **clause_fail_ratio** (NEW) | -0.34 | More rigorous checking = less error |
| 4 | **llm_match_proportion** (NEW) | +0.30 | More LLM matches = more error |
| 5 | document_quality (component) | -0.29 | Better doc quality = less error |
| 6 | line_item_count | -0.27 | More items = less error |

---

## Recommended CCI Changes

### Priority 1: Fix Broken Signals (immediate)

| Change | Impact | File |
|--------|--------|------|
| **Invert `line_item_complexity`** | Fixes the worst inversion; coverage_reliability currently rewards the wrong claims | `confidence/collector.py:310-326` |
| **Remove 3 zero-variance signals** (`assumption_reliance`, `review_needed_rate`, `tier1_ratio`) | Eliminates dead weight; their weight gets redistributed to signals that work | `confidence/scorer.py:33-64` |
| **Add `payout_materiality` flag** | Catches false-approve pattern: when `payout/total_claimed < 5%`, flag as LOW | `confidence/collector.py` (new signal) |

### Priority 2: Add New Signals (short-term)

| Signal | Component | Formula | Catches |
|--------|-----------|---------|---------|
| `payout_math_check` | coverage_reliability | `1.0 if net_payout < gross_covered else 0.0` | Deductible not applied (2/5 worst payout errors) |
| `parts_coverage_check` | coverage_reliability | `1.0 if parts_total > 0 when items_covered > 0 else 0.0` | Parts dropped (3/5 worst payout errors) |
| `assumption_density` | decision_clarity | `1.0 - (num_assumptions / num_line_items)` (clamped) | Strongest payout error predictor (r=0.48) |
| `llm_match_proportion` | coverage_reliability | `1.0 - (llm_matches / total_matches)` | LLM-heavy = more payout variability |
| `zero_coverage_flag` | coverage_reliability | `0.0 if items_covered == 0 and items > 0 else 1.0` | Both false rejects had zero coverage |

### Priority 3: Reweight Components (after fixing signals)

**Current weights:**

```
document_quality:     0.20
data_completeness:    0.15
consistency:          0.15
coverage_reliability: 0.35
decision_clarity:     0.15
```

**Recommended weights (Option A -- adjust existing):**

```
document_quality:     0.15  (was 0.20 -- reduce; weak payout predictor)
data_completeness:    0.15  (keep)
consistency:          0.20  (was 0.15 -- increase; best component for decision accuracy)
coverage_reliability: 0.25  (was 0.35 -- reduce until sub-signals are fixed)
decision_clarity:     0.25  (was 0.15 -- increase; add assumption_density here)
```

**Recommended weights (Option B -- add payout_plausibility component):**

```
document_quality:      0.15
data_completeness:     0.15
consistency:           0.15
coverage_reliability:  0.25
decision_clarity:      0.15
payout_plausibility:   0.15  (NEW: deductible_applied, parts_coverage, assumption_density, llm_pct)
```

### Priority 4: Red Flag Overrides (medium-term)

Add hard overrides that force LOW band regardless of composite score:

| Red Flag | Condition | Catches |
|----------|-----------|---------|
| `ZERO_COVERAGE` | `items_covered == 0 AND total_items > 0` | False rejects (64358, 65040) |
| `TRIVIAL_PAYOUT` | `net_payout / total_claimed < 0.05` | False approve (65113) |
| `HIGH_CLAUSE_FAILURE` | `clause_fail_rate > 0.15 AND consistency < 0.55` | 66.7% error rate combination |
| `NO_DEDUCTIBLE` | `net_payout == gross_covered AND deductible > 0` | Payout math failure |
| `NO_PARTS` | `parts_total == 0 AND items_covered > 0` | Parts dropped from payout |

### Priority 5: Band Threshold Adjustment

**Current thresholds:**
- HIGH >= 0.80, MODERATE >= 0.55, LOW < 0.55

**Recommended thresholds:**
- HIGH >= 0.80 (keep -- 100% accuracy in this band)
- MODERATE >= 0.65 (raise from 0.55 -- pushes 65113 into LOW)
- LOW-MODERATE >= 0.55 (new sub-band)
- LOW < 0.55 (keep)

Or simpler: just raise the MODERATE floor to 0.65. Claims between 0.55-0.65 get LOW, which would catch 65113 (0.6135).

---

## Expected Impact

If all Priority 1-4 changes were applied retroactively:

| Metric | Current | After Fixes |
|--------|---------|-------------|
| Wrong claims in HIGH band | 0/26 | 0/~22 (no regression) |
| Wrong claims in LOW band | 0/0 | 3/~8 (all 3 errors move to LOW) |
| Wrong claims in MODERATE | 3/28 | 0/~24 |
| CCI mean diff (correct vs wrong) | 0.046 | ~0.15+ (3x better separation) |
| Zero-variance signals | 3 | 0 |
| Payout errors caught by CCI | 0/5 worst | 4/5 worst |

---

## Implementation Order

1. **Week 1:** Remove dead-weight signals, invert `line_item_complexity`, add red flag overrides (ZERO_COVERAGE, TRIVIAL_PAYOUT)
2. **Week 2:** Add `payout_math_check`, `parts_coverage_check`, `assumption_density` signals
3. **Week 3:** Reweight components, raise MODERATE threshold to 0.65
4. **Week 4:** Run full eval to validate; adjust thresholds based on results

---

## Appendix: Analysis Files

| File | Description |
|------|-------------|
| `plans/cci-analysis/merged_eval_data.json` | Raw merged dataset (54 claims, ground truth + CCI) |
| `plans/cci-analysis/merged_eval_data_enriched.json` | Enriched with decision dossier data, predicted decisions/payouts |
| `plans/cci-analysis/decision_accuracy_signals.md` | Full decision-level analysis |
| `plans/cci-analysis/payout_accuracy_signals.md` | Full payout-level analysis |
| `plans/cci-analysis/collect_data.py` | Data collection script |
| `plans/cci-analysis/enrich_data.py` | Data enrichment script |
| `plans/cci-analysis/analyze_decision_signals.py` | Decision analysis script |
| `plans/cci-analysis/analyze_payout_signals.py` | Payout analysis script |
