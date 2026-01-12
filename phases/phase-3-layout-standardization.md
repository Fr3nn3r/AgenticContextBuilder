# Phase 3: Layout Standardization

**Completed:** 2026-01-12

## Summary
Removed max-width constraints from ExtractionPage and InsightsPage to make all run-dependent screens use full-width layouts.

## Changes Made

### ui/src/components/ExtractionPage.tsx
- Changed `<div className="p-6 max-w-6xl mx-auto">` to `<div className="p-6">`
- Content now fills available width in the right panel

### ui/src/components/InsightsPage.tsx
- Changed `<div className="p-4 space-y-4 max-w-[1600px] mx-auto">` to `<div className="p-4 space-y-4">`
- Content now uses full viewport width

## Already Full-Width
- ClaimsTable - already used `p-6` without max-width
- ClassificationReview - already used `h-full flex flex-col`

## Verification
- `npm run build` passes with no TypeScript errors
- All run-dependent screens now use full-width layout
