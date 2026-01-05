"""OpenAI API implementation for document classification."""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

from pydantic import ValidationError

from context_builder.classification import (
    DocumentClassifier,
    ClassifierFactory,
    APIError,
    ConfigurationError,
)
from context_builder.utils.prompt_loader import load_prompt
from context_builder.schemas.document_classification import DocumentClassification

logger = logging.getLogger(__name__)


class OpenAIDocumentClassifier(DocumentClassifier):
    """
    OpenAI API implementation for document classification.

    This implementation follows the "Schemas in Python, Prompts in Markdown" pattern:
    - Schema: DocumentClassification Pydantic model defines output structure
    - Prompt: Configurable .md file defines instructions and configuration
    - Runner: This class orchestrates the API calls

    Uses json_object mode to allow flexible key_information structures based
    on document type.
    """

    def __init__(self, prompt_name: str = "claims_document_classification"):
        """
        Initialize OpenAI document classifier.

        Args:
            prompt_name: Name of prompt file in prompts/ directory (without .md)
        """
        super().__init__()

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

            self.timeout = 60  # seconds
            self.retries = 3

            self.client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,  # We handle retries ourselves
            )
            logger.debug("OpenAI client initialized successfully")
        except ImportError:
            raise ConfigurationError(
                "OpenAI package not installed. "
                "Please install it with: pip install openai"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize OpenAI client: {e}")

        # Load prompt configuration
        self.prompt_name = prompt_name
        self._load_prompt_config()

        logger.debug(
            f"Classifier initialized: model={self.model}, "
            f"max_tokens={self.max_tokens}, prompt={self.prompt_name}"
        )

    def _load_prompt_config(self):
        """Load prompt configuration from markdown file."""
        try:
            prompt_data = load_prompt(self.prompt_name)
            self.prompt_config = prompt_data["config"]
            logger.debug(f"Loaded prompt: {self.prompt_config.get('name', 'unnamed')}")

            # Extract configuration
            self.model = self.prompt_config.get("model", "gpt-4o")
            self.max_tokens = self.prompt_config.get("max_tokens", 2048)
            self.temperature = self.prompt_config.get("temperature", 0.2)

        except Exception as e:
            raise ConfigurationError(f"Failed to load prompt configuration: {e}")

    def _build_messages(
        self, text_content: str, filename: str
    ) -> list:
        """Build messages for API call using prompt template."""
        # Load and render prompt with variables
        prompt_data = load_prompt(
            self.prompt_name,
            text_content=text_content,
            filename=filename,
        )
        return prompt_data["messages"]

    def _call_api_with_retry(self, messages: list) -> Dict[str, Any]:
        """
        Call OpenAI API with retry logic for transient failures.

        Args:
            messages: List of message dicts for the API

        Returns:
            Parsed JSON response

        Raises:
            APIError: If all retries fail
        """
        last_error = None

        for attempt in range(self.retries):
            try:
                logger.debug(f"API call attempt {attempt + 1}/{self.retries}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )

                # Extract and parse response
                content = response.choices[0].message.content
                if not content:
                    raise APIError("Empty response from API")

                result = json.loads(content)

                # Log usage for cost tracking
                if response.usage:
                    logger.debug(
                        f"API usage: {response.usage.prompt_tokens} prompt + "
                        f"{response.usage.completion_tokens} completion = "
                        f"{response.usage.total_tokens} total tokens"
                    )

                return result

            except json.JSONDecodeError as e:
                last_error = APIError(f"Failed to parse JSON response: {e}")
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")

            except Exception as e:
                last_error = APIError(f"API call failed: {e}")
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

            # Exponential backoff before retry
            if attempt < self.retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        raise last_error

    def _validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate API response against schema.

        Args:
            response: Raw API response dict

        Returns:
            Validated response dict

        Raises:
            ClassificationError: If validation fails
        """
        try:
            # Validate with Pydantic
            validated = DocumentClassification.model_validate(response)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning(f"Schema validation failed: {e}")
            # Return response as-is if it has required fields
            if "document_type" in response and "summary" in response:
                return response
            raise

    def _classify_implementation(
        self, text_content: str, filename: str = ""
    ) -> Dict[str, Any]:
        """
        Implementation-specific classification logic.

        Args:
            text_content: Extracted text from document
            filename: Original filename (hint for classification)

        Returns:
            Dict with document_type, language, summary, key_information
        """
        # Build messages from prompt template
        messages = self._build_messages(text_content, filename)

        # Call API with retry
        response = self._call_api_with_retry(messages)

        # Validate and return
        return self._validate_response(response)


# Auto-register with factory
ClassifierFactory.register("openai", OpenAIDocumentClassifier)
