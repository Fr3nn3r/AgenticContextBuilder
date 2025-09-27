"""Unit tests for OpenAIVisionAcquisition PDF processing."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from context_builder.acquisition import ConfigurationError


class TestOpenAIVisionAcquisitionPDFProcessing:
    """Test PDF processing functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock OpenAIVisionAcquisition instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition
                acquisition = OpenAIVisionAcquisition()
                # Mock the API call method
                acquisition._call_api_with_retry = Mock()
                return acquisition

    @pytest.fixture
    def mock_pdfium(self):
        """Mock pypdfium2 module."""
        import sys
        # Mock the module import
        mock_pdfium = MagicMock()
        with patch.dict('sys.modules', {'pypdfium2': mock_pdfium}):
            yield mock_pdfium

    def test_process_pdf_pages_success(self, mock_acquisition, mock_pdfium):
        """Test successful PDF page processing."""
        # Mock PDF document with 3 pages
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=3)

        # Mock pages and rendering
        mock_pages = []
        for i in range(3):
            mock_page = Mock()
            mock_mat = Mock()
            mock_pil = Mock()
            mock_mat.to_pil = Mock(return_value=mock_pil)
            mock_page.render = Mock(return_value=mock_mat)
            mock_pages.append(mock_page)

        mock_doc.__getitem__ = lambda _, idx: mock_pages[idx]
        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)

        # Mock _encode_image_from_pil
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64data")

        # Mock API responses
        mock_responses = []
        for i in range(3):
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content=f'{{"text": "page {i+1}"}}'))]
            mock_response.usage = Mock(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150
            )
            mock_responses.append(mock_response)

        mock_acquisition._call_api_with_retry.side_effect = mock_responses

        # Process PDF
        pages, usage = mock_acquisition._process_pdf_pages(Path("test.pdf"))

        # Verify results
        assert len(pages) == 3
        assert pages[0]["text"] == "page 1"
        assert pages[0]["page_number"] == 1
        assert pages[1]["text"] == "page 2"
        assert pages[1]["page_number"] == 2
        assert pages[2]["text"] == "page 3"
        assert pages[2]["page_number"] == 3

        # Verify usage accumulation
        assert usage["prompt_tokens"] == 300
        assert usage["completion_tokens"] == 150
        assert usage["total_tokens"] == 450

        # Verify document was closed
        mock_doc.close.assert_called_once()

    def test_process_pdf_pages_max_pages_limit(self, mock_acquisition, mock_pdfium):
        """Test PDF processing respects max_pages limit."""
        # Set max_pages to 2
        mock_acquisition.max_pages = 2

        # Mock PDF with 5 pages
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=5)

        mock_page = Mock()
        mock_mat = Mock(to_pil=Mock(return_value=Mock()))
        mock_page.render = Mock(return_value=mock_mat)
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        # Mock API response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_acquisition._call_api_with_retry.return_value = mock_response

        # Process PDF
        pages, usage = mock_acquisition._process_pdf_pages(Path("test.pdf"))

        # Should only process 2 pages
        assert len(pages) == 2
        assert mock_acquisition._call_api_with_retry.call_count == 2

    def test_process_pdf_pages_render_scale(self, mock_acquisition, mock_pdfium):
        """Test PDF rendering uses configured scale."""
        mock_acquisition.render_scale = 3.5

        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=1)

        mock_page = Mock()
        mock_mat = Mock(to_pil=Mock(return_value=Mock()))
        mock_page.render = Mock(return_value=mock_mat)
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_acquisition._call_api_with_retry.return_value = mock_response

        # Process PDF
        mock_acquisition._process_pdf_pages(Path("test.pdf"))

        # Verify render was called with correct scale
        mock_page.render.assert_called_once_with(scale=3.5)

    def test_process_pdf_pages_memory_cleanup(self, mock_acquisition, mock_pdfium):
        """Test PDF processing cleans up memory after each page."""
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=2)

        # Create pages properly
        mock_pages = []
        for i in range(2):
            mock_page = Mock()
            mock_mat = Mock()
            mock_pil = Mock()
            mock_mat.to_pil = Mock(return_value=mock_pil)
            mock_page.render = Mock(return_value=mock_mat)
            mock_pages.append(mock_page)

        mock_doc.__getitem__ = Mock(side_effect=lambda idx: mock_pages[idx])
        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_acquisition._call_api_with_retry.return_value = mock_response

        # Process PDF
        pages, usage = mock_acquisition._process_pdf_pages(Path("test.pdf"))

        # Verify processing completed successfully
        assert len(pages) == 2
        assert mock_acquisition._call_api_with_retry.call_count == 2

    def test_process_pdf_pages_no_pypdfium2(self, mock_acquisition):
        """Test PDF processing without pypdfium2 installed."""
        import sys
        # Temporarily remove pypdfium2 from sys.modules to simulate it not being installed
        pypdfium2_backup = sys.modules.get('pypdfium2')
        if 'pypdfium2' in sys.modules:
            del sys.modules['pypdfium2']

        try:
            with patch.dict('sys.modules', {'pypdfium2': None}):
                with pytest.raises(ConfigurationError, match="pypdfium2 package not installed"):
                    mock_acquisition._process_pdf_pages(Path("test.pdf"))
        finally:
            if pypdfium2_backup:
                sys.modules['pypdfium2'] = pypdfium2_backup

    def test_process_pdf_pages_pdf_open_error(self, mock_acquisition, mock_pdfium):
        """Test PDF processing with file open error."""
        mock_pdfium.PdfDocument.side_effect = Exception("Cannot open PDF")

        with pytest.raises(IOError, match="Cannot process PDF file"):
            mock_acquisition._process_pdf_pages(Path("test.pdf"))

    def test_process_pdf_pages_render_error(self, mock_acquisition, mock_pdfium):
        """Test PDF processing with render error."""
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=1)

        mock_page = Mock()
        mock_page.render.side_effect = Exception("Render failed")
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)

        with pytest.raises(IOError, match="Cannot process PDF file"):
            mock_acquisition._process_pdf_pages(Path("test.pdf"))

        # Ensure document is closed even on error
        mock_doc.close.assert_called_once()

    def test_process_pdf_pages_api_error(self, mock_acquisition, mock_pdfium):
        """Test PDF processing with API error."""
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=1)

        mock_page = Mock()
        mock_mat = Mock(to_pil=Mock(return_value=Mock()))
        mock_page.render = Mock(return_value=mock_mat)
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        # API call fails
        mock_acquisition._call_api_with_retry.side_effect = Exception("API error")

        with pytest.raises(IOError, match="Cannot process PDF file"):
            mock_acquisition._process_pdf_pages(Path("test.pdf"))

        # Document should still be closed
        mock_doc.close.assert_called_once()

    def test_process_pdf_pages_logging(self, mock_acquisition, mock_pdfium, caplog):
        """Test PDF processing logs appropriate messages."""
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=3)

        mock_page = Mock()
        mock_mat = Mock(to_pil=Mock(return_value=Mock()))
        mock_page.render = Mock(return_value=mock_mat)
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_acquisition._call_api_with_retry.return_value = mock_response

        with caplog.at_level(logging.INFO):
            mock_acquisition._process_pdf_pages(Path("test.pdf"))

        assert "Processing PDF pages with pypdfium2" in caplog.text
        assert "PDF has 3 pages" in caplog.text
        assert "Processing page 1/3" in caplog.text
        assert "Processing page 2/3" in caplog.text
        assert "Processing page 3/3" in caplog.text

    def test_process_pdf_pages_warning_when_truncated(self, mock_acquisition, mock_pdfium, caplog):
        """Test PDF processing warns when pages are truncated."""
        mock_acquisition.max_pages = 2

        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=10)

        mock_page = Mock()
        mock_mat = Mock(to_pil=Mock(return_value=Mock()))
        mock_page.render = Mock(return_value=mock_mat)
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_acquisition._call_api_with_retry.return_value = mock_response

        with caplog.at_level(logging.WARNING):
            mock_acquisition._process_pdf_pages(Path("test.pdf"))

        assert "PDF has 10 pages, processing only first 2 pages" in caplog.text

    def test_process_pdf_pages_no_usage_info(self, mock_acquisition, mock_pdfium):
        """Test PDF processing handles responses without usage info."""
        mock_doc = MagicMock()
        mock_doc.__len__ = Mock(return_value=1)

        mock_page = Mock()
        mock_mat = Mock(to_pil=Mock(return_value=Mock()))
        mock_page.render = Mock(return_value=mock_mat)
        mock_doc.__getitem__ = Mock(return_value=mock_page)

        mock_pdfium.PdfDocument = Mock(return_value=mock_doc)
        mock_acquisition._encode_image_from_pil = Mock(return_value="base64")

        # Response without usage attribute
        mock_response = Mock(spec=['choices'])
        mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
        mock_acquisition._call_api_with_retry.return_value = mock_response

        pages, usage = mock_acquisition._process_pdf_pages(Path("test.pdf"))

        assert len(pages) == 1
        assert usage["total_tokens"] == 0