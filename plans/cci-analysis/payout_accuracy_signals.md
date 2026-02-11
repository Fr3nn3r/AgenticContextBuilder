# Payout Accuracy Signal Analysis

**Date:** 2026-02-11
**Dataset:** 54 claims total, 25 correctly-approved claims with payout data
**Goal:** Identify which CCI signals separate claims with accurate payouts from those with large payout errors, and recommend new signals/weight adjustments.

---

## 1. Executive Summary

The CCI composite score has **almost no ability to predict payout accuracy** (r = +0.14). In fact, higher CCI scores correlate *slightly* with *larger* payout errors -- the opposite of what we want. The coverage_reliability component (highest weight at 0.35) is **actively misleading**: it scores 0.79 for high-error claims vs 0.49 for low-error claims (r = +0.16).

The root causes of payout error are **not captured by current CCI signals**:
1. **Deductible/VAT not applied** -- payout = gross covered amount with no post-coverage math
2. **Parts misclassified as not-covered** -- labor counted but parts dropped entirely
3. **Reimbursement rate ignored** -- 40-60% reimbursement rates not applied
4. **Assumption density** -- more assumptions per line item = more error (r = +0.48, strongest single predictor)

### Key Metric: The Payout Error Problem

| Bucket | Count | Claim IDs | Mean Error |
|--------|-------|-----------|------------|
| Low (<10%) | 6 | 64288, 64380, 64792, 64850, 65258, 65280 | 4.5% |
| Medium (10-30%) | 12 | 64166, 64168, 64297, 64393, 64535, 64659, 64959, 65047, 65055, 65056, 65150, 65196 | 19.6% |
| High (>30%) | 7 | 64354, 64386, 64818, 64836, 64978, 64984, 65027 | 132.0% |

Overall: mean 47.6%, median 22.3%, driven heavily by outlier 64978 (548% error).

---

## 2. Signal Comparison Across Error Buckets

### Signals Where Low-Error Claims Score HIGHER (desirable -- signal works)

| Signal | Low (<10%) | Med (10-30%) | High (>30%) | Spread | Interpretation |
|--------|-----------|-------------|-------------|--------|----------------|
| num_line_items | 19.5 | 12.3 | 8.9 | +10.6 | More items = better accuracy (more data points) |
| num_items_covered | 11.3 | 4.5 | 4.3 | +7.0 | More covered items = better accuracy |
| cci_sig_method_diversity | 0.67 | 0.62 | 0.54 | +0.12 | More diverse match methods = better |
| cci_sig_primary_repair_confidence | 0.95 | 0.93 | 0.81 | +0.14 | Higher repair confidence = better |
| cci_sig_gate_status_score | 0.42 | 0.42 | 0.21 | +0.20 | Better gate status = better |
| cci_sig_hard_fail_clarity | 1.00 | 1.00 | 0.86 | +0.14 | Clearer hard fails = better |
| cci_consistency | 0.70 | 0.70 | 0.60 | +0.10 | More consistent data = better |

### Signals Where Low-Error Claims Score LOWER (inverted -- signal is broken)

| Signal | Low (<10%) | Med (10-30%) | High (>30%) | Spread | Problem |
|--------|-----------|-------------|-------------|--------|---------|
| **cci_sig_line_item_complexity** | 0.55 | 0.79 | 0.97 | **-0.42** | **Worst offender: high complexity score = high error** |
| **cci_coverage_reliability** | 0.49 | 0.68 | 0.79 | **-0.31** | **Component is inverted! Higher = worse payout** |
| cci_composite_score | 0.72 | 0.79 | 0.81 | -0.09 | Composite slightly inverted |

### Signals With No Discrimination (constant across all claims)

| Signal | Value | Note |
|--------|-------|------|
| cci_sig_review_needed_rate | 1.000 everywhere | Zero variance -- useless |
| cci_sig_tier1_ratio | 0.565 everywhere | Zero variance -- useless |
| cci_sig_assumption_reliance | 1.000 everywhere | Zero variance -- useless |
| num_assumptions_used | 9.0 everywhere | Zero variance -- useless |
| num_clauses_evaluated | 23.0 everywhere | Zero variance -- useless |

---

## 3. Coverage Reliability Deep-Dive

Coverage reliability has weight 0.35 (highest) but correlates *positively* with payout error (r = +0.16). This is the single biggest problem with the CCI weighting for payout prediction.

### Sub-Signal Correlations with Payout Error

| Signal | Pearson r | Interpretation |
|--------|-----------|----------------|
| avg_match_confidence | -0.03 | Nearly zero -- useless for payout |
| review_needed_rate | 0.00 | Constant 1.0 everywhere -- zero information |
| **method_diversity** | **-0.40** | **Best existing predictor: diverse methods = less error** |
| line_item_complexity | +0.20 | Inverted: higher "complexity" signal = more error |
| primary_repair_confidence | -0.04 | Weak signal |
| tier1_ratio | 0.00 | Constant -- zero information |

### Why Coverage Reliability Is Inverted

The `line_item_complexity` signal (weight inside coverage reliability) is computed as `1.0 - (num_items / max_items)` or similar, meaning **fewer items get a higher score**. But claims with fewer items have HIGHER payout error. The signal effectively rewards simplicity, but simplicity correlates with *worse* payout outcomes because:

- Fewer line items means less redundancy and fewer cross-checks
- Simple claims may have a single large-value item where one wrong coverage decision has outsized impact
- Claims with 30 items (e.g., 64288: 3.6% error) have much better accuracy than claims with 3 items (e.g., 64978: 548% error)

**Recommendation:** Invert or remove `line_item_complexity` from coverage reliability. It is actively harming the composite score's predictive power.

---

## 4. Match Method Analysis

### LLM Match Proportion vs Payout Error

| Dominant Method | n | Mean Error | Median Error |
|----------------|---|------------|--------------|
| part_number | 3 | 10.9% | 14.1% |
| rule | 8 | 30.3% | 24.2% |
| llm | 14 | 65.4% | 22.9% |

Pearson correlation (LLM proportion vs error): **r = +0.30**

Claims dominated by part_number matches have the lowest error (10.9% mean). LLM-dominant claims have the highest (65.4% mean), though the median (22.9%) is closer to rule-based claims, indicating a few extreme outliers drive the mean.

**Insight:** Part-number matching is the most reliable match method for payout accuracy. LLM matching introduces variability. The current `method_diversity` signal partially captures this (r = -0.40), but a direct `llm_match_proportion` signal would be more targeted.

---

## 5. Overshoot vs Undershoot Patterns

| Metric | Overshoots (n=10) | Undershoots (n=15) |
|--------|-------------------|---------------------|
| Mean error % | 28.8% | 60.1% |
| num_items_review_needed | 2.0 | 0.4 |
| coverage_pct | 82.0% | 73.3% |
| coverage_total_not_covered | 1052.44 | 907.38 |

**Key pattern:** Undershoots are much larger errors on average (60% vs 29%). Undershoots are characterized by:
- More items correctly identified as covered but the **covered amounts are wrong** (parts dropped, only labor counted)
- Lower gate_status_score (-0.10 vs overshoot)
- Lower hard_fail_clarity (-0.07)

Overshoots are characterized by:
- More items in "review_needed" status (+1.6 items)
- Higher coverage_pct (+8.7pp) -- more items get tentatively approved
- Higher not_covered amounts (+145) -- but also higher total claimed

---

## 6. Line Item Count vs Payout Error

| Complexity | n | Mean Error |
|-----------|---|------------|
| Simple (<=3 items) | 2 | 280.8% |
| Moderate (4-7 items) | 7 | 25.4% |
| Complex (>=8 items) | 16 | 28.2% |

Pearson correlation (line_item_count vs error): **r = -0.27**

More line items = lower error. The "simple" bucket is dominated by claim 64978 (548% error on 3 items). Claims with 30 items average only 7.4% error.

**Insight:** The CCI currently penalizes complexity (more items = lower line_item_complexity score = lower coverage_reliability). This is backwards. More line items provide more data for cross-validation and reduce the impact of any single misclassification.

---

## 7. Claim-Level Root Cause Analysis (Top 5 Errors)

### Claim 64978 -- 548% error (overshoot, CHF 136.90 abs)

**Root cause: Deductible + reimbursement rate not applied.** GT approved = CHF 24.98 (after 150 deductible + 40% reimbursement), but system predicted CHF 161.88 (gross covered, no deductible, no reimbursement). The system paid out 6.5x the correct amount. CCI score was 0.84 ("high") -- completely missed this.

### Claim 64354 -- 93.2% error (undershoot, CHF 876.15 abs)

**Root cause: Parts classified as not-covered.** GT approved CHF 939.98, predicted only CHF 63.83. Pred_parts_total = 0.0 but GT parts_approved = 391.30. The coverage analysis rejected 9 of 12 line items. Payout/covered ratio = 1.0 (no deductible applied). Double failure: wrong coverage decisions AND no post-coverage math.

### Claim 64836 -- 73.7% error (undershoot, CHF 2209.11 abs)

**Root cause: Same pattern -- parts dropped.** Pred_parts = 0.0 vs GT parts = 2292.51. Only labor was counted. Primary repair confidence was 0.0 (no primary repair identified). This is a Rolls Royce Phantom claim with 11 line items where only 3 were covered. The system also applied a 0.30 payout/covered ratio that doesn't match any known formula.

### Claim 65027 -- 64.8% error (undershoot, CHF 435.73 abs)

**Root cause: Parts dropped + reimbursement rate ignored.** Pred_parts = 0.0 vs GT parts = 454.43. GT has 60% reimbursement rate. The system covered 10 of 11 items (good coverage!) but only counted labor (CHF 236.80). The coverage_total_covered was CHF 1728 but payout was only CHF 236.80 -- a 0.137 ratio that suggests severe post-coverage miscalculation.

### Claim 64984 -- 49.9% error (undershoot, CHF 478.25 abs)

**Root cause: Deductible/VAT not applied + labor miscounted.** GT labor = 550.20, pred labor = 5.00. The system found the right parts (CHF 475) but missed almost all labor. Payout/covered ratio = 1.0 (no deductible applied despite CHF 150 deductible in GT).

### Common Themes in High-Error Claims

1. **pred_parts_total = 0.0 in 3 of 5 cases** -- Parts are being systematically excluded from the payout even when covered
2. **Payout = gross covered in 2 of 5 cases** -- No deductible, VAT, or reimbursement adjustment applied
3. **CCI scored all 5 as "high" (0.83+) except one "moderate" (0.68)** -- The CCI does not detect these failures

---

## 8. Recommended New Signals

### High Priority (strong correlation with payout error, not currently captured)

| New Signal | Correlation | Description | Implementation |
|-----------|-------------|-------------|----------------|
| **assumption_density** | **r = +0.48** | Assumptions per line item. More assumptions = more error. | `num_assumptions / num_line_items` |
| **llm_match_proportion** | **r = +0.30** | Fraction of matches using LLM. Higher = more error. | `llm_count / total_match_count` |
| **deductible_applied_flag** | N/A (binary) | Whether payout != gross covered (i.e., post-coverage math was done). In 2/5 worst claims, payout = gross. | `1.0 if pred_net_payout != coverage_total_covered_gross else 0.0` |
| **parts_coverage_flag** | N/A (binary) | Whether pred_parts_total > 0 when items exist. In 3/5 worst claims, parts = 0. | `1.0 if pred_parts_total > 0 else 0.0` |

### Medium Priority (moderate signal, useful context)

| New Signal | Correlation | Description |
|-----------|-------------|-------------|
| **rule_match_proportion** | r = -0.28 | More rule-based matches = less error |
| **clause_fail_ratio** | r = -0.34 | More clause failures = less error (counterintuitive -- failing clauses means more rigorous checking) |
| **review_item_ratio** | r = +0.28 | More items in review-needed = more error |
| **payout_to_covered_ratio** | N/A | `pred_net_payout / coverage_total_covered_gross` -- should be consistent with deductible/VAT |

### Signals to Track (weak but informative)

| New Signal | Correlation | Description |
|-----------|-------------|-------------|
| covered_ratio | r = +0.06 | Ratio of covered to total claimed -- weak predictor |
| parts_vs_labor_ratio | r = +0.12 | Higher parts proportion = slightly more error |
| not_covered_ratio | r = -0.06 | Higher not-covered proportion = slightly less error |

---

## 9. Weight Adjustment Recommendations

### Current Weights (problematic)

| Component | Current Weight | Correlation with Error | Problem |
|-----------|---------------|----------------------|---------|
| document_quality | 0.15 | r = -0.29 | OK -- weakly predictive in right direction |
| data_completeness | 0.15 | r = -0.07 | Near-zero signal |
| consistency | 0.10 | r = -0.08 | Near-zero signal |
| **coverage_reliability** | **0.35** | **r = +0.16** | **INVERTED -- higher weight = worse prediction** |
| decision_clarity | 0.25 | r = -0.05 | Near-zero signal |

### Recommended Changes

1. **CRITICAL: Fix `line_item_complexity` signal** -- It is inverted. Either:
   - Invert it: use `num_items / max_items` instead of `1 - num_items / max_items`
   - Or replace it with `assumption_density` (inverse: `1 - assumptions_per_item`)

2. **Add deductible/VAT verification signal** to coverage_reliability:
   - `payout_math_check`: `1.0` if `pred_net_payout < coverage_total_covered_gross`, `0.0` if they are equal (meaning no deductible was applied). This single binary check would have flagged 2 of the 5 worst claims.

3. **Add parts_coverage_check** to coverage_reliability:
   - `1.0` if `pred_parts_total > 0` when `num_items_covered > 0`, else `0.0`. Would have flagged 3 of the 5 worst claims.

4. **Reduce coverage_reliability weight** from 0.35 to 0.25 until the sub-signals are fixed.

5. **Add new "payout_plausibility" component** (weight 0.15) with:
   - `deductible_applied_flag`
   - `parts_coverage_flag`
   - `assumption_density` (inverted)
   - `llm_match_proportion` (inverted)

6. **Remove zero-variance signals** that waste weight budget:
   - `review_needed_rate` (always 1.0)
   - `tier1_ratio` (always 0.565)
   - `assumption_reliance` (always 1.0)

### Proposed New Weight Structure

| Component | New Weight | Sub-signals |
|-----------|-----------|-------------|
| document_quality | 0.15 | (unchanged) |
| data_completeness | 0.15 | (unchanged) |
| consistency | 0.10 | (unchanged) |
| coverage_reliability | 0.25 | Fix line_item_complexity, add method_quality (rule/pn ratio) |
| decision_clarity | 0.20 | (unchanged) |
| **payout_plausibility (NEW)** | **0.15** | deductible_applied, parts_coverage, assumption_density, llm_match_pct |

---

## 10. Quick Wins (Immediate Impact)

1. **Invert `cci_sig_line_item_complexity`** -- Single change with biggest impact on coverage_reliability accuracy
2. **Add `payout != gross_covered` check** -- Catches deductible/VAT failures (2/5 worst claims)
3. **Add `pred_parts_total > 0` check** -- Catches parts-dropped failures (3/5 worst claims)
4. **Replace zero-variance signals** with the new candidate signals above
5. **Lower coverage_reliability weight** from 0.35 to 0.25 pending sub-signal fixes
