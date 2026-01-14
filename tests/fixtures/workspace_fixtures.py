"""Workspace fixtures for integration testing.

Provides fixtures and context managers for creating isolated test workspaces.
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator
import tempfile

import pytest

from context_builder.api.services.workspace import WorkspaceService


# Standard workspace subdirectories
WORKSPACE_SUBDIRS = [
    "claims",
    "runs",
    "logs",
    "registry",
    "config",
    ".pending",
    ".input",
]


@pytest.fixture
def isolated_workspace(tmp_path: Path) -> Path:
    """Create an isolated test workspace with empty folder structure.

    Yields:
        Path to the workspace root directory.
    """
    workspace_path = tmp_path / "test_workspace"
    workspace_path.mkdir()

    for subdir in WORKSPACE_SUBDIRS:
        (workspace_path / subdir).mkdir()

    return workspace_path


@pytest.fixture
def workspace_service(tmp_path: Path) -> WorkspaceService:
    """Create a WorkspaceService with isolated registry.

    The registry is stored in a temp directory, separate from
    any real workspace data.

    Yields:
        WorkspaceService instance.
    """
    return WorkspaceService(project_root=tmp_path)


@contextmanager
def temporary_workspace() -> Generator[Path, None, None]:
    """Context manager for tests needing an isolated workspace.

    Creates a temporary workspace and points the API to it,
    then restores the original paths on exit.

    Usage:
        with temporary_workspace() as ws_path:
            # API now uses ws_path for all data
            # Test your code here
        # API paths restored to original values

    Yields:
        Path to the temporary workspace.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_path = Path(tmpdir)

        # Initialize folder structure
        for subdir in WORKSPACE_SUBDIRS:
            (workspace_path / subdir).mkdir()

        # Import and save original paths
        from context_builder.api import main

        original_data_dir = main.DATA_DIR
        original_staging_dir = main.STAGING_DIR

        # Point API to temp workspace
        main.DATA_DIR = workspace_path / "claims"
        main.STAGING_DIR = workspace_path / ".pending"

        try:
            yield workspace_path
        finally:
            # Restore original paths
            main.DATA_DIR = original_data_dir
            main.STAGING_DIR = original_staging_dir
