"""Contract tests for LLMCallStorage implementations.

These tests define the behavior that any LLMCallStorage implementation
must satisfy. Subclasses must implement `create_storage()` to provide
the specific backend being tested.

The contract covers:
- Sink: log_call persists records, assigns call_id, atomic writes
- Reader: get_by_id, query_by_decision, count
"""

from abc import ABC, abstractmethod
from pathlib import Path

import pytest

from context_builder.schemas.llm_call_record import LLMCallRecord
from context_builder.services.compliance.interfaces import LLMCallStorage


def make_test_call(
    call_id: str = "",
    decision_id: str = None,
    model: str = "gpt-4o",
    doc_id: str = "doc_001",
    claim_id: str = "claim_001",
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
        claim_id=claim_id,
        doc_id=doc_id,
    )


class LLMCallStorageContractTests(ABC):
    """Contract tests that any LLMCallStorage implementation must pass.

    Subclasses must implement `create_storage()` to provide the backend.

    Example:
        class TestFileLLMContract(LLMCallStorageContractTests):
            def create_storage(self, tmp_path: Path) -> LLMCallStorage:
                return FileLLMCallStorage(tmp_path)
    """

    @abstractmethod
    def create_storage(self, tmp_path: Path) -> LLMCallStorage:
        """Create a fresh storage instance for testing.

        Args:
            tmp_path: Temporary directory for storage files.

        Returns:
            A new LLMCallStorage instance.
        """
        pass

    @pytest.fixture
    def storage(self, tmp_path: Path) -> LLMCallStorage:
        """Fixture providing a fresh storage instance."""
        return self.create_storage(tmp_path)

    # =========================================================================
    # Sink Contract
    # =========================================================================

    def test_log_call_assigns_call_id(self, storage: LLMCallStorage):
        """log_call assigns a call_id if not set."""
        record = make_test_call()
        assert not record.call_id

        result = storage.log_call(record)

        assert result.call_id
        assert result.call_id.startswith("llm_")

    def test_log_call_preserves_existing_call_id(self, storage: LLMCallStorage):
        """log_call preserves call_id if already set."""
        record = make_test_call(call_id="custom_llm_123")

        result = storage.log_call(record)

        assert result.call_id == "custom_llm_123"

    def test_log_call_persists_record(self, storage: LLMCallStorage):
        """log_call persists the record for later retrieval."""
        original = storage.log_call(make_test_call())

        found = storage.get_by_id(original.call_id)

        assert found is not None
        assert found.call_id == original.call_id

    def test_log_call_persists_all_fields(self, storage: LLMCallStorage):
        """log_call persists all record fields."""
        original = storage.log_call(make_test_call(
            model="gpt-4o-mini",
            doc_id="doc_xyz",
            claim_id="claim_abc",
            decision_id="dec_123",
        ))

        found = storage.get_by_id(original.call_id)

        assert found.model == "gpt-4o-mini"
        assert found.doc_id == "doc_xyz"
        assert found.claim_id == "claim_abc"
        assert found.decision_id == "dec_123"

    def test_log_call_unique_ids(self, storage: LLMCallStorage):
        """log_call assigns unique IDs to different records."""
        ids = []
        for i in range(5):
            result = storage.log_call(make_test_call())
            ids.append(result.call_id)

        # All IDs should be unique
        assert len(set(ids)) == 5

    def test_log_multiple_calls(self, storage: LLMCallStorage):
        """Multiple calls can be logged."""
        for i in range(5):
            storage.log_call(make_test_call(doc_id=f"doc_{i}"))

        # Verify count matches
        assert storage.count() == 5

    # =========================================================================
    # Reader Contract
    # =========================================================================

    def test_get_by_id_returns_logged_call(self, storage: LLMCallStorage):
        """get_by_id retrieves previously logged call."""
        original = storage.log_call(make_test_call())

        found = storage.get_by_id(original.call_id)

        assert found is not None
        assert found.call_id == original.call_id
        assert found.model == original.model

    def test_get_by_id_returns_none_for_missing(self, storage: LLMCallStorage):
        """get_by_id returns None for non-existent ID."""
        result = storage.get_by_id("nonexistent_id")
        assert result is None

    def test_get_by_id_empty_storage(self, storage: LLMCallStorage):
        """get_by_id returns None on empty storage."""
        result = storage.get_by_id("any_id")
        assert result is None

    def test_query_by_decision_returns_linked_calls(self, storage: LLMCallStorage):
        """query_by_decision returns calls linked to the decision."""
        storage.log_call(make_test_call(decision_id="dec_001"))
        storage.log_call(make_test_call(decision_id="dec_001"))
        storage.log_call(make_test_call(decision_id="dec_002"))

        results = storage.query_by_decision("dec_001")

        assert len(results) == 2
        for r in results:
            assert r.decision_id == "dec_001"

    def test_query_by_decision_returns_empty_for_no_match(self, storage: LLMCallStorage):
        """query_by_decision returns empty list when no matches."""
        storage.log_call(make_test_call(decision_id="dec_001"))

        results = storage.query_by_decision("nonexistent")

        assert results == []

    def test_query_by_decision_empty_storage(self, storage: LLMCallStorage):
        """query_by_decision returns empty list on empty storage."""
        results = storage.query_by_decision("any_id")
        assert results == []

    def test_query_by_decision_with_none_decision_id(self, storage: LLMCallStorage):
        """query_by_decision handles calls with None decision_id."""
        storage.log_call(make_test_call(decision_id=None))
        storage.log_call(make_test_call(decision_id="dec_001"))

        results = storage.query_by_decision("dec_001")

        assert len(results) == 1
        assert results[0].decision_id == "dec_001"

    def test_count_returns_zero_for_empty(self, storage: LLMCallStorage):
        """count() returns 0 for empty storage."""
        assert storage.count() == 0

    def test_count_returns_correct_number(self, storage: LLMCallStorage):
        """count() returns accurate record count."""
        storage.log_call(make_test_call())
        storage.log_call(make_test_call())
        storage.log_call(make_test_call())

        assert storage.count() == 3

    # =========================================================================
    # Protocol Compliance
    # =========================================================================

    def test_implements_llm_call_storage_protocol(self, storage: LLMCallStorage):
        """Storage implements LLMCallStorage protocol."""
        assert isinstance(storage, LLMCallStorage)

    def test_has_log_call_method(self, storage: LLMCallStorage):
        """Storage has log_call method."""
        assert hasattr(storage, "log_call")
        assert callable(storage.log_call)

    def test_has_get_by_id_method(self, storage: LLMCallStorage):
        """Storage has get_by_id method."""
        assert hasattr(storage, "get_by_id")
        assert callable(storage.get_by_id)

    def test_has_query_by_decision_method(self, storage: LLMCallStorage):
        """Storage has query_by_decision method."""
        assert hasattr(storage, "query_by_decision")
        assert callable(storage.query_by_decision)

    # =========================================================================
    # Data Integrity
    # =========================================================================

    def test_record_fields_roundtrip(self, storage: LLMCallStorage):
        """All record fields survive storage roundtrip."""
        original = LLMCallRecord(
            call_id="",
            model="gpt-4o",
            call_purpose="classification",
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            latency_ms=750,
            decision_id="dec_test",
            claim_id="claim_test",
            doc_id="doc_test",
            run_id="run_test",
        )

        logged = storage.log_call(original)
        found = storage.get_by_id(logged.call_id)

        assert found.model == original.model
        assert found.call_purpose == original.call_purpose
        assert found.prompt_tokens == original.prompt_tokens
        assert found.completion_tokens == original.completion_tokens
        assert found.total_tokens == original.total_tokens
        assert found.latency_ms == original.latency_ms
        assert found.decision_id == original.decision_id
        assert found.claim_id == original.claim_id
        assert found.doc_id == original.doc_id
        assert found.run_id == original.run_id
