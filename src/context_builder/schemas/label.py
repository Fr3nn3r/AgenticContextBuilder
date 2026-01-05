"""Pydantic schemas for human labels on extraction results."""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class FieldLabel(BaseModel):
    """Human label for a single extracted field."""

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(..., description="Name of the field being labeled")
    judgement: Literal["correct", "incorrect", "unknown"] = Field(
        ..., description="Human assessment of extraction correctness"
    )
    correct_value: Optional[str] = Field(
        None, description="Correct value if judgement is 'incorrect'"
    )
    notes: str = Field(default="", description="Optional reviewer notes")


class DocLabels(BaseModel):
    """Document-level labels."""

    model_config = ConfigDict(extra="forbid")

    doc_type_correct: bool = Field(
        ..., description="Whether the classified document type is correct"
    )
    text_readable: Literal["good", "warn", "poor"] = Field(
        ..., description="Quality of extracted text"
    )


class ReviewMetadata(BaseModel):
    """Metadata about the labeling session."""

    model_config = ConfigDict(extra="forbid")

    reviewed_at: datetime = Field(..., description="Timestamp of review")
    reviewer: str = Field(..., description="Reviewer identifier")
    notes: str = Field(default="", description="Overall review notes")


class LabelResult(BaseModel):
    """
    Complete label result for a document.

    This is the schema written to *.labels.json files.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["label_v1"] = Field(
        default="label_v1", description="Schema version for compatibility"
    )
    doc_id: str = Field(..., description="Document identifier")
    claim_id: str = Field(..., description="Parent claim identifier")
    review: ReviewMetadata = Field(..., description="Review session metadata")
    field_labels: List[FieldLabel] = Field(..., description="Per-field labels")
    doc_labels: DocLabels = Field(..., description="Document-level labels")
