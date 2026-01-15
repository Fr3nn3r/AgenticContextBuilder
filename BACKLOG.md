# Backlog

> Single source of truth for all tasks. Update before clearing context.

---

## Doing

_Currently active work. Add handoff notes inline._

(empty)

---

## Todo

### Compliance - High Priority

- [ ] **LLM call linking**
  - Update AuditedOpenAIClient to retain call_id
  - Record `llm_call_ids` list in DecisionRationale

### Infrastructure

- [ ] **Fix hardcoded paths** (remaining)
  - See: `plans/20260114-Fix-Hardcoded-Paths.md`
  - Labels path fixed (2026-01-15), check for others

---

## Done (Recent)

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
