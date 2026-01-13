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

from pathlib import Path as _Path
from dotenv import load_dotenv
import os as _os

# Find project root (where .env is located) by going up from this file
_project_root = _Path(__file__).resolve().parent.parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    print(f"[startup] Loaded .env from {_env_path}")
    print(f"[startup] AZURE_DI_ENDPOINT = {_os.getenv('AZURE_DI_ENDPOINT', 'NOT SET')[:30]}...")
else:
    print(f"[startup] WARNING: .env not found at {_env_path}")

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncio
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from context_builder.api.models import (
    ClaimReviewPayload,
    ClaimSummary,
    ClassificationLabelRequest,
    DocPayload,
    DocReviewRequest,
    DocSummary,
    RunSummary,
    SaveLabelsRequest,
    TemplateSpec,
)
from context_builder.api.services import (
    ClaimsService,
    DocPhase,
    DocumentsService,
    InsightsService,
    LabelsService,
    PipelineService,
    UploadService,
)
from context_builder.api.services.utils import extract_claim_number, get_global_runs_dir


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

# Staging directory for pending uploads
STAGING_DIR: Path = _PROJECT_ROOT / "output" / ".pending"

# Storage abstraction layer (uses indexes when available)
from context_builder.storage import FileStorage, StorageFacade


def get_storage() -> StorageFacade:
    """Get Storage instance (fresh for each request to see new runs)."""
    return StorageFacade.from_storage(FileStorage(DATA_DIR))


def set_data_dir(path: Path):
    """Set the data directory for the API."""
    global DATA_DIR
    DATA_DIR = path


def get_claims_service() -> ClaimsService:
    """Get ClaimsService instance."""
    return ClaimsService(DATA_DIR, get_storage)


def get_documents_service() -> DocumentsService:
    """Get DocumentsService instance."""
    return DocumentsService(DATA_DIR, get_storage)


def get_labels_service() -> LabelsService:
    """Get LabelsService instance."""
    return LabelsService(get_storage)


def get_insights_service() -> InsightsService:
    """Get InsightsService instance."""
    return InsightsService(DATA_DIR)


def get_upload_service() -> UploadService:
    """Get UploadService instance."""
    return UploadService(STAGING_DIR, DATA_DIR)


# Global PipelineService instance (needs to maintain state across requests)
_pipeline_service: Optional[PipelineService] = None


def get_pipeline_service() -> PipelineService:
    """Get PipelineService singleton instance."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService(DATA_DIR, get_upload_service())
    return _pipeline_service


# =============================================================================
# WEBSOCKET CONNECTION MANAGER
# =============================================================================


class ConnectionManager:
    """Manage WebSocket connections for pipeline progress updates."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        """Accept and track a WebSocket connection."""
        await websocket.accept()
        if run_id not in self.active_connections:
            self.active_connections[run_id] = []
        self.active_connections[run_id].append(websocket)

    def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        """Remove a WebSocket connection."""
        if run_id in self.active_connections:
            if websocket in self.active_connections[run_id]:
                self.active_connections[run_id].remove(websocket)

    async def broadcast(self, run_id: str, message: dict) -> None:
        """Broadcast message to all connections for a run."""
        if run_id not in self.active_connections:
            return
        disconnected = []
        for connection in self.active_connections[run_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        # Clean up disconnected
        for conn in disconnected:
            self.disconnect(conn, run_id)


ws_manager = ConnectionManager()


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
    return get_claims_service().list_claims(run_id)


@app.get("/api/claims/runs")
def list_claim_runs():
    """
    List all available run IDs for the claims view.

    Returns list of run IDs sorted newest first, with metadata.
    Reads from global runs directory (output/runs/) when available.
    """
    return get_claims_service().list_runs()


@app.get("/api/claims/{claim_id}/docs", response_model=List[DocSummary])
def list_docs(claim_id: str, run_id: Optional[str] = Query(None, description="Filter by run ID")):
    """
    List documents for a specific claim.

    Args:
        claim_id: Can be either the full folder name or extracted claim number.
        run_id: Optional run ID for extraction metrics. If not provided, uses latest run.
    """
    return get_documents_service().list_docs(claim_id, run_id)


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
    return get_documents_service().get_doc(doc_id, run_id, claim_id)


@app.post("/api/docs/{doc_id}/labels")
def save_labels(doc_id: str, request: SaveLabelsRequest, claim_id: Optional[str] = Query(None)):
    """
    Save human labels for a document.

    Uses Storage abstraction for atomic write (temp file + rename).
    Labels are stored at docs/{doc_id}/labels/latest.json (run-independent).
    """
    return get_labels_service().save_labels(
        doc_id,
        reviewer=request.reviewer,
        notes=request.notes,
        field_labels=request.field_labels,
        doc_labels=request.doc_labels,
    )


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
    return get_claims_service().get_run_summary()


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
    return get_claims_service().get_claim_review(claim_id)


@app.post("/api/docs/{doc_id}/review")
def save_doc_review(doc_id: str, request: DocReviewRequest):
    """
    Save simplified doc-level review (no field labels, no reviewer name).

    Saves doc_type_correct and optional notes.
    Labels are stored at docs/{doc_id}/labels/latest.json (run-independent).
    """
    return get_labels_service().save_doc_review(
        doc_id,
        claim_id=request.claim_id,
        doc_type_correct=request.doc_type_correct,
        notes=request.notes,
    )


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
    source_file, media_type, filename = get_documents_service().get_doc_source(doc_id)
    return FileResponse(
        path=source_file,
        media_type=media_type,
        filename=filename,
    )


@app.get("/api/docs/{doc_id}/azure-di")
def get_doc_azure_di(doc_id: str, claim_id: Optional[str] = Query(None)):
    """
    Get Azure DI raw output for bounding box highlighting.

    Returns the azure_di.json if available, containing word-level
    polygon coordinates for visual highlighting on PDF.
    Uses Storage abstraction for O(1) document lookup.
    """
    return get_documents_service().get_doc_azure_di(doc_id)


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
    return get_insights_service().get_overview()


@app.get("/api/insights/doc-types")
def get_insights_doc_types():
    """
    Get metrics per doc type for the scoreboard.

    Returns list of doc type metrics including:
    - docs_reviewed, docs_doc_type_wrong, docs_needs_vision
    - required_field_presence_pct, required_field_accuracy_pct
    - evidence_rate_pct, top_failing_field
    """
    return get_insights_service().get_doc_type_metrics()


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
    return get_insights_service().get_priorities(limit)


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
    return get_insights_service().get_field_details(doc_type, field, run_id)


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
    return get_insights_service().get_examples(
        doc_type=doc_type,
        field=field,
        outcome=outcome,
        run_id=run_id,
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
    return get_insights_service().list_runs()


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
    return get_insights_service().list_runs_detailed()


@app.get("/api/insights/run/{run_id}/overview")
def get_run_overview(run_id: str):
    """Get overview KPIs for a specific run."""
    return get_insights_service().get_run_overview(run_id)


@app.get("/api/insights/run/{run_id}/doc-types")
def get_run_doc_types(run_id: str):
    """Get doc type metrics for a specific run."""
    return get_insights_service().get_run_doc_types(run_id)


@app.get("/api/insights/run/{run_id}/priorities")
def get_run_priorities(run_id: str, limit: int = Query(10, ge=1, le=50)):
    """Get priorities for a specific run."""
    return get_insights_service().get_run_priorities(run_id, limit)


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
    return get_insights_service().compare_runs(baseline, current)


@app.get("/api/insights/baseline")
def get_baseline_endpoint():
    """Get the current baseline run ID."""
    return get_insights_service().get_baseline()


@app.post("/api/insights/baseline")
def set_baseline_endpoint(run_id: str = Query(..., description="Run ID to set as baseline")):
    """Set a run as the baseline for comparisons."""
    return get_insights_service().set_baseline(run_id)


@app.delete("/api/insights/baseline")
def clear_baseline_endpoint():
    """Clear the baseline setting."""
    return get_insights_service().clear_baseline()


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
    global_runs_dir = get_global_runs_dir(DATA_DIR)

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
    return get_labels_service().save_classification_label(
        doc_id,
        doc_type_correct=request.doc_type_correct,
        doc_type_truth=request.doc_type_truth,
        notes=request.notes,
    )


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


# =============================================================================
# UPLOAD ENDPOINTS
# =============================================================================


@app.post("/api/upload/claim/{claim_id}")
async def upload_documents(
    claim_id: str,
    files: List[UploadFile] = File(..., description="Files to upload"),
):
    """
    Upload documents to a pending claim.

    Creates the claim in staging if it doesn't exist.
    Validates file types (PDF, PNG, JPG, TXT) and size (max 100MB).

    Returns the claim_id and list of uploaded documents.
    """
    upload_service = get_upload_service()
    results = []

    for file in files:
        doc = await upload_service.add_document(claim_id, file)
        results.append({
            "doc_id": doc.doc_id,
            "original_filename": doc.original_filename,
            "file_size": doc.file_size,
            "content_type": doc.content_type,
            "upload_time": doc.upload_time,
        })

    return {"claim_id": claim_id, "documents": results}


@app.delete("/api/upload/claim/{claim_id}")
def delete_pending_claim(claim_id: str):
    """
    Remove a pending claim and all its documents from staging.
    """
    upload_service = get_upload_service()

    if upload_service.remove_claim(claim_id):
        return {"status": "deleted", "claim_id": claim_id}

    raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")


@app.delete("/api/upload/claim/{claim_id}/doc/{doc_id}")
def delete_pending_document(claim_id: str, doc_id: str):
    """
    Remove a single document from a pending claim.
    """
    upload_service = get_upload_service()

    if upload_service.remove_document(claim_id, doc_id):
        return {"status": "deleted", "doc_id": doc_id}

    raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")


@app.get("/api/upload/pending")
def list_pending_claims():
    """
    List all pending claims in the staging area.

    Returns claims with their documents, sorted by creation time (newest first).
    """
    upload_service = get_upload_service()
    claims = upload_service.list_pending_claims()

    return [
        {
            "claim_id": c.claim_id,
            "created_at": c.created_at,
            "documents": [
                {
                    "doc_id": d.doc_id,
                    "original_filename": d.original_filename,
                    "file_size": d.file_size,
                    "content_type": d.content_type,
                    "upload_time": d.upload_time,
                }
                for d in c.documents
            ],
        }
        for c in claims
    ]


@app.post("/api/upload/generate-claim-id")
def generate_claim_id():
    """
    Generate a unique claim file number.

    Format: CLM-YYYYMMDD-XXX where XXX is a sequential number.
    Checks both finalized claims and pending claims to ensure uniqueness.
    """
    from datetime import datetime

    upload_service = get_upload_service()
    today = datetime.now()
    date_str = today.strftime("%Y%m%d")
    prefix = f"CLM-{date_str}-"

    # Get all existing claim IDs (finalized + pending)
    existing_ids = set()

    # Check finalized claims directory
    if upload_service.claims_dir.exists():
        for item in upload_service.claims_dir.iterdir():
            if item.is_dir() and item.name.startswith(prefix):
                existing_ids.add(item.name)

    # Check pending claims
    for claim in upload_service.list_pending_claims():
        if claim.claim_id.startswith(prefix):
            existing_ids.add(claim.claim_id)

    # Find next available number
    max_num = 0
    for claim_id in existing_ids:
        try:
            num = int(claim_id[len(prefix):])
            max_num = max(max_num, num)
        except ValueError:
            pass

    next_num = max_num + 1
    new_claim_id = f"{prefix}{str(next_num).zfill(3)}"

    return {"claim_id": new_claim_id}


@app.put("/api/upload/claim/{claim_id}/reorder")
def reorder_documents(claim_id: str, doc_ids: List[str]):
    """
    Reorder documents within a pending claim.

    Pass the full list of doc_ids in the desired order.
    """
    upload_service = get_upload_service()

    if upload_service.reorder_documents(claim_id, doc_ids):
        return {"status": "reordered", "claim_id": claim_id}

    raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")


@app.get("/api/upload/claim/{claim_id}")
def get_pending_claim(claim_id: str):
    """
    Get a single pending claim by ID.
    """
    upload_service = get_upload_service()
    claim = upload_service.get_pending_claim(claim_id)

    if claim is None:
        raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")

    return {
        "claim_id": claim.claim_id,
        "created_at": claim.created_at,
        "documents": [
            {
                "doc_id": d.doc_id,
                "original_filename": d.original_filename,
                "file_size": d.file_size,
                "content_type": d.content_type,
                "upload_time": d.upload_time,
            }
            for d in claim.documents
        ],
    }


@app.post("/api/upload/claim/{claim_id}/validate")
def validate_claim_id(claim_id: str):
    """
    Validate that a claim ID is acceptable (doesn't already exist).

    Returns status: valid or error details.
    """
    upload_service = get_upload_service()

    try:
        upload_service.validate_claim_id(claim_id)
        return {"status": "valid", "claim_id": claim_id}
    except HTTPException as e:
        raise e


# =============================================================================
# PIPELINE ENDPOINTS
# =============================================================================


class PipelineRunRequest(BaseModel):
    claim_ids: List[str]
    model: str = "gpt-4o"


@app.post("/api/pipeline/run")
async def start_pipeline_run(request: PipelineRunRequest):
    """
    Start pipeline execution for pending claims.

    Args:
        request: Pipeline run request with claim_ids and model

    Returns:
        run_id for tracking progress
    """
    pipeline_service = get_pipeline_service()
    upload_service = get_upload_service()

    # Validate all claims exist in staging
    for claim_id in request.claim_ids:
        if not upload_service.claim_exists_staging(claim_id):
            raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")

    # Create progress callback that broadcasts to WebSocket
    async def broadcast_progress(run_id: str, doc_id: str, phase: DocPhase, error: Optional[str], failed_at_stage: Optional[DocPhase] = None):
        # Handle run completion signal
        if doc_id == "__RUN_COMPLETE__":
            run = pipeline_service.get_run_status(run_id)
            await ws_manager.broadcast(run_id, {
                "type": "run_complete",
                "run_id": run_id,
                "status": run.status.value if run else "completed",
                "summary": run.summary if run else None,
            })
            return

        await ws_manager.broadcast(run_id, {
            "type": "doc_progress",
            "doc_id": doc_id,
            "phase": phase.value,
            "error": error,
            "failed_at_stage": failed_at_stage.value if failed_at_stage else None,
        })

    run_id = await pipeline_service.start_pipeline(
        claim_ids=request.claim_ids,
        model=request.model,
        progress_callback=broadcast_progress,
    )

    return {"run_id": run_id, "status": "running"}


@app.post("/api/pipeline/cancel/{run_id}")
async def cancel_pipeline(run_id: str):
    """
    Cancel a running pipeline.

    Args:
        run_id: Run ID to cancel

    Returns:
        Cancellation status
    """
    pipeline_service = get_pipeline_service()

    if await pipeline_service.cancel_pipeline(run_id):
        # Broadcast cancellation
        await ws_manager.broadcast(run_id, {
            "type": "run_cancelled",
            "run_id": run_id,
        })
        return {"status": "cancelled", "run_id": run_id}

    raise HTTPException(status_code=404, detail=f"Run not found or not running: {run_id}")


@app.get("/api/pipeline/status/{run_id}")
def get_pipeline_status(run_id: str):
    """
    Get current status of a pipeline run.

    Args:
        run_id: Run ID to check

    Returns:
        Run status with document progress
    """
    pipeline_service = get_pipeline_service()
    run = pipeline_service.get_run_status(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return {
        "run_id": run.run_id,
        "status": run.status.value,
        "claim_ids": run.claim_ids,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "summary": run.summary,
        "docs": {
            doc.doc_id: {  # Use doc_id as key for consistency with WebSocket messages
                "doc_id": doc.doc_id,
                "claim_id": doc.claim_id,
                "filename": doc.filename,
                "phase": doc.phase.value,
                "error": doc.error,
            }
            for key, doc in run.docs.items()
        },
    }


@app.get("/api/pipeline/runs")
def list_pipeline_runs():
    """
    List all tracked pipeline runs.

    Returns:
        List of run summaries
    """
    pipeline_service = get_pipeline_service()
    runs = pipeline_service.get_all_runs()

    return [
        {
            "run_id": run.run_id,
            "status": run.status.value,
            "claim_ids": run.claim_ids,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "doc_count": len(run.docs),
            "summary": run.summary,
        }
        for run in runs
    ]


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================


@app.websocket("/api/pipeline/ws/{run_id}")
async def pipeline_websocket(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time pipeline progress updates.

    Messages sent to client:
    - {"type": "sync", "status": "...", "docs": {...}} - Full state on connect
    - {"type": "doc_progress", "doc_id": "...", "phase": "...", "error": ...}
    - {"type": "run_complete", "run_id": "...", "summary": {...}}
    - {"type": "run_cancelled", "run_id": "..."}
    - {"type": "ping"} - Keepalive

    Messages from client:
    - "pong" - Keepalive response
    """
    await ws_manager.connect(websocket, run_id)

    try:
        # Send current state on connect (for reconnection sync)
        pipeline_service = get_pipeline_service()
        run = pipeline_service.get_run_status(run_id)

        if run:
            await websocket.send_json({
                "type": "sync",
                "run_id": run.run_id,
                "status": run.status.value,
                "docs": {
                    doc.doc_id: {  # Use doc_id as key (matches progress messages)
                        "doc_id": doc.doc_id,
                        "claim_id": doc.claim_id,
                        "filename": doc.filename,
                        "phase": doc.phase.value,
                        "error": doc.error,
                        "failed_at_stage": doc.failed_at_stage.value if doc.failed_at_stage else None,
                    }
                    for key, doc in run.docs.items()
                },
            })

        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                # Handle ping/pong
                if data == "pong":
                    continue
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

            # Check if run is complete
            run = pipeline_service.get_run_status(run_id)
            if run and run.status.value in ("completed", "failed", "cancelled"):
                await websocket.send_json({
                    "type": "run_complete",
                    "run_id": run_id,
                    "status": run.status.value,
                    "summary": run.summary,
                })

    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket, run_id)
