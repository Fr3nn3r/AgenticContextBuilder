"""Documents router - endpoints for document operations."""

from typing import List, Optional

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from context_builder.api.dependencies import (
    get_documents_service,
    get_labels_service,
    get_truth_service,
)
from context_builder.api.models import (
    DocPayload,
    DocReviewRequest,
    SaveLabelsRequest,
    TemplateSpec,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.get("/api/documents")
def list_all_documents(
    claim_id: Optional[str] = Query(None, description="Filter by claim ID"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    has_truth: Optional[bool] = Query(None, description="Filter by has ground truth"),
    search: Optional[str] = Query(None, description="Search in filename or doc_id"),
    limit: int = Query(100, ge=1, le=1000, description="Max documents to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List all documents across all claims with optional filters.

    Returns paginated list of documents with metadata.
    """
    docs, total = get_documents_service().list_all_documents(
        claim_id=claim_id,
        doc_type=doc_type,
        has_truth=has_truth,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {"documents": docs, "total": total}


@router.get("/api/docs/{doc_id}", response_model=DocPayload)
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
    try:
        return get_documents_service().get_doc(doc_id, run_id, claim_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error loading document {doc_id}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to load document: {e}"},
        )


@router.post("/api/docs/{doc_id}/labels")
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


@router.post("/api/docs/{doc_id}/extract")
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


@router.post("/api/docs/{doc_id}/review")
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


@router.get("/api/templates", response_model=List[TemplateSpec])
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
                        "validation": rule.validation,
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


@router.get("/api/docs/{doc_id}/source")
def get_doc_source(doc_id: str, claim_id: Optional[str] = Query(None)):
    """
    Serve the original document source file (PDF/image).

    Returns the file from docs/{doc_id}/source/ with correct content-type.
    Uses Storage abstraction for O(1) document lookup.
    """
    try:
        source_file, media_type, filename = get_documents_service().get_doc_source(
            doc_id, claim_id=claim_id
        )
        return FileResponse(
            path=source_file,
            media_type=media_type,
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error loading source for document {doc_id}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Failed to load document source: {e}"},
        )


@router.get("/api/docs/{doc_id}/azure-di")
def get_doc_azure_di(doc_id: str, claim_id: Optional[str] = Query(None)):
    """
    Get Azure DI raw output for bounding box highlighting.

    Returns the azure_di.json if available, containing word-level
    polygon coordinates for visual highlighting on PDF.
    Uses Storage abstraction for O(1) document lookup.
    """
    return get_documents_service().get_doc_azure_di(doc_id)


@router.get("/api/docs/{doc_id}/runs")
def get_doc_runs(doc_id: str, claim_id: str = Query(..., description="Claim ID containing the document")):
    """
    Get all pipeline runs that processed this document.

    Returns list of runs with run_id, timestamp, model, status, and extraction summary.
    Used by the Document Detail page to show run history.
    """
    return get_documents_service().get_doc_runs(doc_id, claim_id)


@router.get("/api/truth")
def list_truth_entries(
    file_md5: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    claim_id: Optional[str] = Query(None),
    reviewer: Optional[str] = Query(None),
    reviewed_after: Optional[str] = Query(None),
    reviewed_before: Optional[str] = Query(None),
    field_name: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """
    List canonical truth entries with per-run extraction comparisons.

    Filters:
    - file_md5, doc_type, claim_id, reviewer, reviewed_after/before,
      field_name, state, outcome, run_id, filename, search.
    """
    return get_truth_service().list_truth_entries(
        file_md5=file_md5,
        doc_type=doc_type,
        claim_id=claim_id,
        reviewer=reviewer,
        reviewed_after=reviewed_after,
        reviewed_before=reviewed_before,
        field_name=field_name,
        state=state,
        outcome=outcome,
        run_id=run_id,
        filename=filename,
        search=search,
    )
