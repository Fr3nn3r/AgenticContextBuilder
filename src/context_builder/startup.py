"""Centralized initialization for all context_builder entry points.

This module provides a single point of initialization for:
- Environment variables (.env loading)
- Active workspace resolution
- Data/staging directory configuration

All entry points (API, CLI, pipeline) should use ensure_initialized()
to guarantee consistent startup behavior.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class WorkspaceState:
    """Current workspace state after initialization."""

    project_root: Path
    data_dir: Path
    staging_dir: Path
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    is_render: bool = False


# Module-level state
_initialized: bool = False
_state: Optional[WorkspaceState] = None


def _find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find project root by looking for .contextbuilder or pyproject.toml.

    Args:
        start_path: Starting path for search. Defaults to this file's location.

    Returns:
        Project root directory.
    """
    if start_path is None:
        # Default: go up from this file's location
        start_path = Path(__file__).resolve().parent.parent.parent

    current = start_path
    for parent in [current] + list(current.parents):
        if (parent / ".contextbuilder").is_dir():
            return parent
        if (parent / "pyproject.toml").exists():
            return parent
    return start_path


def _load_env(project_root: Path) -> bool:
    """Load .env file from project root.

    Args:
        project_root: Project root directory.

    Returns:
        True if .env was loaded, False otherwise.
    """
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[startup] Loaded .env from {env_path}")
        azure_endpoint = os.getenv("AZURE_DI_ENDPOINT", "NOT SET")
        # Truncate for display
        if len(azure_endpoint) > 30:
            azure_endpoint = azure_endpoint[:30] + "..."
        print(f"[startup] AZURE_DI_ENDPOINT = {azure_endpoint}")
        return True
    else:
        print(f"[startup] WARNING: .env not found at {env_path}")
        return False


def _load_active_workspace(project_root: Path) -> WorkspaceState:
    """Load the active workspace from registry and determine paths.

    Args:
        project_root: Project root directory.

    Returns:
        WorkspaceState with resolved paths.
    """
    # Default paths
    data_dir = project_root / "output" / "claims"
    staging_dir = project_root / "output" / ".pending"
    workspace_id = None
    workspace_name = None
    is_render = False

    # Check for Render persistent disk environment variable
    render_workspace = os.getenv("RENDER_WORKSPACE_PATH")
    if render_workspace:
        workspace_path = Path(render_workspace)
        workspace_path.mkdir(parents=True, exist_ok=True)
        data_dir = workspace_path / "claims"
        staging_dir = workspace_path / ".pending"
        data_dir.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir(parents=True, exist_ok=True)
        print(f"[startup] Using Render workspace: {workspace_path}")
        return WorkspaceState(
            project_root=project_root,
            data_dir=data_dir,
            staging_dir=staging_dir,
            is_render=True,
        )

    # Try to load from workspace registry
    registry_path = project_root / ".contextbuilder" / "workspaces.json"

    if not registry_path.exists():
        print(f"[startup] No workspace registry found, using default: {data_dir}")
        return WorkspaceState(
            project_root=project_root,
            data_dir=data_dir,
            staging_dir=staging_dir,
        )

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        active_id = registry.get("active_workspace_id")
        if not active_id:
            print(f"[startup] No active workspace in registry, using default: {data_dir}")
            return WorkspaceState(
                project_root=project_root,
                data_dir=data_dir,
                staging_dir=staging_dir,
            )

        for ws in registry.get("workspaces", []):
            if ws.get("workspace_id") == active_id:
                workspace_path = Path(ws.get("path", ""))
                # Resolve relative paths against project root
                if not workspace_path.is_absolute():
                    workspace_path = project_root / workspace_path
                if workspace_path.exists():
                    data_dir = workspace_path / "claims"
                    staging_dir = workspace_path / ".pending"
                    workspace_id = active_id
                    workspace_name = ws.get("name", active_id)
                    print(f"[startup] Loaded active workspace '{active_id}': {workspace_path}")
                else:
                    print(f"[startup] WARNING: Active workspace path does not exist: {workspace_path}")
                break
        else:
            print(f"[startup] WARNING: Active workspace '{active_id}' not found in registry")

    except Exception as e:
        print(f"[startup] WARNING: Failed to load workspace registry: {e}")

    return WorkspaceState(
        project_root=project_root,
        data_dir=data_dir,
        staging_dir=staging_dir,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
    )


def ensure_initialized() -> WorkspaceState:
    """Ensure the application is initialized (idempotent).

    Loads .env and resolves workspace paths on first call.
    Subsequent calls return cached state.

    Returns:
        Current WorkspaceState.
    """
    global _initialized, _state

    if _initialized and _state is not None:
        return _state

    project_root = _find_project_root()
    _load_env(project_root)
    _state = _load_active_workspace(project_root)
    _initialized = True

    return _state


def get_state() -> WorkspaceState:
    """Get current workspace state.

    Raises:
        RuntimeError: If not initialized. Call ensure_initialized() first.

    Returns:
        Current WorkspaceState.
    """
    if not _initialized or _state is None:
        raise RuntimeError(
            "startup not initialized. Call ensure_initialized() first."
        )
    return _state


def get_project_root() -> Path:
    """Get the project root directory.

    Initializes if needed.

    Returns:
        Project root path.
    """
    state = ensure_initialized()
    return state.project_root


def get_data_dir() -> Path:
    """Get the current data directory (claims folder).

    Initializes if needed.

    Returns:
        Data directory path.
    """
    state = ensure_initialized()
    return state.data_dir


def get_staging_dir() -> Path:
    """Get the current staging directory.

    Initializes if needed.

    Returns:
        Staging directory path.
    """
    state = ensure_initialized()
    return state.staging_dir


def set_workspace_paths(data_dir: Path, staging_dir: Path) -> None:
    """Update workspace paths (for workspace switch).

    Args:
        data_dir: New data directory path.
        staging_dir: New staging directory path.
    """
    global _state

    if _state is None:
        ensure_initialized()

    if _state is not None:
        _state.data_dir = data_dir
        _state.staging_dir = staging_dir


def reset_for_testing() -> None:
    """Reset initialization state for test isolation.

    Should only be used in tests.
    """
    global _initialized, _state
    _initialized = False
    _state = None
