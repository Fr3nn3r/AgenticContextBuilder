# Backlog

> Single source of truth for all tasks. Update before clearing context.

---

## Doing

_Currently active work. Add handoff notes inline._

<!-- Example:
- [ ] **Task name** @window-id
  - Working on: src/path/file.py
  - Handoff: Finished X, next step is Y
-->

---

## Todo

### Compliance - High Priority

- [ ] **Compliance API corrections** (Phase 0)
  - Fix endpoint response fields to match DecisionRecord schema
  - Add tests for `/api/compliance/ledger/decisions` and `/verify`
  - See: `tasks/0_todo/compliance-adoption-plan.md` for details

- [ ] **LLM call linking**
  - Update AuditedOpenAIClient to retain call_id
  - Record `llm_call_ids` list in DecisionRationale

- [ ] **Version bundle propagation**
  - Add version_bundle_id to all decision types
  - Pass through classifier/extractor context

### Compliance - PII & Security

- [ ] **PII vault implementation**
  - File-based storage: `output/pii_vault/{ref_id}.json`
  - Redact PII in decision records and audit logs

### Compliance - UI Demo

- [ ] **Compliance dashboard** (exec view)
  - Hash chain integrity status, ledger volume, version bundle coverage
  - Summary cards with status indicators

- [ ] **Decision ledger explorer** (auditor view)
  - Filterable list by decision_type, claim_id, time range
  - Drilldown to decision detail

- [ ] **Integrity verification center**
  - Run/display hash chain verification
  - Verification history timeline

### Infrastructure

- [ ] **Fix hardcoded paths**
  - See: `plans/20260114-Fix-Hardcoded-Paths.md`

---

## Done (Recent)

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
