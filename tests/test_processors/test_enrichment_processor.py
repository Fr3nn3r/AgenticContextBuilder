#!/usr/bin/env python3
"""
Tests for the enrichment processor.
Tests file categorization and metadata enrichment functionality.
"""

import pytest
from pathlib import Path

from file_ingest.processors.enrichment import EnrichmentProcessor


class TestEnrichmentProcessor:
    """Test suite for the EnrichmentProcessor class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.processor = EnrichmentProcessor()

    def test_file_categorization_image(self, tmp_path):
        """Test categorization of image files."""
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image content")

        result = self.processor.process_file(test_file)
        metadata = result['enriched_metadata']

        assert 'file_category' in metadata
        category = metadata['file_category']
        assert category['primary_category'] == 'image'
        assert category['extension'] == '.jpg'
        assert category['mime_type'] == 'image/jpeg'

    def test_file_categorization_document(self, tmp_path):
        """Test categorization of document files."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        result = self.processor.process_file(test_file)
        metadata = result['enriched_metadata']

        category = metadata['file_category']
        assert category['primary_category'] == 'document'
        assert category['extension'] == '.pdf'
        assert category['mime_type'] == 'application/pdf'

    def test_file_categorization_code(self, tmp_path):
        """Test categorization of code files."""
        test_file = tmp_path / "script.py"
        test_file.write_text("print('hello world')")

        result = self.processor.process_file(test_file)
        metadata = result['enriched_metadata']

        category = metadata['file_category']
        assert category['primary_category'] == 'code'
        assert category['extension'] == '.py'
        assert category['mime_type'] == 'text/x-python'

    def test_file_categorization_unknown(self, tmp_path):
        """Test categorization of unknown file types."""
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"unknown content")

        result = self.processor.process_file(test_file)
        metadata = result['enriched_metadata']

        category = metadata['file_category']
        assert category['primary_category'] == 'other'
        assert category['extension'] == '.xyz'

    def test_binary_vs_text_detection(self, tmp_path):
        """Test detection of binary vs text files."""
        # Text file
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello, world!")

        result = self.processor.process_file(text_file)
        metadata = result['enriched_metadata']
        assert metadata['file_category']['is_binary'] is False

        # Binary-like file (though we can't easily create a true binary file in tests)
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"binary content")

        result = self.processor.process_file(binary_file)
        metadata = result['enriched_metadata']
        assert metadata['file_category']['is_binary'] is True

    def test_configuration_disable_categorization(self, tmp_path):
        """Test disabling file categorization via configuration."""
        processor = EnrichmentProcessor({'categorize_files': False})

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = processor.process_file(test_file)
        metadata = result['enriched_metadata']

        # File categorization should not be present
        assert 'file_category' not in metadata

    def test_placeholder_content_analysis(self, tmp_path):
        """Test placeholder content analysis functionality."""
        processor = EnrichmentProcessor({'enable_content_analysis': True})

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = processor.process_file(test_file)
        metadata = result['enriched_metadata']

        # Should have placeholder content analysis
        assert 'content_analysis' in metadata
        assert metadata['content_analysis']['status'] == 'not_implemented'

    def test_placeholder_image_analysis(self, tmp_path):
        """Test placeholder image analysis functionality."""
        processor = EnrichmentProcessor({'analyze_images': True})

        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"fake image")

        result = processor.process_file(test_file)
        metadata = result['enriched_metadata']

        # Should have placeholder image analysis
        assert 'image_analysis' in metadata
        assert metadata['image_analysis']['status'] == 'not_implemented'

    def test_placeholder_text_preview(self, tmp_path):
        """Test placeholder text preview functionality."""
        processor = EnrichmentProcessor({'extract_text_preview': True})

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = processor.process_file(test_file)
        metadata = result['enriched_metadata']

        # Should have placeholder text preview
        assert 'text_preview' in metadata
        assert metadata['text_preview']['status'] == 'not_implemented'

    def test_enrichment_info_metadata(self, tmp_path):
        """Test enrichment information metadata."""
        processor = EnrichmentProcessor({
            'categorize_files': True,
            'enable_content_analysis': True
        })

        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = processor.process_file(test_file)
        metadata = result['enriched_metadata']

        # Should have enrichment info
        assert 'enrichment_info' in metadata
        enrichment_info = metadata['enrichment_info']
        assert enrichment_info['processor_version'] == '1.0.0'

        # Should list enabled features
        enabled_features = enrichment_info['enrichment_features_enabled']
        assert 'categorize_files' in enabled_features
        assert 'enable_content_analysis' in enabled_features

    def test_is_image_file_detection(self):
        """Test internal image file detection method."""
        test_cases = [
            (Path("test.jpg"), True),
            (Path("test.png"), True),
            (Path("test.gif"), True),
            (Path("test.txt"), False),
            (Path("test.pdf"), False),
        ]

        for file_path, expected in test_cases:
            result = self.processor._is_image_file(file_path)
            assert result == expected

    def test_is_text_file_detection(self):
        """Test internal text file detection method."""
        test_cases = [
            (Path("test.txt"), True),
            (Path("script.py"), True),
            (Path("style.css"), True),
            (Path("data.json"), True),
            (Path("image.jpg"), False),
            (Path("video.mp4"), False),
        ]

        for file_path, expected in test_cases:
            result = self.processor._is_text_file(file_path)
            assert result == expected

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        processor = EnrichmentProcessor({
            'enable_content_analysis': True,
            'categorize_files': False,
            'analyze_images': True,
            'extract_text_preview': False
        })
        assert processor.validate_config() is True

    def test_validate_config_invalid_type(self):
        """Test configuration validation with invalid types."""
        processor = EnrichmentProcessor({
            'enable_content_analysis': 'not_a_boolean'
        })
        assert processor.validate_config() is False

    def test_processor_info(self):
        """Test processor information retrieval."""
        info = self.processor.get_processor_info()

        assert info['name'] == 'EnrichmentProcessor'
        assert info['version'] == '1.0.0'
        assert 'description' in info
        assert info['supported_extensions'] == ['*']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])