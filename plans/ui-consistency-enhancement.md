# UI Consistency & Enhancement Plan

## Summary
Implement 9 UI improvements for consistency across all screens, including layout standardization, shared run selection, human-readable run labels, renamed screens, and a new Document Review screen.

---

## Requirements from Feedback

1. **Layout consistency**: Use full-width layout across all 4 run-dependent screens
2. **Human-readable run labels**: Date + time format (e.g., "Jan 7 at 9:40 AM")
3. **Consistent run selector**: Same position/style across all run-dependent screens
4. **Shared run selection**: Run selection persists across screen navigation
5. **Run-scoped data**: Each screen shows only data from selected run
6. **Classification Review**: Add PDF/image viewer in split panel
7. **Rename**: "Document Review" → "Claims Document Review"
8. **Title placement**: Single title at top only (remove duplicates)
9. **NEW screen**: "Document Review" - flat doc list without claims concept

---

## Implementation Plan

### Phase 1: Shared Run State Infrastructure

**Goal**: Lift run selection to App.tsx so it persists across all screens.

**Files to modify**:
- `ui/src/App.tsx` - Already manages `selectedRunId`, pass to all screens
- `ui/src/components/ClassificationReview.tsx` - Accept run as prop instead of local state

**Changes**:
1. Pass `selectedRunId` and `onRunChange` props to ClassificationReview
2. Pass `selectedRunId` and `onRunChange` props to InsightsPage
3. Remove local run state from ClassificationReview
4. Remove local run state from InsightsPage

---

### Phase 2: Create Shared RunSelector Component

**Goal**: Single reusable component for run selection with consistent styling.

**Files to create**:
- `ui/src/components/shared/RunSelector.tsx`

**Component spec**:
```tsx
interface RunSelectorProps {
  runs: ClaimRunInfo[] | DetailedRunInfo[];
  selectedRunId: string | null;
  onRunChange: (runId: string) => void;
  showMetadata?: boolean; // Show model, docs count on hover/inline
}
```

**Label format**: Human-readable date + time
- `formatRunLabel(run)` → "Jan 7 at 9:40 AM"
- Hover tooltip shows: Run ID, model, doc count
- Position: Top-left below page title area

---

### Phase 3: Layout Standardization

**Goal**: All run-dependent screens use full-width layout with consistent structure.

**Files to modify**:
- `ui/src/components/ExtractionPage.tsx` - Remove max-width, use full width
- `ui/src/components/InsightsPage.tsx` - Remove max-width, use full width
- `ui/src/components/ClaimsTable.tsx` - Already full width, add shared RunSelector
- `ui/src/components/ClassificationReview.tsx` - Already full width, use shared RunSelector

**Layout structure** (consistent across all):
```
┌─────────────────────────────────────────────────┐
│ [RunSelector: top-left]    [Filters: top-right] │
├─────────────────────────────────────────────────┤
│                                                 │
│              Screen Content                     │
│              (full width)                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

### Phase 4: Fix Title Duplication

**Goal**: Title appears ONLY in the header bar (managed by App.tsx), not duplicated inside components.

**Files to modify**:
- `ui/src/components/ExtractionPage.tsx` - Remove `<h2>Extraction</h2>` heading
- `ui/src/components/ClaimsTable.tsx` - Remove `<h2>Document Review</h2>` heading
- `ui/src/components/InsightsPage.tsx` - (already uses header only via tabs)
- `ui/src/App.tsx` - Update `getPageTitle()` for renamed screens

---

### Phase 5: Rename "Document Review" to "Claims Document Review"

**Files to modify**:
- `ui/src/components/Sidebar.tsx` - Change label from "Document Review" to "Claims Document Review"
- `ui/src/App.tsx` - Update `getPageTitle()` to return "Claims Document Review"

---

### Phase 6: Add PDF/Image Viewer to Classification Review

**Goal**: Split panel layout with doc list on left, PDF/image viewer on right.

**Files to modify**:
- `ui/src/components/ClassificationReview.tsx`

**Changes**:
1. Change from 50/50 split (list | detail panel) to:
   - Left: Document list (narrower, ~40%)
   - Right: PDF/Image viewer + classification info (wider, ~60%)
2. Reuse existing `DocumentViewer` component for PDF/image display
3. Show classification info (predicted type, signals, hints) below/beside viewer
4. Keep review actions (confirm/change type) in right panel

**Layout**:
```
┌────────────────┬──────────────────────────────────┐
│  Doc List      │   PDF/Image Viewer               │
│  (sortable)    │   ─────────────────────────────  │
│                │   Classification: FNOL Form      │
│  - doc1.pdf    │   Confidence: 95%                │
│  - doc2.pdf ◄  │   Signals: [...]                 │
│  - doc3.jpg    │   ─────────────────────────────  │
│                │   [Confirm] [Change Type]        │
└────────────────┴──────────────────────────────────┘
```

---

### Phase 7: Create NEW "Document Review" Screen

**Goal**: New screen showing flat list of ALL documents in run (no claims grouping).

**Files to create**:
- `ui/src/components/DocumentReview.tsx`

**Routes to add in App.tsx**:
- `/documents` - New Document Review screen

**Sidebar changes**:
- Add new nav item "Document Review" at `/documents`
- Existing "Claims Document Review" stays at `/claims`

**Screen structure** (3-panel like ClaimReview):
```
┌────────────────┬─────────────────────┬────────────────┐
│  Doc List      │   Document Viewer   │ Field Extract  │
│  ───────────   │                     │                │
│  Filters:      │   [PDF/Image/Text]  │ Extracted vals │
│  - Gate status │                     │ + Labels       │
│  - Doc type    │                     │                │
│  - Label status│                     │ [Save Labels]  │
│  ───────────   │                     │                │
│  doc1 [FAIL]   │                     │                │
│  doc2 [PASS] ◄ │                     │                │
│  doc3 [WARN]   │                     │                │
│  ───────────   │                     │                │
│  [Prev] [Next] │                     │                │
└────────────────┴─────────────────────┴────────────────┘
```

**Features**:
- Filter by: Quality gate (PASS/WARN/FAIL), Doc type, Label status
- Sort by: filename, doc type, confidence, gate status
- Navigation: Previous/Next buttons, keyboard shortcuts (n/p)
- No claims context - just doc_id, filename, doc_type
- Reuses `DocumentViewer` and `FieldsTable` components

**API endpoint**:
The existing `listClassificationDocs(runId)` returns docs for a run but lacks extraction-specific fields (quality_status, has_labels for extraction).

Options:
1. **Preferred**: Add new endpoint `GET /api/runs/{run_id}/documents` with fields: doc_id, filename, claim_id, doc_type, confidence, quality_status, has_labels
2. **Alternative**: Extend classification endpoint to include extraction fields

Will need to add to:
- `src/context_builder/api/main.py` - New endpoint
- `ui/src/api/client.ts` - New `listRunDocuments(runId)` function

---

### Phase 8: Update Sidebar Navigation Order

**Final sidebar order**:
1. Extraction (`/dashboard`)
2. Classification Review (`/classification`)
3. Document Review (`/documents`) - **NEW**
4. Claims Document Review (`/claims`) - **RENAMED**
5. Benchmark (`/insights`)
6. Extraction Templates (`/templates`)

---

## Files Summary

### New files:
- `ui/src/components/shared/RunSelector.tsx`
- `ui/src/components/DocumentReview.tsx`

### Modified files:
- `ui/src/App.tsx` - Routing, shared run state, title updates
- `ui/src/components/Sidebar.tsx` - Nav items renamed/added
- `ui/src/components/ClassificationReview.tsx` - Split panel with viewer, shared run
- `ui/src/components/ExtractionPage.tsx` - Full width, remove title, shared run selector
- `ui/src/components/InsightsPage.tsx` - Full width, shared run
- `ui/src/components/ClaimsTable.tsx` - Remove title, use shared RunSelector

### Backend (if needed):
- `src/context_builder/api/main.py` - Add `/api/runs/{run_id}/documents` endpoint

---

## Verification Plan

1. **Run selection persistence**: Select run on Extraction, navigate to Classification Review, verify same run selected
2. **Layout consistency**: Compare all 4 run-dependent screens side-by-side, verify full-width
3. **Run labels**: Verify dropdown shows "Jan 7 at 9:40 AM" format
4. **Title duplication**: Verify each screen has title only in header, not duplicated
5. **Classification Review viewer**: Click doc, verify PDF/image displays in split panel
6. **New Document Review**: Navigate to `/documents`, verify flat doc list, filters work, navigation works
7. **Sidebar**: Verify correct order and labels
8. **E2E test**: Run existing e2e tests, update snapshots if needed

---

## Implementation Order

1. Phase 1: Shared run state (App.tsx changes)
2. Phase 2: RunSelector component
3. Phase 3: Layout standardization (all screens)
4. Phase 4: Title fixes
5. Phase 5: Rename screen
6. Phase 6: Classification Review PDF viewer
7. Phase 7: New Document Review screen (largest change)
8. Phase 8: Sidebar updates
