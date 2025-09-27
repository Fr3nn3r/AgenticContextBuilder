"""Tests for the main ContentProcessor class."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from context_builder.processors.content import ContentProcessor
from context_builder.processors.content_support.models import ContentProcessorError
from context_builder.processors.base import ProcessingError


class TestContentProcessor:
    """Test suite for ContentProcessor."""

    def test_initialization_without_config(self):
        """Test ContentProcessor initialization with default config."""
        processor = ContentProcessor()

        assert processor is not None
        assert processor.typed_config is not None
        assert processor.prompt_provider is not None
        assert hasattr(processor, 'handlers')

    def test_initialization_with_dict_config(self):
        """Test ContentProcessor initialization with dictionary config."""
        config = {
            'processing': {
                'max_file_size_mb': 20,
                'graceful_degradation': False
            }
        }
        processor = ContentProcessor(config)

        assert processor.typed_config.processing.max_file_size_mb == 20
        assert processor.typed_config.processing.graceful_degradation is False

    def test_initialization_with_typed_config(self, test_config):
        """Test ContentProcessor initialization with typed config object."""
        processor = ContentProcessor(test_config)

        assert processor.typed_config == test_config

    @patch('context_builder.processors.content.load_dotenv')
    def test_ai_service_initialization_no_key(self, mock_load_dotenv):
        """Test AI service initialization without API key."""
        # Mock load_dotenv to do nothing (prevent loading from .env file)
        mock_load_dotenv.return_value = None

        with patch.dict('os.environ', {}, clear=True):
            processor = ContentProcessor()
            # AI service should be None when no key available
            assert processor.ai_service is None

    def test_handler_initialization(self):
        """Test that handlers are properly initialized."""
        processor = ContentProcessor()

        # Should have handlers list
        assert hasattr(processor, 'handlers')
        assert isinstance(processor.handlers, list)

        # Check handler types if AI service is available
        if processor.handlers:
            handler_types = [h.__class__.__name__ for h in processor.handlers]
            expected_types = [
                'TextContentHandler',
                'ImageContentHandler',
                'PDFContentHandler',
                'SpreadsheetContentHandler',
                'DocumentContentHandler'
            ]
            for expected in expected_types:
                assert expected in handler_types

    def test_process_file_system_file(self, tmp_path):
        """Test processing of system files (e.g., .DS_Store)."""
        processor = ContentProcessor()

        # Create system file
        system_file = tmp_path / ".DS_Store"
        system_file.touch()

        result = processor.process_file(system_file)

        assert 'file_content' in result
        content = result['file_content']
        assert content['processing_info']['processing_status'] == 'success'
        # System files should be processed but may not have content extracted
        assert content['content_metadata']['file_category'] == 'system_file'

    def test_process_file_size_limit(self, tmp_path, test_config):
        """Test file size limit enforcement."""
        test_config.processing.max_file_size_mb = 0.001  # 1KB limit
        test_config.processing.graceful_degradation = False  # Disable to get exception
        processor = ContentProcessor(test_config)

        # Create file larger than limit
        large_file = tmp_path / "large.txt"
        large_file.write_text("x" * 2000)  # 2KB

        with pytest.raises(ProcessingError) as exc_info:
            processor.process_file(large_file)

        assert "File size exceeds limit" in str(exc_info.value)

    @patch('context_builder.processors.content_support.factory.create_content_handler')
    def test_process_file_no_handler(self, mock_create_handler, tmp_path, test_config):
        """Test processing file with no available handler."""
        mock_create_handler.return_value = None

        test_config.processing.graceful_degradation = False  # Disable to get exception
        processor = ContentProcessor(test_config)

        # Create unsupported file
        test_file = tmp_path / "test.xyz"
        test_file.touch()

        with pytest.raises(ProcessingError) as exc_info:
            processor.process_file(test_file)

        assert "No handler available" in str(exc_info.value)

    @patch('context_builder.processors.content_support.factory.get_all_handlers')
    def test_process_file_with_handler(self, mock_get_handlers, sample_text_file):
        """Test successful file processing with handler."""
        # Create mock handler
        mock_handler = Mock()
        mock_handler.can_handle.return_value = True
        mock_handler.process.return_value = Mock(
            model_dump=lambda: {
                'processing_info': {'processing_status': 'success'},
                'content_metadata': {'content_type': 'text'},
                'content_data': {'test': 'data'}
            }
        )
        mock_handler.__class__.__name__ = 'TestHandler'

        mock_get_handlers.return_value = [mock_handler]

        processor = ContentProcessor()
        processor.handlers = [mock_handler]  # Set handlers directly

        result = processor.process_file(sample_text_file)

        assert 'file_content' in result
        assert result['file_content']['processing_info']['processing_status'] == 'success'
        mock_handler.process.assert_called_once()

    def test_graceful_degradation_enabled(self, test_config, tmp_path):
        """Test graceful degradation when enabled."""
        test_config.processing.graceful_degradation = True
        processor = ContentProcessor(test_config)

        # Create file that will cause error
        test_file = tmp_path / "test.txt"
        test_file.touch()

        # Mock handler that raises error
        with patch.object(processor, '_find_handler') as mock_find:
            mock_handler = Mock()
            mock_handler.process.side_effect = ContentProcessorError("Test error")
            mock_find.return_value = mock_handler

            result = processor.process_file(test_file)

            # Should return error content instead of raising
            assert 'file_content' in result
            assert result['file_content']['processing_info']['processing_status'] == 'error'

    def test_graceful_degradation_disabled(self, test_config, tmp_path):
        """Test that errors are raised when graceful degradation is disabled."""
        test_config.processing.graceful_degradation = False
        processor = ContentProcessor(test_config)

        # Create file that will cause error
        test_file = tmp_path / "test.txt"
        test_file.touch()

        # Mock handler that raises error
        with patch.object(processor, '_find_handler') as mock_find:
            mock_handler = Mock()
            mock_handler.process.side_effect = ContentProcessorError("Test error")
            mock_find.return_value = mock_handler

            with pytest.raises(Exception):  # ProcessingError from base class
                processor.process_file(test_file)

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        processor = ContentProcessor()
        assert processor.validate_config() is True

    def test_validate_config_no_handlers(self, test_config):
        """Test configuration validation with no handlers enabled."""
        # Disable all handlers
        test_config.handlers.text.enabled = False
        test_config.handlers.image.enabled = False
        test_config.handlers.pdf.enabled = False
        test_config.handlers.spreadsheet.enabled = False
        test_config.handlers.document.enabled = False

        processor = ContentProcessor(test_config)
        assert processor.validate_config() is False

    def test_get_processor_info(self):
        """Test getting processor information."""
        processor = ContentProcessor()
        info = processor.get_processor_info()

        assert 'name' in info
        assert 'version' in info
        assert 'ai_service_available' in info
        assert 'enabled_handlers' in info
        assert 'configuration' in info

    def test_get_supported_file_types(self):
        """Test getting list of supported file types."""
        processor = ContentProcessor()
        supported = processor.get_supported_file_types()

        assert isinstance(supported, list)
        # Should include common extensions
        common_extensions = ['.txt', '.pdf', '.csv', '.jpg']
        for ext in common_extensions:
            assert ext in supported

    def test_test_ai_connectivity(self):
        """Test AI connectivity testing method."""
        processor = ContentProcessor()
        results = processor.test_ai_connectivity()

        assert 'ai_service_available' in results
        assert 'api_key_configured' in results
        assert 'vision_api_enabled' in results
        assert 'test_request_successful' in results

    def test_unexpected_error_handling(self, tmp_path):
        """Test handling of unexpected errors during processing."""
        processor = ContentProcessor()

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.touch()

        # Mock handler that raises unexpected exception
        with patch.object(processor, '_find_handler') as mock_find:
            mock_handler = Mock()
            mock_handler.process.side_effect = ValueError("Unexpected error")
            mock_find.return_value = mock_handler

            result = processor.process_file(test_file)

            # Should handle gracefully
            assert 'file_content' in result
            assert result['file_content']['processing_info']['processing_status'] == 'error'
            assert 'Unexpected error' in result['file_content']['processing_info']['error_message']


# TODO: Add edge case tests
# - Test with various malformed inputs
# - Test concurrent processing scenarios
# - Test with different encoding types

# TODO: Add performance tests
# - Test processing time for large files
# - Test memory usage with multiple large files
# - Test handler caching efficiency

# TODO: Add integration tests with real API
# - Test with actual OpenAI API responses
# - Test rate limiting handling
# - Test timeout scenarios