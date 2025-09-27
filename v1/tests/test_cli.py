"""Tests for CLI functionality."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from context_builder.cli import (
    load_config,
    validate_configuration,
    process_single_file,
    setup_logging,
    SensitiveDataFilter
)


class TestCLI:
    """Test cases for CLI functions."""

    def test_load_config_valid_json(self, tmp_path):
        """Test loading valid JSON configuration."""
        config_file = tmp_path / "config.json"
        config_data = {"processors": [{"name": "MetadataProcessor"}]}
        config_file.write_text(json.dumps(config_data))

        result = load_config(str(config_file))
        assert result == config_data

    def test_load_config_invalid_json(self, tmp_path):
        """Test loading invalid JSON raises ValueError."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{ invalid json }")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(str(config_file))

    def test_load_config_missing_file(self):
        """Test loading non-existent file raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.json")

    @patch('context_builder.cli.logging.getLogger')
    def test_validate_configuration_valid(self, mock_logger, tmp_path):
        """Test configuration validation with valid config."""
        config_file = tmp_path / "config.json"
        config_data = {
            "processors": [
                {
                    "name": "MetadataProcessor",
                    "enabled": True
                }
            ]
        }
        config_file.write_text(json.dumps(config_data))

        logger = MagicMock()
        mock_logger.return_value = logger

        result = validate_configuration(str(config_file), logger)
        assert result == 0
        logger.info.assert_any_call("[OK] Configuration file loaded successfully")

    @patch('context_builder.cli.logging.getLogger')
    @patch('os.getenv')
    def test_validate_configuration_ai_no_key(self, mock_getenv, mock_logger, tmp_path):
        """Test validation fails when AI configured but no API key."""
        mock_getenv.return_value = None

        config_file = tmp_path / "config.json"
        config_data = {
            "processors": [
                {
                    "name": "ContentProcessor",
                    "enabled": True,
                    "config": {
                        "ai": {
                            "enabled": True
                        }
                    }
                }
            ]
        }
        config_file.write_text(json.dumps(config_data))

        logger = MagicMock()
        mock_logger.return_value = logger

        result = validate_configuration(str(config_file), logger)
        assert result == 1
        logger.error.assert_any_call("[X] OPENAI_API_KEY not found in environment or config")

    @patch('context_builder.cli.logging.getLogger')
    def test_validate_configuration_missing_prompt_file(self, mock_logger, tmp_path):
        """Test validation fails when prompt file is missing."""
        config_file = tmp_path / "config.json"
        config_data = {
            "processors": [
                {
                    "name": "ContentProcessor",
                    "config": {
                        "ai": {
                            "enabled": True,
                            "api_key": "test-key",
                            "prompt_config": {
                                "prompt_file": "missing_prompt.txt"
                            }
                        }
                    }
                }
            ]
        }
        config_file.write_text(json.dumps(config_data))

        logger = MagicMock()
        mock_logger.return_value = logger

        result = validate_configuration(str(config_file), logger)
        assert result == 1

    def test_process_single_file_success(self, tmp_path):
        """Test successful single file processing."""
        # Setup
        input_file = tmp_path / "test.txt"
        input_file.write_text("test content")
        output_path = tmp_path / "output"

        # Create mock ingestor
        mock_ingestor = MagicMock()
        mock_ingestor.ingest_file.return_value = {"content": "processed"}

        logger = MagicMock()

        # Execute
        success, metadata, error = process_single_file(
            input_file, output_path, mock_ingestor, logger
        )

        # Assert
        assert success is True
        assert metadata == {"content": "processed"}
        assert error is None
        assert (output_path / "test_context.json").exists()

    def test_process_single_file_failure(self, tmp_path):
        """Test handling of file processing failure."""
        # Setup
        input_file = tmp_path / "test.txt"
        input_file.write_text("test content")
        output_path = tmp_path / "output"

        # Create mock ingestor that fails
        mock_ingestor = MagicMock()
        mock_ingestor.ingest_file.side_effect = Exception("Processing failed")

        logger = MagicMock()

        # Execute
        success, metadata, error = process_single_file(
            input_file, output_path, mock_ingestor, logger
        )

        # Assert
        assert success is False
        assert metadata is None
        assert error == "Processing failed"
        assert (output_path / "test_context.json").exists()

        # Check error file content
        with open(output_path / "test_context.json") as f:
            error_data = json.load(f)
            assert error_data["error"] is True
            assert error_data["error_message"] == "Processing failed"


class TestSensitiveDataFilter:
    """Test cases for the SensitiveDataFilter logging filter."""

    def test_filter_http_requests(self):
        """Test filtering of HTTP request logs."""
        filter = SensitiveDataFilter()

        record = MagicMock()
        record.getMessage.return_value = "HTTP/1.1 200 OK"
        record.name = "test"

        assert filter.filter(record) is False

    def test_filter_binary_data(self):
        """Test filtering of binary data logs."""
        filter = SensitiveDataFilter()

        record = MagicMock()
        record.getMessage.return_value = "Data: b'\\x00\\x01\\x02'"
        record.name = "test"

        assert filter.filter(record) is False

    def test_filter_authorization_header(self):
        """Test filtering of authorization headers."""
        filter = SensitiveDataFilter()

        record = MagicMock()
        record.getMessage.return_value = "Request with Authorization: Bearer token123"
        record.name = "test"

        assert filter.filter(record) is False

    def test_allow_normal_logs(self):
        """Test that normal logs pass through."""
        filter = SensitiveDataFilter()

        record = MagicMock()
        record.getMessage.return_value = "Processing file: test.pdf"
        record.name = "test"

        assert filter.filter(record) is True

    def test_filter_urllib3_logs(self):
        """Test filtering of urllib3 logs."""
        filter = SensitiveDataFilter()

        record = MagicMock()
        record.getMessage.return_value = "Starting new HTTPS connection"
        record.name = "urllib3.connectionpool"

        assert filter.filter(record) is False