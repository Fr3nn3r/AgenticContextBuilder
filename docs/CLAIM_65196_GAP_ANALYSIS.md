# Gap Analysis: Actual Claims Decision vs. Our Assessment

**Claim ID**: 65196
**Date**: 2026-01-26
**Purpose**: Analyze the gap between NSA's actual claims decision and our automated assessment to identify improvements needed in the payout calculation logic.

---

## Summary Comparison

| Metric | Actual NSA Decision | Our Assessment | Difference |
|--------|---------------------|----------------|------------|
| **Final Payout** | **CHF 1,688.82** | **CHF 2,678.77** | **+CHF 989.95** |
| Coverage % | 80% | 60% | Different tier |
| Covered base | CHF 2,366.90 | CHF 3,148.85 | +CHF 781.95 |
| Deductible | CHF 204.70 | CHF 297.88 | +CHF 93.18 |
| VAT handling | Explicit (add, then subtract for company) | Not shown | Missing step |

---

## The Actual NSA Calculation (from PDF)

Source: `data/08-NSA-Supporting-docs/65196/Claim_Decision_for_Claim_Number_65196 1.pdf`

```
1. Covered items (valve + related labor only):
   - Zentralhydraulikventil (8W0616887):    CHF 1,766.90
   - Arbeit (labor):                        CHF   600.00
   - Total covered base:                    CHF 2,366.90

2. Apply 80% coverage:
   2,366.90 × 0.80 = CHF 1,893.52

3. Add VAT (8.1%):
   1,893.52 × 1.081 = CHF 2,046.92

4. Calculate deductible (10% on VAT-inclusive):
   2,046.92 × 0.10 = CHF 204.70

5. Subtract deductible:
   2,046.92 - 204.70 = CHF 1,842.22

6. Subtract VAT (company can reclaim):
   1,842.22 - 153.40 = CHF 1,688.82

Replacement car billed separately: CHF 95.02 (87.90 + VAT)
```

---

## Key Gaps Identified

### 1. Coverage Percentage Mismatch

| Source | Value | At 74,359 km |
|--------|-------|--------------|
| Our claim_facts `coverage_scale` | "80% up to 50k, 60% up to 80k, 40% up to 110k" | Should be **60%** |
| Actual NSA decision | "ab 50.000 Km zu 80%" | Applied **80%** |

**Issue**: Either our coverage_scale extraction is wrong, or NSA uses a different calculation (e.g., mileage at policy inception: 69,850 km). This needs clarification with business.

### 2. Line Item Filtering

**Actual adjuster only covered:**
- The valve (primary defective part): CHF 1,766.90
- Labor directly related to valve replacement: CHF 600.00
- **Total: CHF 2,366.90**

**Our assessment included:**
- All labor items (diagnostic, bumper removal, calibration, etc.): ~CHF 1,344
- All parts (valve + hydraulic oil): CHF 1,804.85
- **Total covered: CHF 3,148.85**

**Gap**: The human adjuster excluded CHF ~890 of labor that our system included because:

| Item | Amount | Our Status | Actual Status |
|------|--------|------------|---------------|
| GFS/GEFUEHRTE FUNKTION DIAGNOSE | CHF 240.00 | covered | excluded |
| ABDECKUNG F STOSSFAENGER HINTEN A+E | CHF 168.00 | unknown | excluded |
| ZENTRALVENTILE AUS- | CHF 120.00 | covered | included (part of CHF 600) |
| RAEDER AUS- U.EINGEBAUT | CHF 48.00 | covered | excluded |
| HYDRAULIKFLUESSIGKEIT ABG+AUFG | CHF 264.00 | covered | included (part of CHF 600) |
| STG. F SPURWECHSELASSISTENT EINGESTELLT | CHF 120.00 | covered | excluded |
| GFS/GEFUEHRTE FUNKTION | CHF 360.00 | covered | excluded |
| BATTERIE GELADEN | CHF 24.00 | covered | excluded |

**Key insight**: The human adjuster appears to only cover labor DIRECTLY related to the valve replacement (removal/installation of valve, hydraulic fluid work), not diagnostic or ancillary work.

### 3. VAT Handling Order

**NSA's actual order:**
1. Apply coverage % → subtotal
2. Add VAT → gross subtotal
3. Calculate deductible on **gross** (VAT-inclusive)
4. Subtract deductible
5. Subtract VAT for company policyholders

**Our assessment** skips the VAT intermediate step and doesn't show the calculation.

**Important note from NSA decision:**
> "Seit Einführung des Mehrwertsteuergesetzes ist der Versicherungsnehmer der Mehrwertsteuer unterworfen. Diese kann als Vorsteuer in Abzug gebracht werden, weshalb der Betrag von CHF 153,40 nicht zu entschädigen ist."

Translation: Companies can reclaim VAT as input tax, so VAT is not compensated.

### 4. Assistance Items

The replacement car (Ersatzfahrzeug CHF 87.90) is handled **completely separately** with its own approval line (CHF 95.02 incl. VAT), not netted against the main repair payout.

---

## Data Availability Check

**All required data is present in `claim_facts_enriched.json`:**

| Data Needed | Available | Location |
|-------------|-----------|----------|
| Line items with prices | ✓ | `structured_data.line_items` |
| Coverage scale | ✓ | `coverage_scale` (but may need validation) |
| Excess percent (10%) | ✓ | `excess_percent` |
| Excess minimum (CHF 150) | ✓ | `excess_minimum` |
| VAT rate (8.1%) | ✓ | `vat_rate` |
| Company identification | ✓ | `policyholder_name: "EM Haustechnik GmbH"` |
| Odometer | ✓ | `odometer_km: 74359` |
| Assistance limits | ✓ | `assistance_rental_per_day`, `assistance_rental_max_event` |

---

## What Would It Take to Match?

| Change | Complexity | Impact |
|--------|------------|--------|
| **1. Clarify coverage % rule** | Low | Verify with business if mileage at claim or policy inception determines tier |
| **2. Smarter line item filtering** | Medium | Need business rules: only "primary repair" labor, not all labor marked covered |
| **3. Fix VAT calculation order** | Low | Update prompt to: apply coverage → add VAT → deductible on gross → subtract VAT for company |
| **4. Separate assistance items** | Already done | Check 5b already handles this |

---

## Feasibility Assessment

**Doable: YES**

### Approach Options

1. **Quick fix (prompt-only)**: Update the claims assessment prompt with explicit calculation steps matching NSA's methodology. This could reduce the gap significantly.

2. **Medium fix (prompt + validation)**: Add validation rules that flag when our calculation differs significantly from typical NSA patterns (e.g., "labor should be ~30-40% of parts" heuristic).

3. **Full fix (business rule extraction)**: Work with NSA to document their exact rules for:
   - Which labor codes are covered for each repair type
   - How coverage % is determined (claim mileage vs policy mileage)
   - VAT calculation order

### Recommendation

Start with option 1 (prompt update) to fix the VAT calculation order and company deduction. The biggest gap (line item filtering) may require business input to define which labor is "directly related" to a covered repair vs. ancillary.

---

## Files Referenced

- **Actual decision**: `data/08-NSA-Supporting-docs/65196/Claim_Decision_for_Claim_Number_65196 1.pdf`
- **Our assessment**: `workspaces/nsa/claims/65196/context/assessment.json`
- **Enriched facts**: `workspaces/nsa/claims/65196/context/claim_facts_enriched.json`
- **Assessment prompt**: `workspaces/nsa/config/prompts/claims_assessment.md`

---

## Next Steps

1. [ ] Confirm with business: coverage % rule (claim mileage vs policy mileage)
2. [ ] Update prompt with correct VAT calculation order for companies
3. [ ] Define business rules for "primary repair labor" vs "ancillary labor"
4. [ ] Re-run assessment on claim 65196 to verify improvement
