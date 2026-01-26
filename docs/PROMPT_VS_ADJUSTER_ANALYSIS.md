# Prompt vs Adjuster Analysis Report

**Date:** 2026-01-26 (Updated)
**Prompt Analyzed:** `workspaces/nsa/config/prompts/claims_assessment.md`
**Adjuster Notes:** Claims 65258, 65196, 65157, 65128

## Summary

The prompt covers **~90%** of the adjuster's core checks after recent updates. There are **4 notable gaps** remaining where the adjuster performs checks that the prompt does not adequately address.

**Major improvement since last analysis:** Service History Compliance, Assistance Package Items, and VAT Handling for Companies are now fully covered.

---

## What the Prompt Covers Well ✅

| Adjuster Check | Prompt Coverage | Notes |
|----------------|-----------------|-------|
| Component coverage (is part insured?) | Check 5 - uses `_coverage_lookup` | All 4 claims |
| Mileage limit validation | Check 3 - compares odometer vs `km_limited_to` | All 4 claims |
| VIN/vehicle matching | Check 2 - Vehicle ID Consistency | All 4 claims |
| Policy period validity | Check 1 - Policy Validity | All 4 claims |
| Pre-existing damage/fraud | Check 1b - Damage Date Validity | Explicit in 65157 |
| **Service History Compliance** | **Check 4b - NEW** | 12-month interval rule |
| **Assistance Package (rental/towing)** | **Check 5b - NEW** | Keywords detection, CHF 100/day limit |
| **VAT Handling for Companies** | **Check 6 Step 5 - NEW** | Company indicator detection |
| Payout calculation with coverage %, deductible, max cap | Check 6 - detailed formula | All 4 claims |
| Max coverage strategy ("close the case") | Check 6 adjuster tip | 65258 |
| Shop Authorization | Check 4a - `_shop_authorization_lookup` | All claims |
| Early rejection for non-covered components | Check 7 HARD FAIL | 65128 |

---

## GAPS: Adjuster Checks NOT in the Prompt ❌

### 1. ⚠️ Vehicle Owner = Policyholder Check (NEW - CRITICAL)

**Status:** NOT IMPLEMENTED

**Adjuster says (3 of 4 claims):**
> "Is the vehicle owner also the policyholder?"

**Prompt says:** Check 2 (Vehicle ID Consistency) only verifies VIN matching:
> "Do VINs/chassis numbers match across all documents?"

**Gap:** The prompt does NOT verify that the vehicle **owner** matches the **policyholder**. This is a fraud vector:
- Someone could take out a policy naming themselves as policyholder
- Submit a claim for a vehicle they don't actually own
- Pass all current checks because VIN is consistent across documents

**Claims mentioning this:**
- 65258: "Is the vehicle owner also the policyholder?"
- 65196: "Is the vehicle owner also the policyholder?"
- 65157: "Is the vehicle owner also the policyholder?"

**Recommendation:** Add Check 2b: Owner/Policyholder Match
```markdown
### Check 2b: Owner/Policyholder Match
- Look for `vehicle_owner`, `fahrzeughalter`, or `halter` in claim facts
- Compare against `policyholder_name` or `versicherungsnehmer`
- If owner ≠ policyholder → Flag for REFER_TO_HUMAN (potential fraud indicator)
- Document any discrepancy in fraud_indicators
```

---

### 2. Documentation Requirements for Costly Repairs (Claims 65157, 65258)

**Adjuster says:**
> "In cases where entire units need to be replaced... we want to know exactly how the defect manifests... a cost estimate alone is not sufficient"

> "We require a copy of the delivery note for the parts quoted, as well as photos of the repair process"

**Prompt:** No mention of requesting delivery notes, repair photos, or additional proof for high-value claims.

**Gap:** Not covered at all. This is a post-approval verification step.

---

### 3. Error Memory/Fault Code Verification for Repair Justification (Claim 65157)

**Adjuster says:**
> "We check the error memory entry together with what was offered to see whether the repair is justified. Usually based on experience or the internet."

**Prompt:** Mentions fault memory dates for damage timing (Check 1b), but NOT for verifying the repair scope is technically justified.

**Gap:** Partially covered (dates only, not repair justification). The prompt should verify that diagnostic findings support the proposed repair.

---

### 4. Part Number Research Approach

**Adjuster says (65196, 65128):**
> "First, I need to find out exactly what kind of valve it is... by searching the internet"

> "If a component has a strange or unknown name, we try to find out what kind of component it is based on the part number. We do this by searching the internet."

**Prompt says:**
> "DO NOT research part numbers yourself" - relies on pre-computed `_coverage_lookup`

**Difference:** Intentional design choice. The prompt assumes lookups handle this; adjuster manually researches. This is acceptable if lookup tables are comprehensive.

---

## Resolved Since Last Analysis ✅

These gaps from the previous analysis (2026-01-25) have been **FIXED**:

| Previous Gap | Now Covered By | Status |
|--------------|----------------|--------|
| Service History Compliance | Check 4b (12-month interval rule) | ✅ FIXED |
| Assistance Package (rental/towing) | Check 5b (keywords detection) | ✅ FIXED |
| VAT Handling for Companies | Check 6 Step 5 (company indicators) | ✅ FIXED |

---

## Minor Differences

| Area | Adjuster | Prompt |
|------|----------|--------|
| Early rejection | "I am not conducting any further examinations to save time" (65128) | All 7 checks in order, but HARD FAIL logic allows early termination |
| Part lookup approach | Manual internet research | Pre-computed `_coverage_lookup` field |
| Repair shop contact | "If necessary, we ask the repair shop" | REFER_TO_HUMAN (no specific action) |

---

## Per-Claim Summary

### Claim 65258 (Cylinder Head Repair)
- **Covered:** Component coverage, mileage, VIN, service history, assistance package, max coverage cap, deductible, VAT
- **Gap:** Owner = policyholder check, delivery notes/repair photos
- **Outcome:** Approved at max coverage (CHF 5,000 - 10% = CHF 4,500)

### Claim 65196 (Valve - Air Suspension)
- **Covered:** Component coverage, mileage, VIN, service history, assistance package (CHF 100/day), VAT
- **Gap:** Owner = policyholder check, part number research approach
- **Outcome:** Requires assistance package verification

### Claim 65157 (Pre-existing Damage Investigation)
- **Covered:** Component coverage, mileage, VIN, service history, damage date fraud check
- **Gap:** Owner = policyholder check, error memory repair justification, proof of defect
- **Outcome:** Flagged for fraud (warranty taken out after damage)

### Claim 65128 (Trunk Lock - Not Covered)
- **Covered:** Component coverage check, early rejection logic
- **Gap:** Owner = policyholder check not mentioned (claim rejected early)
- **Outcome:** Rejected (trunk lock not in scope)

---

## Conclusion

The prompt now handles **~90%** of the adjuster's workflow, up from ~80% in the previous analysis.

**Critical gap to address:**
1. **Vehicle Owner = Policyholder** - This is a fraud check the adjuster performs on every claim but is NOT in the prompt. Should be added as Check 2b.

**Nice-to-have improvements:**
2. Documentation requirements for high-value repairs (delivery notes, photos)
3. Error memory verification for repair justification
4. Explicit escalation paths when components are unknown

---

## Recommended Prompt Enhancement

Add the following to Check 2:

```markdown
### Check 2b: Owner/Policyholder Match

**Verify the vehicle owner matches the policyholder.**

This prevents fraud where someone takes out a policy for a vehicle they don't own.

**Check Steps:**
1. Look for vehicle owner information:
   - `vehicle_owner`, `fahrzeughalter`, `halter`, `registered_owner`
   - May be found in vehicle registration, service history, or invoice documents
2. Compare against policyholder:
   - `policyholder_name`, `versicherungsnehmer`, `policy_holder`
   - Found in nsa_guarantee or policy documents
3. Evaluate match:
   - Exact match or minor variations (spelling, abbreviations) → PASS
   - Clear mismatch → REFER_TO_HUMAN (potential fraud indicator)
   - Owner info not available → Document assumption, proceed with MEDIUM confidence impact

**Decision Logic:**
- **PASS**: Owner = Policyholder (or reasonable variation)
- **INCONCLUSIVE**: Owner info not found in claim facts → REFER_TO_HUMAN
- **FAIL**: Clear mismatch between owner and policyholder → REFER_TO_HUMAN with fraud flag
```
