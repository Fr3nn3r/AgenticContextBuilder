"""Policy Logic Refiner - Fixes errors in extracted rules based on linter feedback.

This service takes rules that failed validation and attempts to fix them using
OpenAI API with structured outputs, guided by linter error messages.

Follows the "Schemas in Python, Prompts in Markdown" pattern:
- Schema: PolicyAnalysis Pydantic model (same as extraction)
- Prompt: policy_logic_refiner.md
- Runner: This class orchestrates the refinement API calls
"""

import copy
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from context_builder.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class RefinementError(Exception):
    """Base exception for refinement errors."""
    pass


class APIError(RefinementError):
    """Exception raised for API-related errors."""
    pass


class ConfigurationError(RefinementError):
    """Exception raised for configuration errors."""
    pass


class PolicyLogicRefiner:
    """
    OpenAI API implementation for fixing policy logic errors.

    Takes failed rules + linter error report, attempts to fix them using
    the policy_logic_refiner.md prompt, and returns corrected rules.

    Follows same pattern as OpenAILogicExtraction for consistency (DRY).
    """

    def __init__(
        self,
        prompt_path: Optional[str] = None,
        schema_path: Optional[str] = None
    ):
        """
        Initialize Policy Logic Refiner.

        Args:
            prompt_path: Absolute path to prompt markdown file.
                        Defaults to policy_logic_refiner.md in prompts/ directory.
            schema_path: Absolute path to schema Python file.
                        Defaults to policy_logic_extraction.py (same schema as extractor).
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
            logger.debug("OpenAI client initialized successfully (Refiner)")
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

        # Load schema (reuse PolicyAnalysis from extraction)
        self._load_schema()

        logger.debug(
            f"Refiner using model: {self.model}, max_tokens: {self.max_tokens}, "
            f"temperature: {self.temperature}"
        )

    def _load_prompt_config(self):
        """Load prompt configuration from markdown file."""
        try:
            if self.prompt_path:
                # Load from absolute path
                self.prompt_name = Path(self.prompt_path).stem
                prompt_data = load_prompt(self.prompt_name)
            else:
                # Load default prompt
                self.prompt_name = "policy_logic_refiner"
                prompt_data = load_prompt(self.prompt_name)

            self.prompt_config = prompt_data["config"]
            logger.debug(f"Loaded refiner prompt: {self.prompt_config.get('name', 'unnamed')}")

            # Extract configuration from prompt file
            self.model = self.prompt_config.get("model", "gpt-4o")
            self.max_tokens = self.prompt_config.get("max_tokens", 16000)
            self.temperature = self.prompt_config.get("temperature", 0.0)

        except Exception as e:
            raise ConfigurationError(f"Failed to load refiner prompt configuration: {e}")

    def _load_schema(self):
        """Load Pydantic schema from Python file (reuse extraction schema)."""
        try:
            if self.schema_path:
                # Load from absolute path
                # For now, use default schema from schemas directory
                from context_builder.schemas.policy_logic_extraction import (
                    PolicyAnalysis,
                )
            else:
                # Load default schema (same as extractor)
                from context_builder.schemas.policy_logic_extraction import (
                    PolicyAnalysis,
                )

            self.schema_class = PolicyAnalysis
            logger.debug(f"Loaded refiner schema: {self.schema_class.__name__}")

        except ImportError as e:
            raise ConfigurationError(f"Failed to import refiner schema: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load refiner schema: {e}")

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

    def _sanitize_null_in_logic(self, logic: Any) -> Any:
        """
        Recursively sanitize null values in JSON Logic tree.

        Replaces null values with placeholder to help LLM understand what to fix:
        - null in 'in' operator arguments → ["__REWRITE_WITH_OR_LOGIC__"]
        - null items inside arrays → "__REWRITE_WITH_OR_LOGIC__"

        Args:
            logic: JSON Logic node (dict, list, or scalar)

        Returns:
            Sanitized copy of logic tree (original unchanged)
        """
        # Handle None/null values
        if logic is None:
            # If null is standalone, replace with placeholder array
            # (most common case: 'in' operator second argument)
            return ["__REWRITE_WITH_OR_LOGIC__"]

        # Handle dict nodes (operators)
        if isinstance(logic, dict):
            sanitized = {}
            for key, value in logic.items():
                # Recursively sanitize all values
                sanitized[key] = self._sanitize_null_in_logic(value)
            return sanitized

        # Handle list nodes (argument arrays)
        if isinstance(logic, list):
            sanitized = []
            for item in logic:
                if item is None:
                    # Replace null items in arrays with string placeholder
                    sanitized.append("__REWRITE_WITH_OR_LOGIC__")
                else:
                    # Recursively sanitize non-null items
                    sanitized.append(self._sanitize_null_in_logic(item))
            return sanitized

        # Handle scalar values (strings, numbers, booleans)
        # Return as-is (no sanitization needed)
        return logic

    def _format_linter_errors(self, failed_rules: List[Dict[str, Any]], violations: List[Dict[str, Any]]) -> str:
        """
        Format linter errors into human-readable report for refiner prompt.

        Args:
            failed_rules: List of rule dicts that failed validation
            violations: List of violation dicts from linter report

        Returns:
            Formatted error report string
        """
        lines = []

        # Group violations by rule_id
        violations_by_rule = {}
        for v in violations:
            rule_id = v.get("rule_id", "unknown")
            if rule_id not in violations_by_rule:
                violations_by_rule[rule_id] = []
            violations_by_rule[rule_id].append(v)

        # Format each failed rule with its errors
        for rule in failed_rules:
            rule_id = rule.get("id", "unknown")
            rule_name = rule.get("name", "unknown")
            source_ref = rule.get("source_ref", "N/A")
            logic = rule.get("logic", {})

            # Sanitize logic to replace null values with placeholders
            # (Don't modify original - work on deep copy)
            sanitized_logic = self._sanitize_null_in_logic(copy.deepcopy(logic))

            lines.append(f"### Rule: {rule_id}")
            lines.append(f"**Name:** {rule_name}")
            lines.append(f"**Source Reference:** {source_ref}")
            lines.append(f"**Current Logic:** `{json.dumps(sanitized_logic)}`")
            lines.append("")

            # Add violations for this rule
            if rule_id in violations_by_rule:
                lines.append("**Errors:**")
                for v in violations_by_rule[rule_id]:
                    error_type = v.get("type", "UNKNOWN")
                    severity = v.get("severity", "UNKNOWN")
                    message = v.get("message", "No message")
                    location = v.get("location", "unknown")

                    lines.append(f"- [{severity}] **{error_type}** at `{location}`: {message}")

                    # Add specific details if available
                    if v.get("variable"):
                        lines.append(f"  - Variable: `{v['variable']}`")
                    if v.get("invalid_value") is not None:
                        lines.append(f"  - Invalid value: `{v['invalid_value']}`")
                    if v.get("operator"):
                        lines.append(f"  - Operator: `{v['operator']}`")
                lines.append("")

        return "\n".join(lines)

    def _build_messages(
        self,
        failed_rules: List[Dict[str, Any]],
        violations: List[Dict[str, Any]],
        symbol_context: str,
        udm_context: str
    ) -> List[Dict[str, Any]]:
        """
        Build messages for OpenAI API call with refiner context.

        Args:
            failed_rules: List of rule dicts that failed validation
            violations: List of violation dicts from linter
            symbol_context: Filtered symbol table markdown
            udm_context: Static UDM schema markdown

        Returns:
            List of message dictionaries for OpenAI API
        """
        # Format linter errors
        linter_error_report = self._format_linter_errors(failed_rules, violations)

        # Load prompt with template variables
        prompt_data = load_prompt(
            self.prompt_name,
            udm_context=udm_context,
            symbol_context=symbol_context,
            linter_error_report=linter_error_report
        )
        messages = prompt_data["messages"]

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
            logger.error(f"Failed to parse JSON response from refiner: {e}")
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
            logger.error(f"Refiner schema validation failed: {e}")
            raise APIError(f"Refiner schema validation failed: {e}")

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
                    f"Refiner API call failed (attempt {attempt + 1}/{self.retries}): {e}. "
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
                    raise APIError(f"Refiner API call failed after {self.retries} retries: {e}")

    def _save_rendered_prompt(
        self,
        messages: List[Dict[str, Any]],
        chunk_file_path: Path,
        chunk_index: int,
        attempt: int
    ) -> None:
        """
        Save rendered refinement prompt to file for debugging.

        Args:
            messages: Built messages list (system + user)
            chunk_file_path: Path to chunk text file
            chunk_index: Chunk index for filename
            attempt: Refinement attempt number (1-based)
        """
        try:
            # Build output path: {base}_chunk_{num}_refinement_attempt_{attempt}_prompt.md
            # Example: policy_chunk_001.md -> policy_chunk_001_refinement_attempt_1_prompt.md
            prompt_path = chunk_file_path.with_name(
                chunk_file_path.stem + f"_refinement_attempt_{attempt}_prompt.md"
            )

            # Format messages as readable markdown
            content_parts = [f"# Refinement Prompt for Chunk {chunk_index} (Attempt {attempt})\n"]

            for msg in messages:
                role = msg["role"].upper()
                content_parts.append(f"## {role} Message\n")
                content_parts.append(msg["content"])
                content_parts.append("\n")

            # Write to file
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(content_parts))

            logger.info(f"Saved refinement prompt to: {prompt_path.name}")

        except Exception as e:
            logger.warning(f"Failed to save refinement prompt for chunk {chunk_index} attempt {attempt}: {e}")

    def _save_refinement_result(
        self,
        validated_data: Dict[str, Any],
        chunk_file_path: Path,
        chunk_index: int,
        attempt: int
    ) -> None:
        """
        Save refinement result to file for debugging.

        Args:
            validated_data: Validated PolicyAnalysis dict from refiner
            chunk_file_path: Path to chunk text file
            chunk_index: Chunk index for filename
            attempt: Refinement attempt number (1-based)
        """
        try:
            # Build output path: {base}_chunk_{num}_refinement_attempt_{attempt}_output.json
            # Example: policy_chunk_001.md -> policy_chunk_001_refinement_attempt_1_output.json
            result_path = chunk_file_path.with_name(
                chunk_file_path.stem + f"_refinement_attempt_{attempt}_output.json"
            )

            # Write to file
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(validated_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved refinement result to: {result_path.name}")

        except Exception as e:
            logger.warning(f"Failed to save refinement result for chunk {chunk_index} attempt {attempt}: {e}")

    def refine_rules(
        self,
        failed_rules: List[Dict[str, Any]],
        violations: List[Dict[str, Any]],
        chunk_symbol_md: str,
        udm_context: str,
        chunk_file_path: Optional[Path] = None,
        chunk_index: int = 0,
        attempt: int = 1
    ) -> Dict[str, Any]:
        """
        Attempt to fix failed rules using OpenAI API.

        Args:
            failed_rules: List of rule dicts that failed validation
            violations: List of violation dicts from linter report
            chunk_symbol_md: Filtered symbol table markdown for this chunk
            udm_context: Static UDM schema markdown
            chunk_file_path: Optional path to chunk text file (for saving debug outputs)
            chunk_index: Chunk index for filename (for saving debug outputs)
            attempt: Refinement attempt number (1-based, for saving debug outputs)

        Returns:
            PolicyAnalysis dict containing ONLY the fixed rules

        Raises:
            APIError: If API call fails
            RefinementError: If refinement cannot be completed
        """
        logger.info(f"Refining {len(failed_rules)} failed rules (attempt {attempt})...")

        # Build messages with error context
        messages = self._build_messages(
            failed_rules=failed_rules,
            violations=violations,
            symbol_context=chunk_symbol_md,
            udm_context=udm_context
        )

        # Save rendered prompt for debugging (if chunk file path provided)
        if chunk_file_path:
            self._save_rendered_prompt(messages, chunk_file_path, chunk_index, attempt)

        # Call API
        response = self._call_api_with_retry(messages)

        # Parse and validate
        parsed_data = self._parse_response(response.choices[0].message.content)
        validated_data = self._validate_with_schema(parsed_data)

        # Add usage statistics
        if hasattr(response, "usage"):
            validated_data["_refinement_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        # Save refinement result for debugging (if chunk file path provided)
        if chunk_file_path:
            self._save_refinement_result(validated_data, chunk_file_path, chunk_index, attempt)

        logger.info(f"Refinement complete. Received {len(validated_data.get('rules', []))} fixed rules.")

        return validated_data
