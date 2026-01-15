"""Decision record schema for compliance audit trail.

This module defines the core schemas for tamper-evident decision logging,
supporting classification, extraction, quality gate, human review, and override decisions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    """Types of decisions that can be recorded."""

    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    QUALITY_GATE = "quality_gate"
    HUMAN_REVIEW = "human_review"
    OVERRIDE = "override"


class VersionBundle(BaseModel):
    """Captures all version information at decision time.

    This enables exact reproducibility by recording the versions of all
    components involved in making a decision.
    """

    bundle_id: str = Field(..., description="Unique identifier for this version bundle")
    created_at: str = Field(..., description="ISO timestamp when bundle was created")
    git_commit: Optional[str] = Field(None, description="Git commit SHA if available")
    git_dirty: Optional[bool] = Field(None, description="Whether working tree had uncommitted changes")
    contextbuilder_version: str = Field(default="1.0.0", description="ContextBuilder version")
    extractor_version: str = Field(default="v1.0.0", description="Extractor version")
    model_name: str = Field(..., description="LLM model used (e.g., gpt-4o)")
    model_version: Optional[str] = Field(None, description="Specific model version/date if known")
    prompt_template_hash: Optional[str] = Field(None, description="Hash of prompt template used")
    extraction_spec_hash: Optional[str] = Field(None, description="Hash of extraction specs")


class EvidenceCitation(BaseModel):
    """Link to source document/field supporting a decision.

    Provides provenance for decisions by citing the exact source material.
    """

    doc_id: str = Field(..., description="Document identifier")
    page: Optional[int] = Field(None, description="Page number (1-indexed)")
    char_start: Optional[int] = Field(None, description="Character offset start")
    char_end: Optional[int] = Field(None, description="Character offset end")
    text_quote: Optional[str] = Field(None, description="Quoted text from source")
    field_name: Optional[str] = Field(None, description="Field name if citing a field")


class RuleTrace(BaseModel):
    """Trace of a rule/heuristic applied during decision-making."""

    rule_name: str = Field(..., description="Name/identifier of the rule")
    rule_version: Optional[str] = Field(None, description="Version of the rule")
    input_values: Dict[str, Any] = Field(default_factory=dict, description="Input values to the rule")
    output_value: Any = Field(None, description="Output/result of the rule")
    triggered: bool = Field(default=True, description="Whether the rule was triggered")


class DecisionRationale(BaseModel):
    """Explanation and evidence for a decision.

    Contains rule traces, evidence citations, and free-form notes
    that explain why a decision was made.
    """

    summary: str = Field(..., description="Human-readable summary of the rationale")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    rule_traces: List[RuleTrace] = Field(default_factory=list, description="Rules applied")
    evidence_citations: List[EvidenceCitation] = Field(
        default_factory=list, description="Source citations"
    )
    llm_call_ids: List[str] = Field(default_factory=list, description="IDs of LLM calls that produced this decision")
    notes: Optional[str] = Field(None, description="Additional notes or context")


class PIIReference(BaseModel):
    """Reference to PII stored in a separate vault (future use).

    This structure allows PII to be stored separately from the audit log
    while maintaining referential integrity.
    """

    ref_id: str = Field(..., description="Reference ID in PII vault")
    field_path: str = Field(..., description="JSON path to the redacted field")
    pii_type: str = Field(..., description="Type of PII (e.g., 'name', 'ssn', 'email')")


class DecisionOutcome(BaseModel):
    """The outcome/result of a decision.

    Stores the actual values produced by the decision in a structured way.
    """

    # Classification outcomes
    doc_type: Optional[str] = Field(None, description="Classified document type")
    doc_type_confidence: Optional[float] = Field(None, description="Classification confidence")
    language: Optional[str] = Field(None, description="Detected language")

    # Extraction outcomes
    fields_extracted: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of extracted fields with values"
    )
    quality_gate_status: Optional[str] = Field(
        None, description="Quality gate result: pass/warn/fail"
    )
    missing_required_fields: Optional[List[str]] = Field(
        None, description="Required fields that were not extracted"
    )

    # Human review outcomes
    field_corrections: Optional[List[Dict[str, Any]]] = Field(
        None, description="Fields corrected by human reviewer"
    )
    doc_type_correction: Optional[str] = Field(
        None, description="Corrected document type if overridden"
    )

    # Override outcomes
    original_value: Optional[Any] = Field(None, description="Original value before override")
    override_value: Optional[Any] = Field(None, description="New value after override")
    override_reason: Optional[str] = Field(None, description="Reason for the override")


class DecisionRecord(BaseModel):
    """Main decision record with hash chain for tamper evidence.

    This is the core schema for the compliance audit trail. Each decision
    is recorded with full context, rationale, and cryptographic linking
    to previous decisions for tamper detection.
    """

    # Identity
    decision_id: str = Field(..., description="Unique identifier for this decision")
    decision_type: DecisionType = Field(..., description="Type of decision")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO timestamp when decision was made",
    )

    # Hash chain for tamper evidence
    record_hash: Optional[str] = Field(
        None, description="SHA-256 hash of this record (computed after creation)"
    )
    previous_hash: str = Field(
        default="GENESIS", description="Hash of the previous record in the chain"
    )

    # Context
    claim_id: Optional[str] = Field(None, description="Associated claim identifier")
    doc_id: Optional[str] = Field(None, description="Associated document identifier")
    run_id: Optional[str] = Field(None, description="Pipeline run identifier")
    version_bundle_id: Optional[str] = Field(
        None, description="Reference to version bundle snapshot"
    )

    # Decision details
    rationale: DecisionRationale = Field(..., description="Explanation and evidence")
    outcome: DecisionOutcome = Field(..., description="Result of the decision")

    # Actor information
    actor_type: str = Field(
        default="system", description="Type of actor: 'system' or 'human'"
    )
    actor_id: Optional[str] = Field(
        None, description="Identifier for the actor (user ID or system component)"
    )

    # PII handling (future use)
    pii_refs: Optional[List[PIIReference]] = Field(
        None, description="References to PII stored in vault"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        """Pydantic config."""

        use_enum_values = True


class DecisionQuery(BaseModel):
    """Query parameters for searching decisions."""

    decision_type: Optional[DecisionType] = Field(None, description="Filter by type")
    claim_id: Optional[str] = Field(None, description="Filter by claim")
    doc_id: Optional[str] = Field(None, description="Filter by document")
    run_id: Optional[str] = Field(None, description="Filter by run")
    actor_id: Optional[str] = Field(None, description="Filter by actor")
    since: Optional[str] = Field(None, description="ISO timestamp to filter after")
    until: Optional[str] = Field(None, description="ISO timestamp to filter before")
    limit: int = Field(default=100, ge=1, le=1000, description="Max results")
    offset: int = Field(default=0, ge=0, description="Results offset")


class IntegrityReport(BaseModel):
    """Report from verifying hash chain integrity."""

    valid: bool = Field(..., description="Whether the chain is valid")
    total_records: int = Field(..., description="Total records checked")
    break_at_index: Optional[int] = Field(
        None, description="Index where chain breaks (if invalid)"
    )
    break_at_decision_id: Optional[str] = Field(
        None, description="Decision ID where chain breaks"
    )
    error_type: Optional[str] = Field(
        None, description="Type of error: 'hash_mismatch', 'missing_record', etc."
    )
    error_details: Optional[str] = Field(None, description="Detailed error message")
    verified_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="When verification was performed",
    )
