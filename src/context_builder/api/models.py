"""Pydantic models for the API layer."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ClaimSummary(BaseModel):
    """Summary of a claim for listing."""

    claim_id: str
    folder_name: str
    doc_count: int
    doc_types: List[str]
    extracted_count: int
    labeled_count: int
    # ClaimEval-style fields (kept for backwards compatibility)
    lob: str = "MOTOR"  # Line of business
    risk_score: int = 0  # 0-100
    loss_type: str = ""
    amount: Optional[float] = None
    currency: str = "USD"
    flags_count: int = 0
    status: str = "Not Reviewed"  # "Not Reviewed" or "Reviewed"
    closed_date: Optional[str] = None
    # Extraction-centric fields (run-dependent)
    gate_pass_count: int = 0
    gate_warn_count: int = 0
    gate_fail_count: int = 0
    last_processed: Optional[str] = None
    # Run context
    in_run: bool = True  # False if claim has no docs in the selected run


class DocSummary(BaseModel):
    """Summary of a document for listing."""

    doc_id: str
    filename: str
    doc_type: str
    language: str
    has_extraction: bool
    has_labels: bool
    quality_status: Optional[str] = None
    confidence: float = 0.0
    # Extraction-centric fields
    missing_required_fields: List[str] = []
    # Display fields
    source_type: str = "unknown"  # "pdf", "image", or "text"
    page_count: int = 0


class DocPayload(BaseModel):
    """Full document payload for review."""

    doc_id: str
    claim_id: str
    filename: str
    doc_type: str
    language: str
    pages: List[Dict[str, Any]]  # Page text content
    extraction: Optional[Dict[str, Any]] = None
    labels: Optional[Dict[str, Any]] = None
    # Source file info
    has_pdf: bool = False
    has_image: bool = False


class RunSummary(BaseModel):
    """Summary metrics for a run."""

    run_dir: str
    total_claims: int
    total_docs: int
    extracted_count: int
    labeled_count: int
    quality_gate: Dict[str, int]  # pass/warn/fail counts


class SaveLabelsRequest(BaseModel):
    """Request body for saving labels."""

    reviewer: str
    notes: str = ""
    field_labels: List[Dict[str, Any]]
    doc_labels: Dict[str, Any]


class DocReviewRequest(BaseModel):
    """Request body for simplified doc-level review."""

    claim_id: str
    doc_type_correct: bool = True
    notes: str = ""


class ClassificationLabelRequest(BaseModel):
    """Request body for saving classification review."""

    claim_id: str
    doc_type_correct: bool = True
    doc_type_truth: Optional[str] = None  # Required if doc_type_correct=False
    notes: str = ""


class GateCounts(BaseModel):
    """Gate status counts."""

    pass_count: int = 0  # renamed from 'pass' to avoid Python keyword
    warn: int = 0
    fail: int = 0


class RunMetadata(BaseModel):
    """Run metadata."""

    run_id: str
    model: str = ""


class ClaimReviewPayload(BaseModel):
    """Payload for claim-level review."""

    claim_id: str
    folder_name: str
    lob: str = "MOTOR"
    doc_count: int
    unlabeled_count: int
    gate_counts: Dict[str, int]  # {"pass": N, "warn": N, "fail": N}
    run_metadata: Optional[Dict[str, str]] = None
    prev_claim_id: Optional[str] = None
    next_claim_id: Optional[str] = None
    docs: List[DocSummary]
    default_doc_id: Optional[str] = None


class FieldRule(BaseModel):
    """Field extraction rule."""

    normalize: str = "uppercase_trim"
    validation: str = "non_empty"
    hints: List[str] = []


class QualityGateRules(BaseModel):
    """Quality gate rules."""

    pass_if: List[str] = []
    warn_if: List[str] = []
    fail_if: List[str] = []


class TemplateSpec(BaseModel):
    """Extraction template specification."""

    doc_type: str
    version: str
    required_fields: List[str]
    optional_fields: List[str]
    field_rules: Dict[str, Dict[str, Any]]
    quality_gate: Dict[str, List[str]]
