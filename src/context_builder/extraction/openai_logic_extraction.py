"""OpenAI API implementation for policy logic extraction with normalized schema.

This implementation uses the normalized recursive LogicNode schema to prevent
hallucinated operators while still producing standard JSON Logic output via
transpilation.

Supports automatic chunking for large documents with dynamic symbol filtering.
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
from context_builder.extraction.chunking import (
    chunk_markdown_with_symbols,
    save_chunks,
    count_tokens,
    get_token_encoder
)

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

    def process_chunk(
        self,
        chunk_text: str,
        chunk_symbol_md: str,
        chunk_index: int,
        total_chunks: int
    ) -> Dict[str, Any]:
        """
        Process single chunk with its filtered symbols.

        Args:
            chunk_text: Text content of chunk
            chunk_symbol_md: Filtered symbol table markdown for this chunk
            chunk_index: Index of this chunk (1-based)
            total_chunks: Total number of chunks

        Returns:
            PolicyAnalysis dict (not saved to file)
        """
        logger.info(f"Processing chunk {chunk_index}/{total_chunks}")

        # Build messages with chunk content and filtered symbols
        messages = self._build_messages(chunk_text, symbol_table=chunk_symbol_md)

        # Call API
        response = self._call_api_with_retry(messages)

        # Parse and validate
        parsed_data = self._parse_response(response.choices[0].message.content)
        validated_data = self._validate_with_schema(parsed_data)

        # Add usage statistics
        if hasattr(response, "usage"):
            validated_data["_chunk_usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        validated_data["_chunk_index"] = chunk_index
        return validated_data

    def consolidate_chunk_results(
        self,
        chunk_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Consolidate multiple PolicyAnalysis results from chunks.

        Merges rules arrays, discards individual chain_of_thought fields.

        Args:
            chunk_results: List of PolicyAnalysis dicts from each chunk

        Returns:
            Consolidated PolicyAnalysis dict
        """
        logger.info(f"Consolidating {len(chunk_results)} chunk results")

        # Collect all rules
        all_rules = []
        total_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }

        for chunk_data in chunk_results:
            # Extract rules
            if "rules" in chunk_data:
                all_rules.extend(chunk_data["rules"])

            # Accumulate usage stats
            if "_chunk_usage" in chunk_data:
                usage = chunk_data["_chunk_usage"]
                total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
                total_usage["total_tokens"] += usage.get("total_tokens", 0)

        logger.info(f"Consolidated {len(all_rules)} rules from {len(chunk_results)} chunks")

        # Build consolidated result
        consolidated = {
            "rules": all_rules,
            "_consolidated_from": [f"chunk_{i+1:03d}" for i in range(len(chunk_results))],
            "_total_rules": len(all_rules),
            "_total_chunks": len(chunk_results),
            "_usage": total_usage
        }

        return consolidated

    def process(
        self,
        markdown_path: str,
        output_base_path: str,
        symbol_table_json_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process markdown file and extract policy logic.

        Automatically chunks large files with symbol filtering if symbol table provided.

        Generates two output files:
        - {output_base_path}_normalized_logic.json: LLM output with normalized format
        - {output_base_path}_logic.json: Transpiled standard JSON Logic format

        Args:
            markdown_path: Path to markdown file to process
            output_base_path: Base path for output files (without extension)
            symbol_table_json_path: Optional path to symbol table JSON for chunking
            **kwargs: Additional template variables (deprecated, use symbol_table_json_path)

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

        # Auto-detect symbol table if not provided
        if not symbol_table_json_path:
            # Try to find symbol table JSON based on markdown filename
            # Expected pattern: {input_name}_symbol_table.json
            potential_symbol_path = markdown_file.with_name(
                f"{markdown_file.stem}_symbol_table.json"
            )
            if potential_symbol_path.exists():
                symbol_table_json_path = str(potential_symbol_path)
                logger.info(f"Auto-detected symbol table: {symbol_table_json_path}")
            else:
                raise FileNotFoundError(
                    f"Symbol table not found: {potential_symbol_path}. "
                    f"Please run symbol extraction first with: "
                    f"extract {markdown_path} -o <output_dir>"
                )

        # Load symbol table
        with open(symbol_table_json_path, 'r', encoding='utf-8') as f:
            symbol_table_json = json.load(f)

        # Get encoder and count tokens
        encoder = get_token_encoder(self.model)

        # Load prompt to count system overhead
        prompt_data = load_prompt(self.prompt_name)
        system_message = next((m["content"] for m in prompt_data["messages"] if m["role"] == "system"), "")
        system_tokens = count_tokens(system_message, encoder)

        # Count markdown tokens
        markdown_tokens = count_tokens(markdown_content, encoder)

        # Render full symbol table to count its tokens
        from context_builder.utils.symbol_table_renderer import render_symbol_context
        full_symbol_md = render_symbol_context(symbol_table_json['extracted_data'])
        symbol_tokens = count_tokens(full_symbol_md, encoder)

        # Check if chunking needed (8000 token target)
        total_tokens = system_tokens + markdown_tokens + symbol_tokens
        needs_chunking = total_tokens > 8000

        logger.info(
            f"Token counts - Markdown: {markdown_tokens}, "
            f"Symbols: {symbol_tokens}, "
            f"System: {system_tokens}, "
            f"Total: {total_tokens}"
        )

        if needs_chunking:
            logger.info(f"Total {total_tokens} tokens exceeds 8000 budget, enabling chunking")

        # Process with or without chunking
        if needs_chunking:
            # CHUNKING PATH
            logger.info("Chunking markdown with symbol filtering")

            # Chunk the markdown
            chunks = chunk_markdown_with_symbols(
                markdown_path=str(markdown_file),
                symbol_table_json=symbol_table_json,
                model_name=self.model,
                system_prompt_text=system_message,
                max_tokens=8000
            )

            # Save chunk files
            chunk_files = save_chunks(chunks, base_path)

            # Process each chunk
            chunk_results = []
            for i, ((chunk_text, chunk_symbol_md, chunk_tokens), (text_path, symbol_path)) in enumerate(zip(chunks, chunk_files), 1):
                try:
                    chunk_result = self.process_chunk(
                        chunk_text=chunk_text,
                        chunk_symbol_md=chunk_symbol_md,
                        chunk_index=i,
                        total_chunks=len(chunks)
                    )
                    chunk_results.append(chunk_result)
                except Exception as e:
                    logger.error(f"Failed to process chunk {i}/{len(chunks)}: {e}")
                    # Continue with remaining chunks

            # Consolidate results
            validated_data = self.consolidate_chunk_results(chunk_results)

            # Add chunking metadata
            result["_chunked"] = True
            result["_chunk_count"] = len(chunks)
            result["_chunks_dir"] = str(base_path.parent / f"{base_path.name}_chunks")

        else:
            # NORMAL PATH (no chunking)
            logger.info("Processing without chunking")

            # Build messages with full symbol table
            messages = self._build_messages(markdown_content, symbol_table=full_symbol_md)

            # Call API with retry logic
            response = self._call_api_with_retry(messages)

            # Parse and validate response
            parsed_data = self._parse_response(response.choices[0].message.content)
            validated_data = self._validate_with_schema(parsed_data)

            # Add usage statistics
            if hasattr(response, "usage"):
                validated_data["_usage"] = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }

            result["_chunked"] = False

        # Transpile to standard JSON Logic
        transpiled_data = transpile_policy_analysis(validated_data)

        # Copy usage stats to result
        if "_usage" in validated_data:
            result["_usage"] = validated_data["_usage"]

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
