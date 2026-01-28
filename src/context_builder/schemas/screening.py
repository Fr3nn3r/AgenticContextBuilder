"""Pydantic models for deterministic screening results.

The screening stage runs rule-based checks on aggregated claim facts
before (or instead of) a full LLM assessment.  These schemas capture
the check verdicts, payout calculation, and auto-reject decision so
they can be persisted as ``screening.json`` alongside each claim.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ── Constants ────────────────────────────────────────────────────────

SCREENING_CHECK_IDS = {"1", "1b", "2", "2b", "3", "4a", "4b", "5", "5b"}

HARD_FAIL_CHECK_IDS = {"1", "1b", "3", "5"}
# 1  = policy_validity
# 1b = damage_date (clear-cut)
# 3  = mileage
# 5  = component_coverage


# ── Enums ────────────────────────────────────────────────────────────

class CheckVerdict(str, Enum):
    """Deterministic verdict for a screening check."""

    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"


# ── Models ───────────────────────────────────────────────────────────

class ScreeningCheck(BaseModel):
    """Result of a single deterministic screening check."""

    check_id: str = Field(
        description="Check identifier, e.g. '1', '1b', '2', '2b', '3', '4a', '4b', '5', '5b'",
    )
    check_name: str = Field(description="Human-readable check name")
    verdict: CheckVerdict = Field(description="Deterministic verdict")
    reason: str = Field(description="Explanation of the verdict")
    evidence: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value evidence supporting the verdict",
    )
    is_hard_fail: bool = Field(
        default=False,
        description="Whether a FAIL verdict triggers auto-reject",
    )
    requires_llm: bool = Field(
        default=False,
        description="Whether the LLM should review this check",
    )


class ScreeningPayoutCalculation(BaseModel):
    """Deterministic payout calculation from screening data."""

    covered_total: float = Field(
        description="Total covered amount before excess (from CoverageSummary)",
    )
    not_covered_total: float = Field(
        description="Total not-covered amount (from CoverageSummary)",
    )
    coverage_percent: Optional[float] = Field(
        default=None, description="Coverage percentage from policy scale"
    )
    max_coverage: Optional[float] = Field(
        default=None, description="Maximum coverage cap from policy terms"
    )
    max_coverage_applied: bool = Field(
        default=False, description="Whether the coverage cap was applied"
    )
    capped_amount: float = Field(
        description="Amount after cap (equals covered_total if no cap)",
    )
    deductible_percent: Optional[float] = Field(
        default=None, description="Deductible percentage from policy"
    )
    deductible_minimum: Optional[float] = Field(
        default=None, description="Minimum deductible from policy"
    )
    deductible_amount: float = Field(
        description="Deductible applied: MAX(capped * percent, minimum)",
    )
    after_deductible: float = Field(
        description="Amount after deductible: capped - deductible",
    )
    policyholder_type: Literal["individual", "company"] = Field(
        description="Determines VAT treatment",
    )
    vat_adjusted: bool = Field(
        default=False, description="True when VAT deduction is applied (companies)"
    )
    vat_deduction: float = Field(
        default=0.0, description="VAT amount deducted"
    )
    final_payout: float = Field(description="Final payout result")
    currency: str = Field(default="CHF", description="Currency code")


class ScreeningResult(BaseModel):
    """Complete screening result persisted as screening.json."""

    schema_version: str = Field(
        default="screening_v1",
        description="Schema version for compatibility tracking",
    )
    claim_id: str = Field(description="Claim identifier")
    screening_timestamp: str = Field(
        description="ISO timestamp of when screening was performed",
    )
    checks: List[ScreeningCheck] = Field(
        default_factory=list, description="All screening check results"
    )
    checks_passed: int = Field(default=0, description="Count of PASS verdicts")
    checks_failed: int = Field(default=0, description="Count of FAIL verdicts")
    checks_inconclusive: int = Field(
        default=0, description="Count of INCONCLUSIVE verdicts"
    )
    checks_for_llm: List[str] = Field(
        default_factory=list,
        description="Check IDs that need LLM review",
    )
    coverage_analysis_ref: Optional[str] = Field(
        default=None,
        description="Relative path to coverage_analysis.json",
    )
    payout: Optional[ScreeningPayoutCalculation] = Field(
        default=None, description="Payout calculation (None if not computable)"
    )
    payout_error: Optional[str] = Field(
        default=None, description="Error message if payout calculation failed"
    )
    auto_reject: bool = Field(
        default=False, description="Whether the claim is auto-rejected"
    )
    auto_reject_reason: Optional[str] = Field(
        default=None, description="Reason for auto-rejection"
    )
    hard_fails: List[str] = Field(
        default_factory=list, description="Check IDs that hard-failed"
    )

    def recompute_counts(self) -> None:
        """Recompute counts, hard_fails, and auto_reject from the checks list."""
        self.checks_passed = sum(
            1 for c in self.checks if c.verdict == CheckVerdict.PASS
        )
        self.checks_failed = sum(
            1 for c in self.checks if c.verdict == CheckVerdict.FAIL
        )
        self.checks_inconclusive = sum(
            1 for c in self.checks if c.verdict == CheckVerdict.INCONCLUSIVE
        )
        self.checks_for_llm = [c.check_id for c in self.checks if c.requires_llm]
        self.hard_fails = [
            c.check_id
            for c in self.checks
            if c.verdict == CheckVerdict.FAIL and c.is_hard_fail
        ]
        self.auto_reject = len(self.hard_fails) > 0
        if self.auto_reject:
            self.auto_reject_reason = (
                f"Hard fail on check(s): {', '.join(sorted(self.hard_fails))}"
            )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra = {
            "example": {
                "schema_version": "screening_v1",
                "claim_id": "CLM-12345",
                "screening_timestamp": "2026-01-28T10:00:00Z",
                "checks": [
                    {
                        "check_id": "1",
                        "check_name": "policy_validity",
                        "verdict": "PASS",
                        "reason": "Claim date 2026-01-10 is within policy period",
                        "evidence": {
                            "claim_date": "2026-01-10",
                            "policy_start": "2025-01-01",
                            "policy_end": "2026-12-31",
                        },
                        "is_hard_fail": True,
                        "requires_llm": False,
                    }
                ],
                "checks_passed": 1,
                "checks_failed": 0,
                "checks_inconclusive": 0,
                "checks_for_llm": [],
                "coverage_analysis_ref": "coverage_analysis.json",
                "payout": {
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
                },
                "payout_error": None,
                "auto_reject": False,
                "auto_reject_reason": None,
                "hard_fails": [],
            }
        }
