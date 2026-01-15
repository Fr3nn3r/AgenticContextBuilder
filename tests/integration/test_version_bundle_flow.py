"""Integration tests for version bundle creation flow.

Tests the end-to-end flow of version bundle creation:
1. Pipeline creates version bundle at correct workspace location
2. API can retrieve bundles created by pipeline
3. Workspace switching correctly changes bundle storage location
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context_builder.storage.version_bundles import (
    VersionBundleStore,
    get_version_bundle_store,
)


class TestPipelineVersionBundleCreation:
    """Tests simulating version bundle creation during pipeline execution."""

    @pytest.fixture
    def workspace_dir(self):
        """Create a realistic workspace directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            # Create full workspace structure as WorkspaceService would
            subdirs = [
                "claims",
                "runs",
                "logs",
                "registry",
                "config",
                "version_bundles",
                ".pending",
                ".input",
            ]
            for subdir in subdirs:
                (workspace / subdir).mkdir(parents=True, exist_ok=True)
            yield workspace

    def test_pipeline_creates_bundle_at_workspace_root(self, workspace_dir):
        """Simulate pipeline creating bundle - should be at workspace root.

        This mirrors what run.py does:
        - output_base = {workspace}/claims
        - workspace_root = output_base.parent
        - store = get_version_bundle_store(workspace_root)
        """
        # Simulate pipeline's output_base (claims dir)
        claims_dir = workspace_dir / "claims"

        # This is what run.py now does - use parent of claims dir
        workspace_root = claims_dir.parent

        # Create store as pipeline would
        store = get_version_bundle_store(workspace_root)

        # Create bundle as pipeline would
        run_id = "BATCH-20240115-001"
        bundle = store.create_version_bundle(
            run_id=run_id,
            model_name="gpt-4o",
            extractor_version="v1.0.0",
        )

        # Verify bundle is at correct location
        expected_path = workspace_dir / "version_bundles" / run_id / "bundle.json"
        assert expected_path.exists(), f"Bundle not at expected path: {expected_path}"

        # Verify NOT at wrong location (the old bug)
        wrong_path = workspace_dir / "claims" / "version_bundles" / run_id / "bundle.json"
        assert not wrong_path.exists(), f"Bundle at wrong path: {wrong_path}"

    def test_api_can_retrieve_pipeline_created_bundle(self, workspace_dir):
        """Simulate API retrieving bundle created by pipeline.

        This verifies fix for the bug where:
        - Pipeline wrote to {workspace}/claims/version_bundles/
        - API read from {workspace}/version_bundles/
        """
        run_id = "BATCH-20240115-002"

        # Simulate pipeline creating bundle
        pipeline_claims_dir = workspace_dir / "claims"
        pipeline_workspace_root = pipeline_claims_dir.parent
        pipeline_store = VersionBundleStore(pipeline_workspace_root)
        created_bundle = pipeline_store.create_version_bundle(
            run_id=run_id,
            model_name="gpt-4o",
        )

        # Simulate API retrieving bundle (uses workspace root directly)
        api_store = VersionBundleStore(workspace_dir)
        retrieved_bundle = api_store.get_version_bundle(run_id)

        # Should find the same bundle
        assert retrieved_bundle is not None, "API should find bundle created by pipeline"
        assert retrieved_bundle.bundle_id == created_bundle.bundle_id
        assert retrieved_bundle.model_name == "gpt-4o"

    def test_api_list_finds_pipeline_bundles(self, workspace_dir):
        """API list endpoint should find all bundles created by pipeline."""
        # Simulate pipeline creating multiple bundles
        pipeline_store = VersionBundleStore(workspace_dir)
        pipeline_store.create_version_bundle(run_id="run1", model_name="gpt-4o")
        pipeline_store.create_version_bundle(run_id="run2", model_name="gpt-4o-mini")
        pipeline_store.create_version_bundle(run_id="run3", model_name="gpt-4o")

        # Simulate API listing bundles
        api_store = VersionBundleStore(workspace_dir)
        run_ids = api_store.list_bundles()

        assert set(run_ids) == {"run1", "run2", "run3"}


class TestMultiWorkspaceVersionBundles:
    """Tests for version bundles with multiple workspaces."""

    @pytest.fixture
    def workspaces(self):
        """Create multiple workspace directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create two workspaces
            ws1 = base / "workspace1"
            ws2 = base / "workspace2"

            for ws in [ws1, ws2]:
                (ws / "claims").mkdir(parents=True)
                (ws / "version_bundles").mkdir(parents=True)

            yield {"ws1": ws1, "ws2": ws2}

    def test_bundles_isolated_between_workspaces(self, workspaces):
        """Bundles in one workspace should not appear in another."""
        ws1, ws2 = workspaces["ws1"], workspaces["ws2"]

        # Create bundle in workspace 1
        store1 = VersionBundleStore(ws1)
        store1.create_version_bundle(run_id="ws1-run", model_name="gpt-4o")

        # Create bundle in workspace 2
        store2 = VersionBundleStore(ws2)
        store2.create_version_bundle(run_id="ws2-run", model_name="gpt-4o")

        # Each workspace should only see its own bundles
        assert store1.list_bundles() == ["ws1-run"]
        assert store2.list_bundles() == ["ws2-run"]

        # Cross-workspace retrieval should return None
        assert store1.get_version_bundle("ws2-run") is None
        assert store2.get_version_bundle("ws1-run") is None

    def test_workspace_switch_changes_bundle_location(self, workspaces):
        """Switching workspaces should change where bundles are stored."""
        ws1, ws2 = workspaces["ws1"], workspaces["ws2"]

        # Simulate workspace 1 active - create bundle
        active_store = VersionBundleStore(ws1)
        active_store.create_version_bundle(run_id="run-before-switch", model_name="gpt-4o")

        # Simulate switching to workspace 2
        active_store = VersionBundleStore(ws2)
        active_store.create_version_bundle(run_id="run-after-switch", model_name="gpt-4o")

        # Verify bundles are in correct workspaces
        assert (ws1 / "version_bundles" / "run-before-switch" / "bundle.json").exists()
        assert (ws2 / "version_bundles" / "run-after-switch" / "bundle.json").exists()

        # Verify cross-contamination didn't occur
        assert not (ws2 / "version_bundles" / "run-before-switch" / "bundle.json").exists()
        assert not (ws1 / "version_bundles" / "run-after-switch" / "bundle.json").exists()


class TestVersionBundleContents:
    """Tests for version bundle content integrity."""

    @pytest.fixture
    def workspace_dir(self):
        """Create workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "version_bundles").mkdir()
            yield workspace

    def test_bundle_contains_required_fields(self, workspace_dir):
        """Version bundle should contain all required compliance fields."""
        store = VersionBundleStore(workspace_dir)
        bundle = store.create_version_bundle(
            run_id="test-run",
            model_name="gpt-4o",
            model_version="2024-05-13",
            extractor_version="v1.0.0",
        )

        # Required fields for compliance
        assert bundle.bundle_id is not None
        assert bundle.bundle_id.startswith("vb_")
        assert bundle.created_at is not None
        assert bundle.model_name == "gpt-4o"
        assert bundle.model_version == "2024-05-13"
        assert bundle.extractor_version == "v1.0.0"

        # Git info (may be None in CI, but should be captured if available)
        assert hasattr(bundle, "git_commit")
        assert hasattr(bundle, "git_dirty")

        # Hashes (may be None if prompts/specs not found)
        assert hasattr(bundle, "prompt_template_hash")
        assert hasattr(bundle, "extraction_spec_hash")

    def test_bundle_persisted_as_json(self, workspace_dir):
        """Bundle should be readable as valid JSON."""
        store = VersionBundleStore(workspace_dir)
        run_id = "json-test-run"
        store.create_version_bundle(run_id=run_id, model_name="gpt-4o")

        # Read raw JSON
        bundle_path = workspace_dir / "version_bundles" / run_id / "bundle.json"
        with open(bundle_path) as f:
            data = json.load(f)

        # Verify structure
        assert "bundle_id" in data
        assert "created_at" in data
        assert "model_name" in data
        assert data["model_name"] == "gpt-4o"

    def test_bundle_id_is_unique(self, workspace_dir):
        """Each bundle should have a unique ID."""
        store = VersionBundleStore(workspace_dir)

        bundles = [
            store.create_version_bundle(run_id=f"run-{i}", model_name="gpt-4o")
            for i in range(5)
        ]

        bundle_ids = [b.bundle_id for b in bundles]
        assert len(set(bundle_ids)) == 5, "All bundle IDs should be unique"
