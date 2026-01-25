"""Compliance router - endpoints for audit, verification, and compliance."""

import traceback
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from context_builder.api.dependencies import (
    CurrentUser,
    _get_workspace_logs_dir,
    get_data_dir,
    get_decision_storage,
    get_project_root,
    get_prompt_config_service,
    get_storage,
    get_workspace_service,
    require_admin,
    require_compliance_access,
)
from context_builder.schemas.decision_record import DecisionType
from context_builder.services.compliance.interfaces import DecisionQuery

router = APIRouter(tags=["compliance"])


def _resolve_workspace_path(path):
    """Resolve a workspace path, handling relative paths."""
    from pathlib import Path
    workspace_path = Path(path)
    if not workspace_path.is_absolute():
        workspace_path = get_project_root() / workspace_path
    return workspace_path


@router.get("/api/compliance/ledger/verify")
def verify_decision_ledger(
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    Verify the integrity of the decision ledger hash chain.

    Requires: admin or auditor role

    Returns:
    - valid: Whether the chain is intact
    - record_count: Number of records in the ledger
    - break_at: Record index where chain broke (if invalid)
    - reason: Reason for validation failure (if invalid)
    """
    storage = get_decision_storage()
    return storage.verify_integrity()


@router.delete("/api/compliance/ledger/reset")
def reset_decision_ledger(
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Reset the decision ledger (delete all records).

    Requires: admin role (not just auditor)

    WARNING: This permanently deletes all compliance records in the active workspace.
    Use only for development/testing purposes.

    Returns:
    - status: "reset"
    - records_deleted: Number of records that were deleted
    """
    logs_dir = _get_workspace_logs_dir()
    decisions_file = logs_dir / "decisions.jsonl"

    records_deleted = 0
    if decisions_file.exists():
        # Count records before deletion
        try:
            with open(decisions_file, "r", encoding="utf-8") as f:
                records_deleted = sum(1 for line in f if line.strip())
        except Exception:
            pass
        # Delete the file
        decisions_file.unlink()

    return {
        "status": "reset",
        "records_deleted": records_deleted,
    }


@router.get("/api/compliance/ledger/decisions")
def list_decisions(
    decision_type: Optional[str] = Query(None, description="Filter by type: classification, extraction, human_review, override"),
    doc_id: Optional[str] = Query(None, description="Filter by document ID"),
    claim_id: Optional[str] = Query(None, description="Filter by claim ID"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter entries after"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    List decision records from the compliance ledger.

    Requires: admin or auditor role

    Returns decisions sorted by timestamp (newest first).
    """
    try:
        storage = get_decision_storage()

        # Map string to DecisionType enum
        dtype = None
        if decision_type:
            type_map = {
                "classification": DecisionType.CLASSIFICATION,
                "extraction": DecisionType.EXTRACTION,
                "human_review": DecisionType.HUMAN_REVIEW,
                "override": DecisionType.OVERRIDE,
            }
            dtype = type_map.get(decision_type.lower())

        # Build query filters
        query = DecisionQuery(
            decision_type=dtype,
            doc_id=doc_id,
            claim_id=claim_id,
            limit=limit,
        )

        records = storage.query(query)

        # Filter by since if provided
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            records = [r for r in records if r.created_at and datetime.fromisoformat(r.created_at.replace("Z", "+00:00")) >= since_dt]

        result = []
        for r in records:
            try:
                result.append({
                    "decision_id": r.decision_id,
                    "decision_type": r.decision_type.value if hasattr(r.decision_type, 'value') else r.decision_type,
                    "timestamp": r.created_at,
                    "claim_id": r.claim_id,
                    "doc_id": r.doc_id,
                    "actor_type": r.actor_type,
                    "actor_id": r.actor_id,
                    "rationale": {
                        "summary": r.rationale.summary if r.rationale else None,
                        "confidence": r.rationale.confidence if r.rationale else None,
                    },
                    "prev_hash": r.previous_hash[:16] + "..." if r.previous_hash else None,
                })
            except Exception as e:
                print(f"[list_decisions] Error processing record {r.decision_id}: {e}")
                print(f"[list_decisions] Record data: {r}")
                raise
        return result
    except Exception as e:
        print(f"[list_decisions] ERROR: {e}")
        print(f"[list_decisions] Traceback: {traceback.format_exc()}")
        raise


@router.get("/api/compliance/version-bundles")
def list_version_bundles(
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    List all version bundle snapshots.

    Requires: admin or auditor role

    Returns list of run IDs with version bundles.
    """
    from context_builder.storage.version_bundles import get_version_bundle_store

    # Use active workspace path for version bundles
    workspace_service = get_workspace_service()
    workspace = workspace_service.get_active_workspace()
    if not workspace:
        raise HTTPException(status_code=500, detail="No active workspace configured")

    store = get_version_bundle_store(_resolve_workspace_path(workspace.path))
    run_ids = store.list_bundles()

    bundles = []
    for run_id in run_ids:
        bundle = store.get_version_bundle(run_id)
        if bundle:
            bundles.append({
                "run_id": run_id,
                "bundle_id": bundle.bundle_id,
                "created_at": bundle.created_at,
                "git_commit": bundle.git_commit[:8] if bundle.git_commit else None,
                "git_dirty": bundle.git_dirty,
                "model_name": bundle.model_name,
                "extractor_version": bundle.extractor_version,
            })

    return sorted(bundles, key=lambda b: b["created_at"] or "", reverse=True)


@router.get("/api/compliance/version-bundles/{run_id}")
def get_version_bundle(
    run_id: str,
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    Get full version bundle details for a specific run.

    Requires: admin or auditor role

    Returns all captured version information for reproducibility.
    """
    from context_builder.storage.version_bundles import get_version_bundle_store

    # Use active workspace path for version bundles
    workspace_service = get_workspace_service()
    workspace = workspace_service.get_active_workspace()
    if not workspace:
        raise HTTPException(status_code=500, detail="No active workspace configured")

    store = get_version_bundle_store(_resolve_workspace_path(workspace.path))
    bundle = store.get_version_bundle(run_id)

    if not bundle:
        raise HTTPException(status_code=404, detail=f"Version bundle not found for run: {run_id}")

    return {
        "bundle_id": bundle.bundle_id,
        "run_id": run_id,
        "created_at": bundle.created_at,
        "git_commit": bundle.git_commit,
        "git_dirty": bundle.git_dirty,
        "contextbuilder_version": bundle.contextbuilder_version,
        "extractor_version": bundle.extractor_version,
        "model_name": bundle.model_name,
        "model_version": bundle.model_version,
        "prompt_template_hash": bundle.prompt_template_hash,
        "extraction_spec_hash": bundle.extraction_spec_hash,
    }


@router.get("/api/compliance/config-history")
def get_config_change_history(
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    Get prompt configuration change history.

    Requires: admin or auditor role

    Returns append-only log of all config changes for audit.
    """
    service = get_prompt_config_service()
    history = service.get_config_history()

    # Return most recent first, limited
    return history[-limit:][::-1]


@router.get("/api/compliance/truth-history/{file_md5}")
def get_truth_history(
    file_md5: str,
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    Get truth version history for a specific file.

    Requires: admin or auditor role

    Returns all historical versions of ground truth labels.
    """
    from context_builder.storage.truth_store import TruthStore

    store = TruthStore(get_data_dir())
    history = store.get_truth_history(file_md5)

    return {
        "file_md5": file_md5,
        "version_count": len(history),
        "versions": [
            {
                "version_number": h.get("_version_metadata", {}).get("version_number"),
                "saved_at": h.get("_version_metadata", {}).get("saved_at"),
                "reviewer": h.get("review", {}).get("reviewer"),
                "field_count": len(h.get("field_labels", [])),
            }
            for h in history
        ],
    }


@router.get("/api/compliance/label-history/{doc_id}")
def get_label_history(
    doc_id: str,
    _user: CurrentUser = Depends(require_compliance_access),
):
    """
    Get label version history for a specific document.

    Requires: admin or auditor role

    Returns all historical versions of labels for audit.
    """
    storage = get_storage()

    # Access underlying FileStorage for history method
    if hasattr(storage, 'label_store') and hasattr(storage.label_store, 'get_label_history'):
        history = storage.label_store.get_label_history(doc_id)
    else:
        # Fallback for FileStorage directly
        from context_builder.storage import FileStorage
        fs = FileStorage(get_data_dir())
        history = fs.get_label_history(doc_id)

    return {
        "doc_id": doc_id,
        "version_count": len(history),
        "versions": [
            {
                "version_number": h.get("_version_metadata", {}).get("version_number"),
                "saved_at": h.get("_version_metadata", {}).get("saved_at"),
                "reviewer": h.get("review", {}).get("reviewer"),
                "field_count": len(h.get("field_labels", [])),
            }
            for h in history
        ],
    }
