"""Unit tests for OpenAIVisionAcquisition parsing methods."""

import json
import logging
from unittest.mock import patch
import pytest


class TestOpenAIVisionAcquisitionParsing:
    """Test JSON response parsing functionality."""

    @pytest.fixture
    def mock_acquisition(self):
        """Create a mock OpenAIVisionAcquisition instance."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('openai.OpenAI'):
                from context_builder.impl.openai_vision_acquisition import OpenAIVisionAcquisition
                return OpenAIVisionAcquisition()

    def test_parse_response_pure_json(self, mock_acquisition):
        """Test parsing pure JSON string."""
        response = json.dumps({
            "document_type": "invoice",
            "language": "en",
            "summary": "Test invoice",
            "key_information": {"total": "100.00"},
            "visual_elements": ["logo"],
            "text_content": "Invoice #123"
        })

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "invoice"
        assert result["language"] == "en"
        assert result["summary"] == "Test invoice"
        assert result["key_information"]["total"] == "100.00"
        assert result["visual_elements"] == ["logo"]
        assert result["text_content"] == "Invoice #123"

    def test_parse_response_json_code_block(self, mock_acquisition):
        """Test parsing JSON from ```json code block."""
        response = """Here's the analysis:
```json
{
    "document_type": "report",
    "language": "fr",
    "summary": "Quarterly report",
    "key_information": {},
    "visual_elements": [],
    "text_content": "Q3 2024 Report"
}
```
Additional text here"""

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "report"
        assert result["language"] == "fr"
        assert result["summary"] == "Quarterly report"
        assert result["text_content"] == "Q3 2024 Report"

    def test_parse_response_plain_code_block(self, mock_acquisition):
        """Test parsing JSON from plain ``` code block."""
        response = """```
{
    "document_type": "form",
    "language": "es",
    "summary": "Application form",
    "key_information": {"name": "John"},
    "visual_elements": ["signature"],
    "text_content": "Application"
}
```"""

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "form"
        assert result["language"] == "es"
        assert result["key_information"]["name"] == "John"

    def test_parse_response_nested_json(self, mock_acquisition):
        """Test parsing nested JSON structures."""
        response = json.dumps({
            "document_type": "complex",
            "language": "en",
            "summary": "Complex doc",
            "key_information": {
                "nested": {
                    "deep": {
                        "value": "found"
                    }
                },
                "list": [1, 2, 3]
            },
            "visual_elements": ["chart", "table"],
            "text_content": "Complex content"
        })

        result = mock_acquisition._parse_response(response)

        assert result["key_information"]["nested"]["deep"]["value"] == "found"
        assert result["key_information"]["list"] == [1, 2, 3]
        assert len(result["visual_elements"]) == 2

    def test_parse_response_unicode(self, mock_acquisition):
        """Test parsing response with Unicode characters."""
        response = json.dumps({
            "document_type": "international",
            "language": "zh",
            "summary": "中文文档",
            "key_information": {"名称": "测试"},
            "visual_elements": ["图表"],
            "text_content": "内容 with émojis 🎉"
        }, ensure_ascii=False)

        result = mock_acquisition._parse_response(response)

        assert result["summary"] == "中文文档"
        assert result["key_information"]["名称"] == "测试"
        assert "🎉" in result["text_content"]

    def test_parse_response_malformed_json(self, mock_acquisition):
        """Test parsing malformed JSON returns fallback."""
        response = "This is not {valid JSON} at all"

        result = mock_acquisition._parse_response(response)

        # Should return fallback structure
        assert result["document_type"] == "unknown"
        assert result["language"] == "unknown"
        assert result["summary"] == "Failed to parse structured response"
        assert result["key_information"] == {}
        assert result["visual_elements"] == []
        assert result["text_content"] == response
        assert "_parse_error" in result

    def test_parse_response_incomplete_json(self, mock_acquisition):
        """Test parsing incomplete JSON."""
        response = '{"document_type": "test", "language":'  # Incomplete

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "unknown"
        assert result["text_content"] == response
        assert "_parse_error" in result

    def test_parse_response_invalid_json_in_code_block(self, mock_acquisition):
        """Test parsing invalid JSON in code block."""
        response = """```json
{
    "document_type": "test",
    "missing_comma_here"
    "language": "en"
}
```"""

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "unknown"
        assert "_parse_error" in result

    def test_parse_response_empty_string(self, mock_acquisition):
        """Test parsing empty string."""
        response = ""

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "unknown"
        assert result["text_content"] == ""
        assert "_parse_error" in result

    def test_parse_response_whitespace_only(self, mock_acquisition):
        """Test parsing whitespace-only string."""
        response = "   \n\t  "

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "unknown"
        assert "_parse_error" in result

    def test_parse_response_logs_error(self, mock_acquisition, caplog):
        """Test parsing logs error for malformed JSON."""
        response = "Not JSON"

        with caplog.at_level(logging.ERROR):
            result = mock_acquisition._parse_response(response)

        assert "Failed to parse JSON response" in caplog.text

    def test_parse_response_logs_raw_response_debug(self, mock_acquisition, caplog):
        """Test parsing logs raw response at debug level."""
        response = "Invalid JSON"

        with caplog.at_level(logging.DEBUG):
            result = mock_acquisition._parse_response(response)

        assert "Raw response: Invalid JSON" in caplog.text

    def test_parse_response_multiple_code_blocks(self, mock_acquisition):
        """Test parsing with multiple code blocks takes first json block."""
        response = """First block:
```json
{"document_type": "first", "language": "en", "summary": "First", "key_information": {}, "visual_elements": [], "text_content": "First"}
```

Second block:
```json
{"document_type": "second", "language": "fr", "summary": "Second", "key_information": {}, "visual_elements": [], "text_content": "Second"}
```"""

        result = mock_acquisition._parse_response(response)

        # Should parse the first JSON block
        assert result["document_type"] == "first"
        assert result["language"] == "en"

    def test_parse_response_code_block_without_json_marker(self, mock_acquisition):
        """Test parsing code block without 'json' language marker."""
        response = """```
{"document_type": "plain", "language": "de", "summary": "Plain block", "key_information": {}, "visual_elements": [], "text_content": "Content"}
```"""

        result = mock_acquisition._parse_response(response)

        assert result["document_type"] == "plain"
        assert result["language"] == "de"

    def test_parse_response_preserves_extra_fields(self, mock_acquisition):
        """Test parsing preserves extra fields not in standard schema."""
        response = json.dumps({
            "document_type": "custom",
            "language": "en",
            "summary": "Custom doc",
            "key_information": {},
            "visual_elements": [],
            "text_content": "Text",
            "extra_field": "extra_value",
            "custom_data": {"nested": "value"}
        })

        result = mock_acquisition._parse_response(response)

        assert result["extra_field"] == "extra_value"
        assert result["custom_data"]["nested"] == "value"