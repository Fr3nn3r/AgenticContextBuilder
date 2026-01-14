"""Unit tests for encrypted LLM call storage.

Tests:
- Log call with encryption
- Query and read with decryption
- Combined storage operations
- Factory integration
"""

from pathlib import Path

import pytest

from context_builder.schemas.llm_call_record import LLMCallRecord
from context_builder.services.compliance import (
    EncryptedLLMCallReader,
    EncryptedLLMCallSink,
    EncryptedLLMCallStorage,
    EnvelopeEncryptor,
    LLMCallStorage,
    generate_key,
)


@pytest.fixture
def encryptor() -> EnvelopeEncryptor:
    """Create an encryptor with a fresh key."""
    return EnvelopeEncryptor(generate_key())


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    """Get a path for the encrypted storage file."""
    return tmp_path / "llm_calls.enc.jsonl"


def make_test_record(
    call_id: str = "",
    decision_id: str = None,
    model: str = "gpt-4o",
) -> LLMCallRecord:
    """Create a test LLM call record."""
    return LLMCallRecord(
        call_id=call_id,
        model=model,
        call_purpose="test",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=500,
        decision_id=decision_id,
        claim_id="claim_001",
        doc_id="doc_001",
    )


class TestEncryptedLLMCallSink:
    """Tests for EncryptedLLMCallSink."""

    def test_log_call_assigns_call_id(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Sink assigns call_id if not set."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)
        record = make_test_record()

        result = sink.log_call(record)

        assert result.call_id
        assert result.call_id.startswith("llm_")

    def test_log_call_preserves_existing_id(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Sink preserves existing call_id."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)
        record = make_test_record(call_id="custom_id_123")

        result = sink.log_call(record)

        assert result.call_id == "custom_id_123"

    def test_log_call_creates_encrypted_file(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Sink creates encrypted file on disk."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)
        sink.log_call(make_test_record())

        assert storage_path.exists()
        content = storage_path.read_text()
        # Content should be base64, not readable JSON
        assert "call_id" not in content
        assert "gpt-4o" not in content

    def test_log_multiple_calls(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Sink can log multiple calls."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)

        ids = []
        for i in range(3):
            result = sink.log_call(make_test_record())
            ids.append(result.call_id)

        # All IDs should be unique
        assert len(set(ids)) == 3

        # File should have 3 lines
        lines = storage_path.read_text().strip().split("\n")
        assert len(lines) == 3


class TestEncryptedLLMCallReader:
    """Tests for EncryptedLLMCallReader."""

    def test_get_by_id_not_found(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """get_by_id returns None for missing ID."""
        reader = EncryptedLLMCallReader(storage_path, encryptor)
        assert reader.get_by_id("nonexistent") is None

    def test_get_by_id_finds_record(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """get_by_id finds and decrypts record."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)
        reader = EncryptedLLMCallReader(storage_path, encryptor)

        original = sink.log_call(make_test_record())
        found = reader.get_by_id(original.call_id)

        assert found is not None
        assert found.call_id == original.call_id
        assert found.model == original.model

    def test_query_by_decision_empty(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query_by_decision returns empty list for no matches."""
        reader = EncryptedLLMCallReader(storage_path, encryptor)
        results = reader.query_by_decision("nonexistent")
        assert results == []

    def test_query_by_decision_finds_records(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query_by_decision finds matching records."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)
        reader = EncryptedLLMCallReader(storage_path, encryptor)

        # Log calls with different decision_ids
        sink.log_call(make_test_record(decision_id="dec_001"))
        sink.log_call(make_test_record(decision_id="dec_001"))
        sink.log_call(make_test_record(decision_id="dec_002"))

        results = reader.query_by_decision("dec_001")

        assert len(results) == 2
        for record in results:
            assert record.decision_id == "dec_001"

    def test_count_empty_storage(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """count returns 0 for empty storage."""
        reader = EncryptedLLMCallReader(storage_path, encryptor)
        assert reader.count() == 0

    def test_count_returns_total(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """count returns total record count."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)
        reader = EncryptedLLMCallReader(storage_path, encryptor)

        for i in range(5):
            sink.log_call(make_test_record())

        assert reader.count() == 5


class TestEncryptedLLMCallStorage:
    """Tests for combined EncryptedLLMCallStorage."""

    def test_implements_protocol(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """EncryptedLLMCallStorage implements LLMCallStorage."""
        storage = EncryptedLLMCallStorage(tmp_path, encryptor)
        assert isinstance(storage, LLMCallStorage)

    def test_log_and_retrieve(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """Storage can log and retrieve records."""
        storage = EncryptedLLMCallStorage(tmp_path, encryptor)

        original = storage.log_call(make_test_record())
        found = storage.get_by_id(original.call_id)

        assert found is not None
        assert found.call_id == original.call_id

    def test_full_workflow(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """Storage supports full workflow: log, query, count."""
        storage = EncryptedLLMCallStorage(tmp_path, encryptor)

        # Log calls
        decision_id = "dec_test"
        for i in range(3):
            storage.log_call(make_test_record(decision_id=decision_id))

        # Query by decision
        results = storage.query_by_decision(decision_id)
        assert len(results) == 3

        # Count
        assert storage.count() == 3

    def test_storage_path_property(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """storage_path property returns correct path."""
        storage = EncryptedLLMCallStorage(tmp_path, encryptor)
        assert storage.storage_path == tmp_path / "llm_calls.enc.jsonl"

    def test_custom_filename(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """Storage supports custom filename."""
        storage = EncryptedLLMCallStorage(
            tmp_path, encryptor, filename="custom_calls.enc"
        )
        assert storage.storage_path == tmp_path / "custom_calls.enc"


class TestWrongKeyDecryption:
    """Tests for decryption with wrong key."""

    def test_wrong_key_cannot_read(self, storage_path: Path):
        """Records encrypted with one key cannot be read with another."""
        encryptor1 = EnvelopeEncryptor(generate_key())
        encryptor2 = EnvelopeEncryptor(generate_key())

        # Write with encryptor1
        sink = EncryptedLLMCallSink(storage_path, encryptor1)
        original = sink.log_call(make_test_record())

        # Try to read with encryptor2
        reader = EncryptedLLMCallReader(storage_path, encryptor2)
        found = reader.get_by_id(original.call_id)

        # Should fail to decrypt and return None
        assert found is None

    def test_wrong_key_query_returns_empty(self, storage_path: Path):
        """Query with wrong key returns empty results."""
        encryptor1 = EnvelopeEncryptor(generate_key())
        encryptor2 = EnvelopeEncryptor(generate_key())

        # Write with encryptor1
        sink = EncryptedLLMCallSink(storage_path, encryptor1)
        sink.log_call(make_test_record(decision_id="dec_001"))

        # Try to query with encryptor2
        reader = EncryptedLLMCallReader(storage_path, encryptor2)
        results = reader.query_by_decision("dec_001")

        assert results == []


class TestFactoryIntegration:
    """Tests for factory integration with encrypted backend."""

    def test_factory_creates_encrypted_storage(self, tmp_path: Path):
        """Factory creates EncryptedLLMCallStorage for encrypted_file backend."""
        from context_builder.services.compliance import (
            ComplianceStorageConfig,
            ComplianceStorageFactory,
            StorageBackendType,
        )

        # Create a key file
        key_path = tmp_path / "master.key"
        key_path.write_bytes(generate_key())

        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            encryption_key_path=key_path,
        )

        storage = ComplianceStorageFactory.create_llm_storage(config)

        assert isinstance(storage, EncryptedLLMCallStorage)

        # Verify it works
        original = storage.log_call(make_test_record())
        found = storage.get_by_id(original.call_id)
        assert found is not None

    def test_create_all_returns_both_encrypted(self, tmp_path: Path):
        """create_all returns both encrypted storage types."""
        from context_builder.services.compliance import (
            ComplianceStorageConfig,
            ComplianceStorageFactory,
            EncryptedDecisionStorage,
            StorageBackendType,
        )

        # Create a key file
        key_path = tmp_path / "master.key"
        key_path.write_bytes(generate_key())

        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            encryption_key_path=key_path,
        )

        decision_storage, llm_storage = ComplianceStorageFactory.create_all(config)

        assert isinstance(decision_storage, EncryptedDecisionStorage)
        assert isinstance(llm_storage, EncryptedLLMCallStorage)


class TestDataProtection:
    """Tests verifying sensitive data is protected."""

    def test_prompt_not_readable_in_file(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Sensitive prompt data is not readable in file."""
        sink = EncryptedLLMCallSink(storage_path, encryptor)

        sensitive_record = LLMCallRecord(
            call_id="",
            model="gpt-4o",
            call_purpose="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=500,
            # Imagine these contain sensitive data
            claim_id="claim_sensitive_123",
            doc_id="doc_with_pii",
        )

        sink.log_call(sensitive_record)

        # File content should not contain any recognizable sensitive data
        content = storage_path.read_text()
        assert "claim_sensitive_123" not in content
        assert "doc_with_pii" not in content
        assert "gpt-4o" not in content
