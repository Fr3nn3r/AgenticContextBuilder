# Fix: Payout Calculation — Single Source of Truth

**Date:** 2026-02-08
**Severity:** Data correctness bug (CHF 4,086.18 vs 4,131.05 mismatch)

## Root Problem

Payout logic (VAT, deductible, coverage rate, max-coverage cap) was **independently reimplemented in 4 places**, each with slightly different formulas:

| # | Location | What it computed | Formula variant |
|---|----------|-----------------|-----------------|
| 1 | `coverage/analyzer.py` `_calculate_summary()` | `vat_amount`, `excess_amount`, `total_payable` | VAT on covered total, deductible on gross (covered+VAT), no max-coverage cap |
| 2 | `screening/screener.py` `_calculate_payout()` | Full payout | VAT on rate-adjusted amount, max-coverage cap, company VAT removal, deductible on subtotal |
| 3 | `ClaimsWorkbenchPage.tsx` `computePayout()` + `CostBreakdownTab` inline | Banner + cost tab payout | Same as #1 (JS port), no max-coverage cap |
| 4 | `ClaimsWorkbenchPage.tsx` `buildEnrichment()` inline | Claims table payout column | Hybrid — used coverage summary excess but recomputed VAT |

### Why the numbers diverged

The screener (#2) is the authoritative calculation — it matches the customer's actual decision letter formula. It applies:
1. Coverage percent on gross amounts
2. Max-coverage cap (e.g., CHF 15,000)
3. VAT (8.1%) on the rate-adjusted + capped amount
4. Deductible: `MAX(subtotal * excess_percent, excess_minimum)`
5. Company VAT removal for business policyholders

The analyzer (#1) and frontend (#3, #4) used a simpler formula that skipped the max-coverage cap and applied VAT/deductible differently. When policies had max-coverage caps or company VAT adjustments, the numbers diverged.

The specific bug: claim 64288 showed CHF 4,086.18 in the UI (frontend computation) but the correct screener value was CHF 4,131.05. The difference came from the max-coverage cap interaction with VAT ordering.

## What Was Fixed

### Principle applied: Compute once, read everywhere

The screener's `_calculate_payout()` is now the **single source of truth**. All other locations were changed to either not compute payout at all, or to read the screener's output.

### Changes

**Backend — analyzer no longer computes payout:**
- `coverage/analyzer.py` `_calculate_summary()`: Removed `vat_rate` parameter. No longer computes VAT, deductible, or total_payable. Sets `vat_amount=0.0`, `excess_amount=0.0`, `total_payable=total_covered_before_excess`.
- `coverage/schemas.py`: Marked `vat_amount`, `excess_amount`, `total_payable` fields as deprecated (kept at 0.0 for backward compat).
- `api/services/coverage_analysis.py`: Removed `vat_rate` extraction and passing.
- `screening/screener.py`: Removed `vat_rate` from `analyze()` call (screener already uses its own `SWISS_VAT_RATE`).
- `cli.py`: Shows "covered (net)" instead of excess/payable, notes payout is calculated by screener.

**Frontend — displays backend values instead of recomputing:**
- Deleted `computePayout()` function entirely.
- `DecisionBanner`: reads `data.assessment?.payout?.final_payout ?? data.screening?.payout?.final_payout`.
- `CostBreakdownTab`: reads `vat_amount`, `deductible_amount`, `final_payout` from `data.screening?.payout`.
- `buildEnrichment()`: reads payout from assessment/screening payout objects.

### Data flow (after fix)

```
screener._calculate_payout()        <-- single computation
  └── writes screening.payout      <-- stored in workspace JSON
        ├── assessment_processor    <-- copies to assessment.payout
        ├── workbench API           <-- serves to frontend
        │     ├── DecisionBanner    <-- reads & displays
        │     ├── CostBreakdownTab  <-- reads & displays
        │     └── buildEnrichment() <-- reads & displays
        └── CLI                     <-- references screener output
```

## How This Happened

1. The analyzer was built first with a simple payout calculation (good enough for early prototyping).
2. The screener was built later with the correct customer formula — but the analyzer's calculation was never removed.
3. The frontend was built to display coverage data and reimplemented the analyzer's formula in TypeScript (because "the backend values were there").
4. `buildEnrichment()` was added later for the claims table and created yet another variant.
5. Nobody noticed the divergence until a claim with a max-coverage cap exposed the numerical difference.

## Remaining Issue: Screener Formula vs Ground Truth (claim 64288)

Unifying to a single source fixed the internal divergence, but the screener's own formula still doesn't match the customer's ground truth. On the latest run (`clm_20260208_202118_5e80d2`), both screening.json and assessment.json agree on **CHF 4,086.18**, but ground truth says **CHF 4,141.02** — a CHF 54.84 gap.

### Step-by-step comparison

**Ground truth formula** (from customer decision letter):
```
parts_approved       = 2,105.85   (already at 70%)
labor_approved       = 2,150.52   (already at 70%)
subtotal             = 4,256.37
+ VAT 8.1%           = 4,256.37 × 1.081 = 4,601.14
- deductible 10%     = 4,601.14 × 0.10  =   460.10
= final              = 4,141.04  (≈ 4,141.02 after rounding)
```

**System formula** (screener `_calculate_payout()`):
```
covered_gross        = 6,065.89   (parts 2,993.71 + labor 3,072.18)
max_coverage cap     = min(6,065.89, 6,000) = 6,000.00
× 70% coverage       = 6,000 × 0.70 = 4,200.00
+ VAT 8.1%           = 4,200 × 1.081 = 4,540.20
- deductible 10%     = 4,540.20 × 0.10 = 454.02
= final              = 4,086.18
```

### Three bugs in the screener formula

**Bug 1 — Max-coverage cap applied before coverage percent (CHF 46.12 impact)**

The system caps gross at 6,000 and _then_ applies 70%, giving 4,200. It should apply 70% first (6,065.89 × 0.70 = 4,246.12), then check against the cap. Since 4,246.12 < 6,000, the cap doesn't bite and the correct pre-VAT subtotal is 4,246.12 — not 4,200.

Correct order: `gross × rate → cap check`. Current order: `cap check → × rate`.

**Bug 2 — Line-item amounts don't match GT at 70% (CHF 10.25 impact on parts)**

Even without the cap, the system's `covered_gross × 70%` doesn't exactly match the GT approved amounts:

| | System gross × 70% | GT approved | Delta |
|--|---------------------|-------------|-------|
| Parts | 2,993.71 × 0.70 = 2,095.60 | 2,105.85 | −10.25 |
| Labor | 3,072.18 × 0.70 = 2,150.53 | 2,150.52 | +0.01 |

The parts gap (CHF 10.25) suggests the GT includes or excludes specific line items differently — possibly the "Recherche de panne" (diagnostic labor, CHF 249.77) is handled differently, or some ancillary parts are classified differently at the line-item level.

**Bug 3 — Assessment payout section omits VAT entirely**

The assessment.json payout block shows `vat_adjusted: false` and `vat_deduction: 0.0` with no VAT step at all — it jumps straight from `after_coverage: 6,000` to `deductible: 454.02`. The screening.json does include VAT (`vat_amount: 340.2`, `subtotal_with_vat: 4,540.2`). Both arrive at the same final number because the assessment copies the screener's `final_payout`, but the assessment's payout breakdown is misleading — it shows an incomplete formula that doesn't add up if you follow the steps.

### Fix priority

| Bug | Impact | Fix |
|-----|--------|-----|
| 1. Cap ordering | CHF 46.12 per affected claim | Swap: apply coverage % before max-coverage cap |
| 2. Line-item delta | CHF 10.25 on this claim | Investigate which parts GT excludes that system includes |
| 3. Assessment VAT display | Display-only (no payout impact) | Either populate assessment.payout with full breakdown, or remove the redundant fields |

## Lesson

When a derived value (like payout) depends on business rules that live in one place (the screener), it must be computed there and only there. Every other layer should read and display — never recompute. Recomputation is a silent fork that will diverge when the authoritative formula evolves.
