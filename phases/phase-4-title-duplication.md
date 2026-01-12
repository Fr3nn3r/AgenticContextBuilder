# Phase 4: Fix Title Duplication

**Completed:** 2026-01-12

## Summary
Removed duplicate titles from component bodies. Title now appears only in the app header (managed by App.tsx's `getPageTitle()` function).

## Changes Made

### ui/src/components/ExtractionPage.tsx
- Removed `<h2>Extraction</h2>` heading and subtitle block

### ui/src/components/ClaimsTable.tsx
- Removed `<h2>Document Review</h2>` heading and subtitle
- Simplified header to just RunSelector

### ui/src/components/TemplatesPage.tsx
- Removed `<h2>Extraction Templates</h2>` heading and subtitle block

## Not Changed
- ClassificationReview - had no duplicate title
- InsightsPage - had no duplicate title (uses tab navigation instead)
- DocReview.tsx - `<h2>Extraction Review</h2>` is appropriate context for the nested component

## How It Works
App.tsx's header already shows the page title via `getPageTitle()`:
- "/" or "/dashboard" -> "Extraction"
- "/claims" -> "Document Review"
- "/classification" -> "Classification Review"
- "/insights" -> "Benchmark"
- "/templates" -> "Extraction Templates"

## Verification
- `npm run build` passes with no TypeScript errors
- Each screen shows title only once in the app header
