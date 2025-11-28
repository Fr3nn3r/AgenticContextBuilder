"""
Batch logic extraction script with progress tracking and resume capability.

Processes all markdown files from Azure DI acquisition using OpenAI logic extraction
and saves the extracted logic to JSON files.

Usage:
    python scripts/batch_logic_extraction.py [OPTIONS]

    Options:
        --resume / --no-resume    Resume from last position (default: True)
        --force                   Reprocess all files, ignore existing
        --start-from <filename>   Start from specific policy file

Requirements:
    - OPENAI_API_KEY environment variable
"""

import sys
import json
import logging
import argparse
import re
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from context_builder.extraction.openai_symbol_extraction import OpenAISymbolExtraction
from context_builder.extraction.openai_logic_extraction import OpenAILogicExtraction

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: Install tqdm for progress bars: pip install tqdm")

# Configure logging to suppress INFO messages during progress bar display
logging.basicConfig(
    level=logging.WARNING,  # Changed from INFO to WARNING
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChunkProgressTracker:
    """Track chunk-level progress by monitoring log output."""

    def __init__(self):
        self.current_chunk = 0
        self.total_chunks = 0
        self.chunk_desc = ""
        self.enabled = False
        self.pbar = None

    def parse_log_message(self, message: str):
        """Parse chunk progress from log messages."""
        # Match patterns like "Processing chunk 5/24" or "[Chunk 5/24]"
        chunk_match = re.search(r'(?:Processing chunk|Chunk)\s+(\d+)/(\d+)', message)
        if chunk_match:
            self.current_chunk = int(chunk_match.group(1))
            self.total_chunks = int(chunk_match.group(2))

            # Extract description
            if "Extracting rules" in message:
                self.chunk_desc = "Extracting rules"
            elif "Linting" in message:
                self.chunk_desc = "Linting"
            elif "Refinement" in message:
                self.chunk_desc = "Refining"
            elif "Step 1" in message:
                self.chunk_desc = "Extracting"
            elif "Step 2" in message:
                self.chunk_desc = "Linting"

            if self.enabled and self.pbar:
                self.pbar.update(1)
                self.pbar.set_description(f"  Chunk {self.current_chunk}/{self.total_chunks}: {self.chunk_desc}")

    def start_tracking(self, total_chunks: int):
        """Start tracking chunks with progress bar."""
        self.enabled = True
        self.total_chunks = total_chunks
        self.current_chunk = 0

        if HAS_TQDM:
            self.pbar = tqdm(
                total=total_chunks,
                desc=f"  Chunks",
                leave=False,
                ncols=80,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            )

    def stop_tracking(self):
        """Stop tracking and close progress bar."""
        self.enabled = False
        if self.pbar:
            self.pbar.close()
            self.pbar = None


def find_markdown_files(input_dir: Path) -> List[Path]:
    """
    Find all extracted markdown files in directory (non-recursive).

    Args:
        input_dir: Input directory path

    Returns:
        List of markdown file paths
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if not input_dir.is_dir():
        raise ValueError(f"Path is not a directory: {input_dir}")

    # Get all *_extracted.md files
    files = list(input_dir.glob("*_extracted.md"))
    files.sort()

    return files


def is_policy_processed(output_dir: Path, policy_stem: str) -> bool:
    """
    Check if policy has been successfully processed.

    Args:
        output_dir: Base output directory
        policy_stem: Policy stem name (without _extracted suffix)

    Returns:
        True if policy is already processed
    """
    # Check for existence of normalized logic file (main output)
    normalized_json = output_dir / policy_stem / f"{policy_stem}_normalized_logic.json"

    if not normalized_json.exists():
        return False

    # Verify file is not empty and is valid JSON
    try:
        with open(normalized_json, 'r') as f:
            data = json.load(f)
            # Check if it has rules (indicating successful extraction)
            return 'rules' in data and len(data['rules']) > 0
    except (json.JSONDecodeError, IOError):
        return False


def load_progress_state(output_dir: Path) -> Dict[str, Any]:
    """Load saved progress state."""
    progress_file = output_dir / ".extraction_progress.json"

    if not progress_file.exists():
        return {
            'last_processed': None,
            'processed_files': [],
            'started_at': None
        }

    try:
        with open(progress_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            'last_processed': None,
            'processed_files': [],
            'started_at': None
        }


def save_progress_state(output_dir: Path, state: Dict[str, Any]):
    """Save progress state."""
    progress_file = output_dir / ".extraction_progress.json"

    try:
        with open(progress_file, 'w') as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        logger.warning(f"Failed to save progress state: {e}")


def save_batch_summary(summary: Dict[str, Any], output_dir: Path):
    """Save batch processing summary to JSON file."""
    summary_path = output_dir / "batch_extraction_summary.json"

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def process_batch(
    input_dir: Path,
    output_dir: Path,
    resume: bool = True,
    force: bool = False,
    start_from: Optional[str] = None,
    continue_on_error: bool = True
) -> Dict[str, Any]:
    """
    Process all markdown files with logic extraction.

    Args:
        input_dir: Input directory containing markdown files
        output_dir: Base output directory for extraction results
        resume: If True, skip already processed files
        force: If True, reprocess all files regardless of resume
        start_from: Optional filename to start from
        continue_on_error: If True, continue processing remaining files on error

    Returns:
        Summary dictionary with processing statistics
    """
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find markdown files
    markdown_files = find_markdown_files(input_dir)

    if not markdown_files:
        print("[!] No markdown files found to process")
        return {
            'total_files': 0,
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }

    # Load progress state
    progress_state = load_progress_state(output_dir) if resume and not force else {
        'last_processed': None,
        'processed_files': [],
        'started_at': datetime.now().isoformat()
    }

    # Filter files based on start_from and resume
    if start_from:
        # Find index of start_from file
        start_idx = next((i for i, f in enumerate(markdown_files) if f.name == start_from), 0)
        markdown_files = markdown_files[start_idx:]
        print(f"[*] Starting from: {start_from}")

    # Initialize extractors
    print("[*] Initializing OpenAI extractors...")
    try:
        symbol_extractor = OpenAISymbolExtraction()
        logic_extractor = OpenAILogicExtraction()
    except Exception as e:
        print(f"[X] Failed to initialize extractors: {e}")
        print("[!] Make sure OPENAI_API_KEY is set in environment")
        raise

    # Process each markdown file
    summary = {
        'total_files': len(markdown_files),
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'errors': [],
        'results': []
    }

    print(f"\n{'='*70}")
    print(f"BATCH SYMBOL + LOGIC EXTRACTION")
    print(f"{'='*70}")
    print(f"Files to process: {len(markdown_files)}")
    print(f"Resume mode: {'ON' if resume and not force else 'OFF'}")
    print(f"{'='*70}\n")

    # Create file progress bar
    file_iterator = enumerate(markdown_files, 1)
    if HAS_TQDM:
        file_iterator = tqdm(
            file_iterator,
            total=len(markdown_files),
            desc="Policies",
            ncols=100,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
        )

    chunk_tracker = ChunkProgressTracker()

    for idx, md_path in file_iterator:
        policy_stem = md_path.stem.replace("_extracted", "")
        file_output_dir = output_dir / policy_stem
        file_output_dir.mkdir(parents=True, exist_ok=True)

        # Update progress bar description with current policy
        if HAS_TQDM:
            file_iterator.set_description(f"Policy: {policy_stem[:30]:<30}")

        # Check if already processed (resume mode)
        if resume and not force and is_policy_processed(output_dir, policy_stem):
            if not HAS_TQDM:
                print(f"[{idx}/{len(markdown_files)}] {md_path.name}")
                print(f"  [SKIP] Already processed")
            summary['skipped'] += 1
            summary['results'].append({
                'file': md_path.name,
                'status': 'skipped',
                'reason': 'already_processed'
            })
            continue

        if not HAS_TQDM:
            print(f"\n[{idx}/{len(markdown_files)}] Processing: {md_path.name}")
            print("-" * 70)

        try:
            # STEP 1: Extract symbol table
            if not HAS_TQDM:
                print(f"  [1/2] Extracting symbol table...")

            symbol_result = symbol_extractor.process(
                markdown_path=str(md_path),
                output_path=str(file_output_dir / f"{md_path.stem}_symbol_table.json")
            )

            symbol_table_path = symbol_result.get('symbol_table_json')

            # STEP 2: Extract logic using symbol table
            if not HAS_TQDM:
                print(f"  [2/2] Extracting logic...")

            result = logic_extractor.process(
                markdown_path=str(md_path),
                output_base_path=str(file_output_dir / md_path.stem.replace("_extracted", "")),
                symbol_table_json_path=symbol_table_path
            )

            # Display summary
            if not HAS_TQDM:
                print(f"  [OK] Success")
                print(f"    Policy: {result.get('policy_name', 'Unknown')}")
                print(f"    Rules: {result.get('total_rules', 0)}")
                print(f"    Sections: {result.get('total_sections', 0)}")

                # Check validation summary if available
                if '_validation_summary' in result:
                    val_summary = result['_validation_summary']
                    violations = val_summary.get('violations', 0)
                    critical = val_summary.get('critical_violations', 0)
                    warnings = val_summary.get('warnings', 0)

                    print(f"    Validation: {violations} violations ({critical} critical, {warnings} warnings)")

                # Track tokens if available
                if '_usage' in result:
                    usage = result['_usage']
                    total_tokens = usage.get('total_tokens', 0)
                    print(f"    Tokens: {total_tokens:,}")

            # Track result
            summary['processed'] += 1
            summary['results'].append({
                'file': md_path.name,
                'status': 'success',
                'policy_name': result.get('policy_name', 'Unknown'),
                'rules': result.get('total_rules', 0),
                'sections': result.get('total_sections', 0),
                'violations': result.get('_validation_summary', {}).get('violations', 0),
                'tokens': result.get('_usage', {}).get('total_tokens', 0),
                'output_dir': str(file_output_dir)
            })

            # Update progress state
            progress_state['last_processed'] = md_path.name
            progress_state['processed_files'].append(md_path.name)
            save_progress_state(output_dir, progress_state)

        except Exception as e:
            error_msg = f"Extraction error: {str(e)}"
            if not HAS_TQDM:
                print(f"  [X] Failed: {error_msg}")
            else:
                tqdm.write(f"[X] Failed {md_path.name}: {error_msg}")

            logger.exception(f"Failed to process {md_path.name}")

            summary['failed'] += 1
            summary['errors'].append({
                'file': md_path.name,
                'error': error_msg
            })
            summary['results'].append({
                'file': md_path.name,
                'status': 'failed',
                'error': error_msg
            })

            if not continue_on_error:
                raise

    return summary


def main():
    """Main entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Batch policy logic extraction with progress tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/batch_logic_extraction.py
  python scripts/batch_logic_extraction.py --no-resume --force
  python scripts/batch_logic_extraction.py --start-from policy_001_extracted.md
        """
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
    parser.add_argument(
        '--force',
        action='store_true',
        help='Reprocess all files, ignore existing outputs'
    )
    parser.add_argument(
        '--start-from',
        type=str,
        metavar='FILENAME',
        help='Start from specific policy file'
    )

    args = parser.parse_args()

    # Configuration
    INPUT_DIR = Path(r"output\acquired-policies")
    OUTPUT_DIR = Path(r"output\extracted-logic")

    # Verify input directory exists
    if not INPUT_DIR.exists():
        print(f"[X] Error: Input directory not found: {INPUT_DIR}")
        return 1

    # Process batch
    try:
        summary = process_batch(
            input_dir=INPUT_DIR,
            output_dir=OUTPUT_DIR,
            resume=args.resume,
            force=args.force,
            start_from=args.start_from,
            continue_on_error=True
        )

        # Save summary
        save_batch_summary(summary, OUTPUT_DIR)

        # Display final summary
        print(f"\n{'='*70}")
        print("BATCH PROCESSING SUMMARY")
        print(f"{'='*70}")
        print(f"Total files:     {summary['total_files']}")
        print(f"Processed:       {summary['processed']} [OK]")
        print(f"Skipped:         {summary['skipped']} [SKIP]")
        print(f"Failed:          {summary['failed']} [X]")

        # Calculate totals
        successful = [r for r in summary['results'] if r.get('status') == 'success']
        total_rules = sum(r.get('rules', 0) for r in successful)
        total_tokens = sum(r.get('tokens', 0) for r in successful)
        total_violations = sum(r.get('violations', 0) for r in successful)

        print(f"\nTotal rules extracted: {total_rules}")
        print(f"Total tokens used:     {total_tokens:,}")
        print(f"Total violations:      {total_violations}")

        if summary['errors']:
            print("\nErrors:")
            for error in summary['errors']:
                print(f"  - {error['file']}: {error['error']}")

        print(f"\nResults saved to: {OUTPUT_DIR}")
        print(f"Summary file:     {OUTPUT_DIR / 'batch_extraction_summary.json'}")
        print(f"{'='*70}")

        return 0 if summary['failed'] == 0 else 1

    except KeyboardInterrupt:
        print("\n\n[!] Process interrupted by user")
        print("[*] Progress has been saved. Use --resume to continue from last position.")
        return 130
    except Exception as e:
        logger.exception("Batch processing failed")
        print(f"\n[X] Batch processing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
