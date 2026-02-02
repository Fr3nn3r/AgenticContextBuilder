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
from context_builder.storage.index_reader import IndexReader, CLAIMS_INDEX_FILE
from context_builder.storage.index_builder import build_claims_index


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


@pytest.fixture
def output_with_run_and_extractions(tmp_path):
    """Create output structure with per-claim runs and extractions."""
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()

    # Claim 1: with run and extractions
    claim1 = claims_dir / "24-01-VH-1234567_ROBO_TOTAL"
    docs1 = claim1 / "docs"
    doc1_dir = docs1 / "doc_aaa"
    (doc1_dir / "meta").mkdir(parents=True)
    (doc1_dir / "text").mkdir(parents=True)
    with open(doc1_dir / "meta" / "doc.json", "w") as f:
        json.dump({
            "doc_id": "doc_aaa",
            "claim_id": "24-01-VH-1234567",
            "original_filename": "loss.pdf",
            "source_type": "pdf",
            "doc_type": "loss_notice",
            "language": "es",
            "page_count": 1,
        }, f)

    doc2_dir = docs1 / "doc_bbb"
    (doc2_dir / "meta").mkdir(parents=True)
    with open(doc2_dir / "meta" / "doc.json", "w") as f:
        json.dump({
            "doc_id": "doc_bbb",
            "claim_id": "24-01-VH-1234567",
            "original_filename": "police.pdf",
            "source_type": "pdf",
            "doc_type": "police_report",
            "language": "es",
            "page_count": 2,
        }, f)

    # Create per-claim run with extractions
    run_dir = claim1 / "runs" / "run_20260101_100000_abc"
    extractions_dir = run_dir / "extraction"
    extractions_dir.mkdir(parents=True)
    (run_dir / "logs").mkdir(parents=True)
    with open(run_dir / "logs" / "summary.json", "w") as f:
        json.dump({"completed_at": "2026-01-01T10:10:00Z", "status": "complete"}, f)

    with open(extractions_dir / "doc_aaa.json", "w") as f:
        json.dump({
            "doc_id": "doc_aaa",
            "quality_gate": {"status": "pass", "missing_required_fields": [], "reasons": []},
            "fields": [{"name": "valor_asegurado", "value": "50000"}],
        }, f)
    with open(extractions_dir / "doc_bbb.json", "w") as f:
        json.dump({
            "doc_id": "doc_bbb",
            "quality_gate": {"status": "warn", "missing_required_fields": ["field_x"], "reasons": []},
            "fields": [],
        }, f)

    # Add a label for doc_aaa
    labels_dir = doc1_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)
    with open(labels_dir / "latest.json", "w") as f:
        json.dump({"doc_id": "doc_aaa", "field_labels": [{"state": "LABELED"}]}, f)

    # Claim 2: no run, no extractions
    claim2 = claims_dir / "24-02-VH-9999999_COLISION"
    docs2 = claim2 / "docs"
    doc3_dir = docs2 / "doc_ccc"
    (doc3_dir / "meta").mkdir(parents=True)
    with open(doc3_dir / "meta" / "doc.json", "w") as f:
        json.dump({
            "doc_id": "doc_ccc",
            "claim_id": "24-02-VH-9999999",
            "original_filename": "claim.pdf",
            "source_type": "pdf",
            "doc_type": "fnol_form",
            "language": "en",
            "page_count": 1,
        }, f)

    # Global runs dir (empty, ok for this test)
    (tmp_path / "runs").mkdir()

    return tmp_path


class TestBuildClaimsIndex:
    """Tests for build_claims_index."""

    def test_produces_correct_schema(self, output_with_run_and_extractions):
        """Test that build_claims_index produces records matching ClaimSummary."""
        tmp = output_with_run_and_extractions
        records = build_claims_index(tmp / "claims", tmp)

        assert len(records) == 2

        # Find claim 1 (with run)
        c1 = next(r for r in records if r["folder_name"] == "24-01-VH-1234567_ROBO_TOTAL")
        assert c1["claim_id"] == "24-01-VH-1234567"
        assert c1["doc_count"] == 2
        assert set(c1["doc_types"]) == {"loss_notice", "police_report"}
        assert c1["extracted_count"] == 2
        assert c1["labeled_count"] == 1
        assert c1["lob"] == "MOTOR"
        assert c1["risk_score"] >= 0
        assert c1["loss_type"] == "Theft - Total Loss"
        assert c1["amount"] == 50000.0
        assert c1["currency"] == "USD"
        assert c1["status"] == "Reviewed"
        assert c1["in_run"] is True
        assert c1["gate_pass_count"] == 1
        assert c1["gate_warn_count"] == 1
        assert c1["closed_date"] is not None
        assert c1["last_processed"] is not None

        # Find claim 2 (no run)
        c2 = next(r for r in records if r["folder_name"] == "24-02-VH-9999999_COLISION")
        assert c2["claim_id"] == "24-02-VH-9999999"
        assert c2["doc_count"] == 1
        assert c2["extracted_count"] == 0
        assert c2["labeled_count"] == 0
        assert c2["loss_type"] == "Collision"
        assert c2["status"] == "Not Reviewed"
        assert c2["in_run"] is False

    def test_empty_claims_dir(self, tmp_path):
        """Test with non-existent claims dir."""
        records = build_claims_index(tmp_path / "nonexistent", tmp_path)
        assert records == []

    def test_build_all_indexes_writes_claims_index(self, output_with_run_and_extractions):
        """Test that build_all_indexes creates claims_index.jsonl."""
        tmp = output_with_run_and_extractions
        stats = build_all_indexes(tmp)

        registry = tmp / "registry"
        assert (registry / CLAIMS_INDEX_FILE).exists()

        # Read it back
        import json
        lines = []
        with open(registry / CLAIMS_INDEX_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(json.loads(line))
        assert len(lines) == 2


class TestIndexReaderClaimsIndex:
    """Tests for IndexReader.get_all_claim_summaries."""

    def test_returns_none_without_index(self, tmp_path):
        """Test returns None when claims_index.jsonl doesn't exist."""
        registry = tmp_path / "registry"
        registry.mkdir()
        reader = IndexReader(registry)
        assert reader.get_all_claim_summaries() is None

    def test_returns_data_with_index(self, output_with_run_and_extractions):
        """Test returns data when index exists."""
        tmp = output_with_run_and_extractions
        build_all_indexes(tmp)

        reader = IndexReader(tmp / "registry")
        summaries = reader.get_all_claim_summaries()
        assert summaries is not None
        assert len(summaries) == 2
        assert all(isinstance(s, dict) for s in summaries)

    def test_caches_result(self, output_with_run_and_extractions):
        """Test that repeated calls return cached data."""
        tmp = output_with_run_and_extractions
        build_all_indexes(tmp)

        reader = IndexReader(tmp / "registry")
        first = reader.get_all_claim_summaries()
        second = reader.get_all_claim_summaries()
        assert first is second  # Same object reference

    def test_invalidate_clears_cache(self, output_with_run_and_extractions):
        """Test that invalidate clears the claims index cache."""
        tmp = output_with_run_and_extractions
        build_all_indexes(tmp)

        reader = IndexReader(tmp / "registry")
        reader.get_all_claim_summaries()
        reader.invalidate()
        assert reader._claims_index is None


class TestClaimsServiceFastPath:
    """Tests for the fast-path in ClaimsService.list_claims."""

    def test_fast_path_used_when_index_exists(self, output_with_run_and_extractions):
        """Test that fast-path returns ClaimSummary objects from index."""
        from context_builder.api.models import ClaimSummary
        from context_builder.api.services.claims import ClaimsService

        tmp = output_with_run_and_extractions
        build_all_indexes(tmp)

        service = ClaimsService(
            data_dir=tmp / "claims",
            storage_factory=lambda: None,  # Should not be called
        )
        claims = service.list_claims(run_id=None)

        assert len(claims) == 2
        assert all(isinstance(c, ClaimSummary) for c in claims)
        # Should be sorted by risk_score descending
        assert claims[0].risk_score >= claims[1].risk_score

    def test_fallback_when_index_missing(self, output_with_run_and_extractions):
        """Test that missing index falls through to existing code."""
        from context_builder.api.services.claims import ClaimsService
        from context_builder.storage import FileStorage, StorageFacade

        tmp = output_with_run_and_extractions
        # Don't build indexes — no claims_index.jsonl

        storage = FileStorage(tmp)
        facade = StorageFacade.from_storage(storage)
        service = ClaimsService(
            data_dir=tmp / "claims",
            storage_factory=lambda: facade,
        )
        claims = service.list_claims(run_id=None)

        # Should still work via filesystem path
        assert len(claims) == 2

    def test_run_id_bypasses_fast_path(self, output_with_run_and_extractions):
        """Test that explicit run_id skips fast-path and calls storage_factory."""
        from context_builder.api.services.claims import ClaimsService
        from context_builder.storage import FileStorage, StorageFacade

        tmp = output_with_run_and_extractions
        build_all_indexes(tmp)

        storage = FileStorage(tmp)
        facade = StorageFacade.from_storage(storage)
        factory_called = []

        def tracking_factory():
            factory_called.append(True)
            return facade

        service = ClaimsService(
            data_dir=tmp / "claims",
            storage_factory=tracking_factory,
        )
        # With run_id=None and index present, fast-path is used (factory NOT called)
        service.list_claims(run_id=None)
        assert len(factory_called) == 0, "Fast-path should not call storage_factory"

        # With explicit run_id, fast-path is bypassed (factory IS called)
        service.list_claims(run_id="run_20260101_100000_abc")
        assert len(factory_called) == 1, "Fallback path should call storage_factory"
