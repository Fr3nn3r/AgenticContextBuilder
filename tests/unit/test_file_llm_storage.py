"""Unit tests for file-based LLM call storage implementations.

Tests cover:
- FileLLMCallSink: log_call, atomic writes
- FileLLMCallReader: get_by_id, query_by_decision
- FileLLMCallStorage: combined operations
- LLMAuditService facade: backwards compatibility
- AuditedOpenAIClient: interface injection
"""

import json
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from context_builder.schemas.llm_call_record import LLMCallRecord
from context_builder.services.compliance import (
    LLMCallReader,
    LLMCallSink,
    LLMCallStorage,
)
from context_builder.services.compliance.file import (
    FileLLMCallReader,
    FileLLMCallSink,
    FileLLMCallStorage,
)
from context_builder.services.llm_audit import (
    AuditedOpenAIClient,
    LLMAuditService,
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_storage_path(temp_storage_dir):
    """Create a temporary file path for storage."""
    return temp_storage_dir / "llm_calls.jsonl"


def create_test_call(
    model: str = "gpt-4o",
    decision_id: str = None,
    claim_id: str = None,
) -> LLMCallRecord:
    """Create a test LLM call record."""
    return LLMCallRecord(
        call_id="",
        model=model,
        temperature=0.5,
        max_tokens=1000,
        messages=[{"role": "user", "content": "Test message"}],
        decision_id=decision_id,
        claim_id=claim_id,
    )


# =============================================================================
# FileLLMCallSink Tests
# =============================================================================


class TestFileLLMCallSinkBasics:
    """Basic tests for FileLLMCallSink."""

    def test_implements_protocol(self, temp_storage_path):
        """FileLLMCallSink implements LLMCallSink protocol."""
        sink = FileLLMCallSink(temp_storage_path)
        assert isinstance(sink, LLMCallSink)

    def test_log_call_generates_call_id(self, temp_storage_path):
        """log_call generates a unique call_id."""
        sink = FileLLMCallSink(temp_storage_path)
        record = create_test_call()
        result = sink.log_call(record)

        assert result.call_id != ""
        assert result.call_id.startswith("llm_")
        assert len(result.call_id) == 16

    def test_log_call_preserves_existing_call_id(self, temp_storage_path):
        """log_call preserves call_id if already set."""
        sink = FileLLMCallSink(temp_storage_path)
        record = create_test_call()
        record.call_id = "llm_custom12345"
        result = sink.log_call(record)

        assert result.call_id == "llm_custom12345"

    def test_log_call_creates_file(self, temp_storage_path):
        """log_call creates the storage file."""
        sink = FileLLMCallSink(temp_storage_path)
        assert not temp_storage_path.exists()

        sink.log_call(create_test_call())
        assert temp_storage_path.exists()

    def test_log_call_writes_jsonl(self, temp_storage_path):
        """log_call writes valid JSONL."""
        sink = FileLLMCallSink(temp_storage_path)
        sink.log_call(create_test_call())

        with open(temp_storage_path, "r", encoding="utf-8") as f:
            line = f.readline()
            data = json.loads(line)

        assert "call_id" in data
        assert "model" in data
        assert data["model"] == "gpt-4o"

    def test_log_call_appends_multiple(self, temp_storage_path):
        """log_call appends multiple records."""
        sink = FileLLMCallSink(temp_storage_path)

        sink.log_call(create_test_call(model="gpt-4o"))
        sink.log_call(create_test_call(model="gpt-3.5-turbo"))
        sink.log_call(create_test_call(model="gpt-4"))

        with open(temp_storage_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 3


class TestFileLLMCallSinkIdGeneration:
    """Tests for ID generation in FileLLMCallSink."""

    def test_generate_call_id_format(self):
        """Generated call IDs have correct format."""
        call_id = FileLLMCallSink.generate_call_id()
        assert call_id.startswith("llm_")
        assert len(call_id) == 16

    def test_generate_call_id_unique(self):
        """Generated call IDs are unique."""
        ids = {FileLLMCallSink.generate_call_id() for _ in range(100)}
        assert len(ids) == 100


# =============================================================================
# FileLLMCallReader Tests
# =============================================================================


class TestFileLLMCallReaderBasics:
    """Basic tests for FileLLMCallReader."""

    def test_implements_protocol(self, temp_storage_path):
        """FileLLMCallReader implements LLMCallReader protocol."""
        reader = FileLLMCallReader(temp_storage_path)
        assert isinstance(reader, LLMCallReader)

    def test_get_by_id_empty_storage(self, temp_storage_path):
        """get_by_id returns None for empty storage."""
        reader = FileLLMCallReader(temp_storage_path)
        assert reader.get_by_id("llm_nonexistent") is None

    def test_get_by_id_finds_record(self, temp_storage_path):
        """get_by_id returns record when found."""
        sink = FileLLMCallSink(temp_storage_path)
        reader = FileLLMCallReader(temp_storage_path)

        logged = sink.log_call(create_test_call(model="gpt-4o"))
        retrieved = reader.get_by_id(logged.call_id)

        assert retrieved is not None
        assert retrieved.call_id == logged.call_id
        assert retrieved.model == "gpt-4o"

    def test_get_by_id_returns_none_for_missing(self, temp_storage_path):
        """get_by_id returns None when ID not found."""
        sink = FileLLMCallSink(temp_storage_path)
        reader = FileLLMCallReader(temp_storage_path)

        sink.log_call(create_test_call())
        assert reader.get_by_id("llm_nonexistent") is None


class TestFileLLMCallReaderQueryByDecision:
    """Tests for query_by_decision in FileLLMCallReader."""

    def test_query_by_decision_empty_storage(self, temp_storage_path):
        """query_by_decision returns empty list for empty storage."""
        reader = FileLLMCallReader(temp_storage_path)
        results = reader.query_by_decision("dec_nonexistent")
        assert results == []

    def test_query_by_decision_finds_linked_calls(self, temp_storage_path):
        """query_by_decision returns calls linked to decision."""
        sink = FileLLMCallSink(temp_storage_path)
        reader = FileLLMCallReader(temp_storage_path)

        # Log calls with different decision_ids
        sink.log_call(create_test_call(decision_id="dec_abc123"))
        sink.log_call(create_test_call(decision_id="dec_def456"))
        sink.log_call(create_test_call(decision_id="dec_abc123"))

        results = reader.query_by_decision("dec_abc123")

        assert len(results) == 2
        for r in results:
            assert r.decision_id == "dec_abc123"

    def test_query_by_decision_returns_empty_for_no_match(self, temp_storage_path):
        """query_by_decision returns empty list when no matches."""
        sink = FileLLMCallSink(temp_storage_path)
        reader = FileLLMCallReader(temp_storage_path)

        sink.log_call(create_test_call(decision_id="dec_abc123"))
        results = reader.query_by_decision("dec_nonexistent")

        assert results == []


class TestFileLLMCallReaderCount:
    """Tests for count in FileLLMCallReader."""

    def test_count_empty_storage(self, temp_storage_path):
        """count returns 0 for empty storage."""
        reader = FileLLMCallReader(temp_storage_path)
        assert reader.count() == 0

    def test_count_with_records(self, temp_storage_path):
        """count returns correct number of records."""
        sink = FileLLMCallSink(temp_storage_path)
        reader = FileLLMCallReader(temp_storage_path)

        sink.log_call(create_test_call())
        assert reader.count() == 1

        sink.log_call(create_test_call())
        assert reader.count() == 2


# =============================================================================
# FileLLMCallStorage Tests
# =============================================================================


class TestFileLLMCallStorageBasics:
    """Basic tests for FileLLMCallStorage."""

    def test_implements_protocol(self, temp_storage_dir):
        """FileLLMCallStorage implements LLMCallStorage protocol."""
        storage = FileLLMCallStorage(temp_storage_dir)
        assert isinstance(storage, LLMCallStorage)

    def test_combines_all_operations(self, temp_storage_dir):
        """FileLLMCallStorage provides all operations."""
        storage = FileLLMCallStorage(temp_storage_dir)

        # Log call
        record = storage.log_call(create_test_call(model="gpt-4o", decision_id="dec_test"))
        assert record.call_id.startswith("llm_")

        # Get by ID
        retrieved = storage.get_by_id(record.call_id)
        assert retrieved is not None
        assert retrieved.model == "gpt-4o"

        # Query by decision
        results = storage.query_by_decision("dec_test")
        assert len(results) == 1

        # Count
        assert storage.count() == 1

    def test_storage_path_property(self, temp_storage_dir):
        """storage_path property returns correct path."""
        storage = FileLLMCallStorage(temp_storage_dir)
        assert storage.storage_path == temp_storage_dir / "llm_calls.jsonl"

    def test_custom_filename(self, temp_storage_dir):
        """Can use custom filename."""
        storage = FileLLMCallStorage(temp_storage_dir, filename="custom_calls.jsonl")
        storage.log_call(create_test_call())
        assert (temp_storage_dir / "custom_calls.jsonl").exists()


# =============================================================================
# LLMAuditService Facade Tests
# =============================================================================


class TestLLMAuditServiceFacade:
    """Tests for LLMAuditService facade backwards compatibility."""

    def test_log_call_works(self, temp_storage_dir):
        """log_call method works through facade."""
        service = LLMAuditService(temp_storage_dir)
        record = service.log_call(create_test_call())

        assert record.call_id.startswith("llm_")

    def test_get_by_id_works(self, temp_storage_dir):
        """get_by_id method works through facade."""
        service = LLMAuditService(temp_storage_dir)
        logged = service.log_call(create_test_call())

        retrieved = service.get_by_id(logged.call_id)
        assert retrieved is not None

    def test_query_by_decision_works(self, temp_storage_dir):
        """query_by_decision method works through facade."""
        service = LLMAuditService(temp_storage_dir)
        service.log_call(create_test_call(decision_id="dec_test"))

        results = service.query_by_decision("dec_test")
        assert len(results) == 1

    def test_log_file_attribute_exists(self, temp_storage_dir):
        """log_file attribute exists for backwards compatibility."""
        service = LLMAuditService(temp_storage_dir)
        assert hasattr(service, "log_file")
        assert service.log_file == temp_storage_dir / "llm_calls.jsonl"

    def test_storage_dir_attribute_exists(self, temp_storage_dir):
        """storage_dir attribute exists for backwards compatibility."""
        service = LLMAuditService(temp_storage_dir)
        assert hasattr(service, "storage_dir")
        assert service.storage_dir == temp_storage_dir


# =============================================================================
# AuditedOpenAIClient Tests
# =============================================================================


class MockOpenAIResponse:
    """Mock OpenAI chat completion response."""

    def __init__(self, content: str = "Test response"):
        self.choices = [MagicMock(message=MagicMock(content=content), finish_reason="stop")]
        self.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self, response: MockOpenAIResponse = None):
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock(return_value=response or MockOpenAIResponse())


class TestAuditedOpenAIClientWithInterface:
    """Tests for AuditedOpenAIClient with LLMCallSink interface."""

    def test_accepts_llm_call_sink(self, temp_storage_dir):
        """AuditedOpenAIClient accepts LLMCallSink interface."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()

        audited = AuditedOpenAIClient(client, sink)
        assert audited._sink is sink

    def test_accepts_llm_audit_service(self, temp_storage_dir):
        """AuditedOpenAIClient accepts LLMAuditService for backwards compatibility."""
        service = LLMAuditService(temp_storage_dir)
        client = MockOpenAIClient()

        audited = AuditedOpenAIClient(client, service)
        assert audited._sink is service

    def test_logs_to_injected_sink(self, temp_storage_dir):
        """Calls are logged to the injected sink."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()
        audited = AuditedOpenAIClient(client, sink)

        audited.chat_completions_create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert sink.count() == 1
        calls = list(sink.query_by_decision(""))  # Get all calls
        # Since no decision_id set, query won't find by decision, but count shows it's logged

    def test_audit_service_attribute_exposed(self, temp_storage_dir):
        """audit_service attribute exposed for backwards compatibility."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()

        audited = AuditedOpenAIClient(client, sink)
        assert hasattr(audited, "audit_service")
        assert audited.audit_service is sink


class TestAuditedOpenAIClientContext:
    """Tests for context management in AuditedOpenAIClient."""

    def test_set_context(self, temp_storage_dir):
        """set_context sets all context fields."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()
        audited = AuditedOpenAIClient(client, sink)

        audited.set_context(
            claim_id="CLM001",
            doc_id="DOC001",
            run_id="run_123",
            decision_id="dec_456",
            call_purpose="classification",
        )

        assert audited._claim_id == "CLM001"
        assert audited._doc_id == "DOC001"
        assert audited._run_id == "run_123"
        assert audited._decision_id == "dec_456"
        assert audited._call_purpose == "classification"

    def test_clear_context(self, temp_storage_dir):
        """clear_context clears all context fields."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()
        audited = AuditedOpenAIClient(client, sink)

        audited.set_context(claim_id="CLM001", doc_id="DOC001")
        audited.clear_context()

        assert audited._claim_id is None
        assert audited._doc_id is None

    def test_context_logged_with_call(self, temp_storage_dir):
        """Context is included in logged call record."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()
        audited = AuditedOpenAIClient(client, sink)

        audited.set_context(
            claim_id="CLM001",
            decision_id="dec_test123",
            call_purpose="classification",
        )

        audited.chat_completions_create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

        results = sink.query_by_decision("dec_test123")
        assert len(results) == 1
        assert results[0].claim_id == "CLM001"
        assert results[0].call_purpose == "classification"


class TestAuditedOpenAIClientRetry:
    """Tests for retry tracking in AuditedOpenAIClient."""

    def test_mark_retry_increments_attempt(self, temp_storage_dir):
        """mark_retry increments attempt_number."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()
        audited = AuditedOpenAIClient(client, sink)

        assert audited._attempt_number == 1

        audited.mark_retry("llm_previous123")
        assert audited._attempt_number == 2
        assert audited._previous_call_id == "llm_previous123"

    def test_retry_info_logged(self, temp_storage_dir):
        """Retry information is included in logged call."""
        sink = FileLLMCallStorage(temp_storage_dir)
        client = MockOpenAIClient()
        audited = AuditedOpenAIClient(client, sink)

        # First call
        audited.chat_completions_create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Mark as retry and make second call
        audited.mark_retry("llm_first_call")
        audited.chat_completions_create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello again"}],
        )

        # Check the logged calls
        with open(sink.storage_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        first_call = json.loads(lines[0])
        second_call = json.loads(lines[1])

        assert first_call["attempt_number"] == 1
        assert first_call["is_retry"] is False

        assert second_call["attempt_number"] == 2
        assert second_call["is_retry"] is True
        assert second_call["previous_call_id"] == "llm_first_call"


# =============================================================================
# NullLLMCallSink Tests
# =============================================================================


class TestNullLLMCallSinkBasics:
    """Tests for NullLLMCallSink (no-op logging)."""

    def test_implements_protocol(self):
        """NullLLMCallSink implements LLMCallSink protocol."""
        from context_builder.services.compliance.file import NullLLMCallSink

        sink = NullLLMCallSink()
        assert isinstance(sink, LLMCallSink)

    def test_log_call_generates_call_id(self):
        """log_call generates a unique call_id."""
        from context_builder.services.compliance.file import NullLLMCallSink

        sink = NullLLMCallSink()
        record = create_test_call()
        result = sink.log_call(record)

        assert result.call_id != ""
        assert result.call_id.startswith("llm_")
        assert len(result.call_id) == 16

    def test_log_call_preserves_existing_call_id(self):
        """log_call preserves call_id if already set."""
        from context_builder.services.compliance.file import NullLLMCallSink

        sink = NullLLMCallSink()
        record = create_test_call()
        record.call_id = "llm_custom12345"
        result = sink.log_call(record)

        assert result.call_id == "llm_custom12345"

    def test_log_call_does_not_write_file(self, temp_storage_dir):
        """log_call does not write any files (no-op)."""
        from context_builder.services.compliance.file import NullLLMCallSink

        sink = NullLLMCallSink()
        sink.log_call(create_test_call())

        # No files should be created
        assert list(temp_storage_dir.iterdir()) == []


# =============================================================================
# NullLLMCallStorage Tests
# =============================================================================


class TestNullLLMCallStorageBasics:
    """Tests for NullLLMCallStorage (no-op logging)."""

    def test_implements_protocol(self):
        """NullLLMCallStorage implements LLMCallStorage protocol."""
        from context_builder.services.compliance.file import NullLLMCallStorage

        storage = NullLLMCallStorage()
        assert isinstance(storage, LLMCallStorage)

    def test_log_call_returns_record(self):
        """log_call returns the record with call_id."""
        from context_builder.services.compliance.file import NullLLMCallStorage

        storage = NullLLMCallStorage()
        record = create_test_call()
        result = storage.log_call(record)

        assert result.call_id.startswith("llm_")

    def test_get_by_id_always_returns_none(self):
        """get_by_id always returns None (nothing stored)."""
        from context_builder.services.compliance.file import NullLLMCallStorage

        storage = NullLLMCallStorage()
        storage.log_call(create_test_call())

        assert storage.get_by_id("llm_any_id") is None

    def test_query_by_decision_always_returns_empty(self):
        """query_by_decision always returns empty list."""
        from context_builder.services.compliance.file import NullLLMCallStorage

        storage = NullLLMCallStorage()
        record = create_test_call(decision_id="dec_123")
        storage.log_call(record)

        assert storage.query_by_decision("dec_123") == []

    def test_count_always_returns_zero(self):
        """count always returns 0 (nothing stored)."""
        from context_builder.services.compliance.file import NullLLMCallStorage

        storage = NullLLMCallStorage()
        storage.log_call(create_test_call())
        storage.log_call(create_test_call())

        assert storage.count() == 0


# =============================================================================
# Factory with LLM Logging Disabled Tests
# =============================================================================


class TestFactoryWithLLMLoggingDisabled:
    """Tests for factory behavior when LLM logging is disabled."""

    def test_creates_null_storage_when_disabled(self, temp_storage_dir):
        """Factory returns NullLLMCallStorage when llm_logging_enabled=False."""
        from context_builder.services.compliance import (
            ComplianceStorageConfig,
            ComplianceStorageFactory,
        )
        from context_builder.services.compliance.file import NullLLMCallStorage

        config = ComplianceStorageConfig(
            storage_dir=temp_storage_dir,
            llm_logging_enabled=False,
        )
        storage = ComplianceStorageFactory.create_llm_storage(config)

        assert isinstance(storage, NullLLMCallStorage)

    def test_creates_file_storage_when_enabled(self, temp_storage_dir):
        """Factory returns FileLLMCallStorage when llm_logging_enabled=True."""
        from context_builder.services.compliance import (
            ComplianceStorageConfig,
            ComplianceStorageFactory,
        )
        from context_builder.services.compliance.file import FileLLMCallStorage

        config = ComplianceStorageConfig(
            storage_dir=temp_storage_dir,
            llm_logging_enabled=True,
        )
        storage = ComplianceStorageFactory.create_llm_storage(config)

        assert isinstance(storage, FileLLMCallStorage)

    def test_default_is_logging_enabled(self, temp_storage_dir):
        """Default config has llm_logging_enabled=True."""
        from context_builder.services.compliance import ComplianceStorageConfig

        config = ComplianceStorageConfig(storage_dir=temp_storage_dir)
        assert config.llm_logging_enabled is True
