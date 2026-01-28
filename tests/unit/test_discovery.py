"""Unit tests for pipeline discovery functions (discover_files, discover_claim_folders)."""

import logging
from pathlib import Path

import pytest

from context_builder.pipeline.discovery import (
    discover_files,
    discover_claim_folders,
)


def _create_pdf(path: Path) -> None:
    """Create a minimal file with .pdf extension and non-empty content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4 fake content")


# ── discover_files ──────────────────────────────────────────────


class TestDiscoverFiles:
    def test_groups_by_parent(self, tmp_path):
        """Files from the same folder become one claim."""
        folder = tmp_path / "CLM-001"
        folder.mkdir()
        _create_pdf(folder / "doc1.pdf")
        _create_pdf(folder / "doc2.pdf")

        claims = discover_files([folder / "doc1.pdf", folder / "doc2.pdf"])
        assert len(claims) == 1
        assert claims[0].claim_id == "CLM-001"
        assert len(claims[0].documents) == 2

    def test_multiple_parents(self, tmp_path):
        """Files from different folders become separate claims."""
        a = tmp_path / "CLM-A"
        b = tmp_path / "CLM-B"
        _create_pdf(a / "a.pdf")
        _create_pdf(b / "b.pdf")

        claims = discover_files([a / "a.pdf", b / "b.pdf"])
        assert len(claims) == 2
        ids = {c.claim_id for c in claims}
        assert ids == {"CLM-A", "CLM-B"}

    def test_with_claim_id_override(self, tmp_path):
        """All files forced into one claim when claim_id is provided."""
        a = tmp_path / "CLM-A"
        b = tmp_path / "CLM-B"
        _create_pdf(a / "a.pdf")
        _create_pdf(b / "b.pdf")

        claims = discover_files(
            [a / "a.pdf", b / "b.pdf"],
            claim_id="FORCED-ID",
        )
        assert len(claims) == 1
        assert claims[0].claim_id == "FORCED-ID"
        assert len(claims[0].documents) == 2

    def test_duplicate_path_dedup(self, tmp_path, caplog):
        """Same file listed twice is deduplicated with a warning."""
        folder = tmp_path / "CLM-001"
        _create_pdf(folder / "doc.pdf")
        path = folder / "doc.pdf"

        with caplog.at_level(logging.WARNING):
            claims = discover_files([path, path])

        assert len(claims) == 1
        assert len(claims[0].documents) == 1
        assert "Duplicate path skipped" in caplog.text

    def test_missing_file_raises(self, tmp_path):
        """Nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            discover_files([tmp_path / "nonexistent.pdf"])

    def test_unsupported_type_raises(self, tmp_path):
        """Unsupported file extension raises ValueError."""
        bad_file = tmp_path / "doc.docx"
        bad_file.write_bytes(b"fake content")

        with pytest.raises(ValueError, match="Unsupported file type"):
            discover_files([bad_file])

    def test_empty_list_raises(self):
        """Empty file list raises ValueError."""
        with pytest.raises(ValueError, match="No file paths provided"):
            discover_files([])

    def test_image_file_supported(self, tmp_path):
        """Image files (.jpg, .png) are supported."""
        folder = tmp_path / "CLM-IMG"
        folder.mkdir()
        img = folder / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff fake jpeg")

        claims = discover_files([img])
        assert len(claims) == 1
        assert claims[0].documents[0].source_type == "image"

    def test_text_file_supported(self, tmp_path):
        """Text files (.txt) are supported."""
        folder = tmp_path / "CLM-TXT"
        folder.mkdir()
        txt = folder / "doc.txt"
        txt.write_text("Some extracted text", encoding="utf-8")

        claims = discover_files([txt])
        assert len(claims) == 1
        assert claims[0].documents[0].source_type == "text"
        assert claims[0].documents[0].content == "Some extracted text"


# ── discover_claim_folders ──────────────────────────────────────


class TestDiscoverClaimFolders:
    def test_basic(self, tmp_path):
        """Multiple folders each become a claim."""
        a = tmp_path / "CLM-001"
        b = tmp_path / "CLM-002"
        _create_pdf(a / "doc.pdf")
        _create_pdf(b / "doc.pdf")

        claims = discover_claim_folders([a, b])
        assert len(claims) == 2
        ids = {c.claim_id for c in claims}
        assert ids == {"CLM-001", "CLM-002"}

    def test_duplicate_id_raises(self, tmp_path):
        """Same folder name from different parent paths raises ValueError."""
        parent1 = tmp_path / "path1" / "CLM-DUP"
        parent2 = tmp_path / "path2" / "CLM-DUP"
        _create_pdf(parent1 / "doc.pdf")
        _create_pdf(parent2 / "doc.pdf")

        with pytest.raises(ValueError, match="Duplicate claim ID"):
            discover_claim_folders([parent1, parent2])

    def test_empty_folder_skipped(self, tmp_path, caplog):
        """Empty folder is skipped with warning."""
        empty = tmp_path / "EMPTY"
        empty.mkdir()
        populated = tmp_path / "CLM-OK"
        _create_pdf(populated / "doc.pdf")

        with caplog.at_level(logging.WARNING):
            claims = discover_claim_folders([empty, populated])

        assert len(claims) == 1
        assert claims[0].claim_id == "CLM-OK"
        assert "Skipping empty folder" in caplog.text

    def test_not_a_dir_raises(self, tmp_path):
        """File path (not a directory) raises NotADirectoryError."""
        file_path = tmp_path / "not_a_dir.pdf"
        file_path.write_bytes(b"%PDF-1.4 fake")

        with pytest.raises(NotADirectoryError, match="not a directory"):
            discover_claim_folders([file_path])

    def test_missing_folder_raises(self, tmp_path):
        """Nonexistent folder raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Folder not found"):
            discover_claim_folders([tmp_path / "nonexistent"])

    def test_empty_list_raises(self):
        """Empty folder list raises ValueError."""
        with pytest.raises(ValueError, match="No folder paths provided"):
            discover_claim_folders([])

    def test_single_folder(self, tmp_path):
        """Single folder works correctly."""
        folder = tmp_path / "CLM-SINGLE"
        _create_pdf(folder / "doc1.pdf")
        _create_pdf(folder / "doc2.pdf")

        claims = discover_claim_folders([folder])
        assert len(claims) == 1
        assert claims[0].claim_id == "CLM-SINGLE"
        assert len(claims[0].documents) == 2

    def test_preserves_document_details(self, tmp_path):
        """Documents have correct source_type and filenames."""
        folder = tmp_path / "CLM-DETAIL"
        _create_pdf(folder / "report.pdf")

        claims = discover_claim_folders([folder])
        doc = claims[0].documents[0]
        assert doc.original_filename == "report.pdf"
        assert doc.source_type == "pdf"
        assert doc.doc_id  # non-empty hash
