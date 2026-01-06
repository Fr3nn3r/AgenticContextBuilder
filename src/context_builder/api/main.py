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
    # Extraction-centric fields
    gate_pass_count: int = 0
    gate_warn_count: int = 0
    gate_fail_count: int = 0
    needs_vision_count: int = 0
    last_processed: Optional[str] = None


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
    text_quality: Optional[str] = None  # "good", "warn", "poor"
    missing_required_fields: List[str] = []
    needs_vision: bool = False


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
DATA_DIR: Path = Path("output/claims")


def set_data_dir(path: Path):
    """Set the data directory for the API."""
    global DATA_DIR
    DATA_DIR = path


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/api/claims", response_model=List[ClaimSummary])
def list_claims():
    """
    List all claims in the data directory.

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

        # Get latest run for this claim
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
        needs_vision_count = 0

        if run_dir:
            extraction_dir = run_dir / "extraction"
            labels_dir = run_dir / "labels"

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

                        # Count needs vision
                        if quality.get("needs_vision_fallback", False):
                            needs_vision_count += 1

                        flags_count += len(quality.get("missing_required_fields", []))

                        # Extract amount
                        amount = extract_amount_from_extraction(ext_data)
                        if amount:
                            total_amount = max(total_amount, amount)

            # Count labels
            if labels_dir and labels_dir.exists():
                labeled_count = len(list(labels_dir.glob("*.labels.json")))

        # Calculate average risk score
        avg_risk = total_risk_score // max(extracted_count, 1)

        # Determine review status
        status = "Reviewed" if labeled_count > 0 else "Not Reviewed"

        # Extract claim number for display
        claim_number = extract_claim_number(claim_dir.name)

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
            # Extraction-centric fields
            gate_pass_count=gate_pass_count,
            gate_warn_count=gate_warn_count,
            gate_fail_count=gate_fail_count,
            needs_vision_count=needs_vision_count,
            last_processed=last_processed,
        ))

    # Sort by risk score descending
    return sorted(claims, key=lambda c: c.risk_score, reverse=True)


@app.get("/api/claims/{claim_id}/docs", response_model=List[DocSummary])
def list_docs(claim_id: str):
    """
    List documents for a specific claim.

    claim_id can be either the full folder name or extracted claim number.
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

    # Get latest run for extractions/labels
    run_dir = get_latest_run_dir_for_claim(claim_dir)
    extraction_dir = run_dir / "extraction" if run_dir else None
    labels_dir = run_dir / "labels" if run_dir else None

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
        text_quality = None
        missing_required_fields: List[str] = []
        needs_vision = False

        if extraction_dir:
            extraction_path = extraction_dir / f"{doc_id}.json"
            has_extraction = extraction_path.exists()
            if has_extraction:
                with open(extraction_path, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    quality_gate = ext_data.get("quality_gate", {})
                    quality_status = quality_gate.get("status")
                    missing_required_fields = quality_gate.get("missing_required_fields", [])
                    needs_vision = quality_gate.get("needs_vision_fallback", False)
                    # Calculate average field confidence
                    fields = ext_data.get("fields", [])
                    if fields:
                        confidence = sum(f.get("confidence", 0) for f in fields) / len(fields)
                    # Determine text quality based on extraction quality
                    if quality_status == "pass":
                        text_quality = "good"
                    elif quality_status == "warn":
                        text_quality = "warn"
                    elif quality_status == "fail":
                        text_quality = "poor"

        # Check for labels
        has_labels = False
        if labels_dir:
            labels_path = labels_dir / f"{doc_id}.labels.json"
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
            text_quality=text_quality,
            missing_required_fields=missing_required_fields,
            needs_vision=needs_vision,
        ))

    return docs


@app.get("/api/docs/{doc_id}", response_model=DocPayload)
def get_doc(doc_id: str, claim_id: Optional[str] = Query(None)):
    """
    Get full document payload for review.

    Args:
        doc_id: The document ID (folder name under docs/)
        claim_id: Optional claim ID to help locate the document

    Returns:
    - Document metadata
    - Page text content (from pages.json)
    - Extraction results (if available)
    - Labels (if available)
    """
    # Find the document across all claims
    doc_folder = None
    claim_dir = None

    for claim in DATA_DIR.iterdir():
        if not claim.is_dir():
            continue

        if claim_id and extract_claim_number(claim.name) != claim_id and claim.name != claim_id:
            continue

        candidate = claim / "docs" / doc_id
        if candidate.exists():
            doc_folder = candidate
            claim_dir = claim
            break

    if not doc_folder:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    # Read document metadata
    meta_path = doc_folder / "meta" / "doc.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Document metadata not found")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    filename = meta.get("original_filename", "Unknown")
    doc_type = meta.get("doc_type", "unknown")
    language = meta.get("language", "es")

    # Load pages from pages.json
    pages = []
    pages_path = doc_folder / "text" / "pages.json"
    if pages_path.exists():
        with open(pages_path, "r", encoding="utf-8") as f:
            pages_data = json.load(f)
            pages = pages_data.get("pages", [])

    # Get latest run
    run_dir = get_latest_run_dir_for_claim(claim_dir)

    # Load extraction if exists
    extraction = None
    if run_dir:
        extraction_path = run_dir / "extraction" / f"{doc_id}.json"
        if extraction_path.exists():
            with open(extraction_path, "r", encoding="utf-8") as f:
                extraction = json.load(f)

    # Load labels if exist
    labels = None
    if run_dir:
        labels_path = run_dir / "labels" / f"{doc_id}.labels.json"
        if labels_path.exists():
            with open(labels_path, "r", encoding="utf-8") as f:
                labels = json.load(f)

    return DocPayload(
        doc_id=doc_id,
        claim_id=extract_claim_number(claim_dir.name),
        filename=filename,
        doc_type=doc_type,
        language=language,
        pages=pages,
        extraction=extraction,
        labels=labels,
    )


@app.post("/api/docs/{doc_id}/labels")
def save_labels(doc_id: str, request: SaveLabelsRequest, claim_id: Optional[str] = Query(None)):
    """
    Save human labels for a document.

    Uses atomic write (temp file + rename) for safety.
    Labels are stored in the latest run directory.
    """
    # Find the document's claim directory
    claim_dir = None
    for claim in DATA_DIR.iterdir():
        if not claim.is_dir():
            continue
        if claim_id and extract_claim_number(claim.name) != claim_id and claim.name != claim_id:
            continue
        if (claim / "docs" / doc_id).exists():
            claim_dir = claim
            break

    if not claim_dir:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    # Get latest run directory
    run_dir = get_latest_run_dir_for_claim(claim_dir)
    if not run_dir:
        raise HTTPException(status_code=404, detail="No run directory found for claim")

    labels_dir = run_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Build label result
    label_data = {
        "schema_version": "label_v1",
        "doc_id": doc_id,
        "claim_id": extract_claim_number(claim_dir.name),
        "review": {
            "reviewed_at": datetime.utcnow().isoformat(),
            "reviewer": request.reviewer,
            "notes": request.notes,
        },
        "field_labels": request.field_labels,
        "doc_labels": request.doc_labels,
    }

    # Atomic write
    labels_path = labels_dir / f"{doc_id}.labels.json"
    temp_path = labels_path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(label_data, f, indent=2, ensure_ascii=False)

    temp_path.replace(labels_path)

    return {"status": "saved", "path": str(labels_path)}


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
