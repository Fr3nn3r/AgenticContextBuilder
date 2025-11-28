"""
Batch Azure Document Intelligence acquisition script.

Processes all documents in a specified folder (non-recursively) using Azure DI
and saves the outputs to a designated output folder.

Usage:
    python scripts/batch_azure_di_acquisition.py

Requirements:
    - AZURE_DI_ENDPOINT environment variable
    - AZURE_DI_API_KEY environment variable
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.acquisition import AcquisitionFactory, AcquisitionError
# Import Azure DI implementation to register it with factory
from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_documents(input_dir: Path) -> List[Path]:
    """
    Find all supported document files in directory (non-recursive).

    Args:
        input_dir: Input directory path

    Returns:
        List of document file paths
    """
    supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.pdf', '.tiff', '.tif'}

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"Path is not a directory: {input_dir}")

    # Get all files in directory (non-recursive)
    files = []
    for file_path in input_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            files.append(file_path)

    # Sort alphabetically
    files.sort()

    logger.info(f"Found {len(files)} documents in {input_dir}")
    for file_path in files:
        logger.info(f"  - {file_path.name}")

    return files


def save_result_json(result: Dict[str, Any], output_dir: Path, source_file: Path) -> Path:
    """
    Save acquisition result to JSON file.

    Args:
        result: Acquisition result dictionary
        output_dir: Output directory path
        source_file: Original source file path

    Returns:
        Path to saved JSON file
    """
    # Create JSON filename based on source file
    json_filename = source_file.stem + "_metadata.json"
    json_path = output_dir / json_filename

    # Make Path objects JSON serializable
    def make_serializable(obj):
        if isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(item) for item in obj]
        return obj

    serializable_result = make_serializable(result)

    # Write JSON file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_result, f, indent=2, ensure_ascii=False)

    return json_path


def process_batch(
    input_dir: Path,
    output_dir: Path,
    continue_on_error: bool = True
) -> Dict[str, Any]:
    """
    Process all documents in input directory with Azure DI.

    Args:
        input_dir: Input directory containing documents
        output_dir: Output directory for results
        continue_on_error: If True, continue processing remaining files on error

    Returns:
        Summary dictionary with processing statistics
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    # Find documents
    documents = find_documents(input_dir)

    if not documents:
        logger.warning("No documents found to process")
        return {
            'total_files': 0,
            'processed': 0,
            'failed': 0,
            'errors': []
        }

    # Initialize Azure DI acquisition
    logger.info("Initializing Azure Document Intelligence client...")
    try:
        azure_di = AcquisitionFactory.create("azure-di")

        # Configure to save markdown files in output directory
        azure_di.output_dir = output_dir
        azure_di.save_markdown = True

    except Exception as e:
        logger.error(f"Failed to initialize Azure DI client: {e}")
        logger.error("Make sure AZURE_DI_ENDPOINT and AZURE_DI_API_KEY are set in environment")
        raise

    # Process each document
    summary = {
        'total_files': len(documents),
        'processed': 0,
        'failed': 0,
        'errors': [],
        'results': []
    }

    print(f"\n{'='*60}")
    print(f"Processing {len(documents)} documents with Azure Document Intelligence")
    print(f"{'='*60}\n")

    for idx, doc_path in enumerate(documents, 1):
        print(f"[{idx}/{len(documents)}] Processing: {doc_path.name}")
        print("-" * 60)

        try:
            # Process document
            result = azure_di.process(doc_path)

            # Save JSON metadata
            json_path = save_result_json(result, output_dir, doc_path)

            # Display summary
            print(f"[OK] Success")
            print(f"  Pages: {result.get('total_pages', 0)}")
            print(f"  Tables: {result.get('table_count', 0)}")
            print(f"  Paragraphs: {result.get('paragraph_count', 0)}")
            print(f"  Language: {result.get('language', 'unknown')}")
            print(f"  Processing time: {result.get('processing_time_ms', 0)}ms")

            if result.get('markdown_file'):
                print(f"  Markdown: {result['markdown_file']}")

            print(f"  Metadata: {json_path.name}")

            # Track result
            summary['processed'] += 1
            summary['results'].append({
                'file': doc_path.name,
                'status': 'success',
                'pages': result.get('total_pages', 0),
                'json_file': json_path.name,
                'markdown_file': result.get('markdown_file')
            })

            # Warn if only 2 pages processed (free tier limit)
            if result.get('total_pages') == 2:
                print(f"  [WARNING] Free tier: Only 2 pages processed")

        except AcquisitionError as e:
            error_msg = f"Acquisition error: {str(e)}"
            logger.error(f"Failed to process {doc_path.name}: {error_msg}")

            summary['failed'] += 1
            summary['errors'].append({
                'file': doc_path.name,
                'error': error_msg
            })
            summary['results'].append({
                'file': doc_path.name,
                'status': 'failed',
                'error': error_msg
            })

            print(f"[X] Failed: {error_msg}")

            if not continue_on_error:
                raise

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"Unexpected error processing {doc_path.name}")

            summary['failed'] += 1
            summary['errors'].append({
                'file': doc_path.name,
                'error': error_msg
            })
            summary['results'].append({
                'file': doc_path.name,
                'status': 'failed',
                'error': error_msg
            })

            print(f"[X] Failed: {error_msg}")

            if not continue_on_error:
                raise

        print()

    return summary


def save_batch_summary(summary: Dict[str, Any], output_dir: Path):
    """Save batch processing summary to JSON file."""
    summary_path = output_dir / "batch_summary.json"

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Batch summary saved to: {summary_path}")


def main():
    """Main entry point."""
    # Configuration
    INPUT_DIR = Path(r"C:\Users\fbrun\Documents\GitHub\AgenticContextBuilder\data\00- Policies")
    OUTPUT_DIR = Path(r"output\acquired-policies")

    print("\n" + "="*60)
    print("BATCH AZURE DOCUMENT INTELLIGENCE ACQUISITION")
    print("="*60)
    print(f"\nInput directory:  {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Verify input directory exists
    if not INPUT_DIR.exists():
        print(f"[X] Error: Input directory not found: {INPUT_DIR}")
        return 1

    # Process batch
    try:
        summary = process_batch(
            input_dir=INPUT_DIR,
            output_dir=OUTPUT_DIR,
            continue_on_error=True
        )

        # Save summary
        save_batch_summary(summary, OUTPUT_DIR)

        # Display final summary
        print("="*60)
        print("BATCH PROCESSING SUMMARY")
        print("="*60)
        print(f"Total files:     {summary['total_files']}")
        print(f"Processed:       {summary['processed']} [OK]")
        print(f"Failed:          {summary['failed']} [X]")
        print()

        if summary['errors']:
            print("Errors:")
            for error in summary['errors']:
                print(f"  - {error['file']}: {error['error']}")
            print()

        print(f"Results saved to: {OUTPUT_DIR}")
        print(f"Summary file:     {OUTPUT_DIR / 'batch_summary.json'}")
        print("="*60)

        return 0 if summary['failed'] == 0 else 1

    except Exception as e:
        logger.exception("Batch processing failed")
        print(f"\n[X] Batch processing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
