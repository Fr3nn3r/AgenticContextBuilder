"""Pydantic schemas for claim reconciliation and quality gates."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GateStatus(str, Enum):
    """Reconciliation gate status."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class ConflictSource(BaseModel):
    """Source document info for a conflicting value."""

    doc_id: str = Field(..., description="Document identifier")
    doc_type: str = Field(..., description="Document type (e.g., cost_estimate, service_history)")
    filename: str = Field(..., description="Original filename for display")


class FactConflict(BaseModel):
    """A fact with conflicting values across documents."""

    fact_name: str = Field(..., description="Name of the conflicting fact")
    values: List[str] = Field(..., description="Different values found across documents")
    sources: List[List[ConflictSource]] = Field(
        ..., description="Source documents grouped by value (parallel to values list)"
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
        default="reconciliation_v3", description="Schema version identifier"
    )
    claim_id: str = Field(..., description="Claim identifier")
    claim_run_id: str = Field(..., description="Claim run ID that produced this reconciliation")
    run_id: Optional[str] = Field(
        None, description="Deprecated - use extractions_used. Single run ID if only one run was used."
    )
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
    extractions_used: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of {doc_id, run_id, filename} showing which extraction was used per document"
    )


class ReconciliationResult(BaseModel):
    """Result returned from reconciliation service."""

    claim_id: str = Field(..., description="Claim identifier")
    success: bool = Field(..., description="Whether reconciliation completed successfully")
    report: Optional[ReconciliationReport] = Field(
        None, description="Reconciliation report (if successful)"
    )
    error: Optional[str] = Field(None, description="Error message (if failed)")


# =============================================================================
# RUN-LEVEL EVALUATION SCHEMAS
# =============================================================================


class ReconciliationClaimResult(BaseModel):
    """Per-claim result in run-level evaluation."""

    claim_id: str = Field(..., description="Claim identifier")
    gate_status: GateStatus = Field(..., description="Gate status (pass/warn/fail)")
    fact_count: int = Field(default=0, description="Number of aggregated facts")
    conflict_count: int = Field(default=0, description="Number of conflicts detected")
    missing_critical_count: int = Field(
        default=0, description="Number of missing critical facts"
    )
    missing_critical_facts: List[str] = Field(
        default_factory=list, description="List of missing critical facts"
    )
    provenance_coverage: float = Field(
        default=0.0, description="Fraction of facts with provenance"
    )
    reasons: List[str] = Field(
        default_factory=list, description="Gate status reasons"
    )


class FactFrequency(BaseModel):
    """Frequency count for a fact (missing or conflicting)."""

    fact_name: str = Field(..., description="Fact name")
    count: int = Field(..., description="Number of claims affected")
    claim_ids: List[str] = Field(
        default_factory=list, description="Claims where this fact is missing/conflicting"
    )


class ReconciliationEvalSummary(BaseModel):
    """Summary statistics for run-level evaluation."""

    total_claims: int = Field(default=0, description="Total claims evaluated")
    passed: int = Field(default=0, description="Claims with PASS gate status")
    warned: int = Field(default=0, description="Claims with WARN gate status")
    failed: int = Field(default=0, description="Claims with FAIL gate status")
    pass_rate: float = Field(default=0.0, description="Fraction of claims passing (0.0-1.0)")
    pass_rate_percent: str = Field(default="0.0%", description="Pass rate as percentage")
    avg_fact_count: float = Field(default=0.0, description="Average facts per claim")
    avg_conflicts: float = Field(default=0.0, description="Average conflicts per claim")
    avg_missing_critical: float = Field(
        default=0.0, description="Average missing critical facts per claim"
    )
    total_conflicts: int = Field(default=0, description="Total conflicts across all claims")


class ReconciliationRunEval(BaseModel):
    """Run-level reconciliation gate evaluation output."""

    schema_version: str = Field(
        default="reconciliation_eval_v1", description="Schema version identifier"
    )
    evaluated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When evaluation was performed"
    )
    run_id: Optional[str] = Field(
        None, description="Run ID used for reconciliation (if consistent)"
    )
    summary: ReconciliationEvalSummary = Field(
        default_factory=ReconciliationEvalSummary, description="Summary statistics"
    )
    top_missing_facts: List[FactFrequency] = Field(
        default_factory=list,
        description="Most frequently missing critical facts across claims",
    )
    top_conflicts: List[FactFrequency] = Field(
        default_factory=list,
        description="Most frequently conflicting facts across claims",
    )
    results: List[ReconciliationClaimResult] = Field(
        default_factory=list, description="Per-claim results"
    )
