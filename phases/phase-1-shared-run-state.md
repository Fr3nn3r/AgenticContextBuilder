# Phase 1: Shared Run State Infrastructure

**Completed:** 2026-01-12

## Summary
Lifted run selection state to App.tsx so it persists across screen navigation. ClassificationReview and InsightsPage now accept `selectedRunId` and `onRunChange` as props instead of managing local run state.

## Changes Made

### App.tsx
- Now passes `selectedRunId` and `onRunChange` to:
  - ClassificationReview
  - InsightsPage
- Run selection persists when navigating between screens

### ClassificationReview.tsx
- Added `ClassificationReviewProps` interface with `runs`, `selectedRunId`, `onRunChange`
- Removed local `loadRuns()` function and useEffect
- Receives runs list from parent
- Uses `onRunChange` callback for run selector

### InsightsPage.tsx
- Added `InsightsPageProps` interface with `selectedRunId`, `onRunChange`
- Keeps local runs list (needs metrics data specific to insights)
- When loading runs, notifies parent if no run selected yet
- Uses `onRunChange` callback for run selector

## Verification
- `npm run build` passes with no TypeScript errors
- Run selection now shared between Extraction, Claims, Classification Review, and Benchmark screens
