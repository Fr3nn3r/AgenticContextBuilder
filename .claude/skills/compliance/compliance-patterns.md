# Compliance Patterns — Detailed Reference

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
    DecisionRecord, DecisionType, DecisionRationale, DecisionOutcome,
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

## 2. LLM Call Auditing

### Automatic Auditing (Preferred)

The `AuditedOpenAIClient` wrapper automatically logs all LLM calls:

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
    decision_context={
        "doc_id": "DOC-001",
        "claim_id": "CLM-001",
        "purpose": "field_extraction",
    }
)
```

### What Gets Captured

Every LLM call automatically logs:
- `call_id` — Unique identifier
- `timestamp` — When the call was made
- `model` — Model ID used
- `messages` — Full prompt (system + user messages)
- `parameters` — temperature, max_tokens, etc.
- `response` — Full response content
- `token_usage` — Prompt/completion/total tokens
- `latency_ms` — Response time
- `decision_context` — Link to related decision

## 3. Version History (Append-Only Storage)

All data stores maintain append-only version history for compliance audit trails.

### Truth Store History

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

### Config History

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

### Label History

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

### Version Metadata

All versioned entries include `_version_metadata`:
```json
{
  "_version_metadata": {
    "saved_at": "2026-01-14T12:00:00Z",
    "version_number": 3
  }
}
```

## 4. Version Bundles (Pipeline Reproducibility)

### Automatic Bundle Creation

Version bundles are automatically created when a pipeline run starts:

```python
version_bundle_store = get_version_bundle_store(output_base)
version_bundle = version_bundle_store.create_version_bundle(
    run_id=run_id,
    model_name=model,
    extractor_version="v1.0.0",
)
```

### What's Captured

Each version bundle includes:
- `bundle_id` — Unique identifier (vb_...)
- `run_id` — Associated pipeline run
- `git_commit` — Code version SHA
- `git_dirty` — Whether working tree had uncommitted changes
- `contextbuilder_version` — Application version
- `extractor_version` — Extractor module version
- `model_name` — LLM model used
- `prompt_template_hash` — Hash of prompt templates
- `extraction_spec_hash` — Hash of extraction specs

### Linking to Extractions

Bundle ID is included in extraction results via `ExtractionRunMetadata.version_bundle_id`.

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

## 5. Adding Compliance to New Features

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
from typing import List

class MyDataStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: dict) -> None:
        """Save data with version history."""
        item_dir = self.data_dir / key
        item_dir.mkdir(parents=True, exist_ok=True)

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

## 6. PII Handling Guidelines

### Current State (Stub Implementation)

The PII vault is currently a stub. Until fully implemented:

1. **Avoid storing PII in decision records** — Use references where possible
2. **Use IDs instead of names** — `user_id` not `user_email`
3. **Document PII locations** — Note where PII exists for future migration

### What Counts as PII

- Names (claimant, policyholder, witnesses)
- Government IDs (SSN, driver's license, passport)
- Contact info (email, phone, address)
- Financial info (bank accounts, policy numbers)
- Medical info (diagnoses, treatment records)

## 7. Retrofitting Existing Code

### Priority 1: Wrap Existing LLM Calls

Find all direct OpenAI client usage and wrap with `AuditedOpenAIClient`:

```bash
grep -r "client.chat.completions.create" src/
```

**Already wrapped:**
- `extraction/extractors/generic.py`
- `classification/openai_classifier.py`
- `impl/openai_vision_ingestion.py`

### Priority 2: Add Decision Logging to Processing Steps

| Component | Status | Location |
|-----------|--------|----------|
| Classification | Done | `openai_classifier.py:_classify_implementation()` |
| Extraction | Done | `generic.py:extract()` |
| Human Review | Done | `labels.py:save_labels()` |
| Override | Done | `labels.py:save_classification_label()` |
| Quality Gate | Done | Logged in extraction flow |

### Priority 3: Verify Hash Chain Integrity

```python
from context_builder.services.decision_ledger import DecisionLedger
from pathlib import Path

ledger = DecisionLedger(Path("output/logs"))
report = ledger.verify_integrity()

if report["valid"]:
    print(f"Chain valid: {report['record_count']} records")
else:
    print(f"Chain broken at record {report['break_at']}: {report['reason']}")
```
