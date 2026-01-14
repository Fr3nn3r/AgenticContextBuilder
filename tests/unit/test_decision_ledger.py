"""Unit tests for DecisionLedger hash chain integrity."""

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
from context_builder.services.decision_ledger import DecisionLedger, GENESIS_HASH


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary directory for ledger storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def ledger(temp_ledger_dir):
    """Create a DecisionLedger instance."""
    return DecisionLedger(temp_ledger_dir)


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


class TestDecisionLedgerBasics:
    """Basic CRUD operations for DecisionLedger."""

    def test_append_generates_decision_id(self, ledger):
        """Appending a record generates a unique decision_id."""
        record = create_test_decision()
        result = ledger.append(record)

        assert result.decision_id != ""
        assert result.decision_id.startswith("dec_")

    def test_append_sets_hashes(self, ledger):
        """Appending a record sets record_hash and previous_hash."""
        record = create_test_decision()
        result = ledger.append(record)

        assert result.record_hash is not None
        assert len(result.record_hash) == 64  # SHA-256 hex
        assert result.previous_hash == GENESIS_HASH

    def test_get_by_id(self, ledger):
        """Can retrieve a record by ID."""
        record = create_test_decision()
        appended = ledger.append(record)

        retrieved = ledger.get_by_id(appended.decision_id)
        assert retrieved is not None
        assert retrieved.decision_id == appended.decision_id
        assert retrieved.doc_id == "test_doc"

    def test_count(self, ledger):
        """Count returns correct number of records."""
        assert ledger.count() == 0

        ledger.append(create_test_decision())
        assert ledger.count() == 1

        ledger.append(create_test_decision())
        assert ledger.count() == 2


class TestHashChainIntegrity:
    """Tests for hash chain verification."""

    def test_empty_ledger_is_valid(self, ledger):
        """Empty ledger passes integrity check."""
        report = ledger.verify_integrity()
        assert report.valid is True
        assert report.total_records == 0

    def test_single_record_is_valid(self, ledger):
        """Single record chain is valid."""
        ledger.append(create_test_decision())

        report = ledger.verify_integrity()
        assert report.valid is True
        assert report.total_records == 1

    def test_multiple_records_chain_valid(self, ledger):
        """Multiple records form valid chain."""
        for i in range(5):
            ledger.append(create_test_decision(doc_id=f"doc_{i}"))

        report = ledger.verify_integrity()
        assert report.valid is True
        assert report.total_records == 5

    def test_chain_links_correctly(self, ledger):
        """Each record's previous_hash links to prior record's hash."""
        first = ledger.append(create_test_decision(doc_id="doc_1"))
        second = ledger.append(create_test_decision(doc_id="doc_2"))
        third = ledger.append(create_test_decision(doc_id="doc_3"))

        # First record links to GENESIS
        assert first.previous_hash == GENESIS_HASH

        # Second links to first's hash
        assert second.previous_hash == first.record_hash

        # Third links to second's hash
        assert third.previous_hash == second.record_hash

    def test_detects_modified_record(self, ledger, temp_ledger_dir):
        """Detects when a record has been tampered with."""
        # Add records
        ledger.append(create_test_decision(doc_id="doc_1"))
        ledger.append(create_test_decision(doc_id="doc_2"))

        # Tamper with the ledger file
        ledger_file = temp_ledger_dir / "decisions.jsonl"
        with open(ledger_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Modify the first record's doc_id
        first_record = json.loads(lines[0])
        first_record["doc_id"] = "tampered_doc"
        lines[0] = json.dumps(first_record) + "\n"

        with open(ledger_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Verify integrity - should detect tampering
        report = ledger.verify_integrity()
        assert report.valid is False
        assert report.error_type == "hash_mismatch"
        assert report.break_at_index == 0

    def test_detects_deleted_record(self, ledger, temp_ledger_dir):
        """Detects when a record has been deleted from chain."""
        # Add multiple records
        ledger.append(create_test_decision(doc_id="doc_1"))
        ledger.append(create_test_decision(doc_id="doc_2"))
        ledger.append(create_test_decision(doc_id="doc_3"))

        # Delete the second record
        ledger_file = temp_ledger_dir / "decisions.jsonl"
        with open(ledger_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Remove middle record
        del lines[1]

        with open(ledger_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Verify integrity - should detect chain break
        report = ledger.verify_integrity()
        assert report.valid is False
        assert report.error_type == "chain_break"

    def test_genesis_hash_for_first_record(self, ledger):
        """First record always has GENESIS as previous_hash."""
        record = ledger.append(create_test_decision())
        assert record.previous_hash == GENESIS_HASH


class TestQueryFiltering:
    """Tests for query filtering functionality."""

    def test_filter_by_decision_type(self, ledger):
        """Can filter by decision type."""
        ledger.append(create_test_decision(decision_type=DecisionType.CLASSIFICATION))
        ledger.append(create_test_decision(decision_type=DecisionType.EXTRACTION))
        ledger.append(create_test_decision(decision_type=DecisionType.CLASSIFICATION))

        query = DecisionQuery(decision_type=DecisionType.CLASSIFICATION)
        results = ledger.query(query)

        assert len(results) == 2
        for r in results:
            assert r.decision_type == DecisionType.CLASSIFICATION

    def test_filter_by_claim_id(self, ledger):
        """Can filter by claim_id."""
        ledger.append(create_test_decision(claim_id="CLM001"))
        ledger.append(create_test_decision(claim_id="CLM002"))
        ledger.append(create_test_decision(claim_id="CLM001"))

        query = DecisionQuery(claim_id="CLM001")
        results = ledger.query(query)

        assert len(results) == 2
        for r in results:
            assert r.claim_id == "CLM001"

    def test_filter_by_doc_id(self, ledger):
        """Can filter by doc_id."""
        ledger.append(create_test_decision(doc_id="DOC_A"))
        ledger.append(create_test_decision(doc_id="DOC_B"))

        query = DecisionQuery(doc_id="DOC_A")
        results = ledger.query(query)

        assert len(results) == 1
        assert results[0].doc_id == "DOC_A"

    def test_pagination(self, ledger):
        """Can paginate results."""
        for i in range(10):
            ledger.append(create_test_decision(doc_id=f"doc_{i}"))

        query = DecisionQuery(limit=3, offset=0)
        results = ledger.query(query)
        assert len(results) == 3

        query = DecisionQuery(limit=3, offset=8)
        results = ledger.query(query)
        assert len(results) == 2  # Only 2 remaining
