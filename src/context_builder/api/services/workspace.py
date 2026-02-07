"""Service for workspace management.

Workspaces allow switching between different storage locations at runtime,
enabling isolated integration testing and multi-environment support.
"""

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .audit import AuditService
from .prompt_config import PromptConfigService
from .users import UsersService

logger = logging.getLogger(__name__)


class WorkspaceStatus(str, Enum):
    """Workspace status."""

    ACTIVE = "active"
    AVAILABLE = "available"
    INITIALIZING = "initializing"


@dataclass
class Workspace:
    """Workspace definition."""

    workspace_id: str
    name: str
    path: str
    status: str = WorkspaceStatus.AVAILABLE.value
    created_at: str = ""
    last_accessed_at: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Workspace":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class WorkspaceRegistry:
    """Registry of all workspaces."""

    active_workspace_id: Optional[str] = None
    workspaces: List[Workspace] = field(default_factory=list)
    schema_version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "schema_version": self.schema_version,
            "active_workspace_id": self.active_workspace_id,
            "workspaces": [ws.to_dict() for ws in self.workspaces],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkspaceRegistry":
        """Create from dictionary."""
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            active_workspace_id=data.get("active_workspace_id"),
            workspaces=[Workspace.from_dict(ws) for ws in data.get("workspaces", [])],
        )


class WorkspaceService:
    """Service for managing workspaces."""

    REGISTRY_FILENAME = ".contextbuilder/workspaces.json"
    WORKSPACE_SUBDIRS = [
        "claims",
        "runs",
        "logs",
        "registry",
        "config",
        "version_bundles",
        ".pending",
        ".input",
    ]

    def __init__(self, project_root: Path):
        """
        Initialize the workspace service.

        Args:
            project_root: Project root directory where registry is stored.
        """
        self.project_root = project_root
        self.registry_path = project_root / self.REGISTRY_FILENAME
        self._ensure_registry()

    def _ensure_registry(self) -> None:
        """Ensure registry file exists with default workspace."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.registry_path.exists():
            default_path = self.project_root / "output"
            default_workspace = Workspace(
                workspace_id="default",
                name="Default",
                path=str(default_path),
                status=WorkspaceStatus.ACTIVE.value,
                description="Default workspace",
            )
            registry = WorkspaceRegistry(
                active_workspace_id="default",
                workspaces=[default_workspace],
            )
            self._save_registry(registry)
            logger.info(f"Created workspace registry with default workspace at {default_path}")

    def _load_registry(self) -> WorkspaceRegistry:
        """Load workspace registry from disk."""
        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return WorkspaceRegistry.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load workspace registry: {e}")
            raise

    def _save_registry(self, registry: WorkspaceRegistry) -> None:
        """Save workspace registry to disk."""
        try:
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(registry.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save workspace registry: {e}")
            raise

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert name to URL-safe slug."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug or "workspace"

    def list_workspaces(self) -> List[Workspace]:
        """List all registered workspaces."""
        registry = self._load_registry()
        return registry.workspaces

    def get_active_workspace_id(self) -> Optional[str]:
        """Get the ID of the currently active workspace."""
        registry = self._load_registry()
        return registry.active_workspace_id

    def get_active_workspace(self) -> Optional[Workspace]:
        """Get the currently active workspace."""
        registry = self._load_registry()
        if not registry.active_workspace_id:
            return None
        for ws in registry.workspaces:
            if ws.workspace_id == registry.active_workspace_id:
                return ws
        return None

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get a workspace by ID."""
        registry = self._load_registry()
        for ws in registry.workspaces:
            if ws.workspace_id == workspace_id:
                return ws
        return None

    def create_workspace(
        self,
        name: str,
        path: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Workspace]:
        """
        Create and initialize a new workspace.

        Args:
            name: Human-readable workspace name.
            path: Absolute path to workspace root directory. If None, auto-generates
                  under project_root/workspaces/{workspace_id}/.
            description: Optional description.

        Returns:
            Created workspace, or None if path already registered.
        """
        registry = self._load_registry()

        # Generate workspace_id first (needed for auto-generated path)
        workspace_id = self._slugify(name)
        existing_ids = {ws.workspace_id for ws in registry.workspaces}
        base_id = workspace_id
        counter = 1
        while workspace_id in existing_ids:
            workspace_id = f"{base_id}-{counter}"
            counter += 1

        # Auto-generate path if not provided
        if path is None:
            workspace_path = self.project_root / "workspaces" / workspace_id
            logger.info(f"Auto-generating workspace path: {workspace_path}")
        else:
            workspace_path = Path(path)

        # Check for duplicate paths
        for ws in registry.workspaces:
            if Path(ws.path).resolve() == workspace_path.resolve():
                logger.warning(f"Workspace already exists at path: {workspace_path}")
                return None

        self._initialize_workspace_folders(workspace_path)
        self._initialize_default_configs(workspace_path)

        workspace = Workspace(
            workspace_id=workspace_id,
            name=name,
            path=str(workspace_path),
            status=WorkspaceStatus.AVAILABLE.value,
            description=description,
        )

        registry.workspaces.append(workspace)
        self._save_registry(registry)

        logger.info(f"Created workspace '{name}' at {path} with ID {workspace_id}")
        return workspace

    def _initialize_workspace_folders(self, workspace_path: Path) -> None:
        """Create empty folder structure for workspace."""
        workspace_path.mkdir(parents=True, exist_ok=True)

        for subdir in self.WORKSPACE_SUBDIRS:
            (workspace_path / subdir).mkdir(exist_ok=True)

        logger.debug(f"Initialized workspace folders at {workspace_path}")

    def _initialize_default_configs(self, workspace_path: Path) -> None:
        """Initialize default configuration files for a new workspace.

        Creates default config files by instantiating services which
        auto-create their defaults on initialization:
        - prompt_configs.json (with default prompt configurations)
        - prompt_configs_history.jsonl (audit trail)
        - users.json (with default users: su, ted, seb, tod)
        - sessions.json (empty sessions file)
        - audit.jsonl is created on first audit log entry

        Args:
            workspace_path: Path to the workspace root directory.
        """
        config_dir = workspace_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Initialize prompt configs (creates prompt_configs.json and history)
        PromptConfigService(config_dir)
        logger.debug(f"Initialized prompt configs at {config_dir}")

        # Initialize users (creates users.json with default users)
        users_service = UsersService(config_dir)
        logger.debug(f"Initialized users at {config_dir}")

        # Initialize sessions file (create empty sessions.json)
        sessions_file = config_dir / "sessions.json"
        if not sessions_file.exists():
            sessions_file.write_text("{}", encoding="utf-8")
            logger.debug(f"Initialized sessions at {sessions_file}")

        # AuditService doesn't create file on init, but we can log workspace creation
        audit_service = AuditService(config_dir)
        audit_service.log(
            action=f"Workspace created at {workspace_path}",
            action_type="workspace_created",
            entity_type="workspace",
            entity_id=workspace_path.name,
            user="system",
        )
        logger.debug(f"Initialized audit log at {config_dir}")

        logger.info(f"Initialized default configs for workspace at {workspace_path}")

    def activate_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """
        Activate a workspace.

        Note: Caller is responsible for clearing sessions and resetting singletons.

        Args:
            workspace_id: ID of workspace to activate.

        Returns:
            Activated workspace, or None if not found.
        """
        registry = self._load_registry()

        workspace = None
        for ws in registry.workspaces:
            if ws.workspace_id == workspace_id:
                workspace = ws
                ws.status = WorkspaceStatus.ACTIVE.value
                ws.last_accessed_at = datetime.utcnow().isoformat() + "Z"
            elif ws.status == WorkspaceStatus.ACTIVE.value:
                ws.status = WorkspaceStatus.AVAILABLE.value

        if not workspace:
            logger.warning(f"Workspace not found: {workspace_id}")
            return None

        registry.active_workspace_id = workspace_id
        self._save_registry(registry)

        logger.info(f"Activated workspace: {workspace_id}")
        return workspace

    def delete_workspace(self, workspace_id: str) -> bool:
        """
        Delete a workspace from registry.

        Note: Does NOT delete files on disk.

        Args:
            workspace_id: ID of workspace to delete.

        Returns:
            True if deleted, False if not found.
        """
        registry = self._load_registry()

        original_count = len(registry.workspaces)
        registry.workspaces = [ws for ws in registry.workspaces if ws.workspace_id != workspace_id]

        if len(registry.workspaces) == original_count:
            logger.warning(f"Workspace not found for deletion: {workspace_id}")
            return False

        self._save_registry(registry)
        logger.info(f"Deleted workspace from registry: {workspace_id}")
        return True

    # Directories to clear during reset (DATA directories)
    DATA_DIRS = ["claims", "runs", "logs", "registry", "version_bundles", ".pending", ".input"]

    def reset_workspace(
        self,
        workspace_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Reset a workspace by clearing all data while preserving configuration.

        This is the equivalent of "DROP DATABASE" - clears all claims, runs, logs,
        indexes, and registries while keeping users and configuration intact.

        Cleared directories:
        - claims/ - all documents and extractions
        - runs/ - pipeline run results
        - logs/ - compliance logs (decisions.jsonl, llm_calls.jsonl)
        - registry/ - indexes and labels
        - version_bundles/ - version snapshots
        - .pending/ - pending uploads
        - .input/ - input staging

        Preserved:
        - config/ - users, sessions, extractors, extraction_specs, prompts, etc.

        Args:
            workspace_id: ID of workspace to reset. If None, uses active workspace.
            dry_run: If True, only report what would be deleted without actually deleting.

        Returns:
            Dict with reset statistics:
            - workspace_id: ID of reset workspace
            - workspace_path: Path to workspace
            - cleared_dirs: List of directories that were cleared
            - preserved_dirs: List of directories that were preserved
            - files_deleted: Count of files deleted
            - dirs_deleted: Count of directories deleted
            - dry_run: Whether this was a dry run

        Raises:
            ValueError: If workspace not found.
        """
        import shutil

        # Get workspace
        if workspace_id is None:
            workspace = self.get_active_workspace()
            if workspace is None:
                raise ValueError("No active workspace found")
        else:
            workspace = self.get_workspace(workspace_id)
            if workspace is None:
                raise ValueError(f"Workspace not found: {workspace_id}")

        workspace_path = Path(workspace.path)
        if not workspace_path.is_absolute():
            workspace_path = self.project_root / workspace_path
        if not workspace_path.exists():
            raise ValueError(f"Workspace path does not exist: {workspace_path}")

        stats = {
            "workspace_id": workspace.workspace_id,
            "workspace_path": str(workspace_path),
            "cleared_dirs": [],
            "preserved_dirs": ["config"],
            "files_deleted": 0,
            "dirs_deleted": 0,
            "dry_run": dry_run,
        }

        # Clear data directories
        for dir_name in self.DATA_DIRS:
            dir_path = workspace_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Count contents before clearing
                file_count = sum(1 for _ in dir_path.rglob("*") if _.is_file())
                dir_count = sum(1 for _ in dir_path.rglob("*") if _.is_dir())

                stats["files_deleted"] += file_count
                stats["dirs_deleted"] += dir_count
                stats["cleared_dirs"].append(dir_name)

                if not dry_run:
                    # Remove all contents but keep the directory
                    shutil.rmtree(dir_path)
                    dir_path.mkdir(exist_ok=True)
                    logger.info(f"Cleared {dir_name}/ ({file_count} files, {dir_count} dirs)")

        # Log the reset action (unless dry run)
        if not dry_run:
            config_dir = workspace_path / "config"
            if config_dir.exists():
                try:
                    audit_service = AuditService(config_dir)
                    audit_service.log(
                        action=f"Workspace reset: cleared {len(stats['cleared_dirs'])} directories",
                        action_type="workspace_reset",
                        entity_type="workspace",
                        entity_id=workspace.workspace_id,
                        user="system",
                        metadata={
                            "files_deleted": stats["files_deleted"],
                            "dirs_deleted": stats["dirs_deleted"],
                            "cleared_dirs": stats["cleared_dirs"],
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to log reset action: {e}")

            logger.info(
                f"Reset workspace '{workspace.workspace_id}': "
                f"deleted {stats['files_deleted']} files, {stats['dirs_deleted']} dirs"
            )

        return stats
