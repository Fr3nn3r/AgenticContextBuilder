# Deep Eval Report — Eval #46

**Eval run**: `eval_20260202_194916`
**Claim run**: `clm_20260202_181533_413645`
**Date**: 2026-02-02
**Decision accuracy**: 98% (49/50 correct)
**Amount accuracy (+/-5%)**: 28% (7/25 approved within tolerance)
**Previous deep eval**: #45 (98% accuracy, 28% amount accuracy)

## Summary

| Metric | Eval #46 | Eval #45 | Delta |
|--------|----------|----------|-------|
| Decisions correct | 49/50 (98%) | 49/50 (98%) | = |
| Denied correctly | 24/25 | 24/25 | = |
| Approved correctly | 25/25 | 25/25 | = |
| False approves | 1 (65288) | 1 (65288) | = |
| False rejects | 0 | 0 | = |
| Amount within 5% | 7/25 | 7/25 | = |
| Amount mismatch (>5%) | 18/25 | 18/25 | = |

### Key Findings

1. **Stable at 98% decision accuracy** — identical to eval #45. Same false approve (65288, EGR→ASR cross-category match). No regressions.
2. **Root cause of amount mismatches identified**: The payout formula in the screener applies the coverage rate AFTER the deductible, while the ground truth (NSA decision letters) applies the rate BEFORE the deductible. This single formula error affects all 8 claims with degraded coverage rates (40%/60%), causing systematic overpayment.
3. **Coverage classification errors** cause 6 claims to have wrong covered amounts, independent of the formula issue.
4. **1 goodwill case** (65047) is inherently unmatchable by any formula.
5. **3 claims** have minor deductible/covered-amount discrepancies at 100% coverage that do not stem from the formula bug.

---

## Part 1: Denied Claims — Explanation Comparison

### 1.1 Summary Table (25 GT-denied claims)

| Claim | Vehicle | System Reason | GT Denial Reason | Reason Match |
|-------|---------|---------------|------------------|--------------|
| 64951 | Mercedes GLC 400d | LEUCHTEINHEIT not covered | Scheinwerfer nicht versichert | **Exact** |
| 64961 | BMW 218 Grand Tourer | No covered items (6 not covered) | Querlenker nicht versichert | **Good** |
| 64980 | VW Tiguan | Zero payout < deductible | Police nicht valide | **No** (different reason) |
| 64986 | Hyundai TUCSON | PM-Sensor not covered | Partikelfilter Sensor | **Exact** |
| 65002 | Mercedes ML 350 | No covered items (10 not covered) | NOx Sensoren, Kabelbaum, ECU | **Good** |
| 65021 | Porsche Cayenne | HEIZUNGSVENTIL not covered | Heizungsventil, Kühlsystem | **Exact** |
| 65029 | Audi A6 | AdBlue valve/clamp not covered | AdBlue-System, Einspritzdüse | **Exact** |
| 65052 | Peugeot Rifter | Service compliance fail (1878 days) | Distribution damage nicht versichert | **Partial** |
| 65054 | VW Touareg | No covered items | Software Updates | **Good** |
| 65060 | Citroen C4 | Zero payout < deductible | Joints (vilebrequin, carter, soupapes) | **Partial** |
| 65113 | BMW X3 | Injektor not covered | Hochdruckpumpe + Folgeschäden | **Partial** |
| 65129 | Seat Leon | Zahnriemen not covered | Zahnriemen nicht abgedeckt | **Exact** |
| 65160 | Mini Clubman | No covered items | Support filtre à huile | **Good** |
| 65174 | Audi RSq8 | No covered items | Software Updates | **Good** |
| 65183 | VW Golf Alltrack | No covered items | Lenkrad nicht abgedeckt | **Good** |
| 65190 | Renault Scenic | Wasserpumpe not covered | Wasserpumpe nicht abgedeckt | **Exact** |
| 65208 | Mini COOPER S | Labor not covered | Couvre culasse nicht versichert | **Good** |
| 65211 | VW Golf GTI | Gaine Etancheite not covered | Gaines d'étanchéité | **Exact** |
| 65215 | Peugeot 3008 | Mileage + component fail | Harnstofftank, AdBlue-System | **Exact** |
| 65268 | Peugeot 308 | Zero payout < deductible | Couvercle de soupape | **Partial** |
| 65276 | VW T6 | EGR component_not_in_list | Vanne EGR nicht versichert | **Exact** |
| **65288** | **VW California** | **APPROVE (false!)** | **Module EGR nicht versichert** | **NO — FALSE APPROVE** |
| 65306 | VW T6 KOMBI | Radiateur not covered | Refroidisseur EGR | **Good** |
| 65307 | VW Golf Club Sport | Mileage exceeded + component fail | Garantie échue (km exceeded) | **Exact** |
| 65319 | Cupra Leon | No covered items | Seuil nicht versichert | **Good** |

**Match quality**: Exact=10, Good=8, Partial=4, No=1 (different reason), False approve=1

### 1.2 Remaining Bug: Claim 65288 (FALSE APPROVE — CHF 1,606)

Same bug as eval #45. The EGR fix blocked `"egr"` → `"bremskraftbegrenzer"` path (fixing 65276), but 65288 finds a **different cross-category match** via `"asr"`:

```
Match path:
1. "Module EGR" → keyword "egr" → egr_valve in "engine" category
2. egr_valve NOT in engine policy list → cross-category search triggers
3. Searches "brakes" policy list, finds "asr" (Anti-Schlupf-Regelung)
4. EGR synonym "abgasrückführung" normalizes to "abgasrueckfuehrung"
5. Reverse substring: "asr" in "abgasrueckfuehrung" → TRUE (position 4)
6. EGR marked COVERED in brakes → false approve
```

**Required fix**: Symmetric guard — when `policy_norm` is also ≤3 chars, require exact match. 1-line fix in `_is_component_in_policy_list()`.

### 1.3 Claims with Mismatched Reasons

| Claim | System Reason | GT Reason | Severity |
|-------|---------------|-----------|----------|
| 64980 | Zero payout < deductible | Police nicht valide | Medium — system can't check admin policy status |
| 65052 | Service compliance (1878 days) | Distribution damage | Low — both valid, system found service gap first |
| 65060 | Zero payout < deductible | Joints not covered | Low — joints correctly excluded, payout safety net worked |
| 65268 | Zero payout < deductible | Valve cover not covered | Low — exclusion pattern correct, zero-payout caught it |

Note: Claim 65268 has a latent `repair_context` bug — `primary_repair.is_covered = true` despite all items being excluded by pattern. The zero-payout override prevents a wrong outcome, but this is a risk if exclusion patterns miss a future claim.

---

## Part 2: Approved Claims — Payment Comparison

### 2.1 Master Table (18 amount mismatch claims)

| Claim | Vehicle | GT Amount | Pred Amount | Diff % | Reimb Rate | Root Cause |
|-------|---------|-----------|-------------|--------|------------|------------|
| 64978 | Mitsubishi ASX | 24.98 | 114.99 | +360% | 40% | Formula: rate after deductible |
| 64792 | Peugeot 3008 | 520.68 | 1,945.80 | +274% | 40% | Formula + overcoverage (labor) + max cap |
| 64297 | Subaru Impreza | 74.00 | 163.98 | +122% | 40% | Formula: rate after deductible |
| 65040 | Bentley Flying Spur | 1,522.03 | 282.00 | -81% | 100% | Coverage: excluded CALCULATEUR DE COFFRE |
| 64354 | VW Golf eTSI | 939.98 | 322.00 | -66% | 100% | Coverage: excluded labor items |
| 64984 | Mercedes G 500 | 958.25 | 366.72 | -62% | 100% | Coverage: excluded labor items |
| 65047 | VW T-Roc | 692.05 | 426.55 | -38% | 100% | Goodwill: "geste commercial" |
| 64659 | Mercedes CLA45 | 2,397.38 | 1,556.64 | -35% | 40% | Formula + coverage underpay + max cap |
| 64535 | Land Rover Evoque | 914.20 | 1,189.08 | +30% | 100% | Coverage: overcovered labor (diagnostic) |
| 64358 | VW Golf GTI | 439.27 | 320.86 | -27% | 60% | Formula + coverage underpay |
| 65280 | VW Golf TSI | 562.75 | 412.23 | -27% | 100% | Coverage: excluded parts (fasteners, disc) |
| 64168 | Land Rover RR | 333.69 | 423.68 | +27% | 40% | Formula: rate after deductible |
| 65055 | Ford Fiesta | 910.15 | 1,123.59 | +23% | 40% | Formula: rate after deductible |
| 64818 | Jeep Compass | 256.95 | 316.94 | +23% | 60% | Formula: rate after deductible |
| 65150 | Audi A8 TFSI e | 1,841.25 | 2,053.79 | +12% | 100% | Covered amount diff + deductible diff |
| 64386 | Jeep Grand Cherokee | 2,429.46 | 2,703.84 | +11% | 100% | Covered amount diff + deductible diff |
| 65056 | Audi A4 TDI | 3,600.00 | 3,891.60 | +8% | 100% | Deductible diff + max cap handling |
| 64836 | Rolls Royce Phantom | 2,995.41 | 3,169.61 | +6% | 100% | Covered amount diff + deductible diff |

### 2.2 The Payout Formula Bug (P0 — 8 claims, CHF 2,072 total overpay)

**The single highest-impact issue.** The screener payout formula (`_calculate_payout` in `screener.py`) applies the coverage rate in the wrong position.

**System formula** (lines 1084-1089 of screener.py):
```
1. gross = total_covered_gross (covered items at full price)
2. Cap at max_coverage if exceeded
3. subtotal = capped + (capped * 8.1% VAT)
4. deductible = max(subtotal * excess_pct, excess_minimum)
5. after_deductible = subtotal - deductible
6. final_payout = after_deductible * coverage_percent    <-- RATE APPLIED LAST
```

**GT formula** (derived from NSA decision letters):
```
1. gross = total_covered_gross (covered items at full price)
2. Cap at max_coverage if exceeded
3. rate_adjusted = capped * coverage_percent               <-- RATE APPLIED FIRST
4. subtotal = rate_adjusted + (rate_adjusted * 8.1% VAT)
5. deductible = max(subtotal * excess_pct, excess_minimum)
6. final_payout = subtotal - deductible
```

**Proof by example (claim 64168, 40% rate):**

| Step | System | GT | Notes |
|------|--------|----|-------|
| Gross covered | 1,118.60 | 1,118.60 | Same base |
| Apply rate | -- | 447.44 (=1118.60*40%) | GT applies rate first |
| Add VAT (8.1%) | 1,209.21 (=1118.60*1.081) | 483.69 (=447.44*1.081) | System adds VAT to gross |
| Deductible | 150.00 | 150.00 | Same (min 150) |
| After deductible | 1,059.21 | 333.69 | |
| Apply rate | 423.68 (=1059.21*40%) | -- | System applies rate last |
| **Final payout** | **423.68** | **333.69** | **+27% overpay** |

**Impact across all 8 claims with degraded rates:**

| Claim | Rate | System | GT | Abs Diff | Direction |
|-------|------|--------|----|---------|----|
| 64978 | 40% | 114.99 | 24.98 | 90.01 | Overpay |
| 64297 | 40% | 163.98 | 74.00 | 89.98 | Overpay |
| 64168 | 40% | 423.68 | 333.69 | 89.99 | Overpay |
| 64818 | 60% | 316.94 | 256.95 | 59.99 | Overpay |
| 65055 | 40% | 1,123.59 | 910.15 | 213.44 | Overpay |
| 64792 | 40% | 1,945.80 | 520.68 | 1,425.12 | Overpay (+ coverage issue) |
| 64659 | 40% | 1,556.64 | 2,397.38 | 840.74 | Underpay (coverage undercount) |
| 64358 | 60% | 320.86 | 439.27 | 118.41 | Underpay (coverage undercount) |

Note: Claims 64792, 64659, and 64358 have BOTH the formula bug AND coverage classification errors, so the formula fix alone will not resolve them fully.

**Fix**: In `_calculate_payout` (screener.py line 1129-1131), apply `coverage_percent` to `capped_amount` BEFORE adding VAT and computing deductible.

### 2.3 Coverage Classification Errors (P1 — 6 claims, CHF 3,620 total impact)

These claims have wrong covered amounts due to the coverage analysis including or excluding items differently from the GT.

#### 2.3.1 Under-coverage (system excluded items GT covers)

**Claim 65040** (Bentley Flying Spur, -81%, CHF -1,240.03):
- System covered: 399.63 (labor only)
- GT covered: 1,564.43 (parts 1,164.80 + labor 399.63)
- Root cause: The main part **CALCULATEUR DE COFFRE** (trunk control unit, CHF 1,164.80) was excluded as `component_not_in_list` for electrical_system. The GT covers it as an electrical component.
- Fix: Add "calculateur" / "steuergeraet" to electrical_system covered components, or improve LLM matching for control units.

**Claim 64354** (VW Golf eTSI, -66%, CHF -617.98):
- System covered: 436.63 (parts only)
- GT covered: 1,008.33 (parts 391.30 + labor 617.03)
- Root cause: System excluded labor items (Hitzeschutz aus+einbauen, Getriebegehause, etc.) totaling ~617 CHF. GT covered labor for all covered repair work.
- GT coverage notes: "ANTENNE - NICHT VERSICHERT. SOFTWAREUPDATE - NICHT VERSICHERT." — only antenna and software update excluded.
- Fix: Labor for covered repairs should be included. The labor exclusion patterns may be over-aggressive.

**Claim 64984** (Mercedes G 500, -62%, CHF -591.53):
- System covered: 478.00 (coolant pump part + minimal)
- GT covered: 1,025.20 (parts 475.00 + labor 550.20)
- Root cause: System excluded significant labor (550 CHF) associated with covered repair work.
- Fix: Same as 64354 — labor for covered repairs should be included.

**Claim 65280** (VW Golf TSI, -27%, CHF -150.52):
- System covered: 520.10 (brake caliper + labor)
- GT covered: 659.35 (parts 398.95 + labor 260.40)
- Root cause: System excluded fasteners (SCHRAUBE, MUTTER) and likely some brake disc labor. GT coverage notes: "Diagnose und Prufarbeiten sind nicht uber die Garantie versichert."
- Fix: Fasteners associated with covered repairs should be included as incidental parts.

**Claim 64659** (Mercedes CLA45, -35%, CHF -840.74):
- System coverage_analysis covered gross: 4,660.20 (mostly differential + labor)
- GT covered: 2,464.18 (parts 1,864.90 + labor 599.28)
- Root cause: System covered 4,660.20 gross while GT only 2,464.18. Plus the formula bug (40% rate applied after deductible). System also applied max_coverage cap of 4,000. Multiple interacting issues.
- Fix: Review item-level coverage for this claim; formula fix will also improve this.

#### 2.3.2 Over-coverage (system included items GT excludes)

**Claim 64535** (Land Rover Evoque, +30%, CHF +274.88):
- System covered: 1,238.74 (including 562.50 diagnostic labor)
- GT covered: 1,064.20 (parts 664.20 + labor 400.00)
- Root cause: System included 562.50 CHF diagnostic labor ("Diagnostic: Essai sur route > plainte du client confirmee...") that GT excluded. The GT only covered the replacement labor (400 CHF), not the diagnostic work.
- GT coverage notes mention VAT deduction of CHF 86.20 not reimbursable.
- Fix: Diagnostic labor detection should exclude this item.

**Claim 64792** (Peugeot 3008, +274%, CHF +1,425.12):
- System covered gross: 7,057.99 (massive labor + all pistons)
- GT covered: 620.43 (parts 49.65 + labor 570.78)
- Root cause: System covered all piston sets and associated labor (5,719 CHF labor), while GT only approved 620.43 total. The GT note says "DICHTUNG ZYLINDERBLOCKSTOPFEN nicht bewilligt (0.00 CHF)" and "Materialkosten wie folgt erstattet: ab 110.000 Km zu 40%". The GT severely limited what was covered.
- Fix: This claim needs manual review of which specific items GT covered. The system massively over-included items.

### 2.4 Goodwill / Special Case (P3 — 1 claim)

**Claim 65047** (VW T-Roc, -38%, CHF -265.50):
- System: Normal calculation yields 426.55 (covered=533.35, deductible=150)
- GT: 692.05 — a "geste commercial" (goodwill payment) with parts=0, labor=0, total_ml=0
- The GT explicitly states: "5Q1953521KSIGI CONTACTEUR - sur la base de la bonne volonte. Geste commercial de 692,05 CHF."
- This is a manual goodwill payment that cannot be computed by any formula. The system correctly computed the standard payout; the GT reflects a discretionary business decision.
- **No fix needed** — this is an inherent limitation. Consider excluding goodwill claims from amount accuracy metrics.

### 2.5 Minor Discrepancies at 100% Coverage (P2 — 3 claims)

These claims have 100% coverage (no rate degradation) but still show >5% mismatch due to covered-amount or deductible differences.

**Claim 65150** (Audi A8, +12%, CHF +212.54):
- System: covered=2,111.00, deductible=228.20, final=2,053.79
- GT: covered=1,892.55, deductible=204.60, final=1,841.25
- Difference: System covered 218.45 more than GT, and higher deductible (228.20 vs 204.60).
- Root cause: System included items GT excluded. Deductible difference follows from different covered base (10% of different subtotals).

**Claim 64386** (Jeep Grand Cherokee, +11%, CHF +274.38):
- System: covered=2,779.16, deductible=300.43, final=2,703.84
- GT: covered=2,497.16, deductible=269.95, final=2,429.46
- Difference: System covered 282.00 more than GT. GT notes: "DISPOSITIF DE COM - non assure."
- Root cause: System likely included the "dispositif de communication" item that GT excluded.

**Claim 65056** (Audi A4, +8.1%, CHF +291.60):
- System: covered=6,238.55, max_cap=4,000, deductible=432.40, final=3,891.60
- GT: covered=3,700.30, deductible=400, final=3,600.00
- Difference: System covered 6,238.55 (capped to 4,000) while GT covered 3,700.30. Different deductibles (432.40 vs 400).
- Root cause: System over-included items beyond what GT approved, but max cap limited the damage. GT note: "Die Kostengutsprache erfolgt mit der maximalen Deckung gemass Police."

**Claim 64836** (Rolls Royce Phantom, +5.8%, CHF +174.20):
- System: covered=3,257.90, deductible=352.18, final=3,169.61
- GT: covered=3,078.81, deductible=332.80, final=2,995.41
- Difference: System covered 179.09 more than GT. Different deductibles follow from covered base difference.
- Root cause: System included items GT excluded (small amount, ~179 CHF of additional parts/labor).

---

## Part 3: Pattern Summary and Financial Impact

### 3.1 Categorized Root Causes

| Pattern | Claims | Count | Total Abs Impact (CHF) | Direction |
|---------|--------|-------|------------------------|-----------|
| **P0: Formula — rate after deductible** | 64168, 64297, 64818, 64978, 65055 | 5 (pure) | 543.41 | All overpay |
| **P0: Formula + coverage mix** | 64358, 64659, 64792 | 3 | 2,384.27 | Mixed |
| **P1: Coverage under-inclusion** | 64354, 64984, 65040, 65280 | 4 | 2,600.06 | All underpay |
| **P1: Coverage over-inclusion** | 64535 | 1 | 274.88 | Overpay |
| **P2: Minor covered-amount diff** | 64386, 64836, 65056, 65150 | 4 | 952.72 | All overpay |
| **P3: Goodwill (not fixable)** | 65047 | 1 | 265.50 | Underpay |
| **Total** | | **18** | **7,020.84** | |

### 3.2 Financial Impact by Direction

| Direction | Claims | Total Impact (CHF) |
|-----------|--------|-------------------|
| System overpays vs GT | 11 | 3,792.65 |
| System underpays vs GT | 7 | 3,228.19 |
| **Net overpay** | | **+564.46** |

### 3.3 If Only Formula Were Fixed (P0)

Fixing the formula (rate before deductible) would resolve 5 claims fully and partially fix 3 more. Estimated impact:

| Claim | Current Diff | After Fix (est.) | Remaining |
|-------|-------------|------------------|-----------|
| 64168 | +89.99 | ~0 | Resolved |
| 64297 | +89.98 | ~0 | Resolved |
| 64818 | +59.99 | ~0 | Resolved |
| 64978 | +90.01 | ~0 | Resolved |
| 65055 | +213.44 | ~0 | Resolved |
| 64358 | -118.41 | Reduced | Coverage still off |
| 64659 | -840.74 | Reduced | Coverage + max cap still off |
| 64792 | +1,425.12 | Reduced | Coverage still off |

**Projected claims resolved**: 5 fully resolved, 3 improved
**Projected amount accuracy**: 12/25 within tolerance (up from 7/25)

---

## Part 4: Priority Fixes

### P0: Symmetric short-term guard for cross-category matching (CHF 1,606 false payout, 1 claim)

**File**: `analyzer.py`, `_is_component_in_policy_list()` (or equivalent)
**Claim**: 65288 (false approve)

When `policy_norm` is ≤3 chars (e.g., `"asr"`), require exact match instead of substring. Currently the guard only protects `term_norm ≤ 3 chars`, not `policy_norm ≤ 3 chars`. Add symmetric guard:
```python
if len(policy_norm) <= 3:
    if policy_norm == term_norm:
        return True, ...
    continue
```

### P0: Fix payout formula order of operations (CHF 2,927 impact, 8 claims)

**File**: `workspaces/nsa/config/screening/screener.py`, method `_calculate_payout`
**Lines**: 1097-1131

**Current code** (simplified):
```python
gross = summary.total_covered_gross
capped_amount = min(gross, max_coverage) if max_coverage else gross
vat_amount = capped_amount * 0.081
subtotal_with_vat = capped_amount + vat_amount
deductible = max(subtotal_with_vat * excess_pct/100, excess_min)
after_deductible = subtotal_with_vat - deductible
final_payout = after_deductible * (coverage_percent / 100.0)  # WRONG ORDER
```

**Corrected formula**:
```python
gross = summary.total_covered_gross
capped_amount = min(gross, max_coverage) if max_coverage else gross
rate_adjusted = capped_amount * (coverage_percent / 100.0)   # RATE FIRST
vat_amount = rate_adjusted * 0.081
subtotal_with_vat = rate_adjusted + vat_amount
deductible = max(subtotal_with_vat * excess_pct/100, excess_min)
final_payout = subtotal_with_vat - deductible                 # NO RATE AT END
```

**Validation**: Verify against all 8 degraded-rate claims (40%: 64168, 64297, 64792, 64978, 65055; 60%: 64358, 64818; also check 64659).

### P1: Fix labor exclusion for covered repairs (CHF 1,825 impact, 3 claims)

**Claims**: 64354 (-617.98), 64984 (-591.53), 65040 (-1,240.03 partial)

The coverage analysis is over-excluding labor associated with covered repairs. When a part is covered, the labor to install/replace it should also be covered unless explicitly excluded.

**Root cause candidates**:
- Labor items without part_number get matched by keyword/LLM and may miss the association with covered parts
- Diagnostic labor exclusion patterns may be too broad, catching legitimate repair labor

**Suggested approach**:
- Review labor promotion logic: if a labor line references a covered part, it should inherit coverage
- Audit exclusion patterns to ensure they only exclude true diagnostic/search labor, not installation labor

### P1: Add CALCULATEUR DE COFFRE to electrical_system (CHF 1,240 impact, 1 claim)

**Claim**: 65040 — trunk control unit (calculateur de coffre) was classified as `component_not_in_list` for electrical_system.

This is a control unit (ECU/calculator) that should be covered under electrical_system. Similar items like "calculateur moteur" and "steuergeraet" are likely already covered.

**Fix**: Add "calculateur" pattern to electrical_system component mappings in customer config.

### P2: Review covered-amount discrepancies (CHF 953 impact, 4 claims)

**Claims**: 64386, 64836, 65056, 65150

All four have the system covering slightly more items than GT. These are minor overcoverage issues where specific items the GT excluded (e.g., "DISPOSITIF DE COM" in 64386) were included by the system.

**Suggested approach**: Review item-level coverage for these 4 claims and add specific exclusion rules where patterns emerge.

### P3: Exclude goodwill claims from amount metrics (1 claim)

**Claim**: 65047 — "geste commercial" of 692.05 CHF. No formula or classification fix can match a discretionary goodwill payment. Consider flagging GT entries with `total_material_labor_approved=0` and non-null `total_approved_amount` as goodwill cases and excluding from amount accuracy.

---

## Appendix: 7 Claims Within Tolerance

| Claim | Vehicle | GT | Pred | Diff % |
|-------|---------|------|------|--------|
| 64166 | Ford Focus | 1,506.52 | 1,568.33 | +4.1% |
| 64288 | Land Rover Velar | 4,141.02 | 4,044.60 | -2.3% |
| 64380 | BMW M3 | 1,171.16 | 1,166.40 | -0.4% |
| 64393 | Alfa Romeo Stelvio | 2,829.75 | 2,699.86 | -4.6% |
| 64850 | Mercedes SL 500 | 3,914.28 | 3,916.91 | +0.1% |
| 64959 | Ford Mustang | 1,480.43 | 1,497.23 | +1.1% |
| 65027 | BMW Alpina B3 | 672.53 | 672.27 | -0.04% |

These 7 claims demonstrate that the formula and coverage classification work correctly when: (a) the coverage rate is 100% or correctly applied via the 70%/90% brackets, and (b) the coverage analysis matches GT item inclusion.
