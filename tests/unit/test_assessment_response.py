"""Unit tests for assessment response schemas."""

import json
import pytest
from pydantic import ValidationError

from context_builder.schemas.assessment_response import (
    AssessmentResponse,
    AssistanceItem,
    AssistanceItems,
    DataGap,
    CheckResult,
    FraudIndicator,
    PayoutCalculation,
    EXPECTED_CHECK_NUMBERS,
    validate_assessment_completeness,
)


class TestCheckResult:
    """Tests for CheckResult schema."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        check = CheckResult(
            check_number="1",
            check_name="policy_validity",
            result="PASS",
            details="Claim date within policy period",
        )

        assert check.check_number == "1"
        assert check.check_name == "policy_validity"
        assert check.result == "PASS"
        assert check.details == "Claim date within policy period"

    def test_default_evidence_refs(self):
        """Test that evidence_refs defaults to empty list."""
        check = CheckResult(
            check_number="1",
            check_name="policy_validity",
            result="PASS",
            details="Test",
        )

        assert check.evidence_refs == []

    def test_result_literals(self):
        """Test that only valid result values are allowed."""
        for result in ["PASS", "FAIL", "INCONCLUSIVE", "NOT_CHECKED"]:
            check = CheckResult(
                check_number="1",
                check_name="test",
                result=result,
                details="Test",
            )
            assert check.result == result

    def test_invalid_result_rejected(self):
        """Test that invalid result values are rejected."""
        with pytest.raises(ValidationError):
            CheckResult(
                check_number="1",
                check_name="test",
                result="INVALID",
                details="Test",
            )

    def test_optional_owner_fields(self):
        """Test optional fields for owner/policyholder check."""
        check = CheckResult(
            check_number="2b",
            check_name="owner_policyholder_match",
            result="PASS",
            details="Names match",
            owner_found="Hans Muller",
            policyholder_found="Hans Muller",
            match_type="exact",
        )

        assert check.owner_found == "Hans Muller"
        assert check.policyholder_found == "Hans Muller"
        assert check.match_type == "exact"

    def test_serialization(self):
        """Test that check serializes to JSON correctly."""
        check = CheckResult(
            check_number="1",
            check_name="policy_validity",
            result="PASS",
            details="Claim date within policy period",
            evidence_refs=["nsa_guarantee.start_date", "nsa_guarantee.end_date"],
        )

        data = check.model_dump(mode="json")

        assert data["check_number"] == "1"
        assert data["result"] == "PASS"
        assert len(data["evidence_refs"]) == 2


class TestPayoutCalculation:
    """Tests for PayoutCalculation schema."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        payout = PayoutCalculation(
            total_claimed=5000.0,
            non_covered_deductions=500.0,
            covered_subtotal=4500.0,
            coverage_percent=80,
            after_coverage=3600.0,
            max_coverage_applied=False,
            deductible=360.0,
            after_deductible=3240.0,
            company_vat_deducted=False,
            policyholder_type="individual",
            final_payout=3240.0,
        )

        assert payout.total_claimed == 5000.0
        assert payout.coverage_percent == 80
        assert payout.final_payout == 3240.0

    def test_default_currency(self):
        """Test that currency defaults to CHF."""
        payout = PayoutCalculation(
            total_claimed=1000.0,
            non_covered_deductions=0.0,
            covered_subtotal=1000.0,
            coverage_percent=100,
            after_coverage=1000.0,
            max_coverage_applied=False,
            deductible=100.0,
            after_deductible=900.0,
            company_vat_deducted=False,
            policyholder_type="individual",
            final_payout=900.0,
        )

        assert payout.currency == "CHF"

    def test_default_vat_deduction(self):
        """Test that vat_deduction defaults to 0."""
        payout = PayoutCalculation(
            total_claimed=1000.0,
            non_covered_deductions=0.0,
            covered_subtotal=1000.0,
            coverage_percent=100,
            after_coverage=1000.0,
            max_coverage_applied=False,
            deductible=100.0,
            after_deductible=900.0,
            company_vat_deducted=False,
            policyholder_type="individual",
            final_payout=900.0,
        )

        assert payout.vat_deduction == 0.0

    def test_company_policyholder_with_vat(self):
        """Test company policyholder with VAT adjustment."""
        payout = PayoutCalculation(
            total_claimed=5000.0,
            non_covered_deductions=0.0,
            covered_subtotal=5000.0,
            coverage_percent=100,
            after_coverage=5000.0,
            max_coverage_applied=False,
            deductible=500.0,
            after_deductible=4500.0,
            company_vat_deducted=True,
            vat_deduction=336.73,
            policyholder_type="company",
            final_payout=4163.27,
        )

        assert payout.company_vat_deducted is True
        assert payout.policyholder_type == "company"

    def test_invalid_policyholder_type_rejected(self):
        """Test that invalid policyholder types are rejected."""
        with pytest.raises(ValidationError):
            PayoutCalculation(
                total_claimed=1000.0,
                non_covered_deductions=0.0,
                covered_subtotal=1000.0,
                coverage_percent=100,
                after_coverage=1000.0,
                max_coverage_applied=False,
                deductible=100.0,
                after_deductible=900.0,
                company_vat_deducted=False,
                policyholder_type="organization",  # Invalid
                final_payout=900.0,
            )


class TestAssistanceItems:
    """Tests for AssistanceItems schema."""

    def test_no_items_detected(self):
        """Test creating with no assistance items."""
        assistance = AssistanceItems(detected=False)

        assert assistance.detected is False
        assert assistance.items == []
        assert assistance.total_amount == 0.0

    def test_with_items(self):
        """Test creating with assistance items."""
        assistance = AssistanceItems(
            detected=True,
            items=[
                AssistanceItem(
                    description="Ersatzwagen 3 Tage",
                    amount=300.0,
                    type="replacement_car",
                ),
                AssistanceItem(
                    description="Abschleppen",
                    amount=150.0,
                    type="towing",
                ),
            ],
            total_amount=450.0,
        )

        assert assistance.detected is True
        assert len(assistance.items) == 2
        assert assistance.total_amount == 450.0

    def test_default_note(self):
        """Test default note value."""
        assistance = AssistanceItems(detected=False)

        assert assistance.note == "Verify separately under assistance package"


class TestDataGap:
    """Tests for DataGap schema."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        gap = DataGap(
            field="km_limited_to",
            impact="HIGH",
            action_taken="Flagged for human review",
        )

        assert gap.field == "km_limited_to"
        assert gap.impact == "HIGH"
        assert gap.action_taken == "Flagged for human review"

    def test_all_impact_levels(self):
        """Test all valid impact levels."""
        for impact in ["LOW", "MEDIUM", "HIGH"]:
            gap = DataGap(
                field="test_field",
                impact=impact,
                action_taken="Test action",
            )
            assert gap.impact == impact

    def test_invalid_impact_rejected(self):
        """Test that invalid impact values are rejected."""
        with pytest.raises(ValidationError):
            DataGap(
                field="test",
                impact="CRITICAL",  # Invalid
                action_taken="test action",
            )


class TestFraudIndicator:
    """Tests for FraudIndicator schema."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        indicator = FraudIndicator(
            indicator="Damage predates policy start",
            severity="high",
            details="Communication date 29.12.2025 is before policy start 31.12.2025",
        )

        assert indicator.indicator == "Damage predates policy start"
        assert indicator.severity == "high"

    def test_severity_values(self):
        """Test valid severity values."""
        for severity in ["high", "medium", "low"]:
            indicator = FraudIndicator(
                indicator="Test",
                severity=severity,
                details="Details",
            )
            assert indicator.severity == severity


class TestAssessmentResponse:
    """Tests for AssessmentResponse schema."""

    def test_required_fields(self):
        """Test creating response with required fields."""
        response = AssessmentResponse(
            claim_id="CLM-12345",
            assessment_timestamp="2026-01-28T10:00:00Z",
            recommendation="APPROVE",
            recommendation_rationale="All checks passed",
            confidence_score=0.85,
            checks=[
                CheckResult(
                    check_number="1",
                    check_name="policy_validity",
                    result="PASS",
                    details="Valid",
                )
            ],
            payout=PayoutCalculation(
                total_claimed=1000.0,
                non_covered_deductions=0.0,
                covered_subtotal=1000.0,
                coverage_percent=100,
                after_coverage=1000.0,
                max_coverage_applied=False,
                deductible=100.0,
                after_deductible=900.0,
                company_vat_deducted=False,
                policyholder_type="individual",
                final_payout=900.0,
            ),
        )

        assert response.claim_id == "CLM-12345"
        assert response.recommendation == "APPROVE"

    def test_default_schema_version(self):
        """Test that schema_version defaults to v2."""
        response = _create_minimal_response()

        assert response.schema_version == "claims_assessment_v2"

    def test_decision_literals(self):
        """Test that only valid decision values are allowed."""
        for decision in ["APPROVE", "REJECT", "REFER_TO_HUMAN"]:
            response = _create_minimal_response(decision=decision)
            assert response.recommendation == decision

    def test_invalid_decision_rejected(self):
        """Test that invalid decision values are rejected."""
        with pytest.raises(ValidationError):
            _create_minimal_response(decision="PENDING")

    def test_confidence_score_bounds(self):
        """Test that confidence score must be between 0 and 1."""
        # Valid bounds
        response = _create_minimal_response(confidence_score=0.0)
        assert response.confidence_score == 0.0

        response = _create_minimal_response(confidence_score=1.0)
        assert response.confidence_score == 1.0

        # Invalid: below 0
        with pytest.raises(ValidationError):
            _create_minimal_response(confidence_score=-0.1)

        # Invalid: above 1
        with pytest.raises(ValidationError):
            _create_minimal_response(confidence_score=1.1)

    def test_default_empty_lists(self):
        """Test that list fields default to empty."""
        response = _create_minimal_response()

        assert response.data_gaps == []
        assert response.fraud_indicators == []
        assert response.recommendations == []

    def test_full_response_serialization(self):
        """Test full response serializes correctly."""
        response = AssessmentResponse(
            schema_version="claims_assessment_v2",
            claim_id="CLM-12345",
            assessment_timestamp="2026-01-28T10:00:00Z",
            recommendation="APPROVE",
            recommendation_rationale="All checks passed, claim is valid",
            confidence_score=0.85,
            checks=[
                CheckResult(
                    check_number="1",
                    check_name="policy_validity",
                    result="PASS",
                    details="Policy valid from 2025-09-01 to 2026-08-31",
                    evidence_refs=["nsa_guarantee.start_date"],
                ),
                CheckResult(
                    check_number="1b",
                    check_name="damage_date_validity",
                    result="PASS",
                    details="No pre-existing damage",
                    evidence_refs=[],
                ),
            ],
            payout=PayoutCalculation(
                total_claimed=5000.0,
                non_covered_deductions=500.0,
                covered_subtotal=4500.0,
                coverage_percent=80,
                after_coverage=3600.0,
                max_coverage_applied=False,
                capped_amount=None,
                deductible=360.0,
                after_deductible=3240.0,
                company_vat_deducted=False,
                vat_deduction=0.0,
                policyholder_type="individual",
                final_payout=3240.0,
                currency="CHF",
            ),
            assistance_items=AssistanceItems(detected=False),
            data_gaps=[
                DataGap(
                    field="shop_authorization",
                    impact="MEDIUM",
                    action_taken="Assumed authorized - most claims from authorized shops",
                )
            ],
            fraud_indicators=[],
            recommendations=["Verify mileage at next service"],
        )

        data = response.model_dump(mode="json")

        assert data["schema_version"] == "claims_assessment_v2"
        assert data["claim_id"] == "CLM-12345"
        assert data["recommendation"] == "APPROVE"
        assert len(data["checks"]) == 2
        assert data["payout"]["final_payout"] == 3240.0
        assert len(data["data_gaps"]) == 1
        assert len(data["recommendations"]) == 1

    def test_json_round_trip(self):
        """Test that response survives JSON round-trip."""
        original = _create_minimal_response()

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Parse back
        data = json.loads(json_str)

        # Reconstruct
        restored = AssessmentResponse.model_validate(data)

        assert restored.claim_id == original.claim_id
        assert restored.recommendation == original.recommendation
        assert restored.confidence_score == original.confidence_score


class TestValidateAssessmentCompleteness:
    """Tests for validate_assessment_completeness function."""

    def test_complete_assessment_no_warnings(self):
        """Test that complete assessment produces no warnings."""
        response = _create_complete_response()

        warnings = validate_assessment_completeness(response)

        assert warnings == []

    def test_insufficient_checks_warning(self):
        """Test warning when too few checks present."""
        response = _create_minimal_response()  # Only 1 check

        warnings = validate_assessment_completeness(response)

        assert len(warnings) > 0
        assert any("Only 1 checks present" in w for w in warnings)

    def test_missing_checks_warning(self):
        """Test warning when specific checks are missing."""
        # Create response with only some checks
        response = AssessmentResponse(
            claim_id="CLM-12345",
            assessment_timestamp="2026-01-28T10:00:00Z",
            recommendation="APPROVE",
            recommendation_rationale="Test",
            confidence_score=0.8,
            checks=[
                CheckResult(check_number="1", check_name="policy_validity", result="PASS", details="OK"),
                CheckResult(check_number="2", check_name="vehicle_id", result="PASS", details="OK"),
                CheckResult(check_number="3", check_name="mileage", result="PASS", details="OK"),
                CheckResult(check_number="5", check_name="coverage", result="PASS", details="OK"),
                CheckResult(check_number="6", check_name="payout", result="PASS", details="OK"),
                CheckResult(check_number="7", check_name="decision", result="PASS", details="OK"),
                # Missing: 1b, 2b, 4a, 4b, 5b
            ],
            payout=_create_minimal_payout(),
        )

        warnings = validate_assessment_completeness(response)

        # Should warn about missing checks
        assert len(warnings) > 0
        assert any("Missing checks" in w for w in warnings)

    def test_expected_check_numbers(self):
        """Test that EXPECTED_CHECK_NUMBERS contains all required checks."""
        assert "1" in EXPECTED_CHECK_NUMBERS
        assert "1b" in EXPECTED_CHECK_NUMBERS
        assert "2" in EXPECTED_CHECK_NUMBERS
        assert "2b" in EXPECTED_CHECK_NUMBERS
        assert "3" in EXPECTED_CHECK_NUMBERS
        assert "4a" in EXPECTED_CHECK_NUMBERS
        assert "4b" in EXPECTED_CHECK_NUMBERS
        assert "5" in EXPECTED_CHECK_NUMBERS
        assert "5b" in EXPECTED_CHECK_NUMBERS
        assert "6" in EXPECTED_CHECK_NUMBERS
        assert "7" in EXPECTED_CHECK_NUMBERS


class TestJsonSchemaGeneration:
    """Tests for JSON schema generation."""

    def test_json_schema_generated(self):
        """Test that JSON schema can be generated."""
        schema = AssessmentResponse.model_json_schema()

        assert schema is not None
        assert "properties" in schema
        assert "claim_id" in schema["properties"]
        assert "recommendation" in schema["properties"]
        assert "checks" in schema["properties"]
        assert "payout" in schema["properties"]

    def test_schema_contains_required_fields(self):
        """Test that schema marks required fields."""
        schema = AssessmentResponse.model_json_schema()

        # Check that required is defined
        assert "required" in schema or all(
            "default" in prop for prop in schema.get("properties", {}).values()
        )


# Helper functions for creating test responses


def _create_minimal_payout() -> PayoutCalculation:
    """Create a minimal valid payout calculation."""
    return PayoutCalculation(
        total_claimed=1000.0,
        non_covered_deductions=0.0,
        covered_subtotal=1000.0,
        coverage_percent=100,
        after_coverage=1000.0,
        max_coverage_applied=False,
        deductible=100.0,
        after_deductible=900.0,
        company_vat_deducted=False,
        policyholder_type="individual",
        final_payout=900.0,
    )


def _create_minimal_response(
    decision: str = "APPROVE",
    confidence_score: float = 0.85,
) -> AssessmentResponse:
    """Create a minimal valid assessment response."""
    return AssessmentResponse(
        claim_id="CLM-12345",
        assessment_timestamp="2026-01-28T10:00:00Z",
        recommendation=decision,
        recommendation_rationale="Test response",
        confidence_score=confidence_score,
        checks=[
            CheckResult(
                check_number="1",
                check_name="policy_validity",
                result="PASS",
                details="Valid",
            )
        ],
        payout=_create_minimal_payout(),
    )


def _create_complete_response() -> AssessmentResponse:
    """Create a complete assessment response with all checks."""
    checks = [
        CheckResult(check_number="1", check_name="policy_validity", result="PASS", details="OK"),
        CheckResult(check_number="1b", check_name="damage_date_validity", result="PASS", details="OK"),
        CheckResult(check_number="2", check_name="vehicle_id_consistency", result="PASS", details="OK"),
        CheckResult(check_number="2b", check_name="owner_policyholder_match", result="PASS", details="OK"),
        CheckResult(check_number="3", check_name="mileage_compliance", result="PASS", details="OK"),
        CheckResult(check_number="4a", check_name="shop_authorization", result="PASS", details="OK"),
        CheckResult(check_number="4b", check_name="service_compliance", result="PASS", details="OK"),
        CheckResult(check_number="5", check_name="component_coverage", result="PASS", details="OK"),
        CheckResult(check_number="5b", check_name="assistance_package_items", result="PASS", details="OK"),
        CheckResult(check_number="6", check_name="payout_calculation", result="PASS", details="OK"),
        CheckResult(check_number="7", check_name="final_decision", result="PASS", details="OK"),
    ]

    return AssessmentResponse(
        claim_id="CLM-12345",
        assessment_timestamp="2026-01-28T10:00:00Z",
        recommendation="APPROVE",
        recommendation_rationale="All checks passed",
        confidence_score=0.95,
        checks=checks,
        payout=_create_minimal_payout(),
    )
