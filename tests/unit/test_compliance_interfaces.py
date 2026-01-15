"""Unit tests for compliance storage interfaces and factories.

Tests cover:
- Protocol definitions and runtime checking
- DecisionRecordFactory methods
- Hash computation for decision records
"""

import hashlib
import json
from typing import List, Optional

import pytest

from context_builder.schemas.decision_record import (
    DecisionOutcome,
    DecisionQuery,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
    EvidenceCitation,
    IntegrityReport,
    RuleTrace,
)
from context_builder.schemas.llm_call_record import LLMCallRecord
from context_builder.services.compliance import (
    DecisionAppender,
    DecisionReader,
    DecisionRecordFactory,
    DecisionStorage,
    DecisionVerifier,
    LLMCallReader,
    LLMCallSink,
    LLMCallStorage,
)


# =============================================================================
# Mock implementations for protocol testing
# =============================================================================


class MockDecisionAppender:
    """Mock implementation of DecisionAppender protocol."""

    def __init__(self):
        self.records: List[DecisionRecord] = []

    def append(self, record: DecisionRecord) -> DecisionRecord:
        self.records.append(record)
        return record


class MockDecisionReader:
    """Mock implementation of DecisionReader protocol."""

    def __init__(self, records: Optional[List[DecisionRecord]] = None):
        self.records = records or []

    def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        for r in self.records:
            if r.decision_id == decision_id:
                return r
        return None

    def query(self, filters: Optional[DecisionQuery] = None) -> List[DecisionRecord]:
        return self.records

    def count(self) -> int:
        return len(self.records)


class MockDecisionVerifier:
    """Mock implementation of DecisionVerifier protocol."""

    def __init__(self, valid: bool = True):
        self._valid = valid

    def verify_integrity(self) -> IntegrityReport:
        return IntegrityReport(valid=self._valid, total_records=0)


class MockDecisionStorage(MockDecisionAppender, MockDecisionReader, MockDecisionVerifier):
    """Mock implementation of combined DecisionStorage protocol."""

    def __init__(self):
        MockDecisionAppender.__init__(self)
        MockDecisionReader.__init__(self, self.records)
        MockDecisionVerifier.__init__(self)


class MockLLMCallSink:
    """Mock implementation of LLMCallSink protocol."""

    def __init__(self):
        self.calls: List[LLMCallRecord] = []

    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        self.calls.append(record)
        return record


class MockLLMCallReader:
    """Mock implementation of LLMCallReader protocol."""

    def __init__(self, calls: Optional[List[LLMCallRecord]] = None):
        self.calls = calls or []

    def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]:
        for c in self.calls:
            if c.call_id == call_id:
                return c
        return None

    def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]:
        return [c for c in self.calls if c.decision_id == decision_id]


class MockLLMCallStorage(MockLLMCallSink, MockLLMCallReader):
    """Mock implementation of combined LLMCallStorage protocol."""

    def __init__(self):
        MockLLMCallSink.__init__(self)
        MockLLMCallReader.__init__(self, self.calls)


# =============================================================================
# Protocol Tests
# =============================================================================


class TestDecisionProtocols:
    """Tests for Decision storage protocol definitions."""

    def test_decision_appender_is_protocol(self):
        """DecisionAppender is a runtime-checkable Protocol."""
        mock = MockDecisionAppender()
        assert isinstance(mock, DecisionAppender)

    def test_decision_reader_is_protocol(self):
        """DecisionReader is a runtime-checkable Protocol."""
        mock = MockDecisionReader()
        assert isinstance(mock, DecisionReader)

    def test_decision_verifier_is_protocol(self):
        """DecisionVerifier is a runtime-checkable Protocol."""
        mock = MockDecisionVerifier()
        assert isinstance(mock, DecisionVerifier)

    def test_decision_storage_is_protocol(self):
        """DecisionStorage is a runtime-checkable Protocol."""
        mock = MockDecisionStorage()
        assert isinstance(mock, DecisionStorage)

    def test_decision_storage_combines_all_protocols(self):
        """DecisionStorage satisfies all sub-protocols."""
        mock = MockDecisionStorage()
        assert isinstance(mock, DecisionAppender)
        assert isinstance(mock, DecisionReader)
        assert isinstance(mock, DecisionVerifier)


class TestLLMCallProtocols:
    """Tests for LLM Call storage protocol definitions."""

    def test_llm_call_sink_is_protocol(self):
        """LLMCallSink is a runtime-checkable Protocol."""
        mock = MockLLMCallSink()
        assert isinstance(mock, LLMCallSink)

    def test_llm_call_reader_is_protocol(self):
        """LLMCallReader is a runtime-checkable Protocol."""
        mock = MockLLMCallReader()
        assert isinstance(mock, LLMCallReader)

    def test_llm_call_storage_is_protocol(self):
        """LLMCallStorage is a runtime-checkable Protocol."""
        mock = MockLLMCallStorage()
        assert isinstance(mock, LLMCallStorage)

    def test_llm_call_storage_combines_both_protocols(self):
        """LLMCallStorage satisfies both sub-protocols."""
        mock = MockLLMCallStorage()
        assert isinstance(mock, LLMCallSink)
        assert isinstance(mock, LLMCallReader)


# =============================================================================
# LLMCallRecord Schema Tests
# =============================================================================


class TestLLMCallRecordSchema:
    """Tests for LLMCallRecord dataclass."""

    def test_default_call_id_generated(self):
        """Default call_id is generated with llm_ prefix."""
        record = LLMCallRecord()
        assert record.call_id.startswith("llm_")
        assert len(record.call_id) == 16  # "llm_" + 12 hex chars

    def test_default_created_at_is_iso_timestamp(self):
        """Default created_at is ISO timestamp with Z suffix."""
        record = LLMCallRecord()
        assert record.created_at.endswith("Z")
        assert "T" in record.created_at

    def test_all_optional_fields_default_to_none(self):
        """Optional fields default to None or appropriate defaults."""
        record = LLMCallRecord()
        assert record.response_content is None
        assert record.decision_id is None
        assert record.error is None
        assert record.attempt_number == 1
        assert record.is_retry is False

    def test_custom_values_preserved(self):
        """Custom values are preserved when creating record."""
        record = LLMCallRecord(
            call_id="llm_custom123456",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=1000,
            decision_id="dec_abc123",
            claim_id="CLM001",
        )
        assert record.call_id == "llm_custom123456"
        assert record.model == "gpt-4o"
        assert record.temperature == 0.7
        assert record.max_tokens == 1000
        assert record.decision_id == "dec_abc123"
        assert record.claim_id == "CLM001"


# =============================================================================
# DecisionRecordFactory Tests
# =============================================================================


class TestDecisionRecordFactoryBasics:
    """Basic tests for DecisionRecordFactory."""

    @pytest.fixture
    def factory(self):
        """Create a factory with a mock previous hash provider."""
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_generate_decision_id_format(self):
        """Generated decision IDs have correct format."""
        decision_id = DecisionRecordFactory.generate_decision_id()
        assert decision_id.startswith("dec_")
        assert len(decision_id) == 16  # "dec_" + 12 hex chars

    def test_generate_decision_id_unique(self):
        """Generated decision IDs are unique."""
        ids = {DecisionRecordFactory.generate_decision_id() for _ in range(100)}
        assert len(ids) == 100

    def test_compute_hash_returns_sha256(self, factory):
        """compute_hash returns a valid SHA-256 hex string."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test classification",
        )
        hash_value = DecisionRecordFactory.compute_hash(record)
        assert len(hash_value) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_compute_hash_deterministic(self, factory):
        """Same record produces same hash."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test classification",
        )
        hash1 = DecisionRecordFactory.compute_hash(record)
        hash2 = DecisionRecordFactory.compute_hash(record)
        assert hash1 == hash2

    def test_compute_hash_different_for_different_content(self, factory):
        """Different records produce different hashes."""
        record1 = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test classification 1",
        )
        record2 = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test classification 2",
        )
        hash1 = DecisionRecordFactory.compute_hash(record1)
        hash2 = DecisionRecordFactory.compute_hash(record2)
        assert hash1 != hash2


class TestDecisionRecordFactoryClassification:
    """Tests for classification decision creation."""

    @pytest.fixture
    def factory(self):
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_creates_classification_type(self, factory):
        """Creates record with CLASSIFICATION decision type."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Classified as invoice",
        )
        assert record.decision_type == DecisionType.CLASSIFICATION

    def test_sets_doc_type_in_outcome(self, factory):
        """Sets doc_type in outcome."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Classified as invoice",
        )
        assert record.outcome.doc_type == "invoice"
        assert record.outcome.doc_type_confidence == 0.95

    def test_sets_rationale(self, factory):
        """Sets rationale with summary and confidence."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.85,
            summary="High confidence invoice detection",
        )
        assert record.rationale.summary == "High confidence invoice detection"
        assert record.rationale.confidence == 0.85

    def test_includes_llm_call_ids(self, factory):
        """Includes LLM call IDs when provided."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
            llm_call_ids=["llm_abc123"],
        )
        assert record.rationale.llm_call_ids == ["llm_abc123"]

    def test_includes_context_ids(self, factory):
        """Includes context IDs when provided."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
            claim_id="CLM001",
            doc_id="DOC123",
            run_id="run_abc",
        )
        assert record.claim_id == "CLM001"
        assert record.doc_id == "DOC123"
        assert record.run_id == "run_abc"

    def test_default_actor_is_openai_classifier(self, factory):
        """Default actor_id is openai_classifier."""
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
        )
        assert record.actor_type == "system"
        assert record.actor_id == "openai_classifier"


class TestDecisionRecordFactoryExtraction:
    """Tests for extraction decision creation."""

    @pytest.fixture
    def factory(self):
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_creates_extraction_type(self, factory):
        """Creates record with EXTRACTION decision type."""
        record = factory.create_extraction_decision(
            fields_extracted=[{"name": "invoice_number", "value": "INV-001"}],
            confidence=0.9,
            summary="Extracted invoice fields",
        )
        assert record.decision_type == DecisionType.EXTRACTION

    def test_sets_fields_in_outcome(self, factory):
        """Sets extracted fields in outcome."""
        fields = [
            {"name": "invoice_number", "value": "INV-001"},
            {"name": "total", "value": "100.00"},
        ]
        record = factory.create_extraction_decision(
            fields_extracted=fields,
            confidence=0.9,
            summary="Test",
        )
        assert record.outcome.fields_extracted == fields

    def test_sets_quality_gate_status(self, factory):
        """Sets quality gate status when provided."""
        record = factory.create_extraction_decision(
            fields_extracted=[],
            confidence=0.9,
            summary="Test",
            quality_gate_status="pass",
        )
        assert record.outcome.quality_gate_status == "pass"

    def test_sets_missing_required_fields(self, factory):
        """Sets missing required fields when provided."""
        record = factory.create_extraction_decision(
            fields_extracted=[],
            confidence=0.5,
            summary="Test",
            missing_required_fields=["invoice_number", "date"],
        )
        assert record.outcome.missing_required_fields == ["invoice_number", "date"]

    def test_default_actor_is_generic_extractor(self, factory):
        """Default actor_id is generic_extractor."""
        record = factory.create_extraction_decision(
            fields_extracted=[],
            confidence=0.9,
            summary="Test",
        )
        assert record.actor_id == "generic_extractor"


class TestDecisionRecordFactoryQualityGate:
    """Tests for quality gate decision creation."""

    @pytest.fixture
    def factory(self):
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_creates_quality_gate_type(self, factory):
        """Creates record with QUALITY_GATE decision type."""
        record = factory.create_quality_gate_decision(
            status="pass",
            confidence=1.0,
            summary="All required fields present",
        )
        assert record.decision_type == DecisionType.QUALITY_GATE

    def test_sets_status_in_outcome(self, factory):
        """Sets quality gate status in outcome."""
        record = factory.create_quality_gate_decision(
            status="warn",
            confidence=0.8,
            summary="Some fields low confidence",
        )
        assert record.outcome.quality_gate_status == "warn"

    def test_default_actor_is_quality_gate(self, factory):
        """Default actor_id is quality_gate."""
        record = factory.create_quality_gate_decision(
            status="pass",
            confidence=1.0,
            summary="Test",
        )
        assert record.actor_id == "quality_gate"


class TestDecisionRecordFactoryHumanReview:
    """Tests for human review decision creation."""

    @pytest.fixture
    def factory(self):
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_creates_human_review_type(self, factory):
        """Creates record with HUMAN_REVIEW decision type."""
        record = factory.create_human_review_decision(
            summary="Reviewed and approved",
        )
        assert record.decision_type == DecisionType.HUMAN_REVIEW

    def test_sets_actor_type_to_human(self, factory):
        """Sets actor_type to human."""
        record = factory.create_human_review_decision(
            summary="Test",
            actor_id="user@example.com",
        )
        assert record.actor_type == "human"
        assert record.actor_id == "user@example.com"

    def test_confidence_is_one(self, factory):
        """Human review confidence is always 1.0 (authoritative)."""
        record = factory.create_human_review_decision(summary="Test")
        assert record.rationale.confidence == 1.0

    def test_sets_field_corrections(self, factory):
        """Sets field corrections when provided."""
        corrections = [{"field": "invoice_number", "old": "INV-001", "new": "INV-002"}]
        record = factory.create_human_review_decision(
            summary="Corrected invoice number",
            field_corrections=corrections,
        )
        assert record.outcome.field_corrections == corrections


class TestDecisionRecordFactoryOverride:
    """Tests for override decision creation."""

    @pytest.fixture
    def factory(self):
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_creates_override_type(self, factory):
        """Creates record with OVERRIDE decision type."""
        record = factory.create_override_decision(
            original_value="invoice",
            override_value="receipt",
            override_reason="Misclassified",
            summary="Document type override",
        )
        assert record.decision_type == DecisionType.OVERRIDE

    def test_sets_override_values_in_outcome(self, factory):
        """Sets original and override values in outcome."""
        record = factory.create_override_decision(
            original_value="invoice",
            override_value="receipt",
            override_reason="Misclassified",
            summary="Test",
        )
        assert record.outcome.original_value == "invoice"
        assert record.outcome.override_value == "receipt"
        assert record.outcome.override_reason == "Misclassified"

    def test_confidence_is_one(self, factory):
        """Override confidence is always 1.0 (explicit decision)."""
        record = factory.create_override_decision(
            original_value="a",
            override_value="b",
            override_reason="Test",
            summary="Test",
        )
        assert record.rationale.confidence == 1.0


class TestDecisionRecordFactoryHashChain:
    """Tests for hash chain integration in factory."""

    def test_uses_provided_previous_hash(self):
        """Factory uses provided previous_hash callback."""
        factory = DecisionRecordFactory(get_previous_hash=lambda: "abc123def456")
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
        )
        assert record.previous_hash == "abc123def456"

    def test_genesis_for_first_record(self):
        """First record uses GENESIS as previous_hash."""
        factory = DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
        )
        assert record.previous_hash == "GENESIS"

    def test_callback_called_for_each_record(self):
        """Previous hash callback is called for each record creation."""
        call_count = [0]
        hashes = ["GENESIS", "hash_1", "hash_2"]

        def get_hash():
            idx = call_count[0]
            call_count[0] += 1
            return hashes[idx]

        factory = DecisionRecordFactory(get_previous_hash=get_hash)

        r1 = factory.create_classification_decision(
            doc_type="a", confidence=0.9, summary="1"
        )
        r2 = factory.create_classification_decision(
            doc_type="b", confidence=0.9, summary="2"
        )
        r3 = factory.create_classification_decision(
            doc_type="c", confidence=0.9, summary="3"
        )

        assert r1.previous_hash == "GENESIS"
        assert r2.previous_hash == "hash_1"
        assert r3.previous_hash == "hash_2"
        assert call_count[0] == 3


class TestDecisionRecordFactoryEvidence:
    """Tests for evidence citation and rule trace support."""

    @pytest.fixture
    def factory(self):
        return DecisionRecordFactory(get_previous_hash=lambda: "GENESIS")

    def test_includes_evidence_citations(self, factory):
        """Evidence citations are included in rationale."""
        citations = [
            EvidenceCitation(
                doc_id="DOC123",
                page=1,
                text_quote="Invoice No: INV-001",
            )
        ]
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
            evidence_citations=citations,
        )
        assert len(record.rationale.evidence_citations) == 1
        assert record.rationale.evidence_citations[0].doc_id == "DOC123"

    def test_includes_rule_traces(self, factory):
        """Rule traces are included in rationale."""
        rules = [
            RuleTrace(
                rule_name="keyword_match",
                input_values={"keyword": "invoice"},
                output_value=True,
                triggered=True,
            )
        ]
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            summary="Test",
            rule_traces=rules,
        )
        assert len(record.rationale.rule_traces) == 1
        assert record.rationale.rule_traces[0].rule_name == "keyword_match"
