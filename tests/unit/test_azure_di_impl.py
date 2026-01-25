"""Unit tests for AzureDocumentIntelligenceIngestion implementation."""

import logging
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest

from context_builder.ingestion import (
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
    @patch('azure.ai.documentintelligence.DocumentIntelligenceClient')
    def test_init_success(self, mock_client):
        """Test successful initialization with valid credentials."""
        import sys
        # Remove cached module to force re-import with mocked env
        if 'context_builder.impl.azure_di_ingestion' in sys.modules:
            del sys.modules['context_builder.impl.azure_di_ingestion']

        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}, clear=True):
            with patch('dotenv.load_dotenv'):  # Prevent .env from overriding test values
                from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                ingestion = AzureDocumentIntelligenceIngestion()

        assert ingestion.endpoint == "https://test.cognitiveservices.azure.com/"
        assert ingestion.api_key == "test_key"
        assert ingestion.model_id == "prebuilt-layout"
        assert ingestion.timeout == 300
        assert ingestion.retries == 3
        assert "ocrHighResolution" in ingestion.features
        assert "languages" in ingestion.features
        assert "styleFont" in ingestion.features

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_init_missing_endpoint(self):
        """Test initialization fails without endpoint."""
        import sys
        if 'context_builder.impl.azure_di_ingestion' in sys.modules:
            del sys.modules['context_builder.impl.azure_di_ingestion']

        with patch.dict(os.environ, {}, clear=True):
            with patch('dotenv.load_dotenv'):
                with pytest.raises(ConfigurationError, match="AZURE_DI_ENDPOINT not found"):
                    from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                    AzureDocumentIntelligenceIngestion()

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        import sys
        if 'context_builder.impl.azure_di_ingestion' in sys.modules:
            del sys.modules['context_builder.impl.azure_di_ingestion']

        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/"}, clear=True):
            with patch('dotenv.load_dotenv'):
                with pytest.raises(ConfigurationError, match="AZURE_DI_API_KEY not found"):
                    from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                    AzureDocumentIntelligenceIngestion()


class TestAzureDocumentIntelligenceRetry:
    """Test retry logic for Azure DI API calls."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock Azure DI ingestion instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                ingestion = AzureDocumentIntelligenceIngestion()
                return ingestion

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_retry_on_rate_limit(self, mock_ingestion):
        """Test retry on rate limit error."""
        mock_poller = Mock()
        mock_poller.result.side_effect = [
            Exception("Rate limit exceeded (429)"),
            Exception("Rate limit exceeded (429)"),
            Mock(content="Test markdown")
        ]

        mock_ingestion.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch('time.sleep'):  # Don't actually sleep
            result = mock_ingestion._call_api_with_retry(b"test bytes")

        assert result.content == "Test markdown"
        assert mock_ingestion.client.begin_analyze_document.call_count == 3

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_retry_exhaustion(self, mock_ingestion):
        """Test that retries are exhausted and error is raised."""
        mock_poller = Mock()
        mock_poller.result.side_effect = Exception("Rate limit exceeded (429)")

        mock_ingestion.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch('time.sleep'):
            with pytest.raises(APIError, match="Rate limit exceeded after 3 retries"):
                mock_ingestion._call_api_with_retry(b"test bytes")

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_no_retry_on_auth_error(self, mock_ingestion):
        """Test no retry on authentication error."""
        mock_poller = Mock()
        mock_poller.result.side_effect = Exception("Unauthorized (403)")

        mock_ingestion.client.begin_analyze_document = Mock(return_value=mock_poller)

        with pytest.raises(ConfigurationError, match="Invalid API key"):
            mock_ingestion._call_api_with_retry(b"test bytes")

        # Should only be called once, no retries
        assert mock_ingestion.client.begin_analyze_document.call_count == 1

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_exponential_backoff_timing(self, mock_ingestion):
        """Test exponential backoff wait times."""
        mock_poller = Mock()
        mock_poller.result.side_effect = [
            Exception("Timeout"),
            Exception("Timeout"),
            Mock(content="Success")
        ]

        mock_ingestion.client.begin_analyze_document = Mock(return_value=mock_poller)

        with patch('time.sleep') as mock_sleep:
            mock_ingestion._call_api_with_retry(b"test bytes")

        # Should sleep for 2, then 4 seconds (exponential backoff)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)
        mock_sleep.assert_any_call(4)


class TestAzureDocumentIntelligenceMarkdownSaving:
    """Test markdown file saving functionality."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock Azure DI ingestion instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                ingestion = AzureDocumentIntelligenceIngestion()
                return ingestion

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_save_markdown_success(self, mock_ingestion, tmp_path):
        """Test successful markdown saving."""
        source_path = Path("test_document.pdf")
        markdown_content = "# Test Document\n\nThis is test content."

        result = mock_ingestion._save_markdown(markdown_content, source_path, tmp_path)

        assert result == "test_document_acquired.md"
        saved_file = tmp_path / result
        assert saved_file.exists()
        assert saved_file.read_text(encoding="utf-8") == markdown_content

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_save_markdown_creates_directory(self, mock_ingestion, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        source_path = Path("test.pdf")
        output_dir = tmp_path / "nested" / "output"
        markdown_content = "Test content"

        result = mock_ingestion._save_markdown(markdown_content, source_path, output_dir)

        assert output_dir.exists()
        assert (output_dir / result).exists()

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_save_markdown_unicode_content(self, mock_ingestion, tmp_path):
        """Test saving markdown with unicode characters."""
        source_path = Path("test.pdf")
        markdown_content = "# Tëst Dòcümënt\n\n中文内容 • émojis 🎉"

        result = mock_ingestion._save_markdown(markdown_content, source_path, tmp_path)

        saved_content = (tmp_path / result).read_text(encoding="utf-8")
        assert saved_content == markdown_content


class TestAzureDocumentIntelligenceMetadataExtraction:
    """Test metadata extraction from Azure DI results."""

    @pytest.fixture
    def mock_ingestion(self):
        """Create a mock Azure DI ingestion instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                ingestion = AzureDocumentIntelligenceIngestion()
                return ingestion

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_extract_metadata_complete(self, mock_ingestion):
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

        metadata = mock_ingestion._extract_metadata(mock_result, "test.md", 1234)

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
    def test_extract_metadata_minimal(self, mock_ingestion):
        """Test metadata extraction with minimal fields."""
        mock_result = Mock()
        mock_result.pages = None
        mock_result.languages = None
        mock_result.paragraphs = None
        mock_result.tables = None

        metadata = mock_ingestion._extract_metadata(mock_result, "test.md", 500)

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
    def mock_ingestion(self):
        """Create a mock Azure DI ingestion instance."""
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/", "AZURE_DI_API_KEY": "test_key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
                ingestion = AzureDocumentIntelligenceIngestion()
                return ingestion

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_process_implementation_success(self, mock_ingestion, tmp_path):
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
        mock_ingestion._call_api_with_retry = Mock(return_value=mock_result)

        result = mock_ingestion._process_implementation(test_file)

        # Check result structure
        assert "file_path" in result
        assert "md5" in result
        assert "markdown_file" in result
        assert result["markdown_file"] == "test_acquired.md"
        assert result["total_pages"] == 2
        assert result["language"] == "en"
        assert result["paragraph_count"] == 5
        assert "processing_time_ms" in result

        # Check markdown file was created
        md_file = tmp_path / "test_acquired.md"
        assert md_file.exists()
        assert md_file.read_text(encoding="utf-8") == "# Test Document\n\nExtracted content"

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_process_implementation_empty_content(self, mock_ingestion, tmp_path):
        """Test processing with empty content."""
        test_file = tmp_path / "empty.pdf"
        test_file.write_bytes(b"content")

        mock_result = Mock()
        mock_result.content = ""  # Empty content
        mock_result.pages = [Mock()]
        mock_result.languages = None
        mock_result.paragraphs = None
        mock_result.tables = None

        mock_ingestion._call_api_with_retry = Mock(return_value=mock_result)

        result = mock_ingestion._process_implementation(test_file)

        # Should create markdown with fallback message
        md_file = tmp_path / "empty_acquired.md"
        assert md_file.exists()
        content = md_file.read_text(encoding="utf-8")
        assert "No content extracted" in content

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_process_implementation_api_error(self, mock_ingestion, tmp_path):
        """Test processing with API error."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")

        mock_ingestion._call_api_with_retry = Mock(side_effect=APIError("API failed"))

        with pytest.raises(APIError, match="API failed"):
            mock_ingestion._process_implementation(test_file)


class TestAzureDocumentIntelligenceFactory:
    """Test factory registration."""

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_factory_registration(self):
        """Test Azure DI is registered with factory."""
        from context_builder.ingestion import IngestionFactory

        # Check that azure-di is in the registry
        assert 'azure-di' in IngestionFactory._registry

        # Should be able to create azure-di instance
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://test.com/", "AZURE_DI_API_KEY": "key"}):
            with patch('azure.ai.documentintelligence.DocumentIntelligenceClient'):
                instance = IngestionFactory.create('azure-di')
                assert instance is not None


class TestEnvironmentVariableLoading:
    """Test that environment variables are loaded correctly from .env file.

    This test class was added after a production incident where:
    - Multiple uvicorn processes were running on port 8000
    - Old processes served requests with cached code that didn't load .env
    - Result: AZURE_DI_ENDPOINT not found errors despite .env being correct

    Prevention: Always fully restart the server (kill all processes) rather than
    relying on auto-reload when debugging environment variable issues.
    """

    def test_dotenv_loads_azure_credentials(self, tmp_path):
        """Test that load_dotenv correctly loads Azure credentials from .env file."""
        from dotenv import load_dotenv

        # Create a temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text(
            "AZURE_DI_ENDPOINT=https://test-endpoint.cognitiveservices.azure.com/\n"
            "AZURE_DI_API_KEY=test_api_key_12345\n"
        )

        # Clear any existing env vars
        with patch.dict(os.environ, {}, clear=True):
            # Load the .env file
            load_dotenv(env_file, override=True)

            # Verify env vars are set
            assert os.getenv("AZURE_DI_ENDPOINT") == "https://test-endpoint.cognitiveservices.azure.com/"
            assert os.getenv("AZURE_DI_API_KEY") == "test_api_key_12345"

    def test_dotenv_override_existing_vars(self, tmp_path):
        """Test that load_dotenv with override=True replaces existing env vars."""
        from dotenv import load_dotenv

        env_file = tmp_path / ".env"
        env_file.write_text("AZURE_DI_ENDPOINT=https://new-endpoint.azure.com/\n")

        # Set an existing env var
        with patch.dict(os.environ, {"AZURE_DI_ENDPOINT": "https://old-endpoint.azure.com/"}):
            # Without override, old value should persist
            load_dotenv(env_file, override=False)
            assert os.getenv("AZURE_DI_ENDPOINT") == "https://old-endpoint.azure.com/"

            # With override, new value should replace
            load_dotenv(env_file, override=True)
            assert os.getenv("AZURE_DI_ENDPOINT") == "https://new-endpoint.azure.com/"

    @pytest.mark.skipif(not AZURE_DI_AVAILABLE, reason="azure-ai-documentintelligence not installed")
    def test_azure_di_uses_os_getenv(self):
        """Test that AzureDocumentIntelligenceIngestion uses os.getenv at init time.

        This is a regression test for the issue where env vars weren't
        available because the module was cached without the dotenv loading code.

        We verify the class uses os.getenv() to read credentials, which means
        as long as env vars are set (by main.py's load_dotenv or otherwise),
        the class will work correctly.
        """
        from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
        import inspect

        # Verify the __init__ method uses os.getenv to read credentials
        source = inspect.getsource(AzureDocumentIntelligenceIngestion.__init__)

        # Check that endpoint and api_key are read from os.getenv
        assert 'os.getenv("AZURE_DI_ENDPOINT")' in source or "os.getenv('AZURE_DI_ENDPOINT')" in source, \
            "AzureDocumentIntelligenceIngestion must read AZURE_DI_ENDPOINT from os.getenv()"
        assert 'os.getenv("AZURE_DI_API_KEY")' in source or "os.getenv('AZURE_DI_API_KEY')" in source, \
            "AzureDocumentIntelligenceIngestion must read AZURE_DI_API_KEY from os.getenv()"

    def test_azure_di_module_has_dotenv_fallback(self):
        """Verify azure_di_ingestion.py has fallback load_dotenv at module level.

        This ensures that even if main.py hasn't loaded .env yet (e.g., during
        CLI usage), the module will load it as a fallback.
        """
        from pathlib import Path
        import ast

        azure_di_path = Path(__file__).parent.parent.parent / "src" / "context_builder" / "impl" / "azure_di_ingestion.py"
        source = azure_di_path.read_text()

        # Verify load_dotenv is imported and called at module level
        assert "from dotenv import load_dotenv" in source, \
            "azure_di_ingestion.py must import load_dotenv"
        assert "load_dotenv(" in source, \
            "azure_di_ingestion.py must call load_dotenv() as fallback"

    def test_main_py_loads_dotenv_at_startup(self):
        """Verify that main.py initializes environment at module level.

        This ensures env vars are available before any request handlers run.
        The initialization is now done via startup.ensure_initialized().
        """
        import ast
        from pathlib import Path

        main_py = Path(__file__).parent.parent.parent / "src" / "context_builder" / "api" / "main.py"
        source = main_py.read_text()
        tree = ast.parse(source)

        # Find the ensure_initialized call (now handles .env loading)
        ensure_init_line = None
        first_decorator_line = float('inf')

        for node in ast.walk(tree):
            # Find _ensure_initialized() calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == '_ensure_initialized':
                    ensure_init_line = node.lineno
                    break
            # Find first @app decorator (marks where routes start)
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if hasattr(decorator.func, 'value') and hasattr(decorator.func.value, 'id'):
                            if decorator.func.value.id == 'app':
                                first_decorator_line = min(first_decorator_line, decorator.lineno)

        assert ensure_init_line is not None, "_ensure_initialized() must be called in main.py"
        assert ensure_init_line < first_decorator_line, \
            f"_ensure_initialized() at line {ensure_init_line} must come before route decorators at line {first_decorator_line}"

        # Also verify startup.py has load_dotenv
        startup_py = Path(__file__).parent.parent.parent / "src" / "context_builder" / "startup.py"
        startup_source = startup_py.read_text()
        assert "from dotenv import load_dotenv" in startup_source, \
            "startup.py must import load_dotenv"
        assert "load_dotenv(" in startup_source, \
            "startup.py must call load_dotenv()"
