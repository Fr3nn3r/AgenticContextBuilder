# Compliance Storage Backends - Phased Implementation Plan

**Source:** `tasks/0_todo/compliance-storage-implementation-plan.md`
**Created:** 2026-01-14
**Constraint:** Each phase achievable in single 200K context window (write tests, don't run)

---

## Current State Summary

### Existing Components
| Component | Location | Purpose |
|-----------|----------|---------|
| `DecisionLedger` | `services/decision_ledger.py` | Append-only JSONL with SHA-256 hash chain |
| `LLMAuditService` | `services/llm_audit.py` | LLM call logging (append-only JSONL) |
| `AuditedOpenAIClient` | `services/llm_audit.py` | Wrapper that auto-logs OpenAI calls |
| `DecisionRecord` | `schemas/decision_record.py` | Main decision schema with hash fields |
| `LLMCallRecord` | `services/llm_audit.py` | Dataclass for LLM call details |

### Storage Locations
- `output/logs/decisions.jsonl` - Decision ledger (hash-chained)
- `output/logs/llm_calls.jsonl` - LLM audit log

### Integration Points
- `classification/openai_classifier.py` - Creates DecisionLedger + AuditedOpenAIClient
- `extraction/extractors/generic.py` - Creates DecisionLedger + AuditedOpenAIClient
- `api/main.py` - Compliance endpoints (verify, list decisions)

---

## Phase 1: Storage Interfaces & Protocols

**Estimated context:** ~60K tokens
**Goal:** Define abstract interfaces that all backends must implement

### Tasks

1. **Create `services/compliance/interfaces.py`**
   ```python
   # Protocols for Decision Storage
   class DecisionAppender(Protocol):
       def append(self, record: DecisionRecord) -> DecisionRecord: ...

   class DecisionReader(Protocol):
       def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]: ...
       def query(self, filters: Optional[DecisionQuery] = None) -> List[DecisionRecord]: ...
       def count(self) -> int: ...

   class DecisionVerifier(Protocol):
       def verify_integrity(self) -> IntegrityReport: ...

   # Protocols for LLM Audit Storage
   class LLMCallSink(Protocol):
       def log_call(self, record: LLMCallRecord) -> None: ...

   class LLMCallReader(Protocol):
       def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]: ...
       def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]: ...

   # Combined interface for convenience
   class DecisionStorage(DecisionAppender, DecisionReader, DecisionVerifier, Protocol):
       pass

   class LLMCallStorage(LLMCallSink, LLMCallReader, Protocol):
       pass
   ```

2. **Create `services/compliance/factories.py`**
   ```python
   class DecisionRecordFactory:
       """Centralized factory for creating DecisionRecord instances with proper hashing."""

       def __init__(self, get_previous_hash: Callable[[], str]):
           self._get_previous_hash = get_previous_hash

       def create_classification_decision(...) -> DecisionRecord: ...
       def create_extraction_decision(...) -> DecisionRecord: ...
       def create_quality_gate_decision(...) -> DecisionRecord: ...
       def create_human_review_decision(...) -> DecisionRecord: ...
       def create_override_decision(...) -> DecisionRecord: ...

       @staticmethod
       def compute_hash(record: DecisionRecord) -> str: ...
   ```

3. **Create `services/compliance/__init__.py`**
   - Export all protocols and factories

4. **Move `LLMCallRecord` to schemas**
   - Create `schemas/llm_call_record.py`
   - Move dataclass from `services/llm_audit.py`
   - Keep backward-compatible import in `services/llm_audit.py`

### Unit Tests
- `tests/unit/test_compliance_interfaces.py`
  - Type checking tests (verify classes implement protocols)
  - Factory method signature tests
  - Hash computation tests

### Files to Create
- `src/context_builder/services/compliance/__init__.py`
- `src/context_builder/services/compliance/interfaces.py`
- `src/context_builder/services/compliance/factories.py`
- `src/context_builder/schemas/llm_call_record.py`
- `tests/unit/test_compliance_interfaces.py`

### Files to Modify
- `src/context_builder/services/llm_audit.py` (add re-export)
- `src/context_builder/schemas/__init__.py` (export new schema)

---

## Phase 2: File Backend - Decision Services

**Estimated context:** ~80K tokens
**Goal:** Split DecisionLedger into interface-implementing components

### Tasks

1. **Create `services/compliance/file/decision_storage.py`**
   ```python
   class FileDecisionAppender(DecisionAppender):
       """Append-only file storage with hash chain."""
       def __init__(self, storage_path: Path): ...
       def append(self, record: DecisionRecord) -> DecisionRecord: ...
       def _get_last_hash(self) -> str: ...
       def _atomic_append(self, line: str) -> None: ...

   class FileDecisionReader(DecisionReader):
       """Read-only query interface for decision JSONL."""
       def __init__(self, storage_path: Path): ...
       def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]: ...
       def query(self, filters: Optional[DecisionQuery] = None) -> List[DecisionRecord]: ...
       def count(self) -> int: ...

   class FileDecisionVerifier(DecisionVerifier):
       """Hash chain integrity verification."""
       def __init__(self, storage_path: Path): ...
       def verify_integrity(self) -> IntegrityReport: ...

   class FileDecisionStorage(DecisionStorage):
       """Combined implementation using composition."""
       def __init__(self, storage_dir: Path):
           self._path = storage_dir / "decisions.jsonl"
           self._appender = FileDecisionAppender(self._path)
           self._reader = FileDecisionReader(self._path)
           self._verifier = FileDecisionVerifier(self._path)

       # Delegate all methods
   ```

2. **Create `services/compliance/file/__init__.py`**
   - Export file backend classes

3. **Update `services/decision_ledger.py`**
   ```python
   # Keep DecisionLedger as facade for backwards compatibility
   class DecisionLedger:
       """Facade maintaining existing API using new implementations."""
       def __init__(self, storage_dir: Path):
           self._storage = FileDecisionStorage(storage_dir)

       def append(self, record): return self._storage.append(record)
       def verify_integrity(self): return self._storage.verify_integrity()
       def query(self, filters=None): return self._storage.query(filters)
       def get_by_id(self, id): return self._storage.get_by_id(id)
       def count(self): return self._storage.count()
   ```

### Unit Tests
- `tests/unit/test_file_decision_storage.py`
  - FileDecisionAppender: append, hash chain, atomic write
  - FileDecisionReader: get_by_id, query with filters, count
  - FileDecisionVerifier: valid chain, tampered chain, empty file
  - FileDecisionStorage: combined operations
  - DecisionLedger facade: backwards compatibility

### Files to Create
- `src/context_builder/services/compliance/file/__init__.py`
- `src/context_builder/services/compliance/file/decision_storage.py`
- `tests/unit/test_file_decision_storage.py`

### Files to Modify
- `src/context_builder/services/decision_ledger.py` (refactor to facade)
- `src/context_builder/services/compliance/__init__.py` (export file backend)

---

## Phase 3: File Backend - LLM Audit Services

**Estimated context:** ~70K tokens
**Goal:** Split LLMAuditService into interface-implementing components

### Tasks

1. **Create `services/compliance/file/llm_storage.py`**
   ```python
   class FileLLMCallSink(LLMCallSink):
       """Append-only LLM call logging."""
       def __init__(self, storage_path: Path): ...
       def log_call(self, record: LLMCallRecord) -> None: ...

   class FileLLMCallReader(LLMCallReader):
       """Query interface for LLM call logs."""
       def __init__(self, storage_path: Path): ...
       def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]: ...
       def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]: ...

   class FileLLMCallStorage(LLMCallStorage):
       """Combined implementation."""
       def __init__(self, storage_dir: Path):
           self._path = storage_dir / "llm_calls.jsonl"
           self._sink = FileLLMCallSink(self._path)
           self._reader = FileLLMCallReader(self._path)
   ```

2. **Update `services/llm_audit.py`**
   ```python
   class LLMAuditService:
       """Facade maintaining existing API."""
       def __init__(self, storage_dir: Path):
           self._storage = FileLLMCallStorage(storage_dir)

       def log_call(self, record): self._storage.log_call(record)
       def get_by_id(self, id): return self._storage.get_by_id(id)
       def query_by_decision(self, id): return self._storage.query_by_decision(id)

   class AuditedOpenAIClient:
       """Updated to accept LLMCallSink interface."""
       def __init__(self, client: OpenAI, sink: LLMCallSink, storage_dir: Optional[Path] = None):
           self._client = client
           self._sink = sink  # Now interface-based
           # ... rest unchanged
   ```

3. **Update factory functions**
   ```python
   def get_llm_audit_service(storage_dir: Optional[Path] = None) -> LLMAuditService:
       # Keep singleton behavior, use new implementation internally

   def create_audited_client(
       storage_dir: Optional[Path] = None,
       sink: Optional[LLMCallSink] = None,  # Allow injection
   ) -> AuditedOpenAIClient:
       ...
   ```

### Unit Tests
- `tests/unit/test_file_llm_storage.py`
  - FileLLMCallSink: log_call, atomic write
  - FileLLMCallReader: get_by_id, query_by_decision
  - FileLLMCallStorage: combined operations
  - LLMAuditService facade: backwards compatibility
  - AuditedOpenAIClient: interface injection

### Files to Create
- `src/context_builder/services/compliance/file/llm_storage.py`
- `tests/unit/test_file_llm_storage.py`

### Files to Modify
- `src/context_builder/services/llm_audit.py` (refactor to facade)
- `src/context_builder/services/compliance/file/__init__.py` (export LLM storage)

---

## Phase 4: Configuration & Composition Root

**Estimated context:** ~70K tokens
**Goal:** Add configuration and factory for backend selection

### Tasks

1. **Create `services/compliance/config.py`**
   ```python
   from enum import Enum
   from pydantic import BaseModel

   class StorageBackendType(str, Enum):
       FILE = "file"
       ENCRYPTED_FILE = "encrypted_file"
       S3 = "s3"
       DATABASE = "database"

   class ComplianceStorageConfig(BaseModel):
       """Configuration for compliance storage backends."""
       backend_type: StorageBackendType = StorageBackendType.FILE
       storage_dir: Path = Path("output/logs")

       # Encrypted backend options
       encryption_key_path: Optional[Path] = None
       encryption_algorithm: str = "AES-256-GCM"

       # S3 backend options (future)
       s3_bucket: Optional[str] = None
       s3_prefix: Optional[str] = None
       s3_region: Optional[str] = None

       # Database backend options (future)
       database_url: Optional[str] = None

       class Config:
           extra = "forbid"
   ```

2. **Create `services/compliance/factory.py`**
   ```python
   class ComplianceStorageFactory:
       """Factory for creating storage implementations based on config."""

       @staticmethod
       def create_decision_storage(config: ComplianceStorageConfig) -> DecisionStorage:
           if config.backend_type == StorageBackendType.FILE:
               return FileDecisionStorage(config.storage_dir)
           elif config.backend_type == StorageBackendType.ENCRYPTED_FILE:
               return EncryptedDecisionStorage(config.storage_dir, config.encryption_key_path)
           # Future: S3, DATABASE
           raise ValueError(f"Unsupported backend: {config.backend_type}")

       @staticmethod
       def create_llm_storage(config: ComplianceStorageConfig) -> LLMCallStorage:
           if config.backend_type == StorageBackendType.FILE:
               return FileLLMCallStorage(config.storage_dir)
           elif config.backend_type == StorageBackendType.ENCRYPTED_FILE:
               return EncryptedLLMCallStorage(config.storage_dir, config.encryption_key_path)
           raise ValueError(f"Unsupported backend: {config.backend_type}")

       @staticmethod
       def create_all(config: ComplianceStorageConfig) -> Tuple[DecisionStorage, LLMCallStorage]:
           return (
               ComplianceStorageFactory.create_decision_storage(config),
               ComplianceStorageFactory.create_llm_storage(config),
           )
   ```

3. **Update API entry points (`api/main.py`)**
   ```python
   # Add config loading
   _compliance_config: Optional[ComplianceStorageConfig] = None

   def get_compliance_config() -> ComplianceStorageConfig:
       global _compliance_config
       if _compliance_config is None:
           # Load from env or config file
           _compliance_config = ComplianceStorageConfig(
               storage_dir=Path(_PROJECT_ROOT / "output" / "logs")
           )
       return _compliance_config

   def get_decision_storage() -> DecisionStorage:
       config = get_compliance_config()
       return ComplianceStorageFactory.create_decision_storage(config)

   # Update endpoints to use factory
   @app.get("/api/compliance/ledger/verify")
   def verify_decision_ledger():
       storage = get_decision_storage()
       return storage.verify_integrity()
   ```

4. **Update pipeline entry points**
   - `classification/openai_classifier.py`: Accept optional `DecisionStorage` and `LLMCallSink`
   - `extraction/extractors/generic.py`: Accept optional `DecisionStorage` and `LLMCallSink`
   - Remove direct instantiation of DecisionLedger/LLMAuditService

### Unit Tests
- `tests/unit/test_compliance_config.py`
  - Config validation, defaults, serialization
- `tests/unit/test_compliance_factory.py`
  - Factory creates correct backends
  - Invalid config raises errors

### Files to Create
- `src/context_builder/services/compliance/config.py`
- `src/context_builder/services/compliance/factory.py`
- `tests/unit/test_compliance_config.py`
- `tests/unit/test_compliance_factory.py`

### Files to Modify
- `src/context_builder/api/main.py` (add DI for compliance)
- `src/context_builder/classification/openai_classifier.py` (accept interfaces)
- `src/context_builder/extraction/extractors/generic.py` (accept interfaces)
- `src/context_builder/services/compliance/__init__.py` (export config/factory)

---

## Phase 5: Encrypted Local Backend

**Estimated context:** ~90K tokens
**Goal:** Implement encrypted file storage with envelope encryption

### Design Decisions
- **Envelope encryption:** Each record encrypted with unique DEK, DEK encrypted with KEK
- **Hash chain:** Computed over plaintext before encryption (preserves verification)
- **Key storage:** KEK loaded from file path in config
- **Algorithm:** AES-256-GCM for authenticated encryption

### Tasks

1. **Create `services/compliance/crypto.py`**
   ```python
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   import os

   class EnvelopeEncryptor:
       """Envelope encryption for compliance records."""

       def __init__(self, kek_path: Path):
           self._kek = self._load_kek(kek_path)

       def encrypt(self, plaintext: bytes) -> bytes:
           """Encrypt with new DEK, return DEK||nonce||ciphertext."""
           dek = AESGCM.generate_key(bit_length=256)
           nonce = os.urandom(12)
           ciphertext = AESGCM(dek).encrypt(nonce, plaintext, None)
           encrypted_dek = AESGCM(self._kek).encrypt(os.urandom(12), dek, None)
           return encrypted_dek + nonce + ciphertext

       def decrypt(self, blob: bytes) -> bytes:
           """Decrypt envelope-encrypted data."""
           # Parse and decrypt DEK, then decrypt payload
   ```

2. **Create `services/compliance/encrypted/__init__.py`**

3. **Create `services/compliance/encrypted/decision_storage.py`**
   ```python
   class EncryptedDecisionAppender(DecisionAppender):
       def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor): ...
       def append(self, record: DecisionRecord) -> DecisionRecord:
           # 1. Compute hash chain over plaintext
           # 2. Serialize record
           # 3. Encrypt serialized JSON
           # 4. Base64 encode and write

   class EncryptedDecisionReader(DecisionReader):
       def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor): ...
       def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
           # Decrypt each line, deserialize, search

   class EncryptedDecisionVerifier(DecisionVerifier):
       def __init__(self, storage_path: Path, encryptor: EnvelopeEncryptor): ...
       def verify_integrity(self) -> IntegrityReport:
           # Decrypt, then verify hash chain over plaintext

   class EncryptedDecisionStorage(DecisionStorage):
       """Combined encrypted implementation."""
   ```

4. **Create `services/compliance/encrypted/llm_storage.py`**
   ```python
   class EncryptedLLMCallSink(LLMCallSink): ...
   class EncryptedLLMCallReader(LLMCallReader): ...
   class EncryptedLLMCallStorage(LLMCallStorage): ...
   ```

5. **Update factory**
   ```python
   # In factory.py
   elif config.backend_type == StorageBackendType.ENCRYPTED_FILE:
       encryptor = EnvelopeEncryptor(config.encryption_key_path)
       return EncryptedDecisionStorage(config.storage_dir, encryptor)
   ```

### Unit Tests
- `tests/unit/test_envelope_encryption.py`
  - Encrypt/decrypt roundtrip
  - Invalid key fails
  - Tampered ciphertext fails
- `tests/unit/test_encrypted_decision_storage.py`
  - All DecisionStorage operations with encryption
  - Hash chain verification works through encryption
- `tests/unit/test_encrypted_llm_storage.py`
  - All LLMCallStorage operations with encryption

### Files to Create
- `src/context_builder/services/compliance/crypto.py`
- `src/context_builder/services/compliance/encrypted/__init__.py`
- `src/context_builder/services/compliance/encrypted/decision_storage.py`
- `src/context_builder/services/compliance/encrypted/llm_storage.py`
- `tests/unit/test_envelope_encryption.py`
- `tests/unit/test_encrypted_decision_storage.py`
- `tests/unit/test_encrypted_llm_storage.py`

### Files to Modify
- `src/context_builder/services/compliance/factory.py` (add encrypted backend)
- `src/context_builder/services/compliance/__init__.py` (export encrypted)

---

## Phase 6: Contract Test Suite

**Estimated context:** ~70K tokens
**Goal:** Create reusable contract tests for all backend implementations

### Tasks

1. **Create `tests/contract/__init__.py`**

2. **Create `tests/contract/decision_storage_contract.py`**
   ```python
   import pytest
   from abc import ABC, abstractmethod

   class DecisionStorageContractTests(ABC):
       """Contract tests that any DecisionStorage must pass."""

       @abstractmethod
       def create_storage(self) -> DecisionStorage:
           """Create a fresh storage instance for testing."""
           pass

       @pytest.fixture
       def storage(self) -> DecisionStorage:
           return self.create_storage()

       # === Appender Contract ===
       def test_append_returns_record_with_hash(self, storage): ...
       def test_append_links_to_previous_hash(self, storage): ...
       def test_append_is_atomic(self, storage): ...
       def test_first_record_has_genesis_previous(self, storage): ...

       # === Reader Contract ===
       def test_get_by_id_returns_appended_record(self, storage): ...
       def test_get_by_id_returns_none_for_missing(self, storage): ...
       def test_query_returns_all_without_filters(self, storage): ...
       def test_query_filters_by_decision_type(self, storage): ...
       def test_query_filters_by_claim_id(self, storage): ...
       def test_query_filters_by_doc_id(self, storage): ...
       def test_query_respects_limit(self, storage): ...
       def test_count_returns_correct_number(self, storage): ...

       # === Verifier Contract ===
       def test_verify_empty_is_valid(self, storage): ...
       def test_verify_single_record_is_valid(self, storage): ...
       def test_verify_chain_is_valid(self, storage): ...
       def test_verify_detects_hash_mismatch(self, storage): ...
       def test_verify_detects_chain_break(self, storage): ...
   ```

3. **Create `tests/contract/llm_storage_contract.py`**
   ```python
   class LLMCallStorageContractTests(ABC):
       """Contract tests for LLMCallStorage implementations."""

       @abstractmethod
       def create_storage(self) -> LLMCallStorage:
           pass

       # === Sink Contract ===
       def test_log_call_persists(self, storage): ...
       def test_log_call_is_atomic(self, storage): ...

       # === Reader Contract ===
       def test_get_by_id_returns_logged_call(self, storage): ...
       def test_get_by_id_returns_none_for_missing(self, storage): ...
       def test_query_by_decision_returns_linked_calls(self, storage): ...
       def test_query_by_decision_returns_empty_for_no_match(self, storage): ...
   ```

4. **Apply to File Backend**
   ```python
   # tests/contract/test_file_decision_contract.py
   class TestFileDecisionStorageContract(DecisionStorageContractTests):
       def create_storage(self) -> DecisionStorage:
           return FileDecisionStorage(self.tmp_path)

   # tests/contract/test_file_llm_contract.py
   class TestFileLLMCallStorageContract(LLMCallStorageContractTests):
       def create_storage(self) -> LLMCallStorage:
           return FileLLMCallStorage(self.tmp_path)
   ```

5. **Apply to Encrypted Backend**
   ```python
   # tests/contract/test_encrypted_decision_contract.py
   class TestEncryptedDecisionStorageContract(DecisionStorageContractTests):
       def create_storage(self) -> DecisionStorage:
           return EncryptedDecisionStorage(self.tmp_path, self.test_encryptor)

   # tests/contract/test_encrypted_llm_contract.py
   class TestEncryptedLLMCallStorageContract(LLMCallStorageContractTests):
       def create_storage(self) -> LLMCallStorage:
           return EncryptedLLMCallStorage(self.tmp_path, self.test_encryptor)
   ```

6. **Add regression tests**
   ```python
   # tests/regression/test_decision_ledger_compat.py
   def test_decision_ledger_facade_api_unchanged(): ...
   def test_llm_audit_service_facade_api_unchanged(): ...
   def test_existing_jsonl_files_still_readable(): ...
   ```

### Files to Create
- `tests/contract/__init__.py`
- `tests/contract/decision_storage_contract.py`
- `tests/contract/llm_storage_contract.py`
- `tests/contract/test_file_decision_contract.py`
- `tests/contract/test_file_llm_contract.py`
- `tests/contract/test_encrypted_decision_contract.py`
- `tests/contract/test_encrypted_llm_contract.py`
- `tests/regression/__init__.py`
- `tests/regression/test_decision_ledger_compat.py`

---

## Summary

| Phase | Focus | New Files | Modified Files | Est. Context |
|-------|-------|-----------|----------------|--------------|
| 1 | Interfaces & Protocols | 5 | 2 | ~60K |
| 2 | File Backend - Decisions | 3 | 2 | ~80K |
| 3 | File Backend - LLM Audit | 2 | 2 | ~70K |
| 4 | Config & Composition | 4 | 4 | ~70K |
| 5 | Encrypted Backend | 7 | 2 | ~90K |
| 6 | Contract Test Suite | 9 | 0 | ~70K |

### Exit Criteria
- [ ] All compliance services use injected interfaces
- [ ] No hardcoded storage directories in services
- [ ] File backend passes all contract tests
- [ ] Encrypted local backend passes all contract tests
- [ ] DecisionLedger and LLMAuditService facades maintain backward compatibility
- [ ] Existing JSONL files remain readable

### Dependencies
```
Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4 ─→ Phase 5 ─→ Phase 6
   │           │           │                    │
   └───────────┴───────────┴────────────────────┴─→ (interfaces used by all)
```

### Out of Scope (Per Source Doc)
- S3 backend implementation
- Database backend implementation
- Full data migration tooling
- Multi-region replication
- UI changes for backend selection
- Real-time monitoring/alerting
