"""Unit tests for AzureDocumentIntelligenceAcquisition implementation."""

import logging
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

from context_builder.acquisition import (
    ConfigurationError,
    APIError,
)

# Check if azure-ai-documentintelligence is available
try:
    import azure.ai.documentintelligence
    AZURE_DI_AVAILABLE = True
except ImportError:
    AZURE_DI_AVAILABLE = False


class TestAzureDocumentIntelligenceInit:
    """Test Azure DI initialization and setup."""

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    @patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"})
    @patch('azure.ai.documentintelligence.DocumentIntelligenceClient')
    def test_init_success(self, mock_client):
        """Test successful initialization with valid credentials."""
        from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition

        acquisition = AzureDocumentIntelligenceAcquisition()

        assert acquisition.endpoint == "https://test.cognitiveservices.azure.com/"
        assert acquisition.api_key == "test_key"
        assert acquisition.model_id == "prebuilt-layout"
        assert acquisition.timeout == 300
        assert acquisition.retries == 3
        assert "ocrHighResolution" in acquisition.features
        assert "languages" in acquisition.features
        assert "styleFont" in acquisition.features

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    @patch.dict(os.environ, {}, clear=True)
    def test_init_missing_endpoint(self):
        """Test initialization fails without endpoint."""
        with pytest.raises(ConfigurationError, match="AZURE_DI_ENDPOINT not found"):
            from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
            AzureDocumentIntelligenceAcquisition()

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    @patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/"})
    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ConfigurationError, match="AZURE_DI_API_KEY not found"):
            from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
            AzureDocumentIntelligenceAcquisition()


class TestAzureDocumentIntelligenceRetry:
    """Test retry logic for Azure DI API calls."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock Azure DI acquisition instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
                acquisition = AzureDocumentIntelligenceAcquisition()
                return acquisition

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_retry_on_rate_limit(self, mock_acquisition):
        """Test retry on rate limit error."""
        mock_poller = Mock()
        mock_poller.result.side_effect = [
            Exception("Rate limit exceeded (429)"),
            Exception("Rate limit exceeded (429)"),
            Mock(content="Test markdown")
        ]

        mock_acquisition.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch('time.sleep'):  # Don't actually sleep
            result = mock_acquisition._call_api_with_retry(b"test bytes")

        assert result.content == "Test markdown"
        assert mock_acquisition.client.begin_analyze_document.call_count == 3

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_retry_exhaustion(self, mock_acquisition):
        """Test that retries are exhausted and error is raised."""
        mock_poller = Mock()
        mock_poller.result.side_effect = Exception("Rate limit exceeded (429)")

        mock_acquisition.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch('time.sleep'):
            with pytest.raises(APIError, match="Rate limit exceeded after 3 retries"):
                mock_acquisition._call_api_with_retry(b"test bytes")

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_no_retry_on_auth_error(self, mock_acquisition):
        """Test no retry on authentication error."""
        mock_poller = Mock()
        mock_poller.result.side_effect = Exception("Unauthorized (403)")

        mock_acquisition.client.begin_analyze_document = Mock(return_value=mock_poller)

        with pytest.raises(ConfigurationError, match="Invalid API key"):
            mock_acquisition._call_api_with_retry(b"test bytes")

        # Should only be called once, no retries
        assert mock_acquisition.client.begin_analyze_document.call_count == 1

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_exponential_backoff_timing(self, mock_acquisition):
        """Test exponential backoff wait times."""
        mock_poller = Mock()
        mock_poller.result.side_effect = [
            Exception("Timeout"),
            Exception("Timeout"),
            Mock(content="Success")
        ]

        mock_acquisition.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch('time.sleep') as mock_sleep:
            mock_acquisition._call_api_with_retry(b"test bytes")

        # Should sleep for 2, then 4 seconds (exponential backoff)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)


class TestAzureDocumentIntelligenceMarkdownSaving:
    """Test markdown file saving functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock Azure DI acquisition instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
                acquisition = AzureDocumentIntelligenceAcquisition()
                return acquisition

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_save_markdown_success(self, mock_acquisition, tmp_path):
        """Test successful markdown saving."""
        source_path = Path("test_document.pdf")
        markdown_content = "# Test Document\n\nThis is test content."

        result = mock_acquisition._save_markdown(markdown_content, source_path, tmp_path)

        assert result == "test_document_extracted.md"
        saved_file = tmp_path / result
        assert saved_file.exists()
        assert saved_file.read_text(encoding="utf-8") == markdown_content

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_save_markdown_creates_directory(self, mock_acquisition, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        source_path = Path("test.pdf")
        output_dir = tmp_path / "nested" / "output"
        markdown_content = "Test content"

        result = mock_acquisition._save_markdown(markdown_content, source_path, output_dir)

        assert output_dir.exists()
        assert (output_dir / result).exists()

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_save_markdown_unicode_content(self, mock_acquisition, tmp_path):
        """Test saving markdown with unicode characters."""
        source_path = Path("test.pdf")
        markdown_content = "# Tëst Dòcümënt\n\n中文内容 • émojis 🎉"

        result = mock_acquisition._save_markdown(markdown_content, source_path, tmp_path)

        saved_content = (tmp_path / result).read_text(encoding="utf-8")
        assert saved_content == markdown_content


class TestAzureDocumentIntelligenceMetadataExtraction:
    """Test metadata extraction from Azure DI results."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock Azure DI acquisition instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
                acquisition = AzureDocumentIntelligenceAcquisition()
                return acquisition

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_extract_metadata_complete(self, mock_acquisition):
        """Test metadata extraction with all fields present."""
        mock_result = Mock()
        mock_result.pages = [Mock(), Mock(), Mock()]  # 3 pages

        mock_lang = Mock()
        mock_lang.locale = "en-US"
        mock_lang.confidence = 0.95
        mock_result.languages = [mock_lang]

        mock_result.paragraphs = [Mock() for _ in range(10)]  # 10 paragraphs

        mock_table1 = Mock()
        mock_table1.row_count = 5
        mock_table1.column_count = 3
        mock_table2 = Mock()
        mock_table2.row_count = 8
        mock_table2.column_count = 4
        mock_result.tables = [mock_table1, mock_table2]

        metadata = mock_acquisition._extract_metadata(mock_result, "test.md", 1234)

        assert metadata["markdown_file"] == "test.md"
        assert metadata["model_id"] == "prebuilt-layout"
        assert metadata["processing_time_ms"] == 1234
        assert metadata["total_pages"] == 3
        assert metadata["language"] == "en-US"
        assert metadata["paragraph_count"] == 10
        assert metadata["table_count"] == 2
        assert len(metadata["tables"]) == 2
        assert metadata["tables"][0]["row_count"] == 5
        assert metadata["tables"][0]["column_count"] == 3

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_extract_metadata_minimal(self, mock_acquisition):
        """Test metadata extraction with minimal fields."""
        mock_result = Mock()
        mock_result.pages = None
        mock_result.languages = None
        mock_result.paragraphs = None
        mock_result.tables = None

        metadata = mock_acquisition._extract_metadata(mock_result, "test.md", 500)

        assert metadata["markdown_file"] == "test.md"
        assert metadata["model_id"] == "prebuilt-layout"
        assert metadata["processing_time_ms"] == 500
        assert "total_pages" not in metadata
        assert "language" not in metadata
        assert "paragraph_count" not in metadata
        assert "table_count" not in metadata


class TestAzureDocumentIntelligenceProcessing:
    """Test end-to-end document processing."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock Azure DI acquisition instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition
                acquisition = AzureDocumentIntelligenceAcquisition()
                return acquisition

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_process_implementation_success(self, mock_acquisition, tmp_path):
        """Test successful document processing."""
        # Create test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock Azure DI result
        mock_result = Mock()
        mock_result.content = "# Test Document\n\nExtracted content"
        mock_result.pages = [Mock(), Mock()]
        mock_lang = Mock()
        mock_lang.locale = "en"
        mock_lang.confidence = 0.9
        mock_result.languages = [mock_lang]
        mock_result.paragraphs = [Mock() for _ in range(5)]
        mock_result.tables = []

        # Mock API call
        mock_acquisition._call_api_with_retry = Mock(return_value=mock_result)

        result = mock_acquisition._process_implementation(test_file)

        # Check result structure
        assert "file_path" in result
        assert "md5" in result
        assert "markdown_file" in result
        assert result["markdown_file"] == "test_extracted.md"
        assert result["total_pages"] == 2
        assert result["language"] == "en"
        assert result["paragraph_count"] == 5
        assert "processing_time_ms" in result

        # Check markdown file was created
        md_file = tmp_path / "test_extracted.md"
        assert md_file.exists()
        assert md_file.read_text(encoding="utf-8") == "# Test Document\n\nExtracted content"

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_process_implementation_empty_content(self, mock_acquisition, tmp_path):
        """Test processing with empty content."""
        test_file = tmp_path / "empty.pdf"
        test_file.write_bytes(b"content")

        mock_result = Mock()
        mock_result.content = ""  # Empty content
        mock_result.pages = [Mock()]
        mock_result.languages = None
        mock_result.paragraphs = None
        mock_result.tables = None

        mock_acquisition._call_api_with_retry = Mock(return_value=mock_result)

        result = mock_acquisition._process_implementation(test_file)

        # Should create markdown with fallback message
        md_file = tmp_path / "empty_extracted.md"
        assert md_file.exists()
        content = md_file.read_text(encoding="utf-8")
        assert "No content extracted" in content

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_process_implementation_api_error(self, mock_acquisition, tmp_path):
        """Test processing with API error."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        mock_acquisition._call_api_with_retry = Mock(side_effect=APIError("API failed"))

        with pytest.raises(APIError, match="API failed"):
            mock_acquisition._process_implementation(test_file)


class TestAzureDocumentIntelligenceFactory:
    """Test factory registration."""

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_factory_registration(self):
        """Test Azure DI is registered with factory."""
        from context_builder.acquisition import AcquisitionFactory

        # Check that azure-di is in the registry
        assert 'azure-di' in AcquisitionFactory._registry

        # Should be able to create azure-di instance
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.com/", "AZURE_DI_API_KEY": "key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                instance = AcquisitionFactory.create('azure-di')
                assert instance is not None
