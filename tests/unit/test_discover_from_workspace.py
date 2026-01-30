"""Unit tests for discover_from_workspace() in pipeline discovery."""

import json
import logging
from pathlib import Path

import pytest

from context_builder.pipeline.discovery import discover_from_workspace


def _write_doc_index(registry_dir: Path, records: list[dict]) -> Path:
    """Write records to doc_index.jsonl and return the file path."""
    registry_dir.mkdir(parents=True, exist_ok=True)
    index_path = registry_dir / "doc_index.jsonl"
    with open(index_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return index_path


def _create_doc_tree(workspace: Path, claim_id: str, doc_id: str, file_md5: str = "abc123") -> dict:
    """Create doc folder structure with doc.json and a source file.

    Returns the index record dict for this document.
    """
    doc_root = f"claims/{claim_id}/docs/{doc_id}"
    doc_dir = workspace / doc_root

    # Create meta/doc.json
    meta_dir = doc_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    doc_json = {
        "doc_id": doc_id,
        "claim_id": claim_id,
        "file_md5": file_md5,
        "original_filename": f"{doc_id}.pdf",
        "source_type": "pdf",
        "doc_type": "unknown",
    }
    with open(meta_dir / "doc.json", "w") as f:
        json.dump(doc_json, f)

    # Create source/original.pdf
    source_dir = doc_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "original.pdf").write_bytes(b"%PDF-1.4 fake")

    # Return index record
    return {
        "doc_id": doc_id,
        "claim_id": claim_id,
        "claim_folder": claim_id,
        "doc_type": "unknown",
        "filename": f"{doc_id}.pdf",
        "source_type": "pdf",
        "doc_root": doc_root.replace("/", "\\"),  # Match Windows-style from real index
        "language": "en",
        "page_count": 1,
    }


class TestDiscoverFromWorkspace:
    """Tests for discover_from_workspace()."""

    def test_happy_path_no_filters(self, tmp_path):
        """All docs returned when no filters applied."""
        ws = tmp_path / "workspace"
        rec1 = _create_doc_tree(ws, "CLM-001", "aaa111", file_md5="md5_aaa")
        rec1["doc_type"] = "cost_estimate"
        rec2 = _create_doc_tree(ws, "CLM-002", "bbb222", file_md5="md5_bbb")
        rec2["doc_type"] = "service_history"
        _write_doc_index(ws / "registry", [rec1, rec2])

        claims = discover_from_workspace(ws)

        assert len(claims) == 2
        assert claims[0].claim_id == "CLM-001"
        assert claims[1].claim_id == "CLM-002"
        assert len(claims[0].documents) == 1
        assert len(claims[1].documents) == 1
        assert claims[0].documents[0].doc_id == "aaa111"
        assert claims[0].documents[0].file_md5 == "md5_aaa"
        assert claims[0].documents[0].needs_ingestion is False

    def test_filter_by_doc_type(self, tmp_path):
        """Only matching doc_type returned."""
        ws = tmp_path / "workspace"
        rec1 = _create_doc_tree(ws, "CLM-001", "aaa111")
        rec1["doc_type"] = "cost_estimate"
        rec2 = _create_doc_tree(ws, "CLM-001", "bbb222")
        rec2["doc_type"] = "service_history"
        rec3 = _create_doc_tree(ws, "CLM-002", "ccc333")
        rec3["doc_type"] = "service_history"
        _write_doc_index(ws / "registry", [rec1, rec2, rec3])

        claims = discover_from_workspace(ws, doc_type_filter=["service_history"])

        # Should get 2 docs across 2 claims
        all_docs = [d for c in claims for d in c.documents]
        assert len(all_docs) == 2
        assert all(d.doc_id in ("bbb222", "ccc333") for d in all_docs)

    def test_filter_by_claim_id(self, tmp_path):
        """Only matching claim_ids returned."""
        ws = tmp_path / "workspace"
        rec1 = _create_doc_tree(ws, "CLM-001", "aaa111")
        rec2 = _create_doc_tree(ws, "CLM-002", "bbb222")
        rec3 = _create_doc_tree(ws, "CLM-003", "ccc333")
        _write_doc_index(ws / "registry", [rec1, rec2, rec3])

        claims = discover_from_workspace(ws, claim_id_filter=["CLM-001", "CLM-003"])

        assert len(claims) == 2
        ids = {c.claim_id for c in claims}
        assert ids == {"CLM-001", "CLM-003"}

    def test_combined_filters(self, tmp_path):
        """Both doc_type and claim_id filters applied together."""
        ws = tmp_path / "workspace"
        rec1 = _create_doc_tree(ws, "CLM-001", "aaa111")
        rec1["doc_type"] = "service_history"
        rec2 = _create_doc_tree(ws, "CLM-001", "bbb222")
        rec2["doc_type"] = "cost_estimate"
        rec3 = _create_doc_tree(ws, "CLM-002", "ccc333")
        rec3["doc_type"] = "service_history"
        _write_doc_index(ws / "registry", [rec1, rec2, rec3])

        claims = discover_from_workspace(
            ws,
            doc_type_filter=["service_history"],
            claim_id_filter=["CLM-001"],
        )

        assert len(claims) == 1
        assert claims[0].claim_id == "CLM-001"
        assert len(claims[0].documents) == 1
        assert claims[0].documents[0].doc_id == "aaa111"

    def test_missing_registry_raises(self, tmp_path):
        """FileNotFoundError raised when doc_index.jsonl missing."""
        ws = tmp_path / "workspace"
        ws.mkdir()

        with pytest.raises(FileNotFoundError, match="Registry index not found"):
            discover_from_workspace(ws)

    def test_empty_result_no_matches(self, tmp_path):
        """Empty list returned when filters match nothing."""
        ws = tmp_path / "workspace"
        rec = _create_doc_tree(ws, "CLM-001", "aaa111")
        rec["doc_type"] = "cost_estimate"
        _write_doc_index(ws / "registry", [rec])

        claims = discover_from_workspace(ws, doc_type_filter=["nonexistent_type"])

        assert claims == []

    def test_missing_doc_json_skips_with_warning(self, tmp_path, caplog):
        """Documents with missing doc.json are skipped with a warning."""
        ws = tmp_path / "workspace"
        # Create a valid doc
        rec1 = _create_doc_tree(ws, "CLM-001", "aaa111")
        # Create an index entry for a doc without doc.json on disk
        rec2 = {
            "doc_id": "bbb222",
            "claim_id": "CLM-001",
            "claim_folder": "CLM-001",
            "doc_type": "cost_estimate",
            "filename": "missing.pdf",
            "source_type": "pdf",
            "doc_root": "claims/CLM-001/docs/bbb222",
        }
        _write_doc_index(ws / "registry", [rec1, rec2])

        with caplog.at_level(logging.WARNING):
            claims = discover_from_workspace(ws)

        # Only the valid doc should be returned
        all_docs = [d for c in claims for d in c.documents]
        assert len(all_docs) == 1
        assert all_docs[0].doc_id == "aaa111"
        assert "Missing doc.json" in caplog.text or "skipping" in caplog.text.lower()

    def test_multiple_docs_per_claim(self, tmp_path):
        """Multiple docs in same claim grouped correctly."""
        ws = tmp_path / "workspace"
        rec1 = _create_doc_tree(ws, "CLM-001", "aaa111")
        rec1["doc_type"] = "service_history"
        rec2 = _create_doc_tree(ws, "CLM-001", "bbb222")
        rec2["doc_type"] = "cost_estimate"
        _write_doc_index(ws / "registry", [rec1, rec2])

        claims = discover_from_workspace(ws)

        assert len(claims) == 1
        assert claims[0].claim_id == "CLM-001"
        assert len(claims[0].documents) == 2
        doc_ids = {d.doc_id for d in claims[0].documents}
        assert doc_ids == {"aaa111", "bbb222"}

    def test_claims_sorted_by_id(self, tmp_path):
        """Claims are returned sorted by claim_id."""
        ws = tmp_path / "workspace"
        rec_c = _create_doc_tree(ws, "CLM-C", "ccc333")
        rec_a = _create_doc_tree(ws, "CLM-A", "aaa111")
        rec_b = _create_doc_tree(ws, "CLM-B", "bbb222")
        _write_doc_index(ws / "registry", [rec_c, rec_a, rec_b])

        claims = discover_from_workspace(ws)

        assert [c.claim_id for c in claims] == ["CLM-A", "CLM-B", "CLM-C"]

    def test_source_path_points_to_claim_folder(self, tmp_path):
        """Claim source_path points to the claim folder in workspace."""
        ws = tmp_path / "workspace"
        rec = _create_doc_tree(ws, "CLM-001", "aaa111")
        _write_doc_index(ws / "registry", [rec])

        claims = discover_from_workspace(ws)

        assert claims[0].source_path == ws / "claims" / "CLM-001"
