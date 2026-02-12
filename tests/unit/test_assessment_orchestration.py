"""Unit tests for assessment orchestration paths.

Tests that ScreeningStage is correctly wired into both:
1. Web API pipeline (_run_assessment_pipeline in claims.py)
2. CLI/Service path (ClaimAssessmentService.assess in claim_assessment.py)

Note: EnrichmentStage was deprecated in Phase 6 cleanup. The pipeline now runs:
  Reconciliation -> Screening -> Assessment
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.pipeline.claim_stages.screening import ScreeningStage
from context_builder.schemas.assessment_response import (
    AssessmentResponse,
    PayoutCalculation,
)
from context_builder.schemas.reconciliation import (
    GateStatus,
    ReconciliationGate,
    ReconciliationReport,
)


# ── Web API Pipeline Tests ───────────────────────────────────────────


class TestWebAPIPipelineStages:
    """Tests for pipeline stage composition (post-Phase 6 cleanup)."""

    def test_pipeline_includes_screening_stage(self):
        """Verify ScreeningStage is available for the pipeline."""
        from context_builder.pipeline.claim_stages import (
            ReconciliationStage,
            ScreeningStage,
            ProcessingStage,
        )

        stages = [ReconciliationStage(), ScreeningStage(), ProcessingStage()]

        stage_types = [type(s) for s in stages]
        assert ScreeningStage in stage_types

    def test_pipeline_stage_order(self):
        """Verify stage order: Reconciliation -> Screening -> Processing."""
        from context_builder.pipeline.claim_stages import (
            ReconciliationStage,
            ScreeningStage,
            ProcessingStage,
        )

        stages = [ReconciliationStage(), ScreeningStage(), ProcessingStage()]

        stage_names = [s.name for s in stages]
        assert stage_names == ["reconciliation", "screening", "processing"]

    def test_pipeline_has_three_stages(self):
        """Verify pipeline has 3 stages (enrichment removed in Phase 6)."""
        from context_builder.pipeline.claim_stages import (
            ReconciliationStage,
            ScreeningStage,
            ProcessingStage,
        )

        stages = [ReconciliationStage(), ScreeningStage(), ProcessingStage()]
        assert len(stages) == 3


# ── CLI/Service Path Tests ───────────────────────────────────────────


def _make_reconciliation_report(claim_run_id: str = "test-run-001") -> ReconciliationReport:
    """Create a minimal ReconciliationReport for test mocks."""
    return ReconciliationReport(
        claim_id="CLM-001",
        claim_run_id=claim_run_id,
        gate=ReconciliationGate(status=GateStatus.PASS),
        fact_count=2,
    )


def _make_assessment_response() -> AssessmentResponse:
    """Create a real AssessmentResponse for test mocks."""
    return AssessmentResponse(
        claim_id="CLM-001",
        assessment_timestamp="2026-01-28T10:00:00Z",
        recommendation="APPROVE",
        recommendation_rationale="All checks passed",
        confidence_score=0.9,
        checks=[],
        payout=PayoutCalculation(
            total_claimed=1000.0,
            non_covered_deductions=0.0,
            covered_subtotal=1000.0,
            coverage_percent=80,
            after_coverage=800.0,
            max_coverage_applied=False,
            deductible=100.0,
            after_deductible=700.0,
            company_vat_deducted=False,
            policyholder_type="individual",
            final_payout=700.0,
            currency="CHF",
        ),
    )


class TestServicePathScreening:
    """Tests for ClaimAssessmentService.assess() screening integration."""

    @pytest.fixture
    def mock_storage(self, tmp_path):
        """Create a mock FileStorage with a workspace path."""
        storage = MagicMock()
        storage.output_root = tmp_path
        return storage

    @pytest.fixture
    def reconciliation_report(self):
        """Create a real ReconciliationReport."""
        return _make_reconciliation_report()

    @pytest.fixture
    def mock_reconciliation(self, reconciliation_report):
        """Create a mock ReconciliationService with a real report."""
        service = MagicMock()
        result = MagicMock()
        result.success = True
        result.report = reconciliation_report
        service.reconcile.return_value = result
        return service

    @pytest.fixture
    def sample_facts(self):
        """Return sample aggregated facts."""
        return {
            "claim_id": "CLM-001",
            "facts": [
                {"name": "policy_start_date", "value": "2025-01-01"},
                {"name": "damage_date", "value": "2025-06-15"},
            ],
        }

    @pytest.fixture
    def mock_claim_run_storage(self, sample_facts):
        """Create a mock ClaimRunStorage."""
        storage = MagicMock()
        storage.read_claim_facts.return_value = sample_facts
        manifest = MagicMock()
        manifest.stages_completed = ["reconciliation"]
        storage.read_manifest.return_value = manifest
        return storage

    def _build_service(self, mock_storage, mock_reconciliation):
        """Build a ClaimAssessmentService instance."""
        from context_builder.api.services.claim_assessment import ClaimAssessmentService

        return ClaimAssessmentService(
            storage=mock_storage,
            reconciliation_service=mock_reconciliation,
        )

    def _run_assess_with_screening(
        self,
        mock_storage,
        mock_reconciliation,
        mock_claim_run_storage,
        sample_facts,
        screening_result_dict=None,
        screening_raises=False,
    ):
        """Helper: run assess() with mocked stages and return (result, mock_processor).

        Note: EnrichmentStage was removed in Phase 6 cleanup. This helper now only
        mocks ScreeningStage, not EnrichmentStage.

        Args:
            screening_result_dict: Dict to set as screening_result on context.
                If None, screening returns context with screening_result=None.
            screening_raises: If True, screening stage raises RuntimeError.
        """
        service = self._build_service(mock_storage, mock_reconciliation)
        mock_storage._find_claim_folder.return_value = Path("/tmp/claims/CLM-001")

        with (
            patch(
                "context_builder.api.services.claim_assessment.ClaimRunStorage",
                return_value=mock_claim_run_storage,
            ),
            patch(
                "context_builder.api.services.claim_assessment.ScreeningStage"
            ) as MockScreeningStage,
            patch(
                "context_builder.api.services.claim_assessment.DecisionStage"
            ) as MockDecisionStage,
            patch(
                "context_builder.api.services.claim_assessment.ConfidenceStage"
            ) as MockConfidenceStage,
            patch(
                "context_builder.api.services.claim_assessment.get_processor"
            ) as mock_get_processor,
            patch(
                "context_builder.api.services.claim_assessment.AssessmentResponse"
            ) as MockAssessmentResponse,
            patch.object(service, "_load_assessment_config") as mock_config,
        ):
            # Mock decision stage (returns context with decision_result)
            mock_decision = MagicMock()
            mock_decision_ctx = ClaimContext(
                claim_id="CLM-001",
                workspace_path=mock_storage.output_root,
                run_id="test-run-001",
                aggregated_facts=sample_facts,
                decision_result={"claim_verdict": "APPROVE"},
            )
            mock_decision.run.return_value = mock_decision_ctx
            MockDecisionStage.return_value = mock_decision

            # Mock confidence stage (returns context unchanged)
            mock_confidence = MagicMock()
            mock_confidence.run.return_value = mock_decision_ctx
            MockConfidenceStage.return_value = mock_confidence

            # Ensure read_from_claim_run returns None for confidence_summary.json
            orig_read = mock_claim_run_storage.read_from_claim_run
            def _read_side_effect(run_id, filename):
                if filename == "confidence_summary.json":
                    return None
                return orig_read(run_id, filename)
            mock_claim_run_storage.read_from_claim_run.side_effect = _read_side_effect
            # Mock screening
            mock_screening = MagicMock()
            if screening_raises:
                mock_screening.run.side_effect = RuntimeError("Screener crashed")
            else:
                screening_ctx = ClaimContext(
                    claim_id="CLM-001",
                    workspace_path=mock_storage.output_root,
                    run_id="test-run-001",
                    aggregated_facts=sample_facts,
                    screening_result=screening_result_dict,
                )
                mock_screening.run.return_value = screening_ctx
            MockScreeningStage.return_value = mock_screening

            # Mock processor
            mock_processor = MagicMock()
            mock_processor.process.return_value = {"recommendation": "APPROVE"}
            mock_get_processor.return_value = mock_processor

            # Mock AssessmentResponse.model_validate to return a real instance
            MockAssessmentResponse.model_validate.return_value = _make_assessment_response()

            # Mock config
            mock_config.return_value = MagicMock()

            result = service.assess("CLM-001")

        return result, mock_processor, MockScreeningStage, mock_screening

    def test_assess_runs_screening(
        self,
        mock_storage,
        mock_reconciliation,
        mock_claim_run_storage,
        sample_facts,
    ):
        """Verify ScreeningStage.run() is called during assess()."""
        result, _, MockScreeningStage, mock_screening = self._run_assess_with_screening(
            mock_storage,
            mock_reconciliation,
            mock_claim_run_storage,
            sample_facts,
            screening_result_dict={"claim_id": "CLM-001", "auto_reject": False},
        )

        MockScreeningStage.assert_called_once()
        mock_screening.run.assert_called_once()

    def test_assess_passes_screening_result_to_context(
        self,
        mock_storage,
        mock_reconciliation,
        mock_claim_run_storage,
        sample_facts,
    ):
        """Verify context.screening_result is set when calling processor."""
        screening_dict = {
            "claim_id": "CLM-001",
            "auto_reject": True,
            "checks": [{"check_name": "policy_expired", "verdict": "FAIL"}],
        }

        result, mock_processor, _, _ = self._run_assess_with_screening(
            mock_storage,
            mock_reconciliation,
            mock_claim_run_storage,
            sample_facts,
            screening_result_dict=screening_dict,
        )

        # Verify processor was called with context that has screening_result
        call_args = mock_processor.process.call_args
        context_arg = call_args.kwargs.get("context") or call_args[1].get("context")
        assert context_arg.screening_result == screening_dict

    def test_assess_screening_failure_non_fatal(
        self,
        mock_storage,
        mock_reconciliation,
        mock_claim_run_storage,
        sample_facts,
    ):
        """Verify assessment continues if screening raises an exception."""
        result, mock_processor, _, _ = self._run_assess_with_screening(
            mock_storage,
            mock_reconciliation,
            mock_claim_run_storage,
            sample_facts,
            screening_raises=True,
        )

        # Assessment should still succeed despite screening failure
        assert result.success is True

        # Processor should have been called with screening_result=None
        call_args = mock_processor.process.call_args
        context_arg = call_args.kwargs.get("context") or call_args[1].get("context")
        assert context_arg.screening_result is None

    def test_assess_no_screener_still_works(
        self,
        mock_storage,
        mock_reconciliation,
        mock_claim_run_storage,
        sample_facts,
    ):
        """Verify backward compat: assessment works with no workspace screener."""
        result, _, _, _ = self._run_assess_with_screening(
            mock_storage,
            mock_reconciliation,
            mock_claim_run_storage,
            sample_facts,
            screening_result_dict=None,  # DefaultScreener behavior
        )

        assert result.success is True

    def test_assess_manifest_includes_screening(
        self,
        mock_storage,
        mock_reconciliation,
        mock_claim_run_storage,
        sample_facts,
    ):
        """Verify 'screening' appears in manifest stages_completed."""
        result, _, _, _ = self._run_assess_with_screening(
            mock_storage,
            mock_reconciliation,
            mock_claim_run_storage,
            sample_facts,
            screening_result_dict={"claim_id": "CLM-001", "auto_reject": False},
        )

        manifest = mock_claim_run_storage.read_manifest.return_value
        assert "screening" in manifest.stages_completed

    def test_assess_manifest_screening_order(
        self,
        mock_storage,
        mock_reconciliation,
        sample_facts,
    ):
        """Verify 'screening' appears between 'reconciliation' and 'assessment' in manifest.

        Note: enrichment was removed in Phase 6 cleanup.
        """
        # Use a real list for stages_completed to track actual append order
        manifest = MagicMock()
        manifest.stages_completed = []

        mock_claim_run_storage = MagicMock()
        mock_claim_run_storage.read_claim_facts.return_value = sample_facts
        mock_claim_run_storage.read_manifest.return_value = manifest

        result, _, _, _ = self._run_assess_with_screening(
            mock_storage,
            mock_reconciliation,
            mock_claim_run_storage,
            sample_facts,
            screening_result_dict={"claim_id": "CLM-001", "auto_reject": False},
        )

        assert manifest.stages_completed == [
            "reconciliation",
            "screening",
            "assessment",
            "decision",
            "confidence",
        ]
