"""Tests for utility functions."""

import pytest
from pathlib import Path
from context_builder.utils import safe_filename


class TestSafeFilename:
    """Test cases for safe_filename function."""

    def test_normal_filename(self):
        """Test that normal filenames are unchanged."""
        assert safe_filename("document.pdf") == "document.pdf"
        assert safe_filename("my-file_123.txt") == "my-file_123.txt"

    def test_invalid_characters(self):
        """Test removal of invalid characters."""
        assert safe_filename("file:name.txt") == "file_name.txt"
        assert safe_filename("folder/file.pdf") == "folder_file.pdf"
        assert safe_filename("file<>name.doc") == "file__name.doc"
        assert safe_filename('file"name".txt') == "file_name_.txt"
        assert safe_filename("file*name?.txt") == "file_name_.txt"
        assert safe_filename("file|name.txt") == "file_name.txt"

    def test_control_characters(self):
        """Test removal of control characters."""
        assert safe_filename("file\nname.txt") == "filename.txt"
        assert safe_filename("file\tname.txt") == "filename.txt"
        assert safe_filename("file\rname.txt") == "filename.txt"
        assert safe_filename("file\x00name.txt") == "filename.txt"

    def test_windows_reserved_names(self):
        """Test handling of Windows reserved names."""
        assert safe_filename("CON.txt") == "CON_.txt"
        assert safe_filename("PRN.pdf") == "PRN_.pdf"
        assert safe_filename("AUX.doc") == "AUX_.doc"
        assert safe_filename("NUL.txt") == "NUL_.txt"
        assert safe_filename("COM1.txt") == "COM1_.txt"
        assert safe_filename("LPT1.txt") == "LPT1_.txt"

    def test_case_insensitive_reserved_names(self):
        """Test that reserved names are handled case-insensitively."""
        assert safe_filename("con.txt") == "con_.txt"
        assert safe_filename("Con.txt") == "Con_.txt"
        assert safe_filename("CON.txt") == "CON_.txt"

    def test_long_filename(self):
        """Test truncation of overly long filenames."""
        long_name = "a" * 300 + ".txt"
        result = safe_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_long_filename_preserves_extension(self):
        """Test that extension is preserved when truncating."""
        long_name = "a" * 300 + ".pdf"
        result = safe_filename(long_name)
        assert result.endswith(".pdf")
        assert len(result) <= 255

    def test_empty_filename(self):
        """Test handling of empty filename."""
        assert safe_filename("") == "unnamed"

    def test_whitespace_only(self):
        """Test handling of whitespace-only filename."""
        assert safe_filename("   ") == "unnamed"
        assert safe_filename("\t\n") == "unnamed"

    def test_leading_trailing_spaces(self):
        """Test removal of leading/trailing spaces."""
        assert safe_filename("  file.txt  ") == "file.txt"
        assert safe_filename("\tfile.txt\n") == "file.txt"

    def test_dots_handling(self):
        """Test handling of dots in filenames."""
        assert safe_filename(".") == "unnamed"
        assert safe_filename("..") == "unnamed"
        assert safe_filename("...txt") == "...txt"  # This is a valid filename
        assert safe_filename(".hidden") == ".hidden"

    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        # These should generally be preserved
        assert safe_filename("café.txt") == "café.txt"
        assert safe_filename("文档.pdf") == "文档.pdf"
        assert safe_filename("файл.doc") == "файл.doc"

    def test_multiple_extensions(self):
        """Test handling of multiple extensions."""
        assert safe_filename("file.tar.gz") == "file.tar.gz"
        assert safe_filename("document.backup.pdf") == "document.backup.pdf"

    def test_no_extension(self):
        """Test handling of files without extension."""
        assert safe_filename("README") == "README"
        assert safe_filename("Makefile") == "Makefile"

    def test_mixed_invalid_characters(self):
        """Test combination of various invalid characters."""
        assert safe_filename('file<>:"/\\|?*.txt') == "file_________.txt"

    def test_filename_after_removing_invalid(self):
        """Test that result is valid after removing invalid chars."""
        # If all characters are invalid, should return unnamed
        assert safe_filename(">>>") == "___"
        assert safe_filename("///") == "___"

    def test_preserve_underscores_and_hyphens(self):
        """Test that underscores and hyphens are preserved."""
        assert safe_filename("my_file-name.txt") == "my_file-name.txt"
        assert safe_filename("__file__.py") == "__file__.py"