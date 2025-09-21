"""Tests for PDF content handler with new extraction architecture."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from intake.processors.content_support.handlers.pdf import PDFContentHandler
from intake.processors.content_support.models import FileContentOutput, ContentProcessorError
from intake.processors.content_support.extractors import ExtractionResult, PageExtractionResult


class TestPDFContentHandler:
    """Test suite for PDFContentHandler with new extraction architecture."""

    @pytest.fixture
    def pdf_handler(self, ai_service, prompt_provider, response_parser):
        """Create PDF handler with mocked dependencies."""
        config = {
            'text_truncation_chars': 1000,
            'extraction_methods': {
                'ocr_tesseract': {
                    'enabled': True,
                    'priority': 1,
                    'config': {'languages': ['eng']}
                },
                'vision_openai': {
                    'enabled': True,
                    'priority': 2,
                    'config': {'model': 'gpt-4o'}
                }
            }
        }

        handler = PDFContentHandler(
            ai_service=ai_service,
            prompt_provider=prompt_provider,
            response_parser=response_parser,
            config=config
        )

        return handler

    def test_initialization(self, pdf_handler):
        """Test PDF handler initialization with registry."""
        assert pdf_handler is not None
        assert hasattr(pdf_handler, 'registry')
        assert pdf_handler.registry is not None

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
    def test_process_with_multiple_methods(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing with multiple extraction methods."""
        mock_getsize.return_value = 1024 * 1024  # 1MB
        pdf_file = sample_files_path / "sample.pdf"

        # Mock registry to return multiple extraction results
        mock_results = [
            ExtractionResult(
                method="ocr_tesseract",
                status="success",
                pages=[
                    PageExtractionResult(
                        page_number=1,
                        status="success",
                        content={"text": "OCR extracted text", "confidence": 0.95},
                        quality_score=0.95
                    )
                ]
            ),
            ExtractionResult(
                method="vision_openai",
                status="success",
                pages=[
                    PageExtractionResult(
                        page_number=1,
                        status="success",
                        content={"document_type": "invoice", "text_content": "Vision extracted text"}
                    )
                ]
            )
        ]

        with patch.object(pdf_handler.registry, 'extract_from_file', return_value=mock_results):
            result = pdf_handler.process(pdf_file)

            assert isinstance(result, FileContentOutput)
            assert result.processing_info.processing_status == "success"
            assert "ocr_tesseract" in result.processing_info.extracted_by
            assert "vision_openai" in result.processing_info.extracted_by
            assert len(result.extraction_results) == 2

    @patch('os.path.getsize')
    def test_process_with_partial_success(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing when one method succeeds and another fails."""
        mock_getsize.return_value = 1024 * 1024
        pdf_file = sample_files_path / "sample.pdf"

        mock_results = [
            ExtractionResult(
                method="ocr_tesseract",
                status="error",
                pages=[],
                error="OCR failed"
            ),
            ExtractionResult(
                method="vision_openai",
                status="success",
                pages=[
                    PageExtractionResult(
                        page_number=1,
                        status="success",
                        content={"text_content": "Vision content"}
                    )
                ]
            )
        ]

        with patch.object(pdf_handler.registry, 'extract_from_file', return_value=mock_results):
            result = pdf_handler.process(pdf_file)

            assert result.processing_info.processing_status == "partial_success"
            assert "vision_openai" in result.processing_info.extracted_by
            assert "ocr_tesseract" in result.processing_info.failed_methods

    @patch('os.path.getsize')
    def test_process_with_skipped_methods(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing when some methods are skipped."""
        mock_getsize.return_value = 1024 * 1024
        pdf_file = sample_files_path / "sample.pdf"

        mock_results = [
            ExtractionResult(
                method="ocr_tesseract",
                status="skipped",
                pages=[],
                error="Tesseract not installed"
            ),
            ExtractionResult(
                method="vision_openai",
                status="success",
                pages=[
                    PageExtractionResult(
                        page_number=1,
                        status="success",
                        content={"text_content": "Vision content"}
                    )
                ]
            )
        ]

        with patch.object(pdf_handler.registry, 'extract_from_file', return_value=mock_results):
            result = pdf_handler.process(pdf_file)

            # When one method is skipped but another succeeds, status is success
            # (skipped doesn't count as failure)
            assert result.processing_info.processing_status == "success"
            assert "vision_openai" in result.processing_info.extracted_by
            assert "ocr_tesseract" in result.processing_info.skipped_methods

    @patch('os.path.getsize')
    def test_process_all_methods_fail(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing when all methods fail."""
        mock_getsize.return_value = 1024 * 1024
        pdf_file = sample_files_path / "sample.pdf"

        mock_results = [
            ExtractionResult(
                method="ocr_tesseract",
                status="error",
                pages=[],
                error="OCR failed"
            ),
            ExtractionResult(
                method="vision_openai",
                status="error",
                pages=[],
                error="Vision API failed"
            )
        ]

        with patch.object(pdf_handler.registry, 'extract_from_file', return_value=mock_results):
            result = pdf_handler.process(pdf_file)

            assert result.processing_info.processing_status == "error"
            assert len(result.processing_info.failed_methods) == 2

    @patch('os.path.getsize')
    def test_process_no_methods_available(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing when no extraction methods are available."""
        mock_getsize.return_value = 1024 * 1024
        pdf_file = sample_files_path / "sample.pdf"

        with patch.object(pdf_handler.registry, 'extract_from_file', return_value=[]):
            result = pdf_handler.process(pdf_file)

            assert result.processing_info.processing_status == "error"
            assert "No extraction methods" in result.processing_info.error_message

    @patch('os.path.getsize')
    def test_process_with_unreadable_pages(self, mock_getsize, pdf_handler, sample_files_path):
        """Test processing with pages marked as unreadable."""
        mock_getsize.return_value = 1024 * 1024
        pdf_file = sample_files_path / "sample.pdf"

        mock_results = [
            ExtractionResult(
                method="ocr_tesseract",
                status="success",
                pages=[
                    PageExtractionResult(
                        page_number=1,
                        status="success",
                        content={"text": "Page 1 text"},
                        quality_score=0.95
                    ),
                    PageExtractionResult(
                        page_number=2,
                        status="unreadable_content",
                        content=None,
                        quality_score=0,
                        error="No readable text found"
                    )
                ]
            )
        ]

        with patch.object(pdf_handler.registry, 'extract_from_file', return_value=mock_results):
            result = pdf_handler.process(pdf_file)

            assert result.processing_info.processing_status == "success"
            extraction = result.extraction_results[0]
            assert extraction["pages"][0]["status"] == "success"
            assert extraction["pages"][1]["status"] == "unreadable_content"

    def test_determine_overall_status_all_success(self, pdf_handler):
        """Test status determination when all methods succeed."""
        mock_results = [
            Mock(status="success"),
            Mock(status="success")
        ]

        status = pdf_handler._determine_overall_status(mock_results)
        assert status == "success"

    def test_determine_overall_status_partial_success(self, pdf_handler):
        """Test status determination with mixed results."""
        mock_results = [
            Mock(status="success"),
            Mock(status="error"),
            Mock(status="skipped")
        ]

        status = pdf_handler._determine_overall_status(mock_results)
        assert status == "partial_success"

    def test_determine_overall_status_all_error(self, pdf_handler):
        """Test status determination when all fail."""
        mock_results = [
            Mock(status="error"),
            Mock(status="error")
        ]

        status = pdf_handler._determine_overall_status(mock_results)
        assert status == "error"

    def test_determine_overall_status_all_skipped(self, pdf_handler):
        """Test status determination when all are skipped."""
        mock_results = [
            Mock(status="skipped"),
            Mock(status="skipped")
        ]

        status = pdf_handler._determine_overall_status(mock_results)
        assert status == "error"

    def test_format_extraction_result(self, pdf_handler):
        """Test formatting of extraction results."""
        result = ExtractionResult(
            method="test_method",
            status="success",
            pages=[
                PageExtractionResult(
                    page_number=1,
                    status="success",
                    content={"test": "data"},
                    quality_score=0.9,
                    processing_time=1.5
                )
            ],
            error=None
        )

        formatted = pdf_handler._format_extraction_result(result)

        assert formatted["method"] == "test_method"
        assert formatted["status"] == "success"
        assert len(formatted["pages"]) == 1
        assert formatted["pages"][0]["page_number"] == 1
        assert formatted["pages"][0]["quality_score"] == 0.9

    @pytest.mark.integration
    def test_process_real_pdf(self, sample_files_path):
        """Integration test with real PDF processing (requires dependencies)."""
        pytest.skip("Integration test - requires OCR/Vision dependencies")