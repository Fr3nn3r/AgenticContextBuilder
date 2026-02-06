"""Service layer for API endpoints."""

from .aggregation import AggregationError, AggregationService
from .assessment import AssessmentStorageService, AssessmentService
from .auth import AuthService, Session
from .claims import ClaimsService
from .documents import DocumentsService
from .evolution import EvolutionService
from .insights import InsightsService
from .labels import LabelsService
from .reconciliation import ReconciliationError, ReconciliationService
from .truth import TruthService
from .upload import PendingClaim, PendingDocument, UploadService
from .pipeline import DocPhase, DocProgress, PipelineRun, PipelineService, PipelineStatus
from .prompt_config import PromptConfig, PromptConfigService
from .audit import AuditEntry, AuditService
from .users import Role, User, UsersService
from .workspace import Workspace, WorkspaceRegistry, WorkspaceService, WorkspaceStatus
from .token_costs import TokenCostsService

__all__ = [
    "AggregationError",
    "AggregationService",
    "AssessmentStorageService",
    "AssessmentService",  # Deprecated alias
    "AuditEntry",
    "AuditService",
    "AuthService",
    "ClaimsService",
    "DocPhase",
    "DocProgress",
    "DocumentsService",
    "EvolutionService",
    "InsightsService",
    "LabelsService",
    "PendingClaim",
    "PendingDocument",
    "PipelineRun",
    "PipelineService",
    "PipelineStatus",
    "PromptConfig",
    "PromptConfigService",
    "ReconciliationError",
    "ReconciliationService",
    "Role",
    "Session",
    "TruthService",
    "UploadService",
    "User",
    "UsersService",
    "Workspace",
    "WorkspaceRegistry",
    "WorkspaceService",
    "WorkspaceStatus",
    "TokenCostsService",
]
