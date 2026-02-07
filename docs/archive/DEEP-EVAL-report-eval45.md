# Deep Eval Report — Eval #45

**Eval run**: `eval_20260202_174142`
**Claim run**: `clm_20260202_162223_5ca0bf`
**Date**: 2026-02-02
**Decision accuracy**: 98% (49/50 correct)
**Amount accuracy (±5%)**: 28% (7/25 approved within tolerance)
**Previous deep eval**: #40 (96% accuracy, same 28% amount accuracy)

## Summary

| Metric | Eval #45 | Eval #40 | Delta |
|--------|----------|----------|-------|
| Decisions correct | 49/50 (98%) | 48/50 (96%) | +2% |
| Denied correctly | 24/25 | 23/25 | +1 |
| Approved correctly | 25/25 | 25/25 | = |
| False approves | 1 (65288) | 2 (65276, 65288) | -1 |
| False rejects | 0 | 0 | = |
| Amount within 5% | 7/25 | 7/25 | = |
| Amount mismatch (>5%) | 18/25 | 18/25 | = |

### Key Changes Since Eval #40

1. **P0 EGR→brakes fix partially works**: Claim 65276 now correctly REJECTED (was false approve). Claim 65288 still false approves via a new match path (`"asr"` instead of `"bremskraftbegrenzer"`).
2. **P1 diagnostic labor patterns working**: All 7 new French/German non-covered labor patterns fire correctly across 8 claims (64354, 64380, 64535, 64818, 64836, 64984, 65040, 65280).
3. **P1 null coverage_percent partially fixed**: Coverage layer correctly sets `covered_amount=0` and flags `coverage_percent_missing=true`, but the screener/assessment still pays out at implied rates for claims 65056 and 65150.
4. **Amount mismatches unchanged**: The 18 amount mismatches are caused by assessment-stage formula errors and labor classification issues, not coverage analysis bugs.

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
| 65276 | VW T6 | EGR component_not_in_list | Vanne EGR nicht versichert | **Exact** ★ FIXED |
| **65288** | **VW California** | **APPROVE (false!)** | **Module EGR nicht versichert** | **NO — FALSE APPROVE** |
| 65306 | VW T6 KOMBI | Radiateur not covered | Refroidisseur EGR | **Good** |
| 65307 | VW Golf Club Sport | Mileage exceeded + component fail | Garantie échue (km exceeded) | **Exact** |
| 65319 | Cupra Leon | No covered items | Seuil nicht versichert | **Good** |

**Match quality**: Exact=10, Good=8, Partial=4, No=2, False approve=1

### 1.2 Improvement: Claim 65276 (EGR now correctly REJECTED)

In eval #40, "REMPL. EGR" cross-category matched to brakes via `"egr" in "bremskraftbegrenzer"`. The ≤3-char synonym guard now blocks this:

```
Previous: egr_valve → synonyms ["egr"...] → "egr" in "bremskraftbegrenzer" → COVERED (brakes) ✗
Current:  egr_valve → synonyms ["egr"...] → len("egr")≤3 → exact match only → not "bremskraftbegrenzer" → NOT_COVERED ✓
```

### 1.3 Remaining Bug: Claim 65288 (FALSE APPROVE — CHF 1,561)

The EGR fix blocked the `"egr"` → `"bremskraftbegrenzer"` path, but claim 65288 found a **new cross-category match path** via `"asr"`:

```json
"match_reasoning": "Part keyword:egr identified as 'egr_valve' in category 'engine'
  (lookup: assumptions_keyword). Cross-category match: component not in 'engine' list
  but found in 'brakes' (Component 'egr_valve' found in policy list as 'asr')"
```

**Match path**:
1. "Module EGR" → keyword `egr` → `egr_valve` in `engine` category
2. `egr_valve` NOT in engine policy list → cross-category search triggers
3. Searches brakes policy list, which contains `"asr"` (Anti-Schlupf-Regelung / traction control)
4. EGR synonym `"abgasrückführung"` normalizes to `"abgasrueckfuehrung"`
5. **Reverse substring**: `"asr" in "abgasrueckfuehrung"` → TRUE (position 4: abga**sr**...)
6. EGR marked COVERED in brakes → false approve

**Why 65276 was fixed but 65288 was not**: Both claims use keyword `"egr"` for lookup. Claim 65276's fix works because `"egr"` (synonym, 3 chars) is now exact-match-only. But in 65288, the match comes from the reverse direction: `"asr"` (policy term, 3 chars) is checked as a substring inside `"abgasrueckfuehrung"` (synonym, 19 chars). The guard only protects `term_norm ≤ 3 chars`, not `policy_norm ≤ 3 chars`.

**Required fix**: Add symmetric guard — when `policy_norm` is also ≤3 chars, require exact match:
```python
if len(policy_norm) <= 3:
    if policy_norm == term_norm:
        return True, ...
    continue
```

**Financial impact**: CHF 1,560.67 false payout.

### 1.4 Claims with Mismatched Reasons

| Claim | System Reason | GT Reason | Severity |
|-------|---------------|-----------|----------|
| 64980 | Zero payout < deductible | Police nicht valide | Medium — system can't check admin policy status |
| 65052 | Service compliance (1878 days) | Distribution damage | Low — both valid, system found service gap first |
| 65060 | Zero payout < deductible | Joints not covered | Low — joints correctly excluded, payout safety net worked |
| 65268 | Zero payout < deductible | Valve cover not covered | Low — exclusion pattern correct, primary_repair contradicts |

---

## Part 2: Approved Claims — Payment Comparison

### 2.1 Within 5% Tolerance (7 claims)

| Claim | Vehicle | GT Amount | System Amount | Diff % |
|-------|---------|-----------|---------------|--------|
| 64166 | Ford FOCUS | 1,506.52 | 1,506.54 | +0.001% |
| 64288 | Land Rover RR Velar | 4,141.02 | 4,086.18 | -1.3% |
| 64380 | BMW M3 | 1,171.16 | 1,167.00 | -0.4% |
| 64393 | Alfa Romeo Stelvio | 2,829.75 | 2,835.50 | +0.2% |
| 64850 | Mercedes SL 500 | 3,914.28 | 3,806.70 | -2.7% |
| 64959 | Ford MUSTANG | 1,480.43 | 1,439.44 | -2.8% |
| 65027 | BMW Alpina B3 | 672.53 | 672.50 | -0.004% |

Notable improvements vs eval #40:
- **64380**: Now within tolerance (was +22% in eval #40) — diagnostic labor fix working
- **65027**: Now exact match (was -11% in eval #40)

### 2.2 Amount Mismatches >5% (18 claims)

| Claim | Vehicle | GT | System | Diff % | Root Cause |
|-------|---------|-----|--------|--------|------------|
| 64978 | Mitsubishi ASX | 25 | 319 | +1176% | Assessment ignores coverage% |
| 64792 | Peugeot 3008 | 521 | 1,946 | +274% | Labor over-inclusion + formula error |
| 64297 | Subaru Impreza | 74 | 164 | +122% | Assessment applies 40% after deductible |
| 64535 | LR Evoque | 914 | 1,189 | +30% | VAT not deducted (corporate) + labor |
| 64168 | Land Rover RR | 334 | 424 | +27% | Assessment applies 40% after deductible |
| 64818 | Jeep Compass | 257 | 317 | +23% | Assessment applies 60% after deductible |
| 64386 | Jeep Grand Cherokee | 2,429 | 2,704 | +11% | Extra transmission labor covered |
| 65056 | Audi A4 TDI | 3,600 | 3,892 | +8% | Null coverage% + max cap handling |
| 65280 | VW Golf GTI | 563 | 412 | -27% | Fasteners + brake labor excluded |
| 64358 | VW Golf GTi | 439 | 321 | -27% | Formula error + labor excluded |
| 64659 | Mercedes CLA45 | 2,397 | 1,557 | -35% | Max cap applied before rate |
| 65047 | VW T-Roc | 692 | 427 | -38% | Goodwill (non-formulaic GT decision) |
| 64836 | Rolls Royce Phantom | 2,995 | 1,793 | -40% | Generic "Arbeit" labor excluded |
| 65055 | Ford Fiesta | 910 | 455 | -50% | Timing belt + MECANICIEN excluded |
| 64984 | Mercedes G 500 | 958 | 367 | -62% | All labor excluded (should be covered) |
| 64354 | VW Golf eTSI | 940 | 253 | -73% | Generic labor + material excluded |
| 65150 | Audi A8 | 1,841 | 442 | -76% | Mirror assembly + null coverage% |
| 65040 | Bentley Flying Spur | 1,522 | 282 | -81% | Trunk ECU excluded (should be covered) |

### 2.3 Root Cause Patterns

| Pattern | Count | Claims | Avg Impact | Direction |
|---------|-------|--------|------------|-----------|
| **A. Payout formula error** (coverage% at wrong stage) | 6 | 64168, 64297, 64659, 64792, 64818, 64978 | Variable | Over-pays |
| **B. Labor over-exclusion** (necessary repair labor) | 6 | 64354, 64358, 64836, 64984, 65055, 65280 | ~CHF 780 | Under-pays |
| **C. Parts classification error** (covered parts excluded) | 3 | 65040, 65055, 65150 | ~CHF 1,090 | Under-pays |
| **D. Null coverage_percent** | 2 | 65056, 65150 | Severe | Both |
| **E. Labor over-inclusion** | 3 | 64386, 64535, 64792 | ~CHF 633 | Over-pays |
| **F. VAT handling** (corporate policyholder) | 1 | 64535 | ~CHF 275 | Over-pays |
| **G. Goodwill** (non-formulaic GT decision) | 1 | 65047 | ~CHF 266 | N/A |

#### Pattern A: Payout Formula Error (P1 — 6 claims)

The assessment LLM stage applies the reimbursement rate (40%/60%) **after** the deductible instead of before. The coverage_analysis stage correctly computes `total_covered_before_excess` (rate-adjusted) and `total_payable`, but the assessment stage ignores these and recomputes incorrectly.

Example (64978 Mitsubishi ASX):
- Coverage analysis: gross=433.69, at 40%=173.48, -excess=23.48 ✓
- Assessment: gross=433.69, -deductible=283.69, ×40%=... → 318.82 ✗
- GT: 24.98

**This is the #1 systemic issue** — it affects 6 claims and produces extreme mismatches (up to +1176%).

#### Pattern B: Labor Over-Exclusion (P1 — 6 claims)

Generic descriptions ("Arbeit", "MATERIAL", "INSTANDSETZUNG VERSCHIEDENES") auto-excluded even when clearly part of a covered repair. Ancillary labor (heat shield removal, wheel removal, soundproofing) excluded as unrelated when GT considers it necessary access work.

This was partially addressed by the diagnostic labor patterns (P1 labor fix from eval #40), which correctly excluded investigative labor. But the over-exclusion of **covered** labor remains.

#### Pattern C: Parts Classification Error (P1 — 3 claims)

| Claim | Part | Category | System | GT | Impact |
|-------|------|----------|--------|-----|--------|
| 65040 | CALCULATEUR DE COFFRE (trunk ECU) | electronics | component_not_in_list | Covered | CHF 1,165 |
| 65055 | Timing belt/chain | engine | component_not_in_list | Covered | CHF 342 |
| 65150 | AUFNAHME (mirror assembly) | comfort_options | component_not_in_list | Covered | CHF 1,145 |

These are customer config fixes — add to assumptions.json or keyword mappings.

#### Pattern D: Null Coverage Percent (P1 — 2 claims)

- **65056**: coverage_percent=null → coverage analysis sets covered_amount=0 → assessment falls back to max_cap logic → overpays
- **65150**: coverage_percent=null → coverage analysis sets covered_amount=0 → assessment pays reduced → underpays

The coverage_percent_missing flag is now set correctly, but the assessment stage doesn't honor it.

---

## Part 3: Comparison vs Eval #40

### What Improved

| Issue from #40 | Status in #45 | Details |
|----------------|---------------|---------|
| P0: EGR→brakes via "egr"/"bremskraftbegrenzer" | **FIXED** for 65276 | Synonym ≤3 char guard blocks this path |
| P1: Diagnostic labor patterns (FR/DE) | **FIXED** for all 8 claims | New patterns: RECHERCHE.*DÉRANGEMENT, STÖRUNGSSUCHE, etc. |
| P1: Null coverage% default to 100% | **PARTIALLY FIXED** | Coverage layer correct; assessment still bypasses |
| False approve count | **1 → from 2** | 65276 now correctly REJECTED |

### What Didn't Improve

| Issue | Status | Details |
|-------|--------|---------|
| P0: EGR→brakes via "asr" reverse substring | **NOT FIXED** | 65288 still false approve via `"asr" in "abgasrueckfuehrung"` |
| Amount mismatches | **UNCHANGED** (18/25) | Assessment formula errors are the main blocker |
| Payout formula error | **NOT ADDRESSED** | Assessment stage applies % at wrong point |
| Parts classification | **NOT ADDRESSED** | Trunk ECU, timing belt, mirror assembly still excluded |

### What Regressed

Nothing regressed — all previously correct decisions remain correct.

---

## Part 4: Priority Fixes

| Priority | Issue | Claims | Financial Impact | Fix Location |
|----------|-------|--------|------------------|--------------|
| **P0** | Symmetric short-term guard for `policy_norm ≤ 3 chars` | 65288 | CHF 1,561 false payout | `analyzer.py` ~L750 |
| **P1** | Assessment payout formula (% applied at wrong stage) | 64168, 64297, 64659, 64792, 64818, 64978 | ~CHF 4,700 total mismatch | Assessment stage / screener |
| **P1** | Labor over-exclusion (generic Arbeit, access labor) | 64354, 64358, 64836, 64984, 65055, 65280 | ~CHF 4,690 under-payment | Rule engine + labor matching |
| **P1** | Parts classification (trunk ECU, timing belt, mirror) | 65040, 65055, 65150 | ~CHF 3,270 under-payment | Customer config (assumptions.json) |
| **P2** | Assessment should use coverage_analysis.total_payable | All approved | Eliminates formula errors | Assessment stage |
| **P2** | Honor coverage_percent_missing flag in screener | 65056, 65150 | ~CHF 1,691 mismatch | Screener payout logic |
| **P2** | VAT deduction for corporate policyholders | 64535 | CHF 275 over-payment | Policyholder type detection |
| **P3** | Primary_repair contradicting line-item reality | 65268 | Misleading rationale | Primary repair selection |
| **P3** | Goodwill payment pathway | 65047 | CHF 266 mismatch | Unfixable by formula |
| **P3** | Policy admin status checking (beyond date range) | 64980 | Right outcome, wrong reason | New data source needed |

### Recommended Fix Order

1. **P0: Symmetric guard** — 1-line fix in `_is_component_in_policy_list()`, eliminates the last false approve
2. **P1: Assessment formula** — Make assessment use `coverage_analysis.total_payable` + VAT instead of recomputing. This single change would fix 6 of 18 amount mismatches.
3. **P1: Customer config** — Add trunk ECU, timing belt, mirror assembly to assumptions.json. Fixes 3 claims.
4. **P1: Labor linking** — Improve context-aware labor coverage: if main repair is covered, related access labor should be too.
