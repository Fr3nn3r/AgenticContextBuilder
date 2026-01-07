"""Unit tests for the Storage abstraction layer."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from context_builder.storage import (
    FileStorage,
    build_all_indexes,
    ClaimRef,
    DocRef,
    RunRef,
    LabelSummary,
)
from context_builder.storage.index_reader import IndexReader


@pytest.fixture
def sample_output_structure(tmp_path):
    """Create a minimal output structure for testing."""
    # Create claims directory
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()

    # Create a claim with docs
    claim_folder = claims_dir / "24-01-VH-1234567"
    docs_dir = claim_folder / "docs"
    docs_dir.mkdir(parents=True)

    # Create doc 1
    doc1_dir = docs_dir / "abc123def456"
    (doc1_dir / "meta").mkdir(parents=True)
    (doc1_dir / "text").mkdir(parents=True)
    (doc1_dir / "source").mkdir(parents=True)
    (doc1_dir / "labels").mkdir(parents=True)

    # Write doc.json
    doc1_meta = {
        "doc_id": "abc123def456",
        "claim_id": "24-01-VH-1234567",
        "original_filename": "test_doc.pdf",
        "source_type": "pdf",
        "doc_type": "loss_notice",
        "doc_type_confidence": 0.95,
        "language": "es",
        "file_md5": "abc123def456789012345678901234",
        "content_md5": "def456abc123789012345678901234",
        "page_count": 2,
        "created_at": "2026-01-07T10:00:00Z",
    }
    with open(doc1_dir / "meta" / "doc.json", "w") as f:
        json.dump(doc1_meta, f)

    # Write pages.json
    pages_data = {
        "schema_version": "doc_text_v1",
        "pages": [
            {"page": 1, "text": "Page 1 content", "text_md5": "md5hash1"},
            {"page": 2, "text": "Page 2 content", "text_md5": "md5hash2"},
        ],
    }
    with open(doc1_dir / "text" / "pages.json", "w") as f:
        json.dump(pages_data, f)

    # Create a source file
    (doc1_dir / "source" / "original.pdf").write_bytes(b"%PDF-1.4 fake pdf")

    # Create doc 2
    doc2_dir = docs_dir / "xyz789uvw012"
    (doc2_dir / "meta").mkdir(parents=True)
    (doc2_dir / "text").mkdir(parents=True)

    doc2_meta = {
        "doc_id": "xyz789uvw012",
        "claim_id": "24-01-VH-1234567",
        "original_filename": "police_report.png",
        "source_type": "image",
        "doc_type": "police_report",
        "doc_type_confidence": 0.88,
        "language": "es",
        "file_md5": "xyz789uvw012345678901234567890",
        "content_md5": "uvw012xyz789345678901234567890",
        "page_count": 1,
        "created_at": "2026-01-07T10:05:00Z",
    }
    with open(doc2_dir / "meta" / "doc.json", "w") as f:
        json.dump(doc2_meta, f)

    # Create runs directory
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    run_dir = runs_dir / "run_20260107_100000_abc123"
    run_dir.mkdir()

    # Write manifest
    manifest = {
        "run_id": "run_20260107_100000_abc123",
        "started_at": "2026-01-07T10:00:00Z",
        "ended_at": "2026-01-07T10:10:00Z",
        "claims_count": 1,
    }
    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Write summary
    summary = {
        "run_id": "run_20260107_100000_abc123",
        "status": "complete",
        "docs_total": 2,
        "docs_success": 2,
        "completed_at": "2026-01-07T10:10:00Z",
    }
    with open(run_dir / "summary.json", "w") as f:
        json.dump(summary, f)

    # Mark complete
    (run_dir / ".complete").touch()

    return tmp_path


class TestIndexBuilder:
    """Tests for index building."""

    def test_build_all_indexes(self, sample_output_structure):
        """Test that indexes are built correctly."""
        stats = build_all_indexes(sample_output_structure)

        assert stats["doc_count"] == 2
        assert stats["run_count"] == 1
        assert stats["claim_count"] == 1

        # Verify files exist
        registry_dir = sample_output_structure / "registry"
        assert (registry_dir / "doc_index.jsonl").exists()
        assert (registry_dir / "run_index.jsonl").exists()
        assert (registry_dir / "registry_meta.json").exists()


class TestIndexReader:
    """Tests for IndexReader."""

    def test_reader_availability(self, sample_output_structure):
        """Test that reader detects index availability."""
        registry_dir = sample_output_structure / "registry"

        # Before building indexes
        reader = IndexReader(registry_dir)
        assert not reader.is_available

        # After building indexes
        build_all_indexes(sample_output_structure)
        reader.invalidate()
        assert reader.is_available

    def test_get_doc(self, sample_output_structure):
        """Test document lookup by ID."""
        build_all_indexes(sample_output_structure)
        reader = IndexReader(sample_output_structure / "registry")

        doc = reader.get_doc("abc123def456")
        assert doc is not None
        assert doc.doc_id == "abc123def456"
        assert doc.doc_type == "loss_notice"
        assert doc.claim_id == "24-01-VH-1234567"

    def test_get_all_claims(self, sample_output_structure):
        """Test listing all claims."""
        build_all_indexes(sample_output_structure)
        reader = IndexReader(sample_output_structure / "registry")

        claims = reader.get_all_claims()
        assert len(claims) == 1
        claim_id, folder, count = claims[0]
        assert claim_id == "24-01-VH-1234567"
        assert count == 2

    def test_get_all_runs(self, sample_output_structure):
        """Test listing all runs."""
        build_all_indexes(sample_output_structure)
        reader = IndexReader(sample_output_structure / "registry")

        runs = reader.get_all_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run_20260107_100000_abc123"
        assert runs[0].status == "complete"


class TestFileStorage:
    """Tests for FileStorage implementation."""

    def test_storage_with_indexes(self, sample_output_structure):
        """Test storage uses indexes when available."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        assert storage.has_indexes()

    def test_list_claims(self, sample_output_structure):
        """Test listing claims."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        claims = storage.list_claims()
        assert len(claims) == 1
        assert claims[0].claim_id == "24-01-VH-1234567"
        assert claims[0].doc_count == 2

    def test_list_docs(self, sample_output_structure):
        """Test listing documents in a claim."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        docs = storage.list_docs("24-01-VH-1234567")
        assert len(docs) == 2

        doc_ids = {d.doc_id for d in docs}
        assert "abc123def456" in doc_ids
        assert "xyz789uvw012" in doc_ids

    def test_list_runs(self, sample_output_structure):
        """Test listing runs."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        runs = storage.list_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run_20260107_100000_abc123"

    def test_get_doc(self, sample_output_structure):
        """Test getting document bundle."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        doc = storage.get_doc("abc123def456")
        assert doc is not None
        assert doc.doc_id == "abc123def456"
        assert doc.claim_id == "24-01-VH-1234567"
        assert doc.metadata["doc_type"] == "loss_notice"

    def test_get_doc_text(self, sample_output_structure):
        """Test getting document text."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        text = storage.get_doc_text("abc123def456")
        assert text is not None
        assert len(text.pages) == 2
        assert text.pages[0]["text"] == "Page 1 content"

    def test_get_doc_source_path(self, sample_output_structure):
        """Test getting source file path."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        path = storage.get_doc_source_path("abc123def456")
        assert path is not None
        assert path.suffix == ".pdf"
        assert path.exists()

    def test_save_and_get_label(self, sample_output_structure):
        """Test saving and retrieving labels."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        # Save a label
        label_data = {
            "schema_version": "label_v3",
            "doc_id": "abc123def456",
            "claim_id": "24-01-VH-1234567",
            "review": {
                "reviewed_at": datetime.utcnow().isoformat() + "Z",
                "reviewer": "test_user",
                "notes": "Test label",
            },
            "field_labels": [
                {"field_name": "test_field", "state": "LABELED", "truth_value": "test"}
            ],
            "doc_labels": {"doc_type_correct": True},
        }

        storage.save_label("abc123def456", label_data)

        # Retrieve label
        retrieved = storage.get_label("abc123def456")
        assert retrieved is not None
        assert retrieved["schema_version"] == "label_v3"
        assert retrieved["review"]["reviewer"] == "test_user"

    def test_fallback_without_indexes(self, sample_output_structure):
        """Test storage falls back to filesystem when indexes missing."""
        # Don't build indexes
        storage = FileStorage(sample_output_structure)

        assert not storage.has_indexes()

        # Should still work via filesystem scan
        claims = storage.list_claims()
        assert len(claims) == 1

        doc = storage.get_doc("abc123def456")
        assert doc is not None

    def test_get_nonexistent_doc(self, sample_output_structure):
        """Test getting a document that doesn't exist."""
        build_all_indexes(sample_output_structure)
        storage = FileStorage(sample_output_structure)

        doc = storage.get_doc("nonexistent123")
        assert doc is None
