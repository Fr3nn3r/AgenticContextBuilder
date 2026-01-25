"""Admin workspace management endpoints: CRUD and activation."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from context_builder.api.dependencies import (
    CurrentUser,
    _reset_service_singletons,
    get_audit_service,
    get_auth_service,
    get_project_root,
    get_workspace_service,
    require_admin,
    set_data_dir,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _resolve_workspace_path(path: str | Path) -> Path:
    """Resolve a workspace path, handling relative paths.

    Args:
        path: Workspace path (absolute or relative to project root).

    Returns:
        Resolved absolute path.
    """
    workspace_path = Path(path)
    if not workspace_path.is_absolute():
        workspace_path = get_project_root() / workspace_path
    return workspace_path


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class WorkspaceResponse(BaseModel):
    """Workspace response body."""

    workspace_id: str
    name: str
    path: str
    status: str
    created_at: str
    last_accessed_at: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = False


class CreateWorkspaceRequest(BaseModel):
    """Create workspace request body."""

    name: str
    path: Optional[str] = None  # Auto-generated if not provided
    description: Optional[str] = None


class ActivateWorkspaceResponse(BaseModel):
    """Activate workspace response."""

    status: str
    workspace_id: str
    sessions_cleared: int
    previous_workspace_id: Optional[str] = None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/workspaces", response_model=List[WorkspaceResponse])
def list_workspaces(current_user: CurrentUser = Depends(require_admin)):
    """List all registered workspaces. Requires admin role."""
    workspace_service = get_workspace_service()
    workspaces = workspace_service.list_workspaces()
    active_id = workspace_service.get_active_workspace_id()
    return [
        WorkspaceResponse(
            workspace_id=ws.workspace_id,
            name=ws.name,
            path=ws.path,
            status=ws.status,
            created_at=ws.created_at,
            last_accessed_at=ws.last_accessed_at,
            description=ws.description,
            is_active=(ws.workspace_id == active_id),
        )
        for ws in workspaces
    ]


@router.get("/workspaces/active", response_model=WorkspaceResponse)
def get_active_workspace(current_user: CurrentUser = Depends(require_admin)):
    """Get the currently active workspace."""
    workspace_service = get_workspace_service()
    workspace = workspace_service.get_active_workspace()
    if not workspace:
        raise HTTPException(status_code=404, detail="No active workspace")
    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        path=workspace.path,
        status=workspace.status,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
        description=workspace.description,
        is_active=True,
    )


@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """Create a new workspace. Requires admin role."""
    workspace_service = get_workspace_service()

    # Validate path is absolute if provided
    if request.path and not Path(request.path).is_absolute():
        raise HTTPException(
            status_code=400,
            detail="Workspace path must be absolute",
        )

    workspace = workspace_service.create_workspace(
        name=request.name,
        path=request.path,  # None triggers auto-generation
        description=request.description,
    )

    if not workspace:
        raise HTTPException(
            status_code=400,
            detail="Workspace already exists at this path",
        )

    return WorkspaceResponse(
        workspace_id=workspace.workspace_id,
        name=workspace.name,
        path=workspace.path,
        status=workspace.status,
        created_at=workspace.created_at,
        last_accessed_at=workspace.last_accessed_at,
        description=workspace.description,
        is_active=False,
    )


@router.post("/workspaces/{workspace_id}/activate", response_model=ActivateWorkspaceResponse)
def activate_workspace(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Activate a workspace. Clears ALL sessions (logs everyone out).

    This is a destructive operation - all users will need to re-login.
    """
    workspace_service = get_workspace_service()
    auth_service = get_auth_service()

    # Get previous workspace for response
    previous_id = workspace_service.get_active_workspace_id()

    # Activate workspace
    workspace = workspace_service.activate_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Update DATA_DIR and STAGING_DIR (resolve relative paths against project root)
    workspace_path = _resolve_workspace_path(workspace.path)
    set_data_dir(workspace_path)

    # Ensure workspace directories exist
    (workspace_path / "config").mkdir(parents=True, exist_ok=True)
    (workspace_path / "logs").mkdir(parents=True, exist_ok=True)

    # Clear ALL sessions (including current user's)
    sessions_cleared = auth_service.clear_all_sessions()

    # Reset service singletons to pick up new paths
    _reset_service_singletons()

    # Audit log (after reset, creates new audit service instance)
    get_audit_service().log(
        action=f"workspace.activated (from={previous_id}, to={workspace_id})",
        user=current_user.username,
        action_type="workspace.activated",
        entity_type="workspace",
        entity_id=workspace_id,
    )

    return ActivateWorkspaceResponse(
        status="activated",
        workspace_id=workspace_id,
        sessions_cleared=sessions_cleared,
        previous_workspace_id=previous_id,
    )


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Delete a workspace from the registry.

    Does NOT delete the workspace files on disk - only removes from registry.
    Cannot delete the active workspace.
    """
    workspace_service = get_workspace_service()

    # Cannot delete active workspace
    if workspace_service.get_active_workspace_id() == workspace_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the active workspace. Activate a different workspace first.",
        )

    success = workspace_service.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {"status": "deleted", "workspace_id": workspace_id}


@router.post("/index/rebuild")
def rebuild_index(current_user: CurrentUser = Depends(require_admin)):
    """
    Rebuild all indexes for the active workspace.

    Scans claims, labels, and runs directories to regenerate:
    - doc_index.jsonl
    - label_index.jsonl
    - run_index.jsonl
    - registry_meta.json

    Requires admin role.
    """
    from context_builder.storage.index_builder import build_all_indexes

    workspace_service = get_workspace_service()
    workspace = workspace_service.get_active_workspace()

    if not workspace:
        raise HTTPException(status_code=404, detail="No active workspace")

    output_dir = _resolve_workspace_path(workspace.path)
    if not output_dir.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Workspace path does not exist: {output_dir}",
        )

    # Build all indexes
    stats = build_all_indexes(output_dir)

    return {
        "status": "success",
        "workspace_id": workspace.workspace_id,
        "stats": stats,
    }
