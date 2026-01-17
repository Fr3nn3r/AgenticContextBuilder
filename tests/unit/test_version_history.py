"""Unit tests for version history tracking in compliance stores.

Tests:
- Truth store version history
- Prompt config version history
- Label version history
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestTruthStoreHistory:
    """Tests for TruthStore version history."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with claims folder for proper path resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create claims folder so registry resolves correctly to temp_dir/registry
            (tmpdir / "claims").mkdir(exist_ok=True)
            yield tmpdir

    @pytest.fixture
    def truth_store(self, temp_dir):
        """Create a TruthStore instance."""
        from context_builder.storage.truth_store import TruthStore
        return TruthStore(temp_dir)

    def test_save_creates_history_file(self, temp_dir, truth_store):
        """Test that saving truth creates a history file."""
        file_md5 = "test_creates_history"
        truth_store.save_truth_by_file_md5(file_md5, {"doc_type": "invoice"})

        history_path = temp_dir / "registry" / "truth" / file_md5 / "history.jsonl"
        assert history_path.exists()

    def test_save_appends_to_history(self, truth_store):
        """Test that each save appends to history."""
        file_md5 = "test_append_history"

        # Save multiple versions
        for i in range(3):
            truth_store.save_truth_by_file_md5(file_md5, {"version": i})

        history = truth_store.get_truth_history(file_md5)
        assert len(history) == 3

    def test_history_preserves_order(self, truth_store):
        """Test that history returns entries in chronological order."""
        file_md5 = "test_order_history"

        for i in range(5):
            truth_store.save_truth_by_file_md5(file_md5, {"version": i})

        history = truth_store.get_truth_history(file_md5)
        for i, entry in enumerate(history):
            assert entry["version"] == i

    def test_version_metadata_added(self, truth_store):
        """Test that version metadata is added to entries."""
        file_md5 = "test_metadata_history"
        truth_store.save_truth_by_file_md5(file_md5, {"data": "test"})

        history = truth_store.get_truth_history(file_md5)
        assert len(history) == 1

        entry = history[0]
        assert "_version_metadata" in entry
        assert "saved_at" in entry["_version_metadata"]
        assert "version_number" in entry["_version_metadata"]
        assert entry["_version_metadata"]["version_number"] == 1

    def test_version_numbers_increment(self, truth_store):
        """Test that version numbers increment correctly."""
        file_md5 = "test_increment_history"

        for i in range(4):
            truth_store.save_truth_by_file_md5(file_md5, {"version": i})

        history = truth_store.get_truth_history(file_md5)
        for i, entry in enumerate(history):
            assert entry["_version_metadata"]["version_number"] == i + 1

    def test_get_specific_version(self, truth_store):
        """Test retrieving a specific version."""
        file_md5 = "test_specific_version"

        for i in range(3):
            truth_store.save_truth_by_file_md5(file_md5, {"data": f"version_{i}"})

        v1 = truth_store.get_truth_version(file_md5, 1)
        v2 = truth_store.get_truth_version(file_md5, 2)
        v3 = truth_store.get_truth_version(file_md5, 3)

        assert v1["data"] == "version_0"
        assert v2["data"] == "version_1"
        assert v3["data"] == "version_2"

    def test_get_invalid_version_returns_none(self, truth_store):
        """Test that invalid version numbers return None."""
        file_md5 = "test_invalid_version"
        truth_store.save_truth_by_file_md5(file_md5, {"data": "test"})

        assert truth_store.get_truth_version(file_md5, 0) is None
        assert truth_store.get_truth_version(file_md5, 2) is None
        assert truth_store.get_truth_version(file_md5, -1) is None

    def test_latest_json_has_version_metadata(self, truth_store):
        """Test that latest.json also includes version metadata."""
        file_md5 = "test_latest_metadata"
        truth_store.save_truth_by_file_md5(file_md5, {"data": "test"})

        latest = truth_store.get_truth_by_file_md5(file_md5)
        assert "_version_metadata" in latest
        assert latest["_version_metadata"]["version_number"] == 1

    def test_empty_history_returns_empty_list(self, truth_store):
        """Test that non-existent file returns empty history."""
        history = truth_store.get_truth_history("nonexistent_xyz")
        assert history == []


class TestPromptConfigHistory:
    """Tests for PromptConfigService change history."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_service(self, temp_dir):
        """Create a PromptConfigService instance."""
        from context_builder.api.services.prompt_config import PromptConfigService
        return PromptConfigService(temp_dir)

    def test_create_logs_to_history(self, config_service):
        """Test that creating a config logs to history."""
        config_service.create_config(name="test_config", model="gpt-4o")

        history = config_service.get_config_history()
        assert len(history) >= 1

        # Find create action (may have init action first)
        create_entry = next((h for h in history if h["action"] == "create"), None)
        assert create_entry is not None
        assert create_entry["config_id"] == "test_config"

    def test_update_logs_to_history(self, config_service):
        """Test that updating a config logs to history."""
        # Create first
        created = config_service.create_config(name="update_test", model="gpt-4o")
        assert created is not None, "Config should be created"

        # Update - use the actual id from created config
        result = config_service.update_config(created.id, {"temperature": 0.5})
        assert result is not None, "Update should succeed"

        history = config_service.get_config_history()
        update_entry = next((h for h in history if h["action"] == "update"), None)
        assert update_entry is not None, f"Update entry not found. History: {history}"
        assert update_entry["config_id"] == created.id

    def test_delete_logs_to_history(self, config_service):
        """Test that deleting a config logs to history."""
        # Create two configs (need at least one remaining after defaults)
        config_service.create_config(name="delete_config1", model="gpt-4o")
        config_service.create_config(name="delete_config2", model="gpt-4o")

        # Delete one
        config_service.delete_config("delete_config1")

        history = config_service.get_config_history()
        delete_entry = next((h for h in history if h["action"] == "delete"), None)
        assert delete_entry is not None
        assert delete_entry["config_id"] == "delete_config1"

    def test_set_default_logs_to_history(self, config_service):
        """Test that setting default logs to history."""
        config_service.create_config(name="default_config1", model="gpt-4o")
        config_service.create_config(name="default_config2", model="gpt-4o")

        config_service.set_default("default_config2")

        history = config_service.get_config_history()
        set_default_entry = next((h for h in history if h["action"] == "set_default"), None)
        assert set_default_entry is not None
        assert set_default_entry["config_id"] == "default_config2"

    def test_history_has_timestamps(self, config_service):
        """Test that history entries have timestamps."""
        config_service.create_config(name="timestamp_test", model="gpt-4o")

        history = config_service.get_config_history()
        for entry in history:
            assert "timestamp" in entry
            # Should be ISO format
            datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

    def test_history_has_snapshot(self, config_service):
        """Test that history entries include config snapshot."""
        config_service.create_config(name="snapshot_test", model="gpt-4o")

        history = config_service.get_config_history()
        for entry in history:
            assert "snapshot" in entry
            assert isinstance(entry["snapshot"], list)

    def test_history_file_location(self, config_service, temp_dir):
        """Test that history file is in expected location."""
        config_service.create_config(name="location_test", model="gpt-4o")

        history_path = temp_dir / "prompt_configs_history.jsonl"
        assert history_path.exists()


class TestLabelHistory:
    """Tests for FileStorage label version history."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with document structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create document structure
            doc_dir = tmpdir / "claims" / "CLM-001" / "docs" / "DOC-001"
            (doc_dir / "meta").mkdir(parents=True)
            with open(doc_dir / "meta" / "doc.json", "w") as f:
                json.dump({"doc_id": "DOC-001", "claim_id": "CLM-001"}, f)
            yield tmpdir

    @pytest.fixture
    def storage(self, temp_dir):
        """Create a FileStorage instance."""
        from context_builder.storage.filesystem import FileStorage
        return FileStorage(temp_dir / "claims")

    def test_save_creates_history_file(self, storage, temp_dir):
        """Test that saving a label creates a history file."""
        storage.save_label("DOC-001", {"doc_id": "DOC-001", "data": "test"})

        # Labels are now stored in registry/labels/{doc_id}_history.jsonl
        history_path = temp_dir / "registry" / "labels" / "DOC-001_history.jsonl"
        assert history_path.exists()

    def test_save_appends_to_history(self, storage):
        """Test that each save appends to history."""
        for i in range(3):
            storage.save_label("DOC-001", {"doc_id": "DOC-001", "version": i})

        history = storage.get_label_history("DOC-001")
        assert len(history) == 3

    def test_history_preserves_order(self, storage):
        """Test that history returns entries in chronological order."""
        for i in range(5):
            storage.save_label("DOC-001", {"doc_id": "DOC-001", "version": i})

        history = storage.get_label_history("DOC-001")
        for i, entry in enumerate(history):
            assert entry["version"] == i

    def test_version_metadata_added(self, storage):
        """Test that version metadata is added."""
        storage.save_label("DOC-001", {"doc_id": "DOC-001", "data": "test"})

        history = storage.get_label_history("DOC-001")
        assert len(history) == 1

        entry = history[0]
        assert "_version_metadata" in entry
        assert "saved_at" in entry["_version_metadata"]
        assert "version_number" in entry["_version_metadata"]

    def test_version_numbers_increment(self, storage):
        """Test that version numbers increment."""
        for i in range(4):
            storage.save_label("DOC-001", {"doc_id": "DOC-001", "version": i})

        history = storage.get_label_history("DOC-001")
        for i, entry in enumerate(history):
            assert entry["_version_metadata"]["version_number"] == i + 1

    def test_latest_json_has_version_metadata(self, storage):
        """Test that latest.json includes version metadata."""
        storage.save_label("DOC-001", {"doc_id": "DOC-001", "data": "test"})

        latest = storage.get_label("DOC-001")
        assert "_version_metadata" in latest
        assert latest["_version_metadata"]["version_number"] == 1

    def test_empty_history_returns_empty_list(self, storage):
        """Test that non-existent doc returns empty history."""
        history = storage.get_label_history("NONEXISTENT")
        assert history == []

    def test_history_preserves_original_data(self, storage):
        """Test that history preserves original data without modification."""
        original = {
            "doc_id": "DOC-001",
            "field_labels": [
                {"field": "claim_number", "value": "CLM-001"},
                {"field": "date", "value": "2026-01-14"},
            ],
            "review": {"reviewer": "user@example.com"},
        }
        storage.save_label("DOC-001", original)

        history = storage.get_label_history("DOC-001")
        entry = history[0]

        # Original data should be preserved
        assert entry["doc_id"] == "DOC-001"
        assert len(entry["field_labels"]) == 2
        assert entry["review"]["reviewer"] == "user@example.com"


class TestVersionBundleStore:
    """Tests for VersionBundleStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def bundle_store(self, temp_dir):
        """Create a VersionBundleStore instance."""
        from context_builder.storage.version_bundles import VersionBundleStore
        return VersionBundleStore(temp_dir)

    def test_create_bundle(self, bundle_store):
        """Test creating a version bundle."""
        bundle = bundle_store.create_version_bundle(
            run_id="run_20260114_120000",
            model_name="gpt-4o",
        )

        assert bundle.bundle_id.startswith("vb_")
        assert bundle.model_name == "gpt-4o"
        assert bundle.created_at is not None

    def test_retrieve_bundle(self, bundle_store):
        """Test retrieving a version bundle."""
        original = bundle_store.create_version_bundle(
            run_id="run_20260114_120000",
            model_name="gpt-4o",
        )

        retrieved = bundle_store.get_version_bundle("run_20260114_120000")
        assert retrieved is not None
        assert retrieved.bundle_id == original.bundle_id
        assert retrieved.model_name == original.model_name

    def test_list_bundles(self, bundle_store):
        """Test listing all bundles."""
        bundle_store.create_version_bundle(run_id="run_1", model_name="gpt-4o")
        bundle_store.create_version_bundle(run_id="run_2", model_name="gpt-4o")
        bundle_store.create_version_bundle(run_id="run_3", model_name="gpt-4o")

        run_ids = bundle_store.list_bundles()
        assert len(run_ids) == 3
        assert "run_1" in run_ids
        assert "run_2" in run_ids
        assert "run_3" in run_ids

    def test_bundle_includes_git_info(self, bundle_store):
        """Test that bundle captures git info when available."""
        bundle = bundle_store.create_version_bundle(
            run_id="run_test",
            model_name="gpt-4o",
        )

        # Git info may or may not be available depending on environment
        # Just verify the fields exist
        assert hasattr(bundle, "git_commit")
        assert hasattr(bundle, "git_dirty")

    def test_bundle_includes_version_info(self, bundle_store):
        """Test that bundle captures version info."""
        bundle = bundle_store.create_version_bundle(
            run_id="run_test",
            model_name="gpt-4o",
            extractor_version="v1.0.0",
        )

        assert bundle.extractor_version == "v1.0.0"
        # contextbuilder_version comes from pyproject.toml
        assert bundle.contextbuilder_version == "0.2.0"

    def test_nonexistent_bundle_returns_none(self, bundle_store):
        """Test that getting nonexistent bundle returns None."""
        result = bundle_store.get_version_bundle("nonexistent_run")
        assert result is None

    def test_bundle_stored_as_json(self, bundle_store, temp_dir):
        """Test that bundle is stored as JSON file."""
        bundle_store.create_version_bundle(
            run_id="run_test",
            model_name="gpt-4o",
        )

        bundle_path = temp_dir / "version_bundles" / "run_test" / "bundle.json"
        assert bundle_path.exists()

        with open(bundle_path) as f:
            data = json.load(f)
        assert data["model_name"] == "gpt-4o"
