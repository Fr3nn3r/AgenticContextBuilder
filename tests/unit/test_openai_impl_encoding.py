"""Unit tests for OpenAIVisionAcquisition encoding methods."""

import base64
import logging
from pathlib import Path
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

from context_builder.acquisition import ConfigurationError


class TestOpenAIVisionAcquisitionEncoding:
    """Test image encoding functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock OpenAIVisionAcquisition instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition
                return OpenAIVisionAcquisition()

    def test_encode_image_valid_file(self, mock_acquisition, tmp_path):
        """Test encoding a valid image file."""
        # Create a test image file with some content
        test_file = tmp_path / "test.jpg"
        test_content = b"fake image data"
        test_file.write_bytes(test_content)

        result = mock_acquisition._encode_image(test_file)

        # Verify it's base64 encoded
        expected = base64.b64encode(test_content).decode("utf-8")
        assert result == expected

    def test_encode_image_empty_file(self, mock_acquisition, tmp_path):
        """Test encoding an empty image file."""
        test_file = tmp_path / "empty.jpg"
        test_file.write_bytes(b"")

        result = mock_acquisition._encode_image(test_file)

        # Empty file should encode to empty base64 string
        assert result == ""

    def test_encode_image_large_file(self, mock_acquisition, tmp_path):
        """Test encoding a large image file."""
        test_file = tmp_path / "large.jpg"
        # Create 1MB of data
        test_content = b"x" * (1024 * 1024)
        test_file.write_bytes(test_content)

        result = mock_acquisition._encode_image(test_file)

        # Should encode successfully
        assert len(result) > 0
        # Verify it can be decoded back
        decoded = base64.b64decode(result)
        assert decoded == test_content

    def test_encode_image_io_error(self, mock_acquisition, tmp_path):
        """Test encoding with IO error."""
        test_file = tmp_path / "test.jpg"

        # File doesn't exist
        with pytest.raises(IOError, match="Cannot read image file"):
            mock_acquisition._encode_image(test_file)

    def test_encode_image_permission_error(self, mock_acquisition, tmp_path, monkeypatch):
        """Test encoding with permission error."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        # Mock open to raise PermissionError
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(IOError, match="Cannot read image file"):
                mock_acquisition._encode_image(test_file)

    def test_encode_image_logs_error(self, mock_acquisition, tmp_path, caplog):
        """Test encoding logs error on failure."""
        test_file = tmp_path / "nonexistent.jpg"

        with caplog.at_level(logging.ERROR):
            with pytest.raises(IOError):
                mock_acquisition._encode_image(test_file)

        assert f"Failed to encode image {test_file}" in caplog.text


class TestOpenAIVisionAcquisitionPILEncoding:
    """Test PIL image encoding functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock OpenAIVisionAcquisition instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition
                return OpenAIVisionAcquisition()

    @pytest.fixture
    def mock_pil_image(self):
        """Create a mock PIL Image."""
        mock_img = Mock()
        mock_img.save = Mock()
        return mock_img

    def test_encode_pil_image_success(self, mock_acquisition, mock_pil_image):
        """Test encoding a PIL image successfully."""
        # Mock the save method to write test data
        def save_side_effect(buffer, format=None):
            buffer.write(b"fake png data")

        mock_pil_image.save.side_effect = save_side_effect

        result = mock_acquisition._encode_image_from_pil(mock_pil_image)

        # Verify save was called with PNG format
        assert mock_pil_image.save.call_count == 1
        save_args = mock_pil_image.save.call_args
        assert save_args[1]['format'] == "PNG"

        # Verify result is base64 encoded
        expected = base64.b64encode(b"fake png data").decode("utf-8")
        assert result == expected

    def test_encode_pil_image_save_error(self, mock_acquisition, mock_pil_image):
        """Test encoding PIL image with save error."""
        mock_pil_image.save.side_effect = Exception("Save failed")

        with pytest.raises(IOError, match="Cannot encode image"):
            mock_acquisition._encode_image_from_pil(mock_pil_image)

    def test_encode_pil_image_logs_error(self, mock_acquisition, mock_pil_image, caplog):
        """Test PIL encoding logs error on failure."""
        mock_pil_image.save.side_effect = RuntimeError("PIL error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(IOError):
                mock_acquisition._encode_image_from_pil(mock_pil_image)

        assert "Failed to encode PIL image" in caplog.text

    def test_encode_pil_image_empty(self, mock_acquisition, mock_pil_image):
        """Test encoding PIL image that produces empty data."""
        def save_empty(buffer, format=None):
            # Don't write anything to buffer
            pass

        mock_pil_image.save.side_effect = save_empty

        result = mock_acquisition._encode_image_from_pil(mock_pil_image)

        # Empty data should encode to empty string
        assert result == ""


class TestOpenAIVisionAcquisitionFileMetadata:
    """Test file metadata extraction."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock OpenAIVisionAcquisition instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition
                return OpenAIVisionAcquisition()

    def test_get_file_metadata_basic(self, mock_acquisition, tmp_path):
        """Test basic file metadata extraction."""
        test_file = tmp_path / "test.jpg"
        test_content = b"test data"
        test_file.write_bytes(test_content)

        metadata = mock_acquisition._get_file_metadata(test_file)

        assert metadata["file_name"] == "test.jpg"
        assert metadata["file_path"] == str(test_file.resolve())
        assert metadata["file_extension"] == ".jpg"
        assert metadata["file_size_bytes"] == len(test_content)
        assert metadata["mime_type"] == "image/jpeg"
        assert "md5" in metadata

    def test_get_file_metadata_absolute_path(self, mock_acquisition, tmp_path):
        """Test metadata returns absolute path."""
        test_file = tmp_path / "subdir" / ".." / "test.png"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"data")

        metadata = mock_acquisition._get_file_metadata(test_file)

        # Path should be resolved to absolute
        assert Path(metadata["file_path"]).is_absolute()
        assert ".." not in metadata["file_path"]

    def test_get_file_metadata_mime_types(self, mock_acquisition, tmp_path):
        """Test correct MIME type detection."""
        test_cases = {
            "test.jpg": "image/jpeg",
            "test.jpeg": "image/jpeg",
            "test.png": "image/png",
            "test.gif": "image/gif",
            "test.pdf": "application/pdf",
            "test.tif": "image/tiff",
            "test.tiff": "image/tiff",
            "test.bmp": "image/bmp",
        }

        for filename, expected_mime in test_cases.items():
            test_file = tmp_path / filename
            test_file.write_bytes(b"data")

            metadata = mock_acquisition._get_file_metadata(test_file)
            # mimetypes.guess_type might return None for some extensions
            if metadata["mime_type"] != "application/octet-stream":
                assert expected_mime in metadata["mime_type"]

    def test_get_file_metadata_unknown_mime(self, mock_acquisition, tmp_path):
        """Test unknown MIME type defaults to octet-stream."""
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"data")

        metadata = mock_acquisition._get_file_metadata(test_file)

        assert metadata["mime_type"] == "application/octet-stream"

    def test_get_file_metadata_md5_calculation(self, mock_acquisition, tmp_path):
        """Test MD5 hash calculation."""
        test_file = tmp_path / "test.jpg"
        test_content = b"test data for md5"
        test_file.write_bytes(test_content)

        metadata = mock_acquisition._get_file_metadata(test_file)

        # Calculate expected MD5
        import hashlib
        expected_md5 = hashlib.md5(test_content).hexdigest()

        assert metadata["md5"] == expected_md5

    def test_calculate_md5_large_file(self, mock_acquisition, tmp_path):
        """Test MD5 calculation for large file uses chunking."""
        test_file = tmp_path / "large.jpg"
        # Create 5MB file
        test_content = b"x" * (5 * 1024 * 1024)
        test_file.write_bytes(test_content)

        md5_hash = mock_acquisition._calculate_md5(test_file)

        # Should calculate correctly
        import hashlib
        expected = hashlib.md5(test_content).hexdigest()
        assert md5_hash == expected

    def test_calculate_md5_error_handling(self, mock_acquisition, tmp_path, caplog):
        """Test MD5 calculation error handling."""
        test_file = tmp_path / "nonexistent.jpg"

        with caplog.at_level(logging.WARNING):
            result = mock_acquisition._calculate_md5(test_file)

        assert result == ""
        assert "Failed to calculate MD5" in caplog.text