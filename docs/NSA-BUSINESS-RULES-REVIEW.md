# NSA Business Rules Review

**Purpose**: Catalog all assumptions and rules currently embedded in the claims assessment system, flag unknowns, and drive clarification with NSA business team.

**System context**: Automated assessment of motor warranty claims (APPROVE / REJECT / REFER_TO_HUMAN). The pipeline runs deterministic screening checks, then optionally an LLM assessment.

---

## 1. Shop / Garage Authorization

### Current Implementation
- We maintain a list of ~50 garages authorized by exact name (AMAG, Emil Frey, Mercedes-Benz, etc.)
- We also match by brand pattern (e.g., any garage with "BMW" or "Toyota" in the name is assumed authorized)
- **If the garage is unknown, the system outputs REFER_TO_HUMAN**

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 1.1 | Is there a master list of authorized garages we can integrate? Or is it brand-based? | We pattern-match on brand names |
| 1.2 | Is a claim from a non-authorized garage automatically denied, or just flagged? | We treat it as REFER_TO_HUMAN, never auto-reject |
| 1.3 | Does "authorized" mean manufacturer-certified, or NSA-partner? What's the distinction? | We assume manufacturer-certified = authorized |
| 1.4 | Are independent garages ever acceptable? Under what conditions? | Currently: unknown = REFER |
| 1.5 | Is shop authorization a hard reject criterion, or an informational flag? | Currently: soft check (not a hard fail) |

---

## 2. Service Compliance (Time Since Last Service)

### Current Implementation
- We check if the last recorded service was within **1,825 days (5 years)** of the claim date
- This is a **soft check**: it flags the gap but **never auto-rejects**
- We do not distinguish by vehicle type, mileage, or service interval schedule

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 2.1 | What is the actual maximum allowed gap since last service? Is 5 years correct? | 5 years (1,825 days) |
| 2.2 | Does the threshold vary by vehicle type, age, or mileage? | No, fixed at 5 years for all |
| 2.3 | Does "service" mean any maintenance visit, or specifically a manufacturer-scheduled service? | Any service entry counts |
| 2.4 | Does it matter whether the service was at an authorized dealer vs. independent garage? | No distinction currently |
| 2.5 | Should service non-compliance be a hard reject, or remain informational? | Currently informational only |
| 2.6 | If the service history document is missing entirely, is that grounds for rejection? | Currently: SKIPPED, not rejected |

---

## 3. Vehicle Age and Coverage Reduction

### Current Implementation
- We have a configurable rule: vehicles **>= 8 years old** get coverage reduced to **40%**
- **This is currently DISABLED for NSA** (`age_threshold: null` in config) -- NSA policies rely on mileage bands only
- The mileage-based coverage scale comes from each policy document (e.g., "90% up to 50,000 km, 70% up to 80,000 km...")

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 3.1 | Does vehicle age ever affect coverage? If so, what are the thresholds? | Currently disabled (mileage-only) |
| 3.2 | Is there ever a maximum vehicle age beyond which no coverage applies? | No age cap currently |
| 3.3 | Is the age calculated from first registration date, or from policy start date? | From first registration |
| 3.4 | If age-based rules exist, do they override or combine with mileage-based tiers? | Currently mileage-only |

---

## 4. Coverage Scale (Mileage-Based Depreciation)

### Current Implementation
- Each policy document contains a `coverage_scale` defining tiers, e.g.:
  - Up to 50,000 km: 90%
  - Up to 80,000 km: 70%
  - Up to 110,000 km: 50%
- The current odometer reading determines which tier applies
- **If the policy is silent**, we fall back to defaults:

| Mileage Band | Parts | Labor |
|---|---|---|
| 0 -- 50,000 km | 80% | 100% |
| 50,001 -- 80,000 km | 60% | 100% |
| 80,001 -- 110,000 km | 40% | 100% |
| 110,001+ km | 20% | 100% |

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 4.1 | Are the fallback tiers above correct when a policy doesn't specify coverage_scale? | See table above |
| 4.2 | Is labor always at 100% regardless of mileage tier? | Yes, labor = 100% always |
| 4.3 | Does the tier apply to the odometer at time of claim, or at time of policy start? | Odometer at claim time |
| 4.4 | "A partir de X km" -- does the tier start AT the threshold or AFTER? | At the threshold (inclusive) |
| 4.5 | If the odometer is below the first stated threshold, is coverage 100%? | Yes, we assume 100% |

---

## 5. Payout Calculation Formula

### Current Implementation

```
1. Start with covered items total (parts + labor for covered components)
2. Apply coverage % from mileage tier (parts get tier %, labor gets 100%)
3. Cap at max_coverage if exceeded (typically CHF 5,000)
4. Add Swiss VAT: subtotal * 1.081 (8.1%)
5. Calculate deductible: max(excess_percent * subtotal_with_vat, excess_minimum)
   - Typical: max(10% * amount, CHF 150)
6. Subtract deductible
7. If policyholder is a COMPANY: divide by 1.081 (remove VAT)
   - Company detected by suffix: AG, SA, GmbH, Sarl, Ltd, Inc, etc.
```

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 5.1 | Is the VAT rate always 8.1%? Does it vary by canton or service type? | Fixed at 8.1% |
| 5.2 | Is the deductible formula `max(percentage * amount, minimum)` correct? | Yes |
| 5.3 | Is the deductible applied AFTER the max coverage cap, or before? | After capping |
| 5.4 | For companies: we remove VAT from the final payout. Is that correct? | Yes, companies recover VAT separately |
| 5.5 | How do we reliably distinguish company vs. individual? Just by name suffix? | Suffix matching (AG, SA, GmbH...) |
| 5.6 | Is max_coverage per claim, per year, or per event? | Per claim (current assumption) |
| 5.7 | "Payout near max (>90%) -> use max_coverage" -- is this an actual NSA rule? If payout is close to max, should we just round up to max? | Currently implemented |
| 5.8 | Does max_coverage_engine differ from max_coverage? When does engine-specific cap apply? | Both extracted from policy, logic unclear |

---

## 6. Damage Date and Policy Validity

### Current Implementation
- **Policy validity**: claim date must be within `start_date` to `end_date` -> **hard fail** if outside
- **Damage date**: must also be within policy period -> **hard fail** if before policy start (pre-existing damage)
- **Waiting period**: policies have a `waiting_period_days` (e.g., 15 days). Damage during waiting period is not covered
- If damage date is missing, the check is SKIPPED (not failed)

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 6.1 | If the damage date is missing from all documents, should the claim be rejected or referred? | Currently: SKIPPED -> REFER |
| 6.2 | Is the waiting period always measured from policy start? | Yes |
| 6.3 | Does the waiting period apply to all claim types, or only first claims? | All claims |
| 6.4 | Can we use the cost estimate document date as a proxy for claim date? | Currently yes |
| 6.5 | If damage date is before policy start but claim is filed during policy period, is that always a reject? | Yes, treated as pre-existing |

---

## 7. Component Coverage Rules

### Current Implementation
- We maintain a mapping of ~350 part numbers to component systems (engine, axle_drive, transmission, etc.)
- We also keyword-match descriptions in French/German to systems
- The policy defines which systems are covered (e.g., "Option turbo: Couvert", "Option hybride: Non couvert")
- **If a part is unknown**, the system either asks the LLM or marks it REVIEW_NEEDED

### Hard Rules (Always NOT COVERED)
- Consumables: oil, oil filter, air filter, brake fluid, coolant, wiper blades
- Fees: disposal (Entsorgung), environmental (Umwelt), rental car (Ersatzfahrzeug), cleaning (Reinigung)
- Diagnostic labor: standalone diagnostics, testing, calibration, coding
- AdBlue / urea system

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 7.1 | Is there a definitive list of covered component systems per guarantee type (BASIC, COMFORT, etc.)? | We extract from each policy document |
| 7.2 | Are labor charges for covered repairs always covered, or are there exceptions? | Labor for covered parts = covered; standalone labor = not covered |
| 7.3 | Are gaskets, seals, and fasteners covered when they support a covered repair? | Yes, treated as ancillary items |
| 7.4 | Is diagnostic labor ever covered (e.g., when it leads to a covered repair)? | Currently: never covered |
| 7.5 | Is valve cover (couvre-culasse) covered or not? We currently exclude it. | NOT_COVERED (hardcoded exclusion) |
| 7.6 | Are brake components (pads, discs, calipers) covered? They appear in our keyword list but are often considered wear items | Currently in our keyword system as "brakes" |
| 7.7 | When a part is not in our lookup tables, what should the default be -- REFER or NOT_COVERED? | Currently: LLM decides, or REFER if uncertain |
| 7.8 | Is there a minimum claim amount below which claims are auto-denied? | No minimum currently |

---

## 8. Owner / Policyholder Match

### Current Implementation
- We compare the vehicle owner name (from registration doc) with the policyholder name (from guarantee)
- Exact match or substring match -> PASS
- Mismatch -> INCONCLUSIVE (sent to LLM for judgment)
- This is a **soft check** (not a hard fail)

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 8.1 | Is an owner/policyholder mismatch grounds for rejection, or just a flag? | Currently: flag only (soft check) |
| 8.2 | Are there legitimate reasons for mismatch (e.g., company car, leasing, family member)? | We assume yes, hence soft check |
| 8.3 | Should we check if the beneficiary (from the guarantee) matches the owner? | We currently check policyholder only |

---

## 9. VIN Consistency

### Current Implementation
- We compare VINs across all documents (guarantee, registration, cost estimate)
- Mismatch -> FAIL (soft, sent to LLM)
- Currently a soft check

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 9.1 | Is a VIN mismatch an automatic reject? | Currently: soft check |
| 9.2 | Are minor formatting differences acceptable (spaces, dashes in VIN)? | We normalize, but unclear on threshold |

---

## 10. Assistance Package Items

### Current Implementation
- We detect rental car, towing, and roadside assistance items in invoices
- These are **excluded from the standard payout** and flagged for separate handling
- We look for keywords: ERSATZFAHRZEUG, MIETWAGEN, RENTAL, ABSCHLEPP, TOWING, REMORQUAGE

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 10.1 | What are the limits for assistance items? (e.g., CHF 100/day rental, CHF 1,000 max?) | We flag but don't calculate |
| 10.2 | Are assistance items processed as a separate claim, or as part of the same claim? | Currently: flagged, not calculated |
| 10.3 | Does the policy "Assistance: Non couvert" mean these items are fully excluded? | Yes, we exclude them |

---

## 11. Decision Thresholds

### Current Implementation

| Condition | Decision |
|---|---|
| Any hard-fail check = FAIL | Auto-REJECT (no LLM needed) |
| All checks PASS | LLM decides (usually APPROVE) |
| Checks have INCONCLUSIVE/SKIPPED but no FAIL | LLM decides (often REFER_TO_HUMAN) |
| APPROVE decision but final_payout = CHF 0 | Override to REJECT |

### Hard-Fail Checks (auto-reject if FAIL)
1. Policy validity (claim outside policy period)
2. Damage date (pre-existing damage)
3. Mileage compliance (exceeds km limit)
4. Component coverage (primary repair not covered)

### Soft Checks (informational, never auto-reject)
- VIN consistency
- Owner/policyholder match
- Shop authorization
- Service compliance
- Assistance items

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 11.1 | Should shop authorization be a hard fail? (Currently it's soft) | Soft check |
| 11.2 | Should VIN mismatch be a hard fail? | Soft check |
| 11.3 | Is there a confidence threshold below which we should always REFER? | No formal threshold |
| 11.4 | When multiple soft checks are INCONCLUSIVE, should we auto-REFER? | Currently: LLM decides |

---

## 12. Data Completeness Rules

### Current Implementation
- If a critical document is missing (e.g., no cost estimate), most checks get SKIPPED
- Missing data = REFER_TO_HUMAN (never auto-reject for missing data, never auto-approve)
- Exception: missing cost estimate means no line items, so component coverage = SKIPPED

### Questions for NSA

| # | Question | Current Assumption |
|---|----------|-------------------|
| 12.1 | If the cost estimate is missing, should the claim be rejected outright? | Currently: REFER |
| 12.2 | What is the minimum document set required to process a claim? (Guarantee + cost estimate + dashboard photo? Registration too?) | All 4 expected but not enforced |
| 12.3 | If service history is missing, does that affect the decision? | Currently: service check = SKIPPED, no impact |

---

## Summary: Top Priorities for Clarification

| Priority | Topic | Impact |
|---|---|---|
| **P0** | Shop authorization: hard fail vs. soft check, master list? | Affects 5+ claims per batch |
| **P0** | Service compliance: what's the actual threshold? Varies by car? | Currently guessed at 5 years |
| **P0** | Component coverage: definitive list per guarantee type? | Main source of false rejects |
| **P1** | Age-based depreciation: does it exist for NSA? | Currently disabled |
| **P1** | Payout formula: VAT timing, deductible order, company detection | 12+ amount mismatches |
| **P1** | Diagnostic labor: ever covered? | Currently always excluded |
| **P2** | Assistance item limits and handling | Flagged but not calculated |
| **P2** | Owner/policyholder mismatch policy | Soft check, unclear if correct |
| **P2** | Missing data policy: reject vs. refer | Currently always REFER |
