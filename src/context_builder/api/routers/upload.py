"""Upload router - endpoints for document upload and staging."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from context_builder.api.dependencies import get_upload_service

router = APIRouter(tags=["upload"])


@router.post("/api/upload/claim/{claim_id}")
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


@router.delete("/api/upload/claim/{claim_id}")
def delete_pending_claim(claim_id: str):
    """
    Remove a pending claim and all its documents from staging.
    """
    upload_service = get_upload_service()

    if upload_service.remove_claim(claim_id):
        return {"status": "deleted", "claim_id": claim_id}

    raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")


@router.delete("/api/upload/claim/{claim_id}/doc/{doc_id}")
def delete_pending_document(claim_id: str, doc_id: str):
    """
    Remove a single document from a pending claim.
    """
    upload_service = get_upload_service()

    if upload_service.remove_document(claim_id, doc_id):
        return {"status": "deleted", "doc_id": doc_id}

    raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")


@router.get("/api/upload/pending")
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


@router.post("/api/upload/generate-claim-id")
def generate_claim_id():
    """
    Generate a unique claim file number.

    Format: CLM-YYYYMMDD-XXX where XXX is a sequential number.
    Checks both finalized claims and pending claims to ensure uniqueness.
    """
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


@router.put("/api/upload/claim/{claim_id}/reorder")
def reorder_documents(claim_id: str, doc_ids: List[str]):
    """
    Reorder documents within a pending claim.

    Pass the full list of doc_ids in the desired order.
    """
    upload_service = get_upload_service()

    if upload_service.reorder_documents(claim_id, doc_ids):
        return {"status": "reordered", "claim_id": claim_id}

    raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")


@router.get("/api/upload/claim/{claim_id}")
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


@router.post("/api/upload/claim/{claim_id}/validate")
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
