# Compliance Implementation Progress

## Phase 1: Decision Ledger Schema & Hash Chain
- [x] Task 1.1: Create DecisionRecord Schema (`schemas/decision_record.py`)
- [x] Task 1.2: Create Decision Ledger Service (`services/decision_ledger.py`)
- [x] Task 1.3: Add Hash Chaining to Audit Service (`api/services/audit.py`)

## Phase 2: LLM Call Capture
- [x] Task 2.1: Create LLM Audit Service (`services/llm_audit.py`)
- [x] Task 2.2: Integrate Wrapper in Extraction (`extraction/extractors/generic.py`)
- [x] Task 2.3: Integrate Wrapper in Classification (`classification/openai_classifier.py`)
- [x] Task 2.4: Integrate Wrapper in Vision Ingestion (`impl/openai_vision_ingestion.py`)

## Phase 3: Decision Logging Integration
- [x] Task 3.1: Log Classification Decisions
- [x] Task 3.2: Log Extraction Decisions
- [x] Task 3.3: Log Human Review Decisions
- [x] Task 3.4: Log Classification Override Decisions

## Phase 4: Version Bundle Snapshots
- [x] Task 4.1: Create Version Bundle Storage (`storage/version_bundles.py`)
- [x] Task 4.2: Integrate Version Bundle in Pipeline (`pipeline/run.py`)
- [x] Task 4.3: Link Version Bundle to Decisions (via ExtractionRunMetadata)

## Phase 5: Append-Only Storage Patterns
- [x] Task 5.1: Version Truth Store (`storage/truth_store.py`) - history.jsonl
- [x] Task 5.2: Version Config History (`api/services/prompt_config.py`) - history.jsonl
- [x] Task 5.3: Version Label History (`storage/filesystem.py`) - history.jsonl

## Phase 6: PII Separation Stubs
- [x] Task 6.1: Add PII Reference Fields to Schemas (in decision_record.py)
- [x] Task 6.2: Create PII Vault Stub (`storage/pii_vault.py`)

## Verification & Testing
- [x] Task V.1: Unit Tests for Hash Chain (`tests/unit/test_decision_ledger.py`)
- [x] Task V.2: Unit Tests for LLM Audit (`tests/unit/test_llm_audit.py`)
- [x] Task V.3: Integration Test for Decision Flow (`tests/integration/test_compliance_decision_flow.py`)
- [x] Task V.4: Verification Endpoints (`api/main.py` - /api/compliance/* endpoints)

---
Last updated: 2026-01-14

## Summary

### All Phases Complete ✅

**Phase 1-3: Core Decision Logging**
- DecisionRecord schema with tamper-evident hash chain
- Decision Ledger service with append-only JSONL storage
- LLM Audit service capturing all OpenAI API calls
- Decision logging for classification, extraction, human review, and overrides

**Phase 4: Version Bundle Integration**
- Pipeline creates version bundle at run start
- Bundle ID linked to extraction run metadata
- Captures git commit, model version, template hashes for reproducibility

**Phase 5: Append-Only Storage**
- Truth Store: `history.jsonl` tracks all truth changes per file_md5
- Config History: `prompt_configs_history.jsonl` logs all config changes
- Label History: `history.jsonl` per document tracks all label changes
- All stores include version metadata (_version_metadata with saved_at, version_number)

**Phase 6: PII Separation (Stubs)**
- Schema fields for PII references
- PII Vault stub ready for future GDPR compliance implementation

**Verification & Testing**
- Unit tests for hash chain integrity
- Unit tests for LLM audit capture
- Integration tests for end-to-end decision flow
- API endpoints for compliance verification

### API Endpoints Added

| Endpoint | Purpose |
|----------|---------|
| `GET /api/compliance/ledger/verify` | Verify hash chain integrity |
| `GET /api/compliance/ledger/decisions` | List decision records with filters |
| `GET /api/compliance/version-bundles` | List all version bundles |
| `GET /api/compliance/version-bundles/{run_id}` | Get version bundle details |
| `GET /api/compliance/config-history` | Get config change history |
| `GET /api/compliance/truth-history/{file_md5}` | Get truth version history |
| `GET /api/compliance/label-history/{doc_id}` | Get label version history |

### Files Created/Modified

**New Files:**
- `src/context_builder/schemas/decision_record.py`
- `src/context_builder/services/__init__.py`
- `src/context_builder/services/decision_ledger.py`
- `src/context_builder/services/llm_audit.py`
- `src/context_builder/storage/version_bundles.py`
- `src/context_builder/storage/pii_vault.py`
- `tests/unit/test_decision_ledger.py`
- `tests/unit/test_llm_audit.py`
- `tests/integration/test_compliance_decision_flow.py`

**Modified Files:**
- `src/context_builder/api/main.py` - Added compliance verification endpoints
- `src/context_builder/api/services/audit.py` - Added hash chaining
- `src/context_builder/api/services/labels.py` - Human review + override decision logging
- `src/context_builder/api/services/prompt_config.py` - Config change history logging
- `src/context_builder/classification/openai_classifier.py` - LLM audit + decision logging
- `src/context_builder/extraction/extractors/generic.py` - LLM audit + decision logging
- `src/context_builder/impl/openai_vision_ingestion.py` - LLM audit
- `src/context_builder/pipeline/run.py` - Version bundle creation at run start
- `src/context_builder/schemas/extraction_result.py` - Added version_bundle_id field
- `src/context_builder/storage/filesystem.py` - Label version history
- `src/context_builder/storage/truth_store.py` - Truth version history

### Data Locations

| Data | Location | Format |
|------|----------|--------|
| Decision Ledger | `output/logs/decisions.jsonl` | Append-only JSONL with hash chain |
| LLM Call Log | `output/logs/llm_calls.jsonl` | Append-only JSONL |
| Version Bundles | `output/version_bundles/{run_id}/bundle.json` | JSON per run |
| Truth History | `output/registry/truth/{file_md5}/history.jsonl` | Append-only JSONL |
| Config History | `output/config/prompt_configs_history.jsonl` | Append-only JSONL |
| Label History | `output/claims/{claim}/docs/{doc}/labels/history.jsonl` | Append-only JSONL |

### Developer Documentation

See `plans/compliance-dev-instructions.md` for:
- How to use the compliance infrastructure
- Code review checklist for compliance
- Troubleshooting guide
