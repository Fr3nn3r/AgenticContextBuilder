# Compliance Adoption Plan (Pragmatic, JSONL + PII Vault)

## Goals
- Implement PII policy using vault references (no PII in decision ledger or LLM audit logs).
- Keep JSONL storage for now, harden append-only writes for concurrency.
- Improve audit traceability: decision ↔ LLM calls (multi-call) and version bundle linkage on every decision.
- Fix compliance API correctness and align with current schemas.

## Scope (In)
- Decision ledger, LLM audit, compliance API endpoints
- Classification, extraction, ingestion (vision), human review logging
- Version bundle propagation
- Minimal PII vault implementation + reference wiring

## Scope (Out)
- Centralized datastore migration
- Backfill/migration of existing logs (explicitly not required)

---

## Phase 0 — Baseline Corrections (Must-Have)
1. Fix compliance API endpoint correctness.
   - Align `DecisionLedger.query` usage in `api/main.py`.
   - Fix response fields to match `DecisionRecord` schema (`created_at`, `previous_hash`, enum values).
   - Add tests for `/api/compliance/ledger/decisions` and `/api/compliance/ledger/verify`.

2. Restore LLM call linking correctness.
   - Update `AuditedOpenAIClient` to retain last successful `call_id`.
   - Record `llm_call_ids` (list) in `DecisionRationale` while keeping `llm_call_id` for backward compatibility.
   - Ensure retries append to list (including failed attempts if desired).

3. Propagate version bundle ID into all decisions.
   - Add `version_bundle_id` to classification, extraction, human review, override decisions.
   - Pass `version_bundle_id` into classifier/extractor context and label services.

Deliverables:
- Working compliance endpoints
- Decision records with correct LLM linkage and version bundle references

---

## Phase 1 — PII Vault + Redaction (Must-Have)
4. Implement minimal PII vault storage.
   - File-based storage: `output/pii_vault/{ref_id}.json`.
   - Include `pii_type`, `stored_at`, `source_context`.
   - Add API access controls later; for now, keep server-side only.

5. Redact PII in decision records and LLM audit logs.
   - For decision outcomes: replace `fields_extracted` values and `truth_value` with PII refs.
   - For audit logs: sanitize image base64 in `openai_vision_ingestion` messages.
   - Add `pii_refs` to `DecisionRecord` where appropriate.

6. Adjust human review logging.
   - Ensure `actor_id` is a user ID (not email).
   - Store reviewer ID in metadata, not PII fields.

Deliverables:
- No raw PII in decision ledger or LLM logs
- Vault references recorded and resolvable

---

## Phase 2 — JSONL Hardening (Should-Have)
7. Make JSONL append operations concurrency-safe.
   - Add file locking for `decisions.jsonl` and `llm_calls.jsonl`.
   - Switch from read-rewrite to append-only writes with locking.

8. Add log rotation (optional).
   - Rotate by size/date if needed; keep an index for audit queries.

Deliverables:
- Append-only integrity in concurrent runs

---

## Phase 3 — Validation & QA (Should-Have)
9. Update and expand tests.
   - Decision ledger integrity tests for multi-call linking.
   - LLM audit tests for sanitized payloads (image redaction).
   - API tests for decision filters + pagination.

10. Add developer checklist updates.
   - Update `AGENTS.md` or repo docs with new compliance requirements.

---

## Detailed Work Items (File-Level)
- `src/context_builder/api/main.py`
  - Fix `/api/compliance/ledger/decisions` query and response mapping.
- `src/context_builder/services/llm_audit.py`
  - Track last successful `call_id`.
  - Add `llm_call_ids` support in decision rationale.
- `src/context_builder/schemas/decision_record.py`
  - Add `llm_call_ids: List[str]` with backward compatibility.
- `src/context_builder/classification/openai_classifier.py`
  - Pass `version_bundle_id` and audit context (claim/doc/run).
  - Link `llm_call_ids` into rationale.
- `src/context_builder/extraction/extractors/generic.py`
  - Add `version_bundle_id` to decisions.
  - Replace extracted values with PII refs (phase 1).
- `src/context_builder/impl/openai_vision_ingestion.py`
  - Strip/replace base64 data before audit logging.
- `src/context_builder/api/services/labels.py`
  - Remove raw `truth_value` from decision records; add PII refs.
- `src/context_builder/storage/pii_vault.py`
  - Implement minimal vault read/write.

---

## Open Questions (Decide Early)
- Should `llm_call_ids` include failed attempts or only successful calls?
- How to handle out-of-band human reviews (no run/version bundle)?
- What PII fields are in scope for redaction first (names, addresses, policy numbers)?

---

## Priority Summary
- P0: Fix compliance API + LLM linkage + version bundle propagation.
- P1: PII vault + redaction (decision ledger + LLM audit).
- P2: JSONL hardening (locking/append-only).
- P3: Tests + docs.
