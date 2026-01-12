# Phase 6: Add PDF Viewer to Classification Review

**Completed:** 2026-01-12

## Summary
Added a split-view layout to ClassificationReview with a PDF/image viewer at the top and classification review controls at the bottom. Reviewers can now see the actual document while reviewing classification predictions.

## Changes Made

### ui/src/components/ClassificationReview.tsx

**New imports:**
- `DocumentViewer` component
- `DocPayload` type
- `getDoc`, `getDocSourceUrl` API functions

**New state:**
- `docPayload: DocPayload | null` - Stores full document data including pages

**Updated `loadDetail` function:**
- Now fetches both classification detail AND full doc payload
- Doc payload provides pages array and source URL for the viewer

**Restructured detail panel:**
- Changed from single scrolling panel to vertical split layout
- Top half (h-1/2): DocumentViewer showing PDF/image
- Bottom half (h-1/2): Condensed classification info + review actions

**UI improvements in review panel:**
- Compact header with filename, claim ID, confidence badge
- Condensed classification info card
- Streamlined review buttons (Confirm/Change Type)
- Notes textarea and Save button

## Layout Structure
```
+-------------------+-------------------+
|                   |                   |
|   Doc List        |   DocumentViewer  |
|   (Table)         |   (PDF/Image)     |
|                   |                   |
|                   +-------------------+
|                   |                   |
|                   |   Classification  |
|                   |   Review Panel    |
|                   |                   |
+-------------------+-------------------+
```

## Verification
- `npm run build` passes with no TypeScript errors
- DocumentViewer displays PDF/image when document selected
- Classification review controls work as before
