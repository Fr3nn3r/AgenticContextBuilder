"""Tests for workspace-level claim run paths."""

from pathlib import Path

import pytest

from context_builder.pipeline.paths import (
    WorkspaceClaimRunPaths,
    create_workspace_claim_run_structure,
    get_workspace_claim_run_paths,
)


class TestGetWorkspaceClaimRunPaths:
    """Tests for get_workspace_claim_run_paths."""

    def test_get_paths_structure(self, tmp_path):
        """Test that paths point to correct locations."""
        workspace_root = tmp_path / "workspaces" / "nsa"
        claim_run_id = "clm_20260128_120000_abc123"

        paths = get_workspace_claim_run_paths(workspace_root, claim_run_id)

        assert isinstance(paths, WorkspaceClaimRunPaths)
        assert paths.run_root == workspace_root / "claim_runs" / claim_run_id
        assert paths.manifest_json == paths.run_root / "manifest.json"
        assert paths.summary_json == paths.run_root / "summary.json"
        assert paths.logs_dir == paths.run_root / "logs"
        assert paths.run_log == paths.run_root / "logs" / "run.log"
        assert paths.complete_marker == paths.run_root / ".complete"

    def test_get_paths_does_not_create_dirs(self, tmp_path):
        """Test that get_paths is pure path computation (no side effects)."""
        workspace_root = tmp_path / "workspaces" / "nsa"
        claim_run_id = "clm_20260128_120000_abc123"

        paths = get_workspace_claim_run_paths(workspace_root, claim_run_id)

        assert not paths.run_root.exists()
        assert not paths.logs_dir.exists()


class TestCreateWorkspaceClaimRunStructure:
    """Tests for create_workspace_claim_run_structure."""

    def test_create_structure_creates_dirs(self, tmp_path):
        """Test that run_root and logs_dir exist after creation."""
        workspace_root = tmp_path / "workspaces" / "nsa"
        claim_run_id = "clm_20260128_120000_abc123"

        paths = create_workspace_claim_run_structure(workspace_root, claim_run_id)

        assert paths.run_root.exists()
        assert paths.run_root.is_dir()
        assert paths.logs_dir.exists()
        assert paths.logs_dir.is_dir()

    def test_create_structure_returns_correct_type(self, tmp_path):
        """Test return type is WorkspaceClaimRunPaths."""
        paths = create_workspace_claim_run_structure(tmp_path, "clm_20260128_120000_abc123")
        assert isinstance(paths, WorkspaceClaimRunPaths)

    def test_create_structure_idempotent(self, tmp_path):
        """Test that calling create twice doesn't fail."""
        workspace_root = tmp_path / "workspaces" / "nsa"
        claim_run_id = "clm_20260128_120000_abc123"

        paths1 = create_workspace_claim_run_structure(workspace_root, claim_run_id)
        paths2 = create_workspace_claim_run_structure(workspace_root, claim_run_id)

        assert paths1.run_root == paths2.run_root
        assert paths1.run_root.exists()
