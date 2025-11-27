"""OpenAI API implementation for symbol table extraction from markdown documents."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from context_builder.utils.file_utils import get_file_metadata
from context_builder.utils.prompt_loader import load_prompt
from context_builder.utils.symbol_table_renderer import render_symbol_context

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Base exception for extraction errors."""

    pass


class APIError(ExtractionError):
    """Exception raised for API-related errors."""

    pass


class ConfigurationError(ExtractionError):
    """Exception raised for configuration errors."""

    pass


class OpenAISymbolExtraction:
    """
    OpenAI API implementation for extracting symbol tables from markdown.

    This implementation uses OpenAI's Structured Outputs feature with strict schema mode
    to extract policy symbols and variables from insurance contract markdown.

    Outputs both JSON and Markdown formats:
    - {filename}_symbol_table.json: Full structured data
    - {filename}_symbol_table.md: Token-efficient format for prompt injection

    Follows the "Schemas in Python, Prompts in Markdown" pattern:
    - Schema: PolicySymbolExtraction Pydantic model (loaded dynamically)
    - Prompt: policy_symbol_extraction.md (configurable)
    - Runner: This class orchestrates the API calls
    """

    def __init__(
        self,
        prompt_path: Optional[str] = None,
        schema_path: Optional[str] = None
    ):
        """
        Initialize OpenAI extraction.

        Args:
            prompt_path: Absolute path to prompt markdown file.
                        Defaults to policy_symbol_extraction.md in prompts/ directory.
            schema_path: Absolute path to schema Python file.
                        Defaults to policy_symbol_extraction.py in schemas/ directory.
        """
        # Get API key from environment
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY not found in environment variables. "
                "Please set it in your .env file."
            )

        # Initialize OpenAI client
        try:
            from openai import OpenAI

            # Default timeout and retry configuration
            self.timeout = 120  # seconds
            self.retries = 3  # number of retries

            # Initialize client with timeout
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0  # We handle retries ourselves for better control
            )
            logger.debug("OpenAI client initialized successfully")
        except ImportError:
            raise ConfigurationError(
                "OpenAI package not installed. "
                "Please install it with: pip install openai"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize OpenAI client: {e}")

        # Set prompt and schema paths
        self.prompt_path = prompt_path
        self.schema_path = schema_path

        # Load prompt configuration
        self._load_prompt_config()

        # Load schema
        self._load_schema()

        logger.debug(
            f"Using model: {self.model}, max_tokens: {self.max_tokens}, "
            f"temperature: {self.temperature}"
        )

    def _load_prompt_config(self):
        """Load prompt configuration from markdown file."""
        try:
            if self.prompt_path:
                # Load from absolute path
                self.prompt_name = Path(self.prompt_path).stem
                # TODO: Update load_prompt to support absolute paths
                # For now, we expect the file to be in prompts/ directory
                prompt_data = load_prompt(self.prompt_name)
            else:
                # Load default prompt
                self.prompt_name = "policy_symbol_extraction"
                prompt_data = load_prompt(self.prompt_name)

            self.prompt_config = prompt_data["config"]
            logger.debug(f"Loaded prompt: {self.prompt_config.get('name', 'unnamed')}")

            # Extract configuration from prompt file
            self.model = self.prompt_config.get("model", "gpt-4o")
            self.max_tokens = self.prompt_config.get("max_tokens", 4096)
            self.temperature = self.prompt_config.get("temperature", 0.0)

        except Exception as e:
            raise ConfigurationError(f"Failed to load prompt configuration: {e}")

    def _load_schema(self):
        """Load Pydantic schema from Python file."""
        try:
            if self.schema_path:
                # Load from absolute path
                # For now, use default schema from schemas directory
                from context_builder.schemas.policy_symbol_extraction import (
                    PolicySymbolExtraction,
                )
            else:
                # Load default schema
                from context_builder.schemas.policy_symbol_extraction import (
                    PolicySymbolExtraction,
                )

            self.schema_class = PolicySymbolExtraction
            logger.debug(f"Loaded schema: {self.schema_class.__name__}")

        except ImportError as e:
            raise ConfigurationError(f"Failed to import schema: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load schema: {e}")

    def _build_json_schema(self) -> Dict[str, Any]:
        """
        Build OpenAI-compatible JSON schema from Pydantic model.

        Returns:
            JSON schema dictionary for OpenAI Structured Outputs
        """
        # Get Pydantic model schema
        pydantic_schema = self.schema_class.model_json_schema()

        # OpenAI Structured Outputs format
        return {
            "name": self.schema_class.__name__,
            "strict": True,
            "schema": pydantic_schema
        }

    def _build_messages(self, markdown_content: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Build messages for OpenAI API call.

        Args:
            markdown_content: Content of the markdown file
            **kwargs: Additional template variables (e.g., symbol_table)

        Returns:
            List of message dictionaries for OpenAI API
        """
        # Load prompt with optional template kwargs
        prompt_data = load_prompt(self.prompt_name, **kwargs)
        messages = prompt_data["messages"]

        # Add markdown content to user message
        # Find user message and append markdown content
        for msg in messages:
            if msg["role"] == "user":
                msg["content"] = f"{msg['content']}\n\n{markdown_content}"
                break

        return messages

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse API response to extract JSON.

        For Structured Outputs, response should already be valid JSON.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dictionary

        Raises:
            APIError: If response cannot be parsed
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            raise APIError(f"Failed to parse JSON response: {e}")

    def _validate_with_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parsed JSON with Pydantic schema.

        Args:
            data: Parsed JSON data

        Returns:
            Validated data as dictionary

        Raises:
            APIError: If validation fails
        """
        try:
            # Validate with Pydantic model
            validated = self.schema_class(**data)
            return validated.model_dump()
        except ValidationError as e:
            logger.error(f"Schema validation failed: {e}")
            raise APIError(f"Schema validation failed: {e}")

    def _call_api_with_retry(
        self, messages: List[Dict[str, Any]], attempt: int = 0
    ) -> Any:
        """
        Call OpenAI API with retry logic and exponential backoff.

        Uses Structured Outputs with strict schema mode.

        Args:
            messages: Messages to send to API
            attempt: Current retry attempt number

        Returns:
            API response object with content

        Raises:
            APIError: If all retries exhausted
        """
        try:
            # Build JSON schema for Structured Outputs
            json_schema = self._build_json_schema()

            # Use Structured Outputs with strict schema
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={
                    "type": "json_schema",
                    "json_schema": json_schema
                },
                timeout=self.timeout
            )
            return response

        except Exception as e:
            error_str = str(e).lower()
            is_retryable = any(
                keyword in error_str
                for keyword in ["rate", "429", "500", "502", "503", "504", "timeout"]
            )

            if is_retryable and attempt < self.retries - 1:
                # Exponential backoff: 2^attempt * base_delay
                wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                logger.warning(
                    f"API call failed (attempt {attempt + 1}/{self.retries}): {e}. "
                    f"Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
                return self._call_api_with_retry(messages, attempt + 1)
            else:
                # Map to appropriate error type
                if "api_key" in error_str or "authentication" in error_str:
                    raise ConfigurationError(f"Invalid API key: {e}")
                elif "rate" in error_str or "429" in error_str:
                    raise APIError(f"Rate limit exceeded after {self.retries} retries: {e}")
                elif "timeout" in error_str:
                    raise APIError(f"Request timed out after {self.retries} retries: {e}")
                else:
                    raise APIError(f"API call failed after {self.retries} retries: {e}")

    def process(self, markdown_path: str, output_path: str, **kwargs) -> Dict[str, Any]:
        """
        Process markdown file and extract symbol table.

        Generates two output files:
        - {output_path} (JSON): Full structured symbol table
        - {output_path.replace('.json', '.md')} (Markdown): Token-efficient format

        Args:
            markdown_path: Path to markdown file to process
            output_path: Path to output JSON file (e.g., 'policy_symbol_table.json')
            **kwargs: Additional template variables

        Returns:
            Dictionary containing:
            - extracted_data: Validated symbol table
            - symbol_table_json: Path to JSON file
            - symbol_table_md: Path to Markdown file
            - file metadata and usage stats

        Raises:
            FileNotFoundError: If markdown file doesn't exist
            APIError: If API call fails
        """
        markdown_file = Path(markdown_path)
        output_file = Path(output_path)

        # Validate file exists
        if not markdown_file.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        logger.info(f"Processing markdown file: {markdown_path}")

        # Get file metadata
        result = get_file_metadata(markdown_file)

        # Read markdown content
        try:
            markdown_content = markdown_file.read_text(encoding="utf-8")
        except Exception as e:
            raise APIError(f"Failed to read markdown file: {e}")

        # Build messages with optional template kwargs
        messages = self._build_messages(markdown_content, **kwargs)

        # Call API with retry logic
        response = self._call_api_with_retry(messages)

        # Parse and validate response
        parsed_data = self._parse_response(response.choices[0].message.content)
        validated_data = self._validate_with_schema(parsed_data)

        # Add extracted data to result
        result["extracted_data"] = validated_data

        # Save JSON file
        logger.info(f"Saving symbol table JSON to: {output_file}")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        result["symbol_table_json"] = str(output_file)

        # Generate and save Markdown file
        md_path = output_file.with_suffix(".md")
        logger.info(f"Generating symbol table Markdown: {md_path}")
        markdown_output = render_symbol_context(validated_data)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_output)
        result["symbol_table_md"] = str(md_path)

        # Add usage statistics
        if hasattr(response, "usage"):
            result["_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        logger.info(f"Successfully extracted symbol table from {markdown_path}")
        logger.info(f"Outputs: {output_file}, {md_path}")
        return result
