# Plan: Improve table readability — proportional column widths

## Context

The Claims Workbench tabs use full-width tables where the label column absorbs all remaining space, pushing right-aligned numeric values far from their row labels. This creates a readability problem — the eye must travel 600-800px of empty space to connect a label to its value.

The fix: give numeric columns **proportional widths** (percentages) instead of tiny fixed widths, so they claim a fair share of the table and bring values closer to labels. This scales with any number of rows or container width.

## Changes

### 1. Costs tab — `ClaimsWorkbenchPage.tsx` (line 511-517)

**Current colgroup:**
```html
<col className="w-7" />     <!-- chevron -->
<col />                      <!-- label (eats all space) -->
<col className="w-28" />     <!-- claimed = 112px fixed -->
<col className="w-28" />     <!-- covered = 112px fixed -->
```

**New colgroup:**
```html
<col className="w-7" />           <!-- chevron -->
<col />                            <!-- label (flex, but now gets less) -->
<col className="w-[20%]" />        <!-- claimed = 20% of table -->
<col className="w-[20%]" />        <!-- covered = 20% of table -->
```

On a 1200px container: numbers start at ~720px instead of ~1090px. On narrow screens, columns shrink proportionally. The label column still flexes for long part descriptions in expanded rows.

### 2. Ground Truth tab — `GroundTruthTab.tsx` (line 99)

**Current:** `<table className="w-full text-sm">` with no column width constraints.

**New:** Add a `<colgroup>` with proportional widths:
```html
<colgroup>
  <col className="w-[40%]" />    <!-- Field -->
  <col className="w-[20%]" />    <!-- System -->
  <col className="w-[20%]" />    <!-- Ground Truth -->
  <col className="w-[20%]" />    <!-- Diff -->
</colgroup>
```

Also add `table-fixed` to the table className to enforce the column proportions:
```html
<table className="w-full text-sm table-fixed">
```

### 3. No changes needed

- **Payout summary card** (line 688-751): Already uses `max-w-xs ml-auto` — reads well as-is.
- **Documents tab**, **Coverage Checks tab**, **Decisions tab**, **Confidence tab**: Not affected by this pattern (either card-based layouts or already compact).

## Files to modify

1. `ui/src/pages/ClaimsWorkbenchPage.tsx` — lines 515-516 (colgroup widths)
2. `ui/src/components/ClaimsWorkbench/GroundTruthTab.tsx` — line 99 (add colgroup + table-fixed)

## Verification

1. Start frontend dev server (`cd ui && npm run dev`)
2. Open Claims Workbench, select a claim with cost data
3. Check **Costs tab**: labels and numbers should be visually closer; expand a cost type to verify long descriptions still render without clipping
4. Check **Ground Truth tab**: payout comparison fields and values should be visually closer
5. Resize browser window to verify proportional scaling (narrow and wide)
