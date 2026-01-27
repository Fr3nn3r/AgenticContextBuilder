"""Tests for ClaimRunStorage."""

import json
import time

import pytest
from pathlib import Path

from context_builder.storage.claim_run import ClaimRunStorage


@pytest.fixture
def claim_folder(tmp_path):
    """Create a temporary claim folder."""
    folder = tmp_path / "CLM-001"
    folder.mkdir()
    return folder


@pytest.fixture
def storage(claim_folder):
    """Create ClaimRunStorage instance."""
    return ClaimRunStorage(claim_folder)


class TestClaimRunIdGeneration:
    """Tests for claim run ID generation."""

    def test_generate_claim_run_id_format(self, storage):
        """Test claim run ID has correct format."""
        run_id = storage.generate_claim_run_id()
        assert run_id.startswith("clm_")
        parts = run_id.split("_")
        assert len(parts) == 4  # clm, date, time, hash
        assert len(parts[3]) == 6  # 6-char hash

    def test_generate_claim_run_id_unique(self, storage):
        """Test that multiple IDs are unique."""
        ids = set()
        for _ in range(10):
            run_id = storage.generate_claim_run_id()
            ids.add(run_id)
            # Small delay to ensure different timestamps
            time.sleep(0.001)
        # All IDs should be unique
        assert len(ids) == 10


class TestCreateClaimRun:
    """Tests for claim run creation."""

    def test_create_claim_run(self, storage):
        """Test basic claim run creation."""
        manifest = storage.create_claim_run(
            extraction_runs=["run_123"],
            contextbuilder_version="0.5.0",
        )

        assert manifest.claim_run_id.startswith("clm_")
        assert manifest.extraction_runs_considered == ["run_123"]
        assert manifest.contextbuilder_version == "0.5.0"
        assert manifest.claim_id == "CLM-001"

    def test_create_claim_run_creates_directory(self, storage):
        """Test that directory is created."""
        manifest = storage.create_claim_run(
            extraction_runs=["run_123"],
            contextbuilder_version="0.5.0",
        )

        run_dir = storage.claim_runs_dir / manifest.claim_run_id
        assert run_dir.exists()
        assert (run_dir / "manifest.json").exists()

    def test_create_claim_run_manifest_content(self, storage):
        """Test manifest file content."""
        manifest = storage.create_claim_run(
            extraction_runs=["run_1", "run_2"],
            contextbuilder_version="1.0.0",
        )

        manifest_path = storage.claim_runs_dir / manifest.claim_run_id / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["claim_run_id"] == manifest.claim_run_id
        assert data["claim_id"] == "CLM-001"
        assert data["extraction_runs_considered"] == ["run_1", "run_2"]
        assert data["contextbuilder_version"] == "1.0.0"
        assert data["schema_version"] == "claim_run_v1"


class TestReadWriteManifest:
    """Tests for manifest read/write."""

    def test_write_and_read_manifest(self, storage):
        """Test round-trip manifest write/read."""
        manifest = storage.create_claim_run(
            extraction_runs=["run_1"],
            contextbuilder_version="0.5.0",
        )

        # Modify and write
        manifest.stages_completed = ["reconciliation"]
        storage.write_manifest(manifest)

        # Read back
        read_manifest = storage.read_manifest(manifest.claim_run_id)
        assert read_manifest is not None
        assert read_manifest.stages_completed == ["reconciliation"]

    def test_read_manifest_not_found(self, storage):
        """Test reading non-existent manifest."""
        result = storage.read_manifest("nonexistent_id")
        assert result is None


class TestListClaimRuns:
    """Tests for listing claim runs."""

    def test_list_claim_runs_empty(self, storage):
        """Test listing when no runs exist."""
        assert storage.list_claim_runs() == []

    def test_list_claim_runs_sorted(self, storage):
        """Test runs are sorted newest first (by ID string)."""
        # Create multiple runs
        run1 = storage.create_claim_run(["run_1"], "0.5.0")
        run2 = storage.create_claim_run(["run_2"], "0.5.0")
        run3 = storage.create_claim_run(["run_3"], "0.5.0")

        runs = storage.list_claim_runs()
        assert len(runs) == 3
        # Should be sorted reverse alphabetically (which is newest first for timestamp-based IDs)
        assert runs == sorted([run1.claim_run_id, run2.claim_run_id, run3.claim_run_id], reverse=True)

    def test_list_claim_runs_ignores_non_clm_dirs(self, storage, claim_folder):
        """Test that non-clm_ directories are ignored."""
        storage.create_claim_run(["run_1"], "0.5.0")

        # Create a non-clm_ directory
        (storage.claim_runs_dir / "some_other_dir").mkdir(parents=True)

        runs = storage.list_claim_runs()
        assert len(runs) == 1


class TestGetLatestClaimRunId:
    """Tests for getting latest claim run ID."""

    def test_get_latest_claim_run_id_empty(self, storage):
        """Test when no runs exist."""
        assert storage.get_latest_claim_run_id() is None

    def test_get_latest_claim_run_id(self, storage):
        """Test getting latest run ID (sorted by string, reverse order)."""
        run1 = storage.create_claim_run(["run_1"], "0.5.0")
        run2 = storage.create_claim_run(["run_2"], "0.5.0")

        # Latest is the one that sorts last in reverse order
        expected_latest = max(run1.claim_run_id, run2.claim_run_id)
        assert storage.get_latest_claim_run_id() == expected_latest


class TestWriteAndReadFromClaimRun:
    """Tests for writing and reading files from claim runs."""

    def test_write_and_read_from_claim_run(self, storage):
        """Test round-trip file write/read."""
        manifest = storage.create_claim_run(["run_1"], "0.5.0")

        data = {"test": "data", "number": 42}
        storage.write_to_claim_run(manifest.claim_run_id, "test.json", data)

        read_data = storage.read_from_claim_run(manifest.claim_run_id, "test.json")
        assert read_data == data

    def test_write_creates_directory(self, storage):
        """Test writing to non-existent run directory creates it."""
        # Manually construct a run ID without creating via create_claim_run
        run_id = "clm_20260126_120000_abc123"

        data = {"test": "data"}
        path = storage.write_to_claim_run(run_id, "test.json", data)

        assert path.exists()
        assert storage.read_from_claim_run(run_id, "test.json") == data

    def test_read_from_claim_run_not_found(self, storage):
        """Test reading non-existent file."""
        result = storage.read_from_claim_run("nonexistent", "test.json")
        assert result is None


class TestReadWithFallback:
    """Tests for read_with_fallback method."""

    def test_read_with_fallback_prefers_claim_run(self, storage, claim_folder):
        """Test that claim run data is preferred over legacy."""
        # Create legacy file
        context_dir = claim_folder / "context"
        context_dir.mkdir()
        legacy_data = {"source": "legacy"}
        with open(context_dir / "claim_facts.json", "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # Create claim run with newer data
        manifest = storage.create_claim_run(["run_1"], "0.5.0")
        new_data = {"source": "claim_run"}
        storage.write_to_claim_run(manifest.claim_run_id, "claim_facts.json", new_data)

        # Should prefer claim run
        result = storage.read_with_fallback("claim_facts.json")
        assert result["source"] == "claim_run"

    def test_read_with_fallback_uses_legacy(self, storage, claim_folder):
        """Test fallback to legacy when no claim runs exist."""
        # Create legacy file only
        context_dir = claim_folder / "context"
        context_dir.mkdir()
        legacy_data = {"source": "legacy"}
        with open(context_dir / "claim_facts.json", "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # No claim runs exist
        result = storage.read_with_fallback("claim_facts.json")
        assert result["source"] == "legacy"

    def test_read_with_fallback_returns_none(self, storage):
        """Test returns None when file not found anywhere."""
        result = storage.read_with_fallback("claim_facts.json")
        assert result is None

    def test_read_with_fallback_claim_run_missing_file(self, storage, claim_folder):
        """Test fallback when claim run exists but file is missing."""
        # Create claim run without the target file
        storage.create_claim_run(["run_1"], "0.5.0")

        # Create legacy file
        context_dir = claim_folder / "context"
        context_dir.mkdir()
        legacy_data = {"source": "legacy"}
        with open(context_dir / "claim_facts.json", "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # Should fall back to legacy since claim run doesn't have the file
        result = storage.read_with_fallback("claim_facts.json")
        assert result["source"] == "legacy"


class TestGetClaimRunPath:
    """Tests for get_claim_run_path."""

    def test_get_claim_run_path(self, storage):
        """Test getting path to claim run directory."""
        run_id = "clm_20260126_120000_abc123"
        path = storage.get_claim_run_path(run_id)
        assert path == storage.claim_runs_dir / run_id
