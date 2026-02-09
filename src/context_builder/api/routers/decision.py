"""Decision Dossier router — endpoints for viewing and re-evaluating decision dossiers."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from context_builder.api.dependencies import (
    get_decision_dossier_service,
)

router = APIRouter(tags=["decision"])


# ── Request/Response models ─────────────────────────────────────────


class EvaluateRequest(BaseModel):
    """Request body for re-evaluation with assumption overrides."""

    assumptions: Dict[str, bool] = {}
    claim_run_id: Optional[str] = None


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("/api/claims/{claim_id}/decision-dossier")
def get_latest_dossier(
    claim_id: str,
    claim_run_id: Optional[str] = Query(None, description="Claim run ID (uses latest if omitted)"),
) -> Dict[str, Any]:
    """Get the latest decision dossier version for a claim.

    Returns the highest-version dossier file from the claim run directory.
    """
    service = get_decision_dossier_service()
    dossier = service.get_latest_dossier(claim_id, claim_run_id)

    if dossier is None:
        raise HTTPException(
            status_code=404,
            detail=f"No decision dossier found for claim {claim_id}",
        )

    return dossier


@router.get("/api/claims/{claim_id}/decision-dossier/versions")
def list_dossier_versions(
    claim_id: str,
    claim_run_id: Optional[str] = Query(None, description="Claim run ID (uses latest if omitted)"),
) -> List[Dict[str, Any]]:
    """List all dossier versions for a claim with metadata.

    Returns version number, verdict, timestamp, and engine info for each version.
    """
    service = get_decision_dossier_service()
    return service.list_versions(claim_id, claim_run_id)


@router.get("/api/claims/{claim_id}/decision-dossier/{version}")
def get_dossier_version(
    claim_id: str,
    version: int,
    claim_run_id: Optional[str] = Query(None, description="Claim run ID (uses latest if omitted)"),
) -> Dict[str, Any]:
    """Get a specific decision dossier version.

    Args:
        claim_id: Claim identifier.
        version: Dossier version number.
        claim_run_id: Optional claim run ID.
    """
    service = get_decision_dossier_service()
    dossier = service.get_version(claim_id, version, claim_run_id)

    if dossier is None:
        raise HTTPException(
            status_code=404,
            detail=f"Decision dossier v{version} not found for claim {claim_id}",
        )

    return dossier


@router.post("/api/claims/{claim_id}/decision-dossier/evaluate")
def evaluate_decision(
    claim_id: str,
    request: EvaluateRequest,
) -> Dict[str, Any]:
    """Re-run the decision engine with assumption overrides.

    The engine evaluates all clauses with the provided assumptions,
    creates a new dossier version, and returns it.

    Request body:
        assumptions: {clause_reference: bool} — overrides for tier 2/3 clauses
        claim_run_id: Optional claim run ID
    """
    service = get_decision_dossier_service()
    dossier = service.evaluate_with_assumptions(
        claim_id=claim_id,
        assumptions=request.assumptions,
        claim_run_id=request.claim_run_id,
    )

    if dossier is None:
        raise HTTPException(
            status_code=500,
            detail=f"Decision evaluation failed for claim {claim_id}",
        )

    return dossier


@router.get("/api/claims/{claim_id}/workbench")
def get_workbench_data(
    claim_id: str,
    claim_run_id: Optional[str] = Query(None, description="Claim run ID (uses latest if omitted)"),
) -> Dict[str, Any]:
    """Get aggregated data for the Claims Workbench view.

    Returns claim facts, screening, coverage analysis, assessment, and
    decision dossier in a single response.
    """
    service = get_decision_dossier_service()
    data = service.get_workbench_data(claim_id, claim_run_id)

    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for claim {claim_id}",
        )

    return data


@router.get("/api/claims-with-dossiers")
def list_claims_with_dossiers() -> List[str]:
    """Return claim IDs that have at least one decision dossier."""
    service = get_decision_dossier_service()
    return service.list_claims_with_dossiers()


@router.get("/api/denial-clauses")
def get_denial_clauses() -> List[Dict[str, Any]]:
    """Get the denial clause registry for the current workspace.

    Returns all clause definitions with metadata (reference, text,
    category, tier, default assumptions).
    """
    service = get_decision_dossier_service()
    return service.get_clause_registry()
