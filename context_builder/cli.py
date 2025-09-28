#!/usr/bin/env python3
"""Command-line interface for document context extraction."""

import argparse
import json
import logging
import signal
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import colorlog
from dotenv import load_dotenv
from rich.console import Console

from context_builder.acquisition import (
    AcquisitionFactory,
    AcquisitionError,
    DataAcquisition,
)


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
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract structured context from documents using AI vision APIs",
        epilog="""
Examples:
  %(prog)s document.pdf                    # Process a single PDF
  %(prog)s folder/ -r                      # Process all files in folder recursively
  %(prog)s file.pdf -o results/           # Save results to specific directory
  %(prog)s doc.pdf --model gpt-4o         # Use specific model
  %(prog)s folder/ -r --max-pages 10       # Limit pages per document
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments
    parser.add_argument(
        "input_path", metavar="PATH", help="Path to the file or folder to process"
    )

    # Output options
    output_group = parser.add_argument_group("Output Options")
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

    # Provider options
    provider_group = parser.add_argument_group("Provider Options")
    available_providers = [
        "openai"
    ]  # Default list, will be extended if more are registered
    provider_group.add_argument(
        "-p",
        "--provider",
        choices=available_providers,
        default="openai",
        help="Vision API provider to use (default: openai)",
    )

    # Model configuration
    model_group = parser.add_argument_group("Model Configuration")
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

    # PDF processing options
    pdf_group = parser.add_argument_group("PDF Processing")
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

    # API options
    api_group = parser.add_argument_group("API Options")
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

    # Logging options
    logging_group = parser.add_argument_group("Logging Options")
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
    supported_extensions = DataAcquisition.SUPPORTED_EXTENSIONS
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
    provider: str = "openai",
    acquisition: Optional[DataAcquisition] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    Process a file and extract context using specified provider.

    Args:
        filepath: Path to input file
        output_dir: Directory for output JSON
        provider: Vision API provider name
        acquisition: Optional acquisition instance to reuse
        config: Optional configuration dictionary

    Returns:
        Dictionary with the processing result

    Raises:
        AcquisitionError: If processing fails
    """
    logger.info(f"Processing file: {filepath}")

    # Get or create acquisition implementation
    if acquisition is None:
        acquisition = AcquisitionFactory.create(provider)

        # Apply configuration if provided
        if config:
            for key, value in config.items():
                if value is not None and hasattr(acquisition, key):
                    setattr(acquisition, key, value)
                    logger.debug(f"Set {key}={value} on acquisition instance")

    # Process the file
    logger.info(f"Using {provider} vision API for processing")
    result = acquisition.process(filepath)

    return result


def save_single_result(
    result: dict, filepath: Path, output_dir: Path, session_id: str = None
) -> Path:
    """
    Save a single file processing result.

    Args:
        result: Processing result dictionary
        filepath: Original file path
        output_dir: Output directory
        session_id: Optional session ID to include in results

    Returns:
        Path to saved file
    """
    # Add session ID if provided
    if session_id:
        result["session_id"] = session_id

    # Generate output filename
    output_filename = f"{filepath.stem}-context.json"
    output_path = output_dir / output_filename

    # Save result
    logger.info(
        f"[Session {session_id}] Saving results to: {output_path}"
        if session_id
        else f"Saving results to: {output_path}"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return output_path


def process_folder(
    folder: Path,
    output_dir: Path,
    provider: str = "openai",
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

    # Create acquisition instance once
    acquisition = AcquisitionFactory.create(provider)

    # Apply configuration if provided
    if config:
        for key, value in config.items():
            if value is not None and hasattr(acquisition, key):
                setattr(acquisition, key, value)
                logger.debug(f"Set {key}={value} on acquisition instance")

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
            result = process_file(filepath, output_dir, provider, acquisition, config)

            if rich_output and console:
                # Simply print the result to stdout
                console.print(result)
            else:
                # Save individual result
                output_path = save_single_result(result, filepath, output_dir, session_id)
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
        logger.info(f"Processed {success_count} files successfully, {error_count} failed")
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

    # Check for mutually exclusive options
    if args.rich_output and args.verbose:
        print("[X] Error: --rich-output and -v/--verbose are mutually exclusive")
        sys.exit(1)

    # Initialize Rich console if needed
    console = None
    if args.rich_output:
        console = Console()
        # Suppress all logging when using rich output
        logging.disable(logging.CRITICAL)
    else:
        # Set up colored logging only if not using rich output
        setup_colored_logging(verbose=args.verbose)

    # Set logging level (only if not using rich output)
    if not args.rich_output:
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        elif args.quiet:
            logging.getLogger().setLevel(logging.WARNING)

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

    # Process based on input type
    try:
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
                output_path = save_single_result(result, input_path, output_dir, session_id)
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
                    console.print(f"[red][X] No supported files found in {input_path}[/red]")
                sys.exit(1)
        else:
            logger.error(f"Invalid input path: {input_path}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n[!] Process interrupted by user. Exiting gracefully...")
        sys.exit(0)

    except AcquisitionError as e:
        logger.error(f"Acquisition failed: {e}")
        print(f"[X] Failed to process: {e}")
        sys.exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"[X] Unexpected error occurred. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
