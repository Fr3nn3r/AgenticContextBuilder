#!/usr/bin/env python3
"""
Unit tests for dataset metadata extraction functionality.
Tests individual functions in isolation with mocked dependencies.
"""

import os
import sys
import tempfile
import hashlib
import stat
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import pytest

# Add the scripts directory to the path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from extract_datasets_metadata import (
    get_file_hash,
    extract_file_metadata,
    format_bytes,
    generate_extraction_id
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
        result = get_file_hash(str(test_file), 'md5')
        assert result == expected_hash

    def test_valid_file_sha1(self, tmp_path):
        """Test SHA1 hash calculation for a valid file."""
        test_file = tmp_path / "test.txt"
        test_content = b"Test content for SHA1"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha1(test_content).hexdigest()
        result = get_file_hash(str(test_file), 'sha1')
        assert result == expected_hash

    def test_valid_file_sha256(self, tmp_path):
        """Test SHA256 hash calculation for a valid file."""
        test_file = tmp_path / "test.txt"
        test_content = b"Test content for SHA256"
        test_file.write_bytes(test_content)

        expected_hash = hashlib.sha256(test_content).hexdigest()
        result = get_file_hash(str(test_file), 'sha256')
        assert result == expected_hash

    def test_nonexistent_file(self):
        """Test hash calculation for non-existent file returns None."""
        result = get_file_hash("/nonexistent/file.txt", 'md5')
        assert result is None

    def test_empty_file(self, tmp_path):
        """Test hash calculation for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        # Empty file should have predictable hashes
        expected_md5 = hashlib.md5(b"").hexdigest()
        result = get_file_hash(str(test_file), 'md5')
        assert result == expected_md5

    def test_large_file(self, tmp_path):
        """Test hash calculation for large file (chunk reading)."""
        test_file = tmp_path / "large.txt"
        # Create a file larger than the chunk size (4096 bytes)
        large_content = b"A" * 10000
        test_file.write_bytes(large_content)

        expected_hash = hashlib.sha256(large_content).hexdigest()
        result = get_file_hash(str(test_file), 'sha256')
        assert result == expected_hash

    def test_binary_file(self, tmp_path):
        """Test hash calculation for binary file."""
        test_file = tmp_path / "binary.bin"
        # Create binary content with various byte values
        binary_content = bytes(range(256))
        test_file.write_bytes(binary_content)

        expected_hash = hashlib.sha256(binary_content).hexdigest()
        result = get_file_hash(str(test_file), 'sha256')
        assert result == expected_hash

    @patch('builtins.open', side_effect=OSError("Permission denied"))
    def test_permission_denied(self, mock_open):
        """Test hash calculation when file permission is denied."""
        result = get_file_hash("/some/file.txt", 'md5')
        assert result is None

    @patch('builtins.open', side_effect=IOError("I/O error"))
    def test_io_error(self, mock_open):
        """Test hash calculation when I/O error occurs."""
        result = get_file_hash("/some/file.txt", 'sha1')
        assert result is None


class TestExtractFileMetadata:
    """Test suite for the extract_file_metadata function."""

    def test_basic_file_attributes(self, tmp_path):
        """Test extraction of basic file attributes."""
        test_file = tmp_path / "test_file.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)

        metadata = extract_file_metadata(str(test_file))

        # Check basic attributes
        assert metadata['file_name'] == "test_file.txt"
        assert metadata['file_path'] == str(test_file.absolute())
        assert metadata['file_extension'] == ".txt"
        assert metadata['file_size_bytes'] == len(test_content.encode())
        assert 'file_size_human' in metadata

    def test_timestamps(self, tmp_path):
        """Test extraction of file timestamps."""
        test_file = tmp_path / "timestamp_test.txt"
        test_file.write_text("test")

        metadata = extract_file_metadata(str(test_file))

        # Check that timestamps are present and in ISO format
        assert 'created_time' in metadata
        assert 'modified_time' in metadata
        assert 'accessed_time' in metadata

        # Verify ISO format (will raise exception if invalid)
        datetime.fromisoformat(metadata['created_time'])
        datetime.fromisoformat(metadata['modified_time'])
        datetime.fromisoformat(metadata['accessed_time'])

    def test_permissions(self, tmp_path):
        """Test extraction of file permissions."""
        test_file = tmp_path / "permissions_test.txt"
        test_file.write_text("test")

        metadata = extract_file_metadata(str(test_file))

        # Check permissions structure
        assert 'permissions' in metadata
        perms = metadata['permissions']
        assert 'octal' in perms
        assert 'readable' in perms
        assert 'writable' in perms
        assert 'executable' in perms

        # Check types
        assert isinstance(perms['readable'], bool)
        assert isinstance(perms['writable'], bool)
        assert isinstance(perms['executable'], bool)
        assert perms['octal'].startswith('0o')  # Octal format

    def test_file_type_detection(self, tmp_path):
        """Test file type detection (file vs directory vs symlink)."""
        # Test regular file
        test_file = tmp_path / "regular_file.txt"
        test_file.write_text("test")

        metadata = extract_file_metadata(str(test_file))
        assert metadata['is_file'] is True
        assert metadata['is_directory'] is False
        assert metadata['is_symlink'] is False

        # Test directory
        test_dir = tmp_path / "test_directory"
        test_dir.mkdir()

        metadata = extract_file_metadata(str(test_dir))
        assert metadata['is_file'] is False
        assert metadata['is_directory'] is True
        assert metadata['is_symlink'] is False

    def test_mime_type_detection(self, tmp_path):
        """Test MIME type detection for various file extensions."""
        test_cases = [
            ("test.txt", "text/plain"),
            ("test.pdf", "application/pdf"),
            ("test.jpg", "image/jpeg"),
            ("test.png", "image/png"),
            ("test.html", "text/html"),
            ("test.json", "application/json"),
        ]

        for filename, expected_mime in test_cases:
            test_file = tmp_path / filename
            test_file.write_text("test content")

            metadata = extract_file_metadata(str(test_file))
            assert metadata['mime_type'] == expected_mime

    def test_hash_generation_for_files(self, tmp_path):
        """Test hash generation for regular files."""
        test_file = tmp_path / "hash_test.txt"
        test_content = "Content for hashing"
        test_file.write_text(test_content)

        metadata = extract_file_metadata(str(test_file))

        # Check that hashes are present for files
        assert 'hashes' in metadata
        hashes = metadata['hashes']
        assert 'md5' in hashes
        assert 'sha1' in hashes
        assert 'sha256' in hashes

        # Verify hash values are not None
        assert hashes['md5'] is not None
        assert hashes['sha1'] is not None
        assert hashes['sha256'] is not None

        # Verify hash lengths
        assert len(hashes['md5']) == 32  # MD5 hex length
        assert len(hashes['sha1']) == 40  # SHA1 hex length
        assert len(hashes['sha256']) == 64  # SHA256 hex length

    def test_no_hash_for_directories(self, tmp_path):
        """Test that hashes are not generated for directories."""
        test_dir = tmp_path / "test_directory"
        test_dir.mkdir()

        metadata = extract_file_metadata(str(test_dir))

        # Directories should not have hashes
        assert 'hashes' not in metadata

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-specific test")
    def test_windows_attributes(self, tmp_path):
        """Test Windows-specific file attributes."""
        test_file = tmp_path / "windows_test.txt"
        test_file.write_text("test")

        metadata = extract_file_metadata(str(test_file))

        # Check Windows attributes are present on Windows
        assert 'windows_attributes' in metadata
        attrs = metadata['windows_attributes']
        assert 'hidden' in attrs
        assert 'system' in attrs
        assert 'archive' in attrs

    @pytest.mark.skipif(os.name == 'nt', reason="Non-Windows test")
    def test_no_windows_attributes_non_windows(self, tmp_path):
        """Test that Windows attributes are not present on non-Windows systems."""
        test_file = tmp_path / "non_windows_test.txt"
        test_file.write_text("test")

        metadata = extract_file_metadata(str(test_file))

        # Windows attributes should not be present on non-Windows
        assert 'windows_attributes' not in metadata

    def test_error_handling_nonexistent_file(self):
        """Test error handling for non-existent files."""
        metadata = extract_file_metadata("/nonexistent/file.txt")

        # Should return error metadata
        assert 'error' in metadata
        assert 'metadata_extraction_failed' in metadata
        assert metadata['metadata_extraction_failed'] is True
        assert metadata['file_name'] == "file.txt"
        assert 'file_path' in metadata

    @patch('os.stat', side_effect=OSError("Permission denied"))
    def test_error_handling_permission_denied(self, mock_stat):
        """Test error handling when permission is denied."""
        metadata = extract_file_metadata("/some/file.txt")

        assert 'error' in metadata
        assert 'metadata_extraction_failed' in metadata
        assert metadata['metadata_extraction_failed'] is True


class TestFormatBytes:
    """Test suite for the format_bytes function."""

    def test_bytes_conversion_accuracy(self):
        """Test byte conversion accuracy for various units."""
        test_cases = [
            (0, "0.00 B"),
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
        assert result == "0.00 B"


class TestGenerateExtractionId:
    """Test suite for the generate_extraction_id function."""

    def test_date_format_consistency(self):
        """Test that extraction ID contains correct date format."""
        with patch('extract_datasets_metadata.datetime') as mock_datetime:
            # Mock current date
            mock_now = MagicMock()
            mock_now.strftime.return_value = "2025-09-19"
            mock_datetime.now.return_value = mock_now

            extraction_id = generate_extraction_id("/some/test_folder")

            # Should start with "ingest-2025-09-19-"
            assert extraction_id.startswith("ingest-2025-09-19-")

    def test_random_suffix_uniqueness(self):
        """Test that random suffix makes IDs unique."""
        extraction_ids = set()

        # Generate multiple IDs for the same folder
        for _ in range(100):
            extraction_id = generate_extraction_id("/same/folder")
            extraction_ids.add(extraction_id)

        # Should have 100 unique IDs (or very close due to randomness)
        assert len(extraction_ids) >= 95  # Allow for small chance of collision

    def test_input_folder_name_handling(self):
        """Test input folder name handling in extraction ID."""
        test_cases = [
            "/path/to/test_folder",
            "/path/to/folder-with-dashes",
            "/path/to/folder_with_underscores",
            "relative/folder",
            "simple_folder",
        ]

        for folder_path in test_cases:
            extraction_id = generate_extraction_id(folder_path)
            folder_name = Path(folder_path).name

            # Should end with the folder name
            assert extraction_id.endswith(f"-{folder_name}")

    def test_special_characters_in_folder_names(self):
        """Test handling of special characters in folder names."""
        test_cases = [
            "/path/to/folder with spaces",
            "/path/to/folder!@#$%",
            "/path/to/folder(with)parentheses",
            "/path/to/folder[with]brackets",
        ]

        for folder_path in test_cases:
            # Should not raise exception
            extraction_id = generate_extraction_id(folder_path)

            # Should contain the folder name (possibly modified)
            folder_name = Path(folder_path).name
            assert folder_name in extraction_id

    def test_id_structure(self):
        """Test the overall structure of extraction ID."""
        extraction_id = generate_extraction_id("/test/my_dataset")

        # Should have format: ingest-YYYY-MM-DD-XXXXXXXXXX-folder_name
        parts = extraction_id.split('-')

        assert parts[0] == "ingest"
        assert len(parts[1]) == 4  # Year
        assert len(parts[2]) == 2  # Month
        assert len(parts[3]) == 2  # Day
        assert len(parts[4]) == 10  # Random suffix
        assert parts[5] == "my_dataset"  # Folder name

    def test_random_suffix_format(self):
        """Test that random suffix is 10 digits."""
        extraction_id = generate_extraction_id("/test/folder")

        # Extract the random part (4th part when split by '-')
        parts = extraction_id.split('-')
        random_part = parts[4]

        assert len(random_part) == 10
        assert random_part.isdigit()  # Should be all digits


if __name__ == '__main__':
    pytest.main([__file__, '-v'])