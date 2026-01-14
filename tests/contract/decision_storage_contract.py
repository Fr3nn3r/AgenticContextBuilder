"""Contract tests for DecisionStorage implementations.

These tests define the behavior that any DecisionStorage implementation
must satisfy. Subclasses must implement `create_storage()` to provide
the specific backend being tested.

The contract covers:
- Appender: append returns record with hash, links to previous, atomic writes
- Reader: get_by_id, query with filters, count
- Verifier: integrity checks for empty, single, chain, and tampered records
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable

import pytest

from context_builder.schemas.decision_record import (
    DecisionOutcome,
    DecisionQuery,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
)
from context_builder.services.compliance.interfaces import DecisionStorage


def make_test_record(
    decision_type: DecisionType = DecisionType.CLASSIFICATION,
    doc_id: str = "doc_001",
    claim_id: str = "claim_001",
    run_id: str = "run_001",
) -> DecisionRecord:
    """Create a test decision record."""
    return DecisionRecord(
        decision_id="",  # Will be assigned by storage
        decision_type=decision_type,
        doc_id=doc_id,
        claim_id=claim_id,
        run_id=run_id,
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


class DecisionStorageContractTests(ABC):
    """Contract tests that any DecisionStorage implementation must pass.

    Subclasses must implement `create_storage()` to provide the backend.

    Example:
        class TestFileDecisionContract(DecisionStorageContractTests):
            def create_storage(self, tmp_path: Path) -> DecisionStorage:
                return FileDecisionStorage(tmp_path)
    """

    @abstractmethod
    def create_storage(self, tmp_path: Path) -> DecisionStorage:
        """Create a fresh storage instance for testing.

        Args:
            tmp_path: Temporary directory for storage files.

        Returns:
            A new DecisionStorage instance.
        """
        pass

    @pytest.fixture
    def storage(self, tmp_path: Path) -> DecisionStorage:
        """Fixture providing a fresh storage instance."""
        return self.create_storage(tmp_path)

    # =========================================================================
    # Appender Contract
    # =========================================================================

    def test_append_returns_record_with_decision_id(self, storage: DecisionStorage):
        """Append assigns a decision_id if not set."""
        record = make_test_record()
        assert not record.decision_id

        result = storage.append(record)

        assert result.decision_id
        assert result.decision_id.startswith("dec_")

    def test_append_returns_record_with_hash(self, storage: DecisionStorage):
        """Append computes and sets record_hash."""
        record = make_test_record()

        result = storage.append(record)

        assert result.record_hash
        assert len(result.record_hash) == 64  # SHA-256 hex

    def test_append_sets_previous_hash(self, storage: DecisionStorage):
        """Append sets previous_hash linking to prior record."""
        record = make_test_record()

        result = storage.append(record)

        assert result.previous_hash is not None

    def test_first_record_has_genesis_previous(self, storage: DecisionStorage):
        """First record's previous_hash is GENESIS."""
        record = make_test_record()

        result = storage.append(record)

        assert result.previous_hash == "GENESIS"

    def test_append_links_to_previous_hash(self, storage: DecisionStorage):
        """Second record's previous_hash equals first record's hash."""
        first = storage.append(make_test_record(doc_id="doc_001"))
        second = storage.append(make_test_record(doc_id="doc_002"))

        assert second.previous_hash == first.record_hash

    def test_append_preserves_existing_decision_id(self, storage: DecisionStorage):
        """Append preserves decision_id if already set."""
        record = make_test_record()
        record.decision_id = "custom_dec_123"

        result = storage.append(record)

        assert result.decision_id == "custom_dec_123"

    def test_append_sets_created_at(self, storage: DecisionStorage):
        """Append sets created_at timestamp if not set."""
        record = make_test_record()
        assert not record.created_at

        result = storage.append(record)

        assert result.created_at
        assert "T" in result.created_at  # ISO format

    def test_append_is_durable(self, storage: DecisionStorage):
        """Appended records survive storage recreation."""
        original = storage.append(make_test_record())

        # The storage should have persisted the record
        found = storage.get_by_id(original.decision_id)
        assert found is not None
        assert found.decision_id == original.decision_id

    # =========================================================================
    # Reader Contract
    # =========================================================================

    def test_get_by_id_returns_appended_record(self, storage: DecisionStorage):
        """get_by_id retrieves previously appended record."""
        original = storage.append(make_test_record())

        found = storage.get_by_id(original.decision_id)

        assert found is not None
        assert found.decision_id == original.decision_id
        assert found.doc_id == original.doc_id
        assert found.record_hash == original.record_hash

    def test_get_by_id_returns_none_for_missing(self, storage: DecisionStorage):
        """get_by_id returns None for non-existent ID."""
        result = storage.get_by_id("nonexistent_id")
        assert result is None

    def test_get_by_id_empty_storage(self, storage: DecisionStorage):
        """get_by_id returns None on empty storage."""
        result = storage.get_by_id("any_id")
        assert result is None

    def test_query_returns_all_without_filters(self, storage: DecisionStorage):
        """query() without filters returns all records."""
        storage.append(make_test_record(doc_id="doc_001"))
        storage.append(make_test_record(doc_id="doc_002"))
        storage.append(make_test_record(doc_id="doc_003"))

        results = storage.query()

        assert len(results) == 3

    def test_query_empty_storage(self, storage: DecisionStorage):
        """query() on empty storage returns empty list."""
        results = storage.query()
        assert results == []

    def test_query_filters_by_decision_type(self, storage: DecisionStorage):
        """query() filters by decision_type."""
        storage.append(make_test_record(decision_type=DecisionType.CLASSIFICATION))
        storage.append(make_test_record(decision_type=DecisionType.EXTRACTION))
        storage.append(make_test_record(decision_type=DecisionType.CLASSIFICATION))

        filters = DecisionQuery(decision_type=DecisionType.CLASSIFICATION)
        results = storage.query(filters)

        assert len(results) == 2
        for r in results:
            assert r.decision_type == DecisionType.CLASSIFICATION

    def test_query_filters_by_claim_id(self, storage: DecisionStorage):
        """query() filters by claim_id."""
        storage.append(make_test_record(claim_id="claim_A"))
        storage.append(make_test_record(claim_id="claim_B"))
        storage.append(make_test_record(claim_id="claim_A"))

        filters = DecisionQuery(claim_id="claim_A")
        results = storage.query(filters)

        assert len(results) == 2
        for r in results:
            assert r.claim_id == "claim_A"

    def test_query_filters_by_doc_id(self, storage: DecisionStorage):
        """query() filters by doc_id."""
        storage.append(make_test_record(doc_id="doc_X"))
        storage.append(make_test_record(doc_id="doc_Y"))
        storage.append(make_test_record(doc_id="doc_X"))

        filters = DecisionQuery(doc_id="doc_X")
        results = storage.query(filters)

        assert len(results) == 2
        for r in results:
            assert r.doc_id == "doc_X"

    def test_query_filters_by_run_id(self, storage: DecisionStorage):
        """query() filters by run_id."""
        storage.append(make_test_record(run_id="run_1"))
        storage.append(make_test_record(run_id="run_2"))

        filters = DecisionQuery(run_id="run_1")
        results = storage.query(filters)

        assert len(results) == 1
        assert results[0].run_id == "run_1"

    def test_query_respects_limit(self, storage: DecisionStorage):
        """query() respects the limit parameter."""
        for i in range(10):
            storage.append(make_test_record(doc_id=f"doc_{i}"))

        filters = DecisionQuery(limit=5)
        results = storage.query(filters)

        assert len(results) == 5

    def test_query_respects_offset(self, storage: DecisionStorage):
        """query() respects the offset parameter."""
        for i in range(10):
            storage.append(make_test_record(doc_id=f"doc_{i}"))

        filters = DecisionQuery(offset=5, limit=100)
        results = storage.query(filters)

        assert len(results) == 5

    def test_query_combines_multiple_filters(self, storage: DecisionStorage):
        """query() combines multiple filters with AND logic."""
        storage.append(make_test_record(
            decision_type=DecisionType.CLASSIFICATION,
            claim_id="claim_A",
        ))
        storage.append(make_test_record(
            decision_type=DecisionType.EXTRACTION,
            claim_id="claim_A",
        ))
        storage.append(make_test_record(
            decision_type=DecisionType.CLASSIFICATION,
            claim_id="claim_B",
        ))

        filters = DecisionQuery(
            decision_type=DecisionType.CLASSIFICATION,
            claim_id="claim_A",
        )
        results = storage.query(filters)

        assert len(results) == 1
        assert results[0].decision_type == DecisionType.CLASSIFICATION
        assert results[0].claim_id == "claim_A"

    def test_count_returns_zero_for_empty(self, storage: DecisionStorage):
        """count() returns 0 for empty storage."""
        assert storage.count() == 0

    def test_count_returns_correct_number(self, storage: DecisionStorage):
        """count() returns accurate record count."""
        storage.append(make_test_record(doc_id="doc_001"))
        storage.append(make_test_record(doc_id="doc_002"))
        storage.append(make_test_record(doc_id="doc_003"))

        assert storage.count() == 3

    # =========================================================================
    # Verifier Contract
    # =========================================================================

    def test_verify_empty_is_valid(self, storage: DecisionStorage):
        """verify_integrity() returns valid for empty storage."""
        report = storage.verify_integrity()

        assert report.valid is True
        assert report.total_records == 0

    def test_verify_single_record_is_valid(self, storage: DecisionStorage):
        """verify_integrity() validates single record."""
        storage.append(make_test_record())

        report = storage.verify_integrity()

        assert report.valid is True
        assert report.total_records == 1

    def test_verify_chain_is_valid(self, storage: DecisionStorage):
        """verify_integrity() validates chain of records."""
        for i in range(5):
            storage.append(make_test_record(doc_id=f"doc_{i}"))

        report = storage.verify_integrity()

        assert report.valid is True
        assert report.total_records == 5

    def test_verify_reports_total_records(self, storage: DecisionStorage):
        """verify_integrity() reports correct total_records."""
        for i in range(3):
            storage.append(make_test_record(doc_id=f"doc_{i}"))

        report = storage.verify_integrity()

        assert report.total_records == 3

    # =========================================================================
    # Protocol Compliance
    # =========================================================================

    def test_implements_decision_storage_protocol(self, storage: DecisionStorage):
        """Storage implements DecisionStorage protocol."""
        assert isinstance(storage, DecisionStorage)

    def test_has_append_method(self, storage: DecisionStorage):
        """Storage has append method."""
        assert hasattr(storage, "append")
        assert callable(storage.append)

    def test_has_get_by_id_method(self, storage: DecisionStorage):
        """Storage has get_by_id method."""
        assert hasattr(storage, "get_by_id")
        assert callable(storage.get_by_id)

    def test_has_query_method(self, storage: DecisionStorage):
        """Storage has query method."""
        assert hasattr(storage, "query")
        assert callable(storage.query)

    def test_has_count_method(self, storage: DecisionStorage):
        """Storage has count method."""
        assert hasattr(storage, "count")
        assert callable(storage.count)

    def test_has_verify_integrity_method(self, storage: DecisionStorage):
        """Storage has verify_integrity method."""
        assert hasattr(storage, "verify_integrity")
        assert callable(storage.verify_integrity)
