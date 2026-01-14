"""Unit tests for encrypted decision storage.

Tests:
- Append with encryption
- Query and read with decryption
- Hash chain verification through encryption
- Combined storage operations
- Factory integration
"""

from pathlib import Path

import pytest

from context_builder.schemas.decision_record import (
    DecisionOutcome,
    DecisionQuery,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
)
from context_builder.services.compliance import (
    DecisionStorage,
    EncryptedDecisionAppender,
    EncryptedDecisionReader,
    EncryptedDecisionStorage,
    EncryptedDecisionVerifier,
    EnvelopeEncryptor,
    generate_key,
)
from context_builder.services.compliance.encrypted.decision_storage import GENESIS_HASH


@pytest.fixture
def encryptor() -> EnvelopeEncryptor:
    """Create an encryptor with a fresh key."""
    return EnvelopeEncryptor(generate_key())


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    """Get a path for the encrypted storage file."""
    return tmp_path / "decisions.enc.jsonl"


def make_test_record(
    decision_type: DecisionType = DecisionType.CLASSIFICATION,
    doc_id: str = "doc_001",
    claim_id: str = "claim_001",
) -> DecisionRecord:
    """Create a test decision record."""
    return DecisionRecord(
        decision_id="",  # Will be assigned
        decision_type=decision_type,
        doc_id=doc_id,
        claim_id=claim_id,
        run_id="run_001",
        actor_type="system",
        actor_id="test",
        rationale=DecisionRationale(
            summary="Test decision",
            confidence=0.95,
        ),
        outcome=DecisionOutcome(
            doc_type="invoice",
            doc_type_confidence=0.95,
        ),
    )


class TestEncryptedDecisionAppender:
    """Tests for EncryptedDecisionAppender."""

    def test_append_assigns_decision_id(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Appender assigns decision_id if not set."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        record = make_test_record()

        result = appender.append(record)

        assert result.decision_id
        assert result.decision_id.startswith("dec_")

    def test_append_computes_hash(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Appender computes record_hash."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        record = make_test_record()

        result = appender.append(record)

        assert result.record_hash
        assert len(result.record_hash) == 64  # SHA-256 hex

    def test_append_links_to_genesis(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """First record links to GENESIS."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        record = make_test_record()

        result = appender.append(record)

        assert result.previous_hash == GENESIS_HASH

    def test_append_chains_records(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Second record links to first."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)

        first = appender.append(make_test_record(doc_id="doc_001"))
        second = appender.append(make_test_record(doc_id="doc_002"))

        assert second.previous_hash == first.record_hash

    def test_append_creates_encrypted_file(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """Appender creates encrypted file on disk."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        appender.append(make_test_record())

        assert storage_path.exists()
        content = storage_path.read_text()
        # Content should be base64, not readable JSON
        assert "decision_id" not in content

    def test_get_last_hash_empty_storage(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """get_last_hash returns GENESIS for empty storage."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        assert appender.get_last_hash() == GENESIS_HASH

    def test_get_last_hash_after_append(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """get_last_hash returns last record's hash."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        result = appender.append(make_test_record())

        assert appender.get_last_hash() == result.record_hash


class TestEncryptedDecisionReader:
    """Tests for EncryptedDecisionReader."""

    def test_get_by_id_not_found(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """get_by_id returns None for missing ID."""
        reader = EncryptedDecisionReader(storage_path, encryptor)
        assert reader.get_by_id("nonexistent") is None

    def test_get_by_id_finds_record(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """get_by_id finds and decrypts record."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        reader = EncryptedDecisionReader(storage_path, encryptor)

        original = appender.append(make_test_record())
        found = reader.get_by_id(original.decision_id)

        assert found is not None
        assert found.decision_id == original.decision_id
        assert found.doc_id == original.doc_id

    def test_query_empty_storage(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query returns empty list for empty storage."""
        reader = EncryptedDecisionReader(storage_path, encryptor)
        results = reader.query()
        assert results == []

    def test_query_returns_all_records(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query returns all records when no filters."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        reader = EncryptedDecisionReader(storage_path, encryptor)

        appender.append(make_test_record(doc_id="doc_001"))
        appender.append(make_test_record(doc_id="doc_002"))

        results = reader.query()
        assert len(results) == 2

    def test_query_filters_by_decision_type(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query filters by decision_type."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        reader = EncryptedDecisionReader(storage_path, encryptor)

        appender.append(make_test_record(decision_type=DecisionType.CLASSIFICATION))
        appender.append(make_test_record(decision_type=DecisionType.EXTRACTION))

        filters = DecisionQuery(decision_type=DecisionType.CLASSIFICATION)
        results = reader.query(filters)

        assert len(results) == 1
        assert results[0].decision_type == DecisionType.CLASSIFICATION

    def test_query_filters_by_doc_id(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query filters by doc_id."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        reader = EncryptedDecisionReader(storage_path, encryptor)

        appender.append(make_test_record(doc_id="doc_001"))
        appender.append(make_test_record(doc_id="doc_002"))

        filters = DecisionQuery(doc_id="doc_001")
        results = reader.query(filters)

        assert len(results) == 1
        assert results[0].doc_id == "doc_001"

    def test_query_applies_limit(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """query respects limit parameter."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        reader = EncryptedDecisionReader(storage_path, encryptor)

        for i in range(5):
            appender.append(make_test_record(doc_id=f"doc_{i}"))

        filters = DecisionQuery(limit=3)
        results = reader.query(filters)

        assert len(results) == 3

    def test_count_empty_storage(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """count returns 0 for empty storage."""
        reader = EncryptedDecisionReader(storage_path, encryptor)
        assert reader.count() == 0

    def test_count_returns_total(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """count returns total record count."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        reader = EncryptedDecisionReader(storage_path, encryptor)

        for i in range(3):
            appender.append(make_test_record(doc_id=f"doc_{i}"))

        assert reader.count() == 3


class TestEncryptedDecisionVerifier:
    """Tests for EncryptedDecisionVerifier."""

    def test_verify_empty_storage(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """verify_integrity returns valid for empty storage."""
        verifier = EncryptedDecisionVerifier(storage_path, encryptor)
        report = verifier.verify_integrity()

        assert report.valid is True
        assert report.total_records == 0

    def test_verify_single_record(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """verify_integrity validates single record."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        verifier = EncryptedDecisionVerifier(storage_path, encryptor)

        appender.append(make_test_record())
        report = verifier.verify_integrity()

        assert report.valid is True
        assert report.total_records == 1

    def test_verify_chain_of_records(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """verify_integrity validates chain of records."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        verifier = EncryptedDecisionVerifier(storage_path, encryptor)

        for i in range(5):
            appender.append(make_test_record(doc_id=f"doc_{i}"))

        report = verifier.verify_integrity()

        assert report.valid is True
        assert report.total_records == 5

    def test_verify_detects_tampered_record(
        self, storage_path: Path, encryptor: EnvelopeEncryptor
    ):
        """verify_integrity detects tampered encrypted data."""
        appender = EncryptedDecisionAppender(storage_path, encryptor)
        verifier = EncryptedDecisionVerifier(storage_path, encryptor)

        appender.append(make_test_record())

        # Tamper with the file
        content = storage_path.read_text()
        lines = content.strip().split("\n")
        lines[0] = lines[0][:-5] + "XXXXX"  # Corrupt base64
        storage_path.write_text("\n".join(lines) + "\n")

        report = verifier.verify_integrity()

        assert report.valid is False


class TestEncryptedDecisionStorage:
    """Tests for combined EncryptedDecisionStorage."""

    def test_implements_protocol(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """EncryptedDecisionStorage implements DecisionStorage."""
        storage = EncryptedDecisionStorage(tmp_path, encryptor)
        assert isinstance(storage, DecisionStorage)

    def test_append_and_retrieve(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """Storage can append and retrieve records."""
        storage = EncryptedDecisionStorage(tmp_path, encryptor)

        original = storage.append(make_test_record())
        found = storage.get_by_id(original.decision_id)

        assert found is not None
        assert found.decision_id == original.decision_id

    def test_full_workflow(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """Storage supports full workflow: append, query, verify."""
        storage = EncryptedDecisionStorage(tmp_path, encryptor)

        # Append records
        for i in range(3):
            storage.append(make_test_record(doc_id=f"doc_{i}"))

        # Query
        results = storage.query()
        assert len(results) == 3

        # Verify integrity
        report = storage.verify_integrity()
        assert report.valid is True
        assert report.total_records == 3

    def test_storage_path_property(self, tmp_path: Path, encryptor: EnvelopeEncryptor):
        """storage_path property returns correct path."""
        storage = EncryptedDecisionStorage(tmp_path, encryptor)
        assert storage.storage_path == tmp_path / "decisions.enc.jsonl"


class TestWrongKeyDecryption:
    """Tests for decryption with wrong key."""

    def test_wrong_key_cannot_read(self, storage_path: Path):
        """Records encrypted with one key cannot be read with another."""
        encryptor1 = EnvelopeEncryptor(generate_key())
        encryptor2 = EnvelopeEncryptor(generate_key())

        # Write with encryptor1
        appender = EncryptedDecisionAppender(storage_path, encryptor1)
        original = appender.append(make_test_record())

        # Try to read with encryptor2
        reader = EncryptedDecisionReader(storage_path, encryptor2)
        found = reader.get_by_id(original.decision_id)

        # Should fail to decrypt and return None
        assert found is None


class TestFactoryIntegration:
    """Tests for factory integration with encrypted backend."""

    def test_factory_creates_encrypted_storage(self, tmp_path: Path):
        """Factory creates EncryptedDecisionStorage for encrypted_file backend."""
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

        storage = ComplianceStorageFactory.create_decision_storage(config)

        assert isinstance(storage, EncryptedDecisionStorage)

        # Verify it works
        original = storage.append(make_test_record())
        found = storage.get_by_id(original.decision_id)
        assert found is not None
