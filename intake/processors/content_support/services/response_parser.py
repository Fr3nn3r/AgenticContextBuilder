# intake/processors/content_support/services/response_parser.py
# Response parsing service for AI outputs
# Handles JSON extraction, markdown cleanup, and response validation

import json
import logging
from typing import Any, Optional, Tuple, Dict


class ResponseParser:
    """Parses and cleans AI responses in various formats."""

    def __init__(self):
        """Initialize the response parser."""
        self.logger = logging.getLogger(__name__)

    def parse_ai_response(
        self,
        response: str,
        expected_format: str = "text"
    ) -> Tuple[Optional[Any], str]:
        """
        Parse AI response based on expected format.

        Args:
            response: Raw AI response string
            expected_format: Expected format ('json' or 'text')

        Returns:
            Tuple of (parsed_data, summary_text)
            - parsed_data: Parsed JSON data or None if text/failed
            - summary_text: Text summary or original response
        """
        if not response or not response.strip():
            self.logger.warning("Empty response received")
            return None, "Empty response"

        if expected_format == "json":
            return self._parse_json_response(response)
        else:
            return None, response

    def _parse_json_response(self, response: str) -> Tuple[Optional[Dict], str]:
        """
        Parse JSON response with markdown cleanup.

        Args:
            response: Raw response that might contain markdown

        Returns:
            Tuple of (parsed_json, summary_text)
        """
        try:
            cleaned = self.extract_json_from_markdown(response)
            parsed_data = json.loads(cleaned)

            # Extract summary if available
            summary = response
            if isinstance(parsed_data, dict):
                summary = parsed_data.get('summary', response)

            self.logger.debug("Successfully parsed JSON response")
            return parsed_data, summary

        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse JSON: {str(e)}")
            self.logger.debug(f"Response preview: {response[:500]}...")
            return None, response

    def extract_json_from_markdown(self, text: str) -> str:
        """
        Extract JSON content from markdown code blocks.

        Args:
            text: Text that might contain markdown code blocks

        Returns:
            Cleaned JSON string
        """
        cleaned = text.strip()

        # Remove markdown code blocks
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]  # Remove ```json
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]  # Remove ```

        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]  # Remove trailing ```

        return cleaned.strip()

    def validate_json_structure(
        self,
        data: Any,
        required_fields: Optional[list] = None
    ) -> bool:
        """
        Validate that parsed JSON has expected structure.

        Args:
            data: Parsed JSON data
            required_fields: List of required field names

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False

        if required_fields:
            for field in required_fields:
                if field not in data:
                    self.logger.warning(f"Missing required field: {field}")
                    return False

        return True

    def extract_text_from_response(
        self,
        response: Any,
        max_length: Optional[int] = None
    ) -> str:
        """
        Extract plain text from various response formats.

        Args:
            response: Response in any format
            max_length: Optional maximum length for truncation

        Returns:
            Plain text string
        """
        if isinstance(response, str):
            text = response
        elif isinstance(response, dict):
            # Try common fields for text content
            text = (
                response.get('text') or
                response.get('content') or
                response.get('summary') or
                str(response)
            )
        else:
            text = str(response)

        if max_length and len(text) > max_length:
            text = text[:max_length] + "... [truncated]"

        return text