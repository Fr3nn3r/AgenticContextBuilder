# Phase 7: Create New Document Review Screen

**Completed:** 2026-01-12

## Summary
Created a new "Document Review" screen that shows a flat list of all documents in a run without claims grouping. This provides a document-centric view for full extraction review with field labeling capabilities built-in.

## Changes Made

### ui/src/components/DocumentReview.tsx (NEW)

**Layout: 3-panel design**
- Left panel (w-72): Document list with filters
- Center panel (flex): DocumentViewer (PDF/text)
- Right panel (w-420px): FieldsTable with full labeling

**Document List Features:**
- Flat list using `listClassificationDocs` API
- Filters by document type, review status, and search query
- Shows filename, doc type, confidence, claim ID, status
- Visual selection indicator with blue highlight

**Full Extraction Review Features:**
- FieldsTable integration with all labeling callbacks:
  - `onConfirm`: Mark field as LABELED with truth value
  - `onUnverifiable`: Mark field as UNVERIFIABLE with reason
  - `onEditTruth`: Edit existing truth values
  - `onQuoteClick`: Highlight provenance in document viewer
- Highlight state for provenance tracking (quote, page, char offsets)
- Reviewer name input
- Review notes textarea
- Save button with unsaved changes indicator
- Optional fields toggle

**State Management:**
- `fieldLabels`: Current label state for all fields
- `docLabels`: Document-level labels
- `hasUnsavedChanges`: Track dirty state
- Warns user before switching documents with unsaved changes

### ui/src/App.tsx

**Updated imports:**
- Added `DocumentReview` component import

**Updated `getPageTitle`:**
- Added `/documents` -> "Document Review"

**Updated `getCurrentView`:**
- Added "documents" to View type
- Added `/documents` path check

**Added route:**
- `/documents` route with DocumentReview component

## Layout Structure
```
+------------+---------------------------+----------------+
|            |                           |                |
|  Document  |                           |  Field         |
|  List      |     DocumentViewer        |  Extraction    |
|  (filters) |     (PDF/Text tabs)       |  Panel         |
|            |                           |  + Save btn    |
|            |                           |  + Reviewer    |
|            |                           |  + Notes       |
+------------+---------------------------+----------------+
```

## Key Differences from Claims Document Review
- **Flat list**: No claims hierarchy, shows all documents in run
- **Self-contained**: Full labeling without navigation to another screen
- **Document-centric**: Optimized for document-by-document review workflow

## Verification
- `npm run build` passes with no TypeScript errors
- DocumentReview displays flat document list when run selected
- Filters work for doc type, status, and search
- DocumentViewer displays PDF/image when document selected
- FieldsTable allows labeling fields as LABELED or UNVERIFIABLE
- Clicking provenance quotes highlights text in viewer
- Save persists labels to backend
