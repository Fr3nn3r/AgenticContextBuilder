# Implementation Plan: Image Viewer Fix + New Claim Upload Screen

## Summary

Two features:
1. **Image Viewer Fix** - Fit-to-container with zoom/pan
2. **New Claim Screen** - Batch upload UI with real-time pipeline execution via WebSocket

## Agreed Requirements

| Aspect | Decision |
|--------|----------|
| Claim ID uniqueness | Error if exists (no merge/suffix) |
| File persistence | Server-side (survives refresh) |
| File limits | PDF/PNG/JPG/TXT, 100MB max |
| Real-time updates | WebSocket with auto-reconnect |
| Pipeline options | None - defaults (gpt-4o, all stages) |
| Partial failures | Continue, show mixed results |
| Cancel | Yes, with confirmation |
| Multi-claim workflow | Batch list view, run all at once |
| Progress granularity | Per-document status |
| Pre-run editing | Remove + reorder documents |
| Post-completion | Stay on results summary |
| Existing claims | New claims only for v1 |
| Image zoom | Fit-to-container + scroll zoom + pan |

---

## Part 1: Image Viewer Fix

**Current issue**: Lines 184-192 of `DocumentViewer.tsx` - basic `<img>` tag doesn't use space well.

**Solution**: Create `ImageViewer.tsx` component with:
- Fit-to-container default using CSS `object-contain` with calculated dimensions
- Mouse wheel zoom (0.5x to 4x scale)
- Pan when zoomed (mouse drag)
- Double-click to reset

**Files to modify**:
- `ui/src/components/ImageViewer.tsx` (NEW)
- `ui/src/components/DocumentViewer.tsx` (replace inline img)

---

## Part 2: New Claim Upload Screen

### Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ FRONTEND: /claims/new                                          │
│ ├── NewClaimPage.tsx (container, state management)             │
│ ├── PendingClaimCard.tsx (claim card with doc list)            │
│ ├── DocumentUploader.tsx (drag-drop zone)                      │
│ └── PipelineProgress.tsx (WebSocket status display)            │
└──────────────────────────────┬─────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────┐
│ BACKEND: New API Endpoints                                     │
│ ├── POST   /api/upload/claim/{claim_id}     Upload files       │
│ ├── DELETE /api/upload/claim/{claim_id}     Remove claim       │
│ ├── DELETE /api/upload/claim/{id}/doc/{id}  Remove doc         │
│ ├── GET    /api/upload/pending              List pending       │
│ ├── PUT    /api/upload/claim/{id}/reorder   Reorder docs       │
│ ├── POST   /api/pipeline/run                Start pipeline     │
│ ├── POST   /api/pipeline/cancel/{run_id}    Cancel             │
│ └── WS     /api/pipeline/ws/{run_id}        Progress stream    │
└──────────────────────────────┬─────────────────────────────────┘
                               │
┌──────────────────────────────▼─────────────────────────────────┐
│ STORAGE                                                        │
│ ├── Staging: output/.pending/{claim_id}/docs/{uuid}.{ext}      │
│ │            manifest.json (claim metadata, doc order)         │
│ └── On run:  Move to output/claims/{claim_id}/                 │
└────────────────────────────────────────────────────────────────┘
```

### Backend Changes

**New service**: `src/context_builder/api/services/upload.py`
- `UploadService` class for staging area management
- Methods: `add_document`, `remove_document`, `reorder_documents`, `list_pending_claims`
- File validation (type, size 100MB)
- Claim ID uniqueness check against both staging and `output/claims/`

**New service**: `src/context_builder/api/services/pipeline.py`
- `PipelineService` class for async pipeline execution
- Methods: `start_pipeline`, `cancel_pipeline`, `get_run_status`
- Progress callback integration with `process_claim()`
- Cancel flag using `asyncio.Event`

**Modify**: `src/context_builder/api/main.py`
- Add all new endpoints
- Add WebSocket endpoint with `ConnectionManager` for broadcasting
- Initialize services with staging dir `output/.pending/`

**Modify**: `src/context_builder/pipeline/run.py`
- Add optional `progress_callback` parameter to `process_claim()`
- Call callback at each phase transition: ingesting → classifying → extracting → done/failed

### Frontend Changes

**New types** in `ui/src/types/index.ts`:
```typescript
PendingDocument, PendingClaim, DocPipelineStatus, DocProgress, PipelineRun, WebSocketMessage
```

**New API calls** in `ui/src/api/client.ts`:
```typescript
uploadDocuments(), listPendingClaims(), deletePendingClaim(), deletePendingDocument(),
reorderDocuments(), startPipeline(), cancelPipeline(), getPipelineStatus()
```

**New hook**: `ui/src/hooks/usePipelineWebSocket.ts`
- WebSocket connection management
- Auto-reconnect on disconnect (3s delay)
- State sync on reconnect
- Callbacks: `onDocProgress`, `onRunComplete`, `onRunFailed`

**New components**:
| Component | Purpose |
|-----------|---------|
| `NewClaimPage.tsx` | Main container, state, orchestration |
| `PendingClaimCard.tsx` | Claim card with drag-drop zone and doc list |
| `DocumentUploader.tsx` | Drag-drop area with validation feedback |
| `PipelineProgress.tsx` | Per-doc status list with icons, timing, errors |

**Modify**: `ui/src/components/Sidebar.tsx`
- Add "New Claim" nav item at top with PlusIcon
- New path: `/claims/new`
- Add to View type

**Modify**: `ui/src/App.tsx`
- Add route: `<Route path="/claims/new" element={<NewClaimPage />} />`

### WebSocket Protocol

**Server → Client**:
```json
{"type": "doc_progress", "claim_id": "X", "doc_id": "Y", "status": "classifying", "error": null}
{"type": "sync", "status": "running", "docs": {...}}
{"type": "run_complete", "summary": {"total": 10, "success": 8, "failed": 2}}
{"type": "run_failed", "error": "message"}
{"type": "ping"}
```

**Client → Server**: `"pong"` (keepalive response)

---

## Implementation Order

### Phase 1: Image Viewer (small fix)
1. Create `ui/src/components/ImageViewer.tsx`
2. Update `DocumentViewer.tsx` lines 184-192

### Phase 2: Backend Upload Infrastructure
1. Create `src/context_builder/api/services/upload.py`
2. Add upload endpoints to `main.py`
3. Test with curl/Postman

### Phase 3: Backend Pipeline Service
1. Create `src/context_builder/api/services/pipeline.py`
2. Modify `pipeline/run.py` to add progress callback
3. Add pipeline endpoints to `main.py`
4. Add WebSocket endpoint

### Phase 4: Frontend Types & API
1. Add types to `ui/src/types/index.ts`
2. Add API functions to `ui/src/api/client.ts`
3. Create `ui/src/hooks/usePipelineWebSocket.ts`

### Phase 5: Frontend UI Components
1. Create `NewClaimPage.tsx` (basic structure)
2. Create `DocumentUploader.tsx` (drag-drop)
3. Create `PendingClaimCard.tsx` (claim + docs list)
4. Create `PipelineProgress.tsx` (status display)

### Phase 6: Integration
1. Update `Sidebar.tsx` with "New Claim" link
2. Update `App.tsx` with route
3. Wire up WebSocket to UI
4. Add cancel confirmation modal

---

## Files to Create

| Path | Purpose |
|------|---------|
| `ui/src/components/ImageViewer.tsx` | Zoomable image viewer |
| `ui/src/components/NewClaimPage.tsx` | New claim page container |
| `ui/src/components/PendingClaimCard.tsx` | Claim card component |
| `ui/src/components/DocumentUploader.tsx` | Drag-drop upload zone |
| `ui/src/components/PipelineProgress.tsx` | Progress display |
| `ui/src/hooks/usePipelineWebSocket.ts` | WebSocket hook |
| `src/context_builder/api/services/upload.py` | Upload service |
| `src/context_builder/api/services/pipeline.py` | Pipeline service |

## Files to Modify

| Path | Changes |
|------|---------|
| `ui/src/components/DocumentViewer.tsx` | Use ImageViewer component |
| `ui/src/components/Sidebar.tsx` | Add "New Claim" nav item |
| `ui/src/App.tsx` | Add `/claims/new` route |
| `ui/src/types/index.ts` | Add new types |
| `ui/src/api/client.ts` | Add API functions |
| `src/context_builder/api/main.py` | Add endpoints |
| `src/context_builder/pipeline/run.py` | Add progress callback |

---

## Verification Plan

1. **Image Viewer**: Open an image document, verify fit-to-container, scroll to zoom, drag to pan
2. **Upload**: Create claim, drag files, verify progress bar, verify files in `output/.pending/`
3. **Remove/Reorder**: Remove a doc, reorder docs, verify manifest updated
4. **Claim ID Validation**: Try duplicate ID, verify error shown
5. **Pipeline Run**: Click "Run Pipeline", verify WebSocket connects, see per-doc status updates
6. **Cancel**: Click cancel mid-pipeline, confirm dialog, verify partial results saved
7. **Reconnect**: Disconnect network briefly, verify auto-reconnect and state sync
8. **Completion**: Verify results summary shows all docs with status, timing, errors
9. **Navigation**: Verify can navigate to Claims Review for processed claims
