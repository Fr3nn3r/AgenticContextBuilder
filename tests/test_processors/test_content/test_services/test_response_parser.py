"""Tests for response parser service."""

import pytest
import json

from intake.processors.content_support.services import ResponseParser


class TestResponseParser:
    """Test suite for ResponseParser."""

    @pytest.fixture
    def parser(self):
        """Create ResponseParser instance."""
        return ResponseParser()

    def test_initialization(self, parser):
        """Test parser initialization."""
        assert parser is not None
        assert parser.logger is not None

    def test_parse_text_response(self, parser):
        """Test parsing plain text response."""
        response = "This is a plain text response"
        parsed, summary = parser.parse_ai_response(response, "text")

        assert parsed is None
        assert summary == response

    def test_parse_json_response_clean(self, parser):
        """Test parsing clean JSON response."""
        json_data = {"key": "value", "summary": "Test summary"}
        response = json.dumps(json_data)

        parsed, summary = parser.parse_ai_response(response, "json")

        assert parsed == json_data
        assert summary == "Test summary"

    def test_parse_json_with_markdown(self, parser):
        """Test parsing JSON wrapped in markdown code blocks."""
        json_data = {"key": "value", "summary": "Test summary"}
        response = f"```json\n{json.dumps(json_data)}\n```"

        parsed, summary = parser.parse_ai_response(response, "json")

        assert parsed == json_data
        assert summary == "Test summary"

    def test_parse_json_with_simple_markdown(self, parser):
        """Test parsing JSON with simple markdown blocks."""
        json_data = {"test": "data"}
        response = f"```\n{json.dumps(json_data)}\n```"

        parsed, summary = parser.parse_ai_response(response, "json")

        assert parsed == json_data
        # When no summary field in JSON, returns original response
        assert summary == response

    def test_parse_empty_response(self, parser):
        """Test parsing empty response."""
        parsed, summary = parser.parse_ai_response("", "json")

        assert parsed is None
        assert summary == "Empty response"

    def test_parse_whitespace_response(self, parser):
        """Test parsing whitespace-only response."""
        parsed, summary = parser.parse_ai_response("   \n\t  ", "json")

        assert parsed is None
        assert summary == "Empty response"

    def test_parse_malformed_json(self, parser):
        """Test parsing malformed JSON."""
        response = '{"key": "value", "broken": }'

        parsed, summary = parser.parse_ai_response(response, "json")

        assert parsed is None
        assert summary == response  # Returns original on parse failure

    def test_extract_json_from_markdown(self, parser):
        """Test JSON extraction from various markdown formats."""
        json_str = '{"test": "data"}'

        # Test with json code block
        result = parser.extract_json_from_markdown(f"```json\n{json_str}\n```")
        assert result == json_str

        # Test with plain code block
        result = parser.extract_json_from_markdown(f"```\n{json_str}\n```")
        assert result == json_str

        # Test without code block
        result = parser.extract_json_from_markdown(json_str)
        assert result == json_str

        # Test with extra whitespace
        result = parser.extract_json_from_markdown(f"  ```json\n{json_str}\n```  ")
        assert result == json_str

    def test_validate_json_structure_valid(self, parser):
        """Test JSON structure validation with valid data."""
        data = {"field1": "value1", "field2": "value2"}

        # Without required fields
        assert parser.validate_json_structure(data) is True

        # With required fields present
        assert parser.validate_json_structure(
            data, required_fields=["field1", "field2"]
        ) is True

    def test_validate_json_structure_invalid(self, parser):
        """Test JSON structure validation with invalid data."""
        # Not a dict
        assert parser.validate_json_structure([1, 2, 3]) is False

        # Missing required field
        data = {"field1": "value1"}
        assert parser.validate_json_structure(
            data, required_fields=["field1", "field2"]
        ) is False

    def test_extract_text_from_string(self, parser):
        """Test text extraction from string response."""
        text = "Simple text response"
        result = parser.extract_text_from_response(text)

        assert result == text

    def test_extract_text_from_dict(self, parser):
        """Test text extraction from dictionary response."""
        # With 'text' field
        response = {"text": "Text content", "other": "data"}
        result = parser.extract_text_from_response(response)
        assert result == "Text content"

        # With 'content' field
        response = {"content": "Content text", "other": "data"}
        result = parser.extract_text_from_response(response)
        assert result == "Content text"

        # With 'summary' field
        response = {"summary": "Summary text", "other": "data"}
        result = parser.extract_text_from_response(response)
        assert result == "Summary text"

        # Without known fields
        response = {"unknown": "data"}
        result = parser.extract_text_from_response(response)
        assert "unknown" in result  # Should be string representation

    def test_extract_text_with_truncation(self, parser):
        """Test text extraction with length limit."""
        long_text = "x" * 1000
        result = parser.extract_text_from_response(long_text, max_length=100)

        assert len(result) <= 120  # 100 + "... [truncated]"
        assert "... [truncated]" in result

    def test_parse_complex_json_response(self, parser):
        """Test parsing complex nested JSON response."""
        complex_data = {
            "summary": "Complex analysis",
            "data": {
                "nested": {
                    "values": [1, 2, 3],
                    "deep": {"key": "value"}
                }
            },
            "metadata": {"timestamp": "2024-01-15"}
        }

        response = f"```json\n{json.dumps(complex_data, indent=2)}\n```"
        parsed, summary = parser.parse_ai_response(response, "json")

        assert parsed == complex_data
        assert summary == "Complex analysis"

    def test_parse_json_with_special_characters(self, parser):
        """Test parsing JSON with special characters."""
        data = {
            "text": "Line 1\nLine 2\tTabbed",
            "special": "Quote: \"test\" and 'single'",
            "unicode": "Emoji: 😊 and symbols: €£¥"
        }

        response = json.dumps(data)
        parsed, summary = parser.parse_ai_response(response, "json")

        assert parsed == data
        assert parsed["unicode"] == "Emoji: 😊 and symbols: €£¥"

    def test_parse_array_json_response(self, parser):
        """Test parsing JSON array response."""
        array_data = [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"}
        ]

        response = json.dumps(array_data)
        parsed, summary = parser.parse_ai_response(response, "json")

        # Array is valid JSON but parser expects dict for summary extraction
        assert parsed == array_data
        assert summary == response  # No summary field in array


# TODO: Add edge case tests
# - Test with extremely large JSON responses
# - Test with deeply nested structures
# - Test with circular reference prevention

# TODO: Add performance tests
# - Test parsing speed for large responses
# - Test memory usage with large JSON structures