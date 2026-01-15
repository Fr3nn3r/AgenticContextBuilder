# Plan: Use Registry Truth for Metrics

## Problem

`InsightsAggregator` uses `get_label(doc_id)` which looks in claim-scoped storage. When the same file exists in multiple claims (same `doc_id`), it finds the wrong claim's labels.

Labels are claim-agnostic - the truth about a document's content doesn't depend on which claim it's in.

## Solution

Use `TruthStore.get_truth_by_file_md5(file_md5)` instead of `get_label(doc_id)` for metrics computation.

**Already exists:**
- `TruthStore` class in `storage/truth_store.py`
- `get_truth_by_file_md5(file_md5)` method
- Registry truth at `registry/truth/{file_md5}/latest.json`
- `file_md5` available in doc metadata and extraction results

## Implementation Steps

### Step 1: Add `get_truth` to Storage protocol

**File:** `src/context_builder/storage/protocol.py`

```python
def get_truth(self, file_md5: str) -> Optional[dict]:
    """Get canonical truth by file MD5 from registry."""
    ...
```

### Step 2: Implement in FileStorage

**File:** `src/context_builder/storage/filesystem.py`

```python
from .truth_store import TruthStore

def get_truth(self, file_md5: str) -> Optional[dict]:
    """Get canonical truth by file MD5 from registry."""
    truth_store = TruthStore(self.claims_dir.parent)
    return truth_store.get_truth_by_file_md5(file_md5)
```

### Step 3: Update InsightsAggregator

**File:** `src/context_builder/api/insights.py`

In `_load_documents()`, change:

```python
# Before (claim_id workaround)
labels = storage.get_label(doc_id, claim_id)

# After (use registry truth)
file_md5 = None
if extraction:
    file_md5 = extraction.get("run", {}).get("input_hashes", {}).get("file_md5")
labels = storage.get_truth(file_md5) if file_md5 else None
```

### Step 4: Revert claim_id workaround

**Files:**
- `storage/protocol.py` - remove `claim_id` param from `get_label`
- `storage/filesystem.py` - remove `claim_id` logic from `get_label`

### Step 5: Verify migration exists

Ensure `TruthService._migrate_from_labels()` runs when registry truth is empty, copying claim-scoped labels to registry.

## Files Changed

| File | Change |
|------|--------|
| `storage/protocol.py` | Add `get_truth()`, revert `get_label` signature |
| `storage/filesystem.py` | Add `get_truth()`, revert `get_label` |
| `api/insights.py` | Use `get_truth(file_md5)` instead of `get_label` |

## Verification

1. Rebuild index: `python -c "from context_builder.storage.index_builder import build_all_indexes; from pathlib import Path; build_all_indexes(Path('output'))"`
2. Test metrics API: `curl http://localhost:8000/api/insights/run/run_20260113_160825_967a139/overview`
3. Verify `labeled_fields > 0` for runs with labeled docs
