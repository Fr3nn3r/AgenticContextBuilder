# Deep Eval Report — Eval #40

**Eval run**: `eval_20260201_203201`
**Claim run**: `clm_20260201_191735_12a735`
**Date**: 2026-02-01
**Decision accuracy**: 96% (48/50 correct)
**Amount accuracy (±5%)**: 28% (7/25 approved within tolerance)

## Summary

This deep eval compares the system's detailed explanations against the ground truth for every claim — not just whether the decision was right, but whether the *reasoning* was right and, for approved claims, whether the *payment calculation* matches.

| Metric | Value |
|--------|-------|
| Decisions correct | 48/50 (96%) |
| Denied correctly | 23/25 |
| Approved correctly | 25/25 |
| False approves | 2 (claims 65276, 65288) |
| False rejects | 0 |
| Amount within 5% | 7/25 approved claims |
| Amount mismatch (>5%) | 18/25 approved claims |

---

## Part 1: Denied Claims — Explanation Comparison

### 1.1 Correctly denied with matching reason (18/23)

These claims were denied by both the system and the ground truth, and the system identified the same uncovered component.

| Claim | Vehicle | System Identified Component | GT Denial Reason | Match |
|-------|---------|----------------------------|------------------|-------|
| 64951 | Mercedes GLC 400d | LEUCHTEINHEIT (headlight unit) | Headlights not covered | Exact |
| 64961 | BMW 218 Grand Tourer | No covered items (6 uncovered) | Control arms not covered | Good |
| 64986 | Hyundai TUCSON | PM-Sensor 392652U250FFF | Particle filter sensor not covered | Exact |
| 65002 | Mercedes ML 350 | No covered items (10 uncovered) | NOx sensors, wiring, ECU not covered | Good |
| 65021 | Porsche Cayenne E-Hybrid | HEIZUNGSVENTIL | Heating valve + cooling not covered | Exact |
| 65029 | Audi A6 | AdBlue valve/clamp | AdBlue system/injector not covered | Exact |
| 65054 | VW Touareg | No covered items (1 uncovered) | Software updates not covered | Good |
| 65113 | BMW X3 | Injektor DMDC/RDC | High pressure pump + consequential damage | Partial |
| 65129 | Seat Leon | Zahnriemen labor | Timing belt not covered | Exact |
| 65160 | Mini Clubman | No covered items (10 uncovered) | Oil filter housing not covered | Good |
| 65174 | Audi RSq8 | No covered items (1 uncovered) | Software updates not covered | Good |
| 65183 | VW Golf Alltrack | No covered items (3 uncovered) | Steering wheel not covered | Good |
| 65190 | Renault Scenic | Wasserpumpe | Water pump not covered | Exact |
| 65208 | Mini COOPER S | Main d'oeuvre (no covered part) | Valve cover not covered | Partial |
| 65211 | VW Golf GTI | component_coverage fail | Sealing sleeves not covered | Good |
| 65215 | Peugeot 3008 | Mileage + component fail | Urea tank + AdBlue not covered | Exact |
| 65306 | VW T6 KOMBI | component_coverage fail | EGR cooler not covered | Good |
| 65319 | Cupra Leon | component_coverage fail | Threshold/sill not covered | Good |

**Match quality key**: Exact = same specific component named; Good = correctly rejected on component_coverage but generic description; Partial = rejected correctly but named a different part than GT.

### 1.2 Correctly denied but DIFFERENT reason (5/23)

These are the most instructive cases — the system got the right answer (DENY) but for a different or incomplete reason.

#### Claim 64980 — VW Tiguan (Medium severity)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | REJECT | DENY |
| Reason | Payout = CHF 0.00 (deductible exceeds covered amount) | "Police n'est pas valide" (policy not valid) |

The system found the policy dates valid and instead rejected because only CHF 54.95 was covered (most items not on the exhaustive parts list), which after 60% rate and CHF 150 deductible yields zero. The GT says the entire policy was invalid — an administrative status the system has no mechanism to check.

**Gap**: No administrative policy invalidation check exists. The system can only validate date ranges and mileage.

#### Claim 65052 — Peugeot Rifter (Low severity)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | REJECT | DENY |
| Reason | Service compliance: last service 1,878 days ago (>5-year limit) | "Dommages causés par la distribution — non assuré" (timing belt damage not insured) |

Both are valid rejection grounds. The system actually caught both issues (timing chain was `component_not_in_list` in coverage analysis, AND service was overdue), but reported the service compliance failure because it hit first in the check sequence. The GT focuses on the component exclusion.

#### Claim 65060 — Citroen C4 (High severity)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | REJECT | DENY |
| Reason | Payout = CHF 0.00 (deductible exceeds covered amount) | Crankshaft seal, timing cover gasket, valve cover gasket not covered |

The synonym matcher **wrongly tagged gaskets as covered parts**: "Joint de cache soupapes" (valve cover gasket) matched "soupape" → "valve" → "ventilkipphebel" (valve rocker). A gasket for a valve is not the valve itself. Similarly, "Joint du vilebrequin" (crankshaft seal) matched to "crankshaft". The covered amount was small enough (CHF 138.34 at 40%) that the deductible absorbed it, masking the bug.

**Bug**: Synonym matcher too aggressive on gaskets/seals. This is a ticking time bomb — on a claim with higher gasket costs, it would cause a false approve.

#### Claim 65268 — Peugeot 308 (Medium severity)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | REJECT | DENY |
| Reason | Payout = CHF 0.00 (deductible exceeds covered amount) | Valve cover not covered |

The exclusion pattern (`COUVRE.?CULASSE|COUVERCLE.?(?:DE.?)?CULASSE`) correctly caught both valve cover items and marked them not covered. But the primary_repair metadata contradicts this, claiming "cylinder_head is covered" while 100% of line items are excluded by the pattern rule. The system should fail check 5 when all items are excluded.

**Bug**: primary_repair inference contradicts line-item reality.

#### Claim 65307 — VW Golf Club Sport (No severity)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | REJECT | DENY |
| Reason | Mileage exceeded + component coverage fail (checks 3, 5) | Mileage exceeded: 39,491 km vs 39,000 km limit |

The system found MORE reasons to reject than the ground truth noted. Both agree on mileage exceedance.

### 1.3 False Approves — Critical Errors (2 claims)

Both false approves share the **same root cause bug** in cross-category component matching.

#### Claim 65276 — VW T6 (CHF 330 wrongly paid)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | APPROVE (CHF 330) | DENY |
| Reason | All checks passed | EGR valve not covered |

The EGR valve ("REMPL. EGR", CHF 740.05) was identified as `egr_valve` in the `engine` category. Cross-category matching then found it in `brakes` as `bremskraftbegrenzer` (brake force limiter). Both contain "valve" semantics but are entirely different automotive systems. The system then covered CHF 444.03 (60% of 740.05) minus CHF 150 deductible = CHF 330.

#### Claim 65288 — VW California Beach (CHF 1,561 wrongly paid)

| | System | Ground Truth |
|-|--------|--------------|
| Decision | APPROVE (CHF 1,561) | DENY |
| Reason | All checks passed | EGR module not covered |

Identical bug. "Module EGR" (CHF 861.25) cross-category matched to `bremskraftbegrenzer` in brakes. Generic labor (CHF 742.89) was linked to the covered EGR part. Total covered: CHF 1,604.14, minus CHF 173.41 = CHF 1,560.67.

**Combined financial impact**: CHF 1,891 in false payouts.

---

## Part 2: Approved Claims — Payment Calculation Comparison

### 2.1 Within 5% tolerance (7 claims)

| Claim | Vehicle | GT Amount | System Amount | Diff % |
|-------|---------|-----------|---------------|--------|
| 64166 | Ford FOCUS | 1,506.52 | 1,506.54 | +0.001% |
| 64168 | Land Rover Range Rover | 333.69 | 333.68 | -0.003% |
| 64297 | Subaru Impreza 1.5R | 74.00 | 73.98 | -0.03% |
| 64850 | Mercedes SL 500 | 3,914.28 | 3,806.70 | -2.7% |
| 64959 | Ford MUSTANG | 1,480.43 | 1,439.44 | -2.8% |
| 64288 | Land Rover RR Velar | 4,141.02 | 4,301.15 | +3.9% |
| 64393 | Alfa Romeo Stelvio | 2,829.75 | 2,692.50 | -4.9% |

### 2.2 Amount mismatches >5% (18 claims)

| Claim | Vehicle | GT | System | Diff % | Root Cause |
|-------|---------|-----|--------|--------|------------|
| 64792 | Peugeot 3008 | 521 | 2,645 | +408% | System processes larger invoice than GT |
| 64978 | Mitsubishi ASX | 25 | 38 | +50% | Small amounts magnify rate/deductible diff |
| 65040 | Bentley Flying Spur | 1,522 | 2,040 | +34% | Diagnostic labor included (GT excludes) |
| 64818 | Jeep Compass | 257 | 337 | +31% | System includes diagnostic labor |
| 64380 | BMW M3 | 1,171 | 1,424 | +22% | Diagnostic labor + deductible calc differs |
| 64535 | LR Range Rover Evoque | 914 | 1,089 | +19% | Diagnostic labor + vague "Couvercle" part |
| 64386 | Jeep Grand Cherokee | 2,429 | 2,704 | +11% | Extra transmission labor covered |
| 65056 | Audi A4 TDI | 3,600 | 3,892 | +8% | Null coverage_percent; no max cap applied |
| 65027 | BMW Alpina B3 | 673 | 597 | -11% | Age threshold reduction (60%→40%) + wrong deductible |
| 65047 | VW T-Roc | 692 | 612 | -11% | GT is goodwill (flat amount); system computes coverage |
| 65280 | VW Golf GTI Black | 563 | 412 | -27% | Fasteners + brake labor excluded |
| 64659 | Mercedes CLA45 AMG | 2,397 | 1,661 | -31% | Rate formula mismatch + more items excluded |
| 64836 | Rolls Royce Phantom | 2,995 | 1,793 | -40% | Multifunction unit + all labor excluded |
| 64358 | VW Golf GTi | 439 | 261 | -41% | Wrong rate application + smaller base |
| 64984 | Mercedes G500 | 958 | 367 | -62% | Labor read as AW units (1.0) not CHF amounts |
| 65055 | Ford Fiesta | 910 | 345 | -62% | Timing chain parts excluded; GT includes them |
| 64354 | VW Golf eTSI | 940 | 253 | -73% | Most labor excluded |
| 65150 | Audi A8 TFSI e | 1,841 | 336 | -82% | Mirror assembly excluded + null coverage rate |

### 2.3 Root Cause Patterns

| Pattern | Count | Claims | Avg Impact | Direction |
|---------|-------|--------|------------|-----------|
| **A. Over-aggressive labor exclusion** | 7 | 64354, 64380, 64535, 64836, 64984, 65040, 65280 | ~40% | System underpays |
| **B. Reimbursement rate/formula mismatch** | 5 | 64358, 64659, 64818, 64978, 65027 | Variable | Both directions |
| **C. Component classification errors** | 4 | 64535, 64836, 65055, 65150 | ~50% | System underpays |
| **D. Null coverage_percent** | 2 | 65056, 65150 | Severe | Both directions |
| **E. Goodwill payment not handled** | 1 | 65047 | -11% | System underpays |
| **F. Labor extraction (AW vs CHF)** | 1 | 64984 | -62% | System underpays |

#### Pattern A: Over-aggressive labor exclusion

The system frequently excludes labor items that the ground truth considers covered:
- **Diagnostic/troubleshooting labor** ("Recherche des derangements", "GFS/FONCTION GUIDEE") — excluded when no covered part directly referenced
- **Generic labor descriptions** ("Arbeit", "INSTANDSETZUNG VERSCHIEDENES") — excluded due to insufficient detail
- **Labor listed as work units** (AW) of 1.0 instead of CHF values

#### Pattern B: Reimbursement rate formula mismatch

The system and ground truth apply the reimbursement percentage and deductible in different orders:
- System formula: `covered_amount × coverage_percent − deductible`
- GT may use: `(total − deductible) × coverage_percent` or a different base amount
- Age threshold reductions (claim 65027: 60% → 40% because vehicle >8 years) may be incorrectly applied

#### Pattern C: Component classification errors

High-value parts excluded by the system but covered in GT:
- "Couvercle" (cover, CHF 664) — too vague for LLM to match
- "MULTIFUNKTIONSEINHEIT" (multifunction unit, CHF 3,577) — not in component list
- "Courroie crantée/chaîne de distribution" (timing belt/chain) — explicitly excluded but GT includes
- "AUFNAHME" (mirror assembly, CHF 1,145) — not in comfort_options list

#### Pattern D: Null coverage_percent

When the system cannot determine the coverage percentage from the policy, it defaults to null, causing either 0% coverage (massive underpayment in 65150) or no reduction (overpayment in 65056).

#### Pattern E: Goodwill payments

Claim 65047 is a "geste commercial" (goodwill gesture) of CHF 692.05 — a flat payment with no standard coverage calculation. The system has no goodwill pathway.

#### Pattern F: Labor extraction (AW vs CHF)

Claim 64984 shows labor items at CHF 1.0 each — these are Arbeitswerte (work units), not monetary values. The extraction pipeline failed to convert them.

---

## Part 3: Priority Fixes

| Priority | Issue | Claims Affected | Financial Impact |
|----------|-------|-----------------|------------------|
| **P0** | Cross-category EGR→brakes match | 65276, 65288 | CHF 1,891 false payouts |
| **P1** | Diagnostic labor coverage rules | 64354, 64380, 64535, 64836, 65040, 65280, 64984 | Systematic underpayment |
| **P1** | Reimbursement formula order (rate vs deductible) | 64358, 64659, 64818, 64978, 65027 | Variable |
| **P1** | Null coverage_percent handling | 65056, 65150 | Severe over/underpayment |
| **P2** | Gasket/seal synonym matching | 65060 (masked by deductible) | Future false approve risk |
| **P2** | Labor extraction (AW vs CHF) | 64984 | -62% underpayment |
| **P2** | Primary_repair vs line-item contradiction | 65268 | Misleading rationale |
| **P3** | Goodwill payment pathway | 65047 | -11% mismatch |
| **P3** | Administrative policy invalidation | 64980 | Right outcome, wrong reason |
