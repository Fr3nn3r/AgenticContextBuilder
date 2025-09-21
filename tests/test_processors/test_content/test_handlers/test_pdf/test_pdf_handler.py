"""Tests for PDF content handler."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from intake.processors.content_support.handlers.pdf import PDFContentHandler
from intake.processors.content_support.models import FileContentOutput, ContentProcessorError


class TestPDFContentHandler:
    """Test suite for PDFContentHandler."""

    @pytest.fixture
    def pdf_handler(self, ai_service, prompt_provider, response_parser):
        """Create PDF handler with mocked dependencies."""
        config = {
            'pdf_use_vision_default': True,
            'ocr_as_fallback': True,
            'pdf_large_file_threshold_mb': 50,
            'pdf_max_pages_vision': 20,
            'ocr_languages': ['eng', 'spa'],
            'text_truncation_chars': 1000
        }

        return PDFContentHandler(
            ai_service=ai_service,
            prompt_provider=prompt_provider,
            response_parser=response_parser,
            config=config
        )

    def test_initialization(self, pdf_handler):
        """Test PDF handler initialization."""
        assert pdf_handler is not None
        assert hasattr(pdf_handler, 'vision_strategy')
        assert hasattr(pdf_handler, 'ocr_strategy')

    def test_can_handle_pdf(self, pdf_handler, tmp_path):
        """Test that handler recognizes PDF files."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.touch()

        assert pdf_handler.can_handle(pdf_file) is True

    def test_cannot_handle_non_pdf(self, pdf_handler, tmp_path):
        """Test that handler rejects non-PDF files."""
        txt_file = tmp_path / "test.txt"
        txt_file.touch()

        assert pdf_handler.can_handle(txt_file) is False

    @patch('os.path.getsize')
    def test_process_with_vision_default(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing with Vision API as default."""
        mock_getsize.return_value = 1024 * 1024  # 1MB

        pdf_file = sample_files_path / "sample.pdf"

        # Mock vision strategy
        with patch.object(pdf_handler.vision_strategy, 'can_handle', return_value=True):
            with patch.object(pdf_handler.vision_strategy, 'extract') as mock_extract:
                mock_extract.return_value = {
                    "pages": [{"page": 1, "analysis": "Test content"}],
                    "extraction_method": "Vision API",
                    "total_pages": 1,
                    "processed_pages": 1
                }

                result = pdf_handler.process(pdf_file)

                assert isinstance(result, FileContentOutput)
                assert result.processing_info.processing_status == "success"
                assert result.processing_info.extraction_method == "Vision API"
                mock_extract.assert_called_once()

    @patch('os.path.getsize')
    def test_vision_to_ocr_fallback(self, mock_getsize, pdf_handler, sample_files_path):
        """Test fallback from Vision API to OCR."""
        mock_getsize.return_value = 1024 * 1024  # 1MB

        pdf_file = sample_files_path / "sample.pdf"

        # Vision fails, OCR succeeds
        with patch.object(pdf_handler.vision_strategy, 'can_handle', return_value=True):
            with patch.object(pdf_handler.vision_strategy, 'extract', side_effect=Exception("Vision failed")):
                with patch.object(pdf_handler.ocr_strategy, 'extract') as mock_ocr:
                    mock_ocr.return_value = {
                        "text": "OCR extracted text",
                        "extraction_method": "OCR",
                        "has_sufficient_quality": True,
                        "quality_stats": {"has_sufficient_quality": True}
                    }

                    result = pdf_handler.process(pdf_file)

                    assert result.processing_info.processing_status == "success"
                    assert "OCR (Fallback)" in result.processing_info.extraction_method
                    mock_ocr.assert_called_once()

    @patch('os.path.getsize')
    def test_ocr_first_when_configured(self, mock_getsize, pdf_handler, sample_files_path):
        """Test using OCR first when configured."""
        mock_getsize.return_value = 1024 * 1024  # 1MB
        pdf_handler.config['pdf_use_vision_default'] = False

        pdf_file = sample_files_path / "sample.pdf"

        with patch.object(pdf_handler.ocr_strategy, 'can_handle', return_value=True):
            with patch.object(pdf_handler.ocr_strategy, 'extract') as mock_ocr:
                mock_ocr.return_value = {
                    "text": "OCR text",
                    "extraction_method": "OCR",
                    "has_sufficient_quality": True,
                    "quality_stats": {"has_sufficient_quality": True}
                }

                result = pdf_handler.process(pdf_file)

                assert result.processing_info.extraction_method == "OCR"
                mock_ocr.assert_called_once()

    @patch('os.path.getsize')
    def test_ocr_insufficient_quality_fallback(self, mock_getsize, pdf_handler, sample_files_path):
        """Test fallback to Vision when OCR quality is insufficient."""
        mock_getsize.return_value = 1024 * 1024
        pdf_handler.config['pdf_use_vision_default'] = False

        pdf_file = sample_files_path / "sample.pdf"

        # OCR returns low quality, fallback to Vision
        with patch.object(pdf_handler.ocr_strategy, 'can_handle', return_value=True):
            with patch.object(pdf_handler.ocr_strategy, 'extract') as mock_ocr:
                mock_ocr.return_value = {
                    "text": "???",
                    "extraction_method": "OCR",
                    "has_sufficient_quality": False,
                    "quality_stats": {"has_sufficient_quality": False}
                }

                with patch.object(pdf_handler.vision_strategy, 'can_handle', return_value=True):
                    with patch.object(pdf_handler.vision_strategy, 'extract') as mock_vision:
                        mock_vision.return_value = {
                            "pages": [{"page": 1, "analysis": "Vision content"}],
                            "extraction_method": "Vision API"
                        }

                        result = pdf_handler.process(pdf_file)

                        assert result.processing_info.extraction_method == "Vision API"
                        mock_vision.assert_called_once()

    @patch('os.path.getsize')
    def test_both_strategies_fail(self, mock_getsize, pdf_handler, sample_files_path):
        """Test error handling when both strategies fail."""
        mock_getsize.return_value = 1024 * 1024

        pdf_file = sample_files_path / "sample.pdf"

        # Both strategies fail
        with patch.object(pdf_handler.vision_strategy, 'can_handle', return_value=True):
            with patch.object(pdf_handler.vision_strategy, 'extract', side_effect=Exception("Vision failed")):
                with patch.object(pdf_handler.ocr_strategy, 'extract', side_effect=Exception("OCR failed")):
                    result = pdf_handler.process(pdf_file)

                    assert result.processing_info.processing_status == "error"
                    assert "Both Vision API and OCR failed" in result.processing_info.error_message

    @patch('os.path.getsize')
    def test_no_fallback_when_disabled(self, mock_getsize, pdf_handler, sample_files_path):
        """Test that fallback doesn't occur when disabled."""
        mock_getsize.return_value = 1024 * 1024
        pdf_handler.config['ocr_as_fallback'] = False

        pdf_file = sample_files_path / "sample.pdf"

        # Vision fails, no OCR fallback
        with patch.object(pdf_handler.vision_strategy, 'can_handle', return_value=True):
            with patch.object(pdf_handler.vision_strategy, 'extract', side_effect=Exception("Vision failed")):
                result = pdf_handler.process(pdf_file)

                # Should return error result since fallback is disabled
                assert result.processing_info.processing_status == "error"
                assert "Vision failed" in result.processing_info.error_message

    def test_process_vision_result(self, pdf_handler):
        """Test processing of Vision API extraction results."""
        extraction_result = {
            "pages": [
                {"page": 1, "analysis": {"content": "Page 1"}},
                {"page": 2, "analysis": {"content": "Page 2"}}
            ],
            "total_pages": 2,
            "processed_pages": 2
        }

        result = pdf_handler._process_vision_result(
            Path("test.pdf"),
            extraction_result,
            "Vision API",
            Mock(duration_seconds=1.0)
        )

        assert isinstance(result, FileContentOutput)
        assert result.content_data["pages"] == extraction_result["pages"]
        assert result.content_data["_extraction_method"] == "Vision API"

    def test_process_text_result_with_ai_analysis(self, pdf_handler, ai_service, response_parser):
        """Test processing of OCR text with AI analysis."""
        text_content = "Extracted text content from OCR"

        # Mock AI analysis
        ai_service.analyze_content = Mock(return_value='{"summary": "AI summary", "language": "en"}')
        response_parser.parse_ai_response = Mock(
            return_value=({"summary": "AI summary", "language": "en"}, "AI summary")
        )

        result = pdf_handler._process_text_result(
            Path("test.pdf"),
            text_content,
            "OCR",
            Mock(duration_seconds=1.0)
        )

        assert isinstance(result, FileContentOutput)
        assert result.content_metadata.summary == "AI summary"
        assert result.content_metadata.detected_language == "en"
        assert result.content_data["_extraction_method"] == "OCR"

    def test_process_text_result_truncation(self, pdf_handler):
        """Test that long text is truncated properly."""
        long_text = "x" * 2000  # Exceed truncation limit

        result = pdf_handler._process_text_result(
            Path("test.pdf"),
            long_text,
            "OCR",
            Mock(duration_seconds=1.0)
        )

        assert "_truncated" in result.content_data
        assert result.content_data["_truncated"] is True

    @patch('os.path.getsize')
    def test_large_file_detection(self, mock_getsize, pdf_handler, sample_files_path):
        """Test that large files are handled differently."""
        # Set file size above threshold
        mock_getsize.return_value = 60 * 1024 * 1024  # 60MB

        pdf_file = sample_files_path / "sample.pdf"

        with patch.object(pdf_handler.vision_strategy, 'extract') as mock_extract:
            mock_extract.return_value = {
                "pages": [],
                "extraction_method": "Vision API (Page-by-Page)"
            }

            result = pdf_handler.process(pdf_file)

            # Check that large file processing was triggered
            mock_extract.assert_called_once()

    def test_no_strategy_available(self, pdf_handler, sample_files_path):
        """Test error when no extraction strategy is available."""
        pdf_handler.config['pdf_use_vision_default'] = False

        pdf_file = sample_files_path / "sample.pdf"

        # Neither strategy can handle
        with patch.object(pdf_handler.ocr_strategy, 'can_handle', return_value=False):
            with patch.object(pdf_handler.vision_strategy, 'can_handle', return_value=False):
                result = pdf_handler.process(pdf_file)

                assert result.processing_info.processing_status == "error"
                assert "No extraction strategy available" in result.processing_info.error_message


@pytest.mark.skipif(
    True,  # Skip by default as pypdfium2 may not be installed
    reason="pypdfium2 not installed"
)
class TestPDFHandlerIntegration:
    """Integration tests for PDF handler with real PDF processing."""

    def test_process_real_pdf(self, sample_files_path):
        """Test processing a real PDF file."""
        # This would test with actual PDF processing
        # Requires pypdfium2 and other dependencies
        pass


# TODO: Add tests for no API key scenario
# - Test behavior when AI service is not available
# - Test fallback mechanisms without AI

# TODO: Add performance tests
# - Test with large PDFs (100+ pages)
# - Test memory usage during processing
# - Test concurrent PDF processing