"""Pydantic models for the API layer."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


# =============================================================================
# DASHBOARD MODELS
# =============================================================================


class DashboardClaimDoc(BaseModel):
    """Document summary for the dashboard."""

    doc_id: str
    filename: str
    doc_type: str
    extraction_run_id: Optional[str] = None


class DashboardClaim(BaseModel):
    """Enriched claim data for the claims dashboard."""

    claim_id: str
    folder_name: str
    claim_date: Optional[str] = None
    doc_count: int = 0

    # Assessment (latest)
    decision: Optional[str] = None
    confidence: Optional[float] = None
    result_code: Optional[str] = None
    inconclusive_warnings: List[str] = Field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    checks_inconclusive: int = 0
    payout: Optional[float] = None
    currency: str = "CHF"
    assessment_method: Optional[str] = None
    claim_run_id: Optional[str] = None

    # Ground truth
    gt_decision: Optional[str] = None
    gt_payout: Optional[float] = None
    gt_denial_reason: Optional[str] = None
    gt_vehicle: Optional[str] = None
    gt_coverage_notes: Optional[str] = None
    decision_match: Optional[bool] = None
    payout_diff: Optional[float] = None
    has_ground_truth_doc: bool = False

    # Dataset
    dataset_id: Optional[str] = None
    dataset_label: Optional[str] = None

    # Documents
    documents: List[DashboardClaimDoc] = Field(default_factory=list)


class DashboardClaimDetail(BaseModel):
    """Expanded detail data for a single claim."""

    claim_id: str
    # Coverage analysis
    coverage_items: List[Dict[str, Any]] = Field(default_factory=list)
    coverage_summary: Optional[Dict[str, Any]] = None
    # Assessment payout breakdown
    payout_calculation: Optional[Dict[str, Any]] = None
    # Ground truth breakdown
    gt_parts_approved: Optional[float] = None
    gt_labor_approved: Optional[float] = None
    gt_total_material_labor: Optional[float] = None
    gt_vat_rate_pct: Optional[float] = None
    gt_deductible: Optional[float] = None
    gt_total_approved: Optional[float] = None
    gt_reimbursement_rate_pct: Optional[float] = None
    # Screening checks
    screening_checks: List[Dict[str, Any]] = Field(default_factory=list)
    # Assessment checks
    assessment_checks: List[Dict[str, Any]] = Field(default_factory=list)
    # Parts/labor breakdown (computed at read time)
    sys_parts_gross: Optional[float] = None
    sys_labor_gross: Optional[float] = None
    sys_parts_adjusted: Optional[float] = None
    sys_labor_adjusted: Optional[float] = None
    sys_total_adjusted: Optional[float] = None
    sys_vat_rate_pct: Optional[float] = None
    sys_vat_amount: Optional[float] = None
    gt_vat_amount: Optional[float] = None
    screening_payout: Optional[Dict[str, Any]] = None
