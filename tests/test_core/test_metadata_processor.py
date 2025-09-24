#!/usr/bin/env python3
"""
Unit tests for metadata processor functionality.
Tests the MetadataProcessor class with mocked dependencies.
"""

import os
import hashlib
import stat
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from context_builder.processors.metadata import MetadataProcessor
from context_builder.processors.base import ProcessingError
from context_builder.models import FileMetadata, MetadataProcessorConfig


class TestMetadataProcessor:
    """Test suite for the MetadataProcessor class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.processor = MetadataProcessor()

    def _get_metadata_dict(self, result):
        """Helper method to convert Pydantic model to dict if needed."""
        metadata = result['file_metadata']
        if hasattr(metadata, 'model_dump'):
            return metadata.model_dump()
        return metadata

    def test_basic_file_attributes(self, tmp_path):
        """Test extraction of basic file attributes."""
        test_file = tmp_path / "test_file.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)

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

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)

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

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)

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

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)
        assert metadata['is_file'] is True
        assert metadata['is_directory'] is False
        assert metadata['is_symlink'] is False

        # Test directory
        test_dir = tmp_path / "test_directory"
        test_dir.mkdir()

        result = self.processor.process_file(test_dir)
        metadata = self._get_metadata_dict(result)
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

            result = self.processor.process_file(test_file)
            metadata = self._get_metadata_dict(result)
            assert metadata['mime_type'] == expected_mime

    def test_hash_generation_for_files(self, tmp_path):
        """Test hash generation for regular files."""
        test_file = tmp_path / "hash_test.txt"
        test_content = "Content for hashing"
        test_file.write_text(test_content)

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)

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

        result = self.processor.process_file(test_dir)
        metadata = self._get_metadata_dict(result)

        # Directories should not have hashes
        assert 'hashes' not in metadata

    @pytest.mark.skipif(os.name != 'nt', reason="Windows-specific test")
    def test_windows_attributes(self, tmp_path):
        """Test Windows-specific file attributes."""
        test_file = tmp_path / "windows_test.txt"
        test_file.write_text("test")

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)

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

        result = self.processor.process_file(test_file)
        metadata = self._get_metadata_dict(result)

        # Windows attributes should not be present on non-Windows
        assert 'windows_attributes' not in metadata

    def test_error_handling_nonexistent_file(self):
        """Test error handling for non-existent files."""
        result = self.processor.process_file(Path("/nonexistent/file.txt"))
        metadata = self._get_metadata_dict(result)

        # Should return error metadata
        assert 'error' in metadata
        assert 'is_metadata_ingestion_failed' in metadata
        assert metadata['is_metadata_ingestion_failed'] is True
        assert metadata['file_name'] == "file.txt"
        assert 'file_path' in metadata

    @patch('os.stat', side_effect=OSError("Permission denied"))
    def test_error_handling_permission_denied(self, mock_stat):
        """Test error handling when permission is denied."""
        result = self.processor.process_file(Path("/some/file.txt"))
        metadata = self._get_metadata_dict(result)

        assert 'error' in metadata
        assert 'is_metadata_ingestion_failed' in metadata
        assert metadata['is_metadata_ingestion_failed'] is True

    def test_configuration_disable_hashes(self, tmp_path):
        """Test disabling hash calculation via configuration."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Configure processor to disable hashes
        processor = MetadataProcessor({'include_hashes': False})
        result = processor.process_file(test_file)
        metadata = result['file_metadata']
        if hasattr(metadata, 'model_dump'):
            metadata = metadata.model_dump()

        # Hashes should not be present
        assert 'hashes' not in metadata

    def test_configuration_custom_hash_algorithms(self, tmp_path):
        """Test custom hash algorithms configuration."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Configure processor to use only MD5
        processor = MetadataProcessor({'hash_algorithms': ['md5']})
        result = processor.process_file(test_file)
        metadata = result['file_metadata']
        if hasattr(metadata, 'model_dump'):
            metadata = metadata.model_dump()

        # Only MD5 should be computed (others should be None)
        assert 'hashes' in metadata
        hashes = metadata['hashes']
        assert 'md5' in hashes
        assert hashes['md5'] is not None
        assert hashes['sha1'] is None
        assert hashes['sha256'] is None

    def test_configuration_disable_permissions(self, tmp_path):
        """Test disabling permissions extraction via configuration."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # Configure processor to disable permissions
        processor = MetadataProcessor({'include_permissions': False})
        result = processor.process_file(test_file)
        metadata = result['file_metadata']
        if hasattr(metadata, 'model_dump'):
            metadata = metadata.model_dump()

        # Permissions should not be present
        assert 'permissions' not in metadata

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        processor = MetadataProcessor({
            'include_hashes': True,
            'hash_algorithms': ['md5', 'sha256'],
            'include_permissions': True
        })
        assert processor.validate_config() is True

    def test_validate_config_invalid_algorithm(self):
        """Test configuration validation with invalid hash algorithm."""
        # Should raise ValidationError during construction
        with pytest.raises(Exception):  # ValidationError from Pydantic
            MetadataProcessor({
                'hash_algorithms': ['invalid_algorithm']
            })

    def test_validate_config_invalid_type(self):
        """Test configuration validation with invalid type."""
        # Should raise ValidationError during construction
        with pytest.raises(Exception):  # ValidationError from Pydantic
            MetadataProcessor({
                'hash_algorithms': 'not_a_list'
            })

    def test_processor_info(self):
        """Test processor information retrieval."""
        info = self.processor.get_processor_info()

        assert info['name'] == 'MetadataProcessor'
        assert info['version'] == '1.0.0'
        assert 'description' in info
        assert info['supported_extensions'] == ['*']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])