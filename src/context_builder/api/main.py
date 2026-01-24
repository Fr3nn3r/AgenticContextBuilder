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
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncio
from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import FileResponse, HTMLResponse
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
    AuditService,
    AuthService,
    ClaimsService,
    DocPhase,
    DocumentsService,
    EvolutionService,
    InsightsService,
    LabelsService,
    PipelineService,
    PromptConfigService,
    Role,
    TokenCostsService,
    TruthService,
    UploadService,
    UsersService,
    Workspace,
    WorkspaceService,
)
from context_builder.api.services.utils import extract_claim_number, get_global_runs_dir
from context_builder.services.compliance import (
    DecisionStorage,
    LLMCallStorage,
)
from context_builder.services.compliance.config import ComplianceStorageConfig
from context_builder.services.compliance.storage_factory import ComplianceStorageFactory
from context_builder.services.llm_audit import reset_llm_audit_service
from context_builder.storage.workspace_paths import reset_workspace_cache


# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="Extraction QA Console API",
    description="Backend for reviewing and labeling document extractions",
    version="1.0.0",
)

# CORS for React frontend
# In production (Render), frontend is served from same origin, so CORS is less critical
# But we keep localhost for development
_cors_origins = ["http://localhost:5173", "http://localhost:3000"]
if _os.getenv("RENDER_WORKSPACE_PATH"):
    # On Render, allow any onrender.com subdomain for preview deploys
    _cors_origins.append("https://*.onrender.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",  # Allow all Render preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory - now points to output/claims with new structure
# Compute path relative to project root (3 levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Default paths (will be overwritten by active workspace on startup)
DATA_DIR: Path = _PROJECT_ROOT / "output" / "claims"
STAGING_DIR: Path = _PROJECT_ROOT / "output" / ".pending"

# Check for Render persistent disk environment variable
_RENDER_WORKSPACE = _os.getenv("RENDER_WORKSPACE_PATH")


# =============================================================================
# VERSION INFO
# =============================================================================


def _get_app_version() -> str:
    """Read version from pyproject.toml."""
    pyproject_path = _PROJECT_ROOT / "pyproject.toml"
    if not pyproject_path.exists():
        return "unknown"

    try:
        content = pyproject_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("version"):
                # Parse: version = "0.1.0"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"


def _get_git_commit_short() -> Optional[str]:
    """Get short git commit hash (7 chars)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(_PROJECT_ROOT),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# Cache version info at startup
_APP_VERSION = _get_app_version()
_GIT_COMMIT = _get_git_commit_short()


class VersionInfo(BaseModel):
    """Application version information."""
    version: str
    git_commit: Optional[str] = None
    display: str  # Formatted for UI display


def _load_active_workspace_on_startup() -> None:
    """Load the active workspace from registry and set DATA_DIR/STAGING_DIR."""
    global DATA_DIR, STAGING_DIR

    # If running on Render with persistent disk, use that path
    if _RENDER_WORKSPACE:
        workspace_path = Path(_RENDER_WORKSPACE)
        workspace_path.mkdir(parents=True, exist_ok=True)
        DATA_DIR = workspace_path / "claims"
        STAGING_DIR = workspace_path / ".pending"
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[startup] Using Render workspace: {workspace_path}")
        return

    registry_path = _PROJECT_ROOT / ".contextbuilder" / "workspaces.json"

    if not registry_path.exists():
        print(f"[startup] No workspace registry found, using default: {DATA_DIR}")
        return

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        active_id = registry.get("active_workspace_id")
        if not active_id:
            print(f"[startup] No active workspace in registry, using default: {DATA_DIR}")
            return

        for ws in registry.get("workspaces", []):
            if ws.get("workspace_id") == active_id:
                workspace_path = Path(ws.get("path", ""))
                # Resolve relative paths against project root
                if not workspace_path.is_absolute():
                    workspace_path = _PROJECT_ROOT / workspace_path
                if workspace_path.exists():
                    DATA_DIR = workspace_path / "claims"
                    STAGING_DIR = workspace_path / ".pending"
                    print(f"[startup] Loaded active workspace '{active_id}': {workspace_path}")
                else:
                    print(f"[startup] WARNING: Active workspace path does not exist: {workspace_path}")
                return

        print(f"[startup] WARNING: Active workspace '{active_id}' not found in registry")
    except Exception as e:
        print(f"[startup] WARNING: Failed to load workspace registry: {e}")


# Load active workspace on module import
_load_active_workspace_on_startup()


def _resolve_workspace_path(path: str | Path) -> Path:
    """Resolve a workspace path, handling relative paths.

    Args:
        path: Workspace path (absolute or relative to project root).

    Returns:
        Resolved absolute path.
    """
    workspace_path = Path(path)
    if not workspace_path.is_absolute():
        workspace_path = _PROJECT_ROOT / workspace_path
    return workspace_path


def _get_global_config_dir() -> Path:
    """Get global config directory (.contextbuilder/).

    Used for data shared across all workspaces:
    - Users and authentication
    - Sessions
    - Global audit logs
    """
    config_dir = _PROJECT_ROOT / ".contextbuilder"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_workspace_config_dir() -> Path:
    """Get workspace-scoped config directory.

    Used for data specific to the active workspace:
    - Pipeline prompt configs
    - Workspace-specific settings
    """
    # DATA_DIR is {workspace}/claims, so parent is workspace root
    config_dir = DATA_DIR.parent / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_workspace_registry_dir() -> Path:
    """Get workspace-scoped registry directory.

    Used for indexes and batch counters:
    - doc_index.jsonl
    - run_index.jsonl
    - label_index.jsonl
    - batch_counter.json
    """
    # DATA_DIR is {workspace}/claims, so parent is workspace root
    registry_dir = DATA_DIR.parent / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    return registry_dir


def _get_workspace_logs_dir() -> Path:
    """Get workspace-scoped logs directory.

    Used for compliance logs specific to the active workspace:
    - Decision ledger
    - LLM call logs
    """
    # DATA_DIR is {workspace}/claims, so parent is workspace root
    logs_dir = DATA_DIR.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


# Storage abstraction layer (uses indexes when available)
from context_builder.storage import FileStorage, StorageFacade


def get_storage() -> StorageFacade:
    """Get Storage instance (fresh for each request to see new runs)."""
    return StorageFacade.from_storage(FileStorage(DATA_DIR))


def set_data_dir(path: Path):
    """Set the data directory for the API.

    Args:
        path: Base workspace path (e.g., output/).
              DATA_DIR will be set to path/claims.
              STAGING_DIR will be set to path/.pending.
    """
    global DATA_DIR, STAGING_DIR
    DATA_DIR = path / "claims"
    STAGING_DIR = path / ".pending"


def get_claims_service() -> ClaimsService:
    """Get ClaimsService instance."""
    return ClaimsService(DATA_DIR, get_storage)


def get_documents_service() -> DocumentsService:
    """Get DocumentsService instance."""
    return DocumentsService(DATA_DIR, get_storage)


def get_labels_service() -> LabelsService:
    """Get LabelsService instance with workspace-scoped compliance logging and index updates."""
    return LabelsService(
        get_storage,
        ledger_dir=_get_workspace_logs_dir(),
        registry_dir=_get_workspace_registry_dir(),
    )


def get_insights_service() -> InsightsService:
    """Get InsightsService instance."""
    return InsightsService(DATA_DIR)


def get_token_costs_service() -> TokenCostsService:
    """Get TokenCostsService instance for token usage and cost aggregation."""
    return TokenCostsService(_get_workspace_logs_dir())


def get_evolution_service() -> EvolutionService:
    """Get EvolutionService instance.

    Note: DATA_DIR is {workspace}/claims, but version_bundles are stored
    at {workspace}/version_bundles, so we pass the workspace root.
    """
    return EvolutionService(DATA_DIR.parent)


def get_upload_service() -> UploadService:
    """Get UploadService instance with compliance logging."""
    return UploadService(STAGING_DIR, DATA_DIR, ledger_dir=_get_workspace_logs_dir())


def get_truth_service() -> TruthService:
    """Get TruthService instance."""
    return TruthService(DATA_DIR)


# Global PipelineService instance (needs to maintain state across requests)
_pipeline_service: Optional[PipelineService] = None


def get_pipeline_service() -> PipelineService:
    """Get PipelineService singleton instance."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService(DATA_DIR, get_upload_service())
    return _pipeline_service


# Global PromptConfigService instance
_prompt_config_service: Optional[PromptConfigService] = None


def get_prompt_config_service() -> PromptConfigService:
    """Get PromptConfigService singleton instance (workspace-scoped)."""
    global _prompt_config_service
    if _prompt_config_service is None:
        _prompt_config_service = PromptConfigService(_get_workspace_config_dir())
    return _prompt_config_service


# Global AuditService instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get AuditService singleton instance (global, shared across workspaces)."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService(_get_global_config_dir())
    return _audit_service


# Global UsersService instance
_users_service: Optional[UsersService] = None


def get_users_service() -> UsersService:
    """Get UsersService singleton instance (global, shared across workspaces)."""
    global _users_service
    if _users_service is None:
        _users_service = UsersService(_get_global_config_dir())
    return _users_service


# Global AuthService instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get AuthService singleton instance (global, shared across workspaces)."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(_get_global_config_dir(), get_users_service())
    return _auth_service


# Global ComplianceStorageConfig instance
_compliance_config: Optional[ComplianceStorageConfig] = None


def get_compliance_config() -> ComplianceStorageConfig:
    """Get ComplianceStorageConfig singleton instance (workspace-scoped).

    Loads configuration from environment variables with COMPLIANCE_ prefix,
    falling back to workspace logs directory.
    """
    global _compliance_config
    if _compliance_config is None:
        # Try loading from environment, fall back to defaults
        try:
            _compliance_config = ComplianceStorageConfig.from_env()
        except Exception:
            pass

        # If not configured via env, use workspace logs directory
        if _compliance_config is None:
            _compliance_config = ComplianceStorageConfig(
                storage_dir=_get_workspace_logs_dir()
            )
    return _compliance_config


def get_decision_storage() -> DecisionStorage:
    """Get DecisionStorage instance based on compliance config."""
    config = get_compliance_config()
    return ComplianceStorageFactory.create_decision_storage(config)


def get_llm_call_storage() -> LLMCallStorage:
    """Get LLMCallStorage instance based on compliance config."""
    config = get_compliance_config()
    return ComplianceStorageFactory.create_llm_storage(config)


# Global WorkspaceService instance
_workspace_service: Optional[WorkspaceService] = None


def get_workspace_service() -> WorkspaceService:
    """Get WorkspaceService singleton instance."""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService(_PROJECT_ROOT)
    return _workspace_service


def _reset_service_singletons() -> None:
    """Reset workspace-scoped service singletons to pick up new workspace paths.

    Called after workspace switch to ensure services use new paths.

    Note: Global services (users, auth, audit) are NOT reset since they are
    shared across all workspaces and stored in .contextbuilder/.
    """
    global _pipeline_service, _prompt_config_service, _compliance_config

    # Only reset workspace-scoped singletons
    _pipeline_service = None
    _prompt_config_service = None
    _compliance_config = None

    # Reset LLM audit service singleton so it recreates with new workspace path
    reset_llm_audit_service()

    # Reset workspace path cache to force re-reading registry
    reset_workspace_cache()

    # Note: _users_service, _auth_service, _audit_service are global and NOT reset


# =============================================================================
# AUTHENTICATION DEPENDENCY
# =============================================================================


class CurrentUser(BaseModel):
    """Current authenticated user."""
    username: str
    role: str


def get_current_user(authorization: Optional[str] = Header(None)) -> CurrentUser:
    """
    Dependency to get the current authenticated user from the Authorization header.

    Expects: Authorization: Bearer <token>
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]  # Remove "Bearer " prefix

    auth_service = get_auth_service()
    user = auth_service.validate_session(token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return CurrentUser(username=user.username, role=user.role)


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[CurrentUser]:
    """
    Dependency to optionally get the current user.
    Returns None if not authenticated instead of raising an exception.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]
    auth_service = get_auth_service()
    user = auth_service.validate_session(token)

    if not user:
        return None

    return CurrentUser(username=user.username, role=user.role)


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Dependency to require admin role."""
    if current_user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_role(allowed_roles: list[str]):
    """Factory for role-based access control dependency.

    Args:
        allowed_roles: List of role values that are permitted access

    Returns:
        Dependency function that validates user role

    Example:
        @app.get("/api/compliance/ledger")
        def get_ledger(user: CurrentUser = Depends(require_role(["admin", "auditor"]))):
            ...
    """
    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


# Pre-built role checker for compliance endpoints (admin or auditor)
require_compliance_access = require_role([Role.ADMIN.value, Role.AUDITOR.value])


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


@app.get("/api/documents")
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


@app.get("/api/health")
@app.get("/health")  # Keep both for compatibility
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "data_dir": str(DATA_DIR)}


@app.get("/api/version", response_model=VersionInfo)
def get_version():
    """Get application version info.

    Returns version from pyproject.toml and git commit hash.
    """
    display = f"v{_APP_VERSION}"
    if _GIT_COMMIT:
        display = f"v{_APP_VERSION} ({_GIT_COMMIT})"

    return VersionInfo(
        version=_APP_VERSION,
        git_commit=_GIT_COMMIT,
        display=display,
    )


# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response body."""
    token: str
    user: CurrentUser


class UserResponse(BaseModel):
    """User response body (without password)."""
    username: str
    role: str
    created_at: str
    updated_at: str


class CreateUserRequest(BaseModel):
    """Create user request body."""
    username: str
    password: str
    role: str = "reviewer"


class UpdateUserRequest(BaseModel):
    """Update user request body."""
    password: Optional[str] = None
    role: Optional[str] = None


@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    """
    Authenticate user and create session.

    Returns token and user info on success.
    """
    auth_service = get_auth_service()
    result = auth_service.login(request.username, request.password)

    if not result:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, user = result
    return LoginResponse(
        token=token,
        user=CurrentUser(username=user.username, role=user.role),
    )


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    """
    Logout user and invalidate session.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return {"success": True}  # Already logged out

    token = authorization[7:]
    auth_service = get_auth_service()
    auth_service.logout(token)
    return {"success": True}


@app.get("/api/auth/me", response_model=CurrentUser)
def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """
    Get current authenticated user info.
    """
    return current_user


# =============================================================================
# ADMIN ENDPOINTS (User Management)
# =============================================================================


@app.get("/api/admin/users", response_model=List[UserResponse])
def list_users(current_user: CurrentUser = Depends(require_admin)):
    """
    List all users. Requires admin role.
    """
    users_service = get_users_service()
    users = users_service.list_users()
    return [UserResponse(**u.to_public_dict()) for u in users]


@app.post("/api/admin/users", response_model=UserResponse)
def create_user(request: CreateUserRequest, current_user: CurrentUser = Depends(require_admin)):
    """
    Create a new user. Requires admin role.
    """
    users_service = get_users_service()

    # Validate role
    valid_roles = [r.value for r in Role]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
        )

    user = users_service.create_user(
        username=request.username,
        password=request.password,
        role=request.role,
    )

    if not user:
        raise HTTPException(status_code=400, detail="Username already exists")

    return UserResponse(**user.to_public_dict())


@app.put("/api/admin/users/{username}", response_model=UserResponse)
def update_user(
    username: str,
    request: UpdateUserRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Update an existing user. Requires admin role.

    Cannot demote self from admin.
    """
    # Prevent self-demotion from admin
    if username == current_user.username and request.role and request.role != Role.ADMIN.value:
        raise HTTPException(status_code=400, detail="Cannot demote yourself from admin")

    users_service = get_users_service()
    user = users_service.update_user(
        username=username,
        password=request.password,
        role=request.role,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # If password was changed, invalidate user's sessions (except if updating self)
    if request.password and username != current_user.username:
        auth_service = get_auth_service()
        auth_service.invalidate_user_sessions(username)

    return UserResponse(**user.to_public_dict())


@app.delete("/api/admin/users/{username}")
def delete_user(username: str, current_user: CurrentUser = Depends(require_admin)):
    """
    Delete a user. Requires admin role.

    Cannot delete self or last admin.
    """
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    users_service = get_users_service()
    success = users_service.delete_user(username)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="User not found or cannot delete (last admin)",
        )

    # Invalidate deleted user's sessions
    auth_service = get_auth_service()
    auth_service.invalidate_user_sessions(username)

    return {"success": True, "username": username}


# =============================================================================
# WORKSPACE MANAGEMENT ENDPOINTS
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


@app.get("/api/admin/workspaces", response_model=List[WorkspaceResponse])
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


@app.get("/api/admin/workspaces/active", response_model=WorkspaceResponse)
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


@app.post("/api/admin/workspaces", response_model=WorkspaceResponse)
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


@app.post("/api/admin/workspaces/{workspace_id}/activate", response_model=ActivateWorkspaceResponse)
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
    audit_service = get_audit_service()

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


@app.delete("/api/admin/workspaces/{workspace_id}")
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


@app.post("/api/admin/index/rebuild")
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


@app.get("/api/docs/{doc_id}/runs")
def get_doc_runs(doc_id: str, claim_id: str = Query(..., description="Claim ID containing the document")):
    """
    Get all pipeline runs that processed this document.

    Returns list of runs with run_id, timestamp, model, status, and extraction summary.
    Used by the Document Detail page to show run history.
    """
    return get_documents_service().get_doc_runs(doc_id, claim_id)


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
# TOKEN COST ENDPOINTS
# =============================================================================


@app.get("/api/insights/costs/overview")
def get_costs_overview():
    """
    Get overall token usage and cost summary.

    Returns:
    - total_cost_usd: Total cost across all LLM calls
    - total_tokens: Total tokens (prompt + completion)
    - total_prompt_tokens, total_completion_tokens: Token breakdown
    - total_calls: Number of LLM API calls
    - docs_processed: Unique documents processed
    - avg_cost_per_doc, avg_cost_per_call: Average costs
    - primary_model: Most frequently used model
    """
    return get_token_costs_service().get_overview()


@app.get("/api/insights/costs/by-operation")
def get_costs_by_operation():
    """
    Get token usage and costs broken down by operation type.

    Operations: classification, extraction, vision_ocr

    Returns list with:
    - operation: Operation type name
    - tokens, prompt_tokens, completion_tokens: Token counts
    - cost_usd: Total cost for this operation
    - call_count: Number of calls
    - percentage: Percentage of total cost
    """
    return get_token_costs_service().get_by_operation()


@app.get("/api/insights/costs/by-run")
def get_costs_by_run(limit: int = Query(20, ge=1, le=100)):
    """
    Get token usage and costs per pipeline run.

    Args:
        limit: Maximum number of runs to return (default 20)

    Returns list sorted by timestamp (newest first) with:
    - run_id, timestamp, model
    - claims_count, docs_count: Scope of run
    - tokens, cost_usd: Usage metrics
    - avg_cost_per_doc: Efficiency metric
    """
    return get_token_costs_service().get_by_run(limit)


@app.get("/api/insights/costs/by-claim")
def get_costs_by_claim(run_id: Optional[str] = Query(None)):
    """
    Get token costs per claim.

    Args:
        run_id: Optional filter by run ID

    Returns list sorted by cost (highest first) with:
    - claim_id, docs_count, tokens, cost_usd
    """
    return get_token_costs_service().get_by_claim(run_id)


@app.get("/api/insights/costs/by-doc")
def get_costs_by_doc(
    claim_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    """
    Get token costs per document.

    Args:
        claim_id: Optional filter by claim ID
        run_id: Optional filter by run ID

    Returns list sorted by cost (highest first) with:
    - doc_id, claim_id, tokens, cost_usd, operations
    """
    return get_token_costs_service().get_by_doc(claim_id, run_id)


@app.get("/api/insights/costs/daily-trend")
def get_costs_daily_trend(days: int = Query(30, ge=1, le=90)):
    """
    Get daily token costs for trend chart.

    Args:
        days: Number of days to include (default 30)

    Returns list in chronological order with:
    - date: YYYY-MM-DD
    - tokens, cost_usd, call_count
    """
    return get_token_costs_service().get_daily_trend(days)


@app.get("/api/insights/costs/by-model")
def get_costs_by_model():
    """
    Get token usage and costs broken down by model.

    Returns list sorted by cost (highest first) with:
    - model: Model name/identifier
    - tokens, cost_usd, call_count
    - percentage: Percentage of total cost
    """
    return get_token_costs_service().get_by_model()


# =============================================================================
# TRUTH ENDPOINTS
# =============================================================================

@app.get("/api/truth")
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
# EVOLUTION ENDPOINTS
# =============================================================================


@app.get("/api/evolution/timeline")
def get_evolution_timeline():
    """Get pipeline evolution timeline with scope and accuracy metrics.

    Returns timeline data showing how the pipeline's scope (doc types, fields)
    and accuracy have evolved across version bundles over time.
    """
    return get_evolution_service().get_evolution_timeline()


@app.get("/api/evolution/doc-types")
def get_evolution_doc_types():
    """Get doc type evolution matrix.

    Returns per-doc-type evolution data showing field counts and accuracy
    across all spec versions.
    """
    return get_evolution_service().get_doc_type_matrix()


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


@app.get("/api/classification/doc/{doc_id}")
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


@app.get("/api/classification/doc-types")
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
    stages: List[str] = ["ingest", "classify", "extract"]
    prompt_config_id: Optional[str] = None
    force_overwrite: bool = False
    compute_metrics: bool = True
    dry_run: bool = False


@app.post("/api/pipeline/run")
async def start_pipeline_run(
    request: PipelineRunRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Start pipeline execution for pending claims.

    Args:
        request: Pipeline run request with claim_ids and model

    Returns:
        run_id for tracking progress

    Requires: Admin role
    """
    pipeline_service = get_pipeline_service()
    upload_service = get_upload_service()

    # Validate claim_ids is not empty
    if not request.claim_ids:
        raise HTTPException(status_code=400, detail="claim_ids cannot be empty")

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
        stages=request.stages,
        prompt_config_id=request.prompt_config_id,
        force_overwrite=request.force_overwrite,
        compute_metrics=request.compute_metrics,
        dry_run=request.dry_run,
        progress_callback=broadcast_progress,
    )

    # Audit log the pipeline start
    audit_service = get_audit_service()
    audit_service.log(
        action=f"pipeline.started (claims: {len(request.claim_ids)}, model: {request.model})",
        user=current_user.username,
        action_type="pipeline.started",
        entity_type="run",
        entity_id=run_id,
    )

    status = "dry_run" if request.dry_run else "running"
    return {"run_id": run_id, "status": status}


@app.get("/api/pipeline/claims")
def list_pipeline_claims():
    """
    List claims available for pipeline processing.

    Returns pending claims from staging area with doc counts and last run info.
    This is the claims selector for the Pipeline Control Center.
    """
    from datetime import datetime, timezone

    upload_service = get_upload_service()
    pipeline_service = get_pipeline_service()

    pending_claims = upload_service.list_pending_claims()

    # Get all runs to find last run per claim
    all_runs = pipeline_service.get_all_runs()
    claim_last_run: dict[str, tuple[str, str]] = {}  # claim_id -> (run_id, started_at)
    for run in all_runs:
        for claim_id in run.claim_ids:
            if claim_id not in claim_last_run or (run.started_at and run.started_at > claim_last_run[claim_id][1]):
                claim_last_run[claim_id] = (run.run_id, run.started_at or "")

    def format_relative_time(iso_time: str) -> str:
        """Convert ISO timestamp to relative time string."""
        if not iso_time:
            return "never processed"
        try:
            dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - dt
            if delta.days > 30:
                return f"{delta.days // 30}mo ago"
            elif delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m ago"
            else:
                return "just now"
        except Exception:
            return "never processed"

    result = []
    for claim in pending_claims:
        last_run_info = claim_last_run.get(claim.claim_id)
        result.append({
            "claim_id": claim.claim_id,
            "doc_count": len(claim.documents),
            "last_run": format_relative_time(last_run_info[1]) if last_run_info else "never processed",
            "last_run_id": last_run_info[0] if last_run_info else None,
            "is_pending": True,
        })

    return result


@app.post("/api/pipeline/cancel/{run_id}")
async def cancel_pipeline(
    run_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Cancel a running pipeline.

    Args:
        run_id: Run ID to cancel

    Returns:
        Cancellation status

    Requires: Admin role
    """
    pipeline_service = get_pipeline_service()

    if await pipeline_service.cancel_pipeline(run_id):
        # Audit log the cancellation
        audit_service = get_audit_service()
        audit_service.log(
            action="pipeline.cancelled",
            user=current_user.username,
            action_type="pipeline.cancelled",
            entity_type="run",
            entity_id=run_id,
        )
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


def _generate_friendly_name(run_id: str) -> str:
    """Return the batch ID as the friendly name (enterprise format).

    The batch ID format BATCH-YYYYMMDD-NNN is already professional and sortable.
    """
    return run_id


def _format_duration(ms: int) -> str:
    """Format milliseconds as human-readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds}s"


@app.get("/api/pipeline/runs")
def list_pipeline_runs():
    """
    List all tracked pipeline runs with enhanced metadata.

    Returns:
        List of run summaries with friendly names, progress, timing, and errors
    """
    from context_builder.api.services.pipeline import DocPhase

    pipeline_service = get_pipeline_service()
    runs = pipeline_service.get_all_runs()

    result = []
    for run in runs:
        # Calculate stage progress from doc phases
        docs_done = sum(1 for d in run.docs.values() if d.phase == DocPhase.DONE)
        docs_failed = sum(1 for d in run.docs.values() if d.phase == DocPhase.FAILED)
        total_docs = len(run.docs) or 1

        # Calculate overall progress percentage
        progress_pct = int((docs_done + docs_failed) / total_docs * 100)

        # Stage progress (simplified: based on overall completion)
        # In a real impl, you'd track per-stage completion
        stage_progress = {
            "ingest": 100 if progress_pct > 0 else 0,
            "classify": 100 if progress_pct > 30 else 0,
            "extract": progress_pct,
        }

        # Calculate duration
        duration_seconds = None
        if run.started_at and run.completed_at:
            from datetime import datetime
            try:
                start = datetime.fromisoformat(run.started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(run.completed_at.replace("Z", "+00:00"))
                duration_seconds = int((end - start).total_seconds())
            except Exception:
                pass

        # Collect errors
        errors = []
        for key, doc in run.docs.items():
            if doc.phase == DocPhase.FAILED and doc.error:
                stage = doc.failed_at_stage.value if doc.failed_at_stage else "unknown"
                errors.append({
                    "doc": doc.filename,
                    "stage": stage,
                    "message": doc.error,
                })

        # Format stage timings
        stage_timings = {
            stage: _format_duration(ms)
            for stage, ms in run.stage_timings.items()
        } if run.stage_timings else {}

        result.append({
            "run_id": run.run_id,
            "friendly_name": _generate_friendly_name(run.run_id),
            "status": run.status.value,
            "claim_ids": run.claim_ids,
            "claims_count": len(run.claim_ids),
            "docs_total": len(run.docs),
            "docs_processed": docs_done + docs_failed,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "duration_seconds": duration_seconds,
            "stage_progress": stage_progress,
            "stage_timings": stage_timings,
            "reuse": run.reuse_counts,
            "cost_estimate_usd": run.cost_estimate_usd,
            "prompt_config": run.prompt_config_id,
            "errors": errors,
            "summary": run.summary,
            "model": run.model,
        })

    # Sort by started_at descending (newest first)
    result.sort(key=lambda r: r["started_at"] or "", reverse=True)
    return result


@app.delete("/api/pipeline/runs/{run_id}")
def delete_pipeline_run(
    run_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Delete a completed/failed/cancelled pipeline run.

    Args:
        run_id: Run ID to delete

    Returns:
        Deletion status

    Requires: Admin role
    """
    pipeline_service = get_pipeline_service()

    if pipeline_service.delete_run(run_id):
        # Audit log the deletion
        audit_service = get_audit_service()
        audit_service.log(
            action="pipeline.deleted",
            user=current_user.username,
            action_type="pipeline.deleted",
            entity_type="run",
            entity_id=run_id,
        )
        return {"status": "deleted", "run_id": run_id}

    raise HTTPException(
        status_code=400,
        detail=f"Cannot delete run {run_id}: not found or still running"
    )


# =============================================================================
# PROMPT CONFIG ENDPOINTS
# =============================================================================


class PromptConfigRequest(BaseModel):
    """Request body for creating a prompt config."""
    name: str
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096


class PromptConfigUpdateRequest(BaseModel):
    """Request body for updating a prompt config."""
    name: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@app.get("/api/pipeline/configs")
def list_prompt_configs():
    """List all prompt configurations."""
    service = get_prompt_config_service()
    configs = service.list_configs()
    return [
        {
            "id": c.id,
            "name": c.name,
            "model": c.model,
            "temperature": c.temperature,
            "max_tokens": c.max_tokens,
            "is_default": c.is_default,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in configs
    ]


@app.get("/api/pipeline/configs/{config_id}")
def get_prompt_config(config_id: str):
    """Get a single prompt configuration."""
    service = get_prompt_config_service()
    config = service.get_config(config_id)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")

    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@app.post("/api/pipeline/configs")
def create_prompt_config(request: PromptConfigRequest):
    """Create a new prompt configuration."""
    service = get_prompt_config_service()
    config = service.create_config(
        name=request.name,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@app.put("/api/pipeline/configs/{config_id}")
def update_prompt_config(config_id: str, request: PromptConfigUpdateRequest):
    """Update an existing prompt configuration."""
    service = get_prompt_config_service()

    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.model is not None:
        updates["model"] = request.model
    if request.temperature is not None:
        updates["temperature"] = request.temperature
    if request.max_tokens is not None:
        updates["max_tokens"] = request.max_tokens

    config = service.update_config(config_id, updates)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")

    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@app.delete("/api/pipeline/configs/{config_id}")
def delete_prompt_config(config_id: str):
    """Delete a prompt configuration."""
    service = get_prompt_config_service()

    if service.delete_config(config_id):
        return {"status": "deleted", "config_id": config_id}

    raise HTTPException(
        status_code=400,
        detail=f"Cannot delete config {config_id}: not found or is the last config"
    )


@app.post("/api/pipeline/configs/{config_id}/set-default")
def set_default_prompt_config(config_id: str):
    """Set a prompt configuration as the default."""
    service = get_prompt_config_service()
    config = service.set_default(config_id)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")

    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================


@app.get("/api/pipeline/audit")
def list_audit_entries(
    action_type: Optional[str] = Query(None, description="Filter by action type (e.g., run_started)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (run, config)"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter entries after"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
):
    """
    List audit log entries.

    Returns entries sorted by timestamp descending (newest first).
    """
    service = get_audit_service()
    entries = service.list_entries(
        action_type=action_type,
        entity_type=entity_type,
        since=since,
        limit=limit,
    )
    return [
        {
            "timestamp": e.timestamp,
            "user": e.user,
            "action": e.action,
            "action_type": e.action_type,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
        }
        for e in entries
    ]


# =============================================================================
# COMPLIANCE VERIFICATION ENDPOINTS
# =============================================================================


@app.get("/api/compliance/ledger/verify")
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


@app.delete("/api/compliance/ledger/reset")
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


@app.get("/api/compliance/ledger/decisions")
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
    import traceback
    from context_builder.schemas.decision_record import DecisionType
    from context_builder.services.compliance.interfaces import DecisionQuery

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
            from datetime import datetime
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


@app.get("/api/compliance/version-bundles")
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


@app.get("/api/compliance/version-bundles/{run_id}")
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


@app.get("/api/compliance/config-history")
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


@app.get("/api/compliance/truth-history/{file_md5}")
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

    store = TruthStore(DATA_DIR)
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


@app.get("/api/compliance/label-history/{doc_id}")
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
        fs = FileStorage(DATA_DIR)
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
    print(f"[WS] Connection attempt for run_id={run_id}")
    await ws_manager.connect(websocket, run_id)
    print(f"[WS] Connected for run_id={run_id}")

    try:
        # Send current state on connect (for reconnection sync)
        pipeline_service = get_pipeline_service()
        run = pipeline_service.get_run_status(run_id)
        print(f"[WS] Got run status: {run.status.value if run else 'NOT_FOUND'}")

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
            print(f"[WS] Sent sync message for run_id={run_id}")

            # If run already completed, send completion and close
            if run.status.value in ("completed", "failed", "cancelled"):
                print(f"[WS] Run already {run.status.value}, sending completion")
                await websocket.send_json({
                    "type": "run_complete",
                    "run_id": run_id,
                    "status": run.status.value,
                    "summary": run.summary,
                })
                return  # Close connection - run is done
        else:
            print(f"[WS] Run {run_id} not found in active runs")
            # Run not found - send error and close
            await websocket.send_json({
                "type": "error",
                "message": f"Run {run_id} not found",
            })
            return

        # Keep connection alive while run is in progress
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
                    print(f"[WS] Failed to send ping, closing")
                    break

            # Check if run is complete
            run = pipeline_service.get_run_status(run_id)
            if run and run.status.value in ("completed", "failed", "cancelled"):
                print(f"[WS] Run {run_id} completed with status {run.status.value}")
                await websocket.send_json({
                    "type": "run_complete",
                    "run_id": run_id,
                    "status": run.status.value,
                    "summary": run.summary,
                })
                break  # Exit loop after sending completion

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected for run_id={run_id}")
    except Exception as e:
        print(f"[WS] Error for run_id={run_id}: {e}")
    finally:
        ws_manager.disconnect(websocket, run_id)
        print(f"[WS] Cleaned up connection for run_id={run_id}")


# =============================================================================
# STATIC FILE SERVING (Production)
# =============================================================================
# Serve React frontend in production when ui/dist exists

_UI_DIST_DIR = _PROJECT_ROOT / "ui" / "dist"

if _UI_DIST_DIR.exists() and _UI_DIST_DIR.is_dir():
    print(f"[startup] Serving static frontend from {_UI_DIST_DIR}")

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_UI_DIST_DIR / "assets"), name="assets")

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA for all non-API routes."""
        # Don't intercept API routes or WebSocket
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404)

        # Serve index.html for SPA routing
        index_path = _UI_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path, media_type="text/html")
        raise HTTPException(status_code=404, detail="Frontend not found")
else:
    print(f"[startup] No frontend build found at {_UI_DIST_DIR} (dev mode)")
