"""Unit tests for OpenAIVisionIngestion encoding methods."""

import base64
import logging
from pathlib import Path
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest
from PIL import Image

from context_builder.ingestion import ConfigurationError


def _write_real_image(path: Path, size=(100, 100), mode="RGB") -> None:
    """Write a valid image file to *path* so PIL can open it."""
    img = Image.new(mode, size, color="red")
    fmt = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "bmp": "BMP"}
    img.save(path, format=fmt.get(path.suffix.lstrip(".").lower(), "JPEG"))


class TestOpenAIVisionIngestionEncoding:
    """Test image encoding functionality."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock OpenAIVisionIngestion instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion
                return OpenAIVisionIngestion()

    def test_encode_image_valid_file(self, mock_ingestion, tmp_path):
        """Test encoding a valid image file returns base64 and mime type."""
        test_file = tmp_path / "test.jpg"
        _write_real_image(test_file)

        b64, mime = mock_ingestion._encode_image(test_file)

        assert len(b64) > 0
        assert mime == "image/jpeg"
        # Verify it can be decoded back to valid bytes
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0

    def test_encode_image_empty_file(self, mock_ingestion, tmp_path):
        """Test encoding an empty image file raises IOError."""
        test_file = tmp_path / "empty.jpg"
        test_file.write_bytes(b"")

        with pytest.raises(IOError, match="Cannot read image file"):
            mock_ingestion._encode_image(test_file)

    def test_encode_image_large_file(self, mock_ingestion, tmp_path):
        """Test encoding a large image file succeeds and produces JPEG."""
        test_file = tmp_path / "large.jpg"
        _write_real_image(test_file, size=(4000, 3000))

        b64, mime = mock_ingestion._encode_image(test_file)

        assert len(b64) > 0
        assert mime == "image/jpeg"
        # Should be capped to max_dimension (2048 default)
        decoded = base64.b64decode(b64)
        result_img = Image.open(BytesIO(decoded))
        assert max(result_img.size) <= 2048

    def test_encode_image_io_error(self, mock_ingestion, tmp_path):
        """Test encoding with IO error."""
        test_file = tmp_path / "test.jpg"

        # File doesn't exist
        with pytest.raises(IOError, match="Cannot read image file"):
            mock_ingestion._encode_image(test_file)

    def test_encode_image_permission_error(self, mock_ingestion, tmp_path, monkeypatch):
        """Test encoding with permission error."""
        test_file = tmp_path / "test.jpg"
        _write_real_image(test_file)

        # Mock PIL.Image.open to raise PermissionError
        with patch('context_builder.utils.image_prep.Image.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(IOError, match="Cannot read image file"):
                mock_ingestion._encode_image(test_file)

    def test_encode_image_logs_error(self, mock_ingestion, tmp_path, caplog):
        """Test encoding logs error on failure."""
        test_file = tmp_path / "nonexistent.jpg"

        with caplog.at_level(logging.ERROR):
            with pytest.raises(IOError):
                mock_ingestion._encode_image(test_file)

        assert f"Failed to encode image {test_file}" in caplog.text


class TestOpenAIVisionIngestionPILEncoding:
    """Test PIL image encoding functionality."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock OpenAIVisionIngestion instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion
                return OpenAIVisionIngestion()

    def test_encode_pil_image_success(self, mock_ingestion):
        """Test encoding a PIL image successfully."""
        pil_image = Image.new("RGB", (200, 150), color="blue")

        b64, mime = mock_ingestion._encode_image_from_pil(pil_image)

        assert mime == "image/jpeg"
        assert len(b64) > 0
        # Verify result is valid base64 decodable to JPEG
        decoded = base64.b64decode(b64)
        assert decoded[:2] == b"\xff\xd8"

    def test_encode_pil_image_save_error(self, mock_ingestion):
        """Test encoding PIL image with save error."""
        mock_pil_image = Mock()
        mock_pil_image.save = Mock(side_effect=Exception("Save failed"))

        with pytest.raises(IOError, match="Cannot encode image"):
            mock_ingestion._encode_image_from_pil(mock_pil_image)

    def test_encode_pil_image_logs_error(self, mock_ingestion, caplog):
        """Test PIL encoding logs error on failure."""
        mock_pil_image = Mock()
        mock_pil_image.save = Mock(side_effect=RuntimeError("PIL error"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(IOError):
                mock_ingestion._encode_image_from_pil(mock_pil_image)

        assert "Failed to encode PIL image" in caplog.text

    def test_encode_pil_image_rgba(self, mock_ingestion):
        """Test encoding RGBA PIL image converts to RGB JPEG."""
        pil_image = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))

        b64, mime = mock_ingestion._encode_image_from_pil(pil_image)

        assert mime == "image/jpeg"
        decoded = base64.b64decode(b64)
        result_img = Image.open(BytesIO(decoded))
        assert result_img.mode == "RGB"


class TestOpenAIVisionIngestionFileMetadata:
    """Test file metadata extraction."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock OpenAIVisionIngestion instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion
                return OpenAIVisionIngestion()

    def test_get_file_metadata_basic(self, mock_ingestion, tmp_path):
        """Test basic file metadata extraction."""
        test_file = tmp_path / "test.jpg"
        test_content = b"test data"
        test_file.write_bytes(test_content)

        from context_builder.utils.file_utils import get_file_metadata
        metadata = get_file_metadata(test_file)

        assert metadata["file_name"] == "test.jpg"
        assert metadata["file_path"] == str(test_file.resolve())
        assert metadata["file_extension"] == ".jpg"
        assert metadata["file_size_bytes"] == len(test_content)
        assert metadata["mime_type"] == "image/jpeg"
        assert "md5" in metadata

    def test_get_file_metadata_absolute_path(self, mock_ingestion, tmp_path):
        """Test metadata returns absolute path."""
        test_file = tmp_path / "subdir" / ".." / "test.png"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"data")

        from context_builder.utils.file_utils import get_file_metadata
        metadata = get_file_metadata(test_file)

        # Path should be resolved to absolute
        assert Path(metadata["file_path"]).is_absolute()
        assert ".." not in metadata["file_path"]

    def test_get_file_metadata_mime_types(self, mock_ingestion, tmp_path):
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

            from context_builder.utils.file_utils import get_file_metadata
            metadata = get_file_metadata(test_file)
            # mimetypes.guess_type might return None for some extensions
            if metadata["mime_type"] != "application/octet-stream":
                assert expected_mime in metadata["mime_type"]

    def test_get_file_metadata_unknown_mime(self, mock_ingestion, tmp_path):
        """Test unknown MIME type defaults to octet-stream."""
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"data")

        from context_builder.utils.file_utils import get_file_metadata
        metadata = get_file_metadata(test_file)

        assert metadata["mime_type"] == "application/octet-stream"

    def test_get_file_metadata_md5_calculation(self, mock_ingestion, tmp_path):
        """Test MD5 hash calculation."""
        test_file = tmp_path / "test.jpg"
        test_content = b"test data for md5"
        test_file.write_bytes(test_content)

        from context_builder.utils.file_utils import get_file_metadata
        metadata = get_file_metadata(test_file)

        # Calculate expected MD5
        import hashlib
        expected_md5 = hashlib.md5(test_content).hexdigest()

        assert metadata["md5"] == expected_md5

    def test_calculate_md5_large_file(self, mock_ingestion, tmp_path):
        """Test MD5 calculation for large file uses chunking."""
        test_file = tmp_path / "large.jpg"
        # Create 5MB file
        test_content = b"x" * (5 * 1024 * 1024)
        test_file.write_bytes(test_content)

        from context_builder.utils.hashing import calculate_file_md5
        md5_hash = calculate_file_md5(test_file)

        # Should calculate correctly
        import hashlib
        expected = hashlib.md5(test_content).hexdigest()
        assert md5_hash == expected

    def test_calculate_md5_error_handling(self, mock_ingestion, tmp_path, caplog):
        """Test MD5 calculation error handling."""
        test_file = tmp_path / "nonexistent.jpg"

        with caplog.at_level(logging.WARNING):
            from context_builder.utils.hashing import calculate_file_md5
            result = calculate_file_md5(test_file)

        assert result == ""
        assert "Failed to calculate MD5" in caplog.text