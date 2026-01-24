"""Pydantic schemas for aggregated claim facts output."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FactProvenance(BaseModel):
    """Provenance information for the selected fact value."""

    doc_id: str = Field(..., description="Document ID where this value was extracted")
    doc_type: str = Field(..., description="Document type (e.g., insurance_policy)")
    run_id: str = Field(..., description="Run ID that produced this extraction")
    page: Optional[int] = Field(None, description="Page number where value was found")
    text_quote: Optional[str] = Field(
        None, description="Text snippet containing the value"
    )
    char_start: Optional[int] = Field(None, description="Character start offset")
    char_end: Optional[int] = Field(None, description="Character end offset")


class AggregatedFact(BaseModel):
    """A single aggregated fact with its selected value."""

    name: str = Field(..., description="Field name (e.g., policy_number)")
    value: Optional[str] = Field(None, description="Selected value (highest confidence)")
    normalized_value: Optional[str] = Field(
        None, description="Normalized form of the selected value"
    )
    confidence: float = Field(..., description="Confidence score of selected value")
    selected_from: FactProvenance = Field(
        ..., description="Provenance of the selected value"
    )


class SourceDocument(BaseModel):
    """Reference to a source document used in aggregation."""

    doc_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    doc_type: str = Field(..., description="Classified document type")


class ClaimFacts(BaseModel):
    """Aggregated facts for a claim, selected from multiple documents."""

    schema_version: str = Field(
        default="claim_facts_v1", description="Schema version identifier"
    )
    claim_id: str = Field(..., description="Claim identifier")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When aggregation was performed"
    )
    run_id: str = Field(..., description="Run ID used for aggregation")
    run_policy: str = Field(
        default="latest_complete",
        description="Policy used to select run (latest_complete)",
    )
    facts: List[AggregatedFact] = Field(
        default_factory=list, description="Aggregated facts from all documents"
    )
    sources: List[SourceDocument] = Field(
        default_factory=list, description="Source documents used in aggregation"
    )
