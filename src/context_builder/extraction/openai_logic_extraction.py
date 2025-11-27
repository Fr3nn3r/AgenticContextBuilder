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

        # Load and generate UDM context from schema (single render for efficiency)
        self._load_udm_context()

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

    def _load_udm_context(self):
        """Load static UDM context from standard claim schema and extract paths."""
        try:
            from context_builder.utils.schema_renderer import load_schema, render_udm_context
            from context_builder.utils.udm_bridge import extract_static_paths

            # Determine schema path (hardcoded to standard claim schema)
            # This is the contract between LLM and execution engine
            schema_file = Path(__file__).parent.parent / "schemas" / "standard_claim_schema.json"

            if not schema_file.exists():
                raise ConfigurationError(f"Standard claim schema not found: {schema_file}")

            # Load and render schema as static UDM context
            schema_dict = load_schema(str(schema_file))
            self.static_udm_md = render_udm_context(schema_dict)

            # Extract static paths for conflict validation
            self.static_udm_paths = extract_static_paths(schema_dict)

            logger.debug(f"Generated static UDM context from schema: {schema_file.name}")
            logger.debug(f"Static UDM size: {len(self.static_udm_md)} characters")
            logger.debug(f"Extracted {len(self.static_udm_paths)} static UDM paths")

        except Exception as e:
            raise ConfigurationError(f"Failed to load UDM context: {e}")

    def _generate_dynamic_udm_map(
        self,
        symbol_table_json: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate dynamic UDM map from symbol table explicit_variables.

        Creates lookup map keyed by lowercase variable name for symbol-based filtering.

        Args:
            symbol_table_json: Symbol table dict with extracted_data.explicit_variables

        Returns:
            Dict mapping lowercase variable name to variable data with UDM path
        """
        from context_builder.utils.udm_bridge import (
            build_dynamic_udm_map,
            generate_udm_path,
            validate_no_conflicts
        )

        # Extract explicit variables
        explicit_variables = symbol_table_json.get("extracted_data", {}).get("explicit_variables", [])

        if not explicit_variables:
            logger.warning("No explicit variables found in symbol table")
            return {}

        # Build dynamic UDM map
        udm_map = build_dynamic_udm_map(explicit_variables)

        # Validate no conflicts with static schema paths
        dynamic_paths = {var_data["udm_path"] for var_data in udm_map.values()}
        try:
            validate_no_conflicts(dynamic_paths, self.static_udm_paths)
        except ValueError as e:
            logger.error(f"Dynamic UDM conflict validation failed: {e}")
            raise ConfigurationError(str(e))

        logger.info(
            f"Generated {len(udm_map)} dynamic UDM variables "
            f"from {len(explicit_variables)} explicit variables"
        )

        return udm_map

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

    def _build_messages(
        self,
        markdown_content: str,
        dynamic_udm_md: str = "",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Build messages for OpenAI API call with composite UDM context.

        Args:
            markdown_content: Content of the markdown file
            dynamic_udm_md: Rendered dynamic UDM variables markdown (filtered per chunk)
            **kwargs: Additional template variables (e.g., symbol_table)

        Returns:
            List of message dictionaries for OpenAI API
        """
        # Build composite UDM context: static + dynamic
        composite_udm = self.static_udm_md
        if dynamic_udm_md:
            composite_udm = f"{self.static_udm_md}\n\n{dynamic_udm_md}"

        # Load prompt with composite UDM and other template kwargs
        prompt_data = load_prompt(self.prompt_name, udm_context=composite_udm, **kwargs)
        messages = prompt_data["messages"]

        # Add markdown content to user message
        # Find user message and append markdown content
        for msg in messages:
            if msg["role"] == "user":
                msg["content"] = f"{msg['content']}\n\n{markdown_content}"
                break

        return messages

    def _save_rendered_prompt(
        self,
        messages: List[Dict[str, Any]],
        chunk_file_path: Path,
        chunk_index: int
    ) -> None:
        """
        Save rendered prompt to file for debugging.

        Args:
            messages: Built messages list (system + user)
            chunk_file_path: Path to chunk text file
            chunk_index: Chunk index for filename
        """
        try:
            # Build output path: {base}_chunk_{num}_rendered_prompt.md
            # Example: policy_chunk_001.md -> policy_chunk_001_rendered_prompt.md
            prompt_path = chunk_file_path.with_name(
                chunk_file_path.stem + "_rendered_prompt.md"
            )

            # Format messages as readable markdown
            content_parts = [f"# Rendered Prompt for Chunk {chunk_index}\n"]

            for msg in messages:
                role = msg["role"].upper()
                content_parts.append(f"## {role} Message\n")
                content_parts.append(msg["content"])
                content_parts.append("\n")

            # Write to file
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(content_parts))

            logger.info(f"Saved rendered prompt to: {prompt_path.name}")

        except Exception as e:
            logger.warning(f"Failed to save rendered prompt for chunk {chunk_index}: {e}")

    def _save_chunk_result(
        self,
        validated_data: Dict[str, Any],
        chunk_file_path: Path,
        chunk_index: int
    ) -> None:
        """
        Save chunk extraction result to file for debugging.

        Args:
            validated_data: Validated PolicyAnalysis dict from chunk
            chunk_file_path: Path to chunk text file
            chunk_index: Chunk index for filename
        """
        try:
            # Build output path: {base}_chunk_{num}_normalized_logic.json
            # Example: policy_chunk_001.md -> policy_chunk_001_normalized_logic.json
            result_path = chunk_file_path.with_name(
                chunk_file_path.stem + "_normalized_logic.json"
            )

            # Write to file
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(validated_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved chunk result to: {result_path.name}")

        except Exception as e:
            logger.warning(f"Failed to save chunk result for chunk {chunk_index}: {e}")

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

    def _check_lazy_reader(self, response: Any) -> None:
        """
        Check if model produced suspiciously short output (lazy reading).

        Detects cases where the model fails to properly process the input
        by checking the completion/prompt token ratio. Logs error but continues
        processing to allow partial results.

        Args:
            response: OpenAI API response object with usage statistics
        """
        if not hasattr(response, "usage"):
            logger.warning("Response missing usage statistics, skipping lazy reader check")
            return

        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        if prompt_tokens == 0:
            logger.warning("Prompt tokens is 0, skipping lazy reader check")
            return

        ratio = completion_tokens / prompt_tokens

        logger.debug(
            f"Token ratio check: {completion_tokens} completion / {prompt_tokens} prompt = {ratio:.4f}"
        )

        # Threshold: 10% allows legitimate short responses while catching lazy reading (<1%)
        if ratio < 0.10:
            logger.error(
                f"LAZY READING DETECTED: Model produced suspiciously short output. "
                f"Token ratio: {ratio:.4f} ({completion_tokens}/{prompt_tokens}). "
                f"Expected ratio >= 0.10 for thorough processing. "
                f"Results may be incomplete or low quality."
            )

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
        total_chunks: int,
        chunk_file_path: Optional[Path] = None,
        dynamic_udm_md: str = ""
    ) -> Dict[str, Any]:
        """
        Process single chunk with its filtered symbols and dynamic UDM variables.

        Args:
            chunk_text: Text content of chunk
            chunk_symbol_md: Filtered symbol table markdown for this chunk
            chunk_index: Index of this chunk (1-based)
            total_chunks: Total number of chunks
            chunk_file_path: Optional path to chunk text file (for saving rendered prompt)
            dynamic_udm_md: Filtered dynamic UDM variables markdown for this chunk

        Returns:
            PolicyAnalysis dict (not saved to file)
        """
        logger.info(f"Processing chunk {chunk_index}/{total_chunks}")

        # Build messages with chunk content, filtered symbols, and composite UDM
        messages = self._build_messages(
            chunk_text,
            dynamic_udm_md=dynamic_udm_md,
            symbol_table=chunk_symbol_md
        )

        # Save rendered prompt for debugging (if chunk file path provided)
        if chunk_file_path:
            self._save_rendered_prompt(messages, chunk_file_path, chunk_index)

        # Call API
        response = self._call_api_with_retry(messages)

        # Check for lazy reading before parsing
        self._check_lazy_reader(response)

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

        # Save chunk result to file for debugging (if chunk file path provided)
        if chunk_file_path:
            self._save_chunk_result(validated_data, chunk_file_path, chunk_index)

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

        # Generate dynamic UDM map from symbol table
        dynamic_udm_map = self._generate_dynamic_udm_map(symbol_table_json)

        # Get encoder and count tokens
        encoder = get_token_encoder(self.model)

        # Load prompt with static UDM context to count system overhead accurately
        prompt_data = load_prompt(self.prompt_name, udm_context=self.static_udm_md)
        system_message = next((m["content"] for m in prompt_data["messages"] if m["role"] == "system"), "")
        system_tokens = count_tokens(system_message, encoder)

        # Count markdown tokens
        markdown_tokens = count_tokens(markdown_content, encoder)

        # Render full symbol table to count its tokens
        from context_builder.utils.symbol_table_renderer import render_symbol_context
        full_symbol_md = render_symbol_context(symbol_table_json['extracted_data'])
        symbol_tokens = count_tokens(full_symbol_md, encoder)

        # Reserve buffer for LLM response (complex policy logic can be large)
        RESPONSE_BUFFER = 2000
        MODEL_CONTEXT_LIMIT = 8000

        # Check if chunking needed
        total_input_tokens = system_tokens + markdown_tokens + symbol_tokens
        effective_limit = MODEL_CONTEXT_LIMIT - RESPONSE_BUFFER
        needs_chunking = total_input_tokens > effective_limit

        logger.info(
            f"Token counts - Markdown: {markdown_tokens}, "
            f"Symbols: {symbol_tokens}, "
            f"System (with UDM): {system_tokens}, "
            f"Total: {total_input_tokens}, "
            f"Limit: {effective_limit} (8000 - {RESPONSE_BUFFER} buffer)"
        )

        if needs_chunking:
            logger.info(f"Total {total_input_tokens} tokens exceeds {effective_limit} budget, enabling chunking")

        # Process with or without chunking
        if needs_chunking:
            # CHUNKING PATH
            logger.info("Chunking markdown with symbol filtering")

            # Chunk the markdown
            chunks = chunk_markdown_with_symbols(
                markdown_path=str(markdown_file),
                symbol_table_json=symbol_table_json,
                model_name=self.model,
                system_prompt_text=system_message
                # max_tokens uses default from chunking.MAX_TOKENS (4000)
            )

            # Save chunk files
            chunk_files = save_chunks(chunks, base_path)

            # Process each chunk with filtered dynamic UDM
            chunk_results = []
            for i, ((chunk_text, chunk_symbol_md, chunk_tokens, symbol_keys), (text_path, symbol_path)) in enumerate(zip(chunks, chunk_files), 1):
                try:
                    # Filter dynamic UDM variables based on symbols mentioned in chunk
                    chunk_dynamic_vars = [
                        dynamic_udm_map[key]["original_data"]
                        for key in symbol_keys
                        if key in dynamic_udm_map
                    ]

                    # Render filtered dynamic UDM
                    from context_builder.utils.udm_bridge import render_dynamic_udm
                    chunk_dynamic_udm_md = render_dynamic_udm(chunk_dynamic_vars)

                    chunk_result = self.process_chunk(
                        chunk_text=chunk_text,
                        chunk_symbol_md=chunk_symbol_md,
                        chunk_index=i,
                        total_chunks=len(chunks),
                        chunk_file_path=text_path,
                        dynamic_udm_md=chunk_dynamic_udm_md
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

            # Render all dynamic UDM variables (no filtering needed)
            from context_builder.utils.udm_bridge import render_dynamic_udm
            all_dynamic_vars = [
                var_data["original_data"]
                for var_data in dynamic_udm_map.values()
            ]
            full_dynamic_udm_md = render_dynamic_udm(all_dynamic_vars)

            # Build messages with full symbol table and composite UDM context
            messages = self._build_messages(
                markdown_content,
                dynamic_udm_md=full_dynamic_udm_md,
                symbol_table=full_symbol_md
            )

            # Call API with retry logic
            response = self._call_api_with_retry(messages)

            # Check for lazy reading before parsing
            self._check_lazy_reader(response)

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

        # Run audit on extracted logic
        try:
            from context_builder.extraction.logic_auditor import LogicAuditor

            logger.info("Running semantic audit on extracted logic...")
            auditor = LogicAuditor()  # Auto-detects schema path
            auditor.audit_files([str(normalized_path)])

            # Generate report in same directory as output files
            report_path = normalized_path.parent / "semantic_audit_report.txt"
            auditor.generate_report(str(report_path))

            # Add audit summary to result
            audit_summary = auditor.get_summary()
            result["_audit_summary"] = audit_summary
            result["_audit_report"] = str(report_path)

            logger.info(f"Audit complete: {report_path}")

        except Exception as e:
            logger.warning(f"Audit failed (non-fatal): {e}")
            # Audit failure is non-blocking

        return result
