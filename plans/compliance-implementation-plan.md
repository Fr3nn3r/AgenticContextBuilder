# Compliance Foundation Implementation Plan

**Goal**: Implement the 6 foundational priorities to avoid future refactoring debt.

**Scope**: Schema + storage foundations only. Does NOT include UI screens, export features, or retention policies (those can be added later without architectural changes).

---

## Phase 1: Decision Ledger Schema & Hash Chain Infrastructure

**Objective**: Create the core schemas and append-only storage with tamper-evidence.

### Task 1.1: Create DecisionRecord Schema
**File**: `src/context_builder/schemas/decision_record.py`

Create Pydantic models:
- `VersionBundle` - captures all version info at decision time
- `DecisionRationale` - rule traces, evidence citations
- `EvidenceCitation` - link to source document/field
- `DecisionRecord` - main schema with all fields from analysis

**Acceptance criteria**:
- Schema validates with Pydantic
- Supports all decision types: `classification`, `extraction`, `quality_gate`, `human_review`, `override`
- Has `record_hash` and `previous_hash` fields for chain integrity

### Task 1.2: Create Decision Ledger Service
**File**: `src/context_builder/services/decision_ledger.py`

Implement:
- `DecisionLedger` class with append-only JSONL storage
- `append(record: DecisionRecord)` - adds hash chain, writes atomically
- `_compute_hash(record)` - SHA-256 of record (excluding hash fields)
- `_get_last_hash()` - reads last record's hash (or "GENESIS")
- `verify_integrity()` - walks chain, verifies all hashes
- `query(filters)` - basic filtering by decision_type, claim_id, time range

**Acceptance criteria**:
- Hash chain is correct (each record's `previous_hash` matches prior `record_hash`)
- `verify_integrity()` detects any tampering
- Atomic writes (temp file + rename pattern)

### Task 1.3: Add Hash Chaining to Existing Audit Service
**File**: `src/context_builder/api/services/audit.py`

Modify:
- Add `record_hash` and `previous_hash` to `AuditEntry` dataclass
- Update `log()` method to compute and include hashes
- Add `verify_chain_integrity()` method
- Add API endpoint `GET /api/pipeline/audit/verify` to return integrity status

**Acceptance criteria**:
- New audit entries have valid hash chain
- Verification endpoint returns `{valid: true/false, records: N, break_at: M}`

---

## Phase 2: LLM Call Capture

**Objective**: Wrap all LLM calls to capture prompts, responses, and context.

### Task 2.1: Create LLM Audit Service
**File**: `src/context_builder/services/llm_audit.py`

Create:
- `LLMCallRecord` dataclass with all fields from analysis
- `AuditedOpenAIClient` wrapper class
- `log_call(record)` - appends to `output/logs/llm_calls.jsonl`
- Helper to link call to decision_id

**Acceptance criteria**:
- Captures: model, temperature, max_tokens, messages, response, token_usage, latency
- Append-only storage
- Call records have unique `call_id`

### Task 2.2: Integrate Wrapper in Extraction
**File**: `src/context_builder/extraction/extractors/generic.py`

Modify `_llm_extract()`:
- Replace direct `self.client.chat.completions.create()` with audited wrapper
- Pass decision context (doc_id, claim_id, run_id) for linking

**Acceptance criteria**:
- Every extraction LLM call is logged
- Log includes full prompt and response

### Task 2.3: Integrate Wrapper in Classification
**File**: `src/context_builder/classification/openai_classifier.py`

Modify `_call_api_with_retry()`:
- Replace direct client call with audited wrapper
- Pass decision context for linking

**Acceptance criteria**:
- Every classification LLM call is logged
- Retries are logged as separate calls

### Task 2.4: Integrate Wrapper in Vision Ingestion
**File**: `src/context_builder/impl/openai_vision_ingestion.py`

Find and wrap any `client.chat.completions.create()` calls.

**Acceptance criteria**:
- Vision LLM calls are logged with image reference (not image data)

---

## Phase 3: Decision Logging Integration

**Objective**: Log decisions at each pipeline step.

### Task 3.1: Log Classification Decisions
**File**: `src/context_builder/classification/openai_classifier.py`

After `_classify_implementation()` returns:
- Create `DecisionRecord` with type `classification`
- Include: doc_id, classification result, confidence, LLM call_id, version_bundle
- Append to decision ledger

**Acceptance criteria**:
- Every classification produces a decision record
- Record links to LLM call via `call_id`

### Task 3.2: Log Extraction Decisions
**File**: `src/context_builder/extraction/extractors/generic.py`

After `extract()` returns:
- Create `DecisionRecord` with type `extraction`
- Include: doc_id, fields extracted, quality_gate result, LLM call_id
- Append to decision ledger

**Acceptance criteria**:
- Every extraction produces a decision record
- Each field has provenance in rationale

### Task 3.3: Log Human Review Decisions
**File**: `src/context_builder/api/services/labels.py`

After `save_labels()` succeeds:
- Create `DecisionRecord` with type `human_review`
- Include: doc_id, reviewer (as ref), field changes, override if any
- Append to decision ledger

**Acceptance criteria**:
- Every human label save creates a decision record
- If human corrected a field, record shows old vs new value

### Task 3.4: Log Classification Override Decisions
**File**: `src/context_builder/api/services/labels.py`

After `save_classification_label()` with `doc_type_correct=False`:
- Create `DecisionRecord` with type `override`
- Include: original classification, corrected doc_type, reviewer, reason

**Acceptance criteria**:
- Classification corrections are explicitly logged as overrides
- Links to original classification decision

---

## Phase 4: Version Bundle Snapshots

**Objective**: Capture complete version state at run start.

### Task 4.1: Create Version Bundle Storage
**File**: `src/context_builder/storage/version_bundles.py`

Create:
- `create_version_bundle(run_id)` - snapshots all versions
- `get_version_bundle(run_id)` - retrieves snapshot
- Storage in `output/version_bundles/{run_id}/`

Snapshot includes:
- `bundle.json` - version IDs and hashes
- `prompts/` - copy of all prompt templates
- `configs/` - copy of extraction specs

**Acceptance criteria**:
- Snapshot is immutable (no overwrites)
- Contains actual file contents, not just references

### Task 4.2: Integrate Version Bundle in Pipeline
**File**: `src/context_builder/pipeline/run.py`

At run start:
- Create version bundle
- Store bundle ID in manifest
- Pass bundle to extraction/classification

**Acceptance criteria**:
- Every run has a version bundle
- Bundle ID appears in manifest.json

### Task 4.3: Link Version Bundle to Decisions
**Files**: `generic.py`, `openai_classifier.py`

Each decision record includes `version_bundle_id` reference.

**Acceptance criteria**:
- Every decision record can be traced to exact versions used

---

## Phase 5: Append-Only Storage Patterns

**Objective**: Convert overwriting storage to versioned, append-only patterns.

### Task 5.1: Version Truth Store
**File**: `src/context_builder/storage/truth_store.py`

Change:
- `save_truth_by_file_md5()` writes timestamped files: `{timestamp}.json`
- `latest.txt` points to current version
- `get_truth_by_file_md5()` reads from `latest.txt` pointer
- Add `list_truth_versions(file_md5)` to see history

**Acceptance criteria**:
- Previous truth values are preserved
- Can retrieve truth as of any point in time

### Task 5.2: Version Config History
**File**: `src/context_builder/api/services/prompt_config.py`

Change:
- Add `config_history.jsonl` for append-only history
- `_save_all()` appends to history before updating current
- Add `get_config_history(config_id)` to see changes

**Acceptance criteria**:
- Config changes are tracked with timestamps
- Can see who changed what when (if user tracking added)

### Task 5.3: Version Label History
**File**: `src/context_builder/api/services/labels.py` (or label_store)

Change:
- Labels saved with timestamp in filename
- `latest.txt` pointer pattern
- Previous labels preserved

**Acceptance criteria**:
- Label history is preserved
- Can see progression of human reviews

---

## Phase 6: PII Separation (Can be deferred but schema should accommodate)

**Objective**: Prepare for PII separation without fully implementing vault.

### Task 6.1: Add PII Reference Fields to Schemas
**File**: `src/context_builder/schemas/decision_record.py`

Add optional `pii_refs` field structure that can hold references instead of values.

**Acceptance criteria**:
- Schema supports both direct values (current) and refs (future)
- No breaking changes to existing code

### Task 6.2: Create PII Vault Stub
**File**: `src/context_builder/storage/pii_vault.py`

Create placeholder:
- `store_pii(data) -> ref_id` - for now, just returns None (not implemented)
- `get_pii(ref_id) -> data` - for now, raises NotImplementedError
- Document the interface for future implementation

**Acceptance criteria**:
- Interface is defined
- Can be implemented later without schema changes

---

## Verification & Testing

### Task V.1: Unit Tests for Hash Chain
**File**: `tests/unit/test_decision_ledger.py`

Test:
- Chain integrity verification passes for valid chain
- Chain integrity verification fails if record modified
- Chain integrity verification fails if record deleted
- Genesis record has `previous_hash = "GENESIS"`

### Task V.2: Unit Tests for LLM Audit
**File**: `tests/unit/test_llm_audit.py`

Test:
- LLM calls are logged with all fields
- Call IDs are unique
- Wrapper doesn't change LLM response behavior

### Task V.3: Integration Test for Decision Flow
**File**: `tests/integration/test_decision_logging.py`

Test end-to-end:
- Run classification → decision logged
- Run extraction → decision logged
- Human review → decision logged
- All decisions have valid version_bundle reference

### Task V.4: Verification Endpoints
**File**: `src/context_builder/api/main.py`

Add:
- `GET /api/compliance/integrity` - verify all ledgers
- `GET /api/compliance/decisions/{decision_id}` - get single decision with full context
- `GET /api/compliance/decisions?claim_id=X` - query decisions for claim

**Acceptance criteria**:
- Endpoints return useful data for auditors
- Integrity check returns actionable results

---

## File Summary

### New Files to Create
| File | Phase | Description |
|------|-------|-------------|
| `schemas/decision_record.py` | 1 | Core decision schema |
| `services/decision_ledger.py` | 1 | Append-only ledger with hash chain |
| `services/llm_audit.py` | 2 | LLM call wrapper and logging |
| `storage/version_bundles.py` | 4 | Immutable version snapshots |
| `storage/pii_vault.py` | 6 | PII vault interface (stub) |
| `tests/unit/test_decision_ledger.py` | V | Hash chain tests |
| `tests/unit/test_llm_audit.py` | V | LLM audit tests |
| `tests/integration/test_decision_logging.py` | V | E2E decision flow |

### Files to Modify
| File | Phase | Changes |
|------|-------|---------|
| `api/services/audit.py` | 1 | Add hash chaining |
| `classification/openai_classifier.py` | 2,3 | Wrap LLM, log decisions |
| `extraction/extractors/generic.py` | 2,3 | Wrap LLM, log decisions |
| `impl/openai_vision_ingestion.py` | 2 | Wrap LLM |
| `api/services/labels.py` | 3 | Log human review decisions |
| `pipeline/run.py` | 4 | Version bundle integration |
| `storage/truth_store.py` | 5 | Versioned storage |
| `api/services/prompt_config.py` | 5 | Config history |
| `api/main.py` | V | Verification endpoints |

---

## Success Criteria

After implementation:

1. **Hash Chain Integrity**: `GET /api/compliance/integrity` returns `{valid: true}`
2. **Decision Coverage**: Every classification, extraction, and human review has a decision record
3. **LLM Traceability**: Can retrieve full prompt/response for any LLM-influenced decision
4. **Version Traceability**: Can prove exactly what code/model/config produced any decision
5. **History Preservation**: No data is ever deleted, only appended
6. **Audit Export**: Can export all decisions for a claim as JSON

---

## Out of Scope (Future Work)

These are important but can be added later:
- Encryption at rest (PII vault implementation)
- Retention policies and legal hold
- Compliance dashboards and UI
- Anomaly detection
- Evidence pack export (PDF bundles)
- Audience-specific views
