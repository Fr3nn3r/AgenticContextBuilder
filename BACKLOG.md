# Backlog

> Single source of truth for all tasks. Update before clearing context.
> Video review analysis: `data/Videos/VIDEO_ANALYSIS.md`

---

## Doing

_Currently active work. Add handoff notes inline._

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

### 2026-01-17 - P1 Bug Fixes

- [x] **BUG-05: Filter shows wrong claim** (Fixed)
  - Filter showed "All Claims" when specific claim was selected from batch
  - Fix: DocumentReview now reads `selectedClaim` from ClaimsContext
  - Modified: `ui/src/components/DocumentReview.tsx` - imports useClaims, checks selectedClaim when no URL param

### 2026-01-17 - P0 Bug Fixes ✅ VERIFIED

**Verification (2026-01-17)**: API tests + Playwright screenshots confirmed all fixes work

- [x] **BUG-01: Extraction data not showing from All Claims** (VERIFIED via API)
  - Backend now auto-detects latest run when accessing documents without run_id
  - Modified: `src/context_builder/api/services/documents.py` - added `_find_latest_run_with_extraction()` method
  - API test: `GET /api/docs/{id}?claim_id=X` returns extraction with 4 fields

- [x] **BUG-03: Ground truth save navigates away** (VERIFIED via code review)
  - Removed auto-advance behavior from Save button
  - Modified: `ui/src/components/DocumentReview.tsx` - handleSave now stays on current document (line 360 comment confirms)
  - No `setSelectedDocId` call after save

- [x] **BUG-04: Doc type scoreboard inaccurate** (VERIFIED via API)
  - Added missing doc types to SUPPORTED_DOC_TYPES list
  - Modified: `src/context_builder/api/insights.py` - added customer_comm, damage_evidence, medical_report
  - API test: `GET /api/insights/doc-types` includes damage_evidence

- [x] **BUG-09: View Documents button** (VERIFIED via Playwright screenshot)
  - `handleViewDocuments()` navigates to `/batches?run_id={batchId}`
  - Screenshot shows green "View Documents" button in expanded batch

- [x] **BUG-10: Export Summary button** (VERIFIED via Playwright screenshot)
  - `handleExportSummary()` downloads batch summary as JSON
  - Screenshot shows "Export Summary" button in expanded batch

- [x] **BUG-14: Audit log dropdown** (VERIFIED via Playwright screenshot)
  - `auditFilter` state with "All actions", "Runs", "Configs" options
  - Screenshot shows dropdown in Config tab
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
