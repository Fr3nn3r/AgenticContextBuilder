"""Unit tests for screening schemas."""

import json

import pytest
from pydantic import ValidationError

from context_builder.schemas.screening import (
    CheckVerdict,
    HARD_FAIL_CHECK_IDS,
    SCREENING_CHECK_IDS,
    ScreeningCheck,
    ScreeningPayoutCalculation,
    ScreeningResult,
)
from context_builder.schemas.assessment_response import AssessmentResponse


# ── Helpers ──────────────────────────────────────────────────────────


def _make_check(
    check_id: str = "1",
    check_name: str = "policy_validity",
    verdict: CheckVerdict = CheckVerdict.PASS,
    reason: str = "OK",
    **kwargs,
) -> ScreeningCheck:
    return ScreeningCheck(
        check_id=check_id,
        check_name=check_name,
        verdict=verdict,
        reason=reason,
        **kwargs,
    )


def _make_payout(**overrides) -> ScreeningPayoutCalculation:
    defaults = dict(
        covered_total=4500.0,
        not_covered_total=500.0,
        capped_amount=4500.0,
        deductible_amount=450.0,
        after_deductible=4050.0,
        policyholder_type="individual",
        final_payout=4050.0,
    )
    defaults.update(overrides)
    return ScreeningPayoutCalculation(**defaults)


def _make_result(**overrides) -> ScreeningResult:
    defaults = dict(
        claim_id="CLM-001",
        screening_timestamp="2026-01-28T10:00:00Z",
    )
    defaults.update(overrides)
    return ScreeningResult(**defaults)


# ── CheckVerdict ─────────────────────────────────────────────────────


class TestCheckVerdict:
    """Tests for CheckVerdict enum."""

    def test_enum_values(self):
        assert CheckVerdict.PASS.value == "PASS"
        assert CheckVerdict.FAIL.value == "FAIL"
        assert CheckVerdict.INCONCLUSIVE.value == "INCONCLUSIVE"
        assert CheckVerdict.SKIPPED.value == "SKIPPED"

    def test_string_comparison(self):
        """CheckVerdict(str, Enum) supports == with plain strings."""
        assert CheckVerdict.PASS == "PASS"
        assert CheckVerdict.FAIL == "FAIL"
        assert CheckVerdict.INCONCLUSIVE == "INCONCLUSIVE"
        assert CheckVerdict.SKIPPED == "SKIPPED"

    def test_all_values_present(self):
        names = {v.name for v in CheckVerdict}
        assert names == {"PASS", "FAIL", "INCONCLUSIVE", "SKIPPED"}

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            CheckVerdict("INVALID")


# ── ScreeningCheck ───────────────────────────────────────────────────


class TestScreeningCheck:
    """Tests for ScreeningCheck model."""

    def test_required_fields(self):
        check = _make_check()
        assert check.check_id == "1"
        assert check.check_name == "policy_validity"
        assert check.verdict == CheckVerdict.PASS
        assert check.reason == "OK"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            ScreeningCheck(check_id="1", check_name="test", verdict="PASS")
        with pytest.raises(ValidationError):
            ScreeningCheck(check_id="1", verdict="PASS", reason="x")

    def test_default_evidence_is_empty_dict(self):
        check = _make_check()
        assert check.evidence == {}

    def test_default_is_hard_fail_false(self):
        check = _make_check()
        assert check.is_hard_fail is False

    def test_default_requires_llm_false(self):
        check = _make_check()
        assert check.requires_llm is False

    def test_invalid_verdict_rejected(self):
        with pytest.raises(ValidationError):
            _make_check(verdict="INVALID")

    def test_serialization_roundtrip(self):
        check = _make_check(
            evidence={"claim_date": "2026-01-15", "policy_end": "2025-12-31"},
            is_hard_fail=True,
            requires_llm=True,
        )
        data = json.loads(check.model_dump_json())
        restored = ScreeningCheck(**data)
        assert restored == check


# ── ScreeningPayoutCalculation ───────────────────────────────────────


class TestScreeningPayoutCalculation:
    """Tests for ScreeningPayoutCalculation model."""

    def test_required_fields(self):
        payout = _make_payout()
        assert payout.covered_total == 4500.0
        assert payout.not_covered_total == 500.0
        assert payout.final_payout == 4050.0

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            ScreeningPayoutCalculation(
                covered_total=100.0,
                # missing not_covered_total and others
            )

    def test_default_currency_chf(self):
        payout = _make_payout()
        assert payout.currency == "CHF"

    def test_default_vat_deduction_zero(self):
        payout = _make_payout()
        assert payout.vat_deduction == 0.0
        assert payout.vat_adjusted is False

    def test_invalid_policyholder_type_rejected(self):
        with pytest.raises(ValidationError):
            _make_payout(policyholder_type="government")

    def test_company_with_vat(self):
        payout = _make_payout(
            policyholder_type="company",
            vat_adjusted=True,
            vat_deduction=308.0,
            final_payout=3742.0,
        )
        assert payout.policyholder_type == "company"
        assert payout.vat_adjusted is True
        assert payout.vat_deduction == 308.0


# ── ScreeningResult ──────────────────────────────────────────────────


class TestScreeningResult:
    """Tests for ScreeningResult model."""

    def test_default_schema_version(self):
        result = _make_result()
        assert result.schema_version == "screening_v1"

    def test_default_counts_zero(self):
        result = _make_result()
        assert result.checks_passed == 0
        assert result.checks_failed == 0
        assert result.checks_inconclusive == 0
        assert result.checks_for_llm == []

    def test_default_auto_reject_false(self):
        result = _make_result()
        assert result.auto_reject is False
        assert result.auto_reject_reason is None

    def test_recompute_counts_basic(self):
        result = _make_result(
            checks=[
                _make_check("1", "policy_validity", CheckVerdict.PASS),
                _make_check("2", "vehicle_id", CheckVerdict.PASS),
                _make_check("3", "mileage", CheckVerdict.FAIL, is_hard_fail=True),
                _make_check("4a", "shop_auth", CheckVerdict.INCONCLUSIVE, requires_llm=True),
                _make_check("5b", "assistance", CheckVerdict.SKIPPED),
            ]
        )
        result.recompute_counts()
        assert result.checks_passed == 2
        assert result.checks_failed == 1
        assert result.checks_inconclusive == 1
        assert result.checks_for_llm == ["4a"]

    def test_recompute_counts_sets_auto_reject_on_hard_fail(self):
        result = _make_result(
            checks=[
                _make_check("1", "policy_validity", CheckVerdict.FAIL, is_hard_fail=True),
                _make_check("2", "vehicle_id", CheckVerdict.PASS),
            ]
        )
        result.recompute_counts()
        assert result.auto_reject is True
        assert result.hard_fails == ["1"]
        assert "1" in result.auto_reject_reason

    def test_recompute_counts_inconclusive_not_hard_fail(self):
        """INCONCLUSIVE on a hard-fail check does NOT trigger auto-reject."""
        result = _make_result(
            checks=[
                _make_check("1", "policy_validity", CheckVerdict.INCONCLUSIVE),
                _make_check("3", "mileage", CheckVerdict.INCONCLUSIVE),
            ]
        )
        result.recompute_counts()
        assert result.auto_reject is False
        assert result.hard_fails == []

    def test_json_roundtrip(self):
        result = _make_result(
            checks=[_make_check("1", "policy_validity", CheckVerdict.PASS)],
            payout=_make_payout(),
            coverage_analysis_ref="coverage_analysis.json",
        )
        result.recompute_counts()
        json_str = result.model_dump_json()
        data = json.loads(json_str)
        restored = ScreeningResult(**data)
        assert restored.claim_id == result.claim_id
        assert restored.checks_passed == result.checks_passed
        assert restored.payout.final_payout == result.payout.final_payout

    def test_full_example(self):
        """Fully populated ScreeningResult with all fields."""
        result = ScreeningResult(
            schema_version="screening_v1",
            claim_id="CLM-999",
            screening_timestamp="2026-01-28T12:00:00Z",
            checks=[
                _make_check("1", "policy_validity", CheckVerdict.PASS, is_hard_fail=True),
                _make_check("1b", "damage_date", CheckVerdict.PASS, is_hard_fail=True),
                _make_check("2", "vehicle_id", CheckVerdict.PASS),
                _make_check("2b", "owner_match", CheckVerdict.INCONCLUSIVE, requires_llm=True),
                _make_check("3", "mileage", CheckVerdict.PASS, is_hard_fail=True),
                _make_check("4a", "shop_auth", CheckVerdict.PASS),
                _make_check("4b", "service_compliance", CheckVerdict.PASS),
                _make_check("5", "component_coverage", CheckVerdict.PASS, is_hard_fail=True),
                _make_check("5b", "assistance", CheckVerdict.SKIPPED),
            ],
            coverage_analysis_ref="coverage_analysis.json",
            payout=_make_payout(),
        )
        result.recompute_counts()
        assert result.checks_passed == 7
        assert result.checks_failed == 0
        assert result.checks_inconclusive == 1
        assert result.checks_for_llm == ["2b"]
        assert result.auto_reject is False
        assert result.hard_fails == []


# ── AssessmentResponse.assessment_method ─────────────────────────────


class TestAssessmentMethodField:
    """Tests for the assessment_method field on AssessmentResponse."""

    @staticmethod
    def _minimal_assessment(**overrides) -> dict:
        """Return minimal valid AssessmentResponse data."""
        base = {
            "claim_id": "CLM-001",
            "assessment_timestamp": "2026-01-28T10:30:00Z",
            "decision": "APPROVE",
            "decision_rationale": "All checks passed",
            "confidence_score": 0.85,
            "checks": [
                {
                    "check_number": "1",
                    "check_name": "policy_validity",
                    "result": "PASS",
                    "details": "OK",
                }
            ],
            "payout": {
                "total_claimed": 5000.0,
                "non_covered_deductions": 500.0,
                "covered_subtotal": 4500.0,
                "coverage_percent": 80,
                "after_coverage": 3600.0,
                "max_coverage_applied": False,
                "deductible": 360.0,
                "after_deductible": 3240.0,
                "vat_adjusted": False,
                "policyholder_type": "individual",
                "final_payout": 3240.0,
            },
        }
        base.update(overrides)
        return base

    def test_default_is_llm(self):
        resp = AssessmentResponse(**self._minimal_assessment())
        assert resp.assessment_method == "llm"

    def test_backward_compat_no_field(self):
        """Old JSON without assessment_method should load with default 'llm'."""
        data = self._minimal_assessment()
        assert "assessment_method" not in data
        resp = AssessmentResponse(**data)
        assert resp.assessment_method == "llm"

    def test_both_literals_accepted(self):
        for method in ("llm", "auto_reject"):
            resp = AssessmentResponse(
                **self._minimal_assessment(assessment_method=method)
            )
            assert resp.assessment_method == method

    def test_invalid_method_rejected(self):
        with pytest.raises(ValidationError):
            AssessmentResponse(
                **self._minimal_assessment(assessment_method="manual")
            )


# ── Constants ────────────────────────────────────────────────────────


class TestConstants:
    """Tests for module-level constants."""

    def test_screening_check_ids(self):
        expected = {"1", "1b", "2", "2b", "3", "4a", "4b", "5", "5b"}
        assert SCREENING_CHECK_IDS == expected

    def test_hard_fail_subset(self):
        assert HARD_FAIL_CHECK_IDS.issubset(SCREENING_CHECK_IDS)
