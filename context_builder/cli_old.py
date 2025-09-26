# intake/cli.py
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
  # Process with content enrichment (requires OPENAI_API_KEY)
  python -m context_builder datasets/ output/ -c config/default_ai_config.json

  # Process metadata only (no AI)
  python -m context_builder datasets/ output/ -c config/metadata_only_config.json

  # Process specific datasets with AI
  python -m context_builder datasets/ output/ -c config/default_ai_config.json -d dataset1 dataset2

  # Process only certain subfolders
  python -m context_builder datasets/ output/ -c config/default_ai_config.json -s train test

  # List available processors
  python -m context_builder --list-processors

  # Verbose logging
  python -m context_builder datasets/ output/ -c config/default_ai_config.json -v
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
        help='Path to configuration file (JSON format). '
             'Use config/default_config.json for default processing'
    )
    parser.add_argument(
        '--extraction-methods',
        type=str,
        help='Comma-separated list of extraction methods to use '
             '(e.g., ocr_tesseract,vision_openai). '
             'Overrides config file settings. Use "all" for all available methods.'
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
    parser.add_argument(
        '--validate-config',
        action='store_true',
        help='Validate configuration file and check extraction method requirements'
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


def validate_config_command(config_path: str) -> int:
    """
    Validate a configuration file and check extraction method requirements.

    Args:
        config_path: Path to configuration file

    Returns:
        Exit code (0 for valid, 1 for invalid)
    """
    print(f"Validating configuration: {config_path}")
    print("=" * 50)

    try:
        # Load configuration
        config = load_config(config_path)

        # Check overall structure
        if 'processors' not in config:
            print("[X] Invalid config: missing 'processors' section")
            return 1

        print("[OK] Configuration structure is valid")

        # Check for ContentProcessor and validate extraction methods
        has_content_processor = False
        for processor in config.get('processors', []):
            if processor.get('name') == 'ContentProcessor':
                has_content_processor = True
                proc_config = processor.get('config', {})
                extraction_methods = proc_config.get('extraction_methods', {})

                if not extraction_methods:
                    print("[!] No extraction methods configured (will use defaults)")
                else:
                    print("\nExtraction Methods:")
                    from .processors.content_support.extractors import get_registry
                    registry = get_registry()

                    # Validate extraction methods
                    errors = registry.validate_configuration(extraction_methods)

                    if errors:
                        print("\n[X] Configuration errors:")
                        for error in errors:
                            print(f"  - {error}")
                        return 1

                    # Show status of each method
                    for method_name, method_config in extraction_methods.items():
                        enabled = method_config.get('enabled', False)
                        priority = method_config.get('priority', 999)
                        status = "[OK] Enabled" if enabled else "[ ] Disabled"
                        print(f"  {method_name}: {status} (priority: {priority})")

                        # Check if method is available
                        if enabled and method_name in registry.get_registered_methods():
                            if registry.is_method_available(method_name):
                                print(f"    [OK] Requirements met")
                            else:
                                print(f"    [!] Requirements not met (missing libraries or API key)")

        if not has_content_processor:
            print("\n[i] ContentProcessor not configured (metadata only mode)")

        print("\n[OK] Configuration is valid")
        return 0

    except FileNotFoundError:
        print(f"[X] Configuration file not found: {config_path}")
        return 1
    except ValueError as e:
        print(f"[X] Invalid configuration: {e}")
        return 1
    except Exception as e:
        print(f"[X] Unexpected error: {e}")
        return 1


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

    # Handle config validation
    if args.validate_config:
        if not args.config:
            parser.error("--validate-config requires -c/--config to specify configuration file")
        return validate_config_command(args.config)

    # Check required arguments for main processing
    if not args.input_folder or not args.output_folder:
        parser.error("input_folder and output_folder are required for processing")

    if not args.config:
        parser.error("Configuration file is required. Use -c config/default_config.json for default processing")

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Validate input paths
        input_path = Path(args.input_folder)
        output_path = Path(args.output_folder)

        validate_path_exists(input_path, "directory")

        # Load configuration
        config = load_config(args.config)

        # Override extraction methods if specified
        if args.extraction_methods:
            # Parse extraction methods
            if args.extraction_methods.lower() == 'all':
                # Enable all available methods
                from .processors.content_support.extractors import get_registry
                registry = get_registry()
                available_methods = registry.get_registered_methods()

                # Update config to enable all methods
                for processor in config.get('processors', []):
                    if processor.get('name') == 'ContentProcessor':
                        if 'config' not in processor:
                            processor['config'] = {}
                        processor['config']['extraction_methods'] = {
                            method: {'enabled': True, 'priority': i+1, 'config': {}}
                            for i, method in enumerate(available_methods)
                        }
            else:
                # Enable specific methods
                methods = [m.strip() for m in args.extraction_methods.split(',')]

                # Update config to use specified methods
                for processor in config.get('processors', []):
                    if processor.get('name') == 'ContentProcessor':
                        if 'config' not in processor:
                            processor['config'] = {}
                        # Disable all methods first
                        if 'extraction_methods' in processor['config']:
                            for method in processor['config']['extraction_methods']:
                                processor['config']['extraction_methods'][method]['enabled'] = False
                        else:
                            processor['config']['extraction_methods'] = {}

                        # Enable specified methods
                        for i, method in enumerate(methods):
                            processor['config']['extraction_methods'][method] = {
                                'enabled': True,
                                'priority': i+1,
                                'config': {}
                            }

        if args.verbose:
            logger.debug(f"Loaded configuration: {config}")
        else:
            logger.info(f"Loaded configuration from {args.config}")

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