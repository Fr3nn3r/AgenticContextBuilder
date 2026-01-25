"""FastAPI dependencies for the Extraction QA Console API.

This module provides:
- Path helper functions for workspace directories
- Storage layer access
- Service instance getters (with singleton patterns where needed)
- Authentication dependencies
"""

from pathlib import Path
from typing import Optional

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from context_builder.api.services import (
    AssessmentService,
    AuditService,
    AuthService,
    ClaimsService,
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
    WorkspaceService,
)
from context_builder.services.compliance import (
    DecisionStorage,
    LLMCallStorage,
)
from context_builder.services.compliance.config import ComplianceStorageConfig
from context_builder.services.compliance.storage_factory import ComplianceStorageFactory
from context_builder.services.llm_audit import reset_llm_audit_service
from context_builder.startup import (
    ensure_initialized,
    get_data_dir as _startup_get_data_dir,
    get_project_root as _startup_get_project_root,
    get_staging_dir as _startup_get_staging_dir,
    set_workspace_paths,
)
from context_builder.storage import FileStorage, StorageFacade
from context_builder.storage.workspace_paths import reset_workspace_cache


# =============================================================================
# PATH HELPERS
# =============================================================================


def get_project_root() -> Path:
    """Get the project root directory."""
    return _startup_get_project_root()


def get_data_dir() -> Path:
    """Get the current data directory (claims folder)."""
    return _startup_get_data_dir()


def get_staging_dir() -> Path:
    """Get the current staging directory."""
    return _startup_get_staging_dir()


def _get_global_config_dir() -> Path:
    """Get global config directory (.contextbuilder/).

    Used for data shared across all workspaces:
    - Users and authentication
    - Sessions
    - Global audit logs
    """
    config_dir = get_project_root() / ".contextbuilder"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_workspace_config_dir() -> Path:
    """Get workspace-scoped config directory.

    Used for data specific to the active workspace:
    - Pipeline prompt configs
    - Workspace-specific settings
    """
    # DATA_DIR is {workspace}/claims, so parent is workspace root
    config_dir = get_data_dir().parent / "config"
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
    registry_dir = get_data_dir().parent / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    return registry_dir


def _get_workspace_logs_dir() -> Path:
    """Get workspace-scoped logs directory.

    Used for compliance logs specific to the active workspace:
    - Decision ledger
    - LLM call logs
    """
    # DATA_DIR is {workspace}/claims, so parent is workspace root
    logs_dir = get_data_dir().parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def set_data_dir(path: Path) -> None:
    """Set the data directory for the API.

    Args:
        path: Base workspace path (e.g., output/).
              DATA_DIR will be set to path/claims.
              STAGING_DIR will be set to path/.pending.
    """
    set_workspace_paths(path / "claims", path / ".pending")


# =============================================================================
# STORAGE
# =============================================================================


def get_storage() -> StorageFacade:
    """Get Storage instance (fresh for each request to see new runs)."""
    return StorageFacade.from_storage(FileStorage(get_data_dir()))


# =============================================================================
# SERVICE GETTERS
# =============================================================================


def get_claims_service() -> ClaimsService:
    """Get ClaimsService instance."""
    return ClaimsService(get_data_dir(), get_storage)


def get_documents_service() -> DocumentsService:
    """Get DocumentsService instance."""
    return DocumentsService(get_data_dir(), get_storage)


def get_labels_service() -> LabelsService:
    """Get LabelsService instance with workspace-scoped compliance logging and index updates."""
    return LabelsService(
        get_storage,
        ledger_dir=_get_workspace_logs_dir(),
        registry_dir=_get_workspace_registry_dir(),
    )


def get_insights_service() -> InsightsService:
    """Get InsightsService instance."""
    return InsightsService(get_data_dir())


def get_token_costs_service() -> TokenCostsService:
    """Get TokenCostsService instance for token usage and cost aggregation."""
    return TokenCostsService(_get_workspace_logs_dir())


def get_evolution_service() -> EvolutionService:
    """Get EvolutionService instance.

    Note: DATA_DIR is {workspace}/claims, but version_bundles are stored
    at {workspace}/version_bundles, so we pass the workspace root.
    """
    return EvolutionService(get_data_dir().parent)


def get_upload_service() -> UploadService:
    """Get UploadService instance with compliance logging."""
    return UploadService(get_staging_dir(), get_data_dir(), ledger_dir=_get_workspace_logs_dir())


def get_truth_service() -> TruthService:
    """Get TruthService instance."""
    return TruthService(get_data_dir())


def get_assessment_service() -> AssessmentService:
    """Get AssessmentService instance."""
    return AssessmentService(get_data_dir())


# Singleton service instances
_pipeline_service: Optional[PipelineService] = None
_prompt_config_service: Optional[PromptConfigService] = None
_audit_service: Optional[AuditService] = None
_users_service: Optional[UsersService] = None
_auth_service: Optional[AuthService] = None
_compliance_config: Optional[ComplianceStorageConfig] = None
_workspace_service: Optional[WorkspaceService] = None


def get_pipeline_service() -> PipelineService:
    """Get PipelineService singleton instance."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService(get_data_dir(), get_upload_service())
    return _pipeline_service


def get_prompt_config_service() -> PromptConfigService:
    """Get PromptConfigService singleton instance (workspace-scoped)."""
    global _prompt_config_service
    if _prompt_config_service is None:
        _prompt_config_service = PromptConfigService(_get_workspace_config_dir())
    return _prompt_config_service


def get_audit_service() -> AuditService:
    """Get AuditService singleton instance (global, shared across workspaces)."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService(_get_global_config_dir())
    return _audit_service


def get_users_service() -> UsersService:
    """Get UsersService singleton instance (global, shared across workspaces)."""
    global _users_service
    if _users_service is None:
        _users_service = UsersService(_get_global_config_dir())
    return _users_service


def get_auth_service() -> AuthService:
    """Get AuthService singleton instance (global, shared across workspaces)."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService(_get_global_config_dir(), get_users_service())
    return _auth_service


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


def get_workspace_service() -> WorkspaceService:
    """Get WorkspaceService singleton instance."""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceService(get_project_root())
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
# AUTHENTICATION DEPENDENCIES
# =============================================================================


class CurrentUser(BaseModel):
    """Current authenticated user."""

    username: str
    role: str


def get_current_user(authorization: Optional[str] = Header(None)) -> CurrentUser:
    """Dependency to get the current authenticated user from the Authorization header.

    Expects: Authorization: Bearer <token>

    Args:
        authorization: The Authorization header value.

    Returns:
        CurrentUser with username and role.

    Raises:
        HTTPException: If not authenticated or token is invalid.
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
    """Dependency to optionally get the current user.

    Returns None if not authenticated instead of raising an exception.

    Args:
        authorization: The Authorization header value.

    Returns:
        CurrentUser if authenticated, None otherwise.
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
    """Dependency to require admin role.

    Args:
        current_user: The current authenticated user.

    Returns:
        CurrentUser if admin.

    Raises:
        HTTPException: If user is not admin.
    """
    if current_user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_role(allowed_roles: list[str]):
    """Factory for role-based access control dependency.

    Args:
        allowed_roles: List of role values that are permitted access.

    Returns:
        Dependency function that validates user role.

    Example:
        @app.get("/api/compliance/ledger")
        def get_ledger(user: CurrentUser = Depends(require_role(["admin", "auditor"]))):
            ...
    """

    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


# Pre-built role checker for compliance endpoints (admin or auditor)
require_compliance_access = require_role([Role.ADMIN.value, Role.AUDITOR.value])
