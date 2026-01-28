# Backlog

> Single source of truth for all tasks. Update before clearing context.
> Video review analysis: `data/Videos/VIDEO_ANALYSIS.md`

---

## Doing

_Currently active work. Add handoff notes inline._

### 2026-01-26 - Claim-Level Runs Architecture (Pending Decision)

**Status**: Architecture designed, awaiting confirmation before implementation.

**Context**: During reconciliation implementation, identified fundamental gap:
- Extraction has runs (versioned), claim-level stages don't
- Missing per-field provenance (which extraction run produced each fact)
- Reconciliation can span multiple extraction runs

**Proposed Solution**:
- Level 1: Add `extraction_run_id` to FactProvenance (per-field traceability)
- Level 2: Introduce `claim_runs/` structure (versioned claim-level processing)

**Estimated Effort**: ~22 hours for full implementation

**Documents**:
- `docs/CLAIM_LEVEL_RUNS_DESIGN.md` - Architecture design and decision matrix
- `docs/HANDOFF_CLAIM_RUNS.md` - Implementation scope and file changes

**Next Steps**:
1. User confirms architecture
2. Create detailed implementation plan
3. Implement in phases

---

### 2026-01-26 - Reconciliation Implementation ✅ COMPLETE

**Status**: All 5 phases complete.

**Completed**:
- Phase 1: ReconciliationService with conflict detection, gate evaluation
- Phase 2: CLI `reconcile` command with dry-run support
- Phase 3: API endpoints (`POST /claims/{id}/reconcile`, `GET /claims/{id}/reconciliation-report`)
- Phase 4: Run-level aggregation (`reconcile-eval` CLI command)
- Phase 5: UI components (Reconciliation tab on Evaluation page)

**Note**: This implementation will be enhanced by Claim-Level Runs architecture (above).

**Handoff**: See `docs/HANDOFF_RECONCILIATION.md` for full details.

---

### 2025-01-25 - Backend Refactoring Week 2 ✅ COMPLETE

**Status**: Router extraction complete. main.py reduced from 2723 to 160 lines.

**Completed**:
- Created 14 router files in `api/routers/`
- Extracted all endpoints from main.py
- Fixed test imports to use dependencies.py
- All 1049 tests passing (2 pre-existing failures)

**Router Files Created**:
- `claims.py`, `documents.py`, `insights.py`, `evolution.py`
- `classification.py`, `upload.py`, `pipeline.py`, `compliance.py`
- (Plus 4 from Week 1: `system.py`, `auth.py`, `admin_users.py`, `admin_workspaces.py`)

**Handoff**: See `docs/REFACTORING_HANDOFF.md` for full details.

**Next Steps**: Optional service layer refactoring or storage cleanup.

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

### P2 - Reconciliation & Pipeline Improvements

- [ ] **FEAT-39: Cross-run reconciliation (best-per-doc policy)**
  - Currently reconciliation only uses the latest extraction run
  - Need: Aggregate across ALL extraction runs, picking most recent extraction per document
  - Use case: Retry failed docs in a new run without re-running entire batch
  - Industry standard for compliance: Immutable runs + smart reconciliation
  - CLI flag exists: `--policy best-per-doc` (returns "not yet implemented")
  - Implementation scope:
    1. Scan all extraction runs for the claim
    2. For each document, pick the most recent extraction
    3. Aggregate facts from best version of each document
    4. Track which run each fact came from (audit provenance)
  - See: `docs/CLAIM_LEVEL_RUNS_DESIGN.md` for architecture context

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

### Code Review - Backend (2026-01-18)

#### Critical Security

- [ ] **SEC-01: Upgrade password hashing to bcrypt**
  - Current: SHA-256 with fixed salt (users.py:66-74)
  - Fix: Use bcrypt/argon2 with per-user random salts
  - Effort: Low

- [ ] **SEC-02: Remove/randomize default credentials**
  - Current: Default users with password "su" (users.py:81-103)
  - Fix: Generate random passwords or require setup wizard
  - Effort: Low

- [ ] **SEC-03: Encrypt or hash session tokens**
  - Current: Plaintext tokens in sessions.json (auth.py:64-76)
  - Fix: Store hashed tokens or use encrypted storage
  - Effort: Medium

#### Medium Security

- [ ] **SEC-04: Add login rate limiting**
  - Current: No protection against brute force (main.py:798-815)
  - Fix: Add rate limiting middleware or account lockout
  - Effort: Low

- [ ] **SEC-05: Validate file magic bytes on upload**
  - Current: Relies on Content-Type header (upload.py:164-170)
  - Fix: Use python-magic to check actual file type
  - Effort: Low

#### Code Quality

- [ ] **REFACTOR-01: Split main.py into route modules**
  - Current: 1000+ lines with all endpoints
  - Fix: Create routes/claims.py, routes/auth.py, etc.
  - Effort: Medium

- [ ] **REFACTOR-02: Add stricter typing for DI**
  - Current: Some `Any` types for injected deps (run.py:958)
  - Fix: Define Protocols for classifier, extractor, etc.
  - Effort: Medium

#### Performance

- [ ] **PERF-01: Auto-rebuild stale indexes**
  - Current: Manual index rebuild required
  - Fix: Auto-rebuild on startup or first query if stale
  - Effort: Medium

- [ ] **PERF-02: Async file I/O for hot paths**
  - Current: Sync file reads in auth.py, users.py
  - Fix: Use aiofiles or thread pool
  - Effort: Medium

### Code Review - Frontend (2026-01-18)

#### Critical

- [ ] **FE-SEC-01: Add Error Boundaries**
  - Current: No error boundaries - uncaught errors crash app
  - Fix: Add ErrorBoundary at App level and major pages
  - Effort: Low

- [ ] **FE-SEC-02: Consider sessionStorage for tokens**
  - Current: localStorage persists indefinitely (AuthContext.tsx:127)
  - Fix: Use sessionStorage or add client-side expiry check
  - Effort: Low

#### Medium

- [ ] **FE-SEC-03: Remove or secure switchUser**
  - Current: Allows role change without re-auth (AuthContext.tsx:154-157)
  - Fix: Remove feature or require re-authentication
  - Effort: Low

- [ ] **FE-PERF-01: Add WebSocket reconnect backoff**
  - Current: Fixed 3s reconnect loop (usePipelineWebSocket.ts:171)
  - Fix: Exponential backoff with max retries
  - Effort: Low

- [ ] **FE-PERF-02: Add request debouncing**
  - Current: No debounce on run selection changes
  - Fix: Debounce user-triggered API calls
  - Effort: Low

#### Code Quality

- [ ] **FE-REFACTOR-01: Split large components**
  - PipelineControlCenter.tsx (46KB), DocumentReview.tsx (34KB)
  - Extract table rows, form sections, custom hooks
  - Effort: Medium

- [ ] **FE-REFACTOR-02: Centralize API types**
  - Current: Types duplicated in client.ts and types/index.ts
  - Fix: Move all types to types/index.ts
  - Effort: Low

#### Accessibility

- [ ] **FE-A11Y-01: Add ARIA labels to icon buttons**
  - Current: Icon-only buttons lack accessible names
  - Fix: Add aria-label or sr-only spans
  - Effort: Low

- [ ] **FE-A11Y-02: Add skip links**
  - Current: No "skip to main content" for keyboard users
  - Effort: Low

- [ ] **FE-A11Y-03: Audit color contrast**
  - Current: Some badge colors may not meet WCAG AA
  - Effort: Medium

---

## Done (Recent)

_Cleared 2026-01-17. See git history for details._

### 2026-01-18 - P1 UI Polish

- [x] **FEAT-29: Confidence tooltips** - Added HelpIcon with classification confidence explanation
- [x] **FEAT-30: Show extractor type** - ExtractorBadge component shows Azure DI/Vision/Text
- [x] **FEAT-31: JSON tab for small outputs** - Added JsonViewer with syntax highlighting (prism-react-renderer)
- [x] **FEAT-32: Remove GPT-4 label** - Removed model label from BatchContextBar
- [x] **FEAT-33: Consistent header** - Added theme/user menu controls to BatchContextBar
- [x] **FEAT-34: Remove redundant status line** - Removed HealthSummaryBanner from ExtractionPage
- [x] **FEAT-36: Enterprise batch names** - Uses run_id directly instead of fun names
- [x] **BUG-07: Missing extraction = red** - Empty extraction with ground truth shows Incorrect (red)
- [x] **HelpTerm tooltips** - Added terminology.ts with 45+ term definitions

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
