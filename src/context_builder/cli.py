#!/usr/bin/env python3
"""Command-line interface for document context extraction."""

import argparse
import json
import logging
import shutil
import signal
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import colorlog
from dotenv import load_dotenv
from rich.console import Console
from tqdm import tqdm

from context_builder.ingestion import (
    IngestionFactory,
    IngestionError,
    DataIngestion,
)

# Import pipeline components for the new pipeline command
from context_builder.pipeline.discovery import discover_claims
from context_builder.pipeline.run import process_claim, StageConfig
from context_builder.pipeline.paths import create_workspace_run_structure, get_claim_paths
from context_builder.extraction.base import generate_run_id
from context_builder.schemas.run_errors import PipelineStage

# Ensure Azure DI implementation is imported so it auto-registers
try:
    from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
except ImportError:
    pass  # Azure DI dependencies not installed


# Configure colored logging
def setup_colored_logging(verbose: bool = False):
    """Set up colored logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    # Create colored formatter
    formatter = colorlog.ColoredFormatter(
        "%(asctime)s - %(log_color)s%(levelname)s%(reset)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    # Configure root logger
    handler = colorlog.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()  # Remove existing handlers
    root_logger.addHandler(handler)

    # Filter out noisy OpenAI logs
    openai_logger = logging.getLogger("openai._base_client")
    openai_logger.setLevel(logging.WARNING)  # Only show warnings and errors

    # Also filter out other noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def parse_stages(stages_str: str) -> list[PipelineStage]:
    """
    Parse comma-separated stages string into PipelineStage list.

    Args:
        stages_str: Comma-separated stages (e.g., "ingest,classify,extract")

    Returns:
        List of PipelineStage enums

    Raises:
        ValueError: If invalid stage name provided
    """
    valid_stages = {s.value for s in PipelineStage}
    stages = []

    for s in stages_str.split(","):
        s = s.strip().lower()
        if s not in valid_stages:
            raise ValueError(
                f"Invalid stage '{s}'. Valid stages: {', '.join(valid_stages)}"
            )
        stages.append(PipelineStage(s))

    return stages


# Set up basic logging initially
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\n[!] Process interrupted by user. Exiting gracefully...")
    sys.exit(0)


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)


def setup_argparser() -> argparse.ArgumentParser:
    """Set up command-line argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Extract structured context and data from documents using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    # ========== ACQUIRE SUBCOMMAND (DEPRECATED) ==========
    acquire_parser = subparsers.add_parser(
        "acquire",
        help="[DEPRECATED] Acquire document content using vision APIs - use 'pipeline' instead",
        epilog="""
*** DEPRECATED: This command creates flat files. Use 'pipeline' for the new
    structured output with runs, manifests, and metrics. ***

Examples:
  %(prog)s document.pdf                    # Process a single PDF
  %(prog)s folder/ -r                      # Process all files in folder recursively
  %(prog)s file.pdf -o results/           # Save results to specific directory
  %(prog)s doc.pdf --model gpt-4o         # Use specific model
  %(prog)s folder/ -r --max-pages 10       # Limit pages per document
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments for acquire
    acquire_parser.add_argument(
        "input_path", metavar="PATH", help="Path to the file or folder to process"
    )

    # Output options for acquire
    output_group = acquire_parser.add_argument_group("Output Options")
    output_group.add_argument(
        "-o",
        "--output-dir",
        metavar="DIR",
        default=".",
        help="Output directory for JSON results (default: current directory)",
    )
    output_group.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Process folder recursively (when input is a folder)",
    )

    # Provider options for acquire
    provider_group = acquire_parser.add_argument_group("Provider Options")
    available_providers = [
        "openai",
        "tesseract",
        "azure-di",
    ]  # Default list, will be extended if more are registered
    provider_group.add_argument(
        "-p",
        "--provider",
        choices=available_providers,
        default="tesseract",
        help="""Data ingestion provider (default: tesseract)
        - openai: OpenAI Vision API (structured JSON with LLM analysis)
          Requires: OPENAI_API_KEY in .env
        - tesseract: Local OCR with Tesseract (text extraction)
          Requires: tesseract binary installed
        - azure-di: Azure Document Intelligence (full JSON + optional markdown)
          Requires: AZURE_DI_ENDPOINT and AZURE_DI_API_KEY in .env
          Output: JSON with raw_azure_di_output + optional .md file
        """,
    )
    provider_group.add_argument(
        "--save-markdown",
        action="store_true",
        default=True,
        help="Save markdown file alongside JSON (azure-di only, default: True)",
    )
    provider_group.add_argument(
        "--no-save-markdown",
        action="store_true",
        help="Disable saving markdown file (azure-di only)",
    )

    # Model configuration for acquire
    model_group = acquire_parser.add_argument_group("Model Configuration")
    model_group.add_argument(
        "--model", metavar="MODEL", help="Model name to use (e.g., 'gpt-4o' for OpenAI)"
    )
    model_group.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        help="Maximum tokens for response (default: provider-specific)",
    )
    model_group.add_argument(
        "--temperature",
        type=float,
        metavar="FLOAT",
        help="Temperature for response generation (0.0-2.0, default: provider-specific)",
    )

    # PDF processing options for acquire
    pdf_group = acquire_parser.add_argument_group("PDF Processing")
    pdf_group.add_argument(
        "--max-pages",
        type=int,
        metavar="N",
        help="Maximum pages to process from PDFs (default: 20)",
    )
    pdf_group.add_argument(
        "--render-scale",
        type=float,
        metavar="FLOAT",
        help="Render scale for PDF to image conversion (default: 2.0)",
    )

    # API options for acquire
    api_group = acquire_parser.add_argument_group("API Options")
    api_group.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        help="API request timeout in seconds (default: 120)",
    )
    api_group.add_argument(
        "--retries",
        type=int,
        metavar="N",
        help="Maximum number of retries for API calls (default: 3)",
    )

    # Logging options for acquire
    logging_group = acquire_parser.add_argument_group("Logging Options")
    logging_group.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    logging_group.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )
    logging_group.add_argument(
        "--rich-output",
        action="store_true",
        help="Display results in rich format to stdout only (no files saved, all logs suppressed, incompatible with -v)",
    )

    # Run control options for acquire
    run_control_group = acquire_parser.add_argument_group("Run Control")
    run_control_group.add_argument(
        "--run-id",
        metavar="ID",
        help="Override run ID (default: auto-generated timestamp_gitsha)",
    )
    run_control_group.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing run folder if it exists",
    )
    run_control_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Discovery only - show what would be processed without actually running",
    )
    run_control_group.add_argument(
        "--no-metrics",
        action="store_true",
        help="Skip metrics computation at end of run",
    )

    # ========== EXTRACT SUBCOMMAND (DEPRECATED) ==========
    extract_parser = subparsers.add_parser(
        "extract",
        help="[DEPRECATED] Extract structured data from markdown files using AI",
        epilog="""
*** DEPRECATED: Use 'pipeline' command for document extraction. ***

Examples:
  %(prog)s input.md -o output.json                          # Extract from markdown
  %(prog)s doc.md -o result.json --prompt custom_prompt.md  # Use custom prompt
  %(prog)s input.md -o out.json --model gpt-4o-mini         # Use different model
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments for extract
    extract_parser.add_argument(
        "input_path",
        metavar="INPUT",
        help="Path to markdown file to extract from"
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        required=True,
        help="Path to output JSON file"
    )

    # Prompt and schema options for extract
    extract_config_group = extract_parser.add_argument_group("Extraction Configuration")
    extract_config_group.add_argument(
        "--prompt",
        metavar="PATH",
        help="Absolute path to custom prompt markdown file (default: policy_symbol_extraction.md)"
    )
    extract_config_group.add_argument(
        "--schema",
        metavar="PATH",
        help="Absolute path to custom schema Python file (default: policy_symbol_extraction.py)"
    )

    # Model configuration for extract
    extract_model_group = extract_parser.add_argument_group("Model Configuration")
    extract_model_group.add_argument(
        "--model",
        metavar="MODEL",
        help="Model name to use (default: from prompt config, typically gpt-4o)"
    )
    extract_model_group.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        help="Maximum tokens for response (default: from prompt config)"
    )
    extract_model_group.add_argument(
        "--temperature",
        type=float,
        metavar="FLOAT",
        help="Temperature for response generation (default: from prompt config)"
    )
    extract_model_group.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        help="API request timeout in seconds (default: 120)"
    )
    extract_model_group.add_argument(
        "--retries",
        type=int,
        metavar="N",
        help="Maximum number of retries for API calls (default: 3)"
    )

    # Logging options for extract
    extract_logging_group = extract_parser.add_argument_group("Logging Options")
    extract_logging_group.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    extract_logging_group.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )

    # ========== EXTRACT_LOGIC SUBCOMMAND (DEPRECATED) ==========
    extract_logic_parser = subparsers.add_parser(
        "extract_logic",
        help="[DEPRECATED] Extract policy logic as normalized JSON Logic from markdown files",
        epilog="""
*** DEPRECATED: This command is for policy logic extraction only. ***

Examples:
  %(prog)s input.md -o output/                             # Extract to directory (generates two files)
  %(prog)s doc.md -o result --symbol-table symbols.json    # Include symbol table
  %(prog)s input.md -o custom_name                         # Custom base name for outputs
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments for extract_logic
    extract_logic_parser.add_argument(
        "input_path",
        metavar="INPUT",
        help="Path to markdown file to extract logic from"
    )
    extract_logic_parser.add_argument(
        "-o",
        "--output",
        metavar="OUTPUT",
        required=True,
        help="Path to output JSON file"
    )

    # Logic extraction options
    extract_logic_config_group = extract_logic_parser.add_argument_group("Logic Extraction Configuration")
    extract_logic_config_group.add_argument(
        "--symbol-table",
        metavar="PATH",
        help="Path to symbol table JSON file (optional - auto-detects {input_name}_symbol_table.json if not provided)"
    )
    extract_logic_config_group.add_argument(
        "--prompt",
        metavar="PATH",
        help="Absolute path to custom prompt markdown file (default: policy_logic_extraction.md)"
    )
    extract_logic_config_group.add_argument(
        "--schema",
        metavar="PATH",
        help="Absolute path to custom schema Python file (default: policy_logic_extraction.py)"
    )

    # Model configuration for extract_logic
    extract_logic_model_group = extract_logic_parser.add_argument_group("Model Configuration")
    extract_logic_model_group.add_argument(
        "--model",
        metavar="MODEL",
        help="Model name to use (default: from prompt config, typically gpt-4o)"
    )
    extract_logic_model_group.add_argument(
        "--max-tokens",
        type=int,
        metavar="N",
        help="Maximum tokens for response (default: from prompt config)"
    )
    extract_logic_model_group.add_argument(
        "--temperature",
        type=float,
        metavar="FLOAT",
        help="Temperature for response generation (default: from prompt config)"
    )
    extract_logic_model_group.add_argument(
        "--timeout",
        type=int,
        metavar="SECONDS",
        help="API request timeout in seconds (default: 120)"
    )
    extract_logic_model_group.add_argument(
        "--retries",
        type=int,
        metavar="N",
        help="Maximum number of retries for API calls (default: 3)"
    )

    # Logging options for extract_logic
    extract_logic_logging_group = extract_logic_parser.add_argument_group("Logging Options")
    extract_logic_logging_group.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    extract_logic_logging_group.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )

    # ========== PIPELINE SUBCOMMAND (NEW) ==========
    pipeline_parser = subparsers.add_parser(
        "pipeline",
        help="Run the full document processing pipeline (discover, classify, extract)",
        epilog="""
The pipeline command processes claim folders and creates structured outputs:

Output Structure:
  output/claims/{claim_id}/
    docs/{doc_id}/           - Document-level data
      source/                - Original files
      text/                  - Extracted text (pages.json)
      meta/                  - Document metadata
      labels/                - Human QA labels (latest.json)
    runs/{run_id}/           - Run-scoped outputs
      manifest.json          - Run metadata (git, versions, timing)
      extraction/            - Extraction results per doc
      context/               - Classification context per doc
      logs/                  - summary.json, metrics.json, run.log
      .complete              - Marker file (written last)

Examples:
  %(prog)s claims_folder/ -o output/claims    # Process all claims
  %(prog)s claims_folder/ -o output/claims --model gpt-4o
  %(prog)s claims_folder/ -o output/claims --dry-run   # Preview only
  %(prog)s claims_folder/ -o output/claims --force     # Overwrite existing run
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments for pipeline
    pipeline_parser.add_argument(
        "input_path",
        metavar="PATH",
        help="Path to claims folder (each subfolder is a claim with documents)",
    )

    # Output options for pipeline
    pipeline_output_group = pipeline_parser.add_argument_group("Output Options")
    pipeline_output_group.add_argument(
        "-o",
        "--output-dir",
        metavar="DIR",
        default="output/claims",
        help="Output directory for structured results (default: output/claims)",
    )

    # Model configuration for pipeline
    pipeline_model_group = pipeline_parser.add_argument_group("Model Configuration")
    pipeline_model_group.add_argument(
        "--model",
        metavar="MODEL",
        default="gpt-4o",
        help="LLM model for classification and extraction (default: gpt-4o)",
    )

    # Run control options for pipeline
    pipeline_run_group = pipeline_parser.add_argument_group("Run Control")
    pipeline_run_group.add_argument(
        "--run-id",
        metavar="ID",
        help="Override run ID (default: auto-generated run_YYYYMMDD_HHMMSS_gitsha)",
    )
    pipeline_run_group.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing run folder if it exists",
    )
    pipeline_run_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Discovery only - show what would be processed without running",
    )
    pipeline_run_group.add_argument(
        "--no-metrics",
        action="store_true",
        help="Skip metrics computation at end of run",
    )
    pipeline_run_group.add_argument(
        "--stages",
        metavar="STAGES",
        default="ingest,classify,extract",
        help="Comma-separated stages to run: ingest,classify,extract (default: all)",
    )

    # Logging options for pipeline
    pipeline_logging_group = pipeline_parser.add_argument_group("Logging Options")
    pipeline_logging_group.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    pipeline_logging_group.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )
    pipeline_logging_group.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars (useful for CI/logging)",
    )

    # ========== INDEX SUBCOMMAND (NEW) ==========
    index_parser = subparsers.add_parser(
        "index",
        help="Build or manage registry indexes for fast lookups",
        epilog="""
The index command builds JSONL indexes for fast document, label, and run lookups.

Index Files (output/registry/):
  doc_index.jsonl      - Document metadata for all docs
  label_index.jsonl    - Label summaries for labeled docs
  run_index.jsonl      - Completed run metadata
  registry_meta.json   - Build timestamp and counts

Examples:
  %(prog)s build                          # Build indexes from default output/
  %(prog)s build --root output            # Specify output directory
  %(prog)s build --root output -v         # Verbose output
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Index subcommands
    index_subparsers = index_parser.add_subparsers(dest="index_command", help="Index commands")
    index_subparsers.required = True

    # Build subcommand
    index_build_parser = index_subparsers.add_parser(
        "build",
        help="Build all indexes from filesystem",
    )
    index_build_parser.add_argument(
        "--root",
        metavar="DIR",
        default="output",
        help="Output root directory (default: output)",
    )
    index_build_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    index_build_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )

    return parser


def get_supported_files(folder: Path, recursive: bool = False) -> list[Path]:
    """
    Get all supported files in a folder.

    Args:
        folder: Folder to search
        recursive: Whether to search recursively

    Returns:
        List of file paths
    """
    supported_extensions = DataIngestion.SUPPORTED_EXTENSIONS
    files = []

    if recursive:
        all_files = folder.rglob("*")
    else:
        all_files = folder.glob("*")

    # Filter by suffix (case-insensitive)
    for file_path in all_files:
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            files.append(file_path)

    # Sort files for consistent ordering
    return sorted(files)


def process_file(
    filepath: Path,
    output_dir: Path,
    provider: str = "tesseract",
    ingestion: Optional[DataIngestion] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    Process a file and extract context using specified provider.

    Args:
        filepath: Path to input file
        output_dir: Directory for output JSON
        provider: Vision API provider name
        ingestion: Optional ingestion instance to reuse
        config: Optional configuration dictionary

    Returns:
        Dictionary with the processing result

    Raises:
        IngestionError: If processing fails
    """
    logger.info(f"Processing file: {filepath}")

    # Get or create ingestion implementation
    if ingestion is None:
        ingestion = IngestionFactory.create(provider)

        # Set output directory if supported (for providers like Azure DI that save additional files)
        if hasattr(ingestion, 'output_dir'):
            ingestion.output_dir = output_dir
            logger.debug(f"Set output_dir={output_dir} on ingestion instance")

        # Apply configuration if provided
        if config:
            for key, value in config.items():
                if value is not None and hasattr(ingestion, key):
                    setattr(ingestion, key, value)
                    logger.debug(f"Set {key}={value} on ingestion instance")

    # Process the file
    logger.info(f"Using {provider} vision API for processing")
    result = ingestion.process(filepath)

    return result


def save_single_result(
    result: dict, filepath: Path, output_dir: Path, session_id: str = None
) -> Path:
    """
    Save a single file processing result.

    For Azure DI provider, also saves the markdown file alongside the JSON.

    Args:
        result: Processing result dictionary
        filepath: Original file path
        output_dir: Output directory
        session_id: Optional session ID to include in results

    Returns:
        Path to saved JSON file
    """
    # Add session ID if provided
    if session_id:
        result["session_id"] = session_id

    # Generate output filename
    output_filename = f"{filepath.stem}-context.json"
    output_path = output_dir / output_filename

    # Save JSON result
    logger.info(
        f"[Session {session_id}] Saving results to: {output_path}"
        if session_id
        else f"Saving results to: {output_path}"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Check if there's a markdown file to save (Azure DI specific)
    if "markdown_file" in result:
        # Get the markdown source path (should be next to the original file)
        md_filename = result["markdown_file"]
        md_source = Path(result.get("file_path", filepath)).parent / md_filename

        if md_source.exists():
            # Copy markdown file to output directory
            md_dest = output_dir / md_filename
            shutil.copy2(md_source, md_dest)
            logger.info(
                f"[Session {session_id}] Saved markdown: {md_dest}"
                if session_id
                else f"Saved markdown: {md_dest}"
            )
        else:
            logger.warning(f"Markdown file not found: {md_source}")

    return output_path


def process_folder(
    folder: Path,
    output_dir: Path,
    provider: str = "tesseract",
    recursive: bool = False,
    config: Optional[dict] = None,
    session_id: str = None,
    rich_output: bool = False,
    console: Optional[Console] = None,
) -> int:
    """
    Process all files in a folder, each to its own output file.

    Args:
        folder: Folder to process
        output_dir: Output directory
        provider: Vision API provider
        recursive: Whether to search recursively
        config: Optional configuration dictionary
        session_id: Optional session ID for tracking

    Returns:
        Number of successfully processed files
    """
    # Get all supported files
    files = get_supported_files(folder, recursive)

    if not files:
        logger.warning(f"No supported files found in {folder}")
        return 0

    logger.info(f"Found {len(files)} files to process")

    # Create ingestion instance once
    ingestion = IngestionFactory.create(provider)

    # Set output directory if supported (for providers like Azure DI that save additional files)
    if hasattr(ingestion, 'output_dir'):
        ingestion.output_dir = output_dir
        logger.debug(f"Set output_dir={output_dir} on ingestion instance")

    # Apply configuration if provided
    if config:
        for key, value in config.items():
            if value is not None and hasattr(ingestion, key):
                setattr(ingestion, key, value)
                logger.debug(f"Set {key}={value} on ingestion instance")

    success_count = 0
    error_count = 0
    output_files = []

    for i, filepath in enumerate(files, 1):
        if session_id:
            logger.info(
                f"[Session {session_id}] [{i}/{len(files)}] Processing: {filepath}"
            )
        else:
            logger.info(f"[{i}/{len(files)}] Processing: {filepath}")

        try:
            # Process the file
            result = process_file(filepath, output_dir, provider, ingestion, config)

            if rich_output and console:
                # Simply print the result to stdout
                console.print(result)
            else:
                # Save individual result
                output_path = save_single_result(
                    result, filepath, output_dir, session_id
                )
                output_files.append(output_path)

            success_count += 1

        except KeyboardInterrupt:
            logger.info(
                f"Interrupted. Processed {success_count} files before interruption."
            )
            raise  # Re-raise to be caught by main handler

        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            error_count += 1

    if not rich_output:
        logger.info(
            f"Processed {success_count} files successfully, {error_count} failed"
        )
        logger.info(f"Output files saved to: {output_dir}")

    return success_count


def process_extraction(
    input_path: Path,
    output_path: Path,
    prompt_path: Optional[str] = None,
    schema_path: Optional[str] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    Process markdown file and extract symbol table.

    Generates two output files:
    - {output_path} (JSON): Full structured symbol table
    - {output_path.replace('.json', '.md')} (Markdown): Token-efficient format

    Args:
        input_path: Path to input markdown file
        output_path: Path to output JSON file (e.g., 'policy_symbol_table.json')
        prompt_path: Optional absolute path to custom prompt file
        schema_path: Optional absolute path to custom schema file
        config: Optional configuration dictionary for model settings

    Returns:
        Dictionary with the extraction result including file paths

    Raises:
        ExtractionError: If extraction fails
    """
    from context_builder.extraction.openai_symbol_extraction import (
        OpenAISymbolExtraction,
        ExtractionError,
    )

    logger.info(f"Extracting symbol table from markdown file: {input_path}")

    try:
        # Create extraction instance
        extractor = OpenAISymbolExtraction(
            prompt_path=prompt_path,
            schema_path=schema_path
        )

        # Apply configuration if provided
        if config:
            for key, value in config.items():
                if value is not None and hasattr(extractor, key):
                    setattr(extractor, key, value)
                    logger.debug(f"Set {key}={value} on extractor instance")

        # Process the file (saves both JSON and MD)
        result = extractor.process(str(input_path), str(output_path))

        return result

    except ExtractionError as e:
        logger.error(f"Symbol extraction failed: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during symbol extraction: {e}")
        raise


def process_logic_extraction(
    input_path: Path,
    output_base_path: Path,
    symbol_table_path: Optional[str] = None,
    prompt_path: Optional[str] = None,
    schema_path: Optional[str] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    Process markdown file and extract policy logic as normalized JSON Logic.

    Generates two output files:
    - {output_base_path}_normalized_logic.json: LLM output with normalized format
    - {output_base_path}_logic.json: Transpiled standard JSON Logic format

    Args:
        input_path: Path to input markdown file
        output_base_path: Base path for output files (without extension)
        symbol_table_path: Optional path to symbol table JSON file
        prompt_path: Optional absolute path to custom prompt file
        schema_path: Optional absolute path to custom schema file
        config: Optional configuration dictionary for model settings

    Returns:
        Dictionary with the extraction result including file paths

    Raises:
        ExtractionError: If extraction fails
        FileNotFoundError: If symbol_table.md file not found
    """
    from context_builder.extraction.openai_logic_extraction import (
        OpenAILogicExtraction,
        ExtractionError,
    )

    logger.info(f"Extracting logic from markdown file: {input_path}")

    try:
        # Create logic extraction instance
        extractor = OpenAILogicExtraction(
            prompt_path=prompt_path,
            schema_path=schema_path
        )

        # Apply configuration if provided
        if config:
            for key, value in config.items():
                if value is not None and hasattr(extractor, key):
                    setattr(extractor, key, value)
                    logger.debug(f"Set {key}={value} on extractor instance")

        # Pass symbol table JSON path for chunking
        # The extractor will handle chunking if file is large
        result = extractor.process(
            str(input_path),
            str(output_base_path),
            symbol_table_json_path=symbol_table_path
        )

        return result

    except ExtractionError as e:
        logger.error(f"Logic extraction failed: {e}")
        raise
    except FileNotFoundError as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during logic extraction: {e}")
        raise


def main():
    """Main entry point for CLI."""
    # Set up signal handlers for graceful shutdown
    setup_signal_handlers()

    # Load environment variables
    load_dotenv()

    # Parse arguments
    parser = setup_argparser()
    args = parser.parse_args()

    # Check for mutually exclusive options (acquire only)
    if args.command == "acquire" and hasattr(args, "rich_output") and args.rich_output and args.verbose:
        print("[X] Error: --rich-output and -v/--verbose are mutually exclusive")
        sys.exit(1)

    # Initialize Rich console if needed (acquire only)
    console = None
    if args.command == "acquire" and hasattr(args, "rich_output") and args.rich_output:
        console = Console()
        # Suppress all logging when using rich output
        logging.disable(logging.CRITICAL)
    else:
        # Set up colored logging
        setup_colored_logging(verbose=args.verbose)

    # Set logging level
    if args.command == "acquire" and hasattr(args, "rich_output") and args.rich_output:
        pass  # Logging already disabled
    elif args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    # Route to appropriate command handler
    try:
        if args.command == "acquire":
            # ========== ACQUIRE COMMAND ==========
            # Validate input path
            input_path = Path(args.input_path)
            if not input_path.exists():
                logger.error(f"Path not found: {input_path}")
                sys.exit(1)

            # Validate output directory (skip if using rich output since no files are saved)
            output_dir = Path(args.output_dir)
            if not args.rich_output:
                if not output_dir.exists():
                    logger.info(f"Creating output directory: {output_dir}")
                    try:
                        output_dir.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        logger.error(f"Failed to create output directory: {e}")
                        sys.exit(1)

                if not output_dir.is_dir():
                    logger.error(f"Output path is not a directory: {output_dir}")
                    sys.exit(1)

            # Generate session ID for tracking
            session_id = str(uuid.uuid4())[:8]
            logger.info(f"Starting session: {session_id}")

            # Build configuration dictionary from CLI args
            config = {}
            if args.model is not None:
                config["model"] = args.model
            if args.max_tokens is not None:
                config["max_tokens"] = args.max_tokens
            if args.temperature is not None:
                config["temperature"] = args.temperature
            if args.max_pages is not None:
                config["max_pages"] = args.max_pages
            if args.render_scale is not None:
                config["render_scale"] = args.render_scale
            if args.timeout is not None:
                config["timeout"] = args.timeout
            if args.retries is not None:
                config["retries"] = args.retries

            # Azure DI specific: handle save_markdown option
            # --no-save-markdown overrides --save-markdown
            if args.no_save_markdown:
                config["save_markdown"] = False
            elif args.save_markdown:
                config["save_markdown"] = True

            # Process based on input type
            if input_path.is_file():
                # Process single file
                result = process_file(
                    filepath=input_path,
                    output_dir=output_dir,
                    provider=args.provider,
                    config=config,
                )

                if args.rich_output:
                    # Simply print the result to stdout
                    console.print(result)
                else:
                    output_path = save_single_result(
                        result, input_path, output_dir, session_id
                    )
                    logger.info(
                        f"[Session {session_id}] Successfully processed file. Output: {output_path}"
                    )
                    if not args.quiet:
                        print(f"[OK] Context extracted to: {output_path}")

            elif input_path.is_dir():
                # Process folder
                success_count = process_folder(
                    folder=input_path,
                    output_dir=output_dir,
                    provider=args.provider,
                    recursive=args.recursive,
                    config=config,
                    session_id=session_id,
                    rich_output=args.rich_output,
                    console=console,
                )
                if success_count > 0:
                    if not args.rich_output:
                        logger.info(
                            f"[Session {session_id}] Successfully processed {success_count} files"
                        )
                        if not args.quiet:
                            print(
                                f"[OK] Processed {success_count} files. Contexts saved to: {output_dir}"
                            )
                else:
                    if not args.quiet and not args.rich_output:
                        print(f"[X] No supported files found in {input_path}")
                    elif args.rich_output:
                        console.print(
                            f"[red][X] No supported files found in {input_path}[/red]"
                        )
                    sys.exit(1)
            else:
                logger.error(f"Invalid input path: {input_path}")
                sys.exit(1)

        elif args.command == "extract":
            # ========== EXTRACT COMMAND ==========
            # Validate input path
            input_path = Path(args.input_path)
            if not input_path.exists():
                logger.error(f"Markdown file not found: {input_path}")
                sys.exit(1)

            if not input_path.is_file():
                logger.error(f"Input path is not a file: {input_path}")
                sys.exit(1)

            # Create timestamped output folder
            from context_builder.utils.file_utils import create_timestamped_output_folder

            base_output_dir = Path(args.output)
            try:
                timestamped_folder = create_timestamped_output_folder(base_output_dir, prefix="ACB")
                logger.info(f"Created timestamped output folder: {timestamped_folder}")
            except FileExistsError as e:
                logger.error(str(e))
                sys.exit(1)
            except Exception as e:
                logger.error(f"Failed to create timestamped output folder: {e}")
                sys.exit(1)

            # Copy input file to timestamped folder
            try:
                input_copy = timestamped_folder / input_path.name
                shutil.copy2(input_path, input_copy)
                logger.info(f"Copied input file to: {input_copy}")
            except Exception as e:
                logger.error(f"Failed to copy input file: {e}")
                sys.exit(1)

            # Set output path within timestamped folder
            output_filename = f"{input_path.stem}_symbol_table.json"
            output_path = timestamped_folder / output_filename

            # Build configuration dictionary from CLI args
            config = {}
            if args.model is not None:
                config["model"] = args.model
            if args.max_tokens is not None:
                config["max_tokens"] = args.max_tokens
            if args.temperature is not None:
                config["temperature"] = args.temperature
            if args.timeout is not None:
                config["timeout"] = args.timeout
            if args.retries is not None:
                config["retries"] = args.retries

            # Get prompt and schema paths
            prompt_path = args.prompt if hasattr(args, "prompt") else None
            schema_path = args.schema if hasattr(args, "schema") else None

            # Process extraction
            result = process_extraction(
                input_path=input_path,
                output_path=output_path,
                prompt_path=prompt_path,
                schema_path=schema_path,
                config=config,
            )

            logger.info(f"Successfully extracted symbol table from {input_path}")
            if not args.quiet:
                # Show timestamped folder and output files
                md_path = output_path.with_suffix(".md")
                print(f"[OK] Symbol extraction complete.")
                print(f"    Output folder: {timestamped_folder}")
                print(f"    JSON: {output_path}")
                print(f"    Markdown: {md_path}")

        elif args.command == "extract_logic":
            # ========== EXTRACT_LOGIC COMMAND ==========
            # Validate input path
            input_path = Path(args.input_path)
            if not input_path.exists():
                logger.error(f"Markdown file not found: {input_path}")
                sys.exit(1)

            if not input_path.is_file():
                logger.error(f"Input path is not a file: {input_path}")
                sys.exit(1)

            # Detect if input is already in a timestamped folder (ACB-YYYYMMDD-HHMMSS pattern)
            import re
            from context_builder.utils.file_utils import create_timestamped_output_folder

            acb_folder_pattern = re.compile(r"^ACB-\d{8}-\d{6}$")
            parent_folder = input_path.parent

            if acb_folder_pattern.match(parent_folder.name):
                # Input is in existing timestamped folder - reuse it
                timestamped_folder = parent_folder
                logger.info(f"Detected existing timestamped folder: {timestamped_folder}")
            else:
                # Create new timestamped folder under specified output directory
                base_output_dir = Path(args.output)
                try:
                    timestamped_folder = create_timestamped_output_folder(base_output_dir, prefix="ACB")
                    logger.info(f"Created timestamped output folder: {timestamped_folder}")
                except FileExistsError as e:
                    logger.error(str(e))
                    sys.exit(1)
                except Exception as e:
                    logger.error(f"Failed to create timestamped output folder: {e}")
                    sys.exit(1)

                # Copy input file to timestamped folder
                try:
                    input_copy = timestamped_folder / input_path.name
                    shutil.copy2(input_path, input_copy)
                    logger.info(f"Copied input file to: {input_copy}")
                except Exception as e:
                    logger.error(f"Failed to copy input file: {e}")
                    sys.exit(1)

            # Set output base path within timestamped folder
            output_base_path = timestamped_folder / input_path.stem

            # Validate symbol table if provided (otherwise will auto-detect)
            symbol_table_path = None
            if hasattr(args, "symbol_table") and args.symbol_table:
                symbol_table_path = Path(args.symbol_table)
                if not symbol_table_path.exists():
                    logger.error(f"Symbol table file not found: {symbol_table_path}")
                    sys.exit(1)
                symbol_table_path = str(symbol_table_path)
                logger.info(f"Using provided symbol table: {symbol_table_path}")
            else:
                logger.info("Symbol table not provided, will auto-detect from input filename")

            # Build configuration dictionary from CLI args
            config = {}
            if args.model is not None:
                config["model"] = args.model
            if args.max_tokens is not None:
                config["max_tokens"] = args.max_tokens
            if args.temperature is not None:
                config["temperature"] = args.temperature
            if args.timeout is not None:
                config["timeout"] = args.timeout
            if args.retries is not None:
                config["retries"] = args.retries

            # Get prompt and schema paths
            prompt_path = args.prompt if hasattr(args, "prompt") else None
            schema_path = args.schema if hasattr(args, "schema") else None

            # Process logic extraction
            result = process_logic_extraction(
                input_path=input_path,
                output_base_path=output_base_path,
                symbol_table_path=symbol_table_path,
                prompt_path=prompt_path,
                schema_path=schema_path,
                config=config,
            )

            logger.info(f"Successfully extracted logic from {input_path}")
            if not args.quiet:
                # Show timestamped folder and output files
                normalized_path = Path(f"{output_base_path}_normalized_logic.json")
                transpiled_path = Path(f"{output_base_path}_logic.json")
                print(f"[OK] Logic extraction complete.")
                print(f"    Output folder: {timestamped_folder}")
                print(f"    Normalized: {normalized_path}")
                print(f"    Transpiled: {transpiled_path}")

                # Display audit summary if available
                if "_audit_summary" in result:
                    summary = result["_audit_summary"]
                    print(f"\nAudit Summary:")
                    print(f"  Variables analyzed: {summary['variables_analyzed']}")
                    print(f"  Orphan concepts found: {summary['orphan_concepts']}")
                    print(f"  NULL bugs detected: {summary['null_bugs']}")
                    if summary["has_issues"]:
                        print(f"  [!] Review semantic_audit_report.txt for details")
                    else:
                        print(f"  [OK] No semantic hallucinations detected")

        elif args.command == "pipeline":
            # ========== PIPELINE COMMAND ==========
            # Validate input path
            input_path = Path(args.input_path)
            if not input_path.exists():
                logger.error(f"Path not found: {input_path}")
                sys.exit(1)

            if not input_path.is_dir():
                logger.error(f"Input path is not a directory: {input_path}")
                sys.exit(1)

            # Create output directory if needed
            output_dir = Path(args.output_dir)
            if not output_dir.exists():
                logger.info(f"Creating output directory: {output_dir}")
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to create output directory: {e}")
                    sys.exit(1)

            # Discover claims
            logger.info(f"Discovering claims in: {input_path}")
            try:
                claims = discover_claims(input_path)
            except Exception as e:
                logger.error(f"Failed to discover claims: {e}")
                sys.exit(1)

            if not claims:
                logger.warning("No claims found in input path")
                if not args.quiet:
                    print(f"[!] No claims found in {input_path}")
                sys.exit(1)

            logger.info(f"Discovered {len(claims)} claim(s)")

            # Dry-run mode: just show what would be processed
            if args.dry_run:
                print(f"\n[DRY RUN] Would process {len(claims)} claim(s):\n")
                for claim in claims:
                    # Handle encoding for Windows console
                    try:
                        print(f"  Claim: {claim.claim_id}")
                        print(f"    Documents: {len(claim.documents)}")
                        for doc in claim.documents:
                            # Encode and decode to handle special chars
                            filename = doc.original_filename.encode('ascii', errors='replace').decode('ascii')
                            print(f"      - {filename} ({doc.source_type})")
                        print()
                    except UnicodeEncodeError:
                        print(f"  Claim: {claim.claim_id} ({len(claim.documents)} docs)")
                        print()
                print(f"Output directory: {output_dir}")
                print(f"Model: {args.model}")
                if args.run_id:
                    print(f"Run ID: {args.run_id}")
                sys.exit(0)

            # Build command string for manifest
            command_str = " ".join(sys.argv)

            # Generate run_id once for all claims (if not provided)
            run_id = args.run_id or generate_run_id()
            logger.info(f"Using run ID: {run_id}")

            # Parse stages argument
            try:
                stages = parse_stages(args.stages)
                stage_config = StageConfig(stages=stages)
                logger.info(f"Pipeline stages: {[s.value for s in stages]} (run_kind={stage_config.run_kind})")
            except ValueError as e:
                print(f"[!] Invalid --stages argument: {e}")
                sys.exit(1)

            # Determine if progress bars should be shown
            show_progress = (
                not args.quiet
                and not getattr(args, "no_progress", False)
                and sys.stdout.isatty()
            )

            # Process each claim
            total_docs = 0
            success_docs = 0
            failed_claims = []
            claim_results = []  # Track results for global run manifest

            # Set up claims iterator with optional progress bar
            if show_progress:
                print(f"\nProcessing pipeline (run_id: {run_id})")
                claims_pbar = tqdm(
                    claims,
                    desc="Claims",
                    unit="claim",
                    position=0,
                    leave=True,
                )
            else:
                claims_pbar = claims

            for i, claim in enumerate(claims_pbar, 1):
                if not show_progress:
                    logger.info(f"[{i}/{len(claims)}] Processing claim: {claim.claim_id}")
                    if not args.quiet:
                        print(f"\n[{i}/{len(claims)}] Processing claim: {claim.claim_id} ({len(claim.documents)} docs)")

                # Create document progress bar if showing progress
                doc_pbar = None

                def make_progress_callback(pbar):
                    """Create a progress callback that updates the given progress bar."""
                    def callback(idx, total, filename):
                        if pbar:
                            pbar.update(1)
                    return callback

                if show_progress:
                    # Truncate long claim IDs for display
                    display_id = claim.claim_id[:20] if len(claim.claim_id) > 20 else claim.claim_id
                    doc_pbar = tqdm(
                        total=len(claim.documents),
                        desc=f"  {display_id}",
                        unit="doc",
                        position=1,
                        leave=False,
                    )

                progress_callback = make_progress_callback(doc_pbar) if show_progress else None

                try:
                    result = process_claim(
                        claim=claim,
                        output_base=output_dir,
                        classifier=None,  # Will be created by process_claim
                        run_id=run_id,  # Use consistent run_id for all claims
                        force=args.force,
                        command=command_str,
                        model=args.model,
                        compute_metrics=not args.no_metrics,
                        stage_config=stage_config,
                        progress_callback=progress_callback,
                    )

                    total_docs += len(result.documents)
                    success_docs += sum(1 for d in result.documents if d.status == "success")
                    claim_results.append(result)  # Store for global manifest

                    if result.status in ("success", "partial"):
                        logger.info(f"Claim {claim.claim_id}: {result.status} - {result.stats}")
                    else:
                        logger.warning(f"Claim {claim.claim_id}: {result.status}")
                        failed_claims.append(claim.claim_id)

                except Exception as e:
                    logger.error(f"Failed to process claim {claim.claim_id}: {e}")
                    failed_claims.append(claim.claim_id)
                finally:
                    if doc_pbar:
                        doc_pbar.close()

            # Close claims progress bar if used
            if show_progress and hasattr(claims_pbar, "close"):
                claims_pbar.close()

            # Create global (workspace-scoped) run
            if claim_results:
                logger.info(f"Creating global run at output/runs/{run_id}/")
                workspace_paths = create_workspace_run_structure(output_dir, run_id)

                # Build global manifest with claim pointers
                global_manifest = {
                    "run_id": run_id,
                    "started_at": datetime.now().isoformat() + "Z",
                    "ended_at": datetime.now().isoformat() + "Z",
                    "command": command_str,
                    "model": args.model,
                    "claims_count": len(claims),
                    "claims": [
                        {
                            "claim_id": r.claim_id,
                            "status": r.status,
                            "docs_count": len(r.documents),
                            "claim_run_path": str(
                                output_dir / r.claim_id / "runs" / run_id
                            ),
                        }
                        for r in claim_results
                    ],
                }

                # Write manifest
                with open(workspace_paths.manifest_json, "w", encoding="utf-8") as f:
                    json.dump(global_manifest, f, indent=2, ensure_ascii=False)

                # Build aggregated summary
                global_summary = {
                    "run_id": run_id,
                    "status": "success" if not failed_claims else ("partial" if success_docs > 0 else "failed"),
                    "claims_discovered": len(claims),
                    "claims_processed": len(claim_results),
                    "claims_failed": len(failed_claims),
                    "docs_total": total_docs,
                    "docs_success": success_docs,
                    "completed_at": datetime.now().isoformat() + "Z",
                }

                # Write summary
                with open(workspace_paths.summary_json, "w", encoding="utf-8") as f:
                    json.dump(global_summary, f, indent=2, ensure_ascii=False)

                # Aggregate metrics from all claims if available
                if not args.no_metrics:
                    aggregated_metrics = {
                        "run_id": run_id,
                        "claims_count": len(claim_results),
                        "docs_total": total_docs,
                        "docs_success": success_docs,
                        "per_claim": [],
                    }
                    for r in claim_results:
                        claim_paths = get_claim_paths(output_dir, r.claim_id)
                        metrics_path = claim_paths.runs_dir / run_id / "logs" / "metrics.json"
                        if metrics_path.exists():
                            with open(metrics_path, "r", encoding="utf-8") as f:
                                claim_metrics = json.load(f)
                                aggregated_metrics["per_claim"].append({
                                    "claim_id": r.claim_id,
                                    "metrics": claim_metrics,
                                })

                    with open(workspace_paths.metrics_json, "w", encoding="utf-8") as f:
                        json.dump(aggregated_metrics, f, indent=2, ensure_ascii=False)

                # Mark run complete
                workspace_paths.complete_marker.touch()
                logger.info(f"Global run created at: {workspace_paths.run_root}")

            # Print summary
            if not args.quiet:
                print(f"\n{'='*50}")
                print(f"Pipeline Complete")
                print(f"{'='*50}")
                print(f"Claims processed: {len(claims)}")
                print(f"Documents: {success_docs}/{total_docs} successful")
                if failed_claims:
                    print(f"Failed claims: {', '.join(failed_claims)}")
                print(f"Output: {output_dir}")

        elif args.command == "index":
            # ========== INDEX COMMAND ==========
            if args.index_command == "build":
                from context_builder.storage.index_builder import build_all_indexes

                output_dir = Path(args.root)
                if not output_dir.exists():
                    logger.error(f"Output directory not found: {output_dir}")
                    sys.exit(1)

                logger.info(f"Building indexes from: {output_dir}")

                try:
                    stats = build_all_indexes(output_dir)

                    if not args.quiet:
                        print(f"\n[OK] Index build complete")
                        print(f"    Documents: {stats['doc_count']}")
                        print(f"    Labels: {stats['label_count']}")
                        print(f"    Runs: {stats['run_count']}")
                        print(f"    Claims: {stats['claim_count']}")
                        print(f"    Registry: {output_dir}/registry/")

                except Exception as e:
                    logger.error(f"Index build failed: {e}")
                    sys.exit(1)

    except KeyboardInterrupt:
        print("\n[!] Process interrupted by user. Exiting gracefully...")
        sys.exit(0)

    except IngestionError as e:
        logger.error(f"Acquisition failed: {e}")
        print(f"[X] Failed to process: {e}")
        sys.exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"[X] Unexpected error occurred. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
