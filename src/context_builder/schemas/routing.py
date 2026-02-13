"""Pydantic models for the claim routing system (v2 -- CCI-driven).

The routing system uses the Composite Confidence Index (CCI) as the sole
driver of tier assignment:
- GREEN: CCI >= 0.70 (auto-processable)
- YELLOW: CCI >= 0.55 (assisted review)
- RED: CCI < 0.55, CCI missing, or verdict is REFER

Structural triggers (RT-1, RT-2, RT-3, RT-5, RT-6) are kept as
informational annotations for audit trail but do NOT affect the tier.

RED tier overrides the verdict to REFER_TO_HUMAN when original verdict
is APPROVE.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RoutingTier(str, Enum):
    """Claim routing tier determining processing mode."""

    GREEN = "GREEN"    # Auto-process
    YELLOW = "YELLOW"  # Assisted review
    RED = "RED"        # Manual review required


class RoutingTriggerResult(BaseModel):
    """Result of evaluating a single routing trigger."""

    trigger_id: str = Field(description="Trigger identifier, e.g. 'RT-1'")
    name: str = Field(description="Trigger name, e.g. 'reconciliation_gate_fail'")
    fired: bool = Field(description="Whether the trigger condition was met")
    severity: RoutingTier = Field(
        description="Tier assigned when this trigger fires"
    )
    signal_value: Optional[Any] = Field(
        default=None,
        description="Actual value of the signal that was evaluated",
    )
    threshold: Optional[Any] = Field(
        default=None,
        description="Threshold the signal was compared against",
    )
    explanation: str = Field(
        default="",
        description="Human-readable explanation of the trigger result",
    )


class RoutingDecision(BaseModel):
    """Complete routing decision for a claim."""

    schema_version: str = Field(default="routing_decision_v2")
    claim_id: str = Field(description="Claim identifier")
    claim_run_id: str = Field(description="Run that produced this decision")
    original_verdict: str = Field(
        description="Verdict before routing (APPROVE, DENY, REFER)"
    )
    routed_verdict: Optional[str] = Field(
        default=None,
        description="Verdict after routing override (set when tier=RED overrides to REFER)",
    )
    routing_tier: RoutingTier = Field(description="Final routing tier")
    triggers_evaluated: int = Field(
        description="Total number of triggers evaluated"
    )
    triggers_fired: List[RoutingTriggerResult] = Field(
        default_factory=list,
        description="Triggers that fired (condition met)",
    )
    all_triggers: List[RoutingTriggerResult] = Field(
        default_factory=list,
        description="All trigger results (fired and not fired)",
    )
    tier_reason: str = Field(
        default="",
        description="Human-readable explanation of why this tier was assigned",
    )
    structural_cci: Optional[float] = Field(
        default=None,
        description="CCI score computed without LLM self-reported confidence signals",
    )
    cci_threshold_green: float = Field(
        default=0.70,
        description="CCI threshold used for GREEN tier assignment",
    )
    cci_threshold_yellow: float = Field(
        default=0.55,
        description="CCI threshold used for YELLOW tier assignment",
    )
