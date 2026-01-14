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
from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile, File, WebSocket, WebSocketDisconnect
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
    AuditService,
    AuthService,
    ClaimsService,
    DocPhase,
    DocumentsService,
    InsightsService,
    LabelsService,
    PipelineService,
    PromptConfigService,
    Role,
    TruthService,
    UploadService,
    UsersService,
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
    """Get PromptConfigService singleton instance."""
    global _prompt_config_service
    if _prompt_config_service is None:
        config_dir = _PROJECT_ROOT / "output" / "config"
        _prompt_config_service = PromptConfigService(config_dir)
    return _prompt_config_service


# Global AuditService instance
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    """Get AuditService singleton instance."""
    global _audit_service
    if _audit_service is None:
        config_dir = _PROJECT_ROOT / "output" / "config"
        _audit_service = AuditService(config_dir)
    return _audit_service


# Global UsersService instance
_users_service: Optional[UsersService] = None


def get_users_service() -> UsersService:
    """Get UsersService singleton instance."""
    global _users_service
    if _users_service is None:
        config_dir = _PROJECT_ROOT / "output" / "config"
        _users_service = UsersService(config_dir)
    return _users_service


# Global AuthService instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """Get AuthService singleton instance."""
    global _auth_service
    if _auth_service is None:
        config_dir = _PROJECT_ROOT / "output" / "config"
        _auth_service = AuthService(config_dir, get_users_service())
    return _auth_service


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
    doc_bundle = storage.doc_store.get_doc(doc_id)
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
    doc_text = storage.doc_store.get_doc_text(doc_id)
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
    """Generate a human-friendly name from run_id using adjective-animal pattern."""
    import hashlib

    adjectives = [
        "swift", "bold", "calm", "crisp", "amber", "quiet", "brave", "fresh",
        "clear", "warm", "cool", "bright", "quick", "keen", "wise", "fair",
    ]
    animals = [
        "falcon", "tiger", "eagle", "panda", "raven", "wolf", "hawk", "bear",
        "lion", "fox", "deer", "owl", "crane", "dove", "heron", "lynx",
    ]

    # Use hash of run_id for consistent name generation
    h = hashlib.md5(run_id.encode()).hexdigest()
    adj_idx = int(h[:4], 16) % len(adjectives)
    animal_idx = int(h[4:8], 16) % len(animals)
    num = int(h[8:10], 16) % 100

    return f"{adjectives[adj_idx]}-{animals[animal_idx]}-{num}"


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
