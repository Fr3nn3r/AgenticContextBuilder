# Compliance Developer Instructions

This document explains how to use the compliance infrastructure and maintain compliance standards in both existing and new code.

---

## Overview

Our compliance infrastructure provides:
1. **Decision Ledger** - Tamper-evident logging of all system decisions
2. **LLM Audit** - Full capture of all LLM API calls
3. **Version Bundles** - Reproducibility snapshots linked to pipeline runs
4. **Version History** - Append-only history for truth, configs, and labels
5. **Compliance API** - REST endpoints for verification and audit queries
6. **PII Vault** - Separation of PII from audit trails (stub, future implementation)

**Key Principle**: Every decision the system makes must be traceable, explainable, and verifiable.

---

## 1. Decision Logging

### When to Log a Decision

Log a `DecisionRecord` whenever the system:
- Classifies a document
- Extracts fields from a document
- Makes a quality gate determination
- Records human review/labeling
- Overrides a previous decision

### How to Log Decisions

```python
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
)
from pathlib import Path

# Create ledger instance
ledger = DecisionLedger(Path("output/logs"))

# Create a decision record
record = DecisionRecord(
    decision_id="",  # Auto-generated if empty
    decision_type=DecisionType.CLASSIFICATION,
    claim_id="CLM-001",
    doc_id="DOC-001",
    actor_type="system",
    actor_id="gpt-4o-2024-05-13",
    rationale=DecisionRationale(
        summary="Document classified as invoice based on header patterns",
        confidence=0.95,
    ),
    outcome=DecisionOutcome(
        doc_type="invoice",
        confidence=0.95,
    ),
)

# Append to ledger (automatically adds hash chain)
ledger.append(record)
```

### Decision Types Reference

| Type | When to Use | Required Fields |
|------|-------------|-----------------|
| `classification` | Document type determined | doc_type, confidence |
| `extraction` | Fields extracted from doc | fields dict, quality_gate_status |
| `quality_gate` | Pass/warn/fail determination | status, reasons |
| `human_review` | Human labels/corrects fields | reviewer, field_changes |
| `override` | Human corrects classification | original_value, override_value, reason |

---

## 2. LLM Call Auditing

### Automatic Auditing (Preferred)

The `AuditedOpenAIClient` wrapper automatically logs all LLM calls. Use it instead of direct OpenAI client calls:

```python
from context_builder.services.llm_audit import AuditedOpenAIClient
from openai import OpenAI

# Wrap your OpenAI client
base_client = OpenAI()
client = AuditedOpenAIClient(base_client)

# Use normally - calls are automatically logged
response = client.chat_completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Extract fields from this document..."}],
    temperature=0.0,
    # Optional: link to decision for traceability
    decision_context={
        "doc_id": "DOC-001",
        "claim_id": "CLM-001",
        "purpose": "field_extraction",
    }
)
```

### What Gets Captured

Every LLM call automatically logs:
- `call_id` - Unique identifier
- `timestamp` - When the call was made
- `model` - Model ID used
- `messages` - Full prompt (system + user messages)
- `parameters` - temperature, max_tokens, etc.
- `response` - Full response content
- `token_usage` - Prompt/completion/total tokens
- `latency_ms` - Response time
- `decision_context` - Link to related decision

### Log Location

LLM calls are logged to: `output/logs/llm_calls.jsonl`

---

## 3. Version History (Append-Only Storage)

All data stores now maintain append-only version history for compliance audit trails.

### Truth Store History

Every time ground truth is saved, it's appended to a history file:

```python
from context_builder.storage.truth_store import TruthStore
from pathlib import Path

store = TruthStore(Path("output"))

# Save truth (automatically versioned)
store.save_truth_by_file_md5("abc123def456", {
    "doc_type": "invoice",
    "field_labels": [{"field": "claim_number", "value": "CLM-001"}],
})

# Get all historical versions
history = store.get_truth_history("abc123def456")
for version in history:
    print(f"Version {version['_version_metadata']['version_number']}")
    print(f"  Saved at: {version['_version_metadata']['saved_at']}")

# Get specific version
v2 = store.get_truth_version("abc123def456", version_number=2)
```

**Storage Location**: `output/registry/truth/{file_md5}/history.jsonl`

### Config History

Prompt configuration changes are tracked:

```python
from context_builder.api.services.prompt_config import PromptConfigService
from pathlib import Path

service = PromptConfigService(Path("output/config"))

# Any config change is logged
service.create_config("new_config", "...", model="gpt-4o")
service.update_config("new_config", {"temperature": 0.5})
service.delete_config("old_config")

# Get change history
history = service.get_config_history()
for entry in history:
    print(f"{entry['action']} at {entry['timestamp']}")
    print(f"  Config ID: {entry['config_id']}")
```

**Storage Location**: `output/config/prompt_configs_history.jsonl`

### Label History

Document label changes are tracked per document:

```python
from context_builder.storage.filesystem import FileStorage
from pathlib import Path

storage = FileStorage(Path("output/claims"))

# Save label (automatically versioned)
storage.save_label("DOC-001", {
    "doc_id": "DOC-001",
    "field_labels": [...],
    "review": {"reviewer": "user@example.com"},
})

# Get label history for a document
history = storage.get_label_history("DOC-001")
for version in history:
    meta = version.get("_version_metadata", {})
    print(f"Version {meta.get('version_number')} at {meta.get('saved_at')}")
```

**Storage Location**: `output/claims/{claim}/docs/{doc}/labels/history.jsonl`

### Version Metadata

All versioned entries include `_version_metadata`:
```json
{
  "_version_metadata": {
    "saved_at": "2026-01-14T12:00:00Z",
    "version_number": 3
  },
  // ... rest of data
}
```

---

## 4. Version Bundles (Pipeline Reproducibility)

### Automatic Bundle Creation

Version bundles are automatically created when a pipeline run starts:

```python
# In pipeline/run.py (automatic):
version_bundle_store = get_version_bundle_store(output_base)
version_bundle = version_bundle_store.create_version_bundle(
    run_id=run_id,
    model_name=model,
    extractor_version="v1.0.0",
)
```

### What's Captured

Each version bundle includes:
- `bundle_id` - Unique identifier (vb_...)
- `run_id` - Associated pipeline run
- `git_commit` - Code version SHA
- `git_dirty` - Whether working tree had uncommitted changes
- `contextbuilder_version` - Application version
- `extractor_version` - Extractor module version
- `model_name` - LLM model used
- `model_version` - Model version string
- `prompt_template_hash` - Hash of prompt templates
- `extraction_spec_hash` - Hash of extraction specs

### Linking to Extractions

Bundle ID is included in extraction results via `ExtractionRunMetadata.version_bundle_id`:

```python
# Extraction results include:
{
    "run": {
        "run_id": "run_20260114_120000",
        "version_bundle_id": "vb_abc123...",  # Links to version snapshot
        ...
    }
}
```

### Manual Bundle Operations

```python
from context_builder.storage.version_bundles import get_version_bundle_store
from pathlib import Path

store = get_version_bundle_store(Path("output"))

# List all bundles
run_ids = store.list_bundles()

# Get bundle details
bundle = store.get_version_bundle("run_20260114_120000")
print(f"Git commit: {bundle.git_commit}")
print(f"Model: {bundle.model_name}")
```

**Storage Location**: `output/version_bundles/{run_id}/bundle.json`

---

## 5. Compliance API Endpoints

### Ledger Verification

```bash
# Verify hash chain integrity
curl http://localhost:8000/api/compliance/ledger/verify

# Response:
{
  "valid": true,
  "record_count": 150,
  "break_at": null,
  "reason": null
}
```

### Query Decisions

```bash
# List recent decisions
curl "http://localhost:8000/api/compliance/ledger/decisions?limit=10"

# Filter by type
curl "http://localhost:8000/api/compliance/ledger/decisions?decision_type=classification"

# Filter by document
curl "http://localhost:8000/api/compliance/ledger/decisions?doc_id=DOC-001"

# Filter by claim
curl "http://localhost:8000/api/compliance/ledger/decisions?claim_id=CLM-001"

# Filter by time
curl "http://localhost:8000/api/compliance/ledger/decisions?since=2026-01-14T00:00:00Z"
```

### Version Bundle Endpoints

```bash
# List all version bundles
curl http://localhost:8000/api/compliance/version-bundles

# Get specific bundle
curl http://localhost:8000/api/compliance/version-bundles/run_20260114_120000
```

### History Endpoints

```bash
# Config change history
curl "http://localhost:8000/api/compliance/config-history?limit=50"

# Truth history for a file
curl http://localhost:8000/api/compliance/truth-history/abc123def456

# Label history for a document
curl http://localhost:8000/api/compliance/label-history/DOC-001
```

### API Response Formats

**Decision List Response:**
```json
[
  {
    "decision_id": "dec_abc123",
    "decision_type": "classification",
    "timestamp": "2026-01-14T12:00:00Z",
    "claim_id": "CLM-001",
    "doc_id": "DOC-001",
    "actor_type": "system",
    "actor_id": "gpt-4o",
    "rationale": {
      "summary": "Classified as invoice",
      "confidence": 0.95
    },
    "prev_hash": "a1b2c3d4e5f6..."
  }
]
```

**History Response:**
```json
{
  "doc_id": "DOC-001",
  "version_count": 3,
  "versions": [
    {
      "version_number": 1,
      "saved_at": "2026-01-14T10:00:00Z",
      "reviewer": "user1",
      "field_count": 5
    },
    {
      "version_number": 2,
      "saved_at": "2026-01-14T11:00:00Z",
      "reviewer": "user2",
      "field_count": 6
    }
  ]
}
```

---

## 6. Adding Compliance to New Features

### Checklist for New LLM-Based Features

- [ ] Use `AuditedOpenAIClient` instead of direct OpenAI client
- [ ] Pass `decision_context` with doc_id/claim_id when calling LLM
- [ ] Log a `DecisionRecord` after processing completes
- [ ] Include rationale with evidence citations
- [ ] Link LLM `call_id` to decision record

### Checklist for New Human Interaction Features

- [ ] Log `DecisionRecord` with `actor_type="human"`
- [ ] Capture `actor_identity` (user ID, not PII like email)
- [ ] Record before/after values for any corrections
- [ ] Use `override` decision type for classification corrections

### Checklist for New Data Storage

- [ ] Use append-only pattern (no updates/deletes to history)
- [ ] Include `_version_metadata` with timestamps
- [ ] Store current state in `latest.json`
- [ ] Append all versions to `history.jsonl`

### Example: Adding a New Data Store with History

```python
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

class MyDataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: dict) -> None:
        """Save data with version history."""
        item_dir = self.data_dir / key
        item_dir.mkdir(parents=True, exist_ok=True)

        # Add version metadata
        version_ts = datetime.utcnow().isoformat() + "Z"
        versioned_data = {
            **data,
            "_version_metadata": {
                "saved_at": version_ts,
                "version_number": self._get_next_version(item_dir),
            },
        }

        # Write latest.json (atomic)
        latest_path = item_dir / "latest.json"
        tmp_path = item_dir / "latest.json.tmp"
        with open(tmp_path, "w") as f:
            json.dump(versioned_data, f, indent=2)
        tmp_path.replace(latest_path)

        # Append to history.jsonl (append-only)
        history_path = item_dir / "history.jsonl"
        with open(history_path, "a") as f:
            f.write(json.dumps(versioned_data) + "\n")

    def _get_next_version(self, item_dir: Path) -> int:
        history_path = item_dir / "history.jsonl"
        if not history_path.exists():
            return 1
        with open(history_path) as f:
            return sum(1 for _ in f) + 1

    def get_history(self, key: str) -> List[dict]:
        history_path = self.data_dir / key / "history.jsonl"
        if not history_path.exists():
            return []
        with open(history_path) as f:
            return [json.loads(line) for line in f if line.strip()]
```

---

## 7. Retrofitting Existing Code

### Priority 1: Wrap Existing LLM Calls

Find all direct OpenAI client usage and wrap with `AuditedOpenAIClient`:

```bash
# Find direct client usage
grep -r "client.chat.completions.create" src/
```

**Already wrapped:**
- `extraction/extractors/generic.py` ✅
- `classification/openai_classifier.py` ✅
- `impl/openai_vision_ingestion.py` ✅

### Priority 2: Add Decision Logging to Processing Steps

| Component | Status | Location |
|-----------|--------|----------|
| Classification | ✅ Done | `openai_classifier.py:_classify_implementation()` |
| Extraction | ✅ Done | `generic.py:extract()` |
| Human Review | ✅ Done | `labels.py:save_labels()` |
| Override | ✅ Done | `labels.py:save_classification_label()` |
| Quality Gate | ✅ Done | Logged in extraction flow |

### Priority 3: Verify Hash Chain Integrity

Use the API endpoint or programmatically:

```python
from context_builder.services.decision_ledger import DecisionLedger
from pathlib import Path

ledger = DecisionLedger(Path("output/logs"))
report = ledger.verify_integrity()

if report["valid"]:
    print(f"✅ Chain valid: {report['record_count']} records")
else:
    print(f"❌ Chain broken at record {report['break_at']}: {report['reason']}")
```

---

## 8. PII Handling Guidelines

### Current State (Stub Implementation)

The PII vault is currently a stub. Until fully implemented:

1. **Avoid storing PII in decision records** - Use references where possible
2. **Use IDs instead of names** - `user_id` not `user_email`
3. **Document PII locations** - Note where PII exists for future migration

### What Counts as PII

- Names (claimant, policyholder, witnesses)
- Government IDs (SSN, driver's license, passport)
- Contact info (email, phone, address)
- Financial info (bank accounts, policy numbers)
- Medical info (diagnoses, treatment records)

---

## 9. Testing Compliance Features

### Unit Tests

```bash
# Decision ledger tests (hash chain integrity)
python -m pytest tests/unit/test_decision_ledger.py -v

# LLM audit tests
python -m pytest tests/unit/test_llm_audit.py -v

# Version history tests
python -m pytest tests/unit/test_version_history.py -v

# Compliance API tests
python -m pytest tests/unit/test_compliance_api.py -v
```

### Integration Tests

```bash
# Full decision flow integration test
python -m pytest tests/integration/test_compliance_decision_flow.py -v
```

### Manual Verification via API

```bash
# Verify ledger integrity
curl http://localhost:8000/api/compliance/ledger/verify

# Check recent decisions
curl "http://localhost:8000/api/compliance/ledger/decisions?limit=5"

# Check version bundles
curl http://localhost:8000/api/compliance/version-bundles
```

---

## 10. Code Review Checklist

When reviewing PRs, verify:

### For Any LLM Usage
- [ ] Uses `AuditedOpenAIClient`, not direct client
- [ ] Passes `decision_context` with identifiers
- [ ] Doesn't log PII in prompts (use refs)

### For Decision Points
- [ ] Logs `DecisionRecord` with appropriate type
- [ ] Includes meaningful rationale
- [ ] Links to LLM calls via `call_id`
- [ ] Uses IDs not PII for actor_identity

### For Human Interactions
- [ ] Logs human decisions with `actor_type="human"`
- [ ] Records before/after for corrections
- [ ] Uses `override` type for classification changes

### For Data Storage
- [ ] No PII in decision ledger
- [ ] Append-only pattern (no updates/deletes to history)
- [ ] Includes timestamps and version metadata
- [ ] Both `latest.json` and `history.jsonl` updated

---

## 11. Troubleshooting

### Decision Ledger Issues

**Problem**: Hash chain verification fails
```
Solution: Do NOT modify decisions.jsonl manually. If corruption detected,
investigate the break point via:
  curl http://localhost:8000/api/compliance/ledger/verify
Contact compliance team before any remediation.
```

**Problem**: Missing decisions in ledger
```
Solution: Check that code path calls ledger.append(). Add logging to
trace execution flow. Verify output/logs directory is writable.
```

### LLM Audit Issues

**Problem**: LLM calls not appearing in log
```
Solution: Verify using AuditedOpenAIClient, not direct OpenAI client.
Check output/logs/llm_calls.jsonl exists and is writable.
```

### Version History Issues

**Problem**: History not being recorded
```
Solution: Ensure using the updated storage classes (TruthStore,
FileStorage, PromptConfigService) that include history tracking.
Check that history.jsonl files are being created.
```

**Problem**: Version numbers not incrementing
```
Solution: Check that _get_next_version() can read history.jsonl.
Verify file permissions allow reading and appending.
```

---

## 12. Quick Reference

### Import Locations

```python
# Decision logging
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
)

# LLM auditing
from context_builder.services.llm_audit import AuditedOpenAIClient

# Version bundles
from context_builder.storage.version_bundles import (
    VersionBundleStore,
    get_version_bundle_store,
)

# Storage with history
from context_builder.storage.truth_store import TruthStore
from context_builder.storage.filesystem import FileStorage
from context_builder.api.services.prompt_config import PromptConfigService

# PII vault (stub)
from context_builder.storage.pii_vault import PIIVault
```

### File Locations

| Component | File |
|-----------|------|
| Decision Ledger | `output/logs/decisions.jsonl` |
| LLM Call Log | `output/logs/llm_calls.jsonl` |
| Version Bundles | `output/version_bundles/{run_id}/bundle.json` |
| Truth History | `output/registry/truth/{file_md5}/history.jsonl` |
| Config History | `output/config/prompt_configs_history.jsonl` |
| Label History | `output/claims/{claim}/docs/{doc}/labels/history.jsonl` |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/compliance/ledger/verify` | GET | Verify hash chain integrity |
| `/api/compliance/ledger/decisions` | GET | List decisions with filters |
| `/api/compliance/version-bundles` | GET | List version bundles |
| `/api/compliance/version-bundles/{run_id}` | GET | Get bundle details |
| `/api/compliance/config-history` | GET | Config change log |
| `/api/compliance/truth-history/{file_md5}` | GET | Truth version history |
| `/api/compliance/label-history/{doc_id}` | GET | Label version history |

### Decision Types

| Type | Actor | Use Case |
|------|-------|----------|
| `classification` | system | Doc type determination |
| `extraction` | system | Field extraction |
| `quality_gate` | system | Pass/warn/fail |
| `human_review` | human | Label verification |
| `override` | human | Correction of system decision |

---

## Questions?

For compliance questions, check:
1. `plans/compliance-implementation-plan.md` - Full implementation details
2. `plans/compliance-foundation-priorities.md` - Architecture rationale
3. `progress/compliance-implementation.md` - Current status

For code examples, see the existing implementations in:
- `src/context_builder/classification/openai_classifier.py`
- `src/context_builder/extraction/extractors/generic.py`
- `src/context_builder/api/services/labels.py`
- `src/context_builder/storage/truth_store.py`
- `src/context_builder/storage/filesystem.py`
