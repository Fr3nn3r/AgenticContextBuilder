# Implementing a New Storage Backend

This guide explains how to implement a new storage backend (PostgreSQL, Supabase, MongoDB, etc.) for the ContextBuilder application after the storage abstraction refactoring.

## Overview

After the refactoring, all storage operations in the API services go through the storage protocol layer. To add a new backend:

1. **Implement the protocols** - Create a new class that implements `DocStore`, `RunStore`, and `LabelStore`
2. **Register the factory** - Update the storage factory to return your implementation
3. **Handle file storage** - Decide how to handle binary files (PDFs, images)
4. **Test** - Run the existing test suite

**Effort estimate**: 2-3 days for a basic implementation, 1 week for production-ready with tests.

---

## Step 1: Understand the Data Model

### Core Entities

| Entity | Description | Key Fields |
|--------|-------------|------------|
| **Claim** | Insurance claim folder | `claim_id`, `claim_folder`, `doc_count` |
| **Document** | Uploaded document | `doc_id`, `claim_id`, `doc_type`, `original_filename` |
| **Run** | Pipeline execution | `run_id`, `started_at`, `completed_at`, `model`, `status` |
| **Extraction** | Extracted fields from a doc | `run_id`, `doc_id`, `claim_id`, `fields[]`, `quality_gate` |
| **Label** | Human-reviewed corrections | `doc_id`, `field_labels[]`, `review` |

### Relationships

```
Claim (1) ──── (N) Document
  │
  └── (N) Run ──── (N) Extraction ──── (1) Document
                         │
Document (1) ──── (0..1) Label
```

### File Storage Considerations

Some data is inherently file-based:
- **Source files**: PDFs, images, text files (the original uploads)
- **Processed text**: `pages.json` with OCR/extracted text per page
- **Azure DI data**: Raw Azure Document Intelligence response

Options for handling files:
1. **Hybrid**: Keep files on disk, metadata in database
2. **Blob storage**: Store files in S3/GCS/Azure Blob, metadata in database
3. **Database BLOBs**: Store everything in database (not recommended for large files)

---

## Step 2: Create Your Storage Class

Create a new file: `src/context_builder/storage/postgres.py` (or `supabase.py`, `mongodb.py`, etc.)

### Template Structure

```python
"""PostgreSQL storage implementation."""

import json
from pathlib import Path
from typing import List, Optional

from .models import (
    ClaimRef,
    DocRef,
    DocBundle,
    DocText,
    RunRef,
    RunBundle,
    LabelSummary,
    SourceFileRef,
    ExtractionRef,
)


class PostgresStorage:
    """PostgreSQL implementation of the storage protocols.

    Implements: DocStore, RunStore, LabelStore
    """

    def __init__(self, connection_string: str, file_root: Optional[Path] = None):
        """
        Args:
            connection_string: PostgreSQL connection string
            file_root: Optional path for hybrid file storage
        """
        self.conn_string = connection_string
        self.file_root = file_root
        self._pool = None  # Initialize connection pool

    # =========================================================================
    # DocStore Protocol (10 methods)
    # =========================================================================

    def list_claims(self) -> List[ClaimRef]:
        """List all claims with document counts."""
        # TODO: Implement
        # SELECT claim_id, claim_folder, COUNT(doc_id) as doc_count
        # FROM documents GROUP BY claim_id, claim_folder
        pass

    def list_docs(self, claim_id: str) -> List[DocRef]:
        """List all documents in a claim."""
        # TODO: Implement
        # SELECT * FROM documents WHERE claim_id = ?
        pass

    def get_doc(self, doc_id: str) -> Optional[DocBundle]:
        """Get full document bundle by doc_id."""
        # TODO: Implement
        pass

    def get_doc_text(self, doc_id: str) -> Optional[DocText]:
        """Get document text content (pages)."""
        # TODO: Implement
        # If hybrid: read pages.json from file_root
        # If full DB: SELECT pages FROM document_text WHERE doc_id = ?
        pass

    def get_doc_source_path(self, doc_id: str) -> Optional[Path]:
        """Get path to document source file."""
        # TODO: Implement
        # Returns file path - may need hybrid approach
        pass

    def find_doc_claim(self, doc_id: str) -> Optional[str]:
        """Find which claim contains a document."""
        # TODO: Implement
        # SELECT claim_id FROM documents WHERE doc_id = ?
        pass

    def get_doc_metadata(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get document metadata (doc.json equivalent)."""
        # TODO: Implement
        # SELECT metadata FROM documents WHERE doc_id = ?
        pass

    def get_source_files(self, doc_id: str, claim_id: Optional[str] = None) -> List[SourceFileRef]:
        """List source files for a document."""
        # TODO: Implement
        pass

    def get_doc_azure_di(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get Azure Document Intelligence data."""
        # TODO: Implement
        # SELECT azure_di_data FROM document_raw WHERE doc_id = ?
        pass

    # =========================================================================
    # RunStore Protocol (11 methods)
    # =========================================================================

    def list_runs(self) -> List[RunRef]:
        """List all completed runs."""
        # TODO: Implement
        # SELECT * FROM runs WHERE status = 'complete' ORDER BY started_at DESC
        pass

    def get_run(self, run_id: str) -> Optional[RunBundle]:
        """Get full run bundle."""
        # TODO: Implement
        pass

    def get_extraction(self, run_id: str, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get extraction result for a document in a run."""
        # TODO: Implement
        # SELECT data FROM extractions WHERE run_id = ? AND doc_id = ?
        pass

    def get_run_manifest(self, run_id: str) -> Optional[dict]:
        """Get run manifest."""
        # TODO: Implement
        # SELECT manifest FROM runs WHERE run_id = ?
        pass

    def get_run_summary(self, run_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get run summary."""
        # TODO: Implement
        # SELECT summary FROM runs WHERE run_id = ?
        # Or: SELECT summary FROM claim_run_summaries WHERE run_id = ? AND claim_id = ?
        pass

    def list_extractions(self, run_id: str, claim_id: Optional[str] = None) -> List[ExtractionRef]:
        """List all extractions in a run."""
        # TODO: Implement
        # SELECT doc_id, claim_id FROM extractions WHERE run_id = ?
        pass

    def save_run_manifest(self, run_id: str, manifest: dict) -> None:
        """Save run manifest."""
        # TODO: Implement
        # INSERT/UPDATE runs SET manifest = ? WHERE run_id = ?
        pass

    def save_run_summary(self, run_id: str, summary: dict, claim_id: Optional[str] = None) -> None:
        """Save run summary."""
        # TODO: Implement
        pass

    def save_extraction(self, run_id: str, doc_id: str, claim_id: str, data: dict) -> None:
        """Save extraction result."""
        # TODO: Implement
        # INSERT INTO extractions (run_id, doc_id, claim_id, data) VALUES (?, ?, ?, ?)
        pass

    def mark_run_complete(self, run_id: str) -> None:
        """Mark a run as complete."""
        # TODO: Implement
        # UPDATE runs SET status = 'complete', completed_at = NOW() WHERE run_id = ?
        pass

    def list_runs_for_doc(self, doc_id: str, claim_id: str) -> List[str]:
        """List all run IDs with extraction for a document."""
        # TODO: Implement
        # SELECT DISTINCT run_id FROM extractions WHERE doc_id = ? ORDER BY created_at DESC
        pass

    # =========================================================================
    # LabelStore Protocol (5 methods)
    # =========================================================================

    def get_label(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]:
        """Get label data for a document."""
        # TODO: Implement
        # SELECT data FROM labels WHERE doc_id = ? ORDER BY version DESC LIMIT 1
        pass

    def save_label(self, doc_id: str, label_data: dict) -> None:
        """Save label data (append to history)."""
        # TODO: Implement
        # INSERT INTO labels (doc_id, data, version, created_at) VALUES (?, ?, ?, NOW())
        pass

    def get_label_summary(self, doc_id: str) -> Optional[LabelSummary]:
        """Get label summary for a document."""
        # TODO: Implement
        pass

    def get_label_history(self, doc_id: str) -> List[dict]:
        """Get all historical versions of labels."""
        # TODO: Implement
        # SELECT data FROM labels WHERE doc_id = ? ORDER BY version ASC
        pass

    def count_labels_for_claim(self, claim_id: str) -> int:
        """Count labeled documents in a claim."""
        # TODO: Implement
        # SELECT COUNT(DISTINCT doc_id) FROM labels l
        # JOIN documents d ON l.doc_id = d.doc_id WHERE d.claim_id = ?
        pass

    # =========================================================================
    # Index Operations (2 methods) - Optional for DB backends
    # =========================================================================

    def has_indexes(self) -> bool:
        """Databases have built-in indexes, always return True."""
        return True

    def get_index_meta(self) -> Optional[dict]:
        """Return database stats as index meta."""
        # TODO: Implement
        # SELECT COUNT(*) as doc_count FROM documents; etc.
        pass
```

---

## Step 3: Database Schema (PostgreSQL Example)

```sql
-- Claims table (optional - can be derived from documents)
CREATE TABLE claims (
    claim_id VARCHAR(64) PRIMARY KEY,
    claim_folder VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Documents table
CREATE TABLE documents (
    doc_id VARCHAR(64) PRIMARY KEY,
    claim_id VARCHAR(64) NOT NULL REFERENCES claims(claim_id),
    doc_type VARCHAR(64),
    original_filename VARCHAR(255),
    language VARCHAR(8) DEFAULT 'es',
    metadata JSONB,  -- Full doc.json content
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_documents_claim ON documents(claim_id);

-- Document text (pages)
CREATE TABLE document_text (
    doc_id VARCHAR(64) PRIMARY KEY REFERENCES documents(doc_id),
    pages JSONB NOT NULL  -- Array of page objects
);

-- Document raw data (Azure DI, etc.)
CREATE TABLE document_raw (
    doc_id VARCHAR(64) PRIMARY KEY REFERENCES documents(doc_id),
    azure_di_data JSONB
);

-- Runs table
CREATE TABLE runs (
    run_id VARCHAR(64) PRIMARY KEY,
    status VARCHAR(32) DEFAULT 'pending',
    model VARCHAR(64),
    manifest JSONB,
    summary JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Claim-specific run summaries (optional)
CREATE TABLE claim_run_summaries (
    run_id VARCHAR(64) REFERENCES runs(run_id),
    claim_id VARCHAR(64) REFERENCES claims(claim_id),
    summary JSONB,
    PRIMARY KEY (run_id, claim_id)
);

-- Extractions table
CREATE TABLE extractions (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL REFERENCES runs(run_id),
    doc_id VARCHAR(64) NOT NULL REFERENCES documents(doc_id),
    claim_id VARCHAR(64) NOT NULL REFERENCES claims(claim_id),
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(run_id, doc_id)
);
CREATE INDEX idx_extractions_run ON extractions(run_id);
CREATE INDEX idx_extractions_doc ON extractions(doc_id);

-- Labels table (versioned for compliance)
CREATE TABLE labels (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(64) NOT NULL REFERENCES documents(doc_id),
    version INT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(doc_id, version)
);
CREATE INDEX idx_labels_doc ON labels(doc_id);
```

---

## Step 4: Register the Storage Factory

Update `src/context_builder/api/main.py` or wherever the storage factory is defined:

```python
from context_builder.storage import FileStorage
from context_builder.storage.postgres import PostgresStorage  # Your new implementation

def get_storage_factory(backend: str = "file"):
    """Get storage factory based on configuration."""

    if backend == "postgres":
        conn_string = os.getenv("DATABASE_URL")
        file_root = Path(os.getenv("FILE_STORAGE_ROOT", "output"))
        return lambda: PostgresStorage(conn_string, file_root)

    elif backend == "supabase":
        # Similar for Supabase
        pass

    else:
        # Default: file-based storage
        output_root = get_active_workspace_path()
        return lambda: FileStorage(output_root=output_root)
```

---

## Step 5: Handle Binary Files

For source files (PDFs, images), you have three options:

### Option A: Hybrid (Recommended)
Keep files on local disk or cloud storage, store paths in database:

```python
def get_doc_source_path(self, doc_id: str) -> Optional[Path]:
    # Get file path from database
    row = self._execute("SELECT source_path FROM documents WHERE doc_id = ?", [doc_id])
    if row:
        return self.file_root / row['source_path']
    return None
```

### Option B: Cloud Blob Storage
Store files in S3/GCS/Azure Blob:

```python
def get_doc_source_path(self, doc_id: str) -> Optional[Path]:
    # Download from blob storage to temp file
    row = self._execute("SELECT blob_url FROM documents WHERE doc_id = ?", [doc_id])
    if row:
        temp_path = self._download_to_temp(row['blob_url'])
        return temp_path
    return None
```

### Option C: Return URL instead of Path
Modify the API to return URLs for frontend direct access:

```python
def get_doc_source_url(self, doc_id: str) -> Optional[str]:
    row = self._execute("SELECT blob_url FROM documents WHERE doc_id = ?", [doc_id])
    return row['blob_url'] if row else None
```

---

## Step 6: Testing

### Run Existing Tests

The existing test suite should pass with your new implementation:

```bash
# Run storage tests
python -m pytest tests/unit/test_storage.py -v

# Run full test suite
python -m pytest tests/unit/ --no-cov -q
```

### Add Backend-Specific Tests

Create `tests/unit/test_postgres_storage.py`:

```python
import pytest
from context_builder.storage.postgres import PostgresStorage

@pytest.fixture
def postgres_storage(tmp_path):
    """Create test PostgreSQL storage."""
    # Use test database
    return PostgresStorage(
        connection_string="postgresql://test:test@localhost/test_db",
        file_root=tmp_path
    )

def test_list_claims(postgres_storage):
    claims = postgres_storage.list_claims()
    assert isinstance(claims, list)

def test_save_and_get_label(postgres_storage):
    label_data = {"field_labels": [], "review": {}}
    postgres_storage.save_label("test_doc", label_data)
    result = postgres_storage.get_label("test_doc")
    assert result == label_data
```

---

## Step 7: Migration Considerations

### Migrating Existing Data

If you have existing file-based data, create a migration script:

```python
"""Migrate file-based storage to PostgreSQL."""

from context_builder.storage import FileStorage
from context_builder.storage.postgres import PostgresStorage

def migrate(source: FileStorage, target: PostgresStorage):
    # Migrate claims and documents
    for claim in source.list_claims():
        # Insert claim
        target._execute(
            "INSERT INTO claims (claim_id, claim_folder) VALUES (?, ?)",
            [claim.claim_id, claim.claim_folder]
        )

        # Migrate documents
        for doc in source.list_docs(claim.claim_id):
            meta = source.get_doc_metadata(doc.doc_id)
            target._execute(
                "INSERT INTO documents (doc_id, claim_id, metadata) VALUES (?, ?, ?)",
                [doc.doc_id, claim.claim_id, json.dumps(meta)]
            )

    # Migrate runs
    for run in source.list_runs():
        manifest = source.get_run_manifest(run.run_id)
        summary = source.get_run_summary(run.run_id)
        # Insert run...

    # Migrate labels
    # ...
```

### Gradual Migration

You can also implement a hybrid storage that reads from both:

```python
class HybridStorage:
    """Read from new DB, fallback to files for missing data."""

    def __init__(self, db_storage, file_storage):
        self.db = db_storage
        self.files = file_storage

    def get_doc_metadata(self, doc_id: str) -> Optional[dict]:
        result = self.db.get_doc_metadata(doc_id)
        if result is None:
            result = self.files.get_doc_metadata(doc_id)
        return result
```

---

## Protocol Method Summary

### DocStore (10 methods)
| Method | Purpose | Read/Write |
|--------|---------|------------|
| `list_claims()` | List all claims | Read |
| `list_docs(claim_id)` | List documents in claim | Read |
| `get_doc(doc_id)` | Get document bundle | Read |
| `get_doc_text(doc_id)` | Get page text | Read |
| `get_doc_source_path(doc_id)` | Get source file path | Read |
| `find_doc_claim(doc_id)` | Find claim for doc | Read |
| `get_doc_metadata(doc_id)` | Get doc.json | Read |
| `get_source_files(doc_id)` | List source files | Read |
| `get_doc_azure_di(doc_id)` | Get Azure DI data | Read |

### RunStore (11 methods)
| Method | Purpose | Read/Write |
|--------|---------|------------|
| `list_runs()` | List completed runs | Read |
| `get_run(run_id)` | Get run bundle | Read |
| `get_extraction(run_id, doc_id)` | Get extraction | Read |
| `get_run_manifest(run_id)` | Get manifest.json | Read |
| `get_run_summary(run_id)` | Get summary.json | Read |
| `list_extractions(run_id)` | List extractions | Read |
| `save_run_manifest(run_id, data)` | Save manifest | Write |
| `save_run_summary(run_id, data)` | Save summary | Write |
| `save_extraction(run_id, doc_id, data)` | Save extraction | Write |
| `mark_run_complete(run_id)` | Mark complete | Write |
| `list_runs_for_doc(doc_id)` | Find runs for doc | Read |

### LabelStore (5 methods)
| Method | Purpose | Read/Write |
|--------|---------|------------|
| `get_label(doc_id)` | Get latest label | Read |
| `save_label(doc_id, data)` | Save label | Write |
| `get_label_summary(doc_id)` | Get label stats | Read |
| `get_label_history(doc_id)` | Get all versions | Read |
| `count_labels_for_claim(claim_id)` | Count labels | Read |

### Index Operations (2 methods) - Optional
| Method | Purpose | Notes |
|--------|---------|-------|
| `has_indexes()` | Check if indexes exist | Return `True` for DB |
| `get_index_meta()` | Get stats | Return DB counts |

---

## Checklist

- [ ] Create new storage class file (`postgres.py`, `supabase.py`, etc.)
- [ ] Implement all 10 DocStore methods
- [ ] Implement all 11 RunStore methods
- [ ] Implement all 5 LabelStore methods
- [ ] Implement `has_indexes()` and `get_index_meta()`
- [ ] Create database schema/migrations
- [ ] Handle binary file storage (hybrid, blob, or URL)
- [ ] Update storage factory to support new backend
- [ ] Run existing test suite
- [ ] Add backend-specific tests
- [ ] Create data migration script (if needed)
- [ ] Update environment configuration
- [ ] Document deployment requirements

---

## Questions?

If you're implementing a specific backend and need guidance:
1. Check the `FileStorage` implementation in `storage/filesystem.py` for reference
2. The method signatures in `storage/protocol.py` are the contract
3. Return types in `storage/models.py` define the data structures
