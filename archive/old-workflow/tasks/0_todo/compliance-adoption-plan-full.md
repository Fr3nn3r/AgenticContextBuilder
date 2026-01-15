# Compliance Adoption Plan (Full Scope + Required New Dev)

Date: 2026-01-14
Status: Draft
Scope: Implement full compliance requirements from `scratch/DELTAILED_COMPLIANCE.md`, including new development.

This plan extends the no-new-dev adoption checklist by adding the engineering work required to reach audit-grade compliance. It is organized by phases with concrete deliverables.

---

## Phase 0 — Enable Existing Features (Baseline)

0.1 Configure compliance storage backend
- Set env:
  - `COMPLIANCE_BACKEND_TYPE=encrypted_file` (recommended)
  - `COMPLIANCE_ENCRYPTION_KEY_PATH=<path to 32-byte key>`
  - `COMPLIANCE_STORAGE_DIR=<workspace>/logs`

0.2 Verify existing logging paths
- Ensure OpenAI classifier + Generic extractor are used.
- Confirm LLM calls are logged for classification/extraction/vision ingestion.

Deliverables:
- `logs/decisions.enc.jsonl`
- `logs/llm_calls.enc.jsonl`
- `output/version_bundles/<run_id>/bundle.json`

---

## Phase 1 — Decision Record Completeness (Must-Have)

1.1 Version bundle linkage
- Add `version_bundle_id` to all decision records (classification, extraction, human review, override).
- Propagate `version_bundle_id` through pipeline, classifier, extractor, and label services.

1.2 Decision schema standardization
- Add `schema_version` to `DecisionRecord` and enforce validation at append time.

1.3 Evidence and input references
- Populate `DecisionRationale.evidence_citations` from extraction provenance.
- Store input hashes and artifact references in decision metadata (file_md5, content_md5, doc version).

Deliverables:
- Decision records show version bundle id + evidence citations + input hashes.

---

## Phase 2 — LLM Audit Completeness (Must-Have)

2.1 Multi-call linkage
- Add `llm_call_ids: List[str]` to `DecisionRationale` (keep `llm_call_id` for backward compat).
- Update `AuditedOpenAIClient` to retain last successful call id and track retries.

2.2 RAG context + tool usage logging
- Extend `LLMCallRecord` to capture retrieved context snippets, tool calls, and tool outputs.
- Ensure ingestion/classification/extraction pass these into LLM log entries.

Deliverables:
- LLM audit log contains request/response, context, tool calls, and decision linkage.

---

## Phase 3 — PII Separation + Redaction (Must-Have)

3.1 Implement PII vault
- Implement file-based PII vault with encryption at rest.
- Store PII blobs under `output/pii_vault/` with `ref_id`.

3.2 Redact PII from logs
- Redact PII in decision outcomes and LLM call logs.
- Replace PII values with `PIIReference` records in decision ledger.

3.3 Right-to-erasure
- Implement cryptographic erasure: delete PII vault key or blob for a given ref_id.
- Preserve ledger integrity while severing PII links.

Deliverables:
- No raw PII in decision ledger or LLM logs; PII retrievable via vault.

---

## Phase 4 — Integrity and Chain-of-Custody (Must-Have)

4.1 Hash chain hardening
- Add file locks and true append mode (no read-rewrite) for JSONL.
- Add optional signing of records (service key) for non-repudiation.

4.2 Chain-of-custody metadata
- Record evidence origin, ingest time, transformations, checksums, and access.

Deliverables:
- Integrity verification passes under concurrency; chain-of-custody metadata recorded.

---

## Phase 5 — Access Control + Access Logging (Must-Have)

5.1 Protect compliance endpoints
- Require authentication + roles for `/api/compliance/*` and audit endpoints.
- Enforce least privilege (auditor vs admin vs reviewer).

5.2 Access logging
- Log every read of ledger/evidence to audit log (who, when, what).

Deliverables:
- Role-based access controls enforced and access logs exist.

---

## Phase 6 — Replayability + Export (Must-Have)

6.1 Replay tooling
- Implement replay module using stored version bundles + artifacts.
- Produce replay report for a decision id.

6.2 Exportable evidence packs
- Add export endpoint producing JSON/CSV/PDF packs with decision trace, evidence, versions, human actions.

Deliverables:
- One-click export + replay reports.

---

## Phase 7 — Governance and Ops (Should-Have)

7.1 Control mapping
- Map ledger features to frameworks (GDPR, AI Act, SOC2, etc.).

7.2 Retention + legal hold
- Implement retention policies by LOB/jurisdiction and legal hold override.

7.3 Incident readiness
- Add anomaly detection and incident export workflows.

Deliverables:
- Control matrix + retention config + incident evidence export.

---

## Dependencies / Open Questions

- PII scope: which fields require vaulting and redaction.
- RAG/tooling: which components provide retrieval context to log.
- Signing keys: where to store service signing keys (KMS/HSM vs file).
- Export formats: JSON only or JSON + PDF pack.

---

## Success Criteria

- Decision ledger is append-only, tamper-evident, and complete.
- Every decision is replayable with exact versions and evidence.
- LLM and evidence logs are PII-safe and access-controlled.
- Auditors can query and export full evidence packs.
