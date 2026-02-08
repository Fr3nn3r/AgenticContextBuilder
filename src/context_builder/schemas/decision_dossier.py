"""Pydantic models for the Decision Dossier.

The decision stage evaluates every claim against a set of denial clauses
from the workspace config, producing a versioned Decision Dossier with
full traceability.  The dossier shows:
- Claim-level verdict (APPROVE / DENY / REFER) with clause citations
- Line-item-level verdicts — what's covered, denied, adjusted, and why
- Assumptions for non-automatable clauses, toggleable by the adjuster
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────


class ClaimVerdict(str, Enum):
    """Top-level claim decision."""

    APPROVE = "APPROVE"
    DENY = "DENY"
    REFER = "REFER"


class LineItemVerdict(str, Enum):
    """Per-line-item decision."""

    COVERED = "COVERED"
    DENIED = "DENIED"
    PARTIAL = "PARTIAL"
    REFER = "REFER"


class EvaluabilityTier(int, Enum):
    """How automatable a denial clause is.

    1 = deterministic (can be evaluated from extracted facts alone)
    2 = inferrable (evidence may exist; falls back to assumption)
    3 = not_automatable (always requires human judgement / assumption)
    """

    DETERMINISTIC = 1
    INFERRABLE = 2
    NOT_AUTOMATABLE = 3


class ClauseEvaluationLevel(str, Enum):
    """Scope at which a denial clause is evaluated."""

    CLAIM = "claim"
    LINE_ITEM = "line_item"
    CLAIM_WITH_ITEM_CONSEQUENCE = "claim_with_item_consequence"


# ── Clause definition (loaded from workspace config) ────────────────


class DenialClauseDefinition(BaseModel):
    """Metadata for a single denial clause loaded from the workspace config."""

    reference: str = Field(description="Clause reference, e.g. '2.2.A'")
    text: str = Field(description="Full clause text")
    short_name: str = Field(description="Human-readable short name")
    category: str = Field(description="Category: coverage, exclusion, limitation, procedural")
    evaluation_level: ClauseEvaluationLevel = Field(
        description="Scope: claim, line_item, or claim_with_item_consequence"
    )
    evaluability_tier: EvaluabilityTier = Field(
        description="Tier 1=deterministic, 2=inferrable, 3=not_automatable"
    )
    default_assumption: bool = Field(
        default=True,
        description="Default assumption value (True = non-rejecting / PASS)",
    )
    assumption_question: Optional[str] = Field(
        default=None,
        description="Question displayed to the adjuster for tier 2/3 clauses",
    )


# ── Evidence & evaluation results ───────────────────────────────────


class ClauseEvidence(BaseModel):
    """A single piece of evidence supporting a clause evaluation."""

    fact_name: str = Field(description="Name of the fact used as evidence")
    fact_value: Optional[str] = Field(default=None, description="Value of the fact")
    source_doc_id: Optional[str] = Field(
        default=None, description="Source document ID"
    )
    screening_check_id: Optional[str] = Field(
        default=None, description="Screening check ID that produced this evidence"
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable description of how evidence applies"
    )


class ClauseEvaluation(BaseModel):
    """Result of evaluating a single denial clause."""

    clause_reference: str = Field(description="Clause reference, e.g. '2.2.A'")
    clause_short_name: str = Field(description="Human-readable short name")
    category: str = Field(description="Clause category")
    evaluation_level: ClauseEvaluationLevel = Field(
        description="Scope at which clause was evaluated"
    )
    evaluability_tier: EvaluabilityTier = Field(description="Automation tier")
    verdict: str = Field(
        description="PASS (clause not triggered) or FAIL (clause triggered / denial applies)"
    )
    assumption_used: Optional[bool] = Field(
        default=None,
        description="If tier 2/3, the assumption value used for this evaluation",
    )
    evidence: List[ClauseEvidence] = Field(
        default_factory=list,
        description="Evidence items supporting the verdict",
    )
    reason: str = Field(description="Explanation of the verdict")
    affected_line_items: List[str] = Field(
        default_factory=list,
        description="Line item IDs affected (for claim_with_item_consequence clauses)",
    )


# ── Line-item decisions ─────────────────────────────────────────────


class LineItemDecision(BaseModel):
    """Decision for a single invoice line item."""

    item_id: str = Field(description="Line item identifier")
    description: str = Field(default="", description="Line item description")
    item_type: str = Field(
        default="unknown",
        description="Item type: parts, labor, fees, other",
    )
    verdict: LineItemVerdict = Field(description="Coverage verdict for this item")
    applicable_clauses: List[str] = Field(
        default_factory=list,
        description="Clause references that apply to this item",
    )
    denial_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for denial or partial coverage",
    )
    claimed_amount: float = Field(default=0.0, description="Amount claimed")
    approved_amount: float = Field(default=0.0, description="Amount approved")
    denied_amount: float = Field(default=0.0, description="Amount denied")
    adjusted_amount: float = Field(
        default=0.0,
        description="Amount adjusted (difference from claimed to approved due to rate limits etc.)",
    )
    adjustment_reason: Optional[str] = Field(
        default=None, description="Reason for adjustment"
    )


# ── Assumptions ─────────────────────────────────────────────────────


class AssumptionRecord(BaseModel):
    """Traces an assumption made during evaluation."""

    clause_reference: str = Field(description="Clause reference this assumption applies to")
    question: str = Field(description="Question posed to the adjuster")
    assumed_value: bool = Field(description="Value assumed (True = non-rejecting)")
    adjuster_confirmed: bool = Field(
        default=False,
        description="Whether the adjuster explicitly confirmed this assumption",
    )
    tier: EvaluabilityTier = Field(description="Evaluability tier of the clause")


# ── Financial summary ───────────────────────────────────────────────


class FinancialSummary(BaseModel):
    """Aggregated financial summary computed from line-item decisions."""

    total_claimed: float = Field(default=0.0, description="Sum of all claimed amounts")
    total_covered: float = Field(default=0.0, description="Sum of approved amounts")
    total_denied: float = Field(default=0.0, description="Sum of denied amounts")
    total_adjusted: float = Field(
        default=0.0, description="Sum of adjustments (rate limits, flat rates)"
    )
    net_payout: float = Field(
        default=0.0, description="Final payout: total_covered (after adjustments)"
    )
    currency: str = Field(default="CHF", description="Currency code")
    parts_total: float = Field(default=0.0, description="Total for parts line items")
    labor_total: float = Field(default=0.0, description="Total for labor line items")
    fees_total: float = Field(default=0.0, description="Total for fees line items")
    other_total: float = Field(default=0.0, description="Total for other line items")


# ── Decision Dossier (top-level) ────────────────────────────────────


class DecisionDossier(BaseModel):
    """Top-level Decision Dossier — the complete decision artifact.

    Versioned per claim: each re-evaluation produces a new version.
    Persisted as ``decision_dossier_v{N}.json`` in the claim run directory.
    """

    schema_version: str = Field(
        default="decision_dossier_v1",
        description="Schema version for compatibility tracking",
    )
    claim_id: str = Field(description="Claim identifier")
    version: int = Field(
        default=1,
        description="Dossier version number (incremented on re-evaluation)",
    )
    claim_verdict: ClaimVerdict = Field(description="Top-level claim decision")
    verdict_reason: str = Field(
        default="", description="Summary explanation of the claim verdict"
    )
    clause_evaluations: List[ClauseEvaluation] = Field(
        default_factory=list,
        description="Evaluation results for all denial clauses",
    )
    line_item_decisions: List[LineItemDecision] = Field(
        default_factory=list,
        description="Per-line-item coverage decisions",
    )
    assumptions_used: List[AssumptionRecord] = Field(
        default_factory=list,
        description="All assumptions made during evaluation",
    )
    financial_summary: Optional[FinancialSummary] = Field(
        default=None,
        description="Aggregated financial summary (None if DENY)",
    )
    engine_id: str = Field(default="", description="ID of the decision engine used")
    engine_version: str = Field(
        default="", description="Version of the decision engine"
    )
    evaluation_timestamp: str = Field(
        default="", description="ISO timestamp of when evaluation was performed"
    )
    input_refs: Dict[str, Any] = Field(
        default_factory=dict,
        description="References to input artifacts (screening, coverage, processing run IDs)",
    )
    failed_clauses: List[str] = Field(
        default_factory=list,
        description="Clause references that triggered (verdict=FAIL)",
    )
    unresolved_assumptions: List[str] = Field(
        default_factory=list,
        description="Clause references with unconfirmed tier 2/3 assumptions",
    )
