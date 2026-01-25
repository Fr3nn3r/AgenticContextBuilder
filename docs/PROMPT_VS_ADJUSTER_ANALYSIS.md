# Prompt vs Adjuster Analysis Report

**Date:** 2026-01-25
**Prompt Analyzed:** `workspaces/nsa/config/prompts/claims_assessment.md`
**Adjuster Notes:** Claims 65258, 65196, 65157, 65128

## Summary

The prompt covers **most** of the adjuster's core checks, but there are **6 notable gaps** where the adjuster performs checks that the prompt does not adequately address.

---

## What the Prompt Covers Well ✅

| Adjuster Check | Prompt Coverage |
|----------------|-----------------|
| Component coverage (is part insured?) | Check 5 - uses `_coverage_lookup` |
| Mileage limit validation | Check 3 - compares odometer vs `km_limited_to` |
| VIN/vehicle matching | Check 2 - Vehicle ID Consistency |
| Policy period validity | Check 1 - Policy Validity |
| Pre-existing damage/fraud (65157) | Check 1b - Damage Date Validity |
| Payout calculation with coverage %, deductible, max cap | Check 6 - detailed formula |
| Max coverage strategy ("close the case") | Mentioned in Check 6 adjuster tip |

---

## GAPS: Adjuster Checks NOT in the Prompt ❌

### 1. Service History Compliance (All claims)
- **Adjuster says:** "Has the service been performed in accordance with the manufacturer's specifications, or is it overdue? The service must not be overdue."
- **Prompt says:** Check 4 focuses on whether the **current repair shop is authorized** (via `_shop_authorization_lookup`)
- **Gap:** Prompt does not check whether **historical maintenance is up to date** per manufacturer specs

### 2. Assistance Package (Replacement Car/Towing) (Claim 65196)
- **Adjuster says:** "Check whether the assistance package covers this and how much the replacement car coverage amounts to" (CHF 100/day, max CHF 1,000/event)
- **Prompt:** No mention of assistance package, rental car, or towing coverage
- **Gap:** Not covered at all

### 3. VAT Handling for Company Policyholders (Claims 65258, 65196)
- **Adjuster says:** "If the policyholder is a company, we are not obliged to reimburse VAT. This is deducted."
- **Prompt:** No mention of VAT treatment or company vs individual distinction
- **Gap:** Not covered at all

### 4. Documentation Requirements for Costly Repairs (Claims 65157, 65258)
- **Adjuster says:** "In cases where entire units need to be replaced... we want to know exactly how the defect manifests... a cost estimate alone is not sufficient"
- **Adjuster also says:** "We require a copy of the delivery note for the parts quoted, as well as photos of the repair process"
- **Prompt:** No mention of requesting delivery notes, repair photos, or additional proof
- **Gap:** Not covered at all

### 5. Error Memory/Fault Code Verification (Claim 65157)
- **Adjuster says:** "We check the error memory entry together with what was offered to see whether the repair is justified. Usually based on experience or the internet."
- **Prompt:** Mentions fault memory dates for damage timing, but **NOT** for verifying repair is justified
- **Gap:** Partially covered (dates only, not repair justification)

### 6. Part Number Research for Unknown Parts (Claim 65196)
- **Adjuster says:** "First, I need to find out exactly what kind of valve it is... by searching the internet" and "we try to find out what kind of component it is and where it belongs based on the part number"
- **Prompt says:** "DO NOT research part numbers yourself" - relies on pre-computed lookups
- **Difference:** Adjuster manually researches; prompt forbids this (assumes lookup handles it)

---

## Minor Differences

| Area | Adjuster | Prompt |
|------|----------|--------|
| Early rejection | "I am not conducting any further examinations to save time" (65128) | All 7 checks in order |
| Part lookup approach | Manual internet research | Pre-computed `_coverage_lookup` field |

---

## Conclusion

The prompt handles **~80%** of the adjuster's workflow well, especially:
- Core eligibility checks (policy, mileage, VIN, component)
- Fraud detection (pre-existing damage)
- Payout calculation

**Missing functionality** that could cause incorrect assessments:
1. **Service history compliance** - could approve claims with overdue maintenance
2. **Assistance package** - won't calculate rental car payouts
3. **VAT deduction for companies** - may overpay company claims
4. **Proof requirements** - won't flag costly repairs needing documentation
