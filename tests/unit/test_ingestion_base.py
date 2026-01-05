"""Unit tests for DataIngestion base class."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from context_builder.ingestion import (
    DataIngestion,
    IngestionError,
    FileNotSupportedError,
)


class ConcreteIngestion(DataIngestion):
    """Concrete implementation for testing."""

    def _process_implementation(self, filepath: Path):
        """Simple implementation for testing."""
        return {"test": "data"}


class TestDataIngestionValidation:
    """Test file validation functionality."""

    def test_validate_file_present(self, tmp_path):
        """Test validation with present file."""
        test_file = tmp_path / "image.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()
        ingestion.validate_file(test_file)
        # Should not raise

    def test_validate_file_missing(self, tmp_path):
        """Test validation with missing file."""
        test_file = tmp_path / "missing.jpg"

        ingestion = ConcreteIngestion()
        with pytest.raises(FileNotFoundError, match="File not found"):
            ingestion.validate_file(test_file)

    def test_validate_non_file_path(self, tmp_path):
        """Test validation with directory path."""
        ingestion = ConcreteIngestion()

        with pytest.raises(FileNotSupportedError, match="Path is not a file"):
            ingestion.validate_file(tmp_path)

    def test_validate_unsupported_suffix(self, tmp_path):
        """Test validation with unsupported file type."""
        test_file = tmp_path / "document.txt"
        test_file.touch()

        ingestion = ConcreteIngestion()
        with pytest.raises(FileNotSupportedError, match="File type '.txt' not supported"):
            ingestion.validate_file(test_file)

    def test_validate_case_insensitive_extensions(self, tmp_path):
        """Test case-insensitive extension validation."""
        test_cases = [
            "image.JPG",
            "photo.Jpeg",
            "scan.TIF",
            "document.PDF",
            "picture.PNG",
            "graphic.Gif",
            "bitmap.BMP"
        ]

        ingestion = ConcreteIngestion()

        for filename in test_cases:
            test_file = tmp_path / filename
            test_file.touch()

            # Should not raise
            ingestion.validate_file(test_file)

    def test_validate_all_supported_extensions(self, tmp_path):
        """Test all supported extensions are valid."""
        ingestion = ConcreteIngestion()

        for ext in DataIngestion.SUPPORTED_EXTENSIONS:
            test_file = tmp_path / f"test{ext}"
            test_file.touch()

            # Should not raise
            ingestion.validate_file(test_file)

    def test_validate_logs_debug_on_success(self, tmp_path, caplog):
        """Test debug logging on successful validation."""
        test_file = tmp_path / "image.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()

        with caplog.at_level(logging.DEBUG):
            ingestion.validate_file(test_file)

        assert "File validation passed" in caplog.text


class TestDataIngestionProcess:
    """Test process method functionality."""

    def test_process_string_path_conversion(self, tmp_path):
        """Test process converts string paths to Path objects."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()
        with patch.object(ingestion, '_process_implementation') as mock_impl:
            mock_impl.return_value = {"result": "data"}

            # Pass as string
            result = ingestion.process(str(test_file))

            # Should be called with Path object
            mock_impl.assert_called_once()
            call_arg = mock_impl.call_args[0][0]
            assert isinstance(call_arg, Path)
            assert str(call_arg) == str(test_file)

    def test_process_path_object(self, tmp_path):
        """Test process accepts Path objects directly."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()
        result = ingestion.process(test_file)

        assert result == {"test": "data"}

    def test_process_validates_file(self, tmp_path):
        """Test process calls validate_file."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()

        with patch.object(ingestion, 'validate_file') as mock_validate:
            ingestion.process(test_file)
            mock_validate.assert_called_once_with(test_file)

    def test_process_logs_info_messages(self, tmp_path, caplog):
        """Test process logs appropriate info messages."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()

        with caplog.at_level(logging.INFO):
            ingestion.process(test_file)

        assert f"Processing file: {test_file}" in caplog.text
        assert f"Successfully processed: {test_file}" in caplog.text

    def test_process_wraps_unknown_exceptions(self, tmp_path):
        """Test process wraps unknown exceptions into IngestionError."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()

        with patch.object(ingestion, '_process_implementation') as mock_impl:
            mock_impl.side_effect = ValueError("Something went wrong")

            with pytest.raises(IngestionError, match="Processing failed: Something went wrong"):
                ingestion.process(test_file)

    def test_process_preserves_ingestion_errors(self, tmp_path):
        """Test process doesn't wrap IngestionError subclasses."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()

        with patch.object(ingestion, '_process_implementation') as mock_impl:
            original_error = FileNotSupportedError("Special error")
            mock_impl.side_effect = original_error

            with pytest.raises(FileNotSupportedError, match="Special error") as exc_info:
                ingestion.process(test_file)

            # Should be the same instance, not wrapped
            assert exc_info.value is original_error

    def test_process_logs_exception_on_unknown_error(self, tmp_path, caplog):
        """Test process logs exception details for unknown errors."""
        test_file = tmp_path / "test.jpg"
        test_file.touch()

        ingestion = ConcreteIngestion()

        with patch.object(ingestion, '_process_implementation') as mock_impl:
            mock_impl.side_effect = RuntimeError("Unexpected")

            with caplog.at_level(logging.ERROR):
                with pytest.raises(IngestionError):
                    ingestion.process(test_file)

            assert "Unexpected error processing" in caplog.text


class TestDataIngestionInitialization:
    """Test DataIngestion initialization."""

    def test_logger_initialization(self):
        """Test logger is initialized with class name."""
        ingestion = ConcreteIngestion()
        assert ingestion.logger.name == "ConcreteIngestion"

    def test_supported_extensions_available(self):
        """Test SUPPORTED_EXTENSIONS is available."""
        ingestion = ConcreteIngestion()
        assert hasattr(ingestion, 'SUPPORTED_EXTENSIONS')
        assert '.jpg' in ingestion.SUPPORTED_EXTENSIONS
        assert '.pdf' in ingestion.SUPPORTED_EXTENSIONS
        assert '.tif' in ingestion.SUPPORTED_EXTENSIONS

    def test_abstract_method_not_implemented(self):
        """Test _process_implementation must be implemented."""
        # DataIngestion is abstract, so we can't instantiate it directly
        # We test that the abstract method exists and must be implemented
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DataIngestion()