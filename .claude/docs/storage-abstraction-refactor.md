# Storage Abstraction Completion - Impact Analysis

This document details the refactoring required to properly abstract ALL storage operations through the storage layer, minimizing future effort when switching to MongoDB, Supabase, or other backends.

**Last Updated**: 2026-01-18
**Status**: Analysis Complete - Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Assessment](#current-state-assessment)
3. [Protocol Extensions Required](#protocol-extensions-required)
4. [File-by-File Refactoring Plan](#file-by-file-refactoring-plan)
5. [Implementation Phases](#implementation-phases)
6. [Effort Estimation](#effort-estimation)
7. [Risk Assessment](#risk-assessment)

---

## Executive Summary

### Problem
The codebase has a storage abstraction layer (`Storage`, `DocStore`, `RunStore`, `LabelStore` protocols) but **11 service files bypass it** with 80+ direct filesystem operations.

### Solution
Extend the protocol layer and refactor all services to use it exclusively.

### Impact Summary

| Metric | Count |
|--------|-------|
| Files to refactor | 11 |
| Direct I/O operations to abstract | 84 |
| New protocol methods needed | ~35 |
| Estimated effort | 5-7 days |

### Benefit
Once complete, switching to any database backend requires implementing **only the protocol interfaces** - zero changes to API services, CLI, or pipeline code.

---

## Current State Assessment

### Direct I/O Operations by Type

| Operation Type | Count | Files Affected |
|----------------|-------|----------------|
| READ (json.load) | 24 | claims, documents, pipeline, upload, evolution, truth, auth, users, prompt_config |
| WRITE (json.dump) | 12 | pipeline, upload, auth, users, prompt_config, writer |
| DISCOVERY (iterdir/glob) | 15 | claims, documents, upload, truth |
| CHECK (exists/is_dir) | 30+ | All service files |
| DELETE (unlink/rmtree) | 3 | upload |

### Files With Direct I/O (Severity)

| File | Direct I/O Instances | Severity |
|------|---------------------|----------|
| `api/services/claims.py` | 18 | HIGH |
| `api/services/documents.py` | 22 | HIGH |
| `api/services/pipeline.py` | 8 | HIGH |
| `api/services/upload.py` | 10 | HIGH |
| `api/services/truth.py` | 12 | MEDIUM |
| `api/services/evolution.py` | 2 | LOW |
| `api/services/auth.py` | 4 | LOW |
| `api/services/users.py` | 4 | LOW |
| `api/services/prompt_config.py` | 6 | LOW |
| `pipeline/writer.py` | 5 | MEDIUM |
| `services/compliance/crypto.py` | 3 | LOW |

---

## Protocol Extensions Required

### Current Protocol Methods (Already Abstracted)

```python
# These already exist and work well
class Storage(Protocol):
    def list_claims() -> list[ClaimRef]
    def list_docs(claim_id: str) -> list[DocRef]
    def list_runs() -> list[RunRef]
    def get_doc(doc_id: str) -> Optional[DocBundle]
    def get_doc_text(doc_id: str) -> Optional[DocText]
    def get_doc_source_path(doc_id: str) -> Optional[Path]
    def find_doc_claim(doc_id: str) -> Optional[str]
    def get_run(run_id: str) -> Optional[RunBundle]
    def get_extraction(run_id: str, doc_id: str) -> Optional[dict]
    def get_label(doc_id: str) -> Optional[dict]
    def save_label(doc_id: str, label_data: dict) -> None
    def get_label_summary(doc_id: str) -> Optional[LabelSummary]
    def has_indexes() -> bool
    def get_index_meta() -> Optional[dict]
```

### NEW Protocol Methods Required

#### DocStore Extensions

```python
class DocStore(Protocol):
    # Existing...

    # NEW: Metadata access
    def get_doc_metadata(self, doc_id: str) -> Optional[dict]:
        """Return raw doc.json metadata dict"""

    def get_doc_azure_di(self, doc_id: str) -> Optional[dict]:
        """Return Azure Document Intelligence raw data"""

    # NEW: Source file discovery
    def get_source_files(self, doc_id: str) -> list[SourceFile]:
        """Return list of source files (PDF, images) for document"""

    def get_source_file_content(self, doc_id: str, filename: str) -> Optional[bytes]:
        """Return binary content of source file"""
```

#### RunStore Extensions

```python
class RunStore(Protocol):
    # Existing...

    # NEW: Read operations
    def get_run_manifest(self, run_id: str) -> Optional[dict]:
        """Return run manifest.json data"""

    def get_run_summary(self, run_id: str) -> Optional[dict]:
        """Return run summary.json data"""

    def get_run_metrics(self, run_id: str) -> Optional[dict]:
        """Return run metrics.json data"""

    def list_extractions(self, run_id: str) -> list[ExtractionRef]:
        """List all extractions for a run"""

    def get_eval_summary(self, run_id: str) -> Optional[dict]:
        """Return evaluation summary for a run"""

    # NEW: Write operations
    def save_run_manifest(self, run_id: str, manifest: dict) -> None:
        """Save run manifest (atomic)"""

    def save_run_summary(self, run_id: str, summary: dict) -> None:
        """Save run summary (atomic)"""

    def save_extraction(self, run_id: str, doc_id: str, data: dict) -> None:
        """Save extraction result for document"""

    def mark_run_complete(self, run_id: str) -> None:
        """Mark run as complete (creates .complete marker)"""

    def append_run_index(self, record: dict) -> None:
        """Append entry to run index"""
```

#### NEW: PendingStore Protocol

```python
@runtime_checkable
class PendingStore(Protocol):
    """Interface for staging/pending document uploads"""

    def get_pending_manifest(self, claim_id: str) -> Optional[PendingManifest]:
        """Get pending claim manifest"""

    def save_pending_manifest(self, claim_id: str, manifest: dict) -> None:
        """Save pending claim manifest"""

    def list_pending_claims(self) -> list[PendingClaimRef]:
        """List all pending claims in staging"""

    def save_pending_document(self, claim_id: str, doc_id: str,
                               filename: str, content: bytes) -> None:
        """Save document to staging area"""

    def delete_pending_document(self, claim_id: str, doc_id: str) -> bool:
        """Delete document from staging"""

    def delete_pending_claim(self, claim_id: str) -> bool:
        """Delete entire pending claim"""

    def cleanup_input_dir(self, claim_id: str) -> None:
        """Clean up temporary input directory"""
```

#### NEW: TruthStore Protocol

```python
@runtime_checkable
class TruthStore(Protocol):
    """Interface for ground truth storage"""

    def get_truth(self, file_md5: str) -> Optional[dict]:
        """Get truth entry by file MD5"""

    def save_truth(self, file_md5: str, data: dict) -> None:
        """Save truth entry (with version history)"""

    def list_truth_entries(self) -> list[TruthRef]:
        """List all truth entries"""

    def get_truth_history(self, file_md5: str) -> list[dict]:
        """Get version history for truth entry"""
```

#### NEW: ConfigStore Protocol

```python
@runtime_checkable
class ConfigStore(Protocol):
    """Interface for configuration storage (users, sessions, prompts)"""

    # Users
    def load_users(self) -> list[User]:
        """Load all users"""

    def save_users(self, users: list[User]) -> None:
        """Save all users"""

    # Sessions
    def load_sessions(self) -> dict[str, Session]:
        """Load all sessions"""

    def save_sessions(self, sessions: dict[str, Session]) -> None:
        """Save all sessions"""

    # Prompt configs
    def load_prompt_configs(self) -> list[PromptConfig]:
        """Load all prompt configurations"""

    def save_prompt_configs(self, configs: list[PromptConfig]) -> None:
        """Save all prompt configurations"""

    def get_config_history(self) -> list[dict]:
        """Get configuration change history"""

    def log_config_change(self, action: str, config_id: str,
                          snapshot: list[PromptConfig]) -> None:
        """Log configuration change to history"""
```

#### NEW: ComplianceStore Protocol

```python
@runtime_checkable
class ComplianceStore(Protocol):
    """Interface for compliance/audit logging"""

    def log_decision(self, decision: dict) -> None:
        """Log human decision (append-only)"""

    def log_llm_call(self, call_data: dict) -> None:
        """Log LLM call (append-only)"""

    def get_decision_log(self, filters: dict = None) -> list[dict]:
        """Query decision log"""

    def get_llm_call_log(self, filters: dict = None) -> list[dict]:
        """Query LLM call log"""
```

### Extended StorageFacade

```python
@dataclass(frozen=True)
class StorageFacade:
    doc_store: DocStore
    label_store: LabelStore
    run_store: RunStore
    pending_store: PendingStore      # NEW
    truth_store: TruthStore          # NEW
    config_store: ConfigStore        # NEW
    compliance_store: ComplianceStore  # NEW

    @classmethod
    def from_storage(cls, storage: FileStorage) -> "StorageFacade":
        return cls(
            doc_store=storage,
            label_store=storage,
            run_store=storage,
            pending_store=storage,
            truth_store=storage,
            config_store=storage,
            compliance_store=storage,
        )
```

---

## File-by-File Refactoring Plan

### 1. `api/services/claims.py` (HIGH - 18 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 50-51 | `open(meta_path)` | `storage.doc_store.get_doc_metadata(doc_id)` |
| 80-81 | `open(summary_path)` | `storage.run_store.get_run_summary(run_id)` |
| 88 | `glob("*.json")` | `storage.run_store.list_extractions(run_id)` |
| 90-91 | `open(ext_file)` | `storage.run_store.get_extraction(run_id, doc_id)` |
| 160, 166, 176 | `open(manifest/summary)` | `storage.run_store.get_run_manifest/summary(run_id)` |
| 210, 212-213 | `glob + open` | `storage.run_store.list_extractions() + get_extraction()` |
| 220 | `glob("*.labels.json")` | `storage.label_store.count_labels_for_run(run_id)` |
| 277-278, 289-290 | `open(meta/extraction)` | Use storage methods |
| 339-340 | `open(summary_path)` | `storage.run_store.get_run_summary(run_id)` |
| 31, 41, 45, 364 | `iterdir()` | `storage.list_claims()` (already exists) |
| 30+ `exists()` checks | Path checks | Storage methods return `None` for missing |

**Refactoring Steps:**
1. Inject `StorageFacade` in constructor (already done partially)
2. Replace all `open()` calls with storage method calls
3. Replace `glob()` with storage list methods
4. Remove `exists()` checks - storage returns `None`

**Estimated Effort:** 3-4 hours

---

### 2. `api/services/documents.py` (HIGH - 22 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 53-54, 102-103, 359-360 | `open(meta_path)` | `storage.doc_store.get_doc_metadata(doc_id)` |
| 65-66, 390-391 | `open(extraction_path)` | `storage.run_store.get_extraction(run_id, doc_id)` |
| 113-114 | `open(pages_json)` | `storage.doc_store.get_doc_text(doc_id)` (exists!) |
| 136-141, 189-194 | `iterdir(source_dir)` | `storage.doc_store.get_source_files(doc_id)` |
| 244-245 | `open(azure_di.json)` | `storage.doc_store.get_doc_azure_di(doc_id)` |
| 286-287, 295 | `open(manifest)` | `storage.run_store.get_run_manifest(run_id)` |
| 43, 262, 331, 349, 452 | `iterdir()` | `storage.list_docs()`, `storage.list_runs()` |
| 28+ `exists()`/`is_dir()` checks | Path checks | Storage methods return `None` |

**Refactoring Steps:**
1. Already has `storage_factory` injection
2. Replace metadata reads with `get_doc_metadata()`
3. Replace extraction reads with `get_extraction()` (already in protocol!)
4. Add `get_doc_azure_di()` method for Azure DI data
5. Add `get_source_files()` for source discovery
6. Remove path existence checks

**Estimated Effort:** 4-5 hours

---

### 3. `api/services/pipeline.py` (HIGH - 8 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 517-518 | `open(manifest_path)` | `storage.run_store.get_run_manifest(run_id)` |
| 524-525 | `open(summary_path)` | `storage.run_store.get_run_summary(run_id)` |
| 729-730 | `json.dump(manifest)` | `storage.run_store.save_run_manifest(run_id, manifest)` |
| 744-745 | `json.dump(summary)` | `storage.run_store.save_run_summary(run_id, summary)` |
| 748 | `touch(.complete)` | `storage.run_store.mark_run_complete(run_id)` |
| 811-812 | JSONL append | `storage.run_store.append_run_index(record)` |

**Refactoring Steps:**
1. Add write methods to `RunStore` protocol
2. Implement atomic writes in `FileStorage`
3. Replace all reads/writes with storage calls
4. Handle index appending through storage

**Estimated Effort:** 2-3 hours

---

### 4. `api/services/upload.py` (HIGH - 10 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 101-102 | `open(manifest)` read | `storage.pending_store.get_pending_manifest(claim_id)` |
| 121-122 | `json.dump(manifest)` | `storage.pending_store.save_pending_manifest(claim_id, data)` |
| 217 | `write_bytes(content)` | `storage.pending_store.save_pending_document(...)` |
| 256 | `unlink()` | `storage.pending_store.delete_pending_document(...)` |
| 291 | `shutil.rmtree()` | `storage.pending_store.delete_pending_claim(claim_id)` |
| 305 | `iterdir(staging)` | `storage.pending_store.list_pending_claims()` |
| 356 | `shutil.rmtree(input)` | `storage.pending_store.cleanup_input_dir(claim_id)` |

**Refactoring Steps:**
1. Create new `PendingStore` protocol
2. Implement in `FileStorage`
3. Add to `StorageFacade`
4. Replace all staging operations

**Estimated Effort:** 3-4 hours

---

### 5. `api/services/truth.py` (MEDIUM - 12 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 64-65 | `open(truth_path)` | `storage.truth_store.get_truth(file_md5)` |
| 132, 142 | `iterdir(truth_root)` | `storage.truth_store.list_truth_entries()` |
| 162, 170 | `iterdir(claims)` | `storage.list_claims()` |
| 177-178, 344-347 | `open(meta/label)` | `storage.doc_store.get_doc_metadata()`, `storage.label_store.get_label()` |

**Refactoring Steps:**
1. Extend `TruthStore` class to implement protocol
2. Add `list_truth_entries()` method
3. Replace all direct reads with storage calls

**Estimated Effort:** 2-3 hours

---

### 6. `api/services/evolution.py` (LOW - 2 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 211 | `exists(eval_path)` | Check return value |
| 215-216 | `open(eval_summary)` | `storage.run_store.get_eval_summary(run_id)` |

**Refactoring Steps:**
1. Add `get_eval_summary()` to `RunStore`
2. Simple 2-line change

**Estimated Effort:** 30 minutes

---

### 7. `api/services/auth.py` (LOW - 4 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 57-59 | `open(sessions)` read | `storage.config_store.load_sessions()` |
| 68-73 | `json.dump(sessions)` | `storage.config_store.save_sessions(sessions)` |

**Refactoring Steps:**
1. Add session methods to `ConfigStore`
2. Replace file operations

**Estimated Effort:** 30 minutes

---

### 8. `api/services/users.py` (LOW - 4 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 113-115 | `open(users)` read | `storage.config_store.load_users()` |
| 124-125 | `json.dump(users)` | `storage.config_store.save_users(users)` |

**Refactoring Steps:**
1. Add user methods to `ConfigStore`
2. Replace file operations

**Estimated Effort:** 30 minutes

---

### 9. `api/services/prompt_config.py` (LOW - 6 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 92-94 | `open(configs)` read | `storage.config_store.load_prompt_configs()` |
| 108-109 | `json.dump(configs)` | `storage.config_store.save_prompt_configs(configs)` |
| 131-132 | JSONL append | `storage.config_store.log_config_change(...)` |
| 143-147 | JSONL read loop | `storage.config_store.get_config_history()` |

**Refactoring Steps:**
1. Add prompt config methods to `ConfigStore`
2. Handle JSONL history through storage layer

**Estimated Effort:** 1 hour

---

### 10. `pipeline/writer.py` (MEDIUM - 5 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 16-17 | `json.dump()` | `storage.write_json(path, data)` |
| 22-24 | Atomic JSON write | `storage.write_json_atomic(path, data)` |
| 28 | `write_text()` | `storage.write_text(path, text)` |
| 32 | `shutil.copy2()` | `storage.copy_file(src, dest)` |
| 36 | `touch()` | `storage.touch(path)` |

**Refactoring Steps:**
1. Add generic write helpers to storage layer
2. Update `ResultWriter` to use storage
3. Or: Route all pipeline writes through `RunStore`

**Estimated Effort:** 1-2 hours

---

### 11. `services/compliance/crypto.py` (LOW - 3 operations)

**Current Direct I/O:**
| Line | Operation | Replace With |
|------|-----------|--------------|
| 127 | `read_bytes(kek_path)` | `storage.encryption_store.load_key(path)` |
| 323, 325, 327 | `write_bytes/text()` | `storage.encryption_store.save_key(...)` |

**Refactoring Steps:**
1. Create optional `EncryptionStore` protocol
2. Implement key loading/saving

**Estimated Effort:** 30 minutes

---

## Implementation Phases

### Phase 1: Protocol Extensions (Day 1)
**Files:** `storage/protocol.py`, `storage/models.py`

1. Add `DocStore` extensions:
   - `get_doc_metadata(doc_id) -> Optional[dict]`
   - `get_doc_azure_di(doc_id) -> Optional[dict]`
   - `get_source_files(doc_id) -> list[SourceFile]`

2. Add `RunStore` extensions:
   - `get_run_manifest(run_id) -> Optional[dict]`
   - `get_run_summary(run_id) -> Optional[dict]`
   - `list_extractions(run_id) -> list[ExtractionRef]`
   - `get_eval_summary(run_id) -> Optional[dict]`
   - `save_run_manifest(run_id, data) -> None`
   - `save_run_summary(run_id, data) -> None`
   - `save_extraction(run_id, doc_id, data) -> None`
   - `mark_run_complete(run_id) -> None`
   - `append_run_index(record) -> None`

3. Create new protocols:
   - `PendingStore` (staging operations)
   - `TruthStore` (already exists as class, make it a protocol)
   - `ConfigStore` (users, sessions, prompt configs)

**Estimated Effort:** 4 hours

---

### Phase 2: FileStorage Implementation (Day 1-2)
**Files:** `storage/filesystem.py`

1. Implement all new `DocStore` methods
2. Implement all new `RunStore` methods
3. Implement `PendingStore` interface
4. Implement `ConfigStore` interface
5. Ensure all writes are atomic (temp + rename)
6. Add proper error handling

**Estimated Effort:** 6 hours

---

### Phase 3: Refactor HIGH Priority Services (Day 2-3)
**Files:** `claims.py`, `documents.py`, `pipeline.py`, `upload.py`

1. Update `ClaimsService` (3-4 hours)
2. Update `DocumentsService` (4-5 hours)
3. Update `PipelineService` (2-3 hours)
4. Update `UploadService` (3-4 hours)

**Estimated Effort:** 12-16 hours

---

### Phase 4: Refactor MEDIUM/LOW Priority Services (Day 3-4)
**Files:** `truth.py`, `evolution.py`, `auth.py`, `users.py`, `prompt_config.py`, `writer.py`, `crypto.py`

1. Update `TruthService` (2-3 hours)
2. Update `EvolutionService` (30 min)
3. Update `AuthService` (30 min)
4. Update `UsersService` (30 min)
5. Update `PromptConfigService` (1 hour)
6. Update `ResultWriter` (1-2 hours)
7. Update crypto operations (30 min)

**Estimated Effort:** 6-8 hours

---

### Phase 5: Testing & Validation (Day 4-5)
1. Unit tests for new protocol methods
2. Integration tests for refactored services
3. End-to-end workflow testing
4. Performance benchmarking

**Estimated Effort:** 8 hours

---

## Effort Estimation

### Summary by Phase

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Protocol Extensions | 4 hours |
| 2 | FileStorage Implementation | 6 hours |
| 3 | HIGH Priority Refactoring | 12-16 hours |
| 4 | MEDIUM/LOW Priority Refactoring | 6-8 hours |
| 5 | Testing & Validation | 8 hours |
| **Total** | | **36-42 hours** |

### Summary by File

| File | Effort | Priority |
|------|--------|----------|
| `storage/protocol.py` | 2 hours | P0 |
| `storage/models.py` | 1 hour | P0 |
| `storage/filesystem.py` | 6 hours | P0 |
| `storage/facade.py` | 1 hour | P0 |
| `api/services/claims.py` | 4 hours | P1 |
| `api/services/documents.py` | 5 hours | P1 |
| `api/services/pipeline.py` | 3 hours | P1 |
| `api/services/upload.py` | 4 hours | P1 |
| `api/services/truth.py` | 3 hours | P2 |
| `api/services/evolution.py` | 0.5 hours | P3 |
| `api/services/auth.py` | 0.5 hours | P3 |
| `api/services/users.py` | 0.5 hours | P3 |
| `api/services/prompt_config.py` | 1 hour | P3 |
| `pipeline/writer.py` | 2 hours | P2 |
| `services/compliance/crypto.py` | 0.5 hours | P3 |
| Testing | 8 hours | P1 |

### Timeline

| Day | Activities |
|-----|------------|
| Day 1 | Protocol extensions + FileStorage implementation |
| Day 2 | Claims + Documents service refactoring |
| Day 3 | Pipeline + Upload service refactoring |
| Day 4 | Remaining services + ResultWriter |
| Day 5 | Testing and validation |

**Total: 5 working days (1 week)**

---

## Risk Assessment

### Low Risk
| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | Incremental refactoring with tests |
| Performance regression | Storage methods delegate to same file ops |
| API response changes | Protocol returns same data types |

### Medium Risk
| Risk | Mitigation |
|------|------------|
| Missing edge cases | Comprehensive test coverage |
| Atomic write failures | Use same temp+rename pattern |
| Index inconsistency | Keep same JSONL format initially |

### Mitigation Strategy
1. **Incremental approach**: Refactor one service at a time
2. **Feature flags**: Can fall back to direct I/O if needed
3. **Parallel testing**: Run old and new code paths simultaneously
4. **Comprehensive logging**: Track all storage operations

---

## Post-Refactoring Benefits

### For Database Swap
Once abstraction is complete:

| Task | Effort (Before) | Effort (After) |
|------|-----------------|----------------|
| Implement Supabase backend | 3-4 weeks | 1 week |
| Implement MongoDB backend | 2-3 weeks | 3-4 days |
| Implement SQLite backend | 1-2 weeks | 2-3 days |

### Other Benefits
1. **Testability**: Mock storage in unit tests
2. **Maintainability**: Single point of change for storage logic
3. **Consistency**: All storage operations use same patterns
4. **Auditability**: Easier to add logging/metrics
5. **Multi-tenancy**: Simpler workspace isolation

---

## Appendix: Protocol Method Reference

### Complete Protocol Interface (After Refactoring)

```python
# src/context_builder/storage/protocol.py

@runtime_checkable
class DocStore(Protocol):
    # Discovery
    def list_claims(self) -> list[ClaimRef]: ...
    def list_docs(self, claim_id: str) -> list[DocRef]: ...

    # Read
    def get_doc(self, doc_id: str) -> Optional[DocBundle]: ...
    def get_doc_metadata(self, doc_id: str) -> Optional[dict]: ...
    def get_doc_text(self, doc_id: str) -> Optional[DocText]: ...
    def get_doc_azure_di(self, doc_id: str) -> Optional[dict]: ...
    def get_doc_source_path(self, doc_id: str) -> Optional[Path]: ...
    def get_source_files(self, doc_id: str) -> list[SourceFile]: ...
    def find_doc_claim(self, doc_id: str) -> Optional[str]: ...


@runtime_checkable
class RunStore(Protocol):
    # Discovery
    def list_runs(self) -> list[RunRef]: ...
    def list_extractions(self, run_id: str) -> list[ExtractionRef]: ...

    # Read
    def get_run(self, run_id: str) -> Optional[RunBundle]: ...
    def get_run_manifest(self, run_id: str) -> Optional[dict]: ...
    def get_run_summary(self, run_id: str) -> Optional[dict]: ...
    def get_run_metrics(self, run_id: str) -> Optional[dict]: ...
    def get_extraction(self, run_id: str, doc_id: str) -> Optional[dict]: ...
    def get_eval_summary(self, run_id: str) -> Optional[dict]: ...

    # Write
    def save_run_manifest(self, run_id: str, manifest: dict) -> None: ...
    def save_run_summary(self, run_id: str, summary: dict) -> None: ...
    def save_extraction(self, run_id: str, doc_id: str, data: dict) -> None: ...
    def mark_run_complete(self, run_id: str) -> None: ...
    def append_run_index(self, record: dict) -> None: ...


@runtime_checkable
class LabelStore(Protocol):
    # Read
    def get_label(self, doc_id: str, claim_id: Optional[str] = None) -> Optional[dict]: ...
    def get_label_summary(self, doc_id: str) -> Optional[LabelSummary]: ...
    def get_label_history(self, doc_id: str) -> list[dict]: ...

    # Write
    def save_label(self, doc_id: str, label_data: dict) -> None: ...


@runtime_checkable
class PendingStore(Protocol):
    # Discovery
    def list_pending_claims(self) -> list[PendingClaimRef]: ...

    # Read
    def get_pending_manifest(self, claim_id: str) -> Optional[PendingManifest]: ...

    # Write
    def save_pending_manifest(self, claim_id: str, manifest: dict) -> None: ...
    def save_pending_document(self, claim_id: str, doc_id: str,
                               filename: str, content: bytes) -> None: ...

    # Delete
    def delete_pending_document(self, claim_id: str, doc_id: str) -> bool: ...
    def delete_pending_claim(self, claim_id: str) -> bool: ...
    def cleanup_input_dir(self, claim_id: str) -> None: ...


@runtime_checkable
class TruthStore(Protocol):
    # Discovery
    def list_truth_entries(self) -> list[TruthRef]: ...

    # Read
    def get_truth(self, file_md5: str) -> Optional[dict]: ...
    def get_truth_history(self, file_md5: str) -> list[dict]: ...

    # Write
    def save_truth(self, file_md5: str, data: dict) -> None: ...


@runtime_checkable
class ConfigStore(Protocol):
    # Users
    def load_users(self) -> list[User]: ...
    def save_users(self, users: list[User]) -> None: ...

    # Sessions
    def load_sessions(self) -> dict[str, Session]: ...
    def save_sessions(self, sessions: dict[str, Session]) -> None: ...

    # Prompt configs
    def load_prompt_configs(self) -> list[PromptConfig]: ...
    def save_prompt_configs(self, configs: list[PromptConfig]) -> None: ...
    def get_config_history(self) -> list[dict]: ...
    def log_config_change(self, action: str, config_id: str,
                          snapshot: list[PromptConfig]) -> None: ...


@runtime_checkable
class Storage(Protocol):
    """Complete storage interface combining all protocols"""
    # Inherits all methods from DocStore, RunStore, LabelStore,
    # PendingStore, TruthStore, ConfigStore

    # Index operations
    def has_indexes(self) -> bool: ...
    def get_index_meta(self) -> Optional[dict]: ...
    def invalidate_indexes(self) -> None: ...
```

---

## Conclusion

This refactoring represents **5 days of focused work** to properly abstract all storage operations. The result will be:

1. **Clean protocol-based architecture** with 6 distinct store interfaces
2. **Zero direct file I/O** in API services
3. **Single implementation point** for any backend swap
4. **Reduced backend swap effort** from 3-4 weeks to 3-4 days

The investment is worthwhile if you plan to support multiple storage backends (Supabase, MongoDB, etc.) or need better testability and maintainability.
