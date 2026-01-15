# Backlog

> Single source of truth for all tasks. Update before clearing context.

---

## Doing

_Currently active work. Add handoff notes inline._

(empty)

---

## Todo

### Batches Overview UI Improvements - High Priority

> Improve visibility and layout of the batches overview screen (`ExtractionPage.tsx`)

- [ ] **1. Remove redundant batch header card**
  - Delete the "Batch Context Header" card (lines 102-159 in ExtractionPage.tsx)
  - Info already exists in top BatchContextBar
  - Frees vertical space for more important content
  - Files: `ui/src/components/ExtractionPage.tsx`

- [ ] **2. Make Batch History sidebar collapsible**
  - Add collapse/expand toggle button to sidebar header
  - Persist collapsed state in localStorage
  - When collapsed, show only icons or mini indicators
  - Consider: remove sidebar entirely if batch selector dropdown suffices
  - Files: `ui/src/components/ExtractionPage.tsx`

- [ ] **3. Add health indicators to phase cards**
  - Add colored top border based on phase health (green/amber/red)
  - Highlight "Failed" rows with background color when > 0
  - Make all cards same height (scrollable distribution in Classification)
  - Add mini health icon in card header
  - Files: `ui/src/components/ExtractionPage.tsx` (PhaseCard component)

- [ ] **4. Emphasize Quality Gate evidence rate**
  - Make evidence rate more prominent (larger font, gauge, or badge)
  - Color code: red when 0%, amber when <50%, green when >80%
  - Consider dedicated "Health Score" summary component
  - Files: `ui/src/components/ExtractionPage.tsx`

- [ ] **5. Improve Coverage section visual communication**
  - Add icon/badge when coverage is 0% ("Needs Review")
  - Add call-to-action link: "0 docs reviewed - Start labeling →"
  - Color text red when coverage below threshold (e.g., <25%)
  - Files: `ui/src/components/ExtractionPage.tsx` (ProgressBar component)

- [ ] **6. Enhance Doc Type Scoreboard scanability**
  - Replace "—" with "No data" or informative tooltip
  - Add color coding to Presence/Evidence columns (green >80%, amber 50-80%, red <50%)
  - Sort by "needs attention" (lowest scores first) by default
  - Files: `ui/src/components/ExtractionPage.tsx`

- [ ] **7. Add summary health banner at top**
  - New component showing at-a-glance batch health
  - Format: `✓ 4/4 ingested | ✓ 4/4 classified | ⚠ 3/4 extracted | ✓ 4 pass`
  - Or single "Batch Health: 85%" score
  - Place above phase cards
  - Files: `ui/src/components/ExtractionPage.tsx`, new `BatchHealthBanner.tsx`

- [ ] **8. Add counts to tab navigation**
  - Update BatchSubNav tabs to show counts: Documents (4), Claims (1), etc.
  - Pass counts from parent via props or context
  - Files: `ui/src/components/shared/BatchSubNav.tsx`, `ui/src/components/BatchWorkspace.tsx`

- [ ] **9. Add empty state guidance**
  - When evidence rate is 0%, show: "No documents labeled yet. Label documents to see accuracy metrics."
  - Contextual help for other zero-value states
  - Files: `ui/src/components/ExtractionPage.tsx`

- [ ] **10. Show relative time**
  - Change absolute timestamps to relative: "2 hours ago"
  - Show absolute time on hover (tooltip)
  - Create reusable `RelativeTime` component
  - Files: new `ui/src/components/shared/RelativeTime.tsx`, update `ExtractionPage.tsx`

### Compliance - High Priority

(empty)

### Infrastructure

- [ ] **Fix hardcoded paths** (remaining)
  - See: `plans/20260114-Fix-Hardcoded-Paths.md`
  - Labels path fixed (2026-01-15), check for others

---

## Done (Recent)

- [x] **LLM call linking for compliance** (2026-01-15)
  - Added `get_call_id()` to AuditedOpenAIClient (retains call_id after success)
  - Changed `DecisionRationale.llm_call_id` → `llm_call_ids: List[str]`
  - Updated factories, classifier, and extractor to use new field
  - Files: `llm_audit.py`, `decision_record.py`, `factories.py`, `openai_classifier.py`, `generic.py`

- [x] **App.tsx refactoring - extract contexts** (2026-01-15)
  - Phase 1: FilterContext - filter state (searchQuery, lobFilter, etc.)
  - Phase 2: BatchContext - batch/run state, dashboard data, API loading
  - Phase 3: ClaimsContext - claims, docs, filtering logic
  - Phase 4: AppRoutes - extracted route definitions
  - Phase 5: ClaimsTable - 17 props → 1 prop via context hooks
  - App.tsx: 583 → 127 lines (78% reduction)
  - New files: `context/FilterContext.tsx`, `BatchContext.tsx`, `ClaimsContext.tsx`, `AppRoutes.tsx`

- [x] **Compliance UI suite** (2026-01-14)
  - Dashboard: `ui/src/pages/compliance/Overview.tsx`
  - Ledger explorer: `Ledger.tsx` with filters (type, claim, doc)
  - Verification center: `Verification.tsx` with hash chain checks
  - Version bundles: `VersionBundles.tsx`

- [x] **PII vault implementation** (2026-01-14)
  - Encrypted vault storage: `services/compliance/pii/vault_storage.py`
  - Per-vault KEK for crypto-shredding
  - Config loader and tokenizer

- [x] **Version bundle propagation** (2026-01-14)
  - `version_bundle_id` in DecisionRecord schema
  - Propagated through pipeline/run.py and factories

- [x] **Refactor labels to global registry storage** (2026-01-15)
  - Labels now stored at `registry/labels/{doc_id}.json` instead of per-claim
  - Fixed 6 hardcoded path locations in api/services and pipeline/metrics
  - Migration script: `scripts/migrate_labels_to_registry.py` (migrated 141 labels)
  - Commit: TBD

- [x] **Multi-window session management** (2026-01-15)
  - Added worktree scripts, session protocol
  - Commit: 8f3c66c

- [x] **Compliance storage implementation** (2026-01-14)
  - Decision ledger, LLM audit, version bundles
  - See: `tasks/2_done/compliance-storage-progress.md`

- [x] **Compliance demo UI with RBAC** (2026-01-14)
  - Role-based access control for compliance pages
  - Commit: 238e0d5

- [x] **Workspace config CLI integration** (2026-01-14)
  - Compliance logging via workspace config
  - Commit: 9cb7c8f

---

## Reference

Detailed docs available in `.claude/docs/`:
- `architecture.md` - Pipeline flow, components, data structures
- `compliance.md` - Compliance dev instructions, decision logging
- `testing.md` - Test commands, organization, troubleshooting

---

## Handoff Template

```markdown
### [DATE] - [WINDOW]
**Done**: What was completed
**Files**: paths changed
**Next**: Immediate next step
```
