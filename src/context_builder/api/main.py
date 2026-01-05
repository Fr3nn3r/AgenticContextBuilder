"""
FastAPI backend for Extraction QA Console.

Provides endpoints for:
- Listing claims and documents
- Getting document content with extraction results
- Saving human labels
- Re-running extraction
- Run metrics dashboard

File-based storage (no database).
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from context_builder.schemas.extraction_result import ExtractionResult
from context_builder.schemas.label import LabelResult, FieldLabel, DocLabels, ReviewMetadata


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


class DocSummary(BaseModel):
    """Summary of a document for listing."""
    doc_id: str
    filename: str
    doc_type: str
    language: str
    has_extraction: bool
    has_labels: bool
    quality_status: Optional[str] = None


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

# Data directory (set via environment or default)
DATA_DIR: Path = Path("output/claims-processed")


def set_data_dir(path: Path):
    """Set the data directory for the API."""
    global DATA_DIR
    DATA_DIR = path


def get_latest_run_dir() -> Optional[Path]:
    """Get the most recent run directory."""
    if not DATA_DIR.exists():
        return None

    run_dirs = [
        d for d in DATA_DIR.iterdir()
        if d.is_dir() and d.name.startswith("run-")
    ]

    if not run_dirs:
        # Check if DATA_DIR itself contains claim folders
        claim_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if claim_dirs:
            return DATA_DIR
        return None

    # Sort by name (timestamp) and return latest
    run_dirs.sort(reverse=True)
    return run_dirs[0]


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/api/claims", response_model=List[ClaimSummary])
def list_claims(run_dir: Optional[str] = Query(None)):
    """
    List all claims in the run directory.

    Args:
        run_dir: Optional specific run directory path
    """
    if run_dir:
        base_dir = Path(run_dir)
    else:
        base_dir = get_latest_run_dir()

    if not base_dir or not base_dir.exists():
        raise HTTPException(status_code=404, detail="No run directory found")

    claims = []
    for claim_dir in base_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue
        if claim_dir.name.startswith("run-"):
            continue  # Skip nested run dirs

        # Read inventory
        inventory_path = claim_dir / "inventory.json"
        if not inventory_path.exists():
            continue

        with open(inventory_path, "r", encoding="utf-8") as f:
            inventory = json.load(f)

        files = inventory.get("files", [])
        doc_types = list(set(f.get("document_type", "unknown") for f in files))

        # Count extractions and labels
        extraction_dir = claim_dir / "extraction"
        labels_dir = claim_dir / "labels"

        extracted_count = len(list(extraction_dir.glob("*.extraction.json"))) if extraction_dir.exists() else 0
        labeled_count = len(list(labels_dir.glob("*.labels.json"))) if labels_dir.exists() else 0

        claims.append(ClaimSummary(
            claim_id=claim_dir.name,
            folder_name=claim_dir.name,
            doc_count=len(files),
            doc_types=doc_types,
            extracted_count=extracted_count,
            labeled_count=labeled_count,
        ))

    return sorted(claims, key=lambda c: c.claim_id)


@app.get("/api/claims/{claim_id}/docs", response_model=List[DocSummary])
def list_docs(claim_id: str, run_dir: Optional[str] = Query(None)):
    """List documents for a specific claim."""
    if run_dir:
        base_dir = Path(run_dir)
    else:
        base_dir = get_latest_run_dir()

    if not base_dir:
        raise HTTPException(status_code=404, detail="No run directory found")

    claim_dir = base_dir / claim_id
    if not claim_dir.exists():
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    # Read inventory
    inventory_path = claim_dir / "inventory.json"
    if not inventory_path.exists():
        raise HTTPException(status_code=404, detail="Inventory not found")

    with open(inventory_path, "r", encoding="utf-8") as f:
        inventory = json.load(f)

    docs = []
    extraction_dir = claim_dir / "extraction"
    labels_dir = claim_dir / "labels"

    for file_info in inventory.get("files", []):
        filename = file_info.get("filename", "")
        safe_name = Path(filename).stem.replace(" ", "_")

        # Check for extraction
        extraction_path = extraction_dir / f"{safe_name}.extraction.json"
        has_extraction = extraction_path.exists()

        # Check for labels
        labels_path = labels_dir / f"{safe_name}.labels.json"
        has_labels = labels_path.exists()

        # Get quality status if extraction exists
        quality_status = None
        if has_extraction:
            with open(extraction_path, "r", encoding="utf-8") as f:
                extraction = json.load(f)
                quality_status = extraction.get("quality_gate", {}).get("status")

        doc_id = f"{claim_id}_{safe_name}"
        docs.append(DocSummary(
            doc_id=doc_id,
            filename=filename,
            doc_type=file_info.get("document_type", "unknown"),
            language=file_info.get("language", "es"),
            has_extraction=has_extraction,
            has_labels=has_labels,
            quality_status=quality_status,
        ))

    return docs


@app.get("/api/docs/{doc_id}", response_model=DocPayload)
def get_doc(doc_id: str, run_dir: Optional[str] = Query(None)):
    """
    Get full document payload for review.

    Returns:
    - Document metadata
    - Page text content (from Azure DI)
    - Extraction results (if available)
    - Labels (if available)
    """
    # Parse doc_id: claim_id_filename
    parts = doc_id.split("_", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid doc_id format")

    claim_id, safe_name = parts

    if run_dir:
        base_dir = Path(run_dir)
    else:
        base_dir = get_latest_run_dir()

    if not base_dir:
        raise HTTPException(status_code=404, detail="No run directory found")

    claim_dir = base_dir / claim_id
    if not claim_dir.exists():
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    # Read inventory to get original filename
    inventory_path = claim_dir / "inventory.json"
    with open(inventory_path, "r", encoding="utf-8") as f:
        inventory = json.load(f)

    # Find file info
    file_info = None
    for f in inventory.get("files", []):
        f_safe = Path(f.get("filename", "")).stem.replace(" ", "_")
        if f_safe == safe_name:
            file_info = f
            break

    if not file_info:
        raise HTTPException(status_code=404, detail=f"Document not found: {safe_name}")

    filename = file_info.get("filename", "")
    doc_type = file_info.get("document_type", "unknown")
    language = file_info.get("language", "es")

    # Load pages from Azure DI markdown
    extraction_dir = claim_dir / "extraction"
    pages = []

    # Find acquired markdown
    base_stem = Path(filename).stem
    md_patterns = [
        f"{base_stem}_acquired.md",
        f"{base_stem.replace(' ', '_')}_acquired.md",
    ]

    md_path = None
    for pattern in md_patterns:
        candidate = extraction_dir / pattern
        if candidate.exists():
            md_path = candidate
            break

    if md_path:
        from context_builder.extraction.page_parser import parse_azure_di_markdown
        markdown_text = md_path.read_text(encoding="utf-8")
        parsed = parse_azure_di_markdown(markdown_text)
        pages = [{"page": p.page, "text": p.text, "text_md5": p.text_md5} for p in parsed]

    # Load extraction if exists
    extraction = None
    extraction_path = extraction_dir / f"{safe_name}.extraction.json"
    if extraction_path.exists():
        with open(extraction_path, "r", encoding="utf-8") as f:
            extraction = json.load(f)

    # Load labels if exist
    labels = None
    labels_dir = claim_dir / "labels"
    labels_path = labels_dir / f"{safe_name}.labels.json"
    if labels_path.exists():
        with open(labels_path, "r", encoding="utf-8") as f:
            labels = json.load(f)

    return DocPayload(
        doc_id=doc_id,
        claim_id=claim_id,
        filename=filename,
        doc_type=doc_type,
        language=language,
        pages=pages,
        extraction=extraction,
        labels=labels,
    )


@app.post("/api/docs/{doc_id}/labels")
def save_labels(doc_id: str, request: SaveLabelsRequest, run_dir: Optional[str] = Query(None)):
    """
    Save human labels for a document.

    Uses atomic write (temp file + rename) for safety.
    """
    # Parse doc_id
    parts = doc_id.split("_", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid doc_id format")

    claim_id, safe_name = parts

    if run_dir:
        base_dir = Path(run_dir)
    else:
        base_dir = get_latest_run_dir()

    if not base_dir:
        raise HTTPException(status_code=404, detail="No run directory found")

    claim_dir = base_dir / claim_id
    labels_dir = claim_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Build label result
    label_data = {
        "schema_version": "label_v1",
        "doc_id": doc_id,
        "claim_id": claim_id,
        "review": {
            "reviewed_at": datetime.utcnow().isoformat(),
            "reviewer": request.reviewer,
            "notes": request.notes,
        },
        "field_labels": request.field_labels,
        "doc_labels": request.doc_labels,
    }

    # Atomic write
    labels_path = labels_dir / f"{safe_name}.labels.json"
    temp_path = labels_path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(label_data, f, indent=2, ensure_ascii=False)

    temp_path.replace(labels_path)

    return {"status": "saved", "path": str(labels_path)}


@app.post("/api/docs/{doc_id}/extract")
def trigger_extraction(doc_id: str, run_dir: Optional[str] = Query(None)):
    """
    Re-run extraction for a document.

    This triggers the extraction pipeline for a single document.
    """
    # Parse doc_id
    parts = doc_id.split("_", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid doc_id format")

    claim_id, safe_name = parts

    if run_dir:
        base_dir = Path(run_dir)
    else:
        base_dir = get_latest_run_dir()

    if not base_dir:
        raise HTTPException(status_code=404, detail="No run directory found")

    # TODO: Implement single-doc extraction
    # For now, return a message to use batch_extraction.py
    return {
        "status": "not_implemented",
        "message": "Use batch_extraction.py to re-run extraction",
    }


@app.get("/api/runs/latest", response_model=RunSummary)
def get_run_summary(run_dir: Optional[str] = Query(None)):
    """Get metrics summary for the latest run."""
    if run_dir:
        base_dir = Path(run_dir)
    else:
        base_dir = get_latest_run_dir()

    if not base_dir or not base_dir.exists():
        raise HTTPException(status_code=404, detail="No run directory found")

    total_claims = 0
    total_docs = 0
    extracted_count = 0
    labeled_count = 0
    quality_gate = {"pass": 0, "warn": 0, "fail": 0}

    for claim_dir in base_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue
        if claim_dir.name.startswith("run-"):
            continue

        total_claims += 1

        # Count docs
        inventory_path = claim_dir / "inventory.json"
        if inventory_path.exists():
            with open(inventory_path, "r", encoding="utf-8") as f:
                inventory = json.load(f)
            total_docs += len(inventory.get("files", []))

        # Count extractions and quality gate
        extraction_dir = claim_dir / "extraction"
        if extraction_dir.exists():
            for ext_file in extraction_dir.glob("*.extraction.json"):
                extracted_count += 1
                with open(ext_file, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    status = ext_data.get("quality_gate", {}).get("status", "unknown")
                    if status in quality_gate:
                        quality_gate[status] += 1

        # Count labels
        labels_dir = claim_dir / "labels"
        if labels_dir.exists():
            labeled_count += len(list(labels_dir.glob("*.labels.json")))

    return RunSummary(
        run_dir=str(base_dir),
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
