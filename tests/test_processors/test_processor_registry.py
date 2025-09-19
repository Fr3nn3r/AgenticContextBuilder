#!/usr/bin/env python3
"""
Tests for the processor registry and plugin system.
Tests processor discovery, instantiation, and pipeline functionality.
"""

import pytest
from unittest.mock import patch, MagicMock

from file_ingest.processors import (
    ProcessorRegistry,
    ProcessingPipeline,
    ProcessingError,
    registry
)
from file_ingest.processors.metadata import MetadataProcessor
from file_ingest.processors.enrichment import EnrichmentProcessor


class TestProcessorRegistry:
    """Test suite for the ProcessorRegistry class."""

    def test_processor_discovery(self):
        """Test that processors are automatically discovered."""
        # Should discover at least MetadataProcessor and EnrichmentProcessor
        processors = registry.list_processors()
        assert 'MetadataProcessor' in processors
        assert 'EnrichmentProcessor' in processors

    def test_get_processor_by_name(self):
        """Test getting processor instance by name."""
        processor = registry.get_processor('MetadataProcessor')
        assert isinstance(processor, MetadataProcessor)

    def test_get_processor_with_config(self):
        """Test getting processor instance with configuration."""
        config = {'include_hashes': False}
        processor = registry.get_processor('MetadataProcessor', config)
        assert isinstance(processor, MetadataProcessor)
        assert processor.config['include_hashes'] is False

    def test_get_nonexistent_processor(self):
        """Test getting non-existent processor raises ValueError."""
        with pytest.raises(ValueError, match="Processor 'NonExistentProcessor' not found"):
            registry.get_processor('NonExistentProcessor')

    def test_get_processor_info(self):
        """Test getting information about a specific processor."""
        info = registry.get_processor_info('MetadataProcessor')

        assert 'name' in info
        assert 'version' in info
        assert 'description' in info
        assert 'supported_extensions' in info
        assert info['name'] == 'MetadataProcessor'

    def test_get_all_processor_info(self):
        """Test getting information about all processors."""
        all_info = registry.get_all_processor_info()

        assert isinstance(all_info, dict)
        assert 'MetadataProcessor' in all_info
        assert 'EnrichmentProcessor' in all_info

    def test_get_info_nonexistent_processor(self):
        """Test getting info for non-existent processor raises ValueError."""
        with pytest.raises(ValueError, match="Processor 'NonExistentProcessor' not found"):
            registry.get_processor_info('NonExistentProcessor')


class TestProcessingPipeline:
    """Test suite for the ProcessingPipeline class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.pipeline = ProcessingPipeline(registry)

    def test_add_processor(self):
        """Test adding processors to the pipeline."""
        self.pipeline.add_processor('MetadataProcessor')
        assert len(self.pipeline.processors) == 1
        assert isinstance(self.pipeline.processors[0], MetadataProcessor)

    def test_add_processor_with_config(self):
        """Test adding processor with configuration."""
        config = {'include_hashes': False}
        self.pipeline.add_processor('MetadataProcessor', config)

        processor = self.pipeline.processors[0]
        assert processor.config['include_hashes'] is False

    def test_add_multiple_processors(self):
        """Test adding multiple processors to the pipeline."""
        self.pipeline.add_processor('MetadataProcessor')
        self.pipeline.add_processor('EnrichmentProcessor')

        assert len(self.pipeline.processors) == 2
        assert isinstance(self.pipeline.processors[0], MetadataProcessor)
        assert isinstance(self.pipeline.processors[1], EnrichmentProcessor)

    def test_process_file_single_processor(self, tmp_path):
        """Test processing file through single processor."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        self.pipeline.add_processor('MetadataProcessor')
        result = self.pipeline.process_file(test_file)

        assert 'file_metadata' in result
        assert result['file_metadata']['file_name'] == "test.txt"

    def test_process_file_multiple_processors(self, tmp_path):
        """Test processing file through multiple processors."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        self.pipeline.add_processor('MetadataProcessor')
        self.pipeline.add_processor('EnrichmentProcessor')
        result = self.pipeline.process_file(test_file)

        # Should have outputs from both processors
        assert 'file_metadata' in result
        assert 'enriched_metadata' in result

    def test_process_file_error_handling(self, tmp_path):
        """Test error handling during file processing."""
        # Create a processor that will fail
        with patch.object(MetadataProcessor, 'process_file', side_effect=Exception("Test error")):
            self.pipeline.add_processor('MetadataProcessor')

            test_file = tmp_path / "test.txt"
            test_file.write_text("test content")

            with pytest.raises(ProcessingError, match="Processing failed: Test error"):
                self.pipeline.process_file(test_file)

    def test_get_pipeline_info(self):
        """Test getting information about the pipeline."""
        self.pipeline.add_processor('MetadataProcessor')
        self.pipeline.add_processor('EnrichmentProcessor')

        info = self.pipeline.get_pipeline_info()

        assert isinstance(info, list)
        assert len(info) == 2
        assert info[0]['name'] == 'MetadataProcessor'
        assert info[1]['name'] == 'EnrichmentProcessor'

    def test_empty_pipeline(self, tmp_path):
        """Test processing with empty pipeline."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = self.pipeline.process_file(test_file)
        assert result == {}  # Empty result for empty pipeline


class TestProcessingError:
    """Test suite for the ProcessingError exception."""

    def test_basic_error_message(self):
        """Test basic error message formatting."""
        error = ProcessingError("Test error message")
        assert str(error) == "Test error message"

    def test_error_with_processor_name(self):
        """Test error message with processor name."""
        error = ProcessingError("Test error", processor_name="TestProcessor")
        assert "Processor: TestProcessor" in str(error)

    def test_error_with_file_path(self):
        """Test error message with file path."""
        from pathlib import Path
        file_path = Path("/test/file.txt")
        error = ProcessingError("Test error", file_path=file_path)
        assert f"File: {file_path}" in str(error)

    def test_error_with_all_info(self):
        """Test error message with all information."""
        from pathlib import Path
        file_path = Path("/test/file.txt")
        error = ProcessingError(
            "Test error",
            file_path=file_path,
            processor_name="TestProcessor"
        )

        error_str = str(error)
        assert "Test error" in error_str
        assert "Processor: TestProcessor" in error_str
        assert f"File: {file_path}" in error_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])