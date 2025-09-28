"""Unit tests for hashing utilities."""

import hashlib
import logging
from pathlib import Path

import pytest

from context_builder.utils.hashing import calculate_file_md5


class TestCalculateFileMD5:
    """Test cases for calculate_file_md5 function."""

    def test_valid_file(self, tmp_path):
        """Test MD5 calculation for valid file."""
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)

        result = calculate_file_md5(test_file)

        expected = hashlib.md5(test_content).hexdigest()
        assert result == expected

    def test_large_file_chunking(self, tmp_path):
        """Test MD5 calculation for large file uses chunking."""
        test_file = tmp_path / "large.bin"
        # Create 5MB file
        test_content = b"x" * (5 * 1024 * 1024)
        test_file.write_bytes(test_content)

        result = calculate_file_md5(test_file)

        # Should calculate correctly despite size
        expected = hashlib.md5(test_content).hexdigest()
        assert result == expected

    def test_empty_file(self, tmp_path):
        """Test MD5 calculation for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        result = calculate_file_md5(test_file)

        # MD5 of empty string
        expected = hashlib.md5(b"").hexdigest()
        assert result == expected
        assert result == "d41d8cd98f00b204e9800998ecf8427e"

    def test_nonexistent_file_returns_empty_string(self, tmp_path, caplog):
        """Test MD5 calculation error handling for nonexistent file."""
        test_file = tmp_path / "nonexistent.txt"

        with caplog.at_level(logging.WARNING):
            result = calculate_file_md5(test_file)

        assert result == ""
        assert "Failed to calculate MD5" in caplog.text

    def test_binary_file(self, tmp_path):
        """Test MD5 calculation for binary file."""
        test_file = tmp_path / "binary.bin"
        # Create binary content with various byte values
        test_content = bytes(range(256))
        test_file.write_bytes(test_content)

        result = calculate_file_md5(test_file)

        expected = hashlib.md5(test_content).hexdigest()
        assert result == expected

    def test_file_with_unicode_name(self, tmp_path):
        """Test MD5 calculation for file with unicode characters in name."""
        test_file = tmp_path / "文件名.txt"
        test_content = b"Unicode filename test"
        test_file.write_bytes(test_content)

        result = calculate_file_md5(test_file)

        expected = hashlib.md5(test_content).hexdigest()
        assert result == expected