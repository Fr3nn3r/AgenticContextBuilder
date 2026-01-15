# Compliance Adoption Plan (No New Dev)

Date: 2026-01-14
Status: Draft
Scope: Use existing code paths and configuration to capture decisions and LLM logs without adding new features.

This plan focuses on enabling and verifying current compliance features already present in the codebase. It does NOT include new schema changes, redaction/vault work, or endpoint changes.

---

## Goals (No New Dev)
- Turn on existing decision ledger + LLM audit logging.
- Ensure version bundles are created per run.
- Use existing API endpoints for verification and retrieval.
- Establish operational guardrails without code changes.

---

## Phase 1 — Configuration (Enable Existing Features)

1) Select compliance backend via env vars
- Set at startup:
  - `COMPLIANCE_BACKEND_TYPE=encrypted_file` (recommended) or `file`
  - `COMPLIANCE_ENCRYPTION_KEY_PATH=<path to 32-byte key>` (required for encrypted_file)
  - `COMPLIANCE_STORAGE_DIR=<workspace>/logs`
- Outcome: decision ledger + LLM call logs are written to workspace logs.

2) Ensure pipeline uses existing logging code paths
- Use default OpenAI classifier and Generic extractor.
- Ensure ingestion for images uses OpenAI Vision (logs LLM calls).
- Outcome: classification + extraction decisions are logged; LLM calls are logged.

Deliverables:
- `logs/decisions.jsonl` (or `decisions.enc.jsonl`)
- `logs/llm_calls.jsonl` (or `llm_calls.enc.jsonl`)
- `output/version_bundles/<run_id>/bundle.json`

---

## Phase 2 — Verification (No Code Changes)

3) Verify ledger integrity via API
- Call `GET /api/compliance/ledger/verify` and confirm `valid: true`.

4) Verify decisions exist
- Call `GET /api/compliance/ledger/decisions?decision_type=classification`
- Call `GET /api/compliance/ledger/decisions?decision_type=extraction`
- Confirm records exist for recent runs.

5) Verify version bundles exist
- Call `GET /api/compliance/version-bundles`
- Call `GET /api/compliance/version-bundles/{run_id}`

6) Verify label/truth histories (if human review used)
- `GET /api/compliance/label-history/{doc_id}`
- `GET /api/compliance/truth-history/{file_md5}`

Deliverables:
- API screenshots or curl logs proving data is present and integrity checks pass.

---

## Phase 3 — Operational Guardrails (No Code Changes)

7) Restrict access to compliance data
- Treat `/api/compliance/*` endpoints as internal-only at the network layer.
- Restrict filesystem access to `logs/`, `output/registry/`, `output/version_bundles/`.

8) Backups
- Back up `logs/` and `output/registry/` and `output/version_bundles/` on a schedule.

9) Documentation
- Record the environment variables and storage paths used for compliance logging.
- Record the encryption key management location and process (if encrypted backend used).

---

## Acceptance Checklist (No New Dev)

- [ ] Decision ledger file created and appended during pipeline runs.
- [ ] LLM call logs created during classification/extraction/vision ingestion.
- [ ] `GET /api/compliance/ledger/verify` returns valid.
- [ ] Version bundles created per run and retrievable via API.
- [ ] Label history and truth history endpoints return data when human review occurs.
- [ ] Ops controls: filesystem ACLs + backup policy in place.

---

## Known Limitations (Explicitly Accepted)

These are NOT addressed without new development:
- Decision records do not include `version_bundle_id` linkage.
- Evidence citations and RAG context are not stored in decision records.
- PII separation and redaction are not implemented (PII vault is stub).
- Compliance endpoints are not protected by auth in code.

---

## Suggested Evidence Pack (Operational)

For each release, collect:
- Ledger verify output (JSON).
- Sample decision records for classification + extraction.
- Sample LLM call log record.
- Version bundle JSON for a run.
- Backup and access control evidence (ops documentation).
