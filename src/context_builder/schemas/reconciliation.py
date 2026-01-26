"""Pydantic schemas for claim reconciliation and quality gates."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    """Reconciliation gate status."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class FactConflict(BaseModel):
    """A fact with conflicting values across documents."""

    fact_name: str = Field(..., description="Name of the conflicting fact")
    values: List[str] = Field(..., description="Different values found across documents")
    sources: List[List[str]] = Field(
        ..., description="Doc IDs grouped by value (parallel to values list)"
    )
    selected_value: str = Field(..., description="The value selected (highest confidence)")
    selected_confidence: float = Field(..., description="Confidence of selected value")
    selection_reason: str = Field(
        default="highest_confidence",
        description="Reason for selection (highest_confidence, most_recent)",
    )


class GateThresholds(BaseModel):
    """Configurable thresholds for reconciliation gate evaluation."""

    missing_critical_warn: int = Field(
        default=2, description="Warn if missing critical facts <= this value"
    )
    missing_critical_fail: int = Field(
        default=2, description="Fail if missing critical facts > this value"
    )
    conflict_warn: int = Field(
        default=2, description="Warn if conflicts <= this value"
    )
    conflict_fail: int = Field(
        default=2, description="Fail if conflicts > this value"
    )
    token_warn: int = Field(
        default=40000, description="Warn if estimated tokens > this value"
    )
    token_fail: int = Field(
        default=60000, description="Fail if estimated tokens > this value"
    )


class ReconciliationGate(BaseModel):
    """Gate evaluation result for claim reconciliation."""

    status: GateStatus = Field(..., description="Overall gate status")
    missing_critical_facts: List[str] = Field(
        default_factory=list, description="Critical facts that are missing"
    )
    conflict_count: int = Field(default=0, description="Number of fact conflicts detected")
    provenance_coverage: float = Field(
        default=0.0, description="Fraction of facts with provenance (0.0-1.0)"
    )
    estimated_tokens: int = Field(
        default=0, description="Estimated token count for facts"
    )
    reasons: List[str] = Field(
        default_factory=list, description="Human-readable reasons for gate status"
    )


class ReconciliationReport(BaseModel):
    """Full reconciliation report written to claim context directory."""

    schema_version: str = Field(
        default="reconciliation_v1", description="Schema version identifier"
    )
    claim_id: str = Field(..., description="Claim identifier")
    run_id: str = Field(..., description="Run ID used for reconciliation")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When reconciliation was performed"
    )
    gate: ReconciliationGate = Field(..., description="Gate evaluation result")
    conflicts: List[FactConflict] = Field(
        default_factory=list, description="List of detected conflicts"
    )
    fact_count: int = Field(default=0, description="Total number of aggregated facts")
    critical_facts_spec: List[str] = Field(
        default_factory=list, description="Critical facts that were checked"
    )
    critical_facts_present: List[str] = Field(
        default_factory=list, description="Critical facts that are present"
    )
    thresholds_used: GateThresholds = Field(
        default_factory=GateThresholds, description="Thresholds used for gate evaluation"
    )


class ReconciliationResult(BaseModel):
    """Result returned from reconciliation service."""

    claim_id: str = Field(..., description="Claim identifier")
    success: bool = Field(..., description="Whether reconciliation completed successfully")
    report: Optional[ReconciliationReport] = Field(
        None, description="Reconciliation report (if successful)"
    )
    error: Optional[str] = Field(None, description="Error message (if failed)")
