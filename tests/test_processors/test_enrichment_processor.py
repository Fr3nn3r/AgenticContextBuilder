#!/usr/bin/env python3
"""
Tests for the enrichment processor.
Tests document insights and key data extraction functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import json

from context_builder.processors.enrichment import EnrichmentProcessor
from context_builder.models import DocumentInsights, KeyDataPoint


class TestEnrichmentProcessor:
    """Test suite for the EnrichmentProcessor class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Mock configuration to avoid loading real config files
        with patch('intake.processors.enrichment.Path.exists', return_value=False):
            with patch.object(EnrichmentProcessor, '_init_prompt_provider'):
                with patch.object(EnrichmentProcessor, '_init_ai_provider'):
                    self.processor = EnrichmentProcessor()
                    # Manually set up mock providers
                    self.processor.prompt_provider = Mock()
                    self.processor.ai_provider = Mock()

    def test_process_file_with_vision_api_content(self, tmp_path):
        """Test processing a file with Vision API extracted content."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock existing metadata from ContentProcessor (new structure)
        existing_metadata = {
            'file_content': {
                'extraction_results': [
                    {
                        'method': 'vision_openai',
                        'pages': [
                            {'page': 1, 'analysis': 'Invoice #12345\nAmount: $500\nDate: 2024-01-15'},
                            {'page': 2, 'analysis': 'Additional terms and conditions'}
                        ]
                    }
                ],
                'content_metadata': {
                    'content_type': 'document',
                    'file_category': 'pdf'
                },
                'processing_info': {
                    'processing_status': 'success'
                }
            }
        }

        # Mock AI response for synthesis
        mock_response = json.dumps({
            'summary': 'Invoice document for $500 dated January 15, 2024',
            'content_category': 'invoice',
            'key_data_points': [
                {'key': 'invoice_number', 'value': '12345', 'confidence': 0.95, 'page': 1},
                {'key': 'amount', 'value': 500, 'confidence': 0.98, 'page': 1},
                {'key': 'date', 'value': '2024-01-15', 'confidence': 0.97, 'page': 1}
            ],
            'category_confidence': 0.95,
            'language': 'en'
        })

        self.processor.ai_provider.analyze_text = Mock(return_value=mock_response)
        self.processor.prompt_provider.get_prompt_template = Mock(return_value="Test prompt")

        result = self.processor.process_file(test_file, existing_metadata)

        assert 'enrichment_metadata' in result
        metadata = result['enrichment_metadata']
        assert 'document_insights' in metadata
        insights = metadata['document_insights']
        assert insights['summary'] == 'Invoice document for $500 dated January 15, 2024'
        assert insights['content_category'] == 'invoice'
        assert len(insights['key_data_points']) == 3

    def test_process_file_with_ocr_content(self, tmp_path):
        """Test processing a file with OCR extracted content."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf content")

        # Mock existing metadata from ContentProcessor (new structure)
        existing_metadata = {
            'file_content': {
                'extraction_results': [
                    {
                        'method': 'ocr_tesseract',
                        'content': 'Policy Number: POL-2024-001\nPremium: $1200/year\nCoverage: Comprehensive'
                    }
                ],
                'content_metadata': {
                    'content_type': 'document',
                    'file_category': 'pdf'
                },
                'processing_info': {
                    'processing_status': 'success'
                }
            }
        }

        # Mock AI response for analysis
        mock_response = json.dumps({
            'summary': 'Insurance policy document with comprehensive coverage',
            'content_category': 'policy_document',
            'key_data_points': [
                {'key': 'policy_number', 'value': 'POL-2024-001', 'confidence': 0.92},
                {'key': 'premium', 'value': 1200, 'confidence': 0.89},
                {'key': 'coverage_type', 'value': 'Comprehensive', 'confidence': 0.85}
            ],
            'category_confidence': 0.88,
            'language': 'en'
        })

        self.processor.ai_provider.analyze_text = Mock(return_value=mock_response)
        self.processor.prompt_provider.get_prompt_template = Mock(return_value="Test prompt")

        result = self.processor.process_file(test_file, existing_metadata)

        assert 'enrichment_metadata' in result
        metadata = result['enrichment_metadata']
        insights = metadata['document_insights']
        assert insights['content_category'] == 'policy_document'
        assert len(insights['key_data_points']) == 3

    def test_process_file_without_content(self, tmp_path):
        """Test processing a file without extracted content."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # No content extracted
        existing_metadata = {}

        result = self.processor.process_file(test_file, existing_metadata)

        # Should return empty dict when no content available
        assert result == {}

    def test_process_file_with_disabled_insights(self, tmp_path):
        """Test processing when document insights is disabled."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        self.processor.config['enable_document_insights'] = False

        existing_metadata = {
            'file_content': {
                'extraction_results': [
                    {'method': 'ocr_tesseract', 'content': 'Some content'}
                ],
                'content_metadata': {},
                'processing_info': {'processing_status': 'success'}
            }
        }

        result = self.processor.process_file(test_file, existing_metadata)

        # Should return empty dict when disabled
        assert result == {}

    def test_process_file_with_empty_extraction_results(self, tmp_path):
        """Test processing when extraction_results is empty."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        existing_metadata = {
            'file_content': {
                'extraction_results': [],
                'content_metadata': {},
                'processing_info': {'processing_status': 'error'}
            }
        }

        result = self.processor.process_file(test_file, existing_metadata)

        # Should return empty dict and log warning
        assert result == {}

    def test_ai_provider_error_handling(self, tmp_path):
        """Test error handling when AI provider fails."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        existing_metadata = {
            'file_content': {
                'extraction_results': [
                    {'method': 'ocr_tesseract', 'content': 'Some content'}
                ],
                'content_metadata': {},
                'processing_info': {'processing_status': 'success'}
            }
        }

        # Mock AI provider to raise an error
        self.processor.ai_provider.analyze_text = Mock(side_effect=Exception("API error"))
        self.processor.prompt_provider.get_prompt_template = Mock(return_value="Test prompt")

        result = self.processor.process_file(test_file, existing_metadata)

        assert 'enrichment_metadata' in result
        metadata = result['enrichment_metadata']
        assert 'error' in metadata
        assert 'API error' in metadata['error']

    def test_max_key_points_limit(self, tmp_path):
        """Test that key data points are limited to max_key_points config."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        existing_metadata = {
            'file_content': {
                'extraction_results': [
                    {'method': 'ocr_tesseract', 'content': 'Test content'}
                ],
                'content_metadata': {},
                'processing_info': {'processing_status': 'success'}
            }
        }

        # Mock response with many key data points
        key_points = [{'key': f'key_{i}', 'value': i, 'confidence': 0.9} for i in range(20)]
        mock_response = json.dumps({
            'summary': 'Test document',
            'content_category': 'other',
            'key_data_points': key_points,
            'category_confidence': 0.8
        })

        self.processor.ai_provider.analyze_text = Mock(return_value=mock_response)
        self.processor.prompt_provider.get_prompt_template = Mock(return_value="Test prompt")
        self.processor.config['max_key_points'] = 5

        result = self.processor.process_file(test_file, existing_metadata)

        insights = result['enrichment_metadata']['document_insights']
        assert len(insights['key_data_points']) == 5

    def test_validate_config_valid(self):
        """Test configuration validation with valid config."""
        # Set up valid config
        self.processor.config['enable_document_insights'] = True
        self.processor.config['enable_key_extraction'] = True
        self.processor.config['max_key_points'] = 10
        self.processor.config['confidence_threshold'] = 0.7

        # Mock providers to be available
        self.processor.prompt_provider = Mock()
        self.processor.ai_provider = Mock()

        assert self.processor.validate_config() is True

    def test_validate_config_invalid_max_key_points(self):
        """Test configuration validation with invalid max_key_points."""
        self.processor.config['max_key_points'] = 100  # Too high

        # Mock providers to be available
        self.processor.prompt_provider = Mock()
        self.processor.ai_provider = Mock()

        assert self.processor.validate_config() is False

    def test_validate_config_invalid_confidence_threshold(self):
        """Test configuration validation with invalid confidence_threshold."""
        self.processor.config['confidence_threshold'] = 1.5  # Out of range

        # Mock providers to be available
        self.processor.prompt_provider = Mock()
        self.processor.ai_provider = Mock()

        assert self.processor.validate_config() is False

    def test_processor_info(self):
        """Test processor information retrieval."""
        info = self.processor.get_processor_info()

        assert info['name'] == 'EnrichmentProcessor'
        assert info['version'] == '2.0.0'
        assert 'description' in info
        assert info['supported_extensions'] == ['*']

    def test_json_response_parsing(self):
        """Test JSON response parsing with various formats."""
        # Test clean JSON
        clean_json = '{"summary": "test", "content_category": "other", "key_data_points": []}'
        result = self.processor._parse_json_response(clean_json)
        assert result['summary'] == 'test'

        # Test JSON with markdown code block
        markdown_json = '```json\n{"summary": "test", "content_category": "other", "key_data_points": []}\n```'
        result = self.processor._parse_json_response(markdown_json)
        assert result['summary'] == 'test'

        # Test invalid JSON (should return fallback)
        invalid_json = 'not valid json'
        result = self.processor._parse_json_response(invalid_json)
        assert result['summary'] == 'Failed to parse document insights'
        assert result['content_category'] == 'other'

    def test_retry_logic(self, tmp_path):
        """Test retry logic for AI calls."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        existing_metadata = {
            'file_content': {
                'extraction_results': [
                    {'method': 'ocr_tesseract', 'content': 'Test content'}
                ],
                'content_metadata': {},
                'processing_info': {'processing_status': 'success'}
            }
        }

        # Mock to fail twice, then succeed
        mock_response = json.dumps({
            'summary': 'Test document',
            'content_category': 'other',
            'key_data_points': [],
            'category_confidence': 0.8
        })

        self.processor.ai_provider.analyze_text = Mock(
            side_effect=[Exception("API error"), Exception("API error"), mock_response]
        )
        self.processor.prompt_provider.get_prompt_template = Mock(return_value="Test prompt")
        self.processor.config['max_retries'] = 2

        result = self.processor.process_file(test_file, existing_metadata)

        # Should succeed after retries
        assert 'enrichment_metadata' in result
        assert 'document_insights' in result['enrichment_metadata']

        # Verify it was called 3 times (initial + 2 retries)
        assert self.processor.ai_provider.analyze_text.call_count == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])