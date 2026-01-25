"""Classification router - endpoints for document classification review."""

import json
from typing import Dict

from fastapi import APIRouter, HTTPException, Query

from context_builder.api.dependencies import (
    get_data_dir,
    get_labels_service,
    get_storage,
)
from context_builder.api.models import ClassificationLabelRequest
from context_builder.api.services.utils import extract_claim_number

router = APIRouter(tags=["classification"])


@router.get("/api/classification/docs")
def list_classification_docs(run_id: str = Query(..., description="Run ID to get classification data for")):
    """
    List all documents with classification data for review.

    Returns doc_id, claim_id, filename, predicted_type, confidence, signals,
    review_status (pending/confirmed/overridden), and doc_type_truth.
    """
    storage = get_storage()

    # Build list of docs using storage layer
    docs = []

    # Use storage layer to list extractions for this run
    extraction_refs = storage.run_store.list_extractions(run_id)

    for ext_ref in extraction_refs:
        doc_id = ext_ref.doc_id
        claim_folder = ext_ref.claim_id

        # Get doc metadata using storage layer
        meta = storage.doc_store.get_doc_metadata(doc_id, claim_id=claim_folder)
        if not meta:
            continue

        # Get extraction using storage layer
        extraction = storage.run_store.get_extraction(run_id, doc_id, claim_id=claim_folder)
        if not extraction:
            continue

        doc_info = extraction.get("doc", {})
        predicted_type = doc_info.get("doc_type", meta.get("doc_type", "unknown"))
        confidence = doc_info.get("doc_type_confidence", meta.get("doc_type_confidence", 0.0))
        signals = []  # Extraction files don't have classification signals

        # Check for existing label (from registry/labels/)
        review_status = "pending"
        doc_type_truth = None

        label_data = storage.label_store.get_label(doc_id)
        if label_data:
            doc_labels = label_data.get("doc_labels", {})
            doc_type_correct = doc_labels.get("doc_type_correct", True)
            doc_type_truth = doc_labels.get("doc_type_truth")

            if doc_type_correct and doc_type_truth is None:
                review_status = "confirmed"
            elif not doc_type_correct and doc_type_truth:
                review_status = "overridden"
            elif doc_type_correct:
                review_status = "confirmed"

        # Extract claim number for display
        claim_id = extract_claim_number(claim_folder)

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


@router.get("/api/classification/doc/{doc_id}")
def get_classification_detail(
    doc_id: str,
    run_id: str = Query(..., description="Run ID"),
    claim_id: str = Query(..., description="Claim ID"),
):
    """
    Get full classification context for a document.

    Returns classification (signals, summary, key_hints), text preview,
    source url info, and existing label if any.
    """
    storage = get_storage()

    # Find claim directory by claim_id
    claim_root = storage.doc_store.claims_dir / claim_id
    if not claim_root.exists():
        # Try with CLM- prefix if not present
        claim_root = storage.doc_store.claims_dir / f"CLM-{claim_id}"
        if not claim_root.exists():
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    # Get the doc directory
    doc_root = claim_root / "docs" / doc_id
    if not doc_root.exists():
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in claim {claim_id}")

    # Load document metadata
    meta_path = doc_root / "meta" / "doc.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"Document metadata not found: {doc_id}")

    with open(meta_path, "r", encoding="utf-8") as f:
        doc_metadata = json.load(f)

    # Load classification context
    context_path = claim_root / "runs" / run_id / "context" / f"{doc_id}.json"
    if not context_path.exists():
        raise HTTPException(status_code=404, detail=f"Classification context not found for run: {run_id}")

    with open(context_path, "r", encoding="utf-8") as f:
        context = json.load(f)

    classification = context.get("classification", {})

    # Load text preview
    doc_text = storage.doc_store.get_doc_text(doc_id)
    pages_preview = ""
    if doc_text and doc_text.pages:
        # Get first 1000 chars across pages
        full_text = "\n\n".join(p.get("text", "") for p in doc_text.pages)
        pages_preview = full_text[:1000] + ("..." if len(full_text) > 1000 else "")

    # Check for source file
    has_pdf = False
    has_image = False
    source_dir = doc_root / "source"
    if source_dir.exists():
        for source_file in source_dir.iterdir():
            ext = source_file.suffix.lower()
            if ext == ".pdf":
                has_pdf = True
            elif ext in {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp"}:
                has_image = True

    # Load existing label
    existing_label = None
    labels_path = doc_root / "labels" / "latest.json"
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
        "filename": doc_metadata.get("original_filename", "Unknown"),
        "predicted_type": classification.get("document_type", "unknown"),
        "confidence": classification.get("confidence", 0.0),
        "signals": classification.get("signals", []),
        "summary": classification.get("summary", ""),
        "key_hints": classification.get("key_hints"),
        "language": classification.get("language", "unknown"),
        "pages_preview": pages_preview,
        "has_pdf": has_pdf,
        "has_image": has_image,
        "existing_label": existing_label,
    }


@router.post("/api/classification/doc/{doc_id}/label")
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


@router.get("/api/classification/doc-types")
def get_doc_type_catalog():
    """
    Get the document type catalog with descriptions and cues.

    Returns list of doc types with:
    - doc_type: string identifier
    - description: human-readable description
    - cues: list of classification cues/keywords
    """
    from context_builder.classification.openai_classifier import load_doc_type_catalog

    return load_doc_type_catalog()


@router.get("/api/classification/stats")
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

    for claim_dir in get_data_dir().iterdir():
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
