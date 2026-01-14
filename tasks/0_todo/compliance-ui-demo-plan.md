# Compliance UI Roadmap - Urgent Demo-First Plan

Context
- Source references: `scratch/DELTAILED_COMPLIANCE.md`, `plans/compliance-foundation-priorities.md`, `tasks/2_done/compliance-implementation.md`.
- Goal: prioritize UI features so demos clearly communicate compliance maturity.
- Constraint: use existing compliance APIs where possible; defer heavy backend unless required.

Most Urgent UI Features (ordered)
1) Compliance Dashboard (exec view)
   - At-a-glance status of: hash chain integrity, ledger volume, last decision time, version bundle coverage.
   - Summary cards for "Audit-First Minimum" (6 items) with status and links.

2) Decision Ledger Explorer (auditor view)
   - Filterable list: decision_type, claim_id, time range, actor_type, model_id, version_bundle_id.
   - Quick drilldown to Decision Detail.

3) Decision Detail + Evidence View
   - Display record, rationale, evidence refs, version bundle, LLM call linkage.
   - Separate tabs for: Rationale, Evidence, Versions, Human Actions.

4) Integrity & Verification Center
   - Run and display hash chain verification status (`/api/compliance/ledger/verify`).
   - Timeline of verification runs (store client-side initially).

5) Version Bundle Viewer
   - List bundles, detail page, compare two bundles (diff key fields).

6) Export & Evidence Pack UX
   - UI button to initiate export (even if stubbed initially) with clear "pack contents" checklist.
   - Show export history (local UI state) for demo.

7) Label/Truth History Viewer
   - For any doc/claim: show version history with diffs and human override markers.

8) Compliance Narrative + Control Mapping (buyer view)
   - UI page mapping system features to control frameworks (AI Act-like, GDPR decisioning, SOC2-ish).
   - Link to specific UI evidence screens.

Implementation Plan (UI first)

Phase A - Demo-Ready UI Skeleton (1-2 days)
- Add Compliance nav section in UI (sidebar).
- Create routes/pages:
  - `/compliance/overview`
  - `/compliance/ledger`
  - `/compliance/ledger/:decisionId`
  - `/compliance/verification`
  - `/compliance/version-bundles`
  - `/compliance/controls`
- Create shared layout + visual language (distinct from QA console).
- Build stub data adapters with feature flags so pages render even if API is empty.

Phase B - Wire to Existing APIs (2-3 days)
- Connect Overview cards to real endpoints:
  - `/api/compliance/ledger/verify`
  - `/api/compliance/ledger/decisions`
  - `/api/compliance/version-bundles`
  - `/api/compliance/config-history`
  - `/api/compliance/truth-history/{file_md5}`
  - `/api/compliance/label-history/{doc_id}`
- Add search/filter state synced to URL params.
- Add loading/empty/error states (demo-safe).

Phase C - Decision Detail UX (2-3 days)
- Build Decision Detail page with tabs:
  - Summary (decision_output, confidence, actor, timestamps)
  - Rationale (rule trace, explanation, citations)
  - Evidence (input refs, doc links, provenance)
  - Versions (version bundle details)
  - Human Actions (overrides, reviewer, reason)
- Implement data join helpers to display related LLM call records (if available).

Phase D - Integrity & Export UX (1-2 days)
- Verification Center: show hash chain status + last verified timestamp.
- Export UX: static evidence pack checklist + button (wire later to backend).
- Add PDF/JSON/CSV export placeholders with disabled state + tooltip.

Phase E - Control Mapping / Buyer Narrative (1 day)
- Compliance mapping page: map "Audit-First Minimum" to UI screens.
- Provide a one-page "What auditors can verify" narrative for demos.

Backend Gaps to Note (non-blocking for UI demos)
- Evidence pack export API (create when ready).
- Access logging UI (needs access log endpoint).
- PII vault UI (depends on full vault implementation).
- Change impact traceability UI (needs analysis jobs).

SOLID (pragmatic application in UI + services)
- Single Responsibility: keep data fetching in `useComplianceApi` hooks; UI components only render.
- Open/Closed: compliance cards and checklist items defined via config arrays.
- Liskov/Interface: use typed DTOs for records; allow mock adapters to implement same interface.
- Interface Segregation: split API client into small modules (ledger, bundles, verification, history).
- Dependency Inversion: pages depend on interfaces (adapters), not fetch directly.

Deliverables / Acceptance
- Demo flow can show: integrity verification, ledger list, decision detail, version bundles, and control mapping.
- All compliance pages render with empty datasets (no crashes).
- Filters work and are shareable via URL.
- Visuals communicate "audit-first" maturity.

Notes
- UI work should not change core logging semantics.
- Use existing endpoints for real data; if missing, keep UI stubbed with clear "coming soon" state.
