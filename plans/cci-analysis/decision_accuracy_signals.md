# Decision Accuracy Signal Analysis

**Dataset**: 54 claims with ground truth, 51 correct (94.4%), 3 incorrect (5.6%)
**Wrong claims**: 64358 (false reject), 65040 (false reject), 65113 (false approve)

---

## 1. Executive Summary

The CCI band system provides strong separation: **all 26 "high" band claims are correct** (100%), while all 3 errors fall in the "moderate" band (89.3% accuracy). However, 25 correct claims also fall in "moderate," so the band alone is not sufficient for flagging.

The **most predictive CCI signals** for decision accuracy are:
1. **`cci_sig_gate_status_score`** -- strongest normalized CCI signal separator (0.22 mean diff)
2. **`cci_sig_line_item_complexity`** -- second strongest (0.14 mean diff)
3. **`cci_sig_hard_fail_clarity`** -- third (0.14 mean diff)
4. **`cci_consistency`** -- strongest component-level separator (0.10 mean diff)
5. **`cci_coverage_reliability`** -- second component (0.08 mean diff)

Three **red flag combinations** each catch 2 of 3 errors at 66.7% error rate (12x baseline):
- `low_consistency + high_clause_fail_rate`
- `low_critical_facts + high_clause_fail_rate`
- `gate_zero + high_clause_fail_rate`

A new **payout materiality signal** is needed: claim 65113 had a 1.3% payout/claimed ratio (CHF 157 on CHF 11,900) -- no existing CCI signal captures this.

---

## 2. Signal Comparison: Correct vs Incorrect

### Top CCI Signal Separators (normalized 0-1 signals only)

| Rank | Signal | Correct Mean | Incorrect Mean | Abs Diff | Direction |
|------|--------|-------------|---------------|----------|-----------|
| 1 | `cci_sig_gate_status_score` | 0.3824 | 0.1667 | 0.2157 | correct higher |
| 2 | `cci_sig_line_item_complexity` | 0.8437 | 0.7000 | 0.1437 | correct higher |
| 3 | `cci_sig_hard_fail_clarity` | 0.4706 | 0.3333 | 0.1373 | correct higher |
| 4 | `cci_sig_primary_repair_confidence` | 0.7290 | 0.8500 | 0.1210 | **incorrect higher** |
| 5 | `cci_consistency` | 0.6824 | 0.5833 | 0.0991 | correct higher |
| 6 | `cci_coverage_reliability` | 0.6616 | 0.5820 | 0.0797 | correct higher |
| 7 | `cci_sig_critical_facts_rate` | 0.7611 | 0.7111 | 0.0500 | correct higher |
| 8 | `cci_composite_score` | 0.7702 | 0.7243 | 0.0458 | correct higher |

### Non-Separating Signals (noise -- diff < 0.02)

These signals show virtually no difference between correct and incorrect decisions and may be **over-weighted** in the current composite:

- `cci_sig_avg_field_confidence` (diff 0.0001)
- `cci_sig_assumption_reliance` (diff 0.0000 -- always 1.0 for all claims)
- `cci_sig_review_needed_rate` (diff 0.0000 -- always 1.0 for all claims)
- `cci_sig_tier1_ratio` (diff 0.0000 -- identical for all claims: 0.5652)
- `cci_sig_provenance_coverage` (diff 0.0008)
- `cci_sig_verified_evidence_rate` (diff 0.0010)
- `cci_sig_assessment_confidence` (diff 0.0010)
- `cci_sig_data_gap_penalty` (diff 0.0024)
- `cci_sig_fraud_indicator_penalty` (diff 0.0039)

**Key finding**: Three signals (`assumption_reliance`, `review_needed_rate`, `tier1_ratio`) are **constant across all 54 claims** and contribute zero discriminative power. They are dead weight in the composite score.

### Structural Signals (non-normalized)

| Signal | Correct Mean | Incorrect Mean | Diff |
|--------|-------------|---------------|------|
| `num_items_covered` | 3.51 | 0.67 | 2.84 |
| `num_items_not_covered` | 6.63 | 14.00 | 7.37 |
| `num_clauses_fail` | 1.96 | 3.33 | 1.37 |
| `num_line_items` | 10.92 | 15.33 | 4.41 |

---

## 3. Error Deep-Dive

### Claim 64358 -- False Reject (GT: APPROVED, Pred: DENIED)

**Pattern**: Coverage analysis found **zero covered items** out of 11 line items. 5 clauses failed (vs 1.96 avg). The system denied a claim that should have been approved.

**Distinctive signals**:
- `num_items_covered` = 0 (vs 3.51 mean) -- total coverage miss
- `num_clauses_fail` = 5 (vs 1.96 mean) -- 3x normal failure rate
- `cci_sig_hard_fail_clarity` = 0.0 (vs 0.47 mean) -- zero hard fail clarity
- `cci_sig_gate_status_score` = 0.0 (vs 0.38 mean) -- gate failed
- `cci_consistency` = 0.50 (vs 0.68 mean) -- below average consistency
- Failed clauses: 2.2.A, 2.2.D, 2.4.A.e, 2.4.A.h, 2.5.A.b

**Root cause hypothesis**: Coverage matching failed to recognize covered items (possibly keyword/rule matching gaps for the transmission repair domain). The zero-coverage result cascaded into clause failures and denial.

### Claim 65040 -- False Reject (GT: APPROVED, Pred: DENIED)

**Pattern**: Nearly identical to 64358. **Zero covered items** out of 5 line items. 4 clauses failed. System denied a valid claim.

**Distinctive signals**:
- `num_items_covered` = 0 (vs 3.51 mean) -- total coverage miss
- `num_clauses_fail` = 4 (vs 1.96 mean) -- 2x normal failure rate
- `cci_sig_hard_fail_clarity` = 0.0 (vs 0.47 mean)
- `cci_sig_gate_status_score` = 0.0 (vs 0.38 mean)
- `cci_consistency` = 0.50 (vs 0.68 mean)
- Failed clauses: 2.2.A, 2.2.D, 2.4.A.h, 2.5.A.b

**Root cause hypothesis**: Same pattern as 64358 -- coverage matching completely missed all items for a control_unit repair. The shared failed clauses (2.2.A, 2.2.D, 2.4.A.h, 2.5.A.b) suggest a systematic gap in coverage rules for certain component types.

### Claim 65113 -- False Approve (GT: DENIED, Pred: APPROVED)

**Pattern**: Radically different from the false rejects. 30 line items, only 2 covered, CHF 157 payout on an CHF 11,900 claim (1.32% payout ratio). The system approved a trivial amount that should have been denied entirely.

**Distinctive signals**:
- `cci_sig_line_item_complexity` = 0.15 (vs 0.84 mean) -- by far the lowest
- `cci_coverage_reliability` = 0.13 (vs 0.66 mean) -- extremely low, nearly the floor
- `cci_composite_score` = 0.6135 (vs 0.77 mean) -- lowest among the 3 errors
- `num_items_not_covered` = 28 (vs 6.63 mean) -- massive rejection count
- `cci_sig_hard_fail_clarity` = 1.0 (vs 0.47 mean) -- **misleadingly high**
- `cci_decision_clarity` = 0.93 (vs 0.81 mean) -- **misleadingly high**

**Root cause hypothesis**: The system found 2 trivially small covered items and auto-approved. The decision engine lacks a **materiality threshold** -- it should flag or deny when payout is a negligible fraction of the total claim. The high `decision_clarity` is misleading because the decision itself was wrong; it was "clearly" approved when it shouldn't have been.

---

## 4. Band Analysis

| Band | Claims | Correct | Incorrect | Accuracy |
|------|--------|---------|-----------|----------|
| high | 26 | 26 | 0 | 100.0% |
| moderate | 28 | 25 | 3 | 89.3% |

**Finding**: The band system works directionally -- "high" is reliable. But the "moderate" band is too broad:
- Composite scores in moderate range from 0.5544 to 0.7976
- All 3 errors (0.6135, 0.7719, 0.7876) fall within this range
- 22 correct claims have scores below the worst error (0.7876)

**Recommendation**: Split "moderate" into two sub-bands or add secondary signal checks for moderate-band claims.

---

## 5. Threshold Analysis

Thresholds where accuracy meaningfully drops:

| Signal | Threshold | Below (n, acc%) | Above (n, acc%) | Lift | Wrong Claims Below |
|--------|-----------|-----------------|-----------------|------|--------------------|
| `cci_sig_critical_facts_rate` | 0.669 | 11, 81.8% | 43, 97.7% | 15.9 pp | 64358, 65040 |
| `cci_composite_score` | 0.637 | 5, 80.0% | 49, 95.9% | 15.9 pp | 65113 |
| `cci_consistency` | 0.545 | 16, 87.5% | 38, 97.4% | 9.9 pp | 64358, 65040 |
| `cci_coverage_reliability` | 0.323 | 7, 85.7% | 47, 95.7% | 10.0 pp | 65113 |
| `cci_sig_gate_status_score` | 0.110 | 16, 87.5% | 38, 97.4% | 9.9 pp | 64358, 65040 |
| `cci_decision_clarity` | 0.734 | 16, 87.5% | 38, 97.4% | 9.9 pp | 64358, 65040 |

**Observation**: No single threshold catches all 3 errors. The false rejects (64358, 65040) are caught by `critical_facts_rate < 0.67` and `consistency < 0.55`, while the false approve (65113) is caught by `composite_score < 0.64` and `coverage_reliability < 0.32`. A combined rule is needed.

---

## 6. Red Flag Combinations

### Individual Conditions

| Condition | Claims Matching | Errors | Error Rate | vs Baseline (5.6%) |
|-----------|----------------|--------|-----------|---------------------|
| `high_clause_fail_rate` (>15%) | 7 | 2 | 28.6% | **5.1x** |
| `low_critical_facts` (<0.70) | 12 | 2 | 16.7% | **3.0x** |
| `low_consistency` (<0.55) | 16 | 2 | 12.5% | **2.2x** |
| `gate_zero` (=0.0) | 16 | 2 | 12.5% | **2.2x** |
| `low_coverage_reliability` (<0.75) | 26 | 1 | 3.8% | 0.7x |

### Pairwise Combinations (elevated error rate)

| Combination | Claims | Errors | Error Rate |
|------------|--------|--------|-----------|
| **`low_consistency + high_clause_fail_rate`** | 3 | 2 | **66.7%** |
| **`low_critical_facts + high_clause_fail_rate`** | 3 | 2 | **66.7%** |
| **`gate_zero + high_clause_fail_rate`** | 3 | 2 | **66.7%** |
| `low_consistency + low_critical_facts` | 12 | 2 | 16.7% |
| `low_consistency + gate_zero` | 16 | 2 | 12.5% |
| `low_critical_facts + gate_zero` | 12 | 2 | 16.7% |

**Key finding**: Any condition paired with `high_clause_fail_rate` produces a 66.7% error rate -- 12x the baseline. This is the strongest red flag pattern, though it only catches the 2 false rejects, not the false approve.

---

## 7. Coverage Method Analysis

| Method | Correct (avg count) | Incorrect (avg count) | Present in Correct | Present in Incorrect |
|--------|--------------------|-----------------------|-------------------|---------------------|
| rule | 3.9 | 3.0 | 86% | 100% |
| part_number | 3.2 | 6.7 | 76% | 100% |
| llm | 5.1 | 5.7 | 92% | 100% |
| keyword | 1.8 | 0.0 | 24% | 0% |

**Observations**:
- Wrong claims have **higher `part_number` counts** (6.7 vs 3.2) -- driven by claim 65113 with 17 part_number matches
- Wrong claims have **zero keyword matches** -- keyword method is absent in all 3 errors
- LLM-heavy claims (>50% LLM) are all correct (20/20) -- LLM majority does not predict errors
- Match confidence is not discriminating: wrong claims average 0.921 vs correct 0.912

---

## 8. Payout Materiality (Claim 65113)

Claim 65113 is a false approve with these characteristics:
- **CHF 157.30 payout on CHF 11,901.49 claimed** (1.32% ratio)
- 2 out of 30 line items covered (6.7% item coverage)
- 28 items explicitly not covered
- `cci_sig_line_item_complexity` = 0.15 (lowest in dataset by far; mean = 0.84)
- `cci_coverage_reliability` = 0.13 (lowest in dataset by far; mean = 0.66)

**No existing CCI signal directly captures payout materiality**. The `line_item_complexity` signal is close (it's very low here) but its purpose is different.

### Proposed: `cci_sig_payout_materiality`

A new signal that captures when the approved payout is trivially small relative to the claim:

```
payout_materiality = pred_net_payout / pred_total_claimed
```

Claims with payout_materiality < 0.05 (5%):
| Claim | Ratio | Correct? |
|-------|-------|----------|
| **65113** | **0.013** | **No** |
| 64354 | 0.042 | Yes |

While there's only one error in this bucket, the 50% error rate at <5% ratio (vs 5.6% baseline) warrants adding this as a CCI flag or signal, especially since these edge cases represent a qualitatively different kind of risk.

---

## 9. Recommendations for CCI Tuning

### High Priority

1. **Remove dead-weight signals**: `cci_sig_assumption_reliance`, `cci_sig_review_needed_rate`, and `cci_sig_tier1_ratio` are constant (identical for all 54 claims). They contribute nothing and dilute the composite score. Either remove them or fix their computation to produce variance.

2. **Add `high_clause_fail_rate` red flag**: When `num_clauses_fail / num_clauses_evaluated > 0.15`, flag the claim. This single condition catches 2/3 errors at 28.6% error rate (5x baseline). Combined with `low_consistency`, it's 66.7%.

3. **Add payout materiality signal**: When `payout / total_claimed < 0.05`, add a CCI flag (`trivial_payout_ratio`). This catches the false-approve pattern that no current signal detects.

4. **Increase weight of `cci_sig_gate_status_score`**: This is the best normalized CCI separator (0.22 mean diff) but its contribution to the composite seems under-weighted given that all claims with gate=0 and high clause failure are wrong.

### Medium Priority

5. **Split "moderate" band**: Consider a "low-moderate" sub-band for composite scores < 0.65. The single claim below 0.65 that was wrong (65113, score 0.6135) is very different from the moderate claims around 0.77-0.79.

6. **Increase weight of `cci_consistency`**: The component-level consistency score (0.10 mean diff) separates errors better than document_quality, data_completeness, or decision_clarity, but it seems to have lower weight in the composite.

7. **Add `zero_coverage_flag`**: When `num_items_covered == 0` despite having line items, add a CCI flag. Both false rejects had exactly zero covered items -- this is a strong indicator of a coverage matching failure rather than a legitimately uncovered claim.

### Low Priority

8. **Investigate `cci_sig_primary_repair_confidence` inversion**: Incorrect decisions have *higher* repair confidence (0.85) than correct ones (0.73). This counter-intuitive result might indicate that overconfident primary repair identification leads to coverage matching errors, or it might be noise from 3 samples.

9. **Down-weight non-separating signals**: Signals with <0.01 mean difference (field_confidence, provenance_coverage, verified_evidence_rate, assessment_confidence, data_gap_penalty, fraud_indicator_penalty) could have their composite weights reduced in favor of the stronger separators.

---

## 10. Key Takeaways

1. **The two failure modes are completely different**: False rejects (64358, 65040) show low consistency, zero coverage, and high clause failure. The false approve (65113) shows trivial payout ratio and extremely low coverage reliability. No single rule catches all errors.

2. **The composite score does not reliably separate errors**: 22 correct claims score lower than the highest-scoring error (0.7876). The composite needs rebalancing.

3. **Three signals are dead weight**: assumption_reliance, review_needed_rate, and tier1_ratio are identical across all 54 claims.

4. **Structural signals (num_items_covered, num_clauses_fail) are the strongest predictors**, stronger than any CCI signal. Consider incorporating these into the CCI computation more directly.

5. **Coverage matching is the root cause**: Both false rejects had zero items covered (coverage matching failure), and the false approve had a negligible coverage amount (materiality gap). The errors are all coverage-related, not extraction or classification errors.
