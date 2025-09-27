"""Unit and integration tests for context_builder improvements."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from context_builder.acquisition import (
    DataAcquisition,
    AcquisitionFactory,
    FileNotSupportedError,
    ConfigurationError,
    APIError
)
from context_builder.cli import get_supported_files, process_file, setup_argparser


class TestFileDiscovery:
    """Test case-insensitive file discovery with .tif support."""

    def test_supported_extensions_includes_tif(self):
        """Verify .tif is in supported extensions."""
        assert '.tif' in DataAcquisition.SUPPORTED_EXTENSIONS
        assert '.tiff' in DataAcquisition.SUPPORTED_EXTENSIONS

    def test_case_insensitive_discovery(self, tmp_path):
        """Test that file discovery is case-insensitive."""
        # Create test files with various case combinations
        test_files = [
            "image.JPG",
            "photo.Jpeg",
            "scan.TIF",
            "document.PDF",
            "picture.png",
            "graphic.GIF"
        ]

        for filename in test_files:
            (tmp_path / filename).touch()

        # Add a non-supported file that should be ignored
        (tmp_path / "text.txt").touch()

        # Get supported files
        found_files = get_supported_files(tmp_path, recursive=False)
        found_names = [f.name for f in found_files]

        # All image files should be found
        for filename in test_files:
            assert filename in found_names

        # Text file should not be found
        assert "text.txt" not in found_names

    def test_recursive_discovery(self, tmp_path):
        """Test recursive file discovery."""
        # Create nested structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        (tmp_path / "root.jpg").touch()
        (subdir / "nested.pdf").touch()

        # Non-recursive should only find root file
        non_recursive = get_supported_files(tmp_path, recursive=False)
        assert len(non_recursive) == 1
        assert non_recursive[0].name == "root.jpg"

        # Recursive should find both
        recursive = get_supported_files(tmp_path, recursive=True)
        assert len(recursive) == 2
        names = [f.name for f in recursive]
        assert "root.jpg" in names
        assert "nested.pdf" in names

    def test_files_are_sorted(self, tmp_path):
        """Test that discovered files are sorted."""
        files = ["c.jpg", "a.png", "b.pdf"]
        for f in files:
            (tmp_path / f).touch()

        found = get_supported_files(tmp_path)
        names = [f.name for f in found]
        assert names == ["a.png", "b.pdf", "c.jpg"]


class TestCLIConfiguration:
    """Test CLI configuration flags."""

    def test_cli_flags_present(self):
        """Test that all new CLI flags are present."""
        parser = setup_argparser()
        args = parser.parse_args(["test.jpg"])

        # Check new configuration attributes exist
        assert hasattr(args, 'model')
        assert hasattr(args, 'max_tokens')
        assert hasattr(args, 'temperature')
        assert hasattr(args, 'max_pages')
        assert hasattr(args, 'render_scale')
        assert hasattr(args, 'timeout')
        assert hasattr(args, 'retries')
        assert hasattr(args, 'quiet')

    def test_cli_flag_defaults(self):
        """Test CLI flag default values."""
        parser = setup_argparser()
        args = parser.parse_args(["test.jpg"])

        assert args.model is None
        assert args.max_tokens is None
        assert args.temperature is None
        assert args.max_pages is None
        assert args.render_scale is None
        assert args.timeout is None
        assert args.retries is None
        assert args.quiet is False

    def test_cli_flag_values(self):
        """Test CLI flag value parsing."""
        parser = setup_argparser()
        args = parser.parse_args([
            "test.jpg",
            "--model", "gpt-4-turbo",
            "--max-tokens", "2048",
            "--temperature", "0.5",
            "--max-pages", "10",
            "--render-scale", "1.5",
            "--timeout", "60",
            "--retries", "5",
            "--quiet"
        ])

        assert args.model == "gpt-4-turbo"
        assert args.max_tokens == 2048
        assert args.temperature == 0.5
        assert args.max_pages == 10
        assert args.render_scale == 1.5
        assert args.timeout == 60
        assert args.retries == 5
        assert args.quiet is True


class TestDataAcquisition:
    """Test DataAcquisition base functionality."""

    def test_validate_file_case_insensitive(self, tmp_path):
        """Test file validation is case-insensitive."""
        test_file = tmp_path / "IMAGE.JPG"
        test_file.touch()

        acquisition = Mock(spec=DataAcquisition)
        acquisition.SUPPORTED_EXTENSIONS = DataAcquisition.SUPPORTED_EXTENSIONS
        acquisition.logger = Mock()

        # Call the real validate_file method
        DataAcquisition.validate_file(acquisition, test_file)

        # Should not raise an exception

    def test_validate_file_with_tif(self, tmp_path):
        """Test .tif file validation."""
        test_file = tmp_path / "scan.tif"
        test_file.touch()

        acquisition = Mock(spec=DataAcquisition)
        acquisition.SUPPORTED_EXTENSIONS = DataAcquisition.SUPPORTED_EXTENSIONS
        acquisition.logger = Mock()

        # Should not raise an exception
        DataAcquisition.validate_file(acquisition, test_file)

    def test_validate_unsupported_file(self, tmp_path):
        """Test validation fails for unsupported file types."""
        test_file = tmp_path / "document.txt"
        test_file.touch()

        acquisition = Mock(spec=DataAcquisition)
        acquisition.SUPPORTED_EXTENSIONS = DataAcquisition.SUPPORTED_EXTENSIONS
        acquisition.logger = Mock()

        with pytest.raises(FileNotSupportedError):
            DataAcquisition.validate_file(acquisition, test_file)


class TestOpenAIResilience:
    """Test OpenAI client resilience features."""

    @patch('openai.OpenAI')
    def test_retry_on_rate_limit(self, mock_openai_class):
        """Test retry logic on rate limit errors."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            # Mock API to fail twice then succeed
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

            acquisition.client.chat.completions.create = Mock(
                side_effect=[
                    Exception("Rate limit exceeded (429)"),
                    Exception("Rate limit exceeded (429)"),
                    mock_response
                ]
            )

            with patch('time.sleep'):  # Don't actually sleep in tests
                result = acquisition._call_api_with_retry([])

            assert result == mock_response
            assert acquisition.client.chat.completions.create.call_count == 3

    @patch('openai.OpenAI')
    def test_retry_on_timeout(self, mock_openai_class):
        """Test retry logic on timeout errors."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

            acquisition.client.chat.completions.create = Mock(
                side_effect=[
                    Exception("Request timeout"),
                    mock_response
                ]
            )

            with patch('time.sleep'):
                result = acquisition._call_api_with_retry([])

            assert result == mock_response
            assert acquisition.client.chat.completions.create.call_count == 2

    @patch('openai.OpenAI')
    def test_no_retry_on_auth_error(self, mock_openai_class):
        """Test no retry on authentication errors."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            acquisition.client.chat.completions.create = Mock(
                side_effect=Exception("Invalid api_key")
            )

            with pytest.raises(ConfigurationError):
                acquisition._call_api_with_retry([])

            # Should only call once (no retry)
            assert acquisition.client.chat.completions.create.call_count == 1

    @patch('openai.OpenAI')
    def test_exponential_backoff(self, mock_openai_class):
        """Test exponential backoff timing."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content='{"text": "success"}'))]

            acquisition.client.chat.completions.create = Mock(
                side_effect=[
                    Exception("Rate limit (429)"),
                    Exception("Rate limit (429)"),
                    mock_response
                ]
            )

            with patch('time.sleep') as mock_sleep:
                acquisition._call_api_with_retry([])

            # Check exponential backoff: 2^0 * 2 = 2, 2^1 * 2 = 4
            calls = mock_sleep.call_args_list
            assert calls[0] == call(2)
            assert calls[1] == call(4)


class TestJSONParsing:
    """Test JSON response parsing fallbacks."""

    @patch('openai.OpenAI')
    def test_parse_json_with_markdown(self, mock_openai_class):
        """Test parsing JSON from markdown code blocks."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            # Test with ```json block
            response = '```json\n{"key": "value"}\n```'
            result = acquisition._parse_response(response)
            assert result == {"key": "value"}

            # Test with plain ``` block
            response = '```\n{"key": "value"}\n```'
            result = acquisition._parse_response(response)
            assert result == {"key": "value"}

    @patch('openai.OpenAI')
    def test_parse_json_fallback(self, mock_openai_class):
        """Test fallback when JSON parsing fails."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            response = "This is not valid JSON"
            result = acquisition._parse_response(response)

            assert result["document_type"] == "unknown"
            assert result["text_content"] == response
            assert "_parse_error" in result


class TestConfigurationApplication:
    """Test configuration application from CLI to acquisition."""

    @patch('context_builder.acquisition.AcquisitionFactory.create')
    def test_config_applied_to_acquisition(self, mock_factory, tmp_path):
        """Test that CLI config is applied to acquisition instance."""
        mock_acquisition = Mock()
        mock_factory.return_value = mock_acquisition

        test_file = tmp_path / "test.jpg"
        test_file.touch()

        config = {
            'model': 'gpt-4-turbo',
            'max_tokens': 2048,
            'temperature': 0.5,
            'timeout': 60,
            'retries': 5
        }

        with patch.object(mock_acquisition, 'process', return_value={}):
            process_file(test_file, tmp_path, "openai", config=config)

        # Check that attributes were set
        assert mock_acquisition.model == 'gpt-4-turbo'
        assert mock_acquisition.max_tokens == 2048
        assert mock_acquisition.temperature == 0.5
        assert mock_acquisition.timeout == 60
        assert mock_acquisition.retries == 5


class TestMemoryOptimization:
    """Test PDF memory optimization."""

    @patch('openai.OpenAI')
    def test_pdf_streaming_processing(self, mock_openai_class):
        """Test that PDFs are processed page by page without accumulation."""
        from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            acquisition = OpenAIVisionAcquisition()

            # Mock pypdfium2
            import sys
            mock_pdfium = MagicMock()
            with patch.dict('sys.modules', {'pypdfium2': mock_pdfium}):
                # Mock PDF with 3 pages
                mock_doc = MagicMock()
                mock_doc.__len__ = Mock(return_value=3)
                mock_doc.__getitem__ = Mock(return_value=Mock(
                    render=Mock(return_value=Mock(
                        to_pil=Mock(return_value=Mock())
                    ))
                ))
                mock_pdfium.PdfDocument.return_value = mock_doc

                # Mock API responses
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content='{"text": "page"}'))]
                mock_response.usage = Mock(
                    prompt_tokens=100,
                    completion_tokens=50,
                    total_tokens=150
                )
                acquisition.client.chat.completions.create = Mock(return_value=mock_response)

                # Process PDF
                pages, usage = acquisition._process_pdf_pages(Path("test.pdf"))

                # Verify results
                assert len(pages) == 3
                assert usage["total_tokens"] == 450  # 150 * 3 pages

                # Verify PDF was closed
                mock_doc.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])