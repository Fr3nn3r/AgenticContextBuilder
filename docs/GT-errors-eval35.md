# Ground Truth Errors — eval_20260213_070503 (Eval #35)

Identified during amount mismatch investigation of 14 claims.

## Confirmed GT Errors

### Claim 65027 — Wrong reimbursement rate applied (GT=60%, should be 40%)

**Dataset**: nsa-motor-seed-v1

**GT values**: reimbursement_rate_pct=60, total_approved_amount=672.53, deductible=74.70

**Issue**: The GT coverage_notes state:
> "Gewährleistungspflichtige Materialkosten und Arbeitskosten sind wie folgt erstattet:
> ab 140.000 Km zu 60 % (Fahrzeuge ab 12 Jahre 40 %)."

The vehicle was first registered 22.07.2008. At the time of the claim (Jan 2026), the vehicle
is 17.5 years old — well above the 12-year threshold stated in the GT's own notes. The human
adjuster applied 60% (km-based rate) but should have applied 40% (age-based override).

**Policy facts**: coverage_scale extracted from policy document confirms `60% from 140'000 km (age 8+: 40%)`. Vehicle odometer = 141,672 km.

**System applied**: 40% (correct per both the policy and the GT's own stated rules).

**Impact on eval**: The system's payout (CHF 597.22) is lower than GT (CHF 672.53), making this
appear as an amount_mismatch underpayment. In reality, the system is correct and the GT is wrong.

**Correction needed**: GT should use reimbursement_rate_pct=40. Corrected amounts:
- total_material_labor_approved = 691.23 * 40% / 60% = 460.82 (recompute from gross)
- Actually: GT gross covered = 691.23 / 0.60 = 1,152.05. At 40% = 460.82.
- With VAT: 460.82 * 1.081 = 498.15. Deductible = 10% = 49.82 (below 150 minimum? need to check).
- Note: the deductible minimum floor question is separate — see below.

---

### Claim 65258 — Max coverage cap applied instead of reimbursement rate

**Dataset**: nsa-motor-seed-v1

**GT values**: reimbursement_rate_pct=None, total_approved_amount=4500, deductible=500,
coverage_notes="Maximum coverage per policy applied (Zylinderkopfschaden / cylinder head damage)."

**Issue**: The policy has a clear coverage_scale: `100% below 50k, 80% from 50k, 60% from 80k, 40% from 110k`. Vehicle odometer = 136,450 km, which falls in the "from 110k" bracket = 40%.

The system correctly applied 40%, yielding covered_total = 8,972 * 40% = 3,588.80. This is below
the max_coverage cap of CHF 5,000, so the cap does not trigger.

The GT instead awarded the full max_coverage (CHF 5,000), bypassing the percentage reduction
entirely. The GT deductible = 500 = 10% of 5,000.

**System applied**: 40% rate, yielding CHF 3,491.54 final payout.

**Interpretation**: The human adjuster appears to have used the max_coverage as a "pay the
maximum" shortcut, ignoring the degradation schedule. The correct calculation should apply the
40% rate first (since it reduces the amount below the cap), then check the cap (which doesn't
trigger). The cap is a ceiling, not a target.

**Impact on eval**: This appears as an amount_mismatch underpayment (-22.4%). The system
calculation is correct per the policy terms.

**Correction needed**: GT should apply 40% to the covered total, not award the max cap directly.

---

## Verified Correct (No GT Error)

The remaining 12 amount_mismatch claims were checked and the GT values are consistent:

### Underpaying claims (system pays less than GT)
| Claim | GT Amount | System | Diff | GT Verified |
|-------|-----------|--------|------|-------------|
| 65150 | 1,841.25 | 445.09 | -75.8% | GT math checks out. System coverage errors. |
| 64984 | 958.25 | 363.48 | -62.1% | GT math checks out. System nominal_price_labor bug. |
| 64168 | 333.69 | 135.38 | -59.4% | GT math checks out (40% rate confirmed). |
| 64358 | 439.27 | 266.53 | -39.3% | GT math checks out (60% rate confirmed). |
| 64166 | 1,506.52 | 1,072.87 | -28.8% | GT math checks out. System coverage scope issue. |
| 64659 | 2,397.38 | 1,813.76 | -24.3% | GT math checks out (40% rate confirmed). |
| 65280 | 562.75 | 468.93 | -16.7% | GT math checks out. |
| 64288 | 4,141.02 | 3,901.42 | -5.8% | GT math checks out (70% rate confirmed). |

### Overpaying claims (system pays more than GT)
| Claim | GT Amount | System | Diff | GT Verified |
|-------|-----------|--------|------|-------------|
| 64535 | 914.20 | 1,404.28 | +53.6% | GT correct. VAT explicitly not reimbursable. System over-covers tubes + adds VAT. |
| 64386 | 2,429.46 | 3,478.52 | +43.2% | GT correct. DISPOSITIF DE COM explicitly "non assure". System wrongly covers it. |
| 64792 | 520.68 | 655.50 | +25.9% | GT correct. 40% rate materials-only (GT notes: "Materialkosten"). System excludes labor, over-covers parts. |
| 64818 | 256.95 | 293.72 | +14.3% | GT correct. System covers 2 extra gaskets (CHF 56.70 gross). |

### Notable GT nuance: 64792 materials-only rate

Claim 64792's GT notes say "Materialkosten sind wie folgt erstattet: ab 110.000 Km zu 40 %" —
the 40% rate applies to **materials only**, not labor. Other claims (64168, 64358, 64659, 65027,
64288) say "Materialkosten **und Arbeitskosten**" — rate applies to both.

The system always applies the reimbursement rate to all covered items (parts + labor). This is
correct for most claims but incorrect for 64792-type policies where the rate is materials-only.

The GT JSON field `reimbursement_rate_pct=40` does not capture this distinction. The rate
applicability (materials-only vs materials+labor) can only be determined from the coverage_notes
text or the original policy document.
