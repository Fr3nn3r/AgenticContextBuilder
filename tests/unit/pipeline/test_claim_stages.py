"""Unit tests for claim-level pipeline stages."""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from context_builder.pipeline.claim_stages.context import (
    ClaimContext,
    ClaimStageConfig,
    ClaimStageTimings,
    ClaimProcessingResult,
)
from context_builder.pipeline.claim_stages.reconciliation import ReconciliationStage


class TestClaimStageConfig:
    """Tests for ClaimStageConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = ClaimStageConfig()

        assert config.run_reconciliation is True
        assert config.run_enrichment is True
        assert config.run_processing is True
        assert config.processing_type == "assessment"

    def test_run_kind_full(self):
        """Test run_kind returns 'full' when all stages enabled."""
        config = ClaimStageConfig(
            run_reconciliation=True,
            run_processing=True,
        )

        assert config.run_kind == "full"

    def test_run_kind_processing_only(self):
        """Test run_kind returns 'processing_only' when only processing enabled."""
        config = ClaimStageConfig(
            run_reconciliation=False,
            run_processing=True,
        )

        assert config.run_kind == "processing_only"

    def test_run_kind_reconciliation_only(self):
        """Test run_kind returns 'reconciliation_only' when only reconciliation enabled."""
        config = ClaimStageConfig(
            run_reconciliation=True,
            run_processing=False,
        )

        assert config.run_kind == "reconciliation_only"

    def test_run_kind_none(self):
        """Test run_kind returns 'none' when no stages enabled."""
        config = ClaimStageConfig(
            run_reconciliation=False,
            run_processing=False,
        )

        assert config.run_kind == "none"


class TestClaimStageTimings:
    """Tests for ClaimStageTimings dataclass."""

    def test_default_values(self):
        """Test that default values are zero."""
        timings = ClaimStageTimings()

        assert timings.reconciliation_ms == 0
        assert timings.enrichment_ms == 0
        assert timings.processing_ms == 0
        assert timings.total_ms == 0


class TestClaimContext:
    """Tests for ClaimContext dataclass."""

    def test_creation_with_required_fields(self, tmp_path):
        """Test creating a ClaimContext with required fields."""
        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
        )

        assert context.claim_id == "CLM-001"
        assert context.workspace_path == tmp_path
        assert context.run_id == "run_001"
        assert context.status == "pending"
        assert context.current_stage == "setup"

    def test_notify_token_update(self, tmp_path):
        """Test that token update callback is invoked."""
        callback_called = []

        def token_callback(input_tokens, output_tokens):
            callback_called.append((input_tokens, output_tokens))

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            on_token_update=token_callback,
        )

        context.notify_token_update(100, 50)

        assert len(callback_called) == 1
        assert callback_called[0] == (100, 50)
        assert context.input_tokens == 100
        assert context.output_tokens == 50

    def test_notify_token_update_no_callback(self, tmp_path):
        """Test that notify_token_update works without callback."""
        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
        )

        # Should not raise
        context.notify_token_update(100, 50)

        assert context.input_tokens == 100
        assert context.output_tokens == 50

    def test_notify_token_update_callback_error_ignored(self, tmp_path):
        """Test that callback errors don't break the pipeline."""
        def bad_callback(input_tokens, output_tokens):
            raise ValueError("Callback error")

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            on_token_update=bad_callback,
        )

        # Should not raise despite callback error
        context.notify_token_update(100, 50)

        assert context.input_tokens == 100

    def test_notify_stage_update(self, tmp_path):
        """Test that stage update callback is invoked."""
        callback_called = []

        def stage_callback(stage_name, status):
            callback_called.append((stage_name, status))

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            on_stage_update=stage_callback,
        )

        context.notify_stage_update("reconciliation", "running")

        assert len(callback_called) == 1
        assert callback_called[0] == ("reconciliation", "running")
        assert context.current_stage == "reconciliation"

    def test_notify_stage_update_no_callback(self, tmp_path):
        """Test that notify_stage_update works without callback."""
        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
        )

        # Should not raise
        context.notify_stage_update("reconciliation", "complete")

        assert context.current_stage == "reconciliation"

    def test_default_stage_config(self, tmp_path):
        """Test that default stage config is created."""
        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
        )

        assert context.stage_config.run_reconciliation is True
        assert context.stage_config.run_processing is True


class TestClaimProcessingResult:
    """Tests for ClaimProcessingResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = ClaimProcessingResult(
            claim_id="CLM-001",
            run_id="run_001",
            status="success",
            processing_type="assessment",
            result={"decision": "APPROVE"},
        )

        assert result.claim_id == "CLM-001"
        assert result.status == "success"
        assert result.result["decision"] == "APPROVE"
        assert result.error is None

    def test_error_result(self):
        """Test creating an error result."""
        result = ClaimProcessingResult(
            claim_id="CLM-001",
            run_id="run_001",
            status="error",
            processing_type="assessment",
            error="Processing failed",
        )

        assert result.status == "error"
        assert result.error == "Processing failed"
        assert result.result is None


class TestReconciliationStage:
    """Tests for ReconciliationStage."""

    @pytest.fixture
    def stage(self):
        """Create a ReconciliationStage instance."""
        return ReconciliationStage()

    def test_stage_name(self, stage):
        """Test that stage name is set correctly."""
        assert stage.name == "reconciliation"

    def test_skips_when_disabled(self, stage, tmp_path):
        """Test that stage is skipped when disabled in config."""
        callback_called = []

        def stage_callback(stage_name, status):
            callback_called.append((stage_name, status))

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            stage_config=ClaimStageConfig(run_reconciliation=False),
            on_stage_update=stage_callback,
        )

        result = stage.run(context)

        assert result.timings.reconciliation_ms == 0
        # Should have notified skipped status
        assert ("reconciliation", "skipped") in callback_called

    @patch("context_builder.pipeline.claim_stages.reconciliation.FileStorage")
    @patch("context_builder.pipeline.claim_stages.reconciliation.AggregationService")
    @patch("context_builder.pipeline.claim_stages.reconciliation.ReconciliationService")
    def test_runs_reconciliation_when_enabled(
        self,
        mock_reconciliation_service,
        mock_aggregation_service,
        mock_file_storage,
        stage,
        tmp_path,
    ):
        """Test that reconciliation runs when enabled."""
        # Setup mocks
        mock_storage_instance = MagicMock()
        mock_file_storage.return_value = mock_storage_instance

        mock_aggregation_instance = MagicMock()
        mock_aggregation_service.return_value = mock_aggregation_instance

        mock_reconciliation_instance = MagicMock()
        mock_reconciliation_service.return_value = mock_reconciliation_instance

        # Mock successful reconciliation result
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.report = MagicMock()
        mock_result.report.run_id = "run_001"
        mock_result.report.gate.status.value = "pass"
        mock_result.report.gate.conflict_count = 0
        mock_result.report.gate.missing_critical_facts = []
        mock_reconciliation_instance.reconcile.return_value = mock_result

        # Mock claim facts
        mock_claim_facts = MagicMock()
        mock_claim_facts.claim_run_id = "run_001"
        mock_claim_facts.facts = []
        mock_claim_facts.model_dump.return_value = {"facts": []}
        mock_aggregation_instance.aggregate_claim_facts.return_value = mock_claim_facts

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            stage_config=ClaimStageConfig(run_reconciliation=True),
        )

        result = stage.run(context)

        # Verify reconciliation was called
        mock_reconciliation_instance.reconcile.assert_called_once()
        assert result.aggregated_facts is not None

    @patch("context_builder.pipeline.claim_stages.reconciliation.FileStorage")
    @patch("context_builder.pipeline.claim_stages.reconciliation.AggregationService")
    @patch("context_builder.pipeline.claim_stages.reconciliation.ReconciliationService")
    def test_handles_reconciliation_failure(
        self,
        mock_reconciliation_service,
        mock_aggregation_service,
        mock_file_storage,
        stage,
        tmp_path,
    ):
        """Test that reconciliation failure is handled correctly."""
        # Setup mocks
        mock_storage_instance = MagicMock()
        mock_file_storage.return_value = mock_storage_instance

        mock_aggregation_instance = MagicMock()
        mock_aggregation_service.return_value = mock_aggregation_instance

        mock_reconciliation_instance = MagicMock()
        mock_reconciliation_service.return_value = mock_reconciliation_instance

        # Mock failed reconciliation result
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Aggregation failed: no extractions"
        mock_reconciliation_instance.reconcile.return_value = mock_result

        callback_called = []

        def stage_callback(stage_name, status):
            callback_called.append((stage_name, status))

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            stage_config=ClaimStageConfig(run_reconciliation=True),
            on_stage_update=stage_callback,
        )

        result = stage.run(context)

        assert result.status == "error"
        assert result.error is not None
        assert ("reconciliation", "error") in callback_called

    @patch("context_builder.pipeline.claim_stages.reconciliation.FileStorage")
    @patch("context_builder.pipeline.claim_stages.reconciliation.AggregationService")
    @patch("context_builder.pipeline.claim_stages.reconciliation.ReconciliationService")
    def test_handles_exception(
        self,
        mock_reconciliation_service,
        mock_aggregation_service,
        mock_file_storage,
        stage,
        tmp_path,
    ):
        """Test that exceptions during reconciliation are handled."""
        # Setup mocks
        mock_storage_instance = MagicMock()
        mock_file_storage.return_value = mock_storage_instance

        mock_aggregation_instance = MagicMock()
        mock_aggregation_service.return_value = mock_aggregation_instance

        mock_reconciliation_instance = MagicMock()
        mock_reconciliation_service.return_value = mock_reconciliation_instance

        # Mock exception during reconciliation
        mock_reconciliation_instance.reconcile.side_effect = Exception("Unexpected error")

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="run_001",
            stage_config=ClaimStageConfig(run_reconciliation=True),
        )

        result = stage.run(context)

        assert result.status == "error"
        assert "Unexpected error" in result.error

    @patch("context_builder.pipeline.claim_stages.reconciliation.FileStorage")
    @patch("context_builder.pipeline.claim_stages.reconciliation.AggregationService")
    @patch("context_builder.pipeline.claim_stages.reconciliation.ReconciliationService")
    def test_uses_real_claim_facts_attributes(
        self,
        mock_reconciliation_service,
        mock_aggregation_service,
        mock_file_storage,
        stage,
        tmp_path,
    ):
        """Regression: use a real ClaimFacts object to catch attribute mismatches.

        Previously claim_facts.run_id was accessed but ClaimFacts v3 uses
        claim_run_id. MagicMock hid the bug by accepting any attribute.
        """
        from context_builder.schemas.claim_facts import ClaimFacts, AggregatedFact, FactProvenance

        mock_file_storage.return_value = MagicMock()
        mock_aggregation_instance = MagicMock()
        mock_aggregation_service.return_value = mock_aggregation_instance

        mock_reconciliation_instance = MagicMock()
        mock_reconciliation_service.return_value = mock_reconciliation_instance

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.report = MagicMock()
        mock_result.report.run_id = "ext_run_001"
        mock_result.report.gate.status.value = "pass"
        mock_result.report.gate.conflict_count = 0
        mock_result.report.gate.missing_critical_facts = []
        mock_reconciliation_instance.reconcile.return_value = mock_result

        # Use a REAL ClaimFacts object (not a mock) to catch attribute errors
        real_claim_facts = ClaimFacts(
            claim_id="CLM-001",
            claim_run_id="ASM-BATCH-001-CLM-001",
            extraction_runs_used=["ext_run_001"],
            facts=[],
            sources=[],
        )
        mock_aggregation_instance.aggregate_claim_facts.return_value = real_claim_facts

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=tmp_path,
            run_id="ASM-BATCH-001-CLM-001",
            stage_config=ClaimStageConfig(run_reconciliation=True),
        )

        result = stage.run(context)

        # Should succeed without AttributeError
        assert result.aggregated_facts is not None
        assert result.facts_run_id == "ASM-BATCH-001-CLM-001"

        # Verify aggregate_claim_facts was called with context.run_id (not report.run_id)
        mock_aggregation_instance.aggregate_claim_facts.assert_called_once_with(
            "CLM-001", "ASM-BATCH-001-CLM-001"
        )
