"""Pydantic schemas for human labels on extraction results.

Schema version: label_v3
- Truth Registry model with LABELED/UNVERIFIABLE/UNLABELED states
- Simplified DocLabels (only doc_type_correct)
"""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


# Field label states
FieldState = Literal["LABELED", "UNVERIFIABLE", "UNLABELED"]

# Reasons why a field cannot be verified
UnverifiableReason = Literal[
    "not_present_in_doc",  # Field doesn't exist in this doc type
    "unreadable_text",     # OCR/extraction quality too poor
    "wrong_doc_type",      # Doc was misclassified
    "cannot_verify",       # Catch-all
    "other"                # Free-text explanation in notes
]


class FieldLabel(BaseModel):
    """
    Truth label for a single extracted field.

    States:
    - LABELED: Truth value is known and stored in truth_value
    - UNVERIFIABLE: Truth cannot be established (reason required)
    - UNLABELED: No decision yet (default state)
    """

    model_config = ConfigDict(extra="forbid")

    field_name: str = Field(..., description="Name of the field being labeled")
    state: FieldState = Field(
        default="UNLABELED",
        description="Label state: LABELED, UNVERIFIABLE, or UNLABELED"
    )
    truth_value: Optional[str] = Field(
        None, description="Truth value (required when state=LABELED)"
    )
    unverifiable_reason: Optional[UnverifiableReason] = Field(
        None, description="Reason field is unverifiable (required when state=UNVERIFIABLE)"
    )
    notes: str = Field(default="", description="Optional reviewer notes")
    updated_at: Optional[datetime] = Field(
        None, description="When this field label was last updated"
    )

    @model_validator(mode="after")
    def validate_state_requirements(self):
        """Ensure required fields are present based on state."""
        if self.state == "LABELED" and self.truth_value is None:
            raise ValueError("truth_value is required when state=LABELED")
        if self.state == "UNVERIFIABLE" and self.unverifiable_reason is None:
            raise ValueError("unverifiable_reason is required when state=UNVERIFIABLE")
        return self


class DocLabels(BaseModel):
    """Document-level labels (simplified)."""

    model_config = ConfigDict(extra="forbid")

    doc_type_correct: bool = Field(
        default=True, description="Whether the classified document type is correct"
    )
    doc_type_truth: Optional[str] = Field(
        default=None,
        description="Corrected doc type when doc_type_correct=False; None means use predicted"
    )


class ReviewMetadata(BaseModel):
    """Metadata about the labeling session."""

    model_config = ConfigDict(extra="forbid")

    reviewed_at: datetime = Field(..., description="Timestamp of review")
    reviewer: str = Field(default="", description="Reviewer identifier")
    notes: str = Field(default="", description="Overall review notes")


class LabelResult(BaseModel):
    """
    Complete label result for a document.

    This is the schema written to docs/{doc_id}/labels/latest.json files.
    Truth labels are stored per-document, independent of extraction runs.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["label_v3"] = Field(
        default="label_v3", description="Schema version for compatibility"
    )
    doc_id: str = Field(..., description="Document identifier")
    claim_id: str = Field(..., description="Parent claim identifier")
    review: ReviewMetadata = Field(..., description="Review session metadata")
    field_labels: List[FieldLabel] = Field(
        default_factory=list, description="Per-field ground truth labels"
    )
    doc_labels: DocLabels = Field(
        default_factory=DocLabels, description="Document-level labels"
    )
