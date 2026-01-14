"""Unit tests for file-based decision storage implementations.

Tests cover:
- FileDecisionAppender: append, hash chain, atomic writes
- FileDecisionReader: get_by_id, query with filters, count
- FileDecisionVerifier: valid chain, tampered chain, empty file
- FileDecisionStorage: combined operations
- DecisionLedger facade: backwards compatibility
"""

import json
import tempfile
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
    DecisionAppender,
    DecisionReader,
    DecisionStorage,
    DecisionVerifier,
)
from context_builder.services.compliance.file import (
    GENESIS_HASH,
    FileDecisionAppender,
    FileDecisionReader,
    FileDecisionStorage,
    FileDecisionVerifier,
)
from context_builder.services.decision_ledger import DecisionLedger


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_storage_path(temp_storage_dir):
    """Create a temporary file path for storage."""
    return temp_storage_dir / "decisions.jsonl"


def create_test_decision(
    decision_type: DecisionType = DecisionType.CLASSIFICATION,
    doc_id: str = "test_doc",
    claim_id: str = "test_claim",
) -> DecisionRecord:
    """Create a test decision record."""
    return DecisionRecord(
        decision_id="",
        decision_type=decision_type,
        doc_id=doc_id,
        claim_id=claim_id,
        rationale=DecisionRationale(
            summary="Test decision",
            confidence=0.9,
        ),
        outcome=DecisionOutcome(
            doc_type="invoice",
            doc_type_confidence=0.9,
        ),
    )


# =============================================================================
# FileDecisionAppender Tests
# =============================================================================


class TestFileDecisionAppenderBasics:
    """Basic tests for FileDecisionAppender."""

    def test_implements_protocol(self, temp_storage_path):
        """FileDecisionAppender implements DecisionAppender protocol."""
        appender = FileDecisionAppender(temp_storage_path)
        assert isinstance(appender, DecisionAppender)

    def test_append_generates_decision_id(self, temp_storage_path):
        """Appending a record generates a unique decision_id."""
        appender = FileDecisionAppender(temp_storage_path)
        record = create_test_decision()
        result = appender.append(record)

        assert result.decision_id != ""
        assert result.decision_id.startswith("dec_")
        assert len(result.decision_id) == 16

    def test_append_preserves_existing_decision_id(self, temp_storage_path):
        """Appending preserves decision_id if already set."""
        appender = FileDecisionAppender(temp_storage_path)
        record = create_test_decision()
        record.decision_id = "dec_custom12345"
        result = appender.append(record)

        assert result.decision_id == "dec_custom12345"

    def test_append_sets_hashes(self, temp_storage_path):
        """Appending sets record_hash and previous_hash."""
        appender = FileDecisionAppender(temp_storage_path)
        record = create_test_decision()
        result = appender.append(record)

        assert result.record_hash is not None
        assert len(result.record_hash) == 64  # SHA-256 hex
        assert result.previous_hash == GENESIS_HASH

    def test_append_creates_file(self, temp_storage_path):
        """Appending creates the storage file."""
        appender = FileDecisionAppender(temp_storage_path)
        assert not temp_storage_path.exists()

        appender.append(create_test_decision())
        assert temp_storage_path.exists()

    def test_append_writes_jsonl(self, temp_storage_path):
        """Appending writes valid JSONL."""
        appender = FileDecisionAppender(temp_storage_path)
        appender.append(create_test_decision())

        with open(temp_storage_path, "r", encoding="utf-8") as f:
            line = f.readline()
            data = json.loads(line)

        assert "decision_id" in data
        assert "record_hash" in data
        assert "previous_hash" in data


class TestFileDecisionAppenderHashChain:
    """Tests for hash chain in FileDecisionAppender."""

    def test_first_record_has_genesis_previous(self, temp_storage_path):
        """First record has GENESIS as previous_hash."""
        appender = FileDecisionAppender(temp_storage_path)
        record = appender.append(create_test_decision())
        assert record.previous_hash == GENESIS_HASH

    def test_chain_links_correctly(self, temp_storage_path):
        """Each record's previous_hash links to prior record's hash."""
        appender = FileDecisionAppender(temp_storage_path)

        first = appender.append(create_test_decision(doc_id="doc_1"))
        second = appender.append(create_test_decision(doc_id="doc_2"))
        third = appender.append(create_test_decision(doc_id="doc_3"))

        assert first.previous_hash == GENESIS_HASH
        assert second.previous_hash == first.record_hash
        assert third.previous_hash == second.record_hash

    def test_get_last_hash_empty_storage(self, temp_storage_path):
        """get_last_hash returns GENESIS for empty storage."""
        appender = FileDecisionAppender(temp_storage_path)
        assert appender.get_last_hash() == GENESIS_HASH

    def test_get_last_hash_with_records(self, temp_storage_path):
        """get_last_hash returns last record's hash."""
        appender = FileDecisionAppender(temp_storage_path)

        first = appender.append(create_test_decision(doc_id="doc_1"))
        assert appender.get_last_hash() == first.record_hash

        second = appender.append(create_test_decision(doc_id="doc_2"))
        assert appender.get_last_hash() == second.record_hash

    def test_compute_hash_deterministic(self, temp_storage_path):
        """compute_hash is deterministic for same record."""
        record = create_test_decision()
        record.decision_id = "dec_test123456"
        record.previous_hash = GENESIS_HASH

        hash1 = FileDecisionAppender.compute_hash(record)
        hash2 = FileDecisionAppender.compute_hash(record)
        assert hash1 == hash2

    def test_compute_hash_different_for_different_content(self, temp_storage_path):
        """compute_hash differs for different record content."""
        record1 = create_test_decision(doc_id="doc_1")
        record1.decision_id = "dec_test123456"
        record1.previous_hash = GENESIS_HASH

        record2 = create_test_decision(doc_id="doc_2")
        record2.decision_id = "dec_test123456"
        record2.previous_hash = GENESIS_HASH

        hash1 = FileDecisionAppender.compute_hash(record1)
        hash2 = FileDecisionAppender.compute_hash(record2)
        assert hash1 != hash2


# =============================================================================
# FileDecisionReader Tests
# =============================================================================


class TestFileDecisionReaderBasics:
    """Basic tests for FileDecisionReader."""

    def test_implements_protocol(self, temp_storage_path):
        """FileDecisionReader implements DecisionReader protocol."""
        reader = FileDecisionReader(temp_storage_path)
        assert isinstance(reader, DecisionReader)

    def test_get_by_id_empty_storage(self, temp_storage_path):
        """get_by_id returns None for empty storage."""
        reader = FileDecisionReader(temp_storage_path)
        assert reader.get_by_id("dec_nonexistent") is None

    def test_get_by_id_finds_record(self, temp_storage_path):
        """get_by_id returns record when found."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        appended = appender.append(create_test_decision(doc_id="test_doc"))
        retrieved = reader.get_by_id(appended.decision_id)

        assert retrieved is not None
        assert retrieved.decision_id == appended.decision_id
        assert retrieved.doc_id == "test_doc"

    def test_get_by_id_returns_none_for_missing(self, temp_storage_path):
        """get_by_id returns None when ID not found."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        appender.append(create_test_decision())
        assert reader.get_by_id("dec_nonexistent") is None

    def test_count_empty_storage(self, temp_storage_path):
        """count returns 0 for empty storage."""
        reader = FileDecisionReader(temp_storage_path)
        assert reader.count() == 0

    def test_count_with_records(self, temp_storage_path):
        """count returns correct number of records."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        appender.append(create_test_decision())
        assert reader.count() == 1

        appender.append(create_test_decision())
        assert reader.count() == 2


class TestFileDecisionReaderQuery:
    """Tests for query filtering in FileDecisionReader."""

    def test_query_returns_all_without_filters(self, temp_storage_path):
        """query returns all records when no filters applied."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        for i in range(5):
            appender.append(create_test_decision(doc_id=f"doc_{i}"))

        results = reader.query()
        assert len(results) == 5

    def test_filter_by_decision_type(self, temp_storage_path):
        """query filters by decision_type."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        appender.append(create_test_decision(decision_type=DecisionType.CLASSIFICATION))
        appender.append(create_test_decision(decision_type=DecisionType.EXTRACTION))
        appender.append(create_test_decision(decision_type=DecisionType.CLASSIFICATION))

        query = DecisionQuery(decision_type=DecisionType.CLASSIFICATION)
        results = reader.query(query)

        assert len(results) == 2
        for r in results:
            assert r.decision_type == DecisionType.CLASSIFICATION

    def test_filter_by_claim_id(self, temp_storage_path):
        """query filters by claim_id."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        appender.append(create_test_decision(claim_id="CLM001"))
        appender.append(create_test_decision(claim_id="CLM002"))
        appender.append(create_test_decision(claim_id="CLM001"))

        query = DecisionQuery(claim_id="CLM001")
        results = reader.query(query)

        assert len(results) == 2
        for r in results:
            assert r.claim_id == "CLM001"

    def test_filter_by_doc_id(self, temp_storage_path):
        """query filters by doc_id."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        appender.append(create_test_decision(doc_id="DOC_A"))
        appender.append(create_test_decision(doc_id="DOC_B"))

        query = DecisionQuery(doc_id="DOC_A")
        results = reader.query(query)

        assert len(results) == 1
        assert results[0].doc_id == "DOC_A"

    def test_pagination_limit(self, temp_storage_path):
        """query respects limit parameter."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        for i in range(10):
            appender.append(create_test_decision(doc_id=f"doc_{i}"))

        query = DecisionQuery(limit=3)
        results = reader.query(query)
        assert len(results) == 3

    def test_pagination_offset(self, temp_storage_path):
        """query respects offset parameter."""
        appender = FileDecisionAppender(temp_storage_path)
        reader = FileDecisionReader(temp_storage_path)

        for i in range(10):
            appender.append(create_test_decision(doc_id=f"doc_{i}"))

        query = DecisionQuery(limit=3, offset=8)
        results = reader.query(query)
        assert len(results) == 2  # Only 2 remaining after offset 8


# =============================================================================
# FileDecisionVerifier Tests
# =============================================================================


class TestFileDecisionVerifierBasics:
    """Basic tests for FileDecisionVerifier."""

    def test_implements_protocol(self, temp_storage_path):
        """FileDecisionVerifier implements DecisionVerifier protocol."""
        verifier = FileDecisionVerifier(temp_storage_path)
        assert isinstance(verifier, DecisionVerifier)

    def test_empty_storage_is_valid(self, temp_storage_path):
        """Empty storage passes integrity check."""
        verifier = FileDecisionVerifier(temp_storage_path)
        report = verifier.verify_integrity()

        assert report.valid is True
        assert report.total_records == 0

    def test_single_record_is_valid(self, temp_storage_path):
        """Single record chain is valid."""
        appender = FileDecisionAppender(temp_storage_path)
        verifier = FileDecisionVerifier(temp_storage_path)

        appender.append(create_test_decision())
        report = verifier.verify_integrity()

        assert report.valid is True
        assert report.total_records == 1

    def test_multiple_records_chain_valid(self, temp_storage_path):
        """Multiple records form valid chain."""
        appender = FileDecisionAppender(temp_storage_path)
        verifier = FileDecisionVerifier(temp_storage_path)

        for i in range(5):
            appender.append(create_test_decision(doc_id=f"doc_{i}"))

        report = verifier.verify_integrity()

        assert report.valid is True
        assert report.total_records == 5


class TestFileDecisionVerifierTampering:
    """Tests for tampering detection in FileDecisionVerifier."""

    def test_detects_modified_record(self, temp_storage_path):
        """Detects when a record has been tampered with."""
        appender = FileDecisionAppender(temp_storage_path)
        verifier = FileDecisionVerifier(temp_storage_path)

        appender.append(create_test_decision(doc_id="doc_1"))
        appender.append(create_test_decision(doc_id="doc_2"))

        # Tamper with the storage file
        with open(temp_storage_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        first_record = json.loads(lines[0])
        first_record["doc_id"] = "tampered_doc"
        lines[0] = json.dumps(first_record) + "\n"

        with open(temp_storage_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        report = verifier.verify_integrity()

        assert report.valid is False
        assert report.error_type == "hash_mismatch"
        assert report.break_at_index == 0

    def test_detects_deleted_record(self, temp_storage_path):
        """Detects when a record has been deleted from chain."""
        appender = FileDecisionAppender(temp_storage_path)
        verifier = FileDecisionVerifier(temp_storage_path)

        appender.append(create_test_decision(doc_id="doc_1"))
        appender.append(create_test_decision(doc_id="doc_2"))
        appender.append(create_test_decision(doc_id="doc_3"))

        # Delete the second record
        with open(temp_storage_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        del lines[1]

        with open(temp_storage_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        report = verifier.verify_integrity()

        assert report.valid is False
        assert report.error_type == "chain_break"

    def test_detects_modified_hash(self, temp_storage_path):
        """Detects when record_hash has been modified."""
        appender = FileDecisionAppender(temp_storage_path)
        verifier = FileDecisionVerifier(temp_storage_path)

        appender.append(create_test_decision())

        # Modify the hash
        with open(temp_storage_path, "r", encoding="utf-8") as f:
            line = f.readline()

        record = json.loads(line)
        record["record_hash"] = "a" * 64  # Fake hash

        with open(temp_storage_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        report = verifier.verify_integrity()

        assert report.valid is False
        assert report.error_type == "hash_mismatch"


# =============================================================================
# FileDecisionStorage Tests
# =============================================================================


class TestFileDecisionStorageBasics:
    """Basic tests for FileDecisionStorage."""

    def test_implements_protocol(self, temp_storage_dir):
        """FileDecisionStorage implements DecisionStorage protocol."""
        storage = FileDecisionStorage(temp_storage_dir)
        assert isinstance(storage, DecisionStorage)

    def test_combines_all_operations(self, temp_storage_dir):
        """FileDecisionStorage provides all operations."""
        storage = FileDecisionStorage(temp_storage_dir)

        # Append
        record = storage.append(create_test_decision(doc_id="test"))
        assert record.decision_id.startswith("dec_")

        # Get by ID
        retrieved = storage.get_by_id(record.decision_id)
        assert retrieved is not None
        assert retrieved.doc_id == "test"

        # Query
        results = storage.query()
        assert len(results) == 1

        # Count
        assert storage.count() == 1

        # Verify
        report = storage.verify_integrity()
        assert report.valid is True

    def test_storage_path_property(self, temp_storage_dir):
        """storage_path property returns correct path."""
        storage = FileDecisionStorage(temp_storage_dir)
        assert storage.storage_path == temp_storage_dir / "decisions.jsonl"

    def test_custom_filename(self, temp_storage_dir):
        """Can use custom filename."""
        storage = FileDecisionStorage(temp_storage_dir, filename="custom.jsonl")
        storage.append(create_test_decision())
        assert (temp_storage_dir / "custom.jsonl").exists()


# =============================================================================
# DecisionLedger Facade Tests
# =============================================================================


class TestDecisionLedgerFacade:
    """Tests for DecisionLedger facade backwards compatibility."""

    def test_append_works(self, temp_storage_dir):
        """append method works through facade."""
        ledger = DecisionLedger(temp_storage_dir)
        record = ledger.append(create_test_decision())

        assert record.decision_id.startswith("dec_")
        assert record.record_hash is not None

    def test_verify_integrity_works(self, temp_storage_dir):
        """verify_integrity method works through facade."""
        ledger = DecisionLedger(temp_storage_dir)
        ledger.append(create_test_decision())

        report = ledger.verify_integrity()
        assert report.valid is True

    def test_query_works(self, temp_storage_dir):
        """query method works through facade."""
        ledger = DecisionLedger(temp_storage_dir)
        ledger.append(create_test_decision(claim_id="CLM001"))
        ledger.append(create_test_decision(claim_id="CLM002"))

        results = ledger.query(DecisionQuery(claim_id="CLM001"))
        assert len(results) == 1

    def test_get_by_id_works(self, temp_storage_dir):
        """get_by_id method works through facade."""
        ledger = DecisionLedger(temp_storage_dir)
        appended = ledger.append(create_test_decision())

        retrieved = ledger.get_by_id(appended.decision_id)
        assert retrieved is not None

    def test_count_works(self, temp_storage_dir):
        """count method works through facade."""
        ledger = DecisionLedger(temp_storage_dir)
        ledger.append(create_test_decision())
        ledger.append(create_test_decision())

        assert ledger.count() == 2

    def test_ledger_file_attribute_exists(self, temp_storage_dir):
        """ledger_file attribute exists for backwards compatibility."""
        ledger = DecisionLedger(temp_storage_dir)
        assert hasattr(ledger, "ledger_file")
        assert ledger.ledger_file == temp_storage_dir / "decisions.jsonl"

    def test_storage_dir_attribute_exists(self, temp_storage_dir):
        """storage_dir attribute exists for backwards compatibility."""
        ledger = DecisionLedger(temp_storage_dir)
        assert hasattr(ledger, "storage_dir")
        assert ledger.storage_dir == temp_storage_dir

    def test_genesis_hash_exported(self):
        """GENESIS_HASH is exported from decision_ledger module."""
        from context_builder.services.decision_ledger import GENESIS_HASH as LedgerGenesis

        assert LedgerGenesis == "GENESIS"
