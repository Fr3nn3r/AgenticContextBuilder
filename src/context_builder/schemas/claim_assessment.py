"""Schemas for claim assessment results.

These schemas are used by the ClaimAssessmentService to return combined
reconciliation and assessment results from the `assess` CLI command.
"""

from typing import Optional

from pydantic import BaseModel, Field

from context_builder.schemas.reconciliation import ReconciliationReport
from context_builder.schemas.assessment_response import AssessmentResponse


class ClaimAssessmentResult(BaseModel):
    """Result of a full claim assessment (reconcile + assess).

    This model wraps both the reconciliation and assessment outputs,
    providing a unified result structure for the `assess` CLI command.
    """

    claim_id: str = Field(..., description="Claim identifier")
    claim_run_id: Optional[str] = Field(
        None, description="Claim run ID where outputs are stored"
    )
    success: bool = Field(..., description="Whether the assessment completed successfully")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Reconciliation output
    reconciliation: Optional[ReconciliationReport] = Field(
        None, description="Reconciliation report from quality gate evaluation"
    )

    # Assessment output
    assessment: Optional[AssessmentResponse] = Field(
        None, description="Assessment response with decision and checks"
    )

    # Summary fields for CLI display (extracted from nested objects)
    @property
    def decision(self) -> Optional[str]:
        """Final assessment decision: APPROVE, REJECT, or REFER_TO_HUMAN."""
        if self.assessment:
            return self.assessment.decision
        return None

    @property
    def confidence_score(self) -> Optional[float]:
        """Confidence score from 0.0 to 1.0."""
        if self.assessment:
            return self.assessment.confidence_score
        return None

    @property
    def final_payout(self) -> Optional[float]:
        """Final recommended payout amount."""
        if self.assessment and self.assessment.payout:
            return self.assessment.payout.final_payout
        return None

    @property
    def gate_status(self) -> Optional[str]:
        """Quality gate status: pass, warn, or fail."""
        if self.reconciliation and self.reconciliation.gate:
            return self.reconciliation.gate.status.value
        return None
