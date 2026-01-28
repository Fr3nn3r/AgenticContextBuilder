"""Pydantic models for structured assessment response output.

This module defines the schema for JSON-only assessment responses.
Using structured outputs (JSON schema) guarantees complete responses
without truncation that can occur when markdown + JSON is requested.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Result of a single assessment check."""

    check_number: str = Field(
        description="Check identifier: '1', '1b', '2', '2b', '3', '4a', '4b', '5', '5b', '6', '7'"
    )
    check_name: str = Field(description="Name of the check performed")
    result: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_CHECKED"] = Field(
        description="Result of the check"
    )
    details: str = Field(description="Detailed explanation of the check result")
    evidence_refs: List[str] = Field(
        default_factory=list, description="Fact names used as evidence for this check"
    )
    # Optional fields for specific checks
    owner_found: Optional[str] = Field(
        default=None, description="Owner name found (for check 2b)"
    )
    policyholder_found: Optional[str] = Field(
        default=None, description="Policyholder name found (for check 2b)"
    )
    match_type: Optional[
        Literal["exact", "variation", "mismatch", "owner_not_found"]
    ] = Field(default=None, description="Type of match for owner/policyholder check")


class PayoutCalculation(BaseModel):
    """Detailed payout calculation breakdown."""

    total_claimed: float = Field(description="Total amount claimed (parts + labor)")
    non_covered_deductions: float = Field(
        description="Amount deducted for non-covered items"
    )
    covered_subtotal: float = Field(
        description="Subtotal after removing non-covered items"
    )
    coverage_percent: int = Field(
        description="Coverage percentage applied to parts (e.g., 40, 60, 80)"
    )
    after_coverage: float = Field(
        description="Amount after applying coverage percentage"
    )
    max_coverage_applied: bool = Field(
        description="Whether max coverage cap was applied"
    )
    capped_amount: Optional[float] = Field(
        default=None, description="Amount after cap (if max_coverage_applied is true)"
    )
    deductible: float = Field(description="Deductible amount applied")
    after_deductible: float = Field(description="Amount after deductible")
    vat_adjusted: bool = Field(
        description="Whether VAT adjustment was applied (company policyholders)"
    )
    vat_deduction: float = Field(
        default=0.0, description="VAT amount deducted (0 for individuals)"
    )
    policyholder_type: Literal["individual", "company"] = Field(
        description="Type of policyholder"
    )
    final_payout: float = Field(description="Final recommended payout amount")
    currency: str = Field(default="CHF", description="Currency code")


class AssistanceItem(BaseModel):
    """Assistance package item detected in the claim."""

    description: str = Field(description="Description of the assistance item")
    amount: float = Field(description="Amount for this item")
    type: Literal["replacement_car", "towing"] = Field(
        description="Type of assistance item"
    )


class AssistanceItems(BaseModel):
    """Container for assistance package items."""

    detected: bool = Field(
        description="Whether any assistance items were detected"
    )
    items: List[AssistanceItem] = Field(
        default_factory=list, description="List of detected assistance items"
    )
    total_amount: float = Field(
        default=0.0, description="Total amount of assistance items"
    )
    note: str = Field(
        default="Verify separately under assistance package",
        description="Note about handling assistance items",
    )


class DataGap(BaseModel):
    """Data gap identified during assessment where information was missing or unclear."""

    field: str = Field(description="Field that was missing or unclear")
    impact: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        description="Impact on confidence score"
    )
    action_taken: str = Field(
        description="How the gap was handled (e.g., inferred value X, flagged for review)"
    )


class FraudIndicator(BaseModel):
    """Potential fraud indicator detected."""

    indicator: str = Field(description="Description of the fraud indicator")
    severity: Literal["high", "medium", "low"] = Field(
        description="Severity of the indicator"
    )
    details: str = Field(description="Supporting details")


class AssessmentResponse(BaseModel):
    """Complete assessment response structure.

    This schema is used with OpenAI structured outputs to guarantee
    a complete, well-formed response from the LLM.
    """

    schema_version: str = Field(
        default="claims_assessment_v2",
        description="Schema version for compatibility tracking",
    )
    assessment_method: Literal["llm", "auto_reject"] = Field(
        default="llm",
        description=(
            "How this assessment was produced: "
            "'llm' for standard LLM assessment, "
            "'auto_reject' for screening auto-rejection (no LLM called)"
        ),
    )
    claim_id: str = Field(description="Identifier of the assessed claim")
    assessment_timestamp: str = Field(
        description="ISO timestamp of when assessment was performed"
    )
    decision: Literal["APPROVE", "REJECT", "REFER_TO_HUMAN"] = Field(
        description="Final assessment decision"
    )
    decision_rationale: str = Field(
        description="Brief explanation of the decision"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0"
    )
    checks: List[CheckResult] = Field(
        description="List of all checks performed (should have 7+ entries)"
    )
    payout: PayoutCalculation = Field(description="Payout calculation details")
    assistance_items: AssistanceItems = Field(
        default_factory=lambda: AssistanceItems(detected=False),
        description="Assistance package items if detected",
    )
    data_gaps: List[DataGap] = Field(
        default_factory=list, description="Data gaps identified during assessment"
    )
    fraud_indicators: List[FraudIndicator] = Field(
        default_factory=list, description="Potential fraud indicators detected"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for next steps"
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "schema_version": "claims_assessment_v2",
                "assessment_method": "llm",
                "claim_id": "CLM-12345",
                "assessment_timestamp": "2026-01-28T10:30:00Z",
                "decision": "APPROVE",
                "decision_rationale": "All checks passed, claim is valid",
                "confidence_score": 0.85,
                "checks": [
                    {
                        "check_number": "1",
                        "check_name": "policy_validity",
                        "result": "PASS",
                        "details": "Claim date within policy period",
                        "evidence_refs": ["nsa_guarantee.start_date"],
                    }
                ],
                "payout": {
                    "total_claimed": 5000.0,
                    "non_covered_deductions": 500.0,
                    "covered_subtotal": 4500.0,
                    "coverage_percent": 80,
                    "after_coverage": 3600.0,
                    "max_coverage_applied": False,
                    "capped_amount": None,
                    "deductible": 360.0,
                    "after_deductible": 3240.0,
                    "vat_adjusted": False,
                    "vat_deduction": 0.0,
                    "policyholder_type": "individual",
                    "final_payout": 3240.0,
                    "currency": "CHF",
                },
                "assistance_items": {
                    "detected": False,
                    "items": [],
                    "total_amount": 0.0,
                    "note": "Verify separately under assistance package",
                },
                "data_gaps": [],
                "fraud_indicators": [],
                "recommendations": [],
            }
        }


# Minimum number of checks expected in a complete assessment
MIN_EXPECTED_CHECKS = 7

# Expected check numbers for validation
EXPECTED_CHECK_NUMBERS = {
    "1",      # policy_validity
    "1b",     # damage_date_validity
    "2",      # vehicle_id_consistency
    "2b",     # owner_policyholder_match
    "3",      # mileage_compliance
    "4a",     # shop_authorization
    "4b",     # service_compliance
    "5",      # component_coverage
    "5b",     # assistance_package_items
    "6",      # payout_calculation
    "7",      # final_decision
}


def validate_assessment_completeness(response: AssessmentResponse) -> List[str]:
    """Validate that an assessment response contains all expected checks.

    Args:
        response: The assessment response to validate.

    Returns:
        List of validation warnings (empty if all checks present).
    """
    warnings = []

    # Check minimum number of checks
    if len(response.checks) < MIN_EXPECTED_CHECKS:
        warnings.append(
            f"Only {len(response.checks)} checks present, expected at least {MIN_EXPECTED_CHECKS}"
        )

    # Check for missing expected checks
    present_checks = {c.check_number for c in response.checks}
    missing_checks = EXPECTED_CHECK_NUMBERS - present_checks
    if missing_checks:
        warnings.append(f"Missing checks: {sorted(missing_checks)}")

    return warnings
