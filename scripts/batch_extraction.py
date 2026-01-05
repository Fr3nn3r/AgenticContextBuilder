"""
Batch extraction script - runs after batch_claims_processing.py

Processes classified documents and extracts structured fields with provenance.

Usage:
    python scripts/batch_extraction.py --run-dir output/claims-processed/run-YYYYMMDD-HHMMSS
    python scripts/batch_extraction.py --run-dir ... --doc-types loss_notice,police_report
    python scripts/batch_extraction.py --run-dir ... --limit 10

Requirements:
    - OPENAI_API_KEY environment variable
    - Run directory from batch_claims_processing.py with:
      - inventory.json (documents with doc_type from classification)
      - extraction/*_acquired.md (Azure DI markdown)
"""

import sys
import json
import logging
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from context_builder.extraction import (
    ExtractorFactory,
    parse_azure_di_markdown,
    generate_run_id,
)
from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractionRunMetadata,
    DocumentMetadata,
    PageContent,
)

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Note: Install tqdm for progress bars: pip install tqdm")

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supported document types for extraction
SUPPORTED_DOC_TYPES = {"loss_notice", "police_report", "insurance_policy"}


@dataclass
class ExtractionStats:
    """Statistics for an extraction run."""
    total_docs: int = 0
    extracted: int = 0
    skipped: int = 0
    errors: int = 0
    by_doc_type: Dict[str, int] = None
    by_status: Dict[str, int] = None

    def __post_init__(self):
        if self.by_doc_type is None:
            self.by_doc_type = {}
        if self.by_status is None:
            self.by_status = {"pass": 0, "warn": 0, "fail": 0}


def compute_md5(content: str) -> str:
    """Compute MD5 hash of content."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def find_acquired_markdown(extraction_dir: Path, filename: str) -> Optional[Path]:
    """
    Find the Azure DI markdown file for a document.

    Azure DI creates files like: original_name_acquired.md
    """
    # Remove extension from original filename
    base_name = Path(filename).stem

    # Try common patterns
    patterns = [
        f"{base_name}_acquired.md",
        f"{base_name}.md",
    ]

    for pattern in patterns:
        md_path = extraction_dir / pattern
        if md_path.exists():
            return md_path

    # Try fuzzy match (handle spaces vs underscores)
    base_normalized = base_name.replace(" ", "_").replace("-", "_").lower()
    for md_file in extraction_dir.glob("*_acquired.md"):
        file_normalized = md_file.stem.replace(" ", "_").replace("-", "_").lower()
        if base_normalized in file_normalized or file_normalized in base_normalized:
            return md_file

    return None


def read_inventory(claim_dir: Path) -> List[Dict[str, Any]]:
    """Read inventory.json from claim directory."""
    inventory_path = claim_dir / "inventory.json"
    if not inventory_path.exists():
        return []

    with open(inventory_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("files", [])


def process_document(
    doc_info: Dict[str, Any],
    claim_id: str,
    extraction_dir: Path,
    run_id: str,
    model: str = "gpt-4o",
) -> Optional[ExtractionResult]:
    """
    Process a single document for extraction.

    Args:
        doc_info: Document info from inventory.json
        claim_id: Parent claim ID
        extraction_dir: Directory with Azure DI markdown files
        run_id: Extraction run ID
        model: LLM model to use

    Returns:
        ExtractionResult or None if extraction not possible
    """
    filename = doc_info.get("filename", "")
    doc_type = doc_info.get("document_type", "")
    language = doc_info.get("language", "es")
    md5 = doc_info.get("md5", "")

    # Skip unsupported doc types
    if doc_type not in SUPPORTED_DOC_TYPES:
        return None

    # Find Azure DI markdown
    md_path = find_acquired_markdown(extraction_dir, filename)
    if not md_path:
        logger.warning(f"No Azure DI markdown found for {filename}")
        return None

    # Read and parse markdown
    markdown_text = md_path.read_text(encoding="utf-8")
    parsed_pages = parse_azure_di_markdown(markdown_text)

    if not parsed_pages:
        logger.warning(f"No pages parsed from {md_path}")
        return None

    # Convert to PageContent objects
    pages = [
        PageContent(
            page=p.page,
            text=p.text,
            text_md5=p.text_md5,
        )
        for p in parsed_pages
    ]

    # Build document metadata
    doc_id = f"{claim_id}_{Path(filename).stem}"
    doc_meta = DocumentMetadata(
        doc_id=doc_id,
        claim_id=claim_id,
        doc_type=doc_type,
        doc_type_confidence=0.9,  # From classification
        language=language,
        page_count=len(pages),
    )

    # Build run metadata
    di_text = "\n".join(p.text for p in pages)
    run_meta = ExtractionRunMetadata(
        run_id=run_id,
        extractor_version="v1.0.0",
        model=model,
        prompt_version="generic_extraction_v1",
        input_hashes={
            "source_md5": md5,
            "di_text_md5": compute_md5(di_text),
        },
    )

    # Get extractor and run extraction
    try:
        extractor = ExtractorFactory.create(doc_type, model=model)
        result = extractor.extract(pages, doc_meta, run_meta)
        return result
    except Exception as e:
        logger.error(f"Extraction failed for {filename}: {e}")
        return None


def write_extraction_result(result: ExtractionResult, output_path: Path):
    """Write extraction result to JSON file with atomic write."""
    # Write to temp file first
    temp_path = output_path.with_suffix(".tmp")

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2, ensure_ascii=False, default=str)

    # Atomic rename
    temp_path.replace(output_path)


def process_claim_folder(
    claim_dir: Path,
    run_id: str,
    doc_types: Optional[set] = None,
    model: str = "gpt-4o",
) -> tuple[int, int, int, Dict[str, int]]:
    """
    Process all documents in a claim folder.

    Returns:
        Tuple of (extracted_count, skipped_count, error_count, status_counts)
    """
    extracted = 0
    skipped = 0
    errors = 0
    status_counts = {"pass": 0, "warn": 0, "fail": 0}

    extraction_dir = claim_dir / "extraction"
    if not extraction_dir.exists():
        return 0, 0, 0, status_counts

    # Read inventory
    inventory = read_inventory(claim_dir)
    claim_id = claim_dir.name

    for doc_info in inventory:
        doc_type = doc_info.get("document_type", "")

        # Filter by doc types if specified
        if doc_types and doc_type not in doc_types:
            skipped += 1
            continue

        # Skip unsupported types
        if doc_type not in SUPPORTED_DOC_TYPES:
            skipped += 1
            continue

        # Process document
        result = process_document(
            doc_info, claim_id, extraction_dir, run_id, model
        )

        if result:
            # Write result
            filename = doc_info.get("filename", "unknown")
            safe_name = Path(filename).stem.replace(" ", "_")
            output_path = extraction_dir / f"{safe_name}.extraction.json"
            write_extraction_result(result, output_path)

            extracted += 1
            status = result.quality_gate.status
            status_counts[status] = status_counts.get(status, 0) + 1
        else:
            errors += 1

    return extracted, skipped, errors, status_counts


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured fields from classified documents"
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Run directory from batch_claims_processing.py",
    )
    parser.add_argument(
        "--doc-types",
        type=str,
        default=None,
        help="Comma-separated doc types to extract (default: all supported)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="OpenAI model for extraction (default: gpt-4o)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of claims to process",
    )

    args = parser.parse_args()

    # Validate run directory
    if not args.run_dir.exists():
        print(f"[X] Run directory not found: {args.run_dir}")
        return 1

    # Parse doc types filter
    doc_types = None
    if args.doc_types:
        doc_types = set(args.doc_types.split(","))
        invalid = doc_types - SUPPORTED_DOC_TYPES
        if invalid:
            print(f"[!] Unsupported doc types: {invalid}")
            doc_types = doc_types & SUPPORTED_DOC_TYPES

    print(f"[OK] Run directory: {args.run_dir}")
    print(f"[OK] Model: {args.model}")
    print(f"[OK] Doc types: {doc_types or 'all supported'}")

    # Find claim folders
    claim_folders = [
        d for d in args.run_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]
    claim_folders.sort()

    if args.limit:
        claim_folders = claim_folders[:args.limit]
        print(f"[OK] Limited to {len(claim_folders)} claims")

    print(f"[OK] Found {len(claim_folders)} claim folders")

    # Generate run ID
    run_id = generate_run_id()
    print(f"[OK] Run ID: {run_id}")

    # Process claims
    stats = ExtractionStats()

    if HAS_TQDM:
        folder_iter = tqdm(claim_folders, desc="Extracting", unit="claim")
    else:
        folder_iter = claim_folders

    for claim_dir in folder_iter:
        if HAS_TQDM:
            folder_iter.set_postfix_str(claim_dir.name[:30])
        else:
            print(f"  Processing: {claim_dir.name}")

        extracted, skipped, errors, status_counts = process_claim_folder(
            claim_dir, run_id, doc_types, args.model
        )

        stats.total_docs += extracted + skipped + errors
        stats.extracted += extracted
        stats.skipped += skipped
        stats.errors += errors

        for status, count in status_counts.items():
            stats.by_status[status] = stats.by_status.get(status, 0) + count

    # Print summary
    print(f"\n{'='*60}")
    print("Extraction complete!")
    print(f"  Total documents: {stats.total_docs}")
    print(f"  Extracted: {stats.extracted}")
    print(f"  Skipped: {stats.skipped}")
    print(f"  Errors: {stats.errors}")
    print(f"\nQuality gate results:")
    print(f"  Pass: {stats.by_status.get('pass', 0)}")
    print(f"  Warn: {stats.by_status.get('warn', 0)}")
    print(f"  Fail: {stats.by_status.get('fail', 0)}")

    return 0 if stats.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
