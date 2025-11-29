"""
Batch PDF processing pipeline with end-to-end orchestration.

Processes PDFs through the complete pipeline:
PDF → Azure DI → Symbol Extraction → Logic Extraction

Each PDF gets its own timestamped processing folder with all outputs.

Usage:
    python scripts/batch_pdf_pipeline.py --input-dir <path-to-pdfs>
    python scripts/batch_pdf_pipeline.py --input-dir data/pdfs/ --output-dir output/processing/
    python scripts/batch_pdf_pipeline.py --input-dir data/pdfs/ --no-resume

Requirements:
    - AZURE_DI_ENDPOINT environment variable
    - AZURE_DI_API_KEY environment variable
    - OPENAI_API_KEY environment variable
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from context_builder.pipeline.processing_orchestrator import PolicyProcessingOrchestrator
from context_builder.extraction.progress_callback import NoOpProgressCallback
from context_builder.extraction.tqdm_progress_callback import TqdmProgressCallback
# Import Azure DI implementation to register it with factory
from context_builder.impl.azure_di_acquisition import AzureDocumentIntelligenceAcquisition

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: Install tqdm for progress bars: pip install tqdm")

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO messages during progress bar display
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_pdf_files(input_dir: Path) -> List[Path]:
    """
    Find all PDF files in directory (non-recursive).

    Args:
        input_dir: Input directory path

    Returns:
        List of PDF file paths
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"Path is not a directory: {input_dir}")

    # Get all PDF files
    files = list(input_dir.glob("*.pdf"))
    files.sort()

    return files


def is_processing_complete(processing_folder: Path) -> bool:
    """
    Check if processing is complete for a folder.

    A folder is complete if it has a processing_summary.json with status="success".

    Args:
        processing_folder: Path to processing folder

    Returns:
        True if processing is complete
    """
    summary_file = processing_folder / "processing_summary.json"

    if not summary_file.exists():
        return False

    try:
        with open(summary_file, 'r') as f:
            summary = json.load(f)
            return summary.get('status') == 'success'
    except (json.JSONDecodeError, IOError):
        return False


def find_existing_processing_folder(
    output_base_dir: Path,
    pdf_name: str
) -> Path | None:
    """
    Find existing processing folder for a PDF (for resume mode).

    Looks for folders matching pattern: *-{pdf_stem}

    Args:
        output_base_dir: Base output directory
        pdf_name: PDF filename

    Returns:
        Path to processing folder if found, None otherwise
    """
    pdf_stem = Path(pdf_name).stem

    if not output_base_dir.exists():
        return None

    # Look for folders ending with the PDF stem
    for folder in output_base_dir.iterdir():
        if folder.is_dir() and folder.name.endswith(pdf_stem):
            return folder

    return None


def process_batch(
    input_dir: Path,
    output_base_dir: Path,
    resume: bool = True,
    continue_on_error: bool = True
) -> Dict[str, Any]:
    """
    Process all PDFs in input directory through complete pipeline.

    Args:
        input_dir: Input directory containing PDFs
        output_base_dir: Base directory for processing folders
        resume: If True, skip already processed PDFs
        continue_on_error: If True, continue processing remaining files on error

    Returns:
        Summary dictionary with processing statistics
    """
    # Create output directory
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # Find PDF files
    pdf_files = find_pdf_files(input_dir)

    if not pdf_files:
        print("[!] No PDF files found to process")
        return {
            'total_files': 0,
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }

    # Initialize orchestrator
    print("[*] Initializing processing orchestrator...")
    orchestrator = PolicyProcessingOrchestrator()

    # Process summary
    summary = {
        'total_files': len(pdf_files),
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'errors': [],
        'results': []
    }

    print(f"\n{'='*70}")
    print(f"BATCH PDF PROCESSING PIPELINE")
    print(f"{'='*70}")
    print(f"PDFs to process: {len(pdf_files)}")
    print(f"Resume mode: {'ON' if resume else 'OFF'}")
    print(f"{'='*70}\n")

    # Create file progress bar
    file_iterator = enumerate(pdf_files, 1)
    file_pbar = None
    if HAS_TQDM:
        file_pbar = tqdm(
            file_iterator,
            total=len(pdf_files),
            desc="PDFs",
            ncols=100,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )
        file_iterator = file_pbar

    for idx, pdf_path in file_iterator:
        pdf_name = pdf_path.name

        # Update progress bar description
        if HAS_TQDM:
            file_pbar.set_description(f"PDF: {pdf_name[:35]:<35}")

        # Check if already processed (resume mode)
        if resume:
            existing_folder = find_existing_processing_folder(output_base_dir, pdf_name)
            if existing_folder and is_processing_complete(existing_folder):
                if not HAS_TQDM:
                    print(f"[{idx}/{len(pdf_files)}] {pdf_name}")
                    print(f"  [SKIP] Already processed in {existing_folder.name}")

                summary['skipped'] += 1
                summary['results'].append({
                    'file': pdf_name,
                    'status': 'skipped',
                    'reason': 'already_processed',
                    'folder': str(existing_folder)
                })
                continue

        if not HAS_TQDM:
            print(f"\n[{idx}/{len(pdf_files)}] Processing: {pdf_name}")
            print("-" * 70)

        # Create stage progress bar for this file (4 stages)
        stage_pbar = None
        if HAS_TQDM:
            stage_pbar = tqdm(
                total=4,
                desc="Stage",
                ncols=100,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}',
                leave=False  # Don't leave the bar after completion
            )

        # Create progress callback with both file and stage bars
        progress_callback = TqdmProgressCallback(file_pbar, stage_pbar) if HAS_TQDM else NoOpProgressCallback()

        try:
            # Process PDF through pipeline
            result = orchestrator.process_pdf(
                pdf_path,
                output_base_dir,
                progress_callback=progress_callback
            )

            # Close stage bar after processing
            if stage_pbar:
                stage_pbar.close()

            # Display summary
            if not HAS_TQDM:
                print(f"  [OK] Success")
                print(f"    Folder: {Path(result['processing_folder']).name}")
                print(f"    Pages: {result['acquisition']['pages']}")
                print(f"    Rules: {result['logic']['total_rules']}")
                print(f"    Chunks: {result['logic']['chunk_count']}")
                print(f"    Violations: {result['logic']['violations']}")
                print(f"    Time: {result['processing_time_seconds']}s")

            summary['processed'] += 1
            summary['results'].append({
                'file': pdf_name,
                'status': 'success',
                'folder': result['processing_folder'],
                'pages': result['acquisition']['pages'],
                'rules': result['logic']['total_rules'],
                'chunks': result['logic']['chunk_count'],
                'violations': result['logic']['violations'],
                'time': result['processing_time_seconds']
            })

        except Exception as e:
            # Close stage bar on error
            if stage_pbar:
                stage_pbar.close()

            error_msg = f"Processing error: {str(e)}"
            if not HAS_TQDM:
                print(f"  [X] Failed: {error_msg}")
            else:
                tqdm.write(f"[X] Failed {pdf_name}: {error_msg}")

            logger.exception(f"Failed to process {pdf_name}")

            summary['failed'] += 1
            summary['errors'].append({
                'file': pdf_name,
                'error': error_msg
            })
            summary['results'].append({
                'file': pdf_name,
                'status': 'failed',
                'error': error_msg
            })

            if not continue_on_error:
                raise

    return summary


def save_batch_summary(summary: Dict[str, Any], output_dir: Path):
    """Save batch processing summary to JSON file."""
    summary_path = output_dir / "batch_pipeline_summary.json"

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Batch summary saved to: {summary_path}")


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Batch PDF processing pipeline (Acquisition → Symbols → Logic)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/batch_pdf_pipeline.py --input-dir data/pdfs/
  python scripts/batch_pdf_pipeline.py --input-dir data/pdfs/ --output-dir output/processing/
  python scripts/batch_pdf_pipeline.py --input-dir data/pdfs/ --no-resume
        """
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        required=True,
        help='Input directory containing PDF files'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output/processing',
        help='Base output directory for processing folders (default: output/processing)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        default=True,
        help='Resume from last position (default: True)'
    )
    parser.add_argument(
        '--no-resume',
        dest='resume',
        action='store_false',
        help='Do not resume, process all files'
    )

    args = parser.parse_args()

    # Convert to Path objects and resolve to absolute paths
    # Strip quotes and trailing slashes/backslashes that may come from shell escaping
    input_dir = Path(args.input_dir.strip('\'"').rstrip('\\/').strip('\'"')).resolve()
    output_dir = Path(args.output_dir.strip('\'"').rstrip('\\/').strip('\'"')).resolve()

    # Verify input directory exists
    if not input_dir.exists():
        print(f"[X] Error: Input directory not found: {input_dir}")
        return 1

    # Process batch
    try:
        summary = process_batch(
            input_dir=input_dir,
            output_base_dir=output_dir,
            resume=args.resume,
            continue_on_error=True
        )

        # Save summary
        save_batch_summary(summary, output_dir)

        # Display final summary
        print(f"\n{'='*70}")
        print("BATCH PROCESSING SUMMARY")
        print(f"{'='*70}")
        print(f"Total PDFs:      {summary['total_files']}")
        print(f"Processed:       {summary['processed']} [OK]")
        print(f"Skipped:         {summary['skipped']} [SKIP]")
        print(f"Failed:          {summary['failed']} [X]")

        # Calculate totals
        successful = [r for r in summary['results'] if r.get('status') == 'success']
        total_rules = sum(r.get('rules', 0) for r in successful)
        total_pages = sum(r.get('pages', 0) for r in successful)
        total_violations = sum(r.get('violations', 0) for r in successful)
        total_time = sum(r.get('time', 0) for r in successful)

        print(f"\nTotal pages processed: {total_pages}")
        print(f"Total rules extracted: {total_rules}")
        print(f"Total violations:      {total_violations}")
        print(f"Total processing time: {total_time:.1f}s")

        if summary['errors']:
            print("\nErrors:")
            for error in summary['errors']:
                print(f"  - {error['file']}: {error['error']}")

        print(f"\nResults saved to: {output_dir}")
        print(f"Summary file:     {output_dir / 'batch_pipeline_summary.json'}")
        print(f"{'='*70}")

        return 0 if summary['failed'] == 0 else 1

    except KeyboardInterrupt:
        print("\n\n[!] Process interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Batch processing failed")
        print(f"\n[X] Batch processing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
