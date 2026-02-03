"""Dashboard router for claims overview with assessment and ground truth data."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from context_builder.api.models import (
    DashboardClaim,
    DashboardClaimDetail,
)
from context_builder.api.services.dashboard import DashboardService
from context_builder.api.dependencies import get_data_dir

router = APIRouter(tags=["dashboard"])


def _get_dashboard_service() -> DashboardService:
    return DashboardService(get_data_dir())


@router.get("/api/dashboard/claims", response_model=List[DashboardClaim])
def list_dashboard_claims():
    """Get enriched claim data for all claims in the workspace."""
    service = _get_dashboard_service()
    return service.list_claims()


@router.get(
    "/api/dashboard/claims/{claim_id}/detail",
    response_model=DashboardClaimDetail,
)
def get_dashboard_claim_detail(claim_id: str):
    """Get expanded detail data for a single claim."""
    service = _get_dashboard_service()
    detail = service.get_claim_detail(claim_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return detail


@router.get("/api/dashboard/claims/{claim_id}/ground-truth-doc")
def get_ground_truth_doc(claim_id: str):
    """Serve the ground truth Claim Decision PDF."""
    service = _get_dashboard_service()
    path = service.get_ground_truth_doc_path(claim_id)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ground truth document not found for claim {claim_id}",
        )
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="Claim_Decision_{claim_id}.pdf"'},
    )
