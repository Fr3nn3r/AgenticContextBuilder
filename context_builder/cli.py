#!/usr/bin/env python3
"""Command-line interface for document context extraction."""

import argparse
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from context_builder.acquisition import AcquisitionFactory, AcquisitionError, DataAcquisition

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    print("\n[!] Process interrupted by user. Exiting gracefully...")
    sys.exit(0)


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


def setup_argparser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract structured context from documents using AI vision APIs"
    )
    parser.add_argument(
        "input_path",
        type=str,
        help="Path to the file or folder to process"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default=".",
        help="Output directory for JSON results (default: current directory)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Process folder recursively (when input is a folder)"
    )
    parser.add_argument(
        "-p", "--provider",
        type=str,
        default="openai",
        choices=["openai"],
        help="Vision API provider to use (default: openai)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
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
        for ext in supported_extensions:
            files.extend(folder.rglob(f"*{ext}"))
    else:
        for ext in supported_extensions:
            files.extend(folder.glob(f"*{ext}"))

    # Sort files for consistent ordering
    return sorted(files)


def process_file(
    filepath: Path,
    output_dir: Path,
    provider: str = "openai",
    acquisition: Optional[DataAcquisition] = None
) -> dict:
    """
    Process a file and extract context using specified provider.

    Args:
        filepath: Path to input file
        output_dir: Directory for output JSON
        provider: Vision API provider name
        acquisition: Optional acquisition instance to reuse

    Returns:
        Dictionary with the processing result

    Raises:
        AcquisitionError: If processing fails
    """
    logger.info(f"Processing file: {filepath}")

    # Get or create acquisition implementation
    if acquisition is None:
        acquisition = AcquisitionFactory.create(provider)

    # Process the file
    logger.info(f"Using {provider} vision API for processing")
    result = acquisition.process(filepath)

    return result


def save_single_result(result: dict, filepath: Path, output_dir: Path) -> Path:
    """
    Save a single file processing result.

    Args:
        result: Processing result dictionary
        filepath: Original file path
        output_dir: Output directory

    Returns:
        Path to saved file
    """
    # Generate output filename
    output_filename = f"{filepath.stem}-context.json"
    output_path = output_dir / output_filename

    # Save result
    logger.info(f"Saving results to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return output_path


def process_folder(
    folder: Path,
    output_dir: Path,
    provider: str = "openai",
    recursive: bool = False
) -> int:
    """
    Process all files in a folder, each to its own output file.

    Args:
        folder: Folder to process
        output_dir: Output directory
        provider: Vision API provider
        recursive: Whether to search recursively

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

    success_count = 0
    error_count = 0
    output_files = []

    for i, filepath in enumerate(files, 1):
        logger.info(f"[{i}/{len(files)}] Processing: {filepath}")

        try:
            # Process the file
            result = process_file(filepath, output_dir, provider, acquisition)

            # Save individual result
            output_path = save_single_result(result, filepath, output_dir)
            output_files.append(output_path)
            success_count += 1

        except KeyboardInterrupt:
            logger.info(f"Interrupted. Processed {success_count} files before interruption.")
            raise  # Re-raise to be caught by main handler

        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            error_count += 1

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

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate input path
    input_path = Path(args.input_path)
    if not input_path.exists():
        logger.error(f"Path not found: {input_path}")
        sys.exit(1)

    # Validate output directory
    output_dir = Path(args.output_dir)
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

    # Process based on input type
    try:
        if input_path.is_file():
            # Process single file
            result = process_file(
                filepath=input_path,
                output_dir=output_dir,
                provider=args.provider
            )
            output_path = save_single_result(result, input_path, output_dir)
            logger.info(f"Successfully processed file. Output: {output_path}")
            print(f"[OK] Context extracted to: {output_path}")

        elif input_path.is_dir():
            # Process folder
            success_count = process_folder(
                folder=input_path,
                output_dir=output_dir,
                provider=args.provider,
                recursive=args.recursive
            )
            if success_count > 0:
                logger.info(f"Successfully processed {success_count} files")
                print(f"[OK] Processed {success_count} files. Contexts saved to: {output_dir}")
            else:
                print(f"[X] No supported files found in {input_path}")
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