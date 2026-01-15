# Compliance Acceptance Checklist and Gap-Closing Plan

Date: 2026-01-14
Owner: TBD
Status: Draft
Scope: Audit-grade decision ledger and evidence trail for AI-assisted claims workflows.

This document translates `scratch/DELTAILED_COMPLIANCE.md` into acceptance criteria and a phased plan. Each requirement has a "Done" definition with objective evidence. Use this as a PRD-style checklist for audit readiness.

---

## A. Audit-First Minimum (Must-Have for external audit)

### A1. Append-only, tamper-evident decision ledger
- Done when:
  - All decision records are written to an append-only log (no in-place edits).
  - Each record includes `record_hash` and `previous_hash` with verified chain integrity.
  - Integrity verification endpoint returns valid for all records.
- Evidence:
  - Automated integrity tests (unit + integration).
  - `GET /api/compliance/ledger/verify` returns `{valid: true}`.

### A2. Version pinning for model/prompt/rules/config
- Done when:
  - Every decision record includes `version_bundle_id`.
  - Each bundle captures git commit, dirty flag, model name+version, prompt template hash, extraction spec hash.
  - Bundle is immutable once created (stored under run ID, not overwritten).
- Evidence:
  - Decision record samples show `version_bundle_id`.
  - `GET /api/compliance/version-bundles/{run_id}` returns full bundle.

### A3. Evidence provenance + retrieval context capture
- Done when:
  - Decision records include evidence citations (doc_id, page, offsets, quote) for all AI-derived outputs.
  - LLM calls record retrieved context used (RAG docs/snippets) and tool calls/outputs.
  - Evidence references are immutable and refer to a versioned artifact.
- Evidence:
  - Decision records show citations and RAG context fields.
  - LLM call logs link to decision IDs and include retrieval context metadata.

### A4. Human override capture with accountability
- Done when:
  - Human review and overrides are logged as decision records with actor identity and role.
  - Override records contain reason code + notes + evidence relied on + policy/rule reference if applicable.
- Evidence:
  - Sample overrides show all required fields populated.

### A5. Replay / reconstruction mechanism
- Done when:
  - System can reconstruct "what would it have done then" for a decision using stored artifacts.
  - Replay uses the exact versions + evidence as of decision time.
- Evidence:
  - Documented replay flow with reproducibility tests.

### A6. Exportable evidence packs + queryability
- Done when:
  - One-click or API export returns JSON/CSV/PDF pack including decision trace, evidence refs, versions, and human actions.
  - Query API supports filters by claim, time range, decision type, version bundle.
- Evidence:
  - Export endpoint documented and tested.

---

## B. Full Requirement Checklist (Acceptance Criteria)

Each item maps to `scratch/DELTAILED_COMPLIANCE.md`.

### 1. Capture requirements

1) Universal decision coverage (MUST)
- Done when: all materially relevant automated steps create decision records. Coverage includes classification, extraction, quality gates, fraud flags, routing, approvals, payouts, denials, and customer-facing outputs.
- Evidence: coverage matrix + integration tests verifying records for each step.

2) Standard decision record schema (MUST)
- Done when: all decision records conform to a single schema versioned by `schema_version` and validated at write time.
- Evidence: schema validation tests for all decision types.

3) Inputs + evidence pointers (MUST)
- Done when: for every decision, all inputs and evidence are stored or referenced immutably, including documents, images, notes, policy terms, external data.
- Evidence: decision records contain references to versioned inputs (hash + storage path + ingest time).

4) Output completeness (MUST)
- Done when: decision record contains final outcome, key sub-decisions, confidence/uncertainty, and rationale artifacts.
- Evidence: schema fields populated in sample records.

5) Context capture for AI components (MUST)
- Done when: each LLM/ML-influenced decision logs model id/provider/region, params, prompts, retrieved context, tool calls, tool outputs.
- Evidence: LLM call logs include full request+response metadata and context linkage to decision_id.

### 2. Reproducibility and replay

6) Replayable decision reconstruction (MUST)
- Done when: system can re-execute or replay frozen artifacts to reproduce past decisions with audit log.
- Evidence: replay report for a sample decision including version bundle and evidence.

7) Time semantics (MUST)
- Done when: decision records contain event_time, decision_time, and effective_time (policy/rule effective date).
- Evidence: fields present and validated.

8) Version pinning for everything (MUST)
- Done when: decision records link to immutable versions for rules, policies, feature extraction logic, model version, prompt version, knowledge base snapshot, config bundles.
- Evidence: version bundle schema expanded and populated.

9) Change impact traceability (SHOULD)
- Done when: system supports queries like "which claims would change if rule X updated".
- Evidence: impact analysis job or query endpoint exists.

### 3. Integrity and non-repudiation

10) Append-only semantics (MUST)
- Done when: storage layer disallows updates/deletes; only new records are appended.
- Evidence: storage interface, tests, and code audit.

11) Tamper evidence (MUST)
- Done when: cryptographic hash chain + optional signatures are verified; auditors can detect edits.
- Evidence: integrity verification report and signature validation (if implemented).

12) Chain-of-custody for evidence (MUST)
- Done when: artifact origin, ingest time, checksums, transformations, and access are recorded.
- Evidence: evidence metadata log attached to decision.

13) Idempotency and deduplication (MUST)
- Done when: duplicate events do not create duplicate decision entries for same event id.
- Evidence: idempotency keys and tests.

### 4. Human oversight

14) Human actions are first-class ledger events (MUST)
- Done when: approvals/denials, overrides, manual edits, escalations, exceptions each create ledger records.
- Evidence: UI actions create records; backend tests.

15) Override accountability (MUST)
- Done when: override record contains actor id, role, reason code, notes, evidence relied on, policy/rule refs.
- Evidence: schema fields and API validation.

16) Decision responsibility model (SHOULD)
- Done when: decision types map to accountable teams/roles (3 lines of defense).
- Evidence: configuration with mapping and audit log references.

### 5. Explainability

17) Traceable rationale (MUST)
- Done when: rule traces, evidence citations, and policy clause linkage present for decisions.
- Evidence: rationale fields populated and tested.

18) Audience-specific views (SHOULD)
- Done when: same record can render audit view, adjuster view, customer view.
- Evidence: API provides view transformations with redaction rules.

### 6. Privacy, data protection, data subject rights

19) Data minimization (MUST)
- Done when: only required fields stored; sensitive content referenced/redacted.
- Evidence: data classification rules and redaction tests.

20) PII separation strategy (MUST)
- Done when: PII stored in separate vault, ledger stores only refs.
- Evidence: PII vault implementation with ref ids.

21) Encryption everywhere (MUST)
- Done when: TLS in transit, strong encryption at rest, KMS/HSM backed keys.
- Evidence: config + deployment checks.

22) Retention + legal hold (MUST)
- Done when: retention policies by jurisdiction/LOB with legal hold override.
- Evidence: retention policy config + enforcement jobs.

23) Right-to-erasure without breaking integrity (MUST)
- Done when: cryptographic erasure or redaction tokens remove PII without breaking hash chain.
- Evidence: erasure workflow tests.

### 7. Access control and audit of auditors

24) Least-privilege access control (MUST)
- Done when: RBAC/ABAC enforced for ledger, evidence, PII, exports.
- Evidence: API auth tests with role matrices.

25) Access logging (MUST)
- Done when: every access to ledger/evidence is logged as an audit entry.
- Evidence: access log records generated for read events.

26) Segregation of duties (SHOULD)
- Done when: users who can change logic cannot edit/audit the ledger.
- Evidence: role policy enforcement.

### 8. Operational resilience and security

27) High availability + durability (MUST)
- Done when: storage is multi-zone durable with backups and tested restores.
- Evidence: DR playbook + restore test evidence.

28) Disaster recovery objectives (SHOULD)
- Done when: RPO/RTO targets defined and tested.
- Evidence: DR test reports.

29) Incident readiness (MUST)
- Done when: anomaly detection, blast radius analysis, and export of incident evidence exists.
- Evidence: incident workflow docs + sample export.

### 9. Interoperability and audit export

30) Queryability at scale (MUST)
- Done when: query APIs support common audit filters efficiently.
- Evidence: query benchmarks or indexes.

31) Exportable evidence packs (MUST)
- Done when: export endpoint outputs JSON/CSV/PDF pack with decision trace + evidence + versions + human actions.
- Evidence: export samples.

32) API-first integration (SHOULD)
- Done when: all ledger features available via API, not UI-only.
- Evidence: API documentation.

### 10. Governance requirements

33) Control mapping (SHOULD)
- Done when: ledger features map to compliance frameworks (AI Act, GDPR decisioning, etc.).
- Evidence: control-mapping table.

34) Policy-as-data lifecycle (MUST)
- Done when: policy artifacts are versioned, approved, rollbackable, and linked to decisions.
- Evidence: policy version log and linkage.

35) Testing evidence linkage (SHOULD)
- Done when: tests/evals are linked to deployed versions with pass/fail thresholds.
- Evidence: evaluation artifacts stored and referenced by version bundles.

---

## C. Gap-Closing Plan (Phased)

### Phase 0 - Safety and access control (Critical)
- Enforce auth on all compliance endpoints.
- Add access logging for ledger and evidence reads.
- Add redaction guardrails to prevent base64 images/PII in LLM logs.

### Phase 1 - Decision record completeness
- Populate evidence citations, input hashes, and metadata in decision records.
- Attach `version_bundle_id` to every decision record.
- Store model parameters (temp, top_p, max_tokens) and prompt ids in decision or LLM call record.

### Phase 2 - PII separation and erasure
- Implement PII vault and store PII references in decision records.
- Add redaction pipeline before LLM call logging.
- Add erasure workflow with cryptographic erasure for PII blobs.

### Phase 3 - Replay and provenance
- Add replay module: reconstruct decision with frozen artifacts.
- Add chain-of-custody metadata (source, ingest, transformations, checksums).

### Phase 4 - Export and governance
- Add export endpoint to build evidence packs.
- Add control-mapping documentation.
- Add testing evidence linkage to version bundles.

---

## D. Evidence Template (for auditors)

For each release, attach:
- Ledger integrity report (hash chain valid).
- Sample decision record with evidence citations + version bundle.
- LLM call log sample showing prompt + response + context.
- Access log sample for decision/evidence read.
- Retention policy config and last enforcement report.
- Erasure workflow run log.
- Export pack sample.

---

## E. Acceptance Signoff

- Product: __________________ Date: __________
- Engineering: ______________ Date: __________
- Security: _________________ Date: __________
- Compliance/Legal: _________ Date: __________
