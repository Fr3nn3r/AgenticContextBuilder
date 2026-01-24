"""Unit tests for WorkspaceService."""

from pathlib import Path

import pytest

from context_builder.api.services.workspace import (
    Workspace,
    WorkspaceRegistry,
    WorkspaceService,
    WorkspaceStatus,
)


class TestWorkspace:
    """Tests for Workspace dataclass."""

    def test_workspace_creation(self):
        """Test basic workspace creation."""
        ws = Workspace(
            workspace_id="test",
            name="Test Workspace",
            path="/tmp/test",
        )
        assert ws.workspace_id == "test"
        assert ws.name == "Test Workspace"
        assert ws.path == "/tmp/test"
        assert ws.status == WorkspaceStatus.AVAILABLE.value
        assert ws.created_at  # Should be auto-populated

    def test_workspace_to_dict(self):
        """Test workspace serialization."""
        ws = Workspace(
            workspace_id="test",
            name="Test",
            path="/tmp/test",
            description="A test workspace",
        )
        data = ws.to_dict()

        assert data["workspace_id"] == "test"
        assert data["name"] == "Test"
        assert data["path"] == "/tmp/test"
        assert data["description"] == "A test workspace"

    def test_workspace_from_dict(self):
        """Test workspace deserialization."""
        data = {
            "workspace_id": "test",
            "name": "Test",
            "path": "/tmp/test",
            "status": "active",
            "created_at": "2026-01-01T00:00:00Z",
        }
        ws = Workspace.from_dict(data)

        assert ws.workspace_id == "test"
        assert ws.name == "Test"
        assert ws.status == "active"


class TestWorkspaceRegistry:
    """Tests for WorkspaceRegistry dataclass."""

    def test_registry_creation(self):
        """Test registry creation with defaults."""
        registry = WorkspaceRegistry()
        assert registry.active_workspace_id is None
        assert registry.workspaces == []
        assert registry.schema_version == "1.0"

    def test_registry_serialization(self):
        """Test registry round-trip serialization."""
        ws = Workspace(
            workspace_id="test",
            name="Test",
            path="/tmp/test",
        )
        registry = WorkspaceRegistry(
            active_workspace_id="test",
            workspaces=[ws],
        )

        data = registry.to_dict()
        restored = WorkspaceRegistry.from_dict(data)

        assert restored.active_workspace_id == "test"
        assert len(restored.workspaces) == 1
        assert restored.workspaces[0].workspace_id == "test"


class TestWorkspaceServiceSlugify:
    """Tests for the _slugify helper."""

    def test_slugify_simple(self):
        """Test simple name slugification."""
        assert WorkspaceService._slugify("Test") == "test"
        assert WorkspaceService._slugify("My Workspace") == "my-workspace"

    def test_slugify_special_chars(self):
        """Test slugification with special characters."""
        assert WorkspaceService._slugify("Test!@#$%") == "test"
        assert WorkspaceService._slugify("A & B") == "a-b"

    def test_slugify_empty(self):
        """Test slugification of empty/special-only strings."""
        assert WorkspaceService._slugify("") == "workspace"
        assert WorkspaceService._slugify("!!!") == "workspace"


class TestWorkspaceServiceCRUD:
    """Tests for WorkspaceService CRUD operations."""

    def test_list_workspaces(self, tmp_path: Path):
        """Test listing workspaces."""
        service = WorkspaceService(tmp_path)
        workspaces = service.list_workspaces()

        # Should have default workspace
        assert len(workspaces) >= 1
        assert any(ws.workspace_id == "default" for ws in workspaces)

    def test_get_active_workspace(self, tmp_path: Path):
        """Test getting active workspace."""
        service = WorkspaceService(tmp_path)
        active = service.get_active_workspace()

        assert active is not None
        assert active.workspace_id == "default"

    def test_get_workspace_by_id(self, tmp_path: Path):
        """Test getting workspace by ID."""
        service = WorkspaceService(tmp_path)

        ws = service.get_workspace("default")
        assert ws is not None
        assert ws.workspace_id == "default"

        ws = service.get_workspace("nonexistent")
        assert ws is None

    def test_create_workspace_success(self, tmp_path: Path):
        """Test successful workspace creation."""
        service = WorkspaceService(tmp_path)
        ws_path = tmp_path / "new_ws"

        ws = service.create_workspace(
            name="New Workspace",
            path=str(ws_path),
            description="Test description",
        )

        assert ws is not None
        assert ws.name == "New Workspace"
        assert ws.description == "Test description"
        assert ws_path.exists()

    def test_activate_nonexistent_workspace(self, tmp_path: Path):
        """Test activating nonexistent workspace returns None."""
        service = WorkspaceService(tmp_path)
        result = service.activate_workspace("nonexistent")
        assert result is None

    def test_create_workspace_initializes_default_configs(self, tmp_path: Path):
        """Test that creating a workspace initializes default config files."""
        service = WorkspaceService(tmp_path)

        ws = service.create_workspace(
            name="Config Test",
            description="Test config initialization",
        )

        assert ws is not None
        ws_path = Path(ws.path)
        config_dir = ws_path / "config"

        # Verify config directory exists
        assert config_dir.exists()

        # Verify prompt configs were created
        prompt_configs = config_dir / "prompt_configs.json"
        assert prompt_configs.exists()
        assert prompt_configs.stat().st_size > 0

        # Verify prompt config history was created
        history_file = config_dir / "prompt_configs_history.jsonl"
        assert history_file.exists()

        # Verify users were created
        users_file = config_dir / "users.json"
        assert users_file.exists()
        assert users_file.stat().st_size > 0

        # Verify sessions file was created
        sessions_file = config_dir / "sessions.json"
        assert sessions_file.exists()

        # Verify audit log was created (workspace creation logged)
        audit_file = config_dir / "audit.jsonl"
        assert audit_file.exists()
        assert audit_file.stat().st_size > 0
