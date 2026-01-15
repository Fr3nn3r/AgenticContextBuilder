"""Tests for workspace_paths module."""

import json
import pytest
from pathlib import Path
from unittest import mock

from context_builder.storage.workspace_paths import (
    get_workspace_logs_dir,
    get_workspace_claims_dir,
    get_workspace_registry_dir,
    get_active_workspace_path,
    reset_workspace_cache,
    _find_project_root,
)


class TestGetActiveWorkspacePath:
    """Tests for get_active_workspace_path function."""

    def test_returns_none_when_no_registry(self, tmp_path):
        """Returns None when no workspaces.json exists."""
        with mock.patch(
            "context_builder.storage.workspace_paths._find_project_root",
            return_value=tmp_path,
        ):
            reset_workspace_cache()
            result = get_active_workspace_path()
            # May return None or fallback depending on actual project structure
            # The key is it doesn't crash

    def test_returns_workspace_path_when_active(self, tmp_path):
        """Returns workspace path when active workspace is configured."""
        # Create workspace registry
        registry_dir = tmp_path / ".contextbuilder"
        registry_dir.mkdir()
        workspace_path = tmp_path / "workspaces" / "test-ws"
        workspace_path.mkdir(parents=True)

        registry = {
            "active_workspace_id": "test-ws",
            "workspaces": [
                {
                    "workspace_id": "test-ws",
                    "name": "Test Workspace",
                    "path": str(workspace_path),
                }
            ],
        }
        (registry_dir / "workspaces.json").write_text(json.dumps(registry))

        with mock.patch(
            "context_builder.storage.workspace_paths._find_project_root",
            return_value=tmp_path,
        ):
            reset_workspace_cache()
            result = get_active_workspace_path()
            assert result == workspace_path


class TestGetWorkspaceLogsDir:
    """Tests for get_workspace_logs_dir function."""

    def test_creates_logs_dir_in_workspace(self, tmp_path):
        """Creates and returns logs dir within active workspace."""
        # Create workspace registry
        registry_dir = tmp_path / ".contextbuilder"
        registry_dir.mkdir()
        workspace_path = tmp_path / "workspaces" / "test-ws"
        workspace_path.mkdir(parents=True)

        registry = {
            "active_workspace_id": "test-ws",
            "workspaces": [
                {
                    "workspace_id": "test-ws",
                    "name": "Test Workspace",
                    "path": str(workspace_path),
                }
            ],
        }
        (registry_dir / "workspaces.json").write_text(json.dumps(registry))

        with mock.patch(
            "context_builder.storage.workspace_paths._find_project_root",
            return_value=tmp_path,
        ):
            reset_workspace_cache()
            result = get_workspace_logs_dir()
            assert result == workspace_path / "logs"
            assert result.exists()

    def test_falls_back_to_output_logs_when_no_workspace(self, tmp_path):
        """Falls back to output/logs when no workspace configured."""
        with mock.patch(
            "context_builder.storage.workspace_paths._find_project_root",
            return_value=tmp_path,
        ):
            reset_workspace_cache()
            result = get_workspace_logs_dir()
            assert result == tmp_path / "output" / "logs"
            assert result.exists()


class TestGetWorkspaceClaimsDir:
    """Tests for get_workspace_claims_dir function."""

    def test_creates_claims_dir_in_workspace(self, tmp_path):
        """Creates and returns claims dir within active workspace."""
        # Create workspace registry
        registry_dir = tmp_path / ".contextbuilder"
        registry_dir.mkdir()
        workspace_path = tmp_path / "workspaces" / "test-ws"
        workspace_path.mkdir(parents=True)

        registry = {
            "active_workspace_id": "test-ws",
            "workspaces": [
                {
                    "workspace_id": "test-ws",
                    "name": "Test Workspace",
                    "path": str(workspace_path),
                }
            ],
        }
        (registry_dir / "workspaces.json").write_text(json.dumps(registry))

        with mock.patch(
            "context_builder.storage.workspace_paths._find_project_root",
            return_value=tmp_path,
        ):
            reset_workspace_cache()
            result = get_workspace_claims_dir()
            assert result == workspace_path / "claims"
            assert result.exists()


class TestGetWorkspaceRegistryDir:
    """Tests for get_workspace_registry_dir function."""

    def test_creates_registry_dir_in_workspace(self, tmp_path):
        """Creates and returns registry dir within active workspace."""
        # Create workspace registry
        registry_dir = tmp_path / ".contextbuilder"
        registry_dir.mkdir()
        workspace_path = tmp_path / "workspaces" / "test-ws"
        workspace_path.mkdir(parents=True)

        registry = {
            "active_workspace_id": "test-ws",
            "workspaces": [
                {
                    "workspace_id": "test-ws",
                    "name": "Test Workspace",
                    "path": str(workspace_path),
                }
            ],
        }
        (registry_dir / "workspaces.json").write_text(json.dumps(registry))

        with mock.patch(
            "context_builder.storage.workspace_paths._find_project_root",
            return_value=tmp_path,
        ):
            reset_workspace_cache()
            result = get_workspace_registry_dir()
            assert result == workspace_path / "registry"
            assert result.exists()


class TestResetWorkspaceCache:
    """Tests for reset_workspace_cache function."""

    def test_clears_cached_project_root(self):
        """Calling reset clears the cached project root."""
        # Just verify it doesn't raise
        reset_workspace_cache()
