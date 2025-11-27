"""OpenAI API implementation for policy logic extraction with normalized schema.

This implementation uses the normalized recursive LogicNode schema to prevent
hallucinated operators while still producing standard JSON Logic output via
transpilation.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from context_builder.utils.file_utils import get_file_metadata
from context_builder.utils.prompt_loader import load_prompt
from context_builder.utils.json_logic_transpiler import transpile_policy_analysis

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


class OpenAILogicExtraction:
    """
    OpenAI API implementation for extracting policy logic as normalized JSON Logic.

    This implementation uses OpenAI's Structured Outputs feature with strict schema mode
    to extract policy rules as normalized logic trees (op/args format), then transpiles
    them to standard JSON Logic format.

    Follows the "Schemas in Python, Prompts in Markdown" pattern:
    - Schema: PolicyAnalysis Pydantic model with normalized LogicNode (loaded dynamically)
    - Prompt: policy_logic_extraction.md (configurable)
    - Runner: This class orchestrates the API calls and transpilation
    """

    def __init__(
        self,
        prompt_path: Optional[str] = None,
        schema_path: Optional[str] = None
    ):
        """
        Initialize OpenAI logic extraction.

        Args:
            prompt_path: Absolute path to prompt markdown file.
                        Defaults to policy_logic_extraction.md in prompts/ directory.
            schema_path: Absolute path to schema Python file.
                        Defaults to policy_logic_extraction.py in schemas/ directory.
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
                self.prompt_name = "policy_logic_extraction"
                prompt_data = load_prompt(self.prompt_name)

            self.prompt_config = prompt_data["config"]
            logger.debug(f"Loaded prompt: {self.prompt_config.get('name', 'unnamed')}")

            # Extract configuration from prompt file
            self.model = self.prompt_config.get("model", "gpt-4o")
            self.max_tokens = self.prompt_config.get("max_tokens", 16000)
            self.temperature = self.prompt_config.get("temperature", 0.0)

        except Exception as e:
            raise ConfigurationError(f"Failed to load prompt configuration: {e}")

    def _load_schema(self):
        """Load Pydantic schema from Python file."""
        try:
            if self.schema_path:
                # Load from absolute path
                # For now, use default schema from schemas directory
                from context_builder.schemas.policy_logic_extraction import (
                    PolicyAnalysis,
                )
            else:
                # Load default schema
                from context_builder.schemas.policy_logic_extraction import (
                    PolicyAnalysis,
                )

            self.schema_class = PolicyAnalysis
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

    def process(
        self,
        markdown_path: str,
        output_base_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process markdown file and extract policy logic.

        Generates two output files:
        - {output_base_path}_normalized_logic.json: LLM output with normalized format
        - {output_base_path}_logic.json: Transpiled standard JSON Logic format

        Args:
            markdown_path: Path to markdown file to process
            output_base_path: Base path for output files (without extension)
            **kwargs: Additional template variables (e.g., symbol_table)

        Returns:
            Dictionary containing:
            - normalized_logic_json: Path to normalized logic file
            - transpiled_logic_json: Path to transpiled logic file
            - file metadata and usage stats

        Raises:
            FileNotFoundError: If markdown file doesn't exist
            APIError: If API call fails
        """
        markdown_file = Path(markdown_path)
        base_path = Path(output_base_path)

        # Validate file exists
        if not markdown_file.exists():
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")

        logger.info(f"Processing markdown file for logic extraction: {markdown_path}")

        # Get file metadata
        result = get_file_metadata(markdown_file)

        # Read markdown content
        try:
            markdown_content = markdown_file.read_text(encoding="utf-8")
        except Exception as e:
            raise APIError(f"Failed to read markdown file: {e}")

        # Build messages with optional template kwargs (e.g., symbol_table)
        messages = self._build_messages(markdown_content, **kwargs)

        # Call API with retry logic
        response = self._call_api_with_retry(messages)

        # Parse and validate response
        parsed_data = self._parse_response(response.choices[0].message.content)
        validated_data = self._validate_with_schema(parsed_data)

        # Transpile to standard JSON Logic
        transpiled_data = transpile_policy_analysis(validated_data)

        # Add usage statistics
        if hasattr(response, "usage"):
            result["_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        # Generate output file paths
        normalized_path = Path(f"{base_path}_normalized_logic.json")
        transpiled_path = Path(f"{base_path}_logic.json")

        # Save normalized logic file
        normalized_result = result.copy()
        normalized_result["extracted_data"] = validated_data
        normalized_result["normalized_logic_json"] = str(normalized_path)
        normalized_result["transpiled_logic_json"] = str(transpiled_path)

        logger.info(f"Saving normalized logic to: {normalized_path}")
        with open(normalized_path, "w", encoding="utf-8") as f:
            json.dump(normalized_result, f, indent=2, ensure_ascii=False)

        # Save transpiled logic file
        transpiled_result = result.copy()
        transpiled_result["transpiled_data"] = transpiled_data
        transpiled_result["normalized_logic_json"] = str(normalized_path)
        transpiled_result["transpiled_logic_json"] = str(transpiled_path)

        logger.info(f"Saving transpiled logic to: {transpiled_path}")
        with open(transpiled_path, "w", encoding="utf-8") as f:
            json.dump(transpiled_result, f, indent=2, ensure_ascii=False)

        # Return result with file paths
        result["normalized_logic_json"] = str(normalized_path)
        result["transpiled_logic_json"] = str(transpiled_path)

        logger.info(f"Successfully extracted logic from {markdown_path}")
        logger.info(f"Outputs: {normalized_path}, {transpiled_path}")
        return result
