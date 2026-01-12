"""
FastAPI backend for Extraction QA Console.

Provides endpoints for:
- Listing claims and documents
- Getting document content with extraction results
- Saving human labels
- Re-running extraction
- Run metrics dashboard

File-based storage (no database).

Data structure expected:
  output/claims/{claim_id}/
    docs/{doc_id}/
      meta/doc.json
      text/pages.json
    runs/{run_id}/
      extraction/{doc_id}.json
      logs/summary.json
      labels/{doc_id}.labels.json
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


# =============================================================================
# API MODELS
# =============================================================================

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
    validate: str = "non_empty"
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
# HELPER FUNCTIONS
# =============================================================================

def parse_loss_type_from_folder(folder_name: str) -> str:
    """Extract loss type from claim folder name."""
    folder_upper = folder_name.upper()
    if "ROBO_TOTAL" in folder_upper or "ROBO TOTAL" in folder_upper:
        return "Theft - Total Loss"
    elif "ROBO_PARCIAL" in folder_upper:
        return "Theft - Partial"
    elif "COLISION" in folder_upper or "COLLISION" in folder_upper:
        return "Collision"
    elif "INCENDIO" in folder_upper:
        return "Fire"
    elif "VANDALISMO" in folder_upper:
        return "Vandalism"
    return "Other"


def extract_claim_number(folder_name: str) -> str:
    """Extract claim number from folder name (e.g., '24-01-VH-7054124')."""
    # Look for pattern like XX-XX-VH-XXXXXXX
    match = re.search(r'(\d{2}-\d{2}-VH-\d+)', folder_name)
    if match:
        return match.group(1)
    return folder_name


def get_latest_run_dir_for_claim(claim_dir: Path) -> Optional[Path]:
    """Get the most recent run directory for a claim."""
    runs_dir = claim_dir / "runs"
    if not runs_dir.exists():
        return None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir() and d.name.startswith("run_")],
        reverse=True
    )
    return run_dirs[0] if run_dirs else None


def get_run_dir_by_id(claim_dir: Path, run_id: str) -> Optional[Path]:
    """Get a specific run directory by ID for a claim."""
    runs_dir = claim_dir / "runs"
    if not runs_dir.exists():
        return None

    run_dir = runs_dir / run_id
    if run_dir.exists() and run_dir.is_dir():
        return run_dir
    return None


def get_global_runs_dir() -> Path:
    """Get the global runs directory (output/runs/)."""
    # DATA_DIR is output/claims, so parent is output/
    return DATA_DIR.parent / "runs"


def get_all_run_ids() -> List[str]:
    """Get all run IDs from the global runs directory, sorted newest first.

    Uses Storage abstraction with index support for fast lookups.
    Falls back to filesystem scan if indexes unavailable.
    """
    storage = get_storage()
    runs = storage.list_runs()
    # Already sorted by run_id (newest first) from storage
    return [r.run_id for r in runs]


def calculate_risk_score(extraction_data: Dict[str, Any]) -> int:
    """Calculate risk score based on extraction quality and completeness."""
    if not extraction_data:
        return 50  # Default medium risk for missing extractions

    quality = extraction_data.get("quality_gate", {})
    status = quality.get("status", "warn")

    # Base score by status
    if status == "pass":
        base = 20
    elif status == "warn":
        base = 45
    else:  # fail
        base = 70

    # Adjust by missing fields
    missing = len(quality.get("missing_required_fields", []))
    base += missing * 5

    # Adjust by reasons count
    reasons = len(quality.get("reasons", []))
    base += reasons * 3

    return min(100, max(0, base))


def extract_amount_from_extraction(extraction_data: Dict[str, Any]) -> Optional[float]:
    """Extract monetary amount from extraction fields."""
    if not extraction_data:
        return None

    fields = extraction_data.get("fields", [])
    # Look for value-related fields
    amount_fields = ["valor_asegurado", "valor_item", "sum_insured", "amount", "value"]

    for field in fields:
        name = field.get("name", "").lower()
        if any(af in name for af in amount_fields):
            value = field.get("normalized_value") or field.get("value")
            if value:
                # Try to parse as number
                try:
                    # Remove currency symbols and commas
                    cleaned = re.sub(r'[^\d.]', '', str(value))
                    return float(cleaned)
                except (ValueError, TypeError):
                    pass
    return None


# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="Extraction QA Console API",
    description="Backend for reviewing and labeling document extractions",
    version="1.0.0",
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory - now points to output/claims with new structure
# Compute path relative to project root (3 levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR: Path = _PROJECT_ROOT / "output" / "claims"

# Storage abstraction layer (uses indexes when available)
from context_builder.storage import FileStorage


def get_storage() -> FileStorage:
    """Get Storage instance (fresh for each request to see new runs)."""
    return FileStorage(DATA_DIR)


def set_data_dir(path: Path):
    """Set the data directory for the API."""
    global DATA_DIR
    DATA_DIR = path


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/api/claims", response_model=List[ClaimSummary])
def list_claims(run_id: Optional[str] = Query(None, description="Filter by run ID")):
    """
    List all claims in the data directory.

    Args:
        run_id: Optional run ID to filter extraction metrics. If not provided, uses latest run.

    Uses new folder structure:
      {claim_id}/docs/{doc_id}/meta/doc.json
      {claim_id}/runs/{run_id}/extraction/{doc_id}.json
    """
    if not DATA_DIR.exists():
        raise HTTPException(status_code=404, detail=f"Data directory not found: {DATA_DIR}")

    claims = []
    for claim_dir in DATA_DIR.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        docs_dir = claim_dir / "docs"
        if not docs_dir.exists():
            continue

        # Read all document metadata
        doc_metas = []
        doc_ids = []
        for doc_folder in docs_dir.iterdir():
            if not doc_folder.is_dir():
                continue
            meta_path = doc_folder / "meta" / "doc.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    doc_metas.append(meta)
                    doc_ids.append(doc_folder.name)

        if not doc_metas:
            continue

        doc_types = list(set(m.get("doc_type", "unknown") for m in doc_metas))

        # Get run directory (specific or latest)
        if run_id:
            run_dir = get_run_dir_by_id(claim_dir, run_id)
        else:
            run_dir = get_latest_run_dir_for_claim(claim_dir)

        # Count extractions and gather data
        extracted_count = 0
        labeled_count = 0
        total_risk_score = 0
        total_amount = 0.0
        flags_count = 0
        closed_date = None
        last_processed = None
        # Extraction-centric counters
        gate_pass_count = 0
        gate_warn_count = 0
        gate_fail_count = 0

        if run_dir:
            extraction_dir = run_dir / "extraction"

            # Read run summary for date
            summary_path = run_dir / "logs" / "summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
                    completed = summary.get("completed_at", "")
                    if completed:
                        # Format as "5 Jan 2026"
                        try:
                            dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                            closed_date = dt.strftime("%d %b %Y")
                            last_processed = dt.strftime("%Y-%m-%d %H:%M")
                        except Exception:
                            pass

            # Count extractions and calculate metrics
            if extraction_dir.exists():
                for ext_file in extraction_dir.glob("*.json"):
                    extracted_count += 1
                    with open(ext_file, "r", encoding="utf-8") as f:
                        ext_data = json.load(f)
                        total_risk_score += calculate_risk_score(ext_data)

                        # Count quality gate statuses
                        quality = ext_data.get("quality_gate", {})
                        status = quality.get("status", "unknown")
                        if status == "pass":
                            gate_pass_count += 1
                        elif status == "warn":
                            gate_warn_count += 1
                            flags_count += 1
                        elif status == "fail":
                            gate_fail_count += 1
                            flags_count += 2

                        flags_count += len(quality.get("missing_required_fields", []))

                        # Extract amount
                        amount = extract_amount_from_extraction(ext_data)
                        if amount:
                            total_amount = max(total_amount, amount)

        # Count labels
        for doc_folder in docs_dir.iterdir():
            if doc_folder.is_dir():
                labels_path = doc_folder / "labels" / "latest.json"
                if labels_path.exists():
                    labeled_count += 1

        # Calculate average risk score
        avg_risk = total_risk_score // max(extracted_count, 1)

        # Determine review status
        status = "Reviewed" if labeled_count > 0 else "Not Reviewed"

        # Extract claim number for display
        claim_number = extract_claim_number(claim_dir.name)

        # Determine if claim has extractions in the selected run
        in_run = run_dir is not None and extracted_count > 0

        claims.append(ClaimSummary(
            claim_id=claim_number,
            folder_name=claim_dir.name,
            doc_count=len(doc_metas),
            doc_types=doc_types,
            extracted_count=extracted_count,
            labeled_count=labeled_count,
            lob="MOTOR",  # All claims in sample are vehicle claims
            risk_score=avg_risk,
            loss_type=parse_loss_type_from_folder(claim_dir.name),
            amount=total_amount if total_amount > 0 else None,
            currency="USD",
            flags_count=flags_count,
            status=status,
            closed_date=closed_date,
            # Extraction-centric fields (run-dependent)
            gate_pass_count=gate_pass_count,
            gate_warn_count=gate_warn_count,
            gate_fail_count=gate_fail_count,
            last_processed=last_processed,
            # Run context
            in_run=in_run,
        ))

    # Sort by risk score descending
    return sorted(claims, key=lambda c: c.risk_score, reverse=True)


@app.get("/api/claims/runs")
def list_claim_runs():
    """
    List all available run IDs for the claims view.

    Returns list of run IDs sorted newest first, with metadata.
    Reads from global runs directory (output/runs/) when available.
    """
    run_ids = get_all_run_ids()
    runs = []
    global_runs_dir = get_global_runs_dir()

    for r_id in run_ids:
        metadata = {"run_id": r_id, "timestamp": None, "model": None}

        # First, try global runs directory (new structure)
        global_run_dir = global_runs_dir / r_id
        if global_run_dir.exists():
            # Read from global summary.json
            summary_path = global_run_dir / "summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
                    metadata["timestamp"] = summary.get("completed_at")

            # Read model from manifest.json
            manifest_path = global_run_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    metadata["model"] = manifest.get("model")
                    metadata["claims_count"] = manifest.get("claims_count", 0)
        else:
            # Fallback: get metadata from first claim that has this run
            for claim_dir in DATA_DIR.iterdir():
                if not claim_dir.is_dir() or claim_dir.name.startswith("."):
                    continue
                run_dir = claim_dir / "runs" / r_id
                if run_dir.exists():
                    summary_path = run_dir / "logs" / "summary.json"
                    if summary_path.exists():
                        with open(summary_path, "r", encoding="utf-8") as f:
                            summary = json.load(f)
                            metadata["timestamp"] = summary.get("completed_at")
                            metadata["model"] = summary.get("model")
                        break

        runs.append(metadata)

    return runs


@app.get("/api/claims/{claim_id}/docs", response_model=List[DocSummary])
def list_docs(claim_id: str, run_id: Optional[str] = Query(None, description="Filter by run ID")):
    """
    List documents for a specific claim.

    Args:
        claim_id: Can be either the full folder name or extracted claim number.
        run_id: Optional run ID for extraction metrics. If not provided, uses latest run.
    """
    # Find claim directory (could be folder_name or claim_id)
    claim_dir = None
    for d in DATA_DIR.iterdir():
        if d.is_dir():
            if d.name == claim_id or extract_claim_number(d.name) == claim_id:
                claim_dir = d
                break

    if not claim_dir or not claim_dir.exists():
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    docs_dir = claim_dir / "docs"
    if not docs_dir.exists():
        raise HTTPException(status_code=404, detail="No documents found")

    # Get run directory (specific or latest) for extraction data
    if run_id:
        run_dir = get_run_dir_by_id(claim_dir, run_id)
    else:
        run_dir = get_latest_run_dir_for_claim(claim_dir)
    extraction_dir = run_dir / "extraction" if run_dir else None
    # Note: labels are now stored at docs/{doc_id}/labels/latest.json (run-independent)

    docs = []
    for doc_folder in docs_dir.iterdir():
        if not doc_folder.is_dir():
            continue

        doc_id = doc_folder.name
        meta_path = doc_folder / "meta" / "doc.json"

        if not meta_path.exists():
            continue

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Check for extraction
        has_extraction = False
        quality_status = None
        confidence = 0.0
        missing_required_fields: List[str] = []

        if extraction_dir:
            extraction_path = extraction_dir / f"{doc_id}.json"
            has_extraction = extraction_path.exists()
            if has_extraction:
                with open(extraction_path, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    quality_gate = ext_data.get("quality_gate", {})
                    quality_status = quality_gate.get("status")
                    missing_required_fields = quality_gate.get("missing_required_fields", [])
                    # Calculate average field confidence
                    fields = ext_data.get("fields", [])
                    if fields:
                        confidence = sum(f.get("confidence", 0) for f in fields) / len(fields)

        # Check for labels (at docs/{doc_id}/labels/latest.json)
        labels_path = doc_folder / "labels" / "latest.json"
        has_labels = labels_path.exists()

        docs.append(DocSummary(
            doc_id=doc_id,
            filename=meta.get("original_filename", "Unknown"),
            doc_type=meta.get("doc_type", "unknown"),
            language=meta.get("language", "es"),
            has_extraction=has_extraction,
            has_labels=has_labels,
            quality_status=quality_status,
            confidence=round(confidence, 2),
            missing_required_fields=missing_required_fields,
        ))

    return docs


@app.get("/api/docs/{doc_id}", response_model=DocPayload)
def get_doc(doc_id: str, claim_id: Optional[str] = Query(None), run_id: Optional[str] = Query(None)):
    """
    Get full document payload for review.

    Args:
        doc_id: The document ID (folder name under docs/)
        claim_id: Optional claim ID to help locate the document
        run_id: Optional run ID for extraction data (uses latest if not provided)

    Returns:
    - Document metadata
    - Page text content (from pages.json)
    - Extraction results (if available)
    - Labels (if available)
    """
    storage = get_storage()

    # Get document bundle (uses index for O(1) lookup)
    doc_bundle = storage.get_doc(doc_id)
    if not doc_bundle:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    meta = doc_bundle.metadata
    filename = meta.get("original_filename", "Unknown")
    doc_type = meta.get("doc_type", "unknown")
    language = meta.get("language", "es")
    resolved_claim_id = doc_bundle.claim_id or extract_claim_number(doc_bundle.claim_folder)

    # Load pages
    doc_text = storage.get_doc_text(doc_id)
    pages = doc_text.pages if doc_text else []

    # Get extraction for specific run only (run_id is required for extraction lookup)
    extraction = None
    if run_id:
        extraction = storage.get_extraction(run_id, doc_id, claim_id=resolved_claim_id)

    # Load labels (uses index for fast lookup if available)
    labels = storage.get_label(doc_id)

    # Check for source files
    has_pdf = False
    has_image = False
    source_dir = doc_bundle.doc_root / "source"
    if source_dir.exists():
        for source_file in source_dir.iterdir():
            ext = source_file.suffix.lower()
            if ext == ".pdf":
                has_pdf = True
            elif ext in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp"}:
                has_image = True

    return DocPayload(
        doc_id=doc_id,
        claim_id=resolved_claim_id,
        filename=filename,
        doc_type=doc_type,
        language=language,
        pages=pages,
        extraction=extraction,
        labels=labels,
        has_pdf=has_pdf,
        has_image=has_image,
    )


@app.post("/api/docs/{doc_id}/labels")
def save_labels(doc_id: str, request: SaveLabelsRequest, claim_id: Optional[str] = Query(None)):
    """
    Save human labels for a document.

    Uses Storage abstraction for atomic write (temp file + rename).
    Labels are stored at docs/{doc_id}/labels/latest.json (run-independent).
    """
    storage = get_storage()

    # Verify document exists and get claim_id
    doc_bundle = storage.get_doc(doc_id)
    if not doc_bundle:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    resolved_claim_id = doc_bundle.claim_id or extract_claim_number(doc_bundle.claim_folder)

    # Build label result (label_v3 schema)
    label_data = {
        "schema_version": "label_v3",
        "doc_id": doc_id,
        "claim_id": resolved_claim_id,
        "review": {
            "reviewed_at": datetime.utcnow().isoformat() + "Z",
            "reviewer": request.reviewer,
            "notes": request.notes,
        },
        "field_labels": request.field_labels,
        "doc_labels": request.doc_labels,
    }

    # Save using Storage's atomic write
    try:
        storage.save_label(doc_id, label_data)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save labels: {e}")

    return {"status": "saved", "doc_id": doc_id}


@app.post("/api/docs/{doc_id}/extract")
def trigger_extraction(doc_id: str):
    """
    Re-run extraction for a document.

    This triggers the extraction pipeline for a single document.
    """
    # TODO: Implement single-doc extraction
    return {
        "status": "not_implemented",
        "message": "Use pipeline/run.py to re-run extraction",
    }


@app.get("/api/runs/latest", response_model=RunSummary)
def get_run_summary():
    """Get metrics summary across all claims."""
    if not DATA_DIR.exists():
        raise HTTPException(status_code=404, detail="Data directory not found")

    total_claims = 0
    total_docs = 0
    extracted_count = 0
    labeled_count = 0
    quality_gate = {"pass": 0, "warn": 0, "fail": 0}

    for claim_dir in DATA_DIR.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        docs_dir = claim_dir / "docs"
        if not docs_dir.exists():
            continue

        total_claims += 1

        # Count docs
        doc_folders = [d for d in docs_dir.iterdir() if d.is_dir()]
        total_docs += len(doc_folders)

        # Get latest run
        run_dir = get_latest_run_dir_for_claim(claim_dir)
        if not run_dir:
            continue

        # Count extractions and quality gate
        extraction_dir = run_dir / "extraction"
        if extraction_dir.exists():
            for ext_file in extraction_dir.glob("*.json"):
                extracted_count += 1
                with open(ext_file, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    status = ext_data.get("quality_gate", {}).get("status", "unknown")
                    if status in quality_gate:
                        quality_gate[status] += 1

        # Count labels
        labels_dir = run_dir / "labels"
        if labels_dir.exists():
            labeled_count += len(list(labels_dir.glob("*.labels.json")))

    return RunSummary(
        run_dir=str(DATA_DIR),
        total_claims=total_claims,
        total_docs=total_docs,
        extracted_count=extracted_count,
        labeled_count=labeled_count,
        quality_gate=quality_gate,
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "data_dir": str(DATA_DIR)}


# =============================================================================
# NEW ENDPOINTS FOR CLAIM-LEVEL REVIEW
# =============================================================================

@app.get("/api/claims/{claim_id}/review", response_model=ClaimReviewPayload)
def get_claim_review(claim_id: str):
    """
    Get claim review payload for the claim-level review screen.

    Returns claim metadata, ordered doc list with status, and prev/next claim IDs
    for sequential navigation.
    """
    # Find claim directory
    claim_dir = None
    for d in DATA_DIR.iterdir():
        if d.is_dir():
            if d.name == claim_id or extract_claim_number(d.name) == claim_id:
                claim_dir = d
                break

    if not claim_dir or not claim_dir.exists():
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    # Get all claims sorted alphabetically for prev/next navigation
    all_claims = sorted([
        d.name for d in DATA_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "docs").exists()
    ])

    # Find prev/next claims
    current_idx = None
    for i, c in enumerate(all_claims):
        if c == claim_dir.name or extract_claim_number(c) == claim_id:
            current_idx = i
            break

    prev_claim_id = extract_claim_number(all_claims[current_idx - 1]) if current_idx and current_idx > 0 else None
    next_claim_id = extract_claim_number(all_claims[current_idx + 1]) if current_idx is not None and current_idx < len(all_claims) - 1 else None

    # Get docs for this claim (reuse list_docs logic)
    docs_dir = claim_dir / "docs"
    run_dir = get_latest_run_dir_for_claim(claim_dir)
    extraction_dir = run_dir / "extraction" if run_dir else None
    # Note: labels are now stored at docs/{doc_id}/labels/latest.json (run-independent)

    docs = []
    gate_counts = {"pass": 0, "warn": 0, "fail": 0}
    unlabeled_count = 0

    for doc_folder in docs_dir.iterdir():
        if not doc_folder.is_dir():
            continue

        doc_id = doc_folder.name
        meta_path = doc_folder / "meta" / "doc.json"

        if not meta_path.exists():
            continue

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Check for extraction
        has_extraction = False
        quality_status = None
        confidence = 0.0
        missing_required_fields: List[str] = []

        if extraction_dir:
            extraction_path = extraction_dir / f"{doc_id}.json"
            has_extraction = extraction_path.exists()
            if has_extraction:
                with open(extraction_path, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    quality_gate = ext_data.get("quality_gate", {})
                    quality_status = quality_gate.get("status")
                    missing_required_fields = quality_gate.get("missing_required_fields", [])
                    fields = ext_data.get("fields", [])
                    if fields:
                        confidence = sum(f.get("confidence", 0) for f in fields) / len(fields)
                    if quality_status == "pass":
                        gate_counts["pass"] += 1
                    elif quality_status == "warn":
                        gate_counts["warn"] += 1
                    elif quality_status == "fail":
                        gate_counts["fail"] += 1

        # Check for labels (at docs/{doc_id}/labels/latest.json)
        labels_path = doc_folder / "labels" / "latest.json"
        has_labels = labels_path.exists()

        if not has_labels:
            unlabeled_count += 1

        docs.append(DocSummary(
            doc_id=doc_id,
            filename=meta.get("original_filename", "Unknown"),
            doc_type=meta.get("doc_type", "unknown"),
            language=meta.get("language", "es"),
            has_extraction=has_extraction,
            has_labels=has_labels,
            quality_status=quality_status,
            confidence=round(confidence, 2),
            missing_required_fields=missing_required_fields,
        ))

    # Sort docs: unlabeled first, then by gate status (FAIL, WARN, PASS)
    status_order = {"fail": 0, "warn": 1, "pass": 2, None: 3}
    docs.sort(key=lambda d: (d.has_labels, status_order.get(d.quality_status, 3)))

    # Find default doc (first unlabeled, or first doc)
    default_doc_id = None
    for d in docs:
        if not d.has_labels:
            default_doc_id = d.doc_id
            break
    if not default_doc_id and docs:
        default_doc_id = docs[0].doc_id

    # Get run metadata
    run_metadata = None
    if run_dir:
        summary_path = run_dir / "logs" / "summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
                run_metadata = {
                    "run_id": run_dir.name,
                    "model": summary.get("model", ""),
                }

    return ClaimReviewPayload(
        claim_id=extract_claim_number(claim_dir.name),
        folder_name=claim_dir.name,
        lob="MOTOR",
        doc_count=len(docs),
        unlabeled_count=unlabeled_count,
        gate_counts=gate_counts,
        run_metadata=run_metadata,
        prev_claim_id=prev_claim_id,
        next_claim_id=next_claim_id,
        docs=docs,
        default_doc_id=default_doc_id,
    )


@app.post("/api/docs/{doc_id}/review")
def save_doc_review(doc_id: str, request: DocReviewRequest):
    """
    Save simplified doc-level review (no field labels, no reviewer name).

    Saves doc_type_correct and optional notes.
    Labels are stored at docs/{doc_id}/labels/latest.json (run-independent).
    """
    claim_id = request.claim_id

    # Find the document's folder
    doc_folder = None
    claim_dir = None
    for claim in DATA_DIR.iterdir():
        if not claim.is_dir():
            continue
        if extract_claim_number(claim.name) != claim_id and claim.name != claim_id:
            continue
        candidate = claim / "docs" / doc_id
        if candidate.exists():
            doc_folder = candidate
            claim_dir = claim
            break

    if not doc_folder:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    # Labels are stored at docs/{doc_id}/labels/latest.json
    labels_dir = doc_folder / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Build label result (label_v2 schema)
    label_data = {
        "schema_version": "label_v2",
        "doc_id": doc_id,
        "claim_id": extract_claim_number(claim_dir.name),
        "review": {
            "reviewed_at": datetime.utcnow().isoformat(),
            "reviewer": "",  # No reviewer name in simplified flow
            "notes": request.notes,
        },
        "field_labels": [],  # No field-level labels in simplified flow
        "doc_labels": {
            "doc_type_correct": request.doc_type_correct,
        },
    }

    # Atomic write
    labels_path = labels_dir / "latest.json"
    temp_path = labels_path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(label_data, f, indent=2, ensure_ascii=False)

    temp_path.replace(labels_path)

    return {"status": "saved"}


@app.get("/api/templates", response_model=List[TemplateSpec])
def get_templates():
    """
    Get all extraction templates from the spec_loader.

    Returns template specs for display in the Extraction Templates screen.
    """
    try:
        from context_builder.extraction.spec_loader import list_available_specs, get_spec
    except ImportError:
        # Fallback if spec_loader not available - return empty list
        return []

    templates = []
    available = list_available_specs()

    for doc_type in available:
        try:
            spec = get_spec(doc_type)
            templates.append(TemplateSpec(
                doc_type=spec.doc_type,
                version=spec.version,
                required_fields=spec.required_fields,
                optional_fields=spec.optional_fields,
                field_rules={
                    name: {
                        "normalize": rule.normalize,
                        "validate": rule.validate,
                        "hints": rule.hints,
                    }
                    for name, rule in spec.field_rules.items()
                },
                quality_gate={
                    "pass_if": spec.quality_gate.pass_if,
                    "warn_if": spec.quality_gate.warn_if,
                    "fail_if": spec.quality_gate.fail_if,
                },
            ))
        except Exception:
            # Skip specs that fail to load
            continue

    return templates


@app.get("/api/docs/{doc_id}/source")
def get_doc_source(doc_id: str, claim_id: Optional[str] = Query(None)):
    """
    Serve the original document source file (PDF/image).

    Returns the file from docs/{doc_id}/source/ with correct content-type.
    Uses Storage abstraction for O(1) document lookup.
    """
    storage = get_storage()

    # Get source path using Storage (uses index for fast lookup)
    source_file = storage.get_doc_source_path(doc_id)
    if not source_file:
        # Check if document exists at all
        doc = storage.get_doc(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
        raise HTTPException(status_code=404, detail="No source file available")

    # Determine media type based on extension
    ext_to_media = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }

    ext = source_file.suffix.lower()
    media_type = ext_to_media.get(ext, "application/octet-stream")

    return FileResponse(
        path=source_file,
        media_type=media_type,
        filename=source_file.name,
    )


@app.get("/api/docs/{doc_id}/azure-di")
def get_doc_azure_di(doc_id: str, claim_id: Optional[str] = Query(None)):
    """
    Get Azure DI raw output for bounding box highlighting.

    Returns the azure_di.json if available, containing word-level
    polygon coordinates for visual highlighting on PDF.
    Uses Storage abstraction for O(1) document lookup.
    """
    storage = get_storage()

    # Get document bundle (uses index for fast lookup)
    doc_bundle = storage.get_doc(doc_id)
    if not doc_bundle:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    # Look for azure_di.json
    azure_di_path = doc_bundle.doc_root / "text" / "raw" / "azure_di.json"
    if not azure_di_path.exists():
        raise HTTPException(status_code=404, detail="Azure DI data not available")

    with open(azure_di_path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# INSIGHTS ENDPOINTS
# =============================================================================

@app.get("/api/insights/overview")
def get_insights_overview():
    """
    Get overview KPIs for the Calibration Insights screen.

    Returns:
    - docs_total: Total docs (supported types)
    - docs_reviewed: Docs with labels
    - docs_doc_type_wrong: Docs where doc_type was labeled incorrect
    - docs_needs_vision: Docs flagged as needing vision
    - required_field_presence_rate: Avg presence rate for required fields
    - required_field_accuracy: Avg accuracy for required fields
    - evidence_rate: Avg evidence rate for extracted fields
    """
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR)
    return aggregator.get_overview()


@app.get("/api/insights/doc-types")
def get_insights_doc_types():
    """
    Get metrics per doc type for the scoreboard.

    Returns list of doc type metrics including:
    - docs_reviewed, docs_doc_type_wrong, docs_needs_vision
    - required_field_presence_pct, required_field_accuracy_pct
    - evidence_rate_pct, top_failing_field
    """
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR)
    return aggregator.get_doc_type_metrics()


@app.get("/api/insights/priorities")
def get_insights_priorities(limit: int = Query(10, ge=1, le=50)):
    """
    Get prioritized list of (doc_type, field) to improve.

    Returns ranked list with:
    - doc_type, field_name, is_required
    - affected_docs count
    - failure breakdown (extractor_miss, incorrect, etc.)
    - priority_score and fix_bucket recommendation
    """
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR)
    return aggregator.get_priorities(limit=limit)


@app.get("/api/insights/field-details")
def get_insights_field_details(
    doc_type: str = Query(..., description="Document type"),
    field: str = Query(..., alias="field", description="Field name"),
    run_id: Optional[str] = Query(None, description="Run ID to scope data to"),
):
    """
    Get detailed breakdown for a specific (doc_type, field).

    Returns:
    - total_docs, labeled_docs, with_prediction, with_evidence
    - breakdown: correct, incorrect, extractor_miss, etc.
    - rates: presence_pct, evidence_pct, accuracy_pct
    """
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR, run_id=run_id)
    return aggregator.get_field_details(doc_type, field)


@app.get("/api/insights/examples")
def get_insights_examples(
    doc_type: Optional[str] = Query(None, description="Filter by doc type"),
    field: Optional[str] = Query(None, description="Filter by field name"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    run_id: Optional[str] = Query(None, description="Run ID to scope data to"),
    limit: int = Query(30, ge=1, le=100),
):
    """
    Get example cases for drilldown.

    Filters:
    - doc_type: loss_notice, police_report, insurance_policy
    - field: specific field name
    - outcome: correct, incorrect, extractor_miss, cannot_verify, evidence_missing
    - run_id: scope examples to a specific run

    Returns list with claim_id, doc_id, values, judgement, and review_url.
    """
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR, run_id=run_id)
    return aggregator.get_examples(
        doc_type=doc_type,
        field_name=field,
        outcome=outcome,
        limit=limit,
    )


# =============================================================================
# RUN MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/insights/runs")
def get_insights_runs():
    """
    List all extraction runs with metadata and KPIs.

    Returns list of runs sorted by timestamp (newest first), each with:
    - run_id, timestamp, model, extractor_version, prompt_version
    - claims_count, docs_count, extracted_count, labeled_count
    - presence_rate, accuracy_rate, evidence_rate
    """
    from context_builder.api.insights import list_all_runs

    return list_all_runs(DATA_DIR)


@app.get("/api/insights/runs/detailed")
def get_insights_runs_detailed():
    """
    List all extraction runs with detailed metadata including phase metrics.

    Returns list of runs sorted by timestamp (newest first), each with:
    - run_id, timestamp, model, status (complete/partial/failed)
    - duration_seconds, claims_count, docs_total, docs_success, docs_failed
    - phases:
      - ingestion: discovered, ingested, skipped, failed
      - classification: classified, low_confidence, distribution
      - extraction: attempted, succeeded, failed
      - quality_gate: pass, warn, fail
    """
    from context_builder.api.insights import list_detailed_runs

    return list_detailed_runs(DATA_DIR)


@app.get("/api/insights/run/{run_id}/overview")
def get_run_overview(run_id: str):
    """Get overview KPIs for a specific run."""
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR, run_id=run_id)
    return {
        "run_metadata": aggregator.get_run_metadata(),
        "overview": aggregator.get_overview(),
    }


@app.get("/api/insights/run/{run_id}/doc-types")
def get_run_doc_types(run_id: str):
    """Get doc type metrics for a specific run."""
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR, run_id=run_id)
    return aggregator.get_doc_type_metrics()


@app.get("/api/insights/run/{run_id}/priorities")
def get_run_priorities(run_id: str, limit: int = Query(10, ge=1, le=50)):
    """Get priorities for a specific run."""
    from context_builder.api.insights import InsightsAggregator

    aggregator = InsightsAggregator(DATA_DIR, run_id=run_id)
    return aggregator.get_priorities(limit=limit)


@app.get("/api/insights/compare")
def compare_runs_endpoint(
    baseline: str = Query(..., description="Baseline run ID"),
    current: str = Query(..., description="Current run ID to compare"),
):
    """
    Compare two runs and compute deltas.

    Returns:
    - overview_deltas: delta for each KPI
    - priority_changes: fields that improved/regressed
    - doc_type_deltas: per doc type metric changes
    """
    from context_builder.api.insights import compare_runs

    return compare_runs(DATA_DIR, baseline, current)


@app.get("/api/insights/baseline")
def get_baseline_endpoint():
    """Get the current baseline run ID."""
    from context_builder.api.insights import get_baseline

    baseline_id = get_baseline(DATA_DIR)
    return {"baseline_run_id": baseline_id}


@app.post("/api/insights/baseline")
def set_baseline_endpoint(run_id: str = Query(..., description="Run ID to set as baseline")):
    """Set a run as the baseline for comparisons."""
    from context_builder.api.insights import set_baseline

    set_baseline(DATA_DIR, run_id)
    return {"status": "ok", "baseline_run_id": run_id}


@app.delete("/api/insights/baseline")
def clear_baseline_endpoint():
    """Clear the baseline setting."""
    from context_builder.api.insights import clear_baseline

    clear_baseline(DATA_DIR)
    return {"status": "ok"}


# =============================================================================
# CLASSIFICATION REVIEW ENDPOINTS
# =============================================================================

@app.get("/api/classification/docs")
def list_classification_docs(run_id: str = Query(..., description="Run ID to get classification data for")):
    """
    List all documents with classification data for review.

    Returns doc_id, claim_id, filename, predicted_type, confidence, signals,
    review_status (pending/confirmed/overridden), and doc_type_truth.
    """
    storage = get_storage()
    global_runs_dir = get_global_runs_dir()

    # Build list of docs from all claims
    docs = []

    for claim_dir in DATA_DIR.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        docs_dir = claim_dir / "docs"
        run_dir = claim_dir / "runs" / run_id

        if not docs_dir.exists() or not run_dir.exists():
            continue

        context_dir = run_dir / "context"
        if not context_dir.exists():
            continue

        claim_id = extract_claim_number(claim_dir.name)

        for doc_folder in docs_dir.iterdir():
            if not doc_folder.is_dir():
                continue

            doc_id = doc_folder.name
            meta_path = doc_folder / "meta" / "doc.json"
            context_path = context_dir / f"{doc_id}.json"

            if not meta_path.exists() or not context_path.exists():
                continue

            # Load metadata
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            # Load classification context
            with open(context_path, "r", encoding="utf-8") as f:
                context = json.load(f)

            classification = context.get("classification", {})
            predicted_type = classification.get("document_type", meta.get("doc_type", "unknown"))
            confidence = classification.get("confidence", meta.get("doc_type_confidence", 0.0))
            signals = classification.get("signals", [])

            # Check for existing label
            labels_path = doc_folder / "labels" / "latest.json"
            review_status = "pending"
            doc_type_truth = None

            if labels_path.exists():
                with open(labels_path, "r", encoding="utf-8") as f:
                    label_data = json.load(f)
                    doc_labels = label_data.get("doc_labels", {})
                    doc_type_correct = doc_labels.get("doc_type_correct", True)
                    doc_type_truth = doc_labels.get("doc_type_truth")

                    if doc_type_correct and doc_type_truth is None:
                        review_status = "confirmed"
                    elif not doc_type_correct and doc_type_truth:
                        review_status = "overridden"
                    elif doc_type_correct:
                        review_status = "confirmed"

            docs.append({
                "doc_id": doc_id,
                "claim_id": claim_id,
                "filename": meta.get("original_filename", "Unknown"),
                "predicted_type": predicted_type,
                "confidence": round(confidence, 2) if confidence else 0.0,
                "signals": signals[:5] if signals else [],  # Limit to 5
                "review_status": review_status,
                "doc_type_truth": doc_type_truth,
            })

    # Sort by confidence ascending (lowest confidence first for review priority)
    docs.sort(key=lambda d: (d["review_status"] != "pending", d["confidence"]))

    return docs


@app.get("/api/classification/doc/{doc_id}")
def get_classification_detail(doc_id: str, run_id: str = Query(..., description="Run ID")):
    """
    Get full classification context for a document.

    Returns classification (signals, summary, key_hints), text preview,
    source url info, and existing label if any.
    """
    storage = get_storage()

    # Get document bundle
    doc_bundle = storage.get_doc(doc_id)
    if not doc_bundle:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    claim_dir = doc_bundle.doc_root.parent.parent
    claim_id = extract_claim_number(claim_dir.name)

    # Load classification context
    context_path = claim_dir / "runs" / run_id / "context" / f"{doc_id}.json"
    if not context_path.exists():
        raise HTTPException(status_code=404, detail=f"Classification context not found for run: {run_id}")

    with open(context_path, "r", encoding="utf-8") as f:
        context = json.load(f)

    classification = context.get("classification", {})

    # Load text preview
    doc_text = storage.get_doc_text(doc_id)
    pages_preview = ""
    if doc_text and doc_text.pages:
        # Get first 1000 chars across pages
        full_text = "\n\n".join(p.get("text", "") for p in doc_text.pages)
        pages_preview = full_text[:1000] + ("..." if len(full_text) > 1000 else "")

    # Check for source file
    has_pdf = False
    has_image = False
    source_dir = doc_bundle.doc_root / "source"
    if source_dir.exists():
        for source_file in source_dir.iterdir():
            ext = source_file.suffix.lower()
            if ext == ".pdf":
                has_pdf = True
            elif ext in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp"}:
                has_image = True

    # Load existing label
    existing_label = None
    labels_path = doc_bundle.doc_root / "labels" / "latest.json"
    if labels_path.exists():
        with open(labels_path, "r", encoding="utf-8") as f:
            label_data = json.load(f)
            doc_labels = label_data.get("doc_labels", {})
            existing_label = {
                "doc_type_correct": doc_labels.get("doc_type_correct", True),
                "doc_type_truth": doc_labels.get("doc_type_truth"),
                "notes": label_data.get("review", {}).get("notes", ""),
            }

    return {
        "doc_id": doc_id,
        "claim_id": claim_id,
        "filename": doc_bundle.metadata.get("original_filename", "Unknown"),
        "predicted_type": classification.get("document_type", "unknown"),
        "confidence": classification.get("confidence", 0.0),
        "signals": classification.get("signals", []),
        "summary": classification.get("summary", ""),
        "key_hints": classification.get("key_hints"),
        "pages_preview": pages_preview,
        "has_pdf": has_pdf,
        "has_image": has_image,
        "existing_label": existing_label,
    }


@app.post("/api/classification/doc/{doc_id}/label")
def save_classification_label(doc_id: str, request: ClassificationLabelRequest):
    """
    Save classification review result.

    Updates doc_labels in the label file with doc_type_correct and doc_type_truth.
    """
    storage = get_storage()

    # Get document bundle
    doc_bundle = storage.get_doc(doc_id)
    if not doc_bundle:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    claim_dir = doc_bundle.doc_root.parent.parent
    resolved_claim_id = extract_claim_number(claim_dir.name)

    # Validate: if doc_type_correct is False, doc_type_truth must be provided
    if not request.doc_type_correct and not request.doc_type_truth:
        raise HTTPException(
            status_code=400,
            detail="doc_type_truth is required when doc_type_correct is False"
        )

    # Load existing label or create new
    labels_path = doc_bundle.doc_root / "labels" / "latest.json"
    if labels_path.exists():
        with open(labels_path, "r", encoding="utf-8") as f:
            label_data = json.load(f)
    else:
        label_data = {
            "schema_version": "label_v3",
            "doc_id": doc_id,
            "claim_id": resolved_claim_id,
            "review": {
                "reviewed_at": None,
                "reviewer": "",
                "notes": "",
            },
            "field_labels": [],
            "doc_labels": {},
        }

    # Update doc_labels with classification review
    label_data["doc_labels"]["doc_type_correct"] = request.doc_type_correct
    label_data["doc_labels"]["doc_type_truth"] = request.doc_type_truth if not request.doc_type_correct else None
    label_data["review"]["reviewed_at"] = datetime.utcnow().isoformat() + "Z"
    if request.notes:
        label_data["review"]["notes"] = request.notes

    # Save using Storage's atomic write
    try:
        storage.save_label(doc_id, label_data)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save label: {e}")

    return {"status": "saved", "doc_id": doc_id}


@app.get("/api/classification/stats")
def get_classification_stats(run_id: str = Query(..., description="Run ID to get stats for")):
    """
    Get classification review KPIs.

    Returns docs_total, docs_reviewed, overrides_count, avg_confidence,
    and confusion_matrix (predicted vs truth).
    """
    docs_total = 0
    docs_reviewed = 0
    overrides_count = 0
    total_confidence = 0.0
    by_predicted_type: Dict[str, Dict[str, int]] = {}
    confusion_entries: Dict[tuple, int] = {}  # (predicted, truth) -> count

    for claim_dir in DATA_DIR.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        docs_dir = claim_dir / "docs"
        run_dir = claim_dir / "runs" / run_id

        if not docs_dir.exists() or not run_dir.exists():
            continue

        context_dir = run_dir / "context"
        if not context_dir.exists():
            continue

        for doc_folder in docs_dir.iterdir():
            if not doc_folder.is_dir():
                continue

            doc_id = doc_folder.name
            meta_path = doc_folder / "meta" / "doc.json"
            context_path = context_dir / f"{doc_id}.json"

            if not meta_path.exists() or not context_path.exists():
                continue

            docs_total += 1

            # Load classification context for confidence
            with open(context_path, "r", encoding="utf-8") as f:
                context = json.load(f)

            classification = context.get("classification", {})
            predicted_type = classification.get("document_type", "unknown")
            confidence = classification.get("confidence", 0.0)
            total_confidence += confidence if confidence else 0.0

            # Track by predicted type
            if predicted_type not in by_predicted_type:
                by_predicted_type[predicted_type] = {"count": 0, "override_count": 0}
            by_predicted_type[predicted_type]["count"] += 1

            # Check for existing label
            labels_path = doc_folder / "labels" / "latest.json"
            if labels_path.exists():
                with open(labels_path, "r", encoding="utf-8") as f:
                    label_data = json.load(f)
                    doc_labels = label_data.get("doc_labels", {})

                    # Check if classification was reviewed
                    if "doc_type_correct" in doc_labels:
                        docs_reviewed += 1
                        doc_type_correct = doc_labels.get("doc_type_correct", True)
                        doc_type_truth = doc_labels.get("doc_type_truth")

                        if not doc_type_correct and doc_type_truth:
                            overrides_count += 1
                            by_predicted_type[predicted_type]["override_count"] += 1

                            # Add to confusion matrix
                            key = (predicted_type, doc_type_truth)
                            confusion_entries[key] = confusion_entries.get(key, 0) + 1

    avg_confidence = round(total_confidence / max(docs_total, 1), 2)

    # Build confusion matrix list
    confusion_matrix = [
        {"predicted": pred, "truth": truth, "count": count}
        for (pred, truth), count in sorted(confusion_entries.items(), key=lambda x: -x[1])
    ]

    return {
        "docs_total": docs_total,
        "docs_reviewed": docs_reviewed,
        "overrides_count": overrides_count,
        "avg_confidence": avg_confidence,
        "by_predicted_type": by_predicted_type,
        "confusion_matrix": confusion_matrix,
    }
