# file_ingest/cli.py
# Command-line interface for the file ingestion system
# Handles argument parsing, logging configuration, and main execution

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, List

from .ingest import FileIngestor
from .utils import validate_path_exists
from .processors import registry


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for the application.

    Args:
        verbose: Enable verbose (DEBUG) logging if True
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Reduce noise from some verbose libraries
    if not verbose:
        logging.getLogger('urllib3').setLevel(logging.WARNING)


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the command-line argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description='Ingest metadata from dataset files with extensible processing pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process first 3 datasets with default settings
  python -m file_ingest datasets/ output/

  # Process specific datasets
  python -m file_ingest datasets/ output/ -d dataset1 dataset2

  # Process only certain subfolders within datasets
  python -m file_ingest datasets/ output/ -s train test

  # List available processors
  python -m file_ingest --list-processors

  # Verbose logging
  python -m file_ingest datasets/ output/ -v
        """
    )

    # Main arguments
    parser.add_argument(
        'input_folder',
        nargs='?',
        help='Path to the input datasets folder'
    )
    parser.add_argument(
        'output_folder',
        nargs='?',
        help='Path to the output folder for metadata files'
    )

    # Dataset selection options
    parser.add_argument(
        '-n', '--num-datasets',
        type=int,
        default=3,
        help='Number of datasets to process (default: 3, ignored if -d is used)'
    )
    parser.add_argument(
        '-d', '--datasets',
        nargs='*',
        help='Specific dataset names to process (optional, processes all by default)'
    )
    parser.add_argument(
        '-s', '--subfolders',
        nargs='*',
        help='Specific subfolders within datasets to process (optional, processes all by default)'
    )

    # Configuration options
    parser.add_argument(
        '-c', '--config',
        type=str,
        help='Path to configuration file (JSON format)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    # Information commands
    parser.add_argument(
        '--list-processors',
        action='store_true',
        help='List all available processors and exit'
    )
    parser.add_argument(
        '--processor-info',
        type=str,
        metavar='PROCESSOR_NAME',
        help='Show detailed information about a specific processor and exit'
    )

    return parser


def load_config(config_path: Optional[str]) -> dict:
    """
    Load configuration from a JSON file.

    Args:
        config_path: Path to the configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is not valid JSON
    """
    if not config_path:
        return {}

    config_file = Path(config_path)
    validate_path_exists(config_file, "configuration file")

    try:
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}")


def list_processors() -> None:
    """List all available processors with their information."""
    processors = registry.get_all_processor_info()

    if not processors:
        print("No processors found.")
        return

    print("Available Processors:")
    print("=" * 50)

    for name, info in processors.items():
        print(f"\n{name}")
        print(f"  Version: {info.get('version', 'Unknown')}")
        print(f"  Description: {info.get('description', 'No description')}")

        extensions = info.get('supported_extensions', [])
        if extensions:
            if '*' in extensions:
                print(f"  Supported Extensions: All files")
            else:
                print(f"  Supported Extensions: {', '.join(extensions)}")


def show_processor_info(processor_name: str) -> None:
    """
    Show detailed information about a specific processor.

    Args:
        processor_name: Name of the processor to show info for
    """
    try:
        info = registry.get_processor_info(processor_name)
        print(f"Processor: {processor_name}")
        print("=" * (len(processor_name) + 11))
        print(f"Version: {info.get('version', 'Unknown')}")
        print(f"Description: {info.get('description', 'No description')}")

        extensions = info.get('supported_extensions', [])
        if extensions:
            if '*' in extensions:
                print(f"Supported Extensions: All files")
            else:
                print(f"Supported Extensions: {', '.join(extensions)}")

        # Try to get the processor class for additional info
        try:
            processor = registry.get_processor(processor_name)
            print(f"Configuration options: {processor.config}")
        except Exception:
            pass

    except ValueError as e:
        print(f"Error: {e}")
        print(f"Available processors: {', '.join(registry.list_processors())}")


def main() -> int:
    """
    Main entry point for the CLI application.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Handle information commands first
    if args.list_processors:
        list_processors()
        return 0

    if args.processor_info:
        show_processor_info(args.processor_info)
        return 0

    # Check required arguments for main processing
    if not args.input_folder or not args.output_folder:
        parser.error("input_folder and output_folder are required for processing")

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Validate input paths
        input_path = Path(args.input_folder)
        output_path = Path(args.output_folder)

        validate_path_exists(input_path, "input folder")
        validate_path_exists(input_path, "directory")

        # Load configuration
        config = load_config(args.config)
        logger.info(f"Loaded configuration: {config}")

        # Create ingestor and process datasets
        ingestor = FileIngestor(config)

        result = ingestor.ingest_multiple_datasets(
            input_path=input_path,
            output_path=output_path,
            num_datasets=args.num_datasets,
            specific_datasets=args.datasets,
            subfolders_filter=args.subfolders
        )

        logger.info("Ingestion completed successfully")
        return 0

    except (FileNotFoundError, NotADirectoryError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Ingestion cancelled by user")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())