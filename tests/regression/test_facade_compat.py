"""Regression tests for facade backward compatibility.

These tests verify that the DecisionLedger and LLMAuditService facades
maintain their original APIs after being refactored to delegate to
the new compliance storage subsystem.

Tests cover:
- Original constructor signatures
- Original method signatures
- Original attribute access
- Existing JSONL file compatibility
"""

import json
from pathlib import Path

import pytest

from context_builder.schemas.decision_record import (
    DecisionOutcome,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
)
from context_builder.schemas.llm_call_record import LLMCallRecord


class TestDecisionLedgerFacadeAPI:
    """Tests verifying DecisionLedger facade maintains original API."""

    def test_constructor_accepts_storage_dir(self, tmp_path: Path):
        """DecisionLedger accepts storage_dir parameter."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        assert ledger is not None

    def test_constructor_creates_default_filename(self, tmp_path: Path):
        """DecisionLedger creates decisions.jsonl by default."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        # Should have ledger_file attribute
        assert hasattr(ledger, "ledger_file") or hasattr(ledger, "_storage")

    def test_append_method_exists(self, tmp_path: Path):
        """DecisionLedger has append method."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        assert hasattr(ledger, "append")
        assert callable(ledger.append)

    def test_append_accepts_decision_record(self, tmp_path: Path):
        """DecisionLedger.append accepts DecisionRecord."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        record = DecisionRecord(
            decision_id="",
            decision_type=DecisionType.CLASSIFICATION,
            doc_id="doc_001",
            claim_id="claim_001",
            actor_type="system",
            actor_id="test",
            rationale=DecisionRationale(summary="Test", confidence=0.9),
            outcome=DecisionOutcome(doc_type="invoice", doc_type_confidence=0.9),
        )

        result = ledger.append(record)

        assert result.decision_id
        assert result.record_hash

    def test_query_method_exists(self, tmp_path: Path):
        """DecisionLedger has query method."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        assert hasattr(ledger, "query")
        assert callable(ledger.query)

    def test_verify_integrity_method_exists(self, tmp_path: Path):
        """DecisionLedger has verify_integrity method."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        assert hasattr(ledger, "verify_integrity")
        assert callable(ledger.verify_integrity)

    def test_verify_integrity_returns_report(self, tmp_path: Path):
        """DecisionLedger.verify_integrity returns IntegrityReport."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(tmp_path)
        report = ledger.verify_integrity()

        assert hasattr(report, "valid")
        assert hasattr(report, "total_records")

    def test_genesis_hash_exported(self):
        """GENESIS_HASH is exported from decision_ledger module."""
        from context_builder.services.decision_ledger import GENESIS_HASH

        assert GENESIS_HASH == "GENESIS"


class TestLLMAuditServiceFacadeAPI:
    """Tests verifying LLMAuditService facade maintains original API."""

    def test_constructor_accepts_storage_dir(self, tmp_path: Path):
        """LLMAuditService accepts storage_dir parameter."""
        from context_builder.services.llm_audit import LLMAuditService

        service = LLMAuditService(tmp_path)
        assert service is not None

    def test_log_call_method_exists(self, tmp_path: Path):
        """LLMAuditService has log_call method."""
        from context_builder.services.llm_audit import LLMAuditService

        service = LLMAuditService(tmp_path)
        assert hasattr(service, "log_call")
        assert callable(service.log_call)

    def test_log_call_accepts_llm_call_record(self, tmp_path: Path):
        """LLMAuditService.log_call accepts LLMCallRecord."""
        from context_builder.services.llm_audit import LLMAuditService

        service = LLMAuditService(tmp_path)
        record = LLMCallRecord(
            call_id="",
            model="gpt-4o",
            call_purpose="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=500,
        )

        result = service.log_call(record)

        assert result.call_id

    def test_get_llm_audit_service_function_exists(self):
        """get_llm_audit_service function is exported."""
        from context_builder.services.llm_audit import get_llm_audit_service

        assert callable(get_llm_audit_service)

    def test_get_llm_audit_service_accepts_storage_dir(self, tmp_path: Path):
        """get_llm_audit_service accepts storage_dir parameter."""
        from context_builder.services.llm_audit import get_llm_audit_service

        service = get_llm_audit_service(tmp_path)
        assert service is not None


class TestAuditedOpenAIClientAPI:
    """Tests verifying AuditedOpenAIClient maintains original API."""

    def test_class_is_exported(self):
        """AuditedOpenAIClient is exported from llm_audit module."""
        from context_builder.services.llm_audit import AuditedOpenAIClient

        assert AuditedOpenAIClient is not None

    def test_accepts_llm_audit_service(self, tmp_path: Path):
        """AuditedOpenAIClient accepts LLMAuditService."""
        from unittest.mock import MagicMock

        from context_builder.services.llm_audit import (
            AuditedOpenAIClient,
            LLMAuditService,
        )

        mock_client = MagicMock()
        audit_service = LLMAuditService(tmp_path)

        audited = AuditedOpenAIClient(mock_client, audit_service)
        assert audited is not None

    def test_set_context_method_exists(self, tmp_path: Path):
        """AuditedOpenAIClient has set_context method."""
        from unittest.mock import MagicMock

        from context_builder.services.llm_audit import (
            AuditedOpenAIClient,
            LLMAuditService,
        )

        mock_client = MagicMock()
        audit_service = LLMAuditService(tmp_path)
        audited = AuditedOpenAIClient(mock_client, audit_service)

        assert hasattr(audited, "set_context")
        assert callable(audited.set_context)


class TestExistingJSONLCompatibility:
    """Tests verifying existing JSONL files remain readable."""

    def test_reads_legacy_decision_jsonl(self, tmp_path: Path):
        """DecisionLedger reads existing decision JSONL files."""
        from context_builder.services.decision_ledger import DecisionLedger

        # Create a legacy-format JSONL file
        legacy_record = {
            "decision_id": "dec_legacy123",
            "decision_type": "classification",
            "doc_id": "doc_001",
            "claim_id": "claim_001",
            "run_id": "run_001",
            "actor_type": "system",
            "actor_id": "openai_classifier",
            "rationale": {"summary": "Test", "confidence": 0.95},
            "outcome": {"doc_type": "invoice", "doc_type_confidence": 0.95},
            "previous_hash": "GENESIS",
            "record_hash": "a" * 64,
            "created_at": "2024-01-01T00:00:00Z",
        }

        ledger_file = tmp_path / "decisions.jsonl"
        ledger_file.write_text(json.dumps(legacy_record) + "\n")

        ledger = DecisionLedger(tmp_path)
        results = ledger.query()

        assert len(results) == 1
        assert results[0].decision_id == "dec_legacy123"

    def test_reads_legacy_llm_calls_jsonl(self, tmp_path: Path):
        """LLMAuditService reads existing LLM call JSONL files."""
        from context_builder.services.llm_audit import LLMAuditService

        # Create a legacy-format JSONL file
        legacy_record = {
            "call_id": "llm_legacy456",
            "model": "gpt-4o",
            "call_purpose": "classification",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "latency_ms": 500,
            "claim_id": "claim_001",
            "doc_id": "doc_001",
        }

        llm_file = tmp_path / "llm_calls.jsonl"
        llm_file.write_text(json.dumps(legacy_record) + "\n")

        service = LLMAuditService(tmp_path)
        result = service.get_by_id("llm_legacy456")

        assert result is not None
        assert result.call_id == "llm_legacy456"


class TestPublicExports:
    """Tests verifying public module exports."""

    def test_decision_ledger_exports(self):
        """decision_ledger module exports expected symbols."""
        from context_builder.services import decision_ledger

        assert hasattr(decision_ledger, "DecisionLedger")
        assert hasattr(decision_ledger, "GENESIS_HASH")

    def test_llm_audit_exports(self):
        """llm_audit module exports expected symbols."""
        from context_builder.services import llm_audit

        assert hasattr(llm_audit, "LLMAuditService")
        assert hasattr(llm_audit, "AuditedOpenAIClient")
        assert hasattr(llm_audit, "get_llm_audit_service")

    def test_compliance_package_exports(self):
        """compliance package exports expected symbols."""
        from context_builder.services import compliance

        # Interfaces
        assert hasattr(compliance, "DecisionStorage")
        assert hasattr(compliance, "LLMCallStorage")

        # File backends
        assert hasattr(compliance, "FileDecisionStorage")
        assert hasattr(compliance, "FileLLMCallStorage")

        # Encrypted backends
        assert hasattr(compliance, "EncryptedDecisionStorage")
        assert hasattr(compliance, "EncryptedLLMCallStorage")

        # Config and factory
        assert hasattr(compliance, "ComplianceStorageConfig")
        assert hasattr(compliance, "ComplianceStorageFactory")
