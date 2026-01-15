"""Workspace-aware path utilities.

This module provides helpers to get workspace-scoped paths (logs, claims, registry)
by reading from the workspace registry. These helpers are used as defaults when
explicit paths are not provided to components like classifiers and extractors.

Usage:
    from context_builder.storage.workspace_paths import get_workspace_logs_dir

    # Returns {active_workspace}/logs, or output/logs as fallback
    logs_dir = get_workspace_logs_dir()
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache the project root (computed once)
_PROJECT_ROOT: Optional[Path] = None


def _find_project_root() -> Path:
    """Find the project root directory.

    Walks up from this file to find a directory containing .contextbuilder/
    or pyproject.toml.

    Returns:
        Path to project root directory.
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    # Start from this file's directory and walk up
    current = Path(__file__).resolve().parent

    # Walk up looking for project markers
    for _ in range(10):  # Max 10 levels up
        if (current / ".contextbuilder").exists():
            _PROJECT_ROOT = current
            return current
        if (current / "pyproject.toml").exists():
            _PROJECT_ROOT = current
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Fallback: assume 4 levels up from storage module
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    return _PROJECT_ROOT


def get_active_workspace_path() -> Optional[Path]:
    """Get the path to the currently active workspace.

    Reads from .contextbuilder/workspaces.json to find the active workspace.

    Returns:
        Path to active workspace directory, or None if not found/configured.
    """
    project_root = _find_project_root()
    registry_path = project_root / ".contextbuilder" / "workspaces.json"

    if not registry_path.exists():
        logger.debug(f"No workspace registry found at {registry_path}")
        return None

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        active_id = registry.get("active_workspace_id")
        if not active_id:
            logger.debug("No active workspace ID in registry")
            return None

        for ws in registry.get("workspaces", []):
            if ws.get("workspace_id") == active_id:
                workspace_path = Path(ws.get("path", ""))
                if workspace_path.exists():
                    return workspace_path
                else:
                    logger.warning(f"Active workspace path does not exist: {workspace_path}")
                    return None

        logger.warning(f"Active workspace '{active_id}' not found in registry")
        return None

    except Exception as e:
        logger.warning(f"Failed to read workspace registry: {e}")
        return None


def get_workspace_logs_dir() -> Path:
    """Get the logs directory for the active workspace.

    This is the correct location for compliance logs (decision ledger, LLM calls).

    Returns:
        Path to workspace logs directory. Creates it if needed.
        Falls back to output/logs if no workspace is active.
    """
    workspace_path = get_active_workspace_path()

    if workspace_path is not None:
        logs_dir = workspace_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    # Fallback to output/logs relative to project root
    project_root = _find_project_root()
    fallback = project_root / "output" / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Using fallback logs directory: {fallback}")
    return fallback


def get_workspace_claims_dir() -> Path:
    """Get the claims directory for the active workspace.

    Returns:
        Path to workspace claims directory. Creates it if needed.
        Falls back to output/claims if no workspace is active.
    """
    workspace_path = get_active_workspace_path()

    if workspace_path is not None:
        claims_dir = workspace_path / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        return claims_dir

    # Fallback to output/claims relative to project root
    project_root = _find_project_root()
    fallback = project_root / "output" / "claims"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_workspace_registry_dir() -> Path:
    """Get the registry directory for the active workspace.

    Used for indexes (doc_index.jsonl, run_index.jsonl, etc).

    Returns:
        Path to workspace registry directory. Creates it if needed.
        Falls back to output/registry if no workspace is active.
    """
    workspace_path = get_active_workspace_path()

    if workspace_path is not None:
        registry_dir = workspace_path / "registry"
        registry_dir.mkdir(parents=True, exist_ok=True)
        return registry_dir

    # Fallback to output/registry relative to project root
    project_root = _find_project_root()
    fallback = project_root / "output" / "registry"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def reset_workspace_cache() -> None:
    """Reset the cached project root.

    Call this after workspace switch to ensure fresh path lookup.
    """
    global _PROJECT_ROOT
    _PROJECT_ROOT = None
