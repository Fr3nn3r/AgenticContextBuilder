# Storage Backend Swap Analysis

This document provides a comprehensive analysis of the current storage architecture and the impact of swapping to a database backend (Supabase, PostgreSQL, or other).

**Last Updated**: 2026-01-18
**Status**: Analysis Complete - No Development

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Overview](#current-architecture-overview)
3. [Storage Interfaces & Protocols](#storage-interfaces--protocols)
4. [Implementation Analysis](#implementation-analysis)
5. [Storage Touchpoints Inventory](#storage-touchpoints-inventory)
6. [Impact Analysis by Backend](#impact-analysis-by-backend)
7. [Migration Strategy](#migration-strategy)
8. [Effort Estimation](#effort-estimation)
9. [Risk Assessment](#risk-assessment)

---

## Executive Summary

### Current State
The ContextBuilder application uses **file-based JSON storage** with:
- A well-defined protocol layer (`Storage`, `DocStore`, `RunStore`, `LabelStore`)
- A primary `FileStorage` implementation
- JSONL indexes for O(1) lookups
- Append-only history for compliance audit trails

### Swap Feasibility
| Aspect | Rating | Notes |
|--------|--------|-------|
| **Abstraction Layer** | ⭐⭐⭐ Good | Protocols exist but underutilized |
| **API Services** | ⭐⭐ Moderate | Heavy direct file I/O bypasses abstraction |
| **Compliance Layer** | ⭐⭐ Moderate | JSONL append-only needs DB event tables |
| **Pipeline** | ⭐ Poor | Direct file writes throughout |
| **Index Layer** | ⭐⭐⭐ Good | Already abstracted via IndexReader |

### Estimated Effort
- **Supabase/PostgreSQL**: 3-4 weeks (medium complexity)
- **MongoDB**: 2-3 weeks (JSON-friendly)
- **SQLite**: 1-2 weeks (local, simpler migration)

---

## Current Architecture Overview

### Directory Structure (Per Workspace)

```
workspace_id/
├── claims/                          # Document storage
│   └── {claim_id}/
│       └── docs/
│           └── {doc_id}/
│               ├── meta/doc.json            # Document metadata
│               ├── text/pages.json          # Extracted text (pages array)
│               ├── source/{file}.pdf        # Original document
│               └── labels/{doc_id}.json     # DEPRECATED (moved to registry)
│
├── runs/                            # Pipeline execution logs
│   └── {run_id}/
│       ├── manifest.json            # Run configuration
│       ├── summary.json             # Execution summary
│       ├── metrics.json             # Quality metrics
│       └── .complete                # Completion marker
│
├── registry/                        # Indexes & canonical data
│   ├── doc_index.jsonl              # O(1) document lookup
│   ├── run_index.jsonl              # O(1) run lookup
│   ├── label_index.jsonl            # O(1) label lookup
│   ├── registry_meta.json           # Index metadata
│   ├── labels/
│   │   ├── {doc_id}.json            # Current label
│   │   └── {doc_id}_history.jsonl   # Version history (append-only)
│   └── truth/
│       └── {file_md5}/
│           ├── latest.json          # Canonical ground truth
│           └── history.jsonl        # Truth version history
│
├── logs/                            # Compliance logs
│   ├── decisions.jsonl              # Human decision audit
│   └── llm_calls.jsonl              # LLM call records
│
└── config/                          # Configuration
    └── prompts.json                 # Prompt templates
```

### Data Flow

```
                     ┌─────────────────────────────────────────────┐
                     │              API Layer                       │
                     │  (ClaimsService, DocumentsService, etc.)    │
                     └──────────────────┬──────────────────────────┘
                                        │
                     ┌──────────────────▼──────────────────────────┐
                     │           StorageFacade                      │
                     │  (doc_store, label_store, run_store)        │
                     └──────────────────┬──────────────────────────┘
                                        │
                     ┌──────────────────▼──────────────────────────┐
                     │            FileStorage                       │
                     │   (Primary implementation - 782 lines)       │
                     └──────────────────┬──────────────────────────┘
                                        │
         ┌──────────────────────────────┼──────────────────────────┐
         │                              │                           │
         ▼                              ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   IndexReader    │         │   Filesystem     │         │   TruthStore    │
│ (JSONL caches)   │         │   (JSON files)   │         │ (MD5-keyed)     │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

---

## Storage Interfaces & Protocols

### Core Protocol Definitions

**File**: `src/context_builder/storage/protocol.py`

```python
@runtime_checkable
class Storage(Protocol):
    """Complete storage interface - all operations"""

    # Discovery
    def list_claims() -> list[ClaimRef]
    def list_docs(claim_id: str) -> list[DocRef]
    def list_runs() -> list[RunRef]

    # Document Access
    def get_doc(doc_id: str) -> Optional[DocBundle]
    def get_doc_text(doc_id: str) -> Optional[DocText]
    def get_doc_source_path(doc_id: str) -> Optional[Path]
    def find_doc_claim(doc_id: str) -> Optional[str]

    # Run Access
    def get_run(run_id: str) -> Optional[RunBundle]
    def get_extraction(run_id: str, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]

    # Labels
    def get_label(doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]
    def save_label(doc_id: str, label_data: dict) -> None
    def get_label_summary(doc_id: str) -> Optional[LabelSummary]

    # Indexes
    def has_indexes() -> bool
    def get_index_meta() -> Optional[dict]

@runtime_checkable
class DocStore(Protocol):
    """Narrow interface for document operations"""
    def list_claims() -> list[ClaimRef]
    def list_docs(claim_id: str) -> list[DocRef]
    def get_doc(doc_id: str) -> Optional[DocBundle]
    def get_doc_text(doc_id: str) -> Optional[DocText]

@runtime_checkable
class RunStore(Protocol):
    """Narrow interface for run operations"""
    def list_runs() -> list[RunRef]
    def get_run(run_id: str) -> Optional[RunBundle]
    def get_extraction(run_id: str, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]

@runtime_checkable
class LabelStore(Protocol):
    """Narrow interface for label operations"""
    def get_label(doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]
    def save_label(doc_id: str, label_data: dict) -> None
    def get_label_summary(doc_id: str) -> Optional[LabelSummary]
```

### Data Models

**File**: `src/context_builder/storage/models.py`

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `ClaimRef` | Claim reference | claim_id, claim_folder, doc_count |
| `DocRef` | Document reference | doc_id, claim_id, doc_type, filename, source_type |
| `DocBundle` | Full document | doc_id, claim_id, metadata dict, doc_root Path |
| `DocText` | Text content | doc_id, pages list |
| `RunRef` | Run reference | run_id, status, timestamps, counts |
| `RunBundle` | Full run | run_id, manifest, summary, metrics |
| `LabelSummary` | Label stats | doc_id, has_label, labeled_count, updated_at |

### StorageFacade

**File**: `src/context_builder/storage/facade.py`

```python
@dataclass(frozen=True)
class StorageFacade:
    doc_store: DocStore
    label_store: LabelStore
    run_store: RunStore

    @classmethod
    def from_storage(cls, storage: FileStorage) -> "StorageFacade":
        return cls(doc_store=storage, label_store=storage, run_store=storage)
```

---

## Implementation Analysis

### FileStorage Class

**File**: `src/context_builder/storage/filesystem.py` (~782 lines)

#### Key Implementation Details

| Feature | Implementation | DB Equivalent |
|---------|----------------|---------------|
| **Atomic Writes** | Temp file + rename | Transaction |
| **Index Caching** | In-memory dict from JSONL | Query cache |
| **Fallback** | Filesystem scan if no index | Full table scan |
| **Version History** | Append-only JSONL | Event/audit table |
| **Path Resolution** | Dynamic via workspace | Parameterized queries |

#### Critical Methods Requiring DB Implementation

```python
# Must implement for ANY backend swap:
list_claims() -> list[ClaimRef]
list_docs(claim_id: str) -> list[DocRef]
list_runs() -> list[RunRef]
get_doc(doc_id: str) -> Optional[DocBundle]
get_doc_text(doc_id: str) -> Optional[DocText]
get_doc_source_path(doc_id: str) -> Optional[Path]  # Binary storage issue!
find_doc_claim(doc_id: str) -> Optional[str]
get_run(run_id: str) -> Optional[RunBundle]
get_extraction(run_id: str, doc_id: str) -> Optional[dict]
get_label(doc_id: str) -> Optional[dict]
save_label(doc_id: str, label_data: dict) -> None
get_label_summary(doc_id: str) -> Optional[LabelSummary]
get_label_history(doc_id: str) -> List[dict]
has_indexes() -> bool
get_index_meta() -> Optional[dict]
invalidate_indexes() -> None
delete_claim(claim_id: str) -> bool
delete_run(run_id: str, delete_claims: bool) -> Tuple[bool, int, int]
```

### What's NOT in the Protocol (Missing Abstractions)

| Operation | Current Location | Issue |
|-----------|-----------------|-------|
| Extraction save | `pipeline/writer.py` | Direct file write |
| Document ingest | `api/services/upload.py` | Direct staging |
| Compliance logging | `services/compliance/` | JSONL append |
| Truth store | `storage/truth_store.py` | MD5-keyed files |
| Config storage | `api/services/prompt_config.py` | Direct JSON |
| Session storage | `api/services/auth.py` | Direct JSON |

---

## Storage Touchpoints Inventory

### Files Requiring Modification

#### HIGH Priority (Core Storage)

| File | Lines | Direct I/O | Facade Use | Impact |
|------|-------|------------|------------|--------|
| `storage/filesystem.py` | 782 | Heavy | N/A (is impl) | Replace entire file |
| `storage/index_reader.py` | ~200 | Heavy | N/A | Replace with DB queries |
| `storage/index_builder.py` | ~250 | Heavy | N/A | Replace with DB writes |
| `storage/truth_store.py` | ~150 | Heavy | N/A | Replace with DB impl |

#### MEDIUM Priority (API Services)

| File | Lines | Direct I/O | Facade Use | Impact |
|------|-------|------------|------------|--------|
| `api/services/claims.py` | 373 | Lines 39-52, 80-90, 165-175, 220 | Partial | Refactor to facade |
| `api/services/documents.py` | 463 | Lines 53-116, 134-141, 240-244, 359-390 | Partial | Refactor to facade |
| `api/services/labels.py` | 427 | Lines 235-288, 343-378, 415-417 | Good | Minor changes |
| `api/services/pipeline.py` | 900+ | Heavy | None | Major refactor |
| `api/services/upload.py` | 300+ | Heavy | None | Major refactor |
| `api/services/evolution.py` | ~200 | Lines 88-99 | None | Refactor |

#### LOW Priority (Supporting)

| File | Lines | Impact |
|------|-------|--------|
| `api/services/auth.py` | ~150 | Sessions to DB |
| `api/services/users.py` | ~150 | Users to DB |
| `api/services/prompt_config.py` | ~200 | Config to DB |
| `pipeline/writer.py` | ~50 | Update for DB writes |
| `services/compliance/file/*.py` | ~400 | Compliance to DB |

### Direct Filesystem Operations to Replace

```python
# Pattern: open() for JSON read/write
open(path, 'r') + json.load()     # → SELECT query
open(path, 'w') + json.dump()     # → INSERT/UPDATE query

# Pattern: Path.glob() for discovery
path.glob("*.json")               # → SELECT with LIKE/pattern
path.iterdir()                    # → SELECT children

# Pattern: Path.exists() checks
path.exists()                     # → SELECT EXISTS

# Pattern: shutil for deletion
shutil.rmtree(path)               # → DELETE CASCADE

# Pattern: Atomic writes (temp + rename)
write(tmp) + rename(tmp, target)  # → Transaction commit
```

---

## Impact Analysis by Backend

### Supabase (PostgreSQL + Storage)

#### Advantages
- PostgreSQL for structured data (claims, docs, runs, labels)
- Supabase Storage for binary files (PDFs, images)
- Built-in Row Level Security (RLS) for multi-tenant
- Real-time subscriptions for live updates
- Edge Functions for serverless processing

#### Schema Design

```sql
-- Core Tables
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'available',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ
);

CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    claim_id TEXT NOT NULL,
    claim_folder TEXT NOT NULL,
    doc_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, claim_id)
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    claim_id UUID REFERENCES claims(id),
    doc_id TEXT NOT NULL,
    doc_type TEXT,
    filename TEXT,
    source_type TEXT,
    language TEXT DEFAULT 'unknown',
    page_count INT DEFAULT 1,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, doc_id)
);

CREATE TABLE document_text (
    doc_id UUID PRIMARY KEY REFERENCES documents(id),
    pages JSONB NOT NULL,  -- Array of {page, text, text_md5}
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    run_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    manifest JSONB,
    summary JSONB,
    metrics JSONB,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    UNIQUE(workspace_id, run_id)
);

CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id),
    doc_id UUID REFERENCES documents(id),
    extraction_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(run_id, doc_id)
);

CREATE TABLE labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    doc_id UUID REFERENCES documents(id),
    label_data JSONB NOT NULL,
    version INT DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT,
    UNIQUE(workspace_id, doc_id)
);

-- Append-only audit tables
CREATE TABLE label_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label_id UUID REFERENCES labels(id),
    label_data JSONB NOT NULL,
    version INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE truth_store (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    file_md5 TEXT NOT NULL,
    truth_data JSONB NOT NULL,
    version INT DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, file_md5)
);

CREATE TABLE truth_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    truth_id UUID REFERENCES truth_store(id),
    truth_data JSONB NOT NULL,
    version INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Compliance tables (append-only)
CREATE TABLE decision_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    decision_type TEXT NOT NULL,
    decision_data JSONB NOT NULL,
    user_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_call_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id),
    call_data JSONB NOT NULL,
    model TEXT,
    tokens_in INT,
    tokens_out INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_documents_workspace_claim ON documents(workspace_id, claim_id);
CREATE INDEX idx_documents_doc_id ON documents(doc_id);
CREATE INDEX idx_labels_doc_id ON labels(doc_id);
CREATE INDEX idx_truth_file_md5 ON truth_store(file_md5);
CREATE INDEX idx_runs_workspace ON runs(workspace_id);
```

#### Binary File Storage
```python
# Use Supabase Storage for PDFs/images
from supabase import create_client

supabase = create_client(url, key)

# Upload
supabase.storage.from_('documents').upload(
    f'{workspace_id}/{claim_id}/{doc_id}/source.pdf',
    file_data
)

# Download
data = supabase.storage.from_('documents').download(
    f'{workspace_id}/{claim_id}/{doc_id}/source.pdf'
)
```

#### Effort Estimate: 3-4 weeks
- Week 1: Schema design, migrations, Supabase setup
- Week 2: Implement `SupabaseStorage` class implementing protocols
- Week 3: Refactor API services to use abstraction layer properly
- Week 4: Testing, binary storage integration, compliance logging

---

### PostgreSQL (Self-Hosted)

#### Advantages
- Full control over infrastructure
- Same schema as Supabase
- Can use any blob storage (S3, local, Azure Blob)

#### Additional Considerations
- Need to manage connection pooling
- Need separate blob storage solution
- More DevOps overhead

#### Effort Estimate: 3-4 weeks
Same as Supabase, plus:
- Additional setup for blob storage
- Connection pool configuration

---

### MongoDB

#### Advantages
- Native JSON/BSON storage (matches current structure)
- Flexible schema evolution
- GridFS for binary files
- Good for document-centric data

#### Schema Design

```javascript
// Collections
db.workspaces        // Workspace registry
db.claims            // Claims with embedded doc refs
db.documents         // Full document metadata + text
db.runs              // Run metadata with embedded results
db.labels            // Current labels
db.label_history     // Append-only label versions
db.truth             // Ground truth by file_md5
db.truth_history     // Append-only truth versions
db.decision_log      // Compliance decisions
db.llm_call_log      // LLM call records

// Document structure matches existing JSON closely
db.documents.insertOne({
    workspace_id: "...",
    claim_id: "...",
    doc_id: "...",
    doc_type: "...",
    metadata: { /* existing doc.json content */ },
    text: { pages: [...] },  // Embedded text
    created_at: new Date()
});
```

#### Effort Estimate: 2-3 weeks
- Week 1: Schema design, MongoDB setup, implement `MongoStorage` class
- Week 2: Refactor services, handle binary storage (GridFS)
- Week 3: Testing, compliance logging migration

---

### SQLite (Local Development)

#### Advantages
- Zero infrastructure
- Single file database
- Good for local/offline use
- Easy testing

#### Considerations
- Single-writer limitation
- No built-in blob storage
- Not suitable for production multi-user

#### Effort Estimate: 1-2 weeks
Simpler migration, good for prototype/testing

---

## Migration Strategy

### Phase 1: Expand Abstraction Layer (Week 1)

1. **Extend protocols** to cover all operations:
```python
# Add to protocol.py
class Storage(Protocol):
    # Existing methods...

    # NEW: Extraction operations
    def save_extraction(run_id: str, doc_id: str, data: dict) -> None
    def list_extractions(run_id: str) -> list[dict]

    # NEW: Document write operations
    def save_doc_metadata(doc_id: str, metadata: dict) -> None
    def save_doc_text(doc_id: str, pages: list[dict]) -> None

    # NEW: Run write operations
    def save_run(run_id: str, manifest: dict, summary: dict) -> None
    def mark_run_complete(run_id: str) -> None

    # NEW: Truth operations
    def get_truth(file_md5: str) -> Optional[dict]
    def save_truth(file_md5: str, data: dict) -> None

    # NEW: Compliance operations
    def log_decision(decision: dict) -> None
    def log_llm_call(call: dict) -> None
```

2. **Update FileStorage** to implement new methods

### Phase 2: Refactor API Services (Week 2)

1. **Remove direct file I/O** from:
   - `api/services/claims.py`
   - `api/services/documents.py`
   - `api/services/pipeline.py`
   - `api/services/upload.py`

2. **Route all operations through StorageFacade**

### Phase 3: Create Database Implementation (Week 2-3)

1. **Implement `DatabaseStorage` class**:
```python
class SupabaseStorage:
    """Supabase implementation of Storage protocol"""

    def __init__(self, supabase_client, workspace_id: str):
        self.client = supabase_client
        self.workspace_id = workspace_id

    def list_claims(self) -> list[ClaimRef]:
        result = self.client.table('claims') \
            .select('*') \
            .eq('workspace_id', self.workspace_id) \
            .execute()
        return [ClaimRef(**row) for row in result.data]

    # ... implement all protocol methods
```

### Phase 4: Binary Storage (Week 3)

1. **Implement blob storage adapter**:
```python
class BlobStorage(Protocol):
    def upload(path: str, data: bytes) -> str  # Returns URL
    def download(path: str) -> bytes
    def delete(path: str) -> bool
    def exists(path: str) -> bool

class SupabaseBlobStorage:
    def upload(self, path: str, data: bytes) -> str:
        self.client.storage.from_('documents').upload(path, data)
        return self.client.storage.from_('documents').get_public_url(path)
```

### Phase 5: Compliance & Audit (Week 3-4)

1. **Migrate append-only logs to database**
2. **Ensure immutability** (no UPDATE/DELETE on audit tables)
3. **Add triggers for automatic history population**

### Phase 6: Testing & Validation (Week 4)

1. **Unit tests** for new storage implementation
2. **Integration tests** with test database
3. **Migration scripts** for existing data
4. **Performance benchmarking**

---

## Effort Estimation

### By Component

| Component | Effort | Complexity | Dependencies |
|-----------|--------|------------|--------------|
| Expand protocols | 2 days | Low | None |
| Database schema | 2 days | Medium | Backend choice |
| DatabaseStorage class | 5 days | High | Schema |
| Refactor API services | 5 days | Medium | New protocols |
| Binary storage | 3 days | Medium | Backend choice |
| Compliance migration | 2 days | Medium | Schema |
| Testing | 5 days | Medium | All above |
| **Total** | **24 days** | - | - |

### By Backend

| Backend | Setup | Implementation | Testing | Total |
|---------|-------|----------------|---------|-------|
| Supabase | 2 days | 15 days | 5 days | **22 days** |
| PostgreSQL | 3 days | 15 days | 5 days | **23 days** |
| MongoDB | 2 days | 12 days | 4 days | **18 days** |
| SQLite | 1 day | 8 days | 3 days | **12 days** |

### Resource Requirements

- **1 Senior Developer**: Full-time for duration
- **1 DevOps** (for Supabase/PostgreSQL): Part-time, setup and deployment
- **Testing**: Included in developer effort

---

## Risk Assessment

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Binary file migration** | Data loss | Staged migration, checksums |
| **Compliance audit trail** | Regulatory | Ensure append-only in DB |
| **Performance regression** | User experience | Benchmark before/after |
| **Index performance** | Slow queries | Proper DB indexes, caching |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Schema changes** | Breaking changes | Version migrations |
| **Connection issues** | Availability | Connection pooling, retries |
| **Large file handling** | Memory/timeout | Streaming uploads |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **API compatibility** | Client updates | Keep same response shapes |
| **Workspace switching** | Context errors | Parameterized queries |

---

## Appendix: File Reference

### Core Storage Files
```
src/context_builder/storage/
├── protocol.py          # Storage interfaces (extend this)
├── facade.py            # StorageFacade (update imports)
├── filesystem.py        # FileStorage (replace with DatabaseStorage)
├── models.py            # Data models (keep unchanged)
├── index_reader.py      # Replace with DB queries
├── index_builder.py     # Replace with DB writes
├── truth_store.py       # Replace with DB implementation
├── version_bundles.py   # Migrate to DB
└── workspace_paths.py   # Update for DB context
```

### API Services to Refactor
```
src/context_builder/api/services/
├── claims.py            # Remove direct I/O (lines 39-220)
├── documents.py         # Remove direct I/O (lines 53-390)
├── labels.py            # Minor updates
├── pipeline.py          # Major refactor (lines 729-811)
├── upload.py            # Major refactor (staging to DB)
├── evolution.py         # Update for DB
├── auth.py              # Sessions to DB
├── users.py             # Users to DB
└── prompt_config.py     # Config to DB
```

### Compliance Files
```
src/context_builder/services/compliance/
├── storage_factory.py   # Add DATABASE backend
├── file/
│   ├── llm_storage.py   # Migrate to DB
│   └── decision_storage.py  # Migrate to DB
```

---

## Conclusion

The ContextBuilder codebase has a **solid foundation** for a database backend swap:
- Well-defined protocols exist
- Data models are clean and reusable
- Facade pattern already in use

**Key challenges**:
1. Many API services bypass the abstraction layer with direct file I/O
2. Pipeline components write directly to filesystem
3. Compliance logging uses append-only JSONL patterns

**Recommendation**: Start with **MongoDB** for fastest migration (JSON-native), or **Supabase** for best long-term scalability (PostgreSQL + Storage + Auth).

The estimated effort of **3-4 weeks** assumes one developer working full-time with clear requirements and no scope creep.
