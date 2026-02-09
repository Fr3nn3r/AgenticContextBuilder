# Customer Feedback Report - February 2026

**Source**: Azure production server (contextbuilder-nsa)
**Downloaded**: 2026-02-07
**Reviewer**: stefano
**Period**: 2026-02-02 to 2026-02-06

## Summary

| Rating | Count | Percentage |
|--------|-------|------------|
| Good   | 5     | 24%        |
| Poor   | 16    | 76%        |
| **Total** | **21** | 100% |

## Feedback by Category

### 1. Coverage Determination Errors (13 claims)

The system incorrectly identified components as covered when they are excluded from the warranty.

| Claim ID | Component | Feedback |
|----------|-----------|----------|
| 64961 | Control arm | Not covered by warranty |
| 65002 | NOx sensors, wiring harness, engine control unit | Not covered by warranty |
| 65029 | AdBlue injection nozzle | Not covered by warranty |
| 65054 | Software updates | Considered "adjustments" - not covered |
| 65060 | Simmerring (seal) | Not insured |
| 65113 | High-pressure pump | Not insured |
| 65128 | Trunk lid lock | Not insured |
| 65160 | Oil filter support | Not insured |
| 65174 | Software updates | Not covered |
| 65183 | Steering wheel | Not insured |
| 65190 | Water pump | Cooling system not covered by warranty |
| 65208 | Cylinder head cover | Not covered (confused with cylinder head) |
| 65268 | Cylinder head cover | Not insured (system confused it with cylinder head which IS covered) |

**Action needed**: Review and update coverage rules for these component categories:
- Suspension (control arm)
- Emissions system (NOx sensors, AdBlue)
- Software/adjustments
- Seals (Simmerring)
- Fuel system (high-pressure pump)
- Body/locks (trunk lid lock)
- Engine accessories (oil filter support)
- Cooling system (water pump)
- Interior (steering wheel)
- Engine covers vs engine internals (cylinder head cover vs cylinder head)

### 2. Calculation Display Format (1 claim)

| Claim ID | Feedback |
|----------|----------|
| 64166 | "I would like to see a more easily comprehensible calculation. A list of all parts that are covered and a list of all labor that is covered. Then a subtotal for parts and a subtotal for labor, then VAT is added, then the deductible is subtracted or shown, and finally the total." |

**Action needed**: Redesign assessment output to show:
1. Covered parts list with prices
2. Covered labor list with prices
3. Parts subtotal
4. Labor subtotal
5. VAT calculation
6. Deductible
7. Final total

### 3. Data Quality Issues (1 claim)

| Claim ID | Issue |
|----------|-------|
| 64297 | Odometer reading of 155,500 km is incorrect. Odometer photo missing. Critical for km-limited policies. |

**Action needed**: Flag missing odometer photos, especially for policies with kilometer limits.

### 4. Domain Knowledge Gap (1 claim)

| Claim ID | Issue |
|----------|-------|
| 65052 | Service was NOT overdue - invoice proves service on Feb 27, 2025. Damage caused by timing chain (uninsured), but this was confirmed via repairer inquiry, not visible in documents. |

**Action needed**:
- Improve service history verification
- Document that some exclusions (e.g., timing chain damage) require external confirmation and cannot be determined from claim documents alone

### 5. Test/Placeholder Feedback (3 claims)

| Claim ID | Rating | Comment |
|----------|--------|---------|
| 64358 | Good | "test" |
| 64535 | Good | "efwe" |
| 64986 | Good | *(empty)* |
| 65021 | Good | *(empty)* |
| 65215 | Good | *(empty)* |

These appear to be test entries or quick approvals without detailed feedback.

## Raw Feedback Data

<details>
<summary>Click to expand all feedback entries</summary>

### 64166 (Poor)
- **Date**: 2026-02-03T08:34:54
- **Comment**: In general, I would like to see a more easily comprehensible calculation. A list of all parts that are covered and a list of all labor that is covered. Then a subtotal for parts and a subtotal for labor, then VAT is added, then the deductible is subtracted or shown, and finally the total.

### 64297 (Poor)
- **Date**: 2026-02-06T09:48:34
- **Comment**: Odometer reading of 155,500 km ist not the actual millage. Photo odometer is missing, especially in this claim important as the policy is limited on kilometers.

### 64358 (Good)
- **Date**: 2026-02-02T07:00:05
- **Comment**: test

### 64535 (Good)
- **Date**: 2026-02-02T14:57:53
- **Comment**: efwe

### 64961 (Poor)
- **Date**: 2026-02-03T08:43:52
- **Comment**: The main component is the control arm, which is not covered by this warranty.

### 64986 (Good)
- **Date**: 2026-02-03T08:44:25
- **Comment**: *(empty)*

### 65002 (Poor)
- **Date**: 2026-02-03T08:51:29
- **Comment**: The Nox sensors, wiring harness, and engine control unit are not covered by the warranty.

### 65021 (Good)
- **Date**: 2026-02-03T08:44:56
- **Comment**: *(empty)*

### 65029 (Poor)
- **Date**: 2026-02-03T08:23:04
- **Comment**: The main component of the cost estimate is the AdBlue injection nozzle, which is not covered by the warranty.

### 65052 (Poor)
- **Date**: 2026-02-03T08:42:26
- **Comment**: Service was not overdue. An invoice has been filed proving that the service was performed on February 27, 2025. Furthermore, we have rejected this claim because the damage was caused by the uninsured timing chain. However, this was confirmed by the repairer when we inquired. This cannot be gleaned from the documents. This is based on our experience that, given a certain type of damage, we suspect this and then seek confirmation.

### 65054 (Poor)
- **Date**: 2026-02-03T08:26:24
- **Comment**: These are software updates that can be considered adjustments and are therefore not covered by the warranty.

### 65060 (Poor)
- **Date**: 2026-02-03T09:04:29
- **Comment**: Main component: Simmerring - not insured

### 65113 (Poor)
- **Date**: 2026-02-03T09:01:16
- **Comment**: Main component: High-pressure pump - not insured

### 65128 (Poor)
- **Date**: 2026-02-03T09:02:58
- **Comment**: Main component: Trunk lid lock - not insured

### 65160 (Poor)
- **Date**: 2026-02-03T08:45:55
- **Comment**: Main component: Oil filter support - not insured

### 65174 (Poor)
- **Date**: 2026-02-03T08:49:48
- **Comment**: Software updates - not covered

### 65183 (Poor)
- **Date**: 2026-02-03T08:46:55
- **Comment**: Main component: Steering wheel - not insured

### 65190 (Poor)
- **Date**: 2026-02-03T08:28:48
- **Comment**: The main component here is the water pump, which is not covered by insurance, as the cooling system is not covered by the warranty.

### 65208 (Poor)
- **Date**: 2026-02-03T08:48:54
- **Comment**: The cylinder head cover is not covered by the warranty.

### 65215 (Good)
- **Date**: 2026-02-03T09:05:42
- **Comment**: *(empty)*

### 65268 (Poor)
- **Date**: 2026-02-03T08:21:11
- **Comment**: The cylinder head is insured, but the part offered is not the cylinder head, but the cylinder head cover, which is not insured.

</details>

## Priority Actions

1. **High**: Fix coverage determination for commonly misclassified components (control arm, water pump, cylinder head cover, etc.)
2. **High**: Add "cylinder head cover" as distinct from "cylinder head" in component matching
3. **Medium**: Add software updates/adjustments as explicit exclusion category
4. **Medium**: Redesign calculation output format per customer request
5. **Low**: Add odometer photo validation warning for km-limited policies
