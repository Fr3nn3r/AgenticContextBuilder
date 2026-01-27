"""Pydantic schemas for claim-level run tracking."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ClaimRunManifest(BaseModel):
    """Manifest tracking a claim-level processing run.

    A claim run aggregates multiple extraction runs and tracks all processing
    stages applied to a claim (aggregation, reconciliation, enrichment, etc.).
    """

    schema_version: str = Field(
        default="claim_run_v1", description="Schema version identifier"
    )
    claim_run_id: str = Field(..., description="Unique identifier for this claim run")
    claim_id: str = Field(..., description="Claim identifier")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the claim run was created"
    )
    extraction_runs_considered: List[str] = Field(
        default_factory=list,
        description="Extraction run IDs considered for this claim run",
    )
    contextbuilder_version: str = Field(
        ..., description="ContextBuilder version that created this run"
    )
    stages_completed: List[str] = Field(
        default_factory=list,
        description="Pipeline stages completed (e.g., aggregate, reconcile, enrich)",
    )
    previous_claim_run_id: Optional[str] = Field(
        None, description="Previous claim run ID if this is a re-run"
    )
