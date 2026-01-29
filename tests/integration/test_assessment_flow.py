"""Integration tests for the two-phase assessment flow.

Tests the full flow: screening → assessment, covering:
- 5.3: Auto-reject flow (screening hard-fail → auto-reject → no LLM call)
- 5.4: LLM assessment flow (screening passes → LLM called with screening context)

These tests verify that ScreeningStage and AssessmentProcessor work together
correctly, without requiring a real workspace or LLM API.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from context_builder.coverage.schemas import CoverageAnalysisResult
from context_builder.pipeline.claim_stages.assessment_processor import (
    AssessmentProcessor,
)
from context_builder.pipeline.claim_stages.context import ClaimContext, ClaimStageConfig
from context_builder.pipeline.claim_stages.processing import ProcessorConfig
from context_builder.pipeline.claim_stages.screening import ScreeningStage
from context_builder.schemas.assessment_response import (
    AssessmentResponse,
    validate_assessment_completeness,
)
from context_builder.schemas.screening import (
    CheckVerdict,
    ScreeningCheck,
    ScreeningPayoutCalculation,
    ScreeningResult,
)


# ── Test screener implementations ────────────────────────────────────


class AutoRejectScreener:
    """Screener that always triggers auto-reject (mileage exceeded)."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def screen(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        reconciliation_report=None,
        claim_run_id=None,
    ) -> Tuple[ScreeningResult, Optional[CoverageAnalysisResult]]:
        checks = [
            ScreeningCheck(
                check_id="1",
                check_name="policy_validity",
                verdict=CheckVerdict.PASS,
                reason="Policy is valid",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="1b",
                check_name="damage_date",
                verdict=CheckVerdict.PASS,
                reason="Damage date within policy",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="2",
                check_name="vin_consistency",
                verdict=CheckVerdict.PASS,
                reason="VINs consistent",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="2b",
                check_name="owner_match",
                verdict=CheckVerdict.PASS,
                reason="Names match",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="3",
                check_name="mileage",
                verdict=CheckVerdict.FAIL,
                reason="Odometer 180,000 km exceeds limit of 150,000 km",
                evidence={"km_limited_to": 150000, "current_odometer": 180000},
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="4a",
                check_name="shop_authorization",
                verdict=CheckVerdict.PASS,
                reason="Shop authorized",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.PASS,
                reason="Service within 12 months",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.PASS,
                reason="Primary component covered",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="5b",
                check_name="assistance_items",
                verdict=CheckVerdict.PASS,
                reason="No assistance items",
                is_hard_fail=False,
            ),
        ]
        result = ScreeningResult(
            claim_id=claim_id,
            screening_timestamp=datetime.utcnow().isoformat(),
            checks=checks,
            payout=ScreeningPayoutCalculation(
                covered_total=4500.0,
                not_covered_total=500.0,
                coverage_percent=80.0,
                max_coverage=10000.0,
                max_coverage_applied=False,
                capped_amount=4500.0,
                deductible_percent=10.0,
                deductible_minimum=200.0,
                deductible_amount=450.0,
                after_deductible=4050.0,
                policyholder_type="individual",
                vat_adjusted=False,
                vat_deduction=0.0,
                final_payout=4050.0,
            ),
        )
        result.recompute_counts()
        return result, None


class AllPassScreener:
    """Screener where all checks pass (claim goes to LLM)."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def screen(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        reconciliation_report=None,
        claim_run_id=None,
    ) -> Tuple[ScreeningResult, Optional[CoverageAnalysisResult]]:
        checks = [
            ScreeningCheck(
                check_id="1",
                check_name="policy_validity",
                verdict=CheckVerdict.PASS,
                reason="Policy valid",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="1b",
                check_name="damage_date",
                verdict=CheckVerdict.PASS,
                reason="Damage date OK",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="2",
                check_name="vin_consistency",
                verdict=CheckVerdict.PASS,
                reason="VINs match",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="2b",
                check_name="owner_match",
                verdict=CheckVerdict.INCONCLUSIVE,
                reason="Owner name needs review",
                is_hard_fail=False,
                requires_llm=True,
            ),
            ScreeningCheck(
                check_id="3",
                check_name="mileage",
                verdict=CheckVerdict.PASS,
                reason="Within limit",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="4a",
                check_name="shop_authorization",
                verdict=CheckVerdict.PASS,
                reason="Authorized",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="4b",
                check_name="service_compliance",
                verdict=CheckVerdict.SKIPPED,
                reason="No service data",
                is_hard_fail=False,
            ),
            ScreeningCheck(
                check_id="5",
                check_name="component_coverage",
                verdict=CheckVerdict.PASS,
                reason="Primary component covered",
                is_hard_fail=True,
            ),
            ScreeningCheck(
                check_id="5b",
                check_name="assistance_items",
                verdict=CheckVerdict.PASS,
                reason="No assistance items",
                is_hard_fail=False,
            ),
        ]
        result = ScreeningResult(
            claim_id=claim_id,
            screening_timestamp=datetime.utcnow().isoformat(),
            checks=checks,
            payout=ScreeningPayoutCalculation(
                covered_total=4500.0,
                not_covered_total=500.0,
                coverage_percent=80.0,
                max_coverage=10000.0,
                max_coverage_applied=False,
                capped_amount=4500.0,
                deductible_percent=10.0,
                deductible_minimum=200.0,
                deductible_amount=450.0,
                after_deductible=4050.0,
                policyholder_type="individual",
                vat_adjusted=False,
                vat_deduction=0.0,
                final_payout=4050.0,
            ),
        )
        result.recompute_counts()
        return result, None


# ── Helpers ──────────────────────────────────────────────────────────


def _make_context(
    tmp_path: Path,
    claim_id: str = "CLM-INTEG-001",
    run_id: str = "clm_20260128_100000_integ",
    facts: Optional[Dict[str, Any]] = None,
    screening_result: Optional[Dict[str, Any]] = None,
):
    """Create a ClaimContext with proper directory structure."""
    claim_folder = tmp_path / "claims" / claim_id
    claim_folder.mkdir(parents=True, exist_ok=True)
    run_dir = claim_folder / "claim_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    return ClaimContext(
        claim_id=claim_id,
        workspace_path=tmp_path,
        run_id=run_id,
        aggregated_facts=facts or {"facts": [], "structured_data": {}},
        screening_result=screening_result,
    )


def _make_processor_config():
    """Create a minimal ProcessorConfig for assessment."""
    return ProcessorConfig(
        type="assessment",
        version="v1",
        prompt_content="System prompt ---USER--- User prompt: evaluate claim",
        prompt_version="test_v1",
        model="gpt-4o",
        temperature=0.0,
        max_tokens=4000,
    )


# ═══════════════════════════════════════════════════════════════════════
# 5.3: AUTO-REJECT FLOW
# ═══════════════════════════════════════════════════════════════════════


class TestAutoRejectFlow:
    """Integration test: screening auto-reject → no LLM call → REJECT decision."""

    @pytest.fixture
    def tmp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_screening_produces_auto_reject_result(self, tmp_workspace):
        """ScreeningStage with AutoRejectScreener produces auto_reject screening."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace

        result_context = stage.run(context)

        assert result_context.screening_result is not None
        assert result_context.screening_result["auto_reject"] is True
        assert "3" in result_context.screening_result["hard_fails"]

    def test_screening_writes_json_file(self, tmp_workspace):
        """Screening stage writes screening.json to claim_run directory."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace

        stage.run(context)

        screening_path = (
            tmp_workspace
            / "claims"
            / "CLM-INTEG-001"
            / "claim_runs"
            / "clm_20260128_100000_integ"
            / "screening.json"
        )
        assert screening_path.exists()

        data = json.loads(screening_path.read_text(encoding="utf-8"))
        assert data["auto_reject"] is True
        assert data["claim_id"] == "CLM-INTEG-001"

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    def test_auto_reject_skips_llm_call(self, mock_get_client, tmp_workspace):
        """Full flow: screening auto-reject → assessment processor skips LLM."""
        # Step 1: Run screening
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        # Step 2: Build context for assessment with screening result
        assess_context = _make_context(
            tmp_workspace,
            screening_result=screened_context.screening_result,
        )

        # Step 3: Run assessment processor
        processor = AssessmentProcessor()
        config = _make_processor_config()
        token_cb = MagicMock()

        result = processor.process(assess_context, config, on_token_update=token_cb)

        # Verify: no LLM call was made
        mock_get_client.assert_not_called()

        # Verify: result is REJECT with auto_reject method
        assert result["decision"] == "REJECT"
        assert result["assessment_method"] == "auto_reject"
        assert result["confidence_score"] == 1.0

        # Verify: token callback reports zero usage
        token_cb.assert_called_once_with(0, 0)

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    def test_auto_reject_produces_valid_assessment(self, mock_get_client, tmp_workspace):
        """Auto-reject assessment validates against AssessmentResponse schema."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        assess_context = _make_context(
            tmp_workspace,
            screening_result=screened_context.screening_result,
        )
        processor = AssessmentProcessor()
        config = _make_processor_config()
        result = processor.process(assess_context, config)

        # Validate with Pydantic
        validated = AssessmentResponse.model_validate(result)
        assert validated.decision == "REJECT"
        assert validated.assessment_method == "auto_reject"

        # Validate completeness
        warnings = validate_assessment_completeness(validated)
        check_count_warnings = [w for w in warnings if "checks present" in w]
        assert check_count_warnings == []

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    def test_auto_reject_includes_payout(self, mock_get_client, tmp_workspace):
        """Auto-reject assessment preserves payout from screening."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        assess_context = _make_context(
            tmp_workspace,
            screening_result=screened_context.screening_result,
        )
        processor = AssessmentProcessor()
        config = _make_processor_config()
        result = processor.process(assess_context, config)

        assert result["payout"]["covered_subtotal"] == 4500.0
        assert result["payout"]["non_covered_deductions"] == 500.0
        assert result["payout"]["total_claimed"] == 5000.0
        assert result["payout"]["final_payout"] == 4050.0

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    def test_auto_reject_has_all_11_checks(self, mock_get_client, tmp_workspace):
        """Auto-reject should have 9 screening checks + 2 synthesized (6, 7)."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        assess_context = _make_context(
            tmp_workspace,
            screening_result=screened_context.screening_result,
        )
        processor = AssessmentProcessor()
        config = _make_processor_config()
        result = processor.process(assess_context, config)

        assert len(result["checks"]) == 11
        check_numbers = {c["check_number"] for c in result["checks"]}
        assert "6" in check_numbers
        assert "7" in check_numbers

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    def test_auto_reject_fraud_indicators(self, mock_get_client, tmp_workspace):
        """Auto-reject produces fraud indicators from hard-fail checks."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AutoRejectScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        assess_context = _make_context(
            tmp_workspace,
            screening_result=screened_context.screening_result,
        )
        processor = AssessmentProcessor()
        config = _make_processor_config()
        result = processor.process(assess_context, config)

        assert len(result["fraud_indicators"]) >= 1
        assert result["fraud_indicators"][0]["severity"] == "high"


# ═══════════════════════════════════════════════════════════════════════
# 5.4: LLM ASSESSMENT FLOW
# ═══════════════════════════════════════════════════════════════════════


class TestLLMAssessmentFlow:
    """Integration test: screening passes → LLM called with screening context."""

    @pytest.fixture
    def tmp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_screening_no_auto_reject(self, tmp_workspace):
        """AllPassScreener should not trigger auto-reject."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AllPassScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace

        result_context = stage.run(context)

        assert result_context.screening_result is not None
        assert result_context.screening_result["auto_reject"] is False
        assert result_context.screening_result["hard_fails"] == []

    def test_screening_has_inconclusive_for_llm(self, tmp_workspace):
        """AllPassScreener flags check 2b as INCONCLUSIVE requiring LLM."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AllPassScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace

        result_context = stage.run(context)

        assert "2b" in result_context.screening_result["checks_for_llm"]

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_llm_audit_service")
    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_workspace_logs_dir")
    def test_llm_called_with_screening_context(
        self, mock_logs_dir, mock_audit_service, mock_get_client, tmp_workspace
    ):
        """Non-auto-reject screening → LLM called with screening context in prompt."""
        # Set up mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_audit_service.return_value = MagicMock()
        mock_logs_dir.return_value = tmp_workspace / "logs"

        # Step 1: Run screening
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AllPassScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        # Step 2: Run assessment with screening result
        assess_context = _make_context(
            tmp_workspace,
            screening_result=screened_context.screening_result,
        )

        mock_llm_response = {
            "schema_version": "claims_assessment_v2",
            "assessment_method": "llm",
            "claim_id": "CLM-INTEG-001",
            "assessment_timestamp": datetime.utcnow().isoformat(),
            "decision": "APPROVE",
            "decision_rationale": "All checks passed, payout calculated",
            "confidence_score": 0.92,
            "checks": [
                {
                    "check_number": "1",
                    "check_name": "policy_validity",
                    "result": "PASS",
                    "details": "Confirmed by screening",
                },
                {
                    "check_number": "2b",
                    "check_name": "owner_match",
                    "result": "PASS",
                    "details": "Names match after LLM review",
                },
            ],
            "payout": AssessmentProcessor._zero_payout(),
            "data_gaps": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        processor = AssessmentProcessor()
        config = _make_processor_config()

        with patch.object(processor, "_call_with_retry", return_value=mock_llm_response):
            result = processor.process(assess_context, config)

        # Verify: LLM was initialized
        mock_get_client.assert_called_once()

        # Verify: result is from LLM
        assert result["decision"] == "APPROVE"
        assert result["assessment_method"] == "llm"

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_llm_audit_service")
    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_workspace_logs_dir")
    def test_screening_context_injected_into_prompt(
        self, mock_logs_dir, mock_audit_service, mock_get_client, tmp_workspace
    ):
        """Screening results should be injected into the LLM user prompt."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_audit_service.return_value = MagicMock()
        mock_logs_dir.return_value = tmp_workspace / "logs"

        # Run screening
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AllPassScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace
        screened_context = stage.run(context)

        # Build prompts with screening context
        processor = AssessmentProcessor()
        screening = screened_context.screening_result

        system, user = processor._build_prompts(
            "System prompt",
            {"facts": [], "structured_data": {}},
            "CLM-INTEG-001",
            screening=screening,
        )

        # Verify screening context is in user prompt
        assert "Pre-computed Screening Results" in user
        assert "requires_llm" in user
        assert '"auto_reject": false' in user

        # Verify screening block appears before facts
        screening_pos = user.index("Pre-computed Screening Results")
        facts_pos = user.index("Aggregated Facts")
        assert screening_pos < facts_pos

    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_openai_client")
    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_llm_audit_service")
    @patch("context_builder.pipeline.claim_stages.assessment_processor.get_workspace_logs_dir")
    def test_no_screening_backward_compatible(
        self, mock_logs_dir, mock_audit_service, mock_get_client, tmp_workspace
    ):
        """Without screening, assessment should work the old way (no screening context)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_audit_service.return_value = MagicMock()
        mock_logs_dir.return_value = tmp_workspace / "logs"

        # No screening result
        assess_context = _make_context(tmp_workspace, screening_result=None)

        mock_response = {
            "schema_version": "claims_assessment_v2",
            "assessment_method": "llm",
            "claim_id": "CLM-INTEG-001",
            "assessment_timestamp": datetime.utcnow().isoformat(),
            "decision": "APPROVE",
            "decision_rationale": "All good",
            "confidence_score": 0.9,
            "checks": [],
            "payout": AssessmentProcessor._zero_payout(),
            "data_gaps": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        processor = AssessmentProcessor()
        config = _make_processor_config()

        with patch.object(processor, "_call_with_retry", return_value=mock_response):
            result = processor.process(assess_context, config)

        # LLM should be called (backward compatible)
        mock_get_client.assert_called_once()
        assert result["decision"] == "APPROVE"


# ═══════════════════════════════════════════════════════════════════════
# COMBINED SCREENING + ASSESSMENT FILE OUTPUT
# ═══════════════════════════════════════════════════════════════════════


class TestScreeningFileOutput:
    """Tests that screening produces expected file artifacts."""

    @pytest.fixture
    def tmp_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_screening_produces_screening_json(self, tmp_workspace):
        """screening.json should be written with correct schema."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AllPassScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace

        stage.run(context)

        screening_path = (
            tmp_workspace
            / "claims"
            / "CLM-INTEG-001"
            / "claim_runs"
            / "clm_20260128_100000_integ"
            / "screening.json"
        )
        assert screening_path.exists()

        data = json.loads(screening_path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "screening_v1"
        assert len(data["checks"]) == 9

    def test_screening_json_parseable_as_pydantic(self, tmp_workspace):
        """screening.json should be valid ScreeningResult."""
        context = _make_context(tmp_workspace, facts={"facts": [], "structured_data": {}})
        stage = ScreeningStage()
        stage._screener = AllPassScreener(tmp_workspace)
        stage._workspace_path = tmp_workspace

        stage.run(context)

        screening_path = (
            tmp_workspace
            / "claims"
            / "CLM-INTEG-001"
            / "claim_runs"
            / "clm_20260128_100000_integ"
            / "screening.json"
        )
        data = json.loads(screening_path.read_text(encoding="utf-8"))
        result = ScreeningResult.model_validate(data)
        assert result.claim_id == "CLM-INTEG-001"
        assert isinstance(result.payout, ScreeningPayoutCalculation)
