# Phase 2: Create Shared RunSelector Component

**Completed:** 2026-01-12

## Summary
Created a reusable RunSelector component with human-readable date labels ("Jan 7 at 9:40 AM") and consistent styling. Updated ClaimsTable, ClassificationReview, and InsightsPage to use it.

## New Files

### ui/src/components/shared/RunSelector.tsx
- Generic component that works with any run type (ClaimRunInfo, RunInfo, DetailedRunInfo)
- Props: `runs`, `selectedRunId`, `onRunChange`, `showMetadata`, `testId`
- `formatRunLabel()` function for human-readable timestamps
- Optional inline metadata display (model, doc count)

## Updated Files

### ui/src/components/shared/index.ts
- Added export for `RunSelector` and `formatRunLabel`

### ui/src/components/ClaimsTable.tsx
- Replaced inline run selector with `<RunSelector showMetadata />`
- Removed unused `selectedRun` variable and `formatTimestamp` import

### ui/src/components/ClassificationReview.tsx
- Replaced inline run selector with `<RunSelector showMetadata />`

### ui/src/components/InsightsPage.tsx
- Replaced inline run selector with `<RunSelector />`
- Kept separate run metadata section (has more detailed info)

## Notes
- ExtractionPage uses a different run selection UX (left panel list organized by date) which is appropriate for its layout - not converted to use RunSelector
- Run selector now shows human-readable labels: "Jan 7 at 9:40 AM (Latest)"

## Verification
- `npm run build` passes with no TypeScript errors
- All three updated screens use consistent run selector styling
