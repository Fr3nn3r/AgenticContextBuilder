"""Integration tests for workspace isolation.

Tests that workspaces provide proper data isolation and that
switching workspaces clears sessions correctly.
"""

import json
from pathlib import Path

import pytest

from context_builder.api.services.workspace import (
    Workspace,
    WorkspaceService,
    WorkspaceStatus,
)


class TestWorkspaceService:
    """Tests for WorkspaceService functionality."""

    def test_creates_default_workspace_on_init(self, tmp_path: Path):
        """Service should create a default workspace on first init."""
        service = WorkspaceService(tmp_path)

        workspaces = service.list_workspaces()
        assert len(workspaces) == 1
        assert workspaces[0].workspace_id == "default"
        assert workspaces[0].name == "Default"
        assert workspaces[0].status == WorkspaceStatus.ACTIVE.value

    def test_create_workspace_initializes_folders(self, tmp_path: Path):
        """Creating a workspace should initialize all required folders."""
        service = WorkspaceService(tmp_path)

        ws_path = tmp_path / "new_workspace"
        workspace = service.create_workspace(
            name="Test Workspace",
            path=str(ws_path),
            description="For testing",
        )

        assert workspace is not None
        assert workspace.name == "Test Workspace"
        assert workspace.workspace_id == "test-workspace"

        # Check folders were created
        expected_subdirs = ["claims", "runs", "logs", "registry", "config", ".pending", ".input"]
        for subdir in expected_subdirs:
            assert (ws_path / subdir).exists(), f"Missing subdir: {subdir}"

    def test_create_workspace_generates_unique_ids(self, tmp_path: Path):
        """Creating workspaces with same name should generate unique IDs."""
        service = WorkspaceService(tmp_path)

        ws1 = service.create_workspace("Test", str(tmp_path / "ws1"))
        ws2 = service.create_workspace("Test", str(tmp_path / "ws2"))
        ws3 = service.create_workspace("Test", str(tmp_path / "ws3"))

        assert ws1.workspace_id == "test"
        assert ws2.workspace_id == "test-1"
        assert ws3.workspace_id == "test-2"

    def test_cannot_create_duplicate_path(self, tmp_path: Path):
        """Cannot create two workspaces at the same path."""
        service = WorkspaceService(tmp_path)

        ws_path = tmp_path / "shared_path"
        ws1 = service.create_workspace("First", str(ws_path))
        ws2 = service.create_workspace("Second", str(ws_path))

        assert ws1 is not None
        assert ws2 is None  # Should fail

    def test_activate_workspace(self, tmp_path: Path):
        """Activating a workspace should update its status."""
        service = WorkspaceService(tmp_path)

        # Create a second workspace
        ws_path = tmp_path / "second"
        service.create_workspace("Second", str(ws_path))

        # Default should be active
        assert service.get_active_workspace_id() == "default"

        # Activate second workspace
        workspace = service.activate_workspace("second")
        assert workspace is not None
        assert workspace.status == WorkspaceStatus.ACTIVE.value
        assert service.get_active_workspace_id() == "second"

        # Check that default is no longer active
        workspaces = service.list_workspaces()
        default_ws = next(ws for ws in workspaces if ws.workspace_id == "default")
        assert default_ws.status == WorkspaceStatus.AVAILABLE.value

    def test_delete_workspace(self, tmp_path: Path):
        """Deleting a workspace removes it from registry but not files."""
        service = WorkspaceService(tmp_path)

        ws_path = tmp_path / "to_delete"
        service.create_workspace("ToDelete", str(ws_path))

        # Verify workspace and files exist
        assert len(service.list_workspaces()) == 2
        assert ws_path.exists()

        # Delete workspace
        result = service.delete_workspace("todelete")
        assert result is True

        # Workspace removed from registry
        assert len(service.list_workspaces()) == 1

        # Files still exist on disk
        assert ws_path.exists()
        assert (ws_path / "claims").exists()

    def test_cannot_delete_nonexistent_workspace(self, tmp_path: Path):
        """Deleting a nonexistent workspace should return False."""
        service = WorkspaceService(tmp_path)
        result = service.delete_workspace("nonexistent")
        assert result is False


class TestWorkspaceIsolation:
    """Tests for data isolation between workspaces."""

    def test_workspace_data_isolation(self, tmp_path: Path):
        """Data in one workspace should not appear in another."""
        service = WorkspaceService(tmp_path)

        ws1_path = tmp_path / "ws1"
        ws2_path = tmp_path / "ws2"

        service.create_workspace("WS1", str(ws1_path))
        service.create_workspace("WS2", str(ws2_path))

        # Add data to ws1
        claim_dir = ws1_path / "claims" / "CLM-001"
        claim_dir.mkdir(parents=True)
        (claim_dir / "test.json").write_text('{"test": "data"}')

        # ws2 should have no claims
        ws2_claims = list((ws2_path / "claims").iterdir())
        assert len(ws2_claims) == 0

        # ws1 should have the claim
        ws1_claims = list((ws1_path / "claims").iterdir())
        assert len(ws1_claims) == 1
        assert ws1_claims[0].name == "CLM-001"


class TestWorkspaceRegistry:
    """Tests for workspace registry persistence."""

    def test_registry_persists_across_instances(self, tmp_path: Path):
        """Registry should persist across service instances."""
        service1 = WorkspaceService(tmp_path)
        service1.create_workspace("Persistent", str(tmp_path / "persist"))

        # Create new service instance
        service2 = WorkspaceService(tmp_path)
        workspaces = service2.list_workspaces()

        assert len(workspaces) == 2
        ws_names = {ws.name for ws in workspaces}
        assert "Persistent" in ws_names

    def test_registry_location(self, tmp_path: Path):
        """Registry should be stored at .contextbuilder/workspaces.json."""
        service = WorkspaceService(tmp_path)

        registry_path = tmp_path / ".contextbuilder" / "workspaces.json"
        assert registry_path.exists()

        # Verify JSON structure
        with open(registry_path) as f:
            data = json.load(f)

        assert "schema_version" in data
        assert "active_workspace_id" in data
        assert "workspaces" in data
        assert len(data["workspaces"]) >= 1
