#!/usr/bin/env python3
"""
Unit tests for file ingestion utility functions.
Tests individual utility functions in isolation with mocked dependencies.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from context_builder.utils import (
    get_file_hash,
    format_bytes,
    generate_ingestion_id,
    ensure_directory,
    get_relative_path_safe,
    validate_path_exists,
    safe_filename
)


class TestGetFileHash:
    """Test suite for the get_file_hash function."""

    def test_valid_file_md5(self, tmp_path):
        """Test MD5 hash calculation for a valid file."""
        # Create a test file with known content
        test_file = tmp_path / "test.txt"
        test_content = b"Hello, World!"
        test_file.write_bytes(test_content)

        # Calculate expected hash
        expected_hash = hashlib.md5(test_content).hexdigest()

        # Test the function
        result = get_file_hash(test_file, 'md5')
        assert result == expected_hash

    def test_valid_file_sha1(self, tmp_path):
        """Test SHA1 hash calculation for a valid file."""
        test_file = tmp_path / "test.txt"
        test_content = b"Test content for SHA1"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha1(test_content).hexdigest()
        result = get_file_hash(test_file, 'sha1')
        assert result == expected_hash

    def test_valid_file_sha256(self, tmp_path):
        """Test SHA256 hash calculation for a valid file."""
        test_file = tmp_path / "test.txt"
        test_content = b"Test content for SHA256"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        result = get_file_hash(test_file, 'sha256')
        assert result == expected_hash

    def test_nonexistent_file(self):
        """Test hash calculation for non-existent file returns None."""
        result = get_file_hash(Path("/nonexistent/file.txt"), 'md5')
        assert result is None

    def test_empty_file(self, tmp_path):
        """Test hash calculation for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        # Empty file should have predictable hashes
        expected_md5 = hashlib.md5(b"").hexdigest()
        result = get_file_hash(test_file, 'md5')
        assert result == expected_md5

    def test_large_file(self, tmp_path):
        """Test hash calculation for large file (chunk reading)."""
        test_file = tmp_path / "large.txt"
        # Create a file larger than the chunk size (4096 bytes)
        large_content = b"A" * 10000
        test_file.write_bytes(large_content)

        expected_hash = hashlib.sha256(large_content).hexdigest()
        result = get_file_hash(test_file, 'sha256')
        assert result == expected_hash

    def test_binary_file(self, tmp_path):
        """Test hash calculation for binary file."""
        test_file = tmp_path / "binary.bin"
        # Create binary content with various byte values
        binary_content = bytes(range(256))
        test_file.write_bytes(binary_content)

        expected_hash = hashlib.sha256(binary_content).hexdigest()
        result = get_file_hash(test_file, 'sha256')
        assert result == expected_hash

    def test_unsupported_algorithm(self):
        """Test hash calculation with unsupported algorithm raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            get_file_hash(Path("/some/file.txt"), 'unsupported_algo')

    def test_permission_denied(self, tmp_path):
        """Test hash calculation when file permission is denied."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with patch('builtins.open', side_effect=OSError("Permission denied")):
            result = get_file_hash(test_file, 'md5')
            assert result is None


class TestFormatBytes:
    """Test suite for the format_bytes function."""

    def test_bytes_conversion_accuracy(self):
        """Test byte conversion accuracy for various units."""
        test_cases = [
            (0, "0 B"),
            (512, "512.00 B"),
            (1024, "1.00 KB"),
            (1536, "1.50 KB"),  # 1.5 KB
            (1048576, "1.00 MB"),  # 1 MB
            (1073741824, "1.00 GB"),  # 1 GB
            (1099511627776, "1.00 TB"),  # 1 TB
            (1125899906842624, "1.00 PB"),  # 1 PB
        ]

        for bytes_value, expected in test_cases:
            result = format_bytes(bytes_value)
            assert result == expected

    def test_edge_case_exactly_1024(self):
        """Test conversion when value is exactly 1024."""
        result = format_bytes(1024)
        assert result == "1.00 KB"

    def test_very_large_numbers(self):
        """Test conversion for very large numbers."""
        # Test petabyte range
        result = format_bytes(2 * 1125899906842624)  # 2 PB
        assert result == "2.00 PB"

        # Test beyond petabyte (should still show PB)
        result = format_bytes(1024 * 1125899906842624)  # 1024 PB
        assert result == "1024.00 PB"

    def test_floating_point_precision(self):
        """Test floating point precision in conversions."""
        # Test that we get 2 decimal places
        result = format_bytes(1536)  # 1.5 KB
        assert result == "1.50 KB"

        result = format_bytes(1587)  # ~1.55 KB
        assert result == "1.55 KB"

    def test_zero_bytes(self):
        """Test formatting of zero bytes."""
        result = format_bytes(0)
        assert result == "0 B"


class TestGenerateIngestionId:
    """Test suite for the generate_ingestion_id function."""

    def test_date_format_consistency(self):
        """Test that ingestion ID contains correct date format."""
        with patch('context_builder.utils.datetime') as mock_datetime:
            # Mock current datetime with HHMM
            mock_now = MagicMock()
            mock_now.strftime.return_value = "2025-09-19-1430"
            mock_datetime.now.return_value = mock_now

            ingestion_id = generate_ingestion_id(Path("/some/test_folder"))

            # Should start with "intake-2025-09-19-1430-"
            assert ingestion_id.startswith("intake-2025-09-19-1430-")

    def test_random_suffix_uniqueness(self):
        """Test that random suffix makes IDs unique."""
        ingestion_ids = set()

        # Generate multiple IDs for the same folder
        for _ in range(100):
            ingestion_id = generate_ingestion_id(Path("/same/folder"))
            ingestion_ids.add(ingestion_id)

        # Should have 100 unique IDs (or very close due to randomness)
        assert len(ingestion_ids) >= 95  # Allow for small chance of collision

    def test_input_folder_name_handling(self):
        """Test input folder name handling in ingestion ID."""
        test_cases = [
            Path("/path/to/test_folder"),
            Path("/path/to/folder-with-dashes"),
            Path("/path/to/folder_with_underscores"),
            Path("relative/folder"),
            Path("simple_folder"),
        ]

        for folder_path in test_cases:
            ingestion_id = generate_ingestion_id(folder_path)
            folder_name = folder_path.name

            # Should end with the folder name
            assert ingestion_id.endswith(f"-{folder_name}")

    def test_id_structure(self):
        """Test the overall structure of ingestion ID."""
        ingestion_id = generate_ingestion_id(Path("/test/my_dataset"))

        # Should have format: intake-YYYY-MM-DD-HHMM-XXXXXXXXXX-folder_name
        parts = ingestion_id.split('-')

        assert parts[0] == "intake"
        assert len(parts[1]) == 4  # Year
        assert len(parts[2]) == 2  # Month
        assert len(parts[3]) == 2  # Day
        assert len(parts[4]) == 4  # HHMM
        assert len(parts[5]) == 10  # Random suffix
        assert parts[6] == "my_dataset"  # Folder name

    def test_random_suffix_format(self):
        """Test that random suffix is 10 digits."""
        ingestion_id = generate_ingestion_id(Path("/test/folder"))

        # Extract the random part (5th part when split by '-', after HH:MM)
        parts = ingestion_id.split('-')
        random_part = parts[5]

        assert len(random_part) == 10
        assert random_part.isdigit()  # Should be all digits


class TestEnsureDirectory:
    """Test suite for the ensure_directory function."""

    def test_create_new_directory(self, tmp_path):
        """Test creating a new directory."""
        new_dir = tmp_path / "new_directory"
        assert not new_dir.exists()

        ensure_directory(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()

    def test_create_nested_directories(self, tmp_path):
        """Test creating nested directories."""
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        assert not nested_dir.exists()

        ensure_directory(nested_dir)
        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_existing_directory_no_error(self, tmp_path):
        """Test that existing directory doesn't cause error."""
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        # Should not raise exception
        ensure_directory(existing_dir)
        assert existing_dir.exists()


class TestGetRelativePathSafe:
    """Test suite for the get_relative_path_safe function."""

    def test_file_under_base_path(self, tmp_path):
        """Test getting relative path when file is under base path."""
        base_path = tmp_path
        file_path = tmp_path / "subfolder" / "file.txt"

        result = get_relative_path_safe(file_path, base_path)
        assert result == Path("subfolder/file.txt")

    def test_file_not_under_base_path(self, tmp_path):
        """Test getting relative path when file is not under base path."""
        base_path = tmp_path / "base"
        file_path = tmp_path / "other" / "file.txt"

        result = get_relative_path_safe(file_path, base_path)
        assert result == Path("file.txt")  # Should return just filename

    def test_same_path(self, tmp_path):
        """Test when file path and base path are the same."""
        result = get_relative_path_safe(tmp_path, tmp_path)
        assert result == Path(".")


class TestValidatePathExists:
    """Test suite for the validate_path_exists function."""

    def test_existing_file(self, tmp_path):
        """Test validation of existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # Should not raise exception
        validate_path_exists(test_file, "test file")

    def test_existing_directory(self, tmp_path):
        """Test validation of existing directory."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Should not raise exception
        validate_path_exists(test_dir, "directory")

    def test_nonexistent_path(self):
        """Test validation of non-existent path."""
        with pytest.raises(FileNotFoundError, match="Test path does not exist"):
            validate_path_exists(Path("/nonexistent/path"), "test path")

    def test_file_instead_of_directory(self, tmp_path):
        """Test validation when expecting directory but got file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(NotADirectoryError, match="Directory is not a directory:"):
            validate_path_exists(test_file, "directory")


class TestSafeFilename:
    """Test suite for the safe_filename function."""

    def test_basic_safe_filename(self):
        """Test that safe filenames are unchanged."""
        safe_names = ["file.txt", "my_document.pdf", "image-001.jpg"]

        for filename in safe_names:
            result = safe_filename(filename)
            assert result == filename

    def test_replace_invalid_characters(self):
        """Test replacement of invalid characters."""
        test_cases = [
            ("file<>name.txt", "file__name.txt"),
            ('file"name.txt', "file_name.txt"),
            ("file|name.txt", "file_name.txt"),
            ("file?name.txt", "file_name.txt"),
            ("file*name.txt", "file_name.txt"),
            ("file\\name.txt", "file_name.txt"),
            ("file/name.txt", "file_name.txt"),
        ]

        for original, expected in test_cases:
            result = safe_filename(original)
            assert result == expected

    def test_control_characters_removed(self):
        """Test that control characters are removed."""
        filename_with_control = "file\x00\x01name.txt"
        result = safe_filename(filename_with_control)
        assert result == "filename.txt"

    def test_empty_filename_fallback(self):
        """Test fallback for empty or whitespace-only filenames."""
        test_cases = ["", "   ", "\t\n"]

        for empty_name in test_cases:
            result = safe_filename(empty_name)
            assert result == "unnamed"

    def test_long_filename_truncation(self):
        """Test truncation of very long filenames."""
        long_name = "a" * 300 + ".txt"
        result = safe_filename(long_name)

        assert len(result) <= 255
        assert result.endswith(".txt")

    def test_custom_replacement_character(self):
        """Test using custom replacement character."""
        result = safe_filename("file<>name.txt", replacement="-")
        assert result == "file--name.txt"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])