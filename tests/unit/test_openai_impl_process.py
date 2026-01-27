"""Unit tests for OpenAIVisionIngestion _process_implementation."""

import logging
import time
from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest

from context_builder.ingestion import (
    ConfigurationError,
    APIError,
)


class TestOpenAIVisionIngestionProcess:
    """Test _process_implementation and API retry functionality."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock OpenAIVisionIngestion instance."""
        with patch('context_builder.services.openai_client.get_openai_client'):
            from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion
            return OpenAIVisionIngestion()

    def test_process_implementation_image_success(self, mock_ingestion, tmp_path):
        """Test successful image file processing."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image")

        # Mock encoding
        mock_ingestion._encode_image = Mock(return_value="base64data")

        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"document_type": "image", "text_content": "test"}'))]
        mock_response.usage = Mock(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        mock_ingestion._call_api_with_retry = Mock(return_value=mock_response)

        result = mock_ingestion._process_implementation(test_file)

        # Check metadata
        assert result["file_name"] == "test.jpg"
        assert result["file_extension"] == ".jpg"
        assert result["total_pages"] == 1

        # Check content
        assert result["pages"][0]["document_type"] == "image"
        assert result["pages"][0]["text_content"] == "test"

        # Check usage
        assert result["_usage"]["total_tokens"] == 150

    def test_process_implementation_pdf_success(self, mock_ingestion, tmp_path):
        """Test successful PDF file processing."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")

        # Mock PDF processing
        mock_pages = [
            {"document_type": "page1", "page_number": 1},
            {"document_type": "page2", "page_number": 2}
        ]
        mock_usage = {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
        mock_ingestion._process_pdf_pages = Mock(return_value=(mock_pages, mock_usage))

        result = mock_ingestion._process_implementation(test_file)

        # Check metadata
        assert result["file_name"] == "test.pdf"
        assert result["file_extension"] == ".pdf"
        assert result["total_pages"] == 2

        # Check pages
        assert len(result["pages"]) == 2
        assert result["pages"][0]["document_type"] == "page1"
        assert result["pages"][1]["document_type"] == "page2"

        # Check usage
        assert result["_usage"]["total_tokens"] == 300

    def test_process_implementation_various_image_formats(self, mock_ingestion, tmp_path):
        """Test processing various image formats."""
        formats = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif"]

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "content"}'))]
        mock_ingestion._call_api_with_retry = Mock(return_value=mock_response)

        for fmt in formats:
            test_file = tmp_path / f"test{fmt}"
            test_file.write_bytes(b"data")

            result = mock_ingestion._process_implementation(test_file)

            assert result["file_extension"] == fmt
            assert result["total_pages"] == 1

    def test_process_implementation_no_usage_info(self, mock_ingestion, tmp_path):
        """Test processing when API doesn't return usage info."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")

        # Response without usage
        mock_response = Mock(spec=['choices'])
        mock_response.choices = [Mock(message=Mock(content='{"text": "content"}'))]
        mock_ingestion._call_api_with_retry = Mock(return_value=mock_response)

        result = mock_ingestion._process_implementation(test_file)

        # Should not have _usage key
        assert "_usage" not in result

    def test_process_implementation_api_key_error(self, mock_ingestion, tmp_path):
        """Test handling of API key errors."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_ingestion._call_api_with_retry = Mock(side_effect=Exception("Invalid api_key provided"))

        with pytest.raises(ConfigurationError, match="Invalid API key"):
            mock_ingestion._process_implementation(test_file)

    def test_process_implementation_rate_limit_error(self, mock_ingestion, tmp_path):
        """Test handling of rate limit errors."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_ingestion._call_api_with_retry = Mock(side_effect=Exception("Rate limit exceeded"))

        with pytest.raises(APIError, match="Rate limit exceeded"):
            mock_ingestion._process_implementation(test_file)

    def test_process_implementation_timeout_error(self, mock_ingestion, tmp_path):
        """Test handling of timeout errors."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_ingestion._call_api_with_retry = Mock(side_effect=Exception("Request timeout"))

        with pytest.raises(APIError, match="Request timed out"):
            mock_ingestion._process_implementation(test_file)

    def test_process_implementation_generic_error(self, mock_ingestion, tmp_path):
        """Test handling of generic errors."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_ingestion._call_api_with_retry = Mock(side_effect=Exception("Unknown error"))

        with pytest.raises(APIError, match="Failed to process file"):
            mock_ingestion._process_implementation(test_file)

    def test_process_implementation_logs_info(self, mock_ingestion, tmp_path, caplog):
        """Test process logs appropriate info messages."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "content"}'))]
        mock_ingestion._call_api_with_retry = Mock(return_value=mock_response)

        with caplog.at_level(logging.INFO):
            mock_ingestion._process_implementation(test_file)

        assert "Processing with OpenAI Vision API" in caplog.text

    def test_process_implementation_logs_error(self, mock_ingestion, tmp_path, caplog):
        """Test process logs error on failure."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"data")

        mock_ingestion._encode_image = Mock(return_value="base64")
        mock_ingestion._call_api_with_retry = Mock(side_effect=Exception("Test error"))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(APIError):
                mock_ingestion._process_implementation(test_file)

        assert "Failed to process file" in caplog.text


class TestOpenAIVisionIngestionRetry:
    """Test API retry logic with exponential backoff."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock OpenAIVisionIngestion instance."""
        with patch('context_builder.services.openai_client.get_openai_client'):
            from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion
            ingestion = OpenAIVisionIngestion()
            # Reset retries to default
            ingestion.retries = 3
            ingestion.timeout = 120
            return ingestion

    def test_retry_on_rate_limit(self, mock_ingestion):
        """Test retry logic on rate limit errors."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

        # Fail twice with rate limit, then succeed
        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=[
                Exception("Rate limit exceeded (429)"),
                Exception("429 Too Many Requests"),
                mock_response
            ]
        )

        with patch('time.sleep') as mock_sleep:
            result = mock_ingestion._call_api_with_retry([])

        assert result == mock_response
        assert mock_ingestion.client.chat.completions.create.call_count == 3

        # Check exponential backoff: 2^0 * 2 = 2, 2^1 * 2 = 4
        mock_sleep.assert_has_calls([call(2), call(4)])

    def test_retry_on_timeout(self, mock_ingestion):
        """Test retry logic on timeout errors."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=[
                Exception("Request timeout"),
                mock_response
            ]
        )

        with patch('time.sleep') as mock_sleep:
            result = mock_ingestion._call_api_with_retry([])

        assert result == mock_response
        assert mock_ingestion.client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once_with(2)

    def test_retry_on_server_errors(self, mock_ingestion):
        """Test retry on 5xx server errors."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

        errors = ["500 Internal Server Error", "502 Bad Gateway", "503 Service Unavailable", "504 Gateway Timeout"]

        for error in errors:
            mock_ingestion.client.chat.completions.create = Mock(
                side_effect=[Exception(error), mock_response]
            )

            with patch('time.sleep'):
                result = mock_ingestion._call_api_with_retry([])

            assert result == mock_response

    def test_no_retry_on_auth_error(self, mock_ingestion):
        """Test no retry on authentication errors."""
        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=Exception("Invalid api_key")
        )

        with pytest.raises(ConfigurationError, match="Invalid API key"):
            mock_ingestion._call_api_with_retry([])

        # Should only try once
        assert mock_ingestion.client.chat.completions.create.call_count == 1

    def test_no_retry_on_non_retryable_error(self, mock_ingestion):
        """Test no retry on non-retryable errors."""
        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=Exception("Model not found")
        )

        with pytest.raises(APIError, match="API call failed after 3 retries"):
            mock_ingestion._call_api_with_retry([])

        # Non-retryable errors should not retry, only call once
        assert mock_ingestion.client.chat.completions.create.call_count == 1

    def test_retry_exhaustion(self, mock_ingestion):
        """Test error when all retries are exhausted."""
        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=Exception("429 Rate limit")
        )

        with patch('time.sleep'):
            with pytest.raises(APIError, match="Rate limit exceeded after 3 retries"):
                mock_ingestion._call_api_with_retry([])

        assert mock_ingestion.client.chat.completions.create.call_count == 3

    def test_exponential_backoff_timing(self, mock_ingestion):
        """Test exponential backoff increases correctly."""
        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=[
                Exception("429"),
                Exception("429"),
                Exception("429")
            ]
        )

        with patch('time.sleep') as mock_sleep:
            with pytest.raises(APIError):
                mock_ingestion._call_api_with_retry([])

        # 2^0 * 2 = 2, 2^1 * 2 = 4, no third sleep (max retries reached)
        mock_sleep.assert_has_calls([call(2), call(4)])

    def test_retry_logging(self, mock_ingestion, caplog):
        """Test retry attempts are logged."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=[
                Exception("429 Rate limit"),
                mock_response
            ]
        )

        with patch('time.sleep'):
            with caplog.at_level(logging.WARNING):
                mock_ingestion._call_api_with_retry([])

        assert "API call failed (attempt 1/3)" in caplog.text
        assert "Retrying in 2 seconds" in caplog.text

    def test_custom_retry_count(self, mock_ingestion):
        """Test custom retry count configuration."""
        mock_ingestion.retries = 5

        mock_ingestion.client.chat.completions.create = Mock(
            side_effect=Exception("429 Rate limit")
        )

        with patch('time.sleep'):
            with pytest.raises(APIError, match="Rate limit exceeded after 5 retries"):
                mock_ingestion._call_api_with_retry([])

        assert mock_ingestion.client.chat.completions.create.call_count == 5

    def test_api_call_includes_timeout(self, mock_ingestion):
        """Test API calls include timeout parameter."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]
        mock_ingestion.client.chat.completions.create = Mock(return_value=mock_response)

        messages = [{"role": "user", "content": "test"}]
        mock_ingestion._call_api_with_retry(messages)

        # Verify timeout was passed
        call_kwargs = mock_ingestion.client.chat.completions.create.call_args[1]
        assert call_kwargs["timeout"] == 120