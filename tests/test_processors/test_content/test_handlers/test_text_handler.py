"""Tests for text content handler."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from intake.processors.content_support.handlers import TextContentHandler
from intake.processors.content_support.models import FileContentOutput, ContentProcessorError


class TestTextContentHandler:
    """Test suite for TextContentHandler."""

    @pytest.fixture
    def text_handler(self, ai_service, prompt_manager, response_parser):
        """Create text handler with mocked dependencies."""
        config = {
            'text_truncation_chars': 1000
        }

        return TextContentHandler(
            ai_service=ai_service,
            prompt_manager=prompt_manager,
            response_parser=response_parser,
            config=config
        )

    def test_initialization(self, text_handler):
        """Test text handler initialization."""
        assert text_handler is not None
        assert hasattr(text_handler, 'SUPPORTED_EXTENSIONS')

    @pytest.mark.parametrize("extension", [
        '.txt', '.json', '.md', '.xml', '.html',
        '.py', '.js', '.css', '.yaml', '.yml'
    ])
    def test_can_handle_supported_extensions(self, text_handler, tmp_path, extension):
        """Test handler recognizes supported file extensions."""
        test_file = tmp_path / f"test{extension}"
        test_file.touch()

        assert text_handler.can_handle(test_file) is True

    def test_cannot_handle_unsupported(self, text_handler, tmp_path):
        """Test handler rejects unsupported file types."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        assert text_handler.can_handle(pdf_file) is False

    def test_process_small_text_file(self, text_handler, sample_text_file):
        """Test processing a small text file."""
        result = text_handler.process(sample_text_file)

        assert isinstance(result, FileContentOutput)
        assert result.processing_info.processing_status == "success"
        assert result.processing_info.extraction_method == "Direct Text"
        assert result.content_metadata.content_type == "text"
        assert result.data_text_content is not None

    def test_process_large_file_truncation(self, text_handler, large_text_file):
        """Test that large files are processed successfully."""
        result = text_handler.process(large_text_file)

        assert isinstance(result, FileContentOutput)
        # Check that processing succeeds for large files
        assert result.processing_info.processing_status == "success"
        assert result.data_text_content is not None

    def test_process_empty_file(self, text_handler, empty_file):
        """Test processing an empty file."""
        result = text_handler.process(empty_file)

        assert isinstance(result, FileContentOutput)
        assert result.processing_info.processing_status == "success"
        assert result.data_text_content == ""

    def test_process_with_json_prompt(self, text_handler, sample_text_file):
        """Test processing with JSON-formatted prompt response."""
        # Mock JSON response
        text_handler.response_parser.parse_ai_response = Mock(return_value=(
            {"summary": "Test summary", "language": "en"},
            "Test summary"
        ))

        result = text_handler.process(sample_text_file)

        assert result.content_metadata.summary == "Test summary"
        assert result.content_metadata.detected_language == "en"
        assert result.content_data == {"summary": "Test summary", "language": "en"}

    def test_process_with_text_prompt(self, text_handler, sample_text_file):
        """Test processing with text-only prompt response."""
        # Mock text response (None for JSON, text for plain text)
        with patch.object(text_handler.response_parser, 'parse_ai_response', return_value=(None, "Plain text analysis")):
            result = text_handler.process(sample_text_file)

            # When no JSON is parsed, content_data should be None
            assert result.content_data is None
            # Summary should be based on file analysis
            assert result.content_metadata.summary is not None

    def test_read_file_encoding_error(self, text_handler, tmp_path):
        """Test handling of file encoding errors."""
        # Create file with problematic encoding
        test_file = tmp_path / "bad_encoding.txt"
        test_file.write_bytes(b'\x80\x81\x82\x83')  # Invalid UTF-8

        # Should handle gracefully with errors='ignore'
        result = text_handler.process(test_file)

        assert result.processing_info.processing_status == "success"

    def test_missing_prompt_configuration(self, text_handler, sample_text_file):
        """Test error when prompt configuration is missing."""
        # Mock missing prompt
        with patch.object(text_handler.prompt_manager, 'get_active_prompt', return_value=None):
            result = text_handler.process(sample_text_file)

            # Should return error result when prompt is missing
            assert result.processing_info.processing_status == "error"
            assert "Prompt 'text_analysis' not found" in result.processing_info.error_message

    def test_ai_analysis_failure(self, text_handler, sample_text_file):
        """Test handling of AI analysis failure."""
        # Mock AI failure
        with patch.object(text_handler.ai_service, 'analyze_content', side_effect=Exception("AI error")):
            result = text_handler.process(sample_text_file)

            assert result.processing_info.processing_status == "error"
            assert "AI error" in result.processing_info.error_message

    def test_process_json_file(self, text_handler, sample_files_path):
        """Test processing a JSON file."""
        json_file = sample_files_path / "sample.json"

        result = text_handler.process(json_file)

        assert result.processing_info.processing_status == "success"
        assert result.content_metadata.file_category == "text_document"

    def test_process_csv_as_text(self, text_handler, sample_csv_file):
        """Test that CSV files can be processed as text (not as spreadsheets)."""
        # TextHandler should not handle CSV files
        assert text_handler.can_handle(sample_csv_file) is False

    def test_truncate_content(self, text_handler):
        """Test content truncation method."""
        long_content = "x" * 2000

        truncated = text_handler._truncate_content(long_content)

        assert len(truncated) <= 1100
        assert "[... content truncated ...]" in truncated

    def test_read_nonexistent_file(self, text_handler, tmp_path):
        """Test error when reading non-existent file."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(ContentProcessorError) as exc_info:
            text_handler._read_text_file(nonexistent)

        assert exc_info.value.error_type == "file_read_error"


# TODO: Add performance tests
# - Test with files of various sizes
# - Test memory usage with large files
# - Test processing speed benchmarks