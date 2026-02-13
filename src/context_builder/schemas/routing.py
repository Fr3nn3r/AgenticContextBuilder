"""Pydantic models for the claim routing system.

The routing system evaluates structural signals to classify claims into
three tiers:
- GREEN: auto-processable (high structural confidence)
- YELLOW: assisted review (some concerns but manageable)
- RED: manual review required (hard triggers fired)

RED triggers override the verdict to REFER_TO_HUMAN.
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

    schema_version: str = Field(default="routing_decision_v1")
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
