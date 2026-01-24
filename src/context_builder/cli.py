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
from typing import List

# Import pipeline components for the new pipeline command
from context_builder.pipeline.discovery import discover_claims
from context_builder.pipeline.run import process_claim, StageConfig
from context_builder.pipeline.paths import create_workspace_run_structure, get_claim_paths
from context_builder.schemas.run_errors import PipelineStage

# Ensure Azure DI implementation is imported so it auto-registers
try:
    from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion
except ImportError:
    pass  # Azure DI dependencies not installed


# =============================================================================
# Pipeline Progress Display
# =============================================================================


class ClaimProgressDisplay:
    """
    Displays a single tqdm progress bar for a claim's processing.

    Progress advances on each STAGE completion (not per document).
    So 4 docs × 3 stages = 12 total steps.

    The bar description shows current document and stage:
        Processing claim: 65128
        FZA.pdf: classify |████████████░░░░░░░░| 7/12 [00:15<00:08]
    """

    def __init__(self, claim_id: str, doc_count: int, stages: List[str]):
        self.claim_id = claim_id
        self.doc_count = doc_count
        self.stages = stages  # e.g., ["ingest", "classify", "extract"]
        self.stage_count = len(stages)
        self.total_steps = doc_count * self.stage_count
        self.pbar: Optional[tqdm] = None
        self.current_filename: Optional[str] = None
        self.current_stage: Optional[str] = None

    def start(self) -> None:
        """Print claim header and initialize progress bar."""
        print(f"\nProcessing claim: {self.claim_id}")
        self.pbar = tqdm(
            total=self.total_steps,
            unit="stage",
            leave=True,
            bar_format="{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            colour="cyan",
        )

    def start_document(self, filename: str, doc_id: str) -> None:
        """Called when starting to process a new document."""
        self.current_filename = filename
        # Truncate long filenames
        if len(filename) > 35:
            filename = filename[:32] + "..."
        if self.pbar:
            self.pbar.set_description_str(f"{filename}")

    def on_phase_start(self, phase: str) -> None:
        """Called when a phase starts - update the description."""
        self.current_stage = phase
        if self.pbar and self.current_filename:
            filename = self.current_filename
            if len(filename) > 30:
                filename = filename[:27] + "..."
            self.pbar.set_description_str(f"{filename}: {phase}")

    def on_phase_end(self, phase: str, status: str = "success") -> None:
        """Called when a phase ends - advance the progress bar."""
        if self.pbar:
            self.pbar.update(1)

    def complete_document(self, timings: Optional[object] = None, status: str = "success",
                          doc_type: Optional[str] = None, error: Optional[str] = None) -> None:
        """Called when a document finishes all stages."""
        # Progress is already updated by on_phase_end, nothing extra needed
        pass

    def finish(self) -> None:
        """Close progress bar for this claim."""
        if self.pbar:
            self.pbar.close()


# =============================================================================
# Workspace Configuration
# =============================================================================

def get_project_root() -> Path:
    """Find project root by looking for .contextbuilder directory."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".contextbuilder").is_dir():
            return parent
    return current


def get_active_workspace() -> Optional[dict]:
    """Read active workspace from .contextbuilder/workspaces.json.

    Returns:
        Workspace dict with keys: workspace_id, name, path, status
        None if no workspace config found
    """
    project_root = get_project_root()
    workspaces_file = project_root / ".contextbuilder" / "workspaces.json"

    if not workspaces_file.exists():
        return None

    try:
        with open(workspaces_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        active_id = config.get("active_workspace_id")
        if not active_id:
            return None

        for ws in config.get("workspaces", []):
            if ws.get("workspace_id") == active_id:
                return ws

        return None
    except (json.JSONDecodeError, IOError):
        return None


def get_workspace_claims_dir() -> Path:
    """Get claims directory for active workspace, or default to output/claims."""
    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        return Path(workspace["path"]) / "claims"
    return Path("output/claims")


def get_workspace_logs_dir() -> Path:
    """Get logs directory for active workspace, or default to output/logs."""
    workspace = get_active_workspace()
    if workspace and workspace.get("path"):
        return Path(workspace["path"]) / "logs"
    return Path("output/logs")


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

    # ========== PIPELINE SUBCOMMAND ==========
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
        default=None,
        help="Output directory for structured results (default: active workspace or output/claims)",
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
    pipeline_run_group.add_argument(
        "--doc-types",
        metavar="TYPES",
        default=None,
        help="Comma-separated doc types to extract (e.g., fnol_form,police_report). "
             "Use 'list' to show available types. Default: extract all supported types.",
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

    # ========== EVAL SUBCOMMAND ==========
    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluate a run against canonical truth",
        epilog="""
Examples:
  %(prog)s eval run --run-id run_20260101_010101_abc123 --output output
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", help="Eval commands")
    eval_subparsers.required = True

    eval_run_parser = eval_subparsers.add_parser(
        "run",
        help="Evaluate a run and emit per-doc + summary eval outputs",
    )
    eval_run_parser.add_argument(
        "--run-id",
        required=True,
        metavar="ID",
        help="Run ID to evaluate",
    )
    eval_run_parser.add_argument(
        "--output",
        metavar="DIR",
        default="output",
        help="Output root directory (default: output)",
    )
    eval_run_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    eval_run_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )

    # ========== AGGREGATE SUBCOMMAND ==========
    aggregate_parser = subparsers.add_parser(
        "aggregate",
        help="Aggregate extracted facts for a claim into claim_facts.json",
        epilog="""
Aggregates facts from multiple documents into a single claim-level file.

Uses the latest complete run by default. Selection strategy: highest confidence wins.

Output:
  claims/{claim_id}/context/claim_facts.json

Examples:
  %(prog)s aggregate --claim-id CLM-001              # Aggregate for a claim
  %(prog)s aggregate --claim-id CLM-001 --dry-run   # Preview without writing
  %(prog)s aggregate --claim-id CLM-001 --run-id run_20260124_153000  # Specific run
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    aggregate_parser.add_argument(
        "--claim-id",
        required=True,
        metavar="ID",
        help="Claim ID to aggregate facts for",
    )
    aggregate_parser.add_argument(
        "--run-id",
        metavar="ID",
        help="Specific run ID to use (default: latest complete run)",
    )
    aggregate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show aggregated output without writing to file",
    )
    aggregate_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    aggregate_parser.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal console output"
    )

    # ========== BACKFILL-EVIDENCE SUBCOMMAND ==========
    backfill_parser = subparsers.add_parser(
        "backfill-evidence",
        help="Reprocess extractions to fill missing evidence offsets",
        epilog="""
Reprocesses existing extraction files to:
1. Fill missing character offsets (char_start/char_end = 0)
2. Set has_verified_evidence flags on fields
3. Run validation checks and attach _extraction_meta

Examples:
  %(prog)s backfill-evidence              # Backfill all extractions
  %(prog)s backfill-evidence --dry-run    # Preview without writing
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    backfill_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing",
    )
    backfill_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    backfill_parser.add_argument(
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
    result = ingestion.process(filepath, envelope=True)

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
    # Normalize to ingestion envelope
    data = result.get("data", result)

    # Add session ID if provided
    if session_id:
        if "data" in result:
            result["data"]["session_id"] = session_id
        else:
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
    if "markdown_file" in data:
        # Get the markdown source path (should be next to the original file)
        md_filename = data["markdown_file"]
        md_source = Path(data.get("file_path", filepath)).parent / md_filename

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

        elif args.command == "pipeline":
            # ========== PIPELINE COMMAND ==========
            # Handle --doc-types list before path validation
            if getattr(args, 'doc_types', None) and args.doc_types.lower() == "list":
                from context_builder.extraction.spec_loader import list_available_specs
                available_types = list_available_specs()
                print("\nAvailable document types for extraction:")
                for dt in available_types:
                    print(f"  - {dt}")
                print(f"\nUsage: --doc-types {','.join(available_types[:3])}")
                sys.exit(0)

            # Validate input path
            input_path = Path(args.input_path)
            if not input_path.exists():
                logger.error(f"Path not found: {input_path}")
                sys.exit(1)

            if not input_path.is_dir():
                logger.error(f"Input path is not a directory: {input_path}")
                sys.exit(1)

            # Resolve output directory from workspace config or default
            if args.output_dir:
                output_dir = Path(args.output_dir)
            else:
                output_dir = get_workspace_claims_dir()
                workspace = get_active_workspace()
                if workspace:
                    logger.info(f"Using workspace '{workspace.get('name', workspace.get('workspace_id'))}': {output_dir}")
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

            # Parse --doc-types argument early (for dry-run display)
            # Note: "list" is handled earlier before path validation
            doc_type_filter = None
            if args.doc_types:
                from context_builder.extraction.spec_loader import list_available_specs
                available_types = list_available_specs()

                # Parse comma-separated list
                doc_type_filter = [t.strip() for t in args.doc_types.split(",") if t.strip()]

                # Validate doc types
                invalid_types = [t for t in doc_type_filter if t not in available_types]
                if invalid_types:
                    print(f"[!] Invalid doc type(s): {', '.join(invalid_types)}")
                    print(f"    Available types: {', '.join(available_types)}")
                    sys.exit(1)

                logger.info(f"Doc type filter: {doc_type_filter}")

            # Dry-run mode: just show what would be processed
            if args.dry_run:
                print(f"\n[DRY RUN] Would process {len(claims)} claim(s):\n")
                if doc_type_filter:
                    print(f"  Doc type filter: {', '.join(doc_type_filter)}")
                    print(f"  (Only documents classified as these types will be extracted)\n")
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
                if args.run_id:
                    print(f"Run ID: {args.run_id}")
                sys.exit(0)

            # Build command string for manifest
            command_str = " ".join(sys.argv)

            # Generate run_id once for all claims (if not provided)
            if args.run_id:
                run_id = args.run_id
            else:
                from context_builder.extraction.base import generate_run_id
                run_id = generate_run_id()
            logger.info(f"Using run ID: {run_id}")

            # Parse stages argument
            try:
                stages = parse_stages(args.stages)
            except ValueError as e:
                print(f"[!] Invalid --stages argument: {e}")
                sys.exit(1)

            # doc_type_filter was already parsed above (before dry-run)
            stage_config = StageConfig(stages=stages, doc_type_filter=doc_type_filter)
            logger.info(f"Pipeline stages: {[s.value for s in stages]} (run_kind={stage_config.run_kind})")

            # Determine if progress bars should be shown
            show_progress = (
                not args.quiet
                and not getattr(args, "no_progress", False)
            )

            # Create classifier once for the run to centralize defaults
            from context_builder.classification import ClassifierFactory
            classifier = ClassifierFactory.create("openai")

            # Suppress INFO/DEBUG during pipeline - only show warnings/errors
            # Full logs still go to run.log
            if show_progress:
                for handler in logging.getLogger().handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(logging.WARNING)

            # Process each claim
            total_docs = 0
            success_docs = 0
            failed_claims = []
            claim_results = []  # Track results for global run manifest

            # Get stage names for display
            stage_names = [s.value for s in stages]  # e.g., ["ingest", "classify", "extract"]

            for i, claim in enumerate(claims, 1):
                if not show_progress:
                    logger.info(f"[{i}/{len(claims)}] Processing claim: {claim.claim_id}")

                # Create progress display for this claim
                display = None
                if show_progress:
                    display = ClaimProgressDisplay(
                        claim_id=claim.claim_id,
                        doc_count=len(claim.documents),
                        stages=stage_names,
                    )
                    display.start()

                # Track current document for phase callback
                current_doc_id = [None]  # Use list to allow mutation in closure

                def make_phase_callback(disp):
                    """Create a phase callback that updates the display on phase start."""
                    def callback(phase: str, doc_id: str, filename: str):
                        if disp:
                            # If this is a new document, start tracking it
                            if doc_id != current_doc_id[0]:
                                current_doc_id[0] = doc_id
                                disp.start_document(filename, doc_id)
                            disp.on_phase_start(phase)
                    return callback

                def make_phase_end_callback(disp):
                    """Create a phase end callback that updates the display on phase completion."""
                    def callback(phase: str, doc_id: str, filename: str, status: str):
                        if disp:
                            disp.on_phase_end(phase, status)
                    return callback

                def make_progress_callback(disp):
                    """Create a progress callback that completes the document display."""
                    def callback(idx, total, filename, doc_result):
                        if disp:
                            disp.complete_document(
                                timings=doc_result.timings,
                                status=doc_result.status,
                                doc_type=doc_result.doc_type,
                                error=doc_result.error,
                            )
                    return callback

                phase_callback = make_phase_callback(display) if show_progress else None
                phase_end_callback = make_phase_end_callback(display) if show_progress else None
                progress_callback = make_progress_callback(display) if show_progress else None

                try:
                    result = process_claim(
                        claim=claim,
                        output_base=output_dir,
                        classifier=classifier,
                        run_id=run_id,  # Use consistent run_id for all claims
                        force=args.force,
                        command=command_str,
                        compute_metrics=not args.no_metrics,
                        stage_config=stage_config,
                        progress_callback=progress_callback,
                        phase_callback=phase_callback,
                        phase_end_callback=phase_end_callback,
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
                    if display:
                        display.finish()

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

            # Auto-build indexes after pipeline completes
            if success_docs > 0:
                from context_builder.storage.index_builder import build_all_indexes
                try:
                    logger.info("Building indexes...")
                    # Pass workspace root (parent of claims dir), not claims dir itself
                    stats = build_all_indexes(output_dir.parent)
                    if not args.quiet:
                        print(f"Indexes updated: {stats['doc_count']} docs, {stats['run_count']} runs")
                except Exception as e:
                    logger.warning(f"Index build failed (non-fatal): {e}")

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

        elif args.command == "eval":
            # ========== EVAL COMMAND ==========
            if args.eval_command == "run":
                from context_builder.pipeline.eval import evaluate_run

                if args.verbose:
                    logging.getLogger().setLevel(logging.DEBUG)
                elif args.quiet:
                    logging.getLogger().setLevel(logging.WARNING)

                output_dir = Path(args.output)
                if not output_dir.exists():
                    logger.error(f"Output directory not found: {output_dir}")
                    sys.exit(1)

                summary = evaluate_run(output_dir, args.run_id)

                if not args.quiet:
                    print(f"\n[OK] Eval complete for {args.run_id}")
                    print(f"    Docs evaluated: {summary['docs_evaluated']}/{summary['docs_total']}")
                    print(f"    Fields labeled: {summary['fields_labeled']}")
                    print(f"    Correct: {summary['correct']}")
                    print(f"    Incorrect: {summary['incorrect']}")
                    print(f"    Missing: {summary['missing']}")
                    print(f"    Unverifiable: {summary['unverifiable']}")

        elif args.command == "aggregate":
            # ========== AGGREGATE COMMAND ==========
            from context_builder.api.services.aggregation import (
                AggregationError,
                AggregationService,
            )
            from context_builder.storage.filesystem import FileStorage

            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            elif args.quiet:
                logging.getLogger().setLevel(logging.WARNING)

            # Use active workspace
            workspace = get_active_workspace()
            if workspace and workspace.get("path"):
                workspace_root = Path(workspace["path"])
                if not args.quiet:
                    logger.info(f"Using workspace '{workspace.get('name', workspace.get('workspace_id'))}': {workspace_root}")
            else:
                workspace_root = Path("output")

            if not workspace_root.exists():
                logger.error(f"Workspace not found: {workspace_root}")
                sys.exit(1)

            # Initialize storage and service
            storage = FileStorage(workspace_root)
            service = AggregationService(storage)

            try:
                # Aggregate facts
                facts = service.aggregate_claim_facts(
                    claim_id=args.claim_id,
                    run_id=getattr(args, "run_id", None),
                )

                if args.dry_run:
                    # Print JSON output to stdout
                    print(facts.model_dump_json(indent=2))
                else:
                    # Write to file
                    output_path = service.write_claim_facts(args.claim_id, facts)
                    if not args.quiet:
                        print(f"\n[OK] Aggregated {len(facts.facts)} facts for {args.claim_id}")
                        print(f"    Run: {facts.run_id}")
                        print(f"    Sources: {len(facts.sources)} documents")
                        print(f"    Output: {output_path}")

            except AggregationError as e:
                logger.error(f"Aggregation failed: {e}")
                print(f"[X] Aggregation failed: {e}")
                sys.exit(1)

        elif args.command == "backfill-evidence":
            # ========== BACKFILL-EVIDENCE COMMAND ==========
            from context_builder.extraction.backfill import backfill_workspace

            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            elif args.quiet:
                logging.getLogger().setLevel(logging.WARNING)

            # Use active workspace
            workspace = get_active_workspace()
            if workspace and workspace.get("path"):
                claims_dir = Path(workspace["path"]) / "claims"
                if not args.quiet:
                    logger.info(f"Using workspace '{workspace.get('name', workspace.get('workspace_id'))}': {claims_dir}")
            else:
                claims_dir = Path("output") / "claims"

            if not claims_dir.exists():
                logger.error(f"Claims directory not found: {claims_dir}")
                sys.exit(1)

            print(f"Backfilling evidence in: {claims_dir}")
            if args.dry_run:
                print("(dry run - no changes will be written)")

            stats = backfill_workspace(claims_dir, dry_run=args.dry_run)

            print(f"\nProcessed: {stats['processed']} extractions")
            print(f"Improved:  {stats['improved']} extractions")
            if stats['errors']:
                print(f"Errors:    {len(stats['errors'])}")
                for err in stats['errors'][:5]:
                    print(f"  - {err['file']}: {err['error']}")

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
