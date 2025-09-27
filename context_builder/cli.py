# context_builder/cli.py
# File and folder context processor CLI with progress tracking

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from tqdm import tqdm

from .ingest import FileIngestor
from .utils import validate_path_exists


class SensitiveDataFilter(logging.Filter):
    """Filter that removes sensitive data and unwanted log records."""

    def filter(self, record):
        """Return False to drop the record, True to keep it."""
        # Filter out HTTP request/response details
        if 'HTTP/' in record.getMessage() or 'urllib3' in record.name:
            return False

        # Filter out binary data patterns
        msg = record.getMessage()
        if any(pattern in msg for pattern in [
            'b\'\\x', 'b"\\x',  # Binary data
            'Request:', 'Response:',  # HTTP details
            'POST ', 'GET ',  # HTTP methods
            'Content-Type:', 'Authorization:',  # Headers
        ]):
            return False

        # Redact authorization headers if present in the message
        if 'Authorization:' in msg:
            record.msg = record.msg.replace(
                record.msg[record.msg.find('Authorization:'):record.msg.find('\n', record.msg.find('Authorization:'))],
                'Authorization: [REDACTED]'
            )

        return True


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application with filtering."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(levelname)s - %(message)s'

    # Create standard handler with formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(format_str))

    # Add the sensitive data filter to the handler
    handler.addFilter(SensitiveDataFilter())

    logging.basicConfig(
        level=level,
        handlers=[handler]
    )

    # Suppress noisy loggers
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('httpx').setLevel(logging.ERROR)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.ERROR)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description='Process files or folders to generate context metadata',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process single file
  python -m context_builder input.pdf output/ -c config/default_ai_config.json

  # Process entire folder
  python -m context_builder input_folder/ output_folder/ -c config/metadata_only_config.json

  # Verbose mode
  python -m context_builder input.pdf output/ -c config/default_ai_config.json -v
        """
    )

    parser.add_argument(
        'input',
        help='Path to input file or folder'
    )
    parser.add_argument(
        'output_folder',
        help='Path to output folder for context files'
    )
    parser.add_argument(
        '-c', '--config',
        type=str,
        required=True,
        help='Path to configuration file (JSON format)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--validate-config',
        action='store_true',
        help='Validate configuration and exit without processing'
    )

    return parser


def load_config(config_path: str) -> dict:
    """Load configuration from a JSON file."""
    config_file = Path(config_path)
    validate_path_exists(config_file, "configuration file")

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")
    except OSError as e:
        raise ValueError(f"Cannot read configuration file: {e}")


def process_single_file(
    file_path: Path,
    output_path: Path,
    ingestor: 'FileIngestor',
    logger: logging.Logger,
    pbar: Optional[tqdm] = None,
    file_num: int = 1,
    total_files: int = 1
) -> Tuple[bool, Optional[dict], Optional[str]]:
    """
    Process a single file and return processing status.

    Args:
        file_path: Path to file to process
        output_path: Path to output directory
        ingestor: FileIngestor instance to use for processing
        logger: Logger instance
        pbar: Optional progress bar
        file_num: Current file number
        total_files: Total number of files

    Returns:
        Tuple of (success, metadata_dict, error_message)
    """
    try:
        # Update progress bar description
        if pbar:
            pbar.set_description(f"[{file_num}/{total_files}] {file_path.name[:50]}")

        logger.debug(f"Processing: {file_path}")

        # Process the file using ingest_file method
        metadata = ingestor.ingest_file(file_path)

        # Determine output file path maintaining structure
        output_file = output_path / f"{file_path.stem}_context.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Save metadata
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved to: {output_file}")

        if pbar:
            pbar.update(1)

        return True, metadata, None

    except Exception as e:
        error_msg = f"Failed to process {file_path.name}: {str(e)}"
        logger.exception(error_msg)  # This logs the full stack trace

        # Create error output file
        output_file = output_path / f"{file_path.stem}_context.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        error_data = {
            "error": True,
            "error_message": str(e),
            "file_path": str(file_path),
            "timestamp": datetime.now().isoformat()
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2)

        if pbar:
            pbar.update(1)

        return False, None, str(e)


def process_folder(
    input_folder: Path,
    intake_folder: Path,
    config: dict,
    logger: logging.Logger
) -> Tuple[List[dict], bool]:
    """
    Process all files in a folder recursively with progress tracking.

    Returns:
        Tuple of (list of processing results for each file, interrupted flag)
    """
    results = []
    interrupted = False

    # Find all files recursively
    all_files = [f for f in input_folder.rglob('*') if f.is_file()]
    total_files = len(all_files)

    logger.info(f"Found {total_files} files to process")

    # Create FileIngestor once for all files
    logger.info("Initializing processing pipeline...")
    ingestor = FileIngestor(config)
    logger.info("Pipeline initialized successfully")

    # Create progress bar
    with tqdm(total=total_files,
              desc="Processing files",
              unit="file",
              bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:

        start_time = time.time()

        for idx, file_path in enumerate(all_files, 1):
            try:
                # Maintain folder structure in intake folder
                relative_path = file_path.relative_to(input_folder)
                output_subfolder = intake_folder / relative_path.parent

                # Process file using shared ingestor
                success, metadata, error = process_single_file(
                    file_path, output_subfolder, ingestor, logger, pbar, idx, total_files
                )

                results.append({
                    "file": str(file_path),
                    "relative_path": str(relative_path),
                    "success": success,
                    "error": error,
                    "timestamp": datetime.now().isoformat()
                })

            except KeyboardInterrupt:
                logger.info("\n" + "="*60)
                logger.info("Processing interrupted by user (Ctrl+C)")
                logger.info(f"Processed {idx-1} of {total_files} files before interruption")
                interrupted = True
                # Add remaining files as not processed
                for remaining_file in all_files[idx:]:
                    rel_path = remaining_file.relative_to(input_folder)
                    results.append({
                        "file": str(remaining_file),
                        "relative_path": str(rel_path),
                        "success": False,
                        "error": "Processing interrupted by user",
                        "timestamp": datetime.now().isoformat()
                    })
                break

    return results, interrupted


def generate_summary_report(
    input_path: Path,
    intake_folder: Path,
    ingestion_id: str,
    config: dict,
    results: List[dict],
    processing_time: float,
    interrupted: bool = False
) -> dict:
    """Generate a summary report of the processing."""
    # Count successes and failures
    successful = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])

    # Separate interrupted files from failed
    interrupted_count = sum(1 for r in results if not r["success"] and r.get("error") == "Processing interrupted by user")

    # Extract processor pipeline info from config
    processors_info = []
    for processor_config in config.get("processors", []):
        processor_info = {
            "name": processor_config.get("name"),
            "enabled": processor_config.get("enabled", True)
        }

        # Add extraction methods if ContentProcessor
        if processor_config.get("name") == "ContentProcessor":
            extraction_methods = processor_config.get("config", {}).get("extraction_methods", {})
            enabled_methods = [
                method for method, cfg in extraction_methods.items()
                if cfg.get("enabled", False)
            ]
            processor_info["extraction_methods"] = enabled_methods

        processors_info.append(processor_info)

    summary = {
        "ingestion_id": ingestion_id,
        "timestamp": datetime.now().isoformat(),
        "input_path": str(input_path),
        "output_path": str(intake_folder),
        "config_file": config.get("_config_path", "unknown"),
        "processing_time_seconds": processing_time,
        "statistics": {
            "total_files": len(results),
            "successful": successful,
            "failed": failed - interrupted_count,  # Subtract interrupted from failed
            "interrupted": interrupted_count,
            "success_rate": f"{(successful/len(results)*100):.1f}%" if results else "0%",
            "processing_status": "interrupted" if interrupted else "completed"
        },
        "pipeline": {
            "processors": processors_info
        },
        "files_processed": results
    }

    return summary


def validate_configuration(config_path: str, logger: logging.Logger) -> int:
    """Validate configuration file and prerequisites.

    Args:
        config_path: Path to configuration file
        logger: Logger instance

    Returns:
        0 if valid, 1 if invalid
    """
    try:
        # Load and parse configuration
        config = load_config(config_path)
        logger.info("[OK] Configuration file loaded successfully")

        # Check processors
        processors = config.get('processors', [])
        if not processors:
            logger.warning("[WARNING] No processors configured")
        else:
            logger.info(f"[OK] Found {len(processors)} processor(s)")

        # Check for AI processor requirements
        has_content_processor = any(
            p.get('name') == 'ContentProcessor' and p.get('enabled', True)
            for p in processors
        )

        if has_content_processor:
            # Check AI configuration
            content_config = next(
                (p for p in processors if p.get('name') == 'ContentProcessor'),
                {}
            )
            ai_config = content_config.get('config', {}).get('ai', {})

            if ai_config.get('enabled', True):
                # Check OpenAI API key
                import os
                from dotenv import load_dotenv
                load_dotenv()

                api_key = os.getenv('OPENAI_API_KEY') or ai_config.get('api_key')
                if not api_key:
                    logger.error("[X] OPENAI_API_KEY not found in environment or config")
                    logger.info("    Set OPENAI_API_KEY in .env file or disable AI in config")
                    return 1
                else:
                    logger.info("[OK] OpenAI API key configured")

                # Check prompt files
                prompt_config = ai_config.get('prompt_config', {})
                prompt_file = prompt_config.get('prompt_file')
                if prompt_file:
                    prompt_path = Path(prompt_file)
                    if not prompt_path.exists():
                        logger.error(f"[X] Prompt file not found: {prompt_file}")
                        return 1
                    else:
                        logger.info(f"[OK] Prompt file exists: {prompt_file}")

            # Check extraction methods
            extraction_methods = content_config.get('config', {}).get('extraction_methods', {})
            enabled_methods = [
                method for method, cfg in extraction_methods.items()
                if cfg.get('enabled', False)
            ]

            if not enabled_methods:
                logger.warning("[WARNING] No extraction methods enabled")
            else:
                logger.info(f"[OK] Enabled extraction methods: {', '.join(enabled_methods)}")

                # Check OCR requirements
                if 'ocr_tesseract' in enabled_methods:
                    try:
                        import pytesseract
                        pytesseract.get_tesseract_version()
                        logger.info("[OK] Tesseract OCR is available")
                    except Exception as e:
                        logger.warning(f"[WARNING] Tesseract OCR not available: {e}")
                        logger.info("    Install Tesseract or disable ocr_tesseract in config")

        # Validate output configuration
        output_config = config.get('output', {})
        if output_config:
            logger.info(f"[OK] Output format: {output_config.get('format', 'json')}")

        logger.info("="*60)
        logger.info("[OK] Configuration is valid and ready to use")
        return 0

    except FileNotFoundError as e:
        logger.error(f"[X] Configuration file not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"[X] Invalid configuration: {e}")
        return 1
    except Exception as e:
        logger.exception(f"[X] Unexpected error during validation: {e}")
        return 1


def main() -> int:
    """Main entry point for the context processor CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging with filtering
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Handle configuration validation mode
    if args.validate_config:
        logger.info("Running configuration validation...")
        return validate_configuration(args.config, logger)

    try:
        # Record start time
        start_time = datetime.now()

        # Validate paths
        input_path = Path(args.input)
        output_base_path = Path(args.output_folder)

        if not input_path.exists():
            logger.error(f"Input path does not exist: {input_path}")
            return 1

        # Generate unique ingestion ID and create intake folder
        import random
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(5)])
        ingestion_id = f"{timestamp}_{random_suffix}"
        intake_folder_name = f"intake_{ingestion_id}"
        intake_folder = output_base_path / intake_folder_name

        # Create intake folder
        intake_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"Starting ingestion {ingestion_id}")
        logger.info(f"Output folder: {intake_folder}")

        # Load configuration
        config = load_config(args.config)
        config["_config_path"] = args.config  # Store for summary

        # Process based on input type
        interrupted = False
        if input_path.is_file():
            # Single file processing
            logger.info(f"Processing single file: {input_path.name}")

            # Create FileIngestor for single file
            logger.info("Initializing processing pipeline...")
            ingestor = FileIngestor(config)
            logger.info("Pipeline initialized successfully")

            with tqdm(total=1, desc=f"Processing {input_path.name[:50]}", unit="file") as pbar:
                success, metadata, error = process_single_file(
                    input_path, intake_folder, ingestor, logger, pbar, 1, 1
                )

            results = [{
                "file": str(input_path),
                "relative_path": input_path.name,
                "success": success,
                "error": error,
                "timestamp": datetime.now().isoformat()
            }]
        else:
            # Folder processing
            logger.info(f"Processing folder: {input_path}")
            results, interrupted = process_folder(input_path, intake_folder, config, logger)

        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()

        # Generate summary report
        summary = generate_summary_report(
            input_path, intake_folder, ingestion_id, config, results, processing_time, interrupted
        )

        # Save summary report in intake folder
        summary_path = intake_folder / "processing_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # Print final summary
        stats = summary["statistics"]
        logger.info("=" * 60)
        if interrupted:
            logger.info(f"Processing INTERRUPTED for ingestion {ingestion_id}")
        else:
            logger.info(f"Processing complete for ingestion {ingestion_id}")
        logger.info(f"Files processed: {stats['successful'] + stats['failed']}/{stats['total_files']}")
        logger.info(f"Successful: {stats['successful']}")
        logger.info(f"Failed: {stats['failed']}")
        if stats.get('interrupted', 0) > 0:
            logger.info(f"Interrupted: {stats['interrupted']} (not processed)")
        logger.info(f"Success rate: {stats['success_rate']}")
        logger.info(f"Processing time: {processing_time:.2f} seconds")
        logger.info(f"Summary saved to: {summary_path}")

        return 0 if stats['failed'] == 0 else 1

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Processing cancelled by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")  # Always log full stack trace for unexpected errors
        return 1


if __name__ == '__main__':
    sys.exit(main())