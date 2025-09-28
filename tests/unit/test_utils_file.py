"""Unit tests for file utilities."""

import hashlib
from pathlib import Path

import pytest

from context_builder.utils.file_utils import get_file_metadata


class TestGetFileMetadata:
    """Test cases for get_file_metadata function."""

    def test_basic_file_metadata(self, tmp_path):
        """Test metadata extraction for basic file."""
        test_file = tmp_path / "test.txt"
        test_content = b"Test content"
        test_file.write_bytes(test_content)

        metadata = get_file_metadata(test_file)

        assert metadata["file_name"] == "test.txt"
        assert metadata["file_path"] == str(test_file.resolve())
        assert metadata["file_extension"] == ".txt"
        assert metadata["file_size_bytes"] == len(test_content)
        assert metadata["mime_type"] == "text/plain"
        assert metadata["md5"] == hashlib.md5(test_content).hexdigest()

    def test_image_file_metadata(self, tmp_path):
        """Test metadata extraction for image file."""
        test_file = tmp_path / "image.jpg"
        test_content = b"\xFF\xD8\xFF\xE0"  # JPEG header
        test_file.write_bytes(test_content)

        metadata = get_file_metadata(test_file)

        assert metadata["file_name"] == "image.jpg"
        assert metadata["file_extension"] == ".jpg"
        assert metadata["mime_type"] == "image/jpeg"
        assert metadata["file_size_bytes"] == len(test_content)

    def test_pdf_file_metadata(self, tmp_path):
        """Test metadata extraction for PDF file."""
        test_file = tmp_path / "document.pdf"
        test_content = b"%PDF-1.4"  # PDF header
        test_file.write_bytes(test_content)

        metadata = get_file_metadata(test_file)

        assert metadata["file_name"] == "document.pdf"
        assert metadata["file_extension"] == ".pdf"
        assert metadata["mime_type"] == "application/pdf"
        assert metadata["file_size_bytes"] == len(test_content)

    def test_unknown_mime_type(self, tmp_path):
        """Test metadata extraction for file with unknown extension."""
        test_file = tmp_path / "unknown.xyz"
        test_content = b"Unknown content"
        test_file.write_bytes(test_content)

        metadata = get_file_metadata(test_file)

        assert metadata["file_name"] == "unknown.xyz"
        assert metadata["file_extension"] == ".xyz"
        assert metadata["mime_type"] == "application/octet-stream"  # Default for unknown
        assert metadata["file_size_bytes"] == len(test_content)

    def test_empty_file_metadata(self, tmp_path):
        """Test metadata extraction for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        metadata = get_file_metadata(test_file)

        assert metadata["file_name"] == "empty.txt"
        assert metadata["file_size_bytes"] == 0
        assert metadata["md5"] == "d41d8cd98f00b204e9800998ecf8427e"  # MD5 of empty

    def test_uppercase_extension(self, tmp_path):
        """Test that file extension is normalized to lowercase."""
        test_file = tmp_path / "IMAGE.JPG"
        test_file.write_bytes(b"content")

        metadata = get_file_metadata(test_file)

        assert metadata["file_extension"] == ".jpg"  # Should be lowercase

    def test_absolute_path_resolution(self, tmp_path):
        """Test that relative paths are resolved to absolute."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"content")

        # Change to tmp_path directory to test relative path
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            relative_path = Path("test.txt")

            metadata = get_file_metadata(relative_path)

            assert metadata["file_path"] == str(test_file.resolve())
            assert Path(metadata["file_path"]).is_absolute()
        finally:
            os.chdir(original_cwd)