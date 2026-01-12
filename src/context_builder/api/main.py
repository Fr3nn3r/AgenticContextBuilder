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
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
from context_builder.api.services import ClaimsService, DocumentsService, InsightsService, LabelsService
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

# Storage abstraction layer (uses indexes when available)
from context_builder.storage import FileStorage


def get_storage() -> FileStorage:
    """Get Storage instance (fresh for each request to see new runs)."""
    return FileStorage(DATA_DIR)


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
    return get_documents_service().get_doc(doc_id, run_id)


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
