"""Unit tests for AssessmentProcessor screening integration.

Tests cover:
- Static mapping methods (pure functions, no mocking)
- Auto-reject response building
- Process branching on screening
- Prompt injection of screening context
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context_builder.pipeline.claim_stages.assessment_processor import (
    AssessmentProcessor,
)
from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.pipeline.claim_stages.processing import ProcessorConfig
from context_builder.schemas.assessment_response import (
    MIN_EXPECTED_CHECKS,
    AssessmentResponse,
    validate_assessment_completeness,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_screening_check(
    check_id="1",
    check_name="policy_validity",
    verdict="PASS",
    reason="OK",
    evidence=None,
    is_hard_fail=False,
    requires_llm=False,
):
    """Build a screening check dict (as from ScreeningResult.model_dump())."""
    return {
        "check_id": check_id,
        "check_name": check_name,
        "verdict": verdict,
        "reason": reason,
        "evidence": evidence or {},
        "is_hard_fail": is_hard_fail,
        "requires_llm": requires_llm,
    }


def _make_screening_payout(**overrides):
    """Build a screening payout dict."""
    defaults = {
        "covered_total": 4500.0,
        "not_covered_total": 500.0,
        "coverage_percent": 80.0,
        "max_coverage": 10000.0,
        "max_coverage_applied": False,
        "capped_amount": 4500.0,
        "deductible_percent": 10.0,
        "deductible_minimum": 200.0,
        "deductible_amount": 450.0,
        "after_deductible": 4050.0,
        "policyholder_type": "individual",
        "vat_adjusted": False,
        "vat_deduction": 0.0,
        "final_payout": 4050.0,
        "currency": "CHF",
    }
    defaults.update(overrides)
    return defaults


def _all_nine_screening_checks():
    """Return all 9 screening checks (1, 1b, 2, 2b, 3, 4a, 4b, 5, 5b)."""
    ids_names = [
        ("1", "policy_validity"),
        ("1b", "damage_date_validity"),
        ("2", "vehicle_id_consistency"),
        ("2b", "owner_policyholder_match"),
        ("3", "mileage_compliance"),
        ("4a", "shop_authorization"),
        ("4b", "service_compliance"),
        ("5", "component_coverage"),
        ("5b", "assistance_package_items"),
    ]
    return [
        _make_screening_check(check_id=cid, check_name=cname)
        for cid, cname in ids_names
    ]


def _make_auto_reject_screening(hard_fail_check_id="3", with_payout=True):
    """Build a complete auto-reject screening result dict."""
    checks = _all_nine_screening_checks()
    # Set the specified check to FAIL + is_hard_fail
    for c in checks:
        if c["check_id"] == hard_fail_check_id:
            c["verdict"] = "FAIL"
            c["is_hard_fail"] = True
            c["reason"] = f"Check {hard_fail_check_id} failed deterministically"
            c["evidence"] = {"key1": "val1", "key2": "val2"}

    screening = {
        "schema_version": "screening_v1",
        "claim_id": "CLM-TEST",
        "screening_timestamp": "2026-01-28T10:00:00Z",
        "checks": checks,
        "checks_passed": 8,
        "checks_failed": 1,
        "checks_inconclusive": 0,
        "checks_for_llm": [],
        "coverage_analysis_ref": None,
        "auto_reject": True,
        "auto_reject_reason": f"Hard fail on check(s): {hard_fail_check_id}",
        "hard_fails": [hard_fail_check_id],
    }

    if with_payout:
        screening["payout"] = _make_screening_payout()
        screening["payout_error"] = None
    else:
        screening["payout"] = None
        screening["payout_error"] = "Missing policy terms"

    return screening


def _make_non_auto_reject_screening():
    """Build a screening result that does NOT auto-reject (for LLM path)."""
    checks = _all_nine_screening_checks()
    # Mark one as INCONCLUSIVE + requires_llm
    for c in checks:
        if c["check_id"] == "2b":
            c["verdict"] = "INCONCLUSIVE"
            c["requires_llm"] = True
            c["reason"] = "Owner name needs LLM review"

    return {
        "schema_version": "screening_v1",
        "claim_id": "CLM-TEST",
        "screening_timestamp": "2026-01-28T10:00:00Z",
        "checks": checks,
        "checks_passed": 8,
        "checks_failed": 0,
        "checks_inconclusive": 1,
        "checks_for_llm": ["2b"],
        "coverage_analysis_ref": None,
        "payout": _make_screening_payout(),
        "payout_error": None,
        "auto_reject": False,
        "auto_reject_reason": None,
        "hard_fails": [],
    }


# ── _map_screening_checks tests ─────────────────────────────────────


class TestMapScreeningChecks:
    """Tests for _map_screening_checks (pure function)."""

    def test_verdict_mapping_pass(self):
        checks = [_make_screening_check(verdict="PASS")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["result"] == "PASS"

    def test_verdict_mapping_fail(self):
        checks = [_make_screening_check(verdict="FAIL")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["result"] == "FAIL"

    def test_verdict_mapping_inconclusive(self):
        checks = [_make_screening_check(verdict="INCONCLUSIVE")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["result"] == "INCONCLUSIVE"

    def test_verdict_mapping_skipped_to_not_checked(self):
        checks = [_make_screening_check(verdict="SKIPPED")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["result"] == "NOT_CHECKED"

    def test_field_mapping_check_id_to_check_number(self):
        checks = [_make_screening_check(check_id="2b")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["check_number"] == "2b"

    def test_field_mapping_reason_to_details(self):
        checks = [_make_screening_check(reason="Policy is valid")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["details"] == "Policy is valid"

    def test_evidence_dict_keys_to_refs_list(self):
        checks = [
            _make_screening_check(
                evidence={"claim_date": "2026-01-10", "policy_start": "2025-01-01"}
            )
        ]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert sorted(result[0]["evidence_refs"]) == ["claim_date", "policy_start"]

    def test_empty_evidence_gives_empty_refs(self):
        checks = [_make_screening_check(evidence={})]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["evidence_refs"] == []

    def test_check_name_preserved(self):
        checks = [_make_screening_check(check_name="mileage_compliance")]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert result[0]["check_name"] == "mileage_compliance"

    def test_multiple_checks_mapped(self):
        checks = [
            _make_screening_check(check_id="1", verdict="PASS"),
            _make_screening_check(check_id="2", verdict="FAIL"),
            _make_screening_check(check_id="3", verdict="SKIPPED"),
        ]
        result = AssessmentProcessor._map_screening_checks(checks)
        assert len(result) == 3
        assert [r["result"] for r in result] == ["PASS", "FAIL", "NOT_CHECKED"]


# ── _map_screening_payout tests ─────────────────────────────────────


class TestMapScreeningPayout:
    """Tests for _map_screening_payout (pure function)."""

    def test_field_renames(self):
        payout = _make_screening_payout()
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["covered_subtotal"] == 4500.0
        assert result["non_covered_deductions"] == 500.0
        assert result["deductible"] == 450.0

    def test_total_claimed_computed(self):
        payout = _make_screening_payout(covered_total=3000.0, not_covered_total=700.0)
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["total_claimed"] == 3700.0

    def test_coverage_percent_float_to_int(self):
        payout = _make_screening_payout(coverage_percent=80.0)
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["coverage_percent"] == 80
        assert isinstance(result["coverage_percent"], int)

    def test_coverage_percent_none_defaults_to_zero(self):
        payout = _make_screening_payout(coverage_percent=None)
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["coverage_percent"] == 0

    def test_after_coverage_equals_capped_amount(self):
        payout = _make_screening_payout(capped_amount=3600.0)
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["after_coverage"] == 3600.0

    def test_capped_amount_set_when_max_coverage_applied(self):
        payout = _make_screening_payout(
            max_coverage_applied=True, capped_amount=8000.0
        )
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["capped_amount"] == 8000.0

    def test_capped_amount_none_when_no_cap(self):
        payout = _make_screening_payout(
            max_coverage_applied=False, capped_amount=4500.0
        )
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["capped_amount"] is None

    def test_passthrough_fields(self):
        payout = _make_screening_payout(
            after_deductible=4050.0,
            policyholder_type="company",
            vat_adjusted=True,
            vat_deduction=350.0,
            final_payout=3700.0,
            currency="EUR",
        )
        result = AssessmentProcessor._map_screening_payout(payout)
        assert result["after_deductible"] == 4050.0
        assert result["policyholder_type"] == "company"
        assert result["vat_adjusted"] is True
        assert result["vat_deduction"] == 350.0
        assert result["final_payout"] == 3700.0
        assert result["currency"] == "EUR"


# ── _zero_payout tests ──────────────────────────────────────────────


class TestZeroPayout:
    """Tests for _zero_payout (pure function)."""

    def test_all_defaults(self):
        result = AssessmentProcessor._zero_payout()
        assert result["total_claimed"] == 0.0
        assert result["non_covered_deductions"] == 0.0
        assert result["covered_subtotal"] == 0.0
        assert result["coverage_percent"] == 0
        assert result["after_coverage"] == 0.0
        assert result["max_coverage_applied"] is False
        assert result["capped_amount"] is None
        assert result["deductible"] == 0.0
        assert result["after_deductible"] == 0.0
        assert result["vat_adjusted"] is False
        assert result["vat_deduction"] == 0.0
        assert result["policyholder_type"] == "individual"
        assert result["final_payout"] == 0.0
        assert result["currency"] == "CHF"

    def test_validates_as_payout_calculation(self):
        """Zero payout should be valid for PayoutCalculation schema."""
        from context_builder.schemas.assessment_response import PayoutCalculation

        PayoutCalculation.model_validate(AssessmentProcessor._zero_payout())


# ── _extract_fraud_indicators tests ─────────────────────────────────


class TestExtractFraudIndicators:
    """Tests for _extract_fraud_indicators (pure function)."""

    def test_from_hard_fails(self):
        checks = [
            _make_screening_check(
                check_id="3",
                check_name="mileage_compliance",
                verdict="FAIL",
                is_hard_fail=True,
                reason="Mileage exceeds limit",
            ),
        ]
        result = AssessmentProcessor._extract_fraud_indicators(checks)
        assert len(result) == 1
        assert result[0]["severity"] == "high"
        assert "mileage_compliance" in result[0]["indicator"]
        assert result[0]["details"] == "Mileage exceeds limit"

    def test_empty_when_no_hard_fails(self):
        checks = [
            _make_screening_check(verdict="PASS"),
            _make_screening_check(verdict="FAIL", is_hard_fail=False),
            _make_screening_check(verdict="INCONCLUSIVE"),
        ]
        result = AssessmentProcessor._extract_fraud_indicators(checks)
        assert result == []

    def test_multiple_hard_fails(self):
        checks = [
            _make_screening_check(
                check_id="1", verdict="FAIL", is_hard_fail=True, reason="Policy expired"
            ),
            _make_screening_check(
                check_id="3", verdict="FAIL", is_hard_fail=True, reason="Mileage issue"
            ),
        ]
        result = AssessmentProcessor._extract_fraud_indicators(checks)
        assert len(result) == 2

    def test_non_fail_hard_fail_flag_ignored(self):
        """A check with is_hard_fail=True but verdict=PASS should not produce an indicator."""
        checks = [
            _make_screening_check(verdict="PASS", is_hard_fail=True),
        ]
        result = AssessmentProcessor._extract_fraud_indicators(checks)
        assert result == []


# ── _build_auto_reject_response tests ───────────────────────────────


class TestBuildAutoRejectResponse:
    """Tests for _build_auto_reject_response."""

    def setup_method(self):
        self.processor = AssessmentProcessor()

    def test_basic_auto_reject(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        assert result["decision"] == "REJECT"
        assert result["confidence_score"] == 1.0
        assert result["assessment_method"] == "auto_reject"

    def test_with_payout(self):
        screening = _make_auto_reject_screening(with_payout=True)
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        # Payout should be mapped from screening
        assert result["payout"]["covered_subtotal"] == 4500.0
        assert result["payout"]["non_covered_deductions"] == 500.0
        assert result["payout"]["total_claimed"] == 5000.0

    def test_without_payout(self):
        screening = _make_auto_reject_screening(with_payout=False)
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        # Payout should be zeroed
        assert result["payout"]["total_claimed"] == 0.0
        assert result["payout"]["final_payout"] == 0.0

    def test_passes_pydantic_validation(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        # Should not raise
        validated = AssessmentResponse.model_validate(result)
        assert validated.decision == "REJECT"

    def test_meets_min_checks(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        assert len(result["checks"]) >= MIN_EXPECTED_CHECKS
        # 9 screening checks + 2 synthesized = 11
        assert len(result["checks"]) == 11

    def test_has_checks_6_and_7(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        check_numbers = {c["check_number"] for c in result["checks"]}
        assert "6" in check_numbers
        assert "7" in check_numbers

    def test_check_6_pass_when_payout_computed(self):
        screening = _make_auto_reject_screening(with_payout=True)
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        check_6 = [c for c in result["checks"] if c["check_number"] == "6"][0]
        assert check_6["result"] == "PASS"

    def test_check_6_not_checked_when_payout_error(self):
        screening = _make_auto_reject_screening(with_payout=False)
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        check_6 = [c for c in result["checks"] if c["check_number"] == "6"][0]
        assert check_6["result"] == "NOT_CHECKED"

    def test_check_7_is_fail(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        check_7 = [c for c in result["checks"] if c["check_number"] == "7"][0]
        assert check_7["result"] == "FAIL"

    def test_method_is_auto_reject(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        assert result["assessment_method"] == "auto_reject"

    def test_decision_rationale_from_screening(self):
        screening = _make_auto_reject_screening(hard_fail_check_id="3")
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        assert "3" in result["decision_rationale"]

    def test_fraud_indicators_from_hard_fails(self):
        screening = _make_auto_reject_screening(hard_fail_check_id="3")
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        assert len(result["fraud_indicators"]) >= 1
        assert result["fraud_indicators"][0]["severity"] == "high"

    def test_passes_completeness_validation(self):
        screening = _make_auto_reject_screening()
        result = self.processor._build_auto_reject_response("CLM-001", screening)

        validated = AssessmentResponse.model_validate(result)
        warnings = validate_assessment_completeness(validated)
        # Should have no "too few checks" warning
        check_count_warnings = [w for w in warnings if "checks present" in w]
        assert check_count_warnings == []


# ── process() branching tests ────────────────────────────────────────


class TestProcessBranching:
    """Tests for process() branching on screening result."""

    def setup_method(self):
        self.processor = AssessmentProcessor()

    def _make_context(self, screening_result=None):
        return ClaimContext(
            claim_id="CLM-001",
            workspace_path=Path("/tmp/test"),
            run_id="run-001",
            aggregated_facts={"some": "facts"},
            screening_result=screening_result,
        )

    def _make_config(self):
        return ProcessorConfig(
            type="assessment",
            version="v1",
            prompt_content="System prompt ---USER--- User prompt",
            prompt_version="v1",
            model="gpt-4o",
            temperature=0.0,
            max_tokens=4000,
        )

    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_openai_client"
    )
    def test_auto_reject_skips_llm(self, mock_get_client):
        """When screening auto-rejects, no OpenAI client should be created."""
        screening = _make_auto_reject_screening()
        context = self._make_context(screening_result=screening)
        config = self._make_config()

        token_cb = MagicMock()
        result = self.processor.process(context, config, on_token_update=token_cb)

        # OpenAI client should NOT be initialized
        mock_get_client.assert_not_called()

        # Result should be auto-reject
        assert result["decision"] == "REJECT"
        assert result["assessment_method"] == "auto_reject"
        assert result["model"] == "none (auto-reject)"
        assert result["prompt_version"] == "v1"

        # Token callback should report zero
        token_cb.assert_called_once_with(0, 0)

    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_openai_client"
    )
    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_llm_audit_service"
    )
    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_workspace_logs_dir"
    )
    def test_no_screening_uses_llm(
        self, mock_logs_dir, mock_audit_service, mock_get_client
    ):
        """When no screening result, backward compatible LLM path is used."""
        # Set up mock client chain
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_audit_service.return_value = MagicMock()
        mock_logs_dir.return_value = Path("/tmp/logs")

        # Mock the _call_with_retry to avoid real API calls
        mock_response = {
            "schema_version": "claims_assessment_v2",
            "assessment_method": "llm",
            "claim_id": "CLM-001",
            "assessment_timestamp": "2026-01-28T10:00:00Z",
            "decision": "APPROVE",
            "decision_rationale": "All good",
            "confidence_score": 0.9,
            "checks": [],
            "payout": AssessmentProcessor._zero_payout(),
            "data_gaps": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        with patch.object(
            self.processor, "_call_with_retry", return_value=mock_response
        ):
            context = self._make_context(screening_result=None)
            config = self._make_config()
            result = self.processor.process(context, config)

        # OpenAI client SHOULD be initialized
        mock_get_client.assert_called_once()
        assert result["decision"] == "APPROVE"

    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_openai_client"
    )
    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_llm_audit_service"
    )
    @patch(
        "context_builder.pipeline.claim_stages.assessment_processor.get_workspace_logs_dir"
    )
    def test_screening_not_auto_reject_calls_llm(
        self, mock_logs_dir, mock_audit_service, mock_get_client
    ):
        """When screening exists but no auto-reject, LLM is still called."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_audit_service.return_value = MagicMock()
        mock_logs_dir.return_value = Path("/tmp/logs")

        mock_response = {
            "schema_version": "claims_assessment_v2",
            "assessment_method": "llm",
            "claim_id": "CLM-001",
            "assessment_timestamp": "2026-01-28T10:00:00Z",
            "decision": "APPROVE",
            "decision_rationale": "All good",
            "confidence_score": 0.9,
            "checks": [],
            "payout": AssessmentProcessor._zero_payout(),
            "data_gaps": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        with patch.object(
            self.processor, "_call_with_retry", return_value=mock_response
        ):
            screening = _make_non_auto_reject_screening()
            context = self._make_context(screening_result=screening)
            config = self._make_config()
            result = self.processor.process(context, config)

        # LLM should be called
        mock_get_client.assert_called_once()
        assert result["decision"] == "APPROVE"


# ── _build_prompts tests ────────────────────────────────────────────


class TestBuildPromptsScreening:
    """Tests for _build_prompts with screening injection."""

    def setup_method(self):
        self.processor = AssessmentProcessor()

    def test_without_screening_unchanged(self):
        """When no screening, prompt should be identical to baseline."""
        system, user = self.processor._build_prompts(
            "System prompt",
            {"fact1": "value1"},
            "CLM-001",
        )
        assert "Screening" not in user
        assert "Pre-computed" not in user
        assert "CLM-001" in user

    def test_with_screening_injects_json(self):
        """When screening is provided, its JSON should appear in the user prompt."""
        screening = _make_non_auto_reject_screening()
        system, user = self.processor._build_prompts(
            "System prompt",
            {"fact1": "value1"},
            "CLM-001",
            screening=screening,
        )

        assert "Pre-computed Screening Results" in user
        assert "requires_llm" in user
        # The screening JSON should be parseable
        assert '"auto_reject": false' in user

    def test_screening_block_before_facts(self):
        """The screening block should appear before the aggregated facts."""
        screening = _make_non_auto_reject_screening()
        _, user = self.processor._build_prompts(
            "System prompt",
            {"fact1": "value1"},
            "CLM-001",
            screening=screening,
        )

        screening_pos = user.index("Pre-computed Screening Results")
        facts_pos = user.index("Aggregated Facts")
        assert screening_pos < facts_pos

    def test_system_prompt_not_affected_by_screening(self):
        """Screening should only affect the user prompt, not the system prompt."""
        screening = _make_non_auto_reject_screening()
        system_with, _ = self.processor._build_prompts(
            "System prompt content",
            {"fact1": "value1"},
            "CLM-001",
            screening=screening,
        )
        system_without, _ = self.processor._build_prompts(
            "System prompt content",
            {"fact1": "value1"},
            "CLM-001",
        )
        assert system_with == system_without

    def test_screening_none_same_as_no_param(self):
        """Passing screening=None should produce the same result as omitting it."""
        _, user_none = self.processor._build_prompts(
            "System prompt",
            {"fact1": "value1"},
            "CLM-001",
            screening=None,
        )
        _, user_default = self.processor._build_prompts(
            "System prompt",
            {"fact1": "value1"},
            "CLM-001",
        )
        assert user_none == user_default
