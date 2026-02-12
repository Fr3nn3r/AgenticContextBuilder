"""Schemas for claim assessment results.

These schemas are used by the ClaimAssessmentService to return combined
reconciliation and assessment results from the `assess` CLI command.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from context_builder.schemas.reconciliation import ReconciliationReport
from context_builder.schemas.assessment_response import AssessmentResponse


class ClaimAssessmentResult(BaseModel):
    """Result of a full claim assessment (reconcile + assess).

    This model wraps both the reconciliation and assessment outputs,
    providing a unified result structure for the `assess` CLI command.

    The ``decision``, ``confidence_score``, and ``final_payout`` properties
    use authoritative sources only (dossier verdict, CCI score, screener
    payout).  The assessment's ``recommendation`` field is advisory and
    is NOT used as a fallback for the verdict.
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

    # Decision stage output (authoritative verdict)
    decision_dossier: Optional[Dict[str, Any]] = Field(
        None, description="Decision dossier from DecisionStage"
    )

    # Confidence stage output (authoritative CCI score)
    confidence_summary: Optional[Dict[str, Any]] = Field(
        None, description="Confidence summary from ConfidenceStage"
    )

    # Screening payout (authoritative payout)
    screening_payout: Optional[float] = Field(
        None, description="Screener-computed final payout"
    )

    # Summary fields for CLI display (extracted from nested objects)
    @property
    def decision(self) -> Optional[str]:
        """Final claim verdict (from dossier only).

        Returns the authoritative dossier claim_verdict.
        Does NOT fall back to the assessment recommendation.
        """
        if self.decision_dossier:
            verdict = self.decision_dossier.get("claim_verdict")
            if verdict:
                return verdict
        return None

    @property
    def confidence_score(self) -> Optional[float]:
        """Composite confidence score (0.0 - 1.0).

        Prefers CCI composite_score; falls back to LLM assessment confidence.
        """
        if self.confidence_summary:
            score = self.confidence_summary.get("composite_score")
            if score is not None:
                return float(score)
        if self.assessment:
            return self.assessment.confidence_score
        return None

    @property
    def confidence_band(self) -> Optional[str]:
        """CCI confidence band (high / moderate / low)."""
        if self.confidence_summary:
            return self.confidence_summary.get("band")
        return None

    @property
    def final_payout(self) -> Optional[float]:
        """Final recommended payout amount.

        Returns 0.0 for rejected claims.  Otherwise prefers screener
        payout, falling back to LLM assessment payout.
        """
        decision = self.decision
        if decision and decision.upper() in ("REJECT", "DENY"):
            return 0.0
        if self.screening_payout is not None:
            return self.screening_payout
        if self.assessment and self.assessment.payout:
            return self.assessment.payout.final_payout
        return None

    @property
    def gate_status(self) -> Optional[str]:
        """Quality gate status: pass, warn, or fail."""
        if self.reconciliation and self.reconciliation.gate:
            return self.reconciliation.gate.status.value
        return None
