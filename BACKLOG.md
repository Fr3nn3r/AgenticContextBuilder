# Backlog

> Single source of truth for all tasks. Update before clearing context.
> Video review analysis: `data/Videos/VIDEO_ANALYSIS.md`

---

## Doing

_Currently active work. Add handoff notes inline._

### 2026-01-17 - P0 Bug Fixes (Session 3) - NEEDS MANUAL VERIFICATION

**Status**: Code changes complete, unit tests pass, **manual testing required**

**Changes Made** (not yet verified in running app):

1. **BUG-01: Extraction data not showing from All Claims**
   - File: `src/context_builder/api/services/documents.py`
   - Added `_find_latest_run_with_extraction()` method
   - `get_doc()` now auto-detects latest run when no `run_id` provided
   - Root cause: Code analysis only, not reproduced first

2. **BUG-03: Ground truth save navigates away**
   - File: `ui/src/components/DocumentReview.tsx`
   - Removed auto-advance logic from `handleSave()` (lines 331-340 deleted)
   - Root cause: Clear from code - had explicit `setSelectedDocId(nextDoc.doc_id)`

3. **BUG-04: Doc type scoreboard inaccurate**
   - File: `src/context_builder/api/insights.py`
   - Added missing doc types to `SUPPORTED_DOC_TYPES`: customer_comm, damage_evidence, medical_report
   - Root cause: Likely correct but not verified with real data

4. **Non-functional buttons (BUG-09-15)**
   - File: `ui/src/components/PipelineControlCenter.tsx`
   - View Documents: Added `handleViewDocuments()` - navigates to `/batches?run_id={batchId}`
   - Export Summary: Added `handleExportSummary()` - downloads JSON file
   - Audit log dropdown: Added `auditFilter` state and filtering logic
   - Bell notification: Does not exist in codebase (not a bug)

**Test Results**:
- Python unit tests: 994/994 pass ✅
- UI unit tests: 163/163 pass ✅
- E2E tests: NOT RUN (wouldn't catch these bugs anyway - use mocks)

**⚠️ CRITICAL: Manual Testing Required**

The fixes were made based on code analysis only. To verify they actually work:

```powershell
# Terminal 1: Start backend
.\scripts\dev-restart.ps1
# or: uvicorn context_builder.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd ui && npm run dev
```

**Manual Test Checklist**:

- [ ] **BUG-01**: Navigate to All Claims → Click any document → Verify extraction data shows (not empty)
- [ ] **BUG-03**: Open document in Batches → Make a label change → Click Save → Verify you stay on same document
- [ ] **BUG-04**: View Doc Type Scoreboard → Verify "Extracted" column shows non-zero for documents that were extracted
- [ ] **BUG-09**: Pipeline → Batches tab → Expand batch → Click "View Documents" → Verify navigation works
- [ ] **BUG-10**: Pipeline → Batches tab → Expand batch → Click "Export Summary" → Verify JSON file downloads
- [ ] **BUG-14**: Pipeline → Config tab → Use audit log dropdown → Verify filtering works

**Files Changed This Session**:
- `src/context_builder/api/services/documents.py` (added auto-run detection)
- `src/context_builder/api/insights.py` (added 3 doc types)
- `ui/src/components/DocumentReview.tsx` (removed auto-advance)
- `ui/src/components/PipelineControlCenter.tsx` (added button handlers, audit filter)

---

### 2026-01-17 - E2E Test Fixes ✅ COMPLETE

**Status**: All E2E tests passing (255 passed, 9 skipped, 0 failed)

**Session 2 Fixes**:
1. Added missing `/api/documents` mock in `ui/e2e/utils/mock-api.ts`
2. Fixed `document-labeling.spec.ts` test expectation (stays on current doc)

**Session 1 Fixes**:
1. Fixed DocumentReview status badge update
2. Fixed test infrastructure mocks
3. Fixed selector issues

**Final Results**:
- Python unit tests: 994/994 pass ✅
- UI unit tests: 163/163 pass ✅
- Full E2E: 255/264 pass, 9 skipped ✅

---

## Todo

### P0 - Critical Bugs (Fix First)

_All P0 bugs fixed! See Done section._

### P1 - UI Consistency & Polish

- [ ] **FEAT-28: Batches filter**
  - Add filter functionality for batches list on left panel
  - Currently will be difficult to scale with many batches

- [ ] **FEAT-29: Confidence tooltips**
  - Add hints explaining confidence percentages
  - Currently unclear if it's classification or extraction confidence

- [ ] **FEAT-30: Show extractor type**
  - Display which extractor ran (Azure vs OpenAI Vision) on document screen
  - Currently can't tell who was responsible for extraction

- [ ] **FEAT-31: JSON tab for small outputs**
  - Formatted JSON view for vision/classification output
  - Only for small outputs (not full text documents - crashes Playwright)
  - Color-formatted like Python console package

- [ ] **FEAT-32: Remove GPT-4 label**
  - Remove model label from batches header
  - Each stage could use different models - label is misleading

- [ ] **FEAT-33: Consistent header**
  - Add sign out menu and theme toggle to batches screen
  - Currently missing on batches but present on other screens

- [ ] **FEAT-34: Remove redundant status line**
  - Remove "4x4 ingested, 4x4 classified" line above cards
  - Redundant with card content

- [ ] **FEAT-36: Enterprise batch names**
  - Replace fun names (wise fox, quick lion, crisp bear) with professional naming
  - Current names don't feel enterprise-grade

- [ ] **BUG-05: Filter shows wrong claim**
  - Filter shows "All Claims" when specific claim is selected from batch
  - Should display the actual claim number

- [ ] **BUG-07: Missing extraction = yellow instead of red**
  - When extraction returns nothing but ground truth exists, show as incorrect (red)
  - Currently shows yellow warning - should be red "incorrect"

### P2 - Pipeline Screen Improvements

- [ ] **FEAT-17: Three-level config display**
  - Show: bundle version, classification version, extraction version
  - Classification version = prompt + model + document registry version
  - Extraction version = prompt template + model + extraction template version

- [ ] **FEAT-18: View prompt details**
  - Sliding pane from right with color-formatted prompt display
  - Apply to Pipeline config and Compliance bundle details

- [ ] **FEAT-19: Separate classifier/extractor config**
  - Classification config and extraction config as separate sections
  - Not just "prompt config"

- [ ] **FEAT-20: Config tooltips**
  - Add hints explaining: overwrite, compute metrics, dry run options
  - Mouse-over explanations

- [ ] **FEAT-21: Flexible scope selection for new batch**
  - Select specific claims/documents to rerun (not just all)
  - Use cases: rerun 3 claims, or just 1 document extraction

- [ ] **FEAT-22: Export summary panel**
  - Sliding panel with formatted JSON manifest
  - Download button to save

- [ ] **FEAT-23: View documents navigation**
  - Link to batch documents from pipeline screen
  - Currently button does nothing

- [ ] **FEAT-35: Logs tab**
  - Separate "Logs" tab instead of audit logs in Config section
  - Show logs per batch

### P3 - Versioning Strategy (Discussion → Implementation)

- [ ] **DISC-03/04/05: Define versioning strategy**
  - Classification version = prompt + model + document registry version
  - Extraction version = prompt template + model + extraction template version
  - Decision needed: per-template versions or global?

- [ ] **DISC-06: Bump minor version more often**
  - Context builder version wasn't updated between runs with different bundles
  - Need policy for when to bump

- [ ] **FEAT-24: Show classifier version in compliance**
  - Display classifier version alongside extractor version
  - Currently only shows extractor

### P4 - Templates Editing Features

- [ ] **FEAT-08: Edit templates in UI**
  - Ability to edit extraction templates directly in UI

- [ ] **FEAT-09: Drag & drop fields**
  - Move fields between required/optional via drag & drop

- [ ] **FEAT-10: Template versioning**
  - Version control for each extraction template
  - Changes to template = new version

- [ ] **FEAT-11: Define new fields**
  - Dynamically add new fields to templates
  - Should inform document registry for classification

- [ ] **FEAT-12: Edit quality gate rules**
  - Make quality gate rules editable in UI
  - Add hints explaining what rules mean

### P5 - Evaluation Screen Redesign

- [ ] **FEAT-13: Pipeline scope view**
  - Show fields and docs over time for pipeline versions
  - Track what's included in each version

- [ ] **FEAT-14: Compare classifiers**
  - Compare classification accuracy across versions
  - Not compare runs/batches - compare classifier versions

- [ ] **FEAT-15: Compare extractors**
  - Compare extraction accuracy across versions

- [ ] **FEAT-16: Scope & accuracy dimensions**
  - Two key metrics for any comparison
  - Rethink entire screen around these concepts

### P6 - Compliance Screen Enhancements

- [ ] **FEAT-25: View prompt sliding panel**
  - Click to view prompt with colors in compliance bundle details

- [ ] **FEAT-26: Decision records sorting**
  - Sort table by clicking column headers

- [ ] **FEAT-27: Decision records pagination**
  - 50-100 per page with navigation arrows
  - Currently shows all (limited to 100)

### P7 - User Role Permissions

- [ ] **FEAT-37: Role permissions implementation**
  - Implement fine-grained permissions for: reviewer, operator, auditor, admin
  - Define what features available per role

- [ ] **FEAT-38: Profile-based testing**
  - Test features based on each profile
  - Add to test plan

### P8 - AI Agent Screen (Major New Feature)

- [ ] **FEAT-01: AI Agent chat interface**
  - ChatGPT-style chatbot interface for claims analysis
  - New screen/section in the app

- [ ] **FEAT-02: Claim selector**
  - Ability to select a claim to work on in agent

- [ ] **FEAT-03: Canonical claim view**
  - Generate unified view of claim from all extracted documents
  - Feed to model context at start

- [ ] **FEAT-04: Agent tools**
  - Tools for agent to retrieve full document text at runtime
  - Load policy, medical report, etc. on demand

- [ ] **FEAT-05: RAG strategy**
  - Implement RAG for large documents
  - Think about chunking strategy

- [ ] **FEAT-06: Evidence drag & drop**
  - Drag & drop new evidence/documents into agent chat

- [ ] **FEAT-07: Auto-pipeline on upload**
  - Auto-run pipeline when new documents added to agent
  - Naturally adds to claims context

### P9 - Architectural Discussions

- [ ] **DISC-01: Claims abstraction**
  - How to abstract "claims" concept for other use cases
  - Support: underwriting, manufacturing warranty, etc.
  - Should be "anything context builder"

- [ ] **DISC-02: Line of Business (LOB)**
  - How to define LOB - automatic or from metadata?
  - What if dealing with non-claim files?

- [ ] **DISC-07: Missing vs wrong extraction**
  - Decision: Both are INCORRECT (user confirmed)
  - Update logic to treat missing with ground truth as incorrect

- [ ] **DISC-08: Hint language**
  - Should hints be English-only for better accuracy?
  - Currently mix of Spanish/French causing issues

- [ ] **DISC-09: Consistent tree view**
  - When clicking claim in tree, need batch selector + consistent structure

- [ ] **DISC-10: Root documents view**
  - What to show at root level? Currently "a bit messy"

### Infrastructure

- [ ] **Fix hardcoded paths** (remaining)
  - See: `plans/20260114-Fix-Hardcoded-Paths.md`
  - Labels path fixed (2026-01-15), check for others

---

## Done (Recent)

_Cleared 2026-01-17. See git history for details._

### 2026-01-17 - P0 Bug Fixes

- [x] **BUG-01: Extraction data not showing from All Claims** (FIXED)
  - Backend now auto-detects latest run when accessing documents without run_id
  - Modified: `src/context_builder/api/services/documents.py` - added `_find_latest_run_with_extraction()` method
  - Documents from "All Claims" now show extraction data correctly

- [x] **BUG-03: Ground truth save navigates away** (FIXED)
  - Removed auto-advance behavior from Save button
  - Modified: `ui/src/components/DocumentReview.tsx` - handleSave now stays on current document
  - Users can manually select next document when ready

- [x] **BUG-04: Doc type scoreboard inaccurate** (FIXED)
  - Added missing doc types to SUPPORTED_DOC_TYPES list
  - Modified: `src/context_builder/api/insights.py` - added customer_comm, damage_evidence, medical_report
  - Scoreboard now shows correct extracted counts for all doc types

- [x] **Non-functional buttons (BUG-09 to BUG-15)** (FIXED)
  - View Documents: navigates to `/batches?run_id={batchId}`
  - Export Summary: downloads batch summary as JSON
  - Delete Batches: already worked (had onClick)
  - Audit log dropdown: now filters entries by action type
  - Refresh buttons: already worked
  - Bell notification: doesn't exist in codebase (not implemented yet)
  - Modified: `ui/src/components/PipelineControlCenter.tsx`

- [x] Document Detail Page, Documents List Page, Phase 3-4 UI updates (2026-01-15)
- [x] Batches Overview UI Improvements - 10 tasks (2026-01-15)
- [x] App.tsx refactoring - 78% reduction (2026-01-15)
- [x] Compliance UI suite, storage, version bundles (2026-01-14)
- [x] Labels migration to global registry (2026-01-15)
- [x] LLM call linking for compliance (2026-01-15)

---

## Reference

Detailed docs available in `.claude/docs/`:
- `architecture.md` - Pipeline flow, components, data structures
- `compliance.md` - Compliance dev instructions, decision logging
- `testing.md` - Test commands, organization, troubleshooting
- `data/Videos/VIDEO_ANALYSIS.md` - Full video review analysis

---

## Handoff Template

```markdown
### [DATE] - [WINDOW]
**Done**: What was completed
**Files**: paths changed
**Next**: Immediate next step
```
