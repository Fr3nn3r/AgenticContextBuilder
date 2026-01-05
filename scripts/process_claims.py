#!/usr/bin/env python
"""
Process claims into tidy folder structure with classification and extraction.

Usage:
    python scripts/process_claims.py --input data/04-Claims-Motor-Ecuador --output output/claims
    python scripts/process_claims.py --input data/04-Claims-Motor-Ecuador/some-claim --output output/claims
    python scripts/process_claims.py --input ... --force
    python scripts/process_claims.py --input ... --claim-id specific-claim
    python scripts/process_claims.py --input ... --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from context_builder.classification import ClassifierFactory
from context_builder.extraction.base import generate_run_id
from context_builder.pipeline.discovery import DiscoveredClaim, discover_claims
from context_builder.pipeline.run import ClaimResult, process_claim
from context_builder.pipeline.state import is_claim_processed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def filter_claims(
    claims: List[DiscoveredClaim],
    output_base: Path,
    claim_id_filter: str | None,
    limit: int | None,
    force: bool,
) -> List[DiscoveredClaim]:
    """Filter claims based on CLI options."""
    # Filter by claim_id if specified
    if claim_id_filter:
        claims = [c for c in claims if c.claim_id == claim_id_filter]
        if not claims:
            logger.warning(f"No claim found with ID: {claim_id_filter}")

    # Filter already processed (unless --force)
    if not force:
        original_count = len(claims)
        claims = [c for c in claims if not is_claim_processed(output_base, c.claim_id)]
        skipped = original_count - len(claims)
        if skipped > 0:
            logger.info(f"Skipping {skipped} already processed claims")

    # Apply limit
    if limit and len(claims) > limit:
        claims = claims[:limit]
        logger.info(f"Limited to {limit} claims")

    return claims


def print_summary(results: List[ClaimResult]) -> None:
    """Print processing summary."""
    total_claims = len(results)
    success_claims = sum(1 for r in results if r.status == "success")
    partial_claims = sum(1 for r in results if r.status == "partial")
    failed_claims = sum(1 for r in results if r.status == "failed")
    skipped_claims = sum(1 for r in results if r.status == "skipped")

    total_docs = sum(r.stats.get("total", 0) for r in results)
    success_docs = sum(r.stats.get("success", 0) for r in results)
    error_docs = sum(r.stats.get("errors", 0) for r in results)

    # Source type counts
    pdf_docs = sum(r.stats.get("pdfs", 0) for r in results)
    image_docs = sum(r.stats.get("images", 0) for r in results)
    text_docs = sum(r.stats.get("texts", 0) for r in results)

    total_time = sum(r.time_seconds for r in results)

    print("\n" + "=" * 50)
    print("PROCESSING SUMMARY")
    print("=" * 50)
    print(f"Claims:    {total_claims} total")
    print(f"           {success_claims} success, {partial_claims} partial, {failed_claims} failed, {skipped_claims} skipped")
    print(f"Documents: {total_docs} total, {success_docs} success, {error_docs} errors")
    if pdf_docs or image_docs or text_docs:
        print(f"           {pdf_docs} PDFs, {image_docs} images, {text_docs} pre-extracted")
    print(f"Time:      {total_time:.1f} seconds")
    print("=" * 50)

    # Show errors if any
    errors = []
    for r in results:
        for doc in r.documents:
            if doc.error:
                errors.append(f"  [{r.claim_id}] {doc.original_filename}: {doc.error}")

    if errors:
        print("\nERRORS:")
        for err in errors[:10]:  # Show first 10
            print(err)
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process claims into tidy folder structure with classification and extraction"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Input path (claim folder or parent of claim folders)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("output/claims"),
        help="Output base directory (default: output/claims)",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force reprocessing even if already done",
    )
    parser.add_argument(
        "--claim-id",
        type=str,
        default=None,
        help="Process only a specific claim ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of claims to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without doing it",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Discover claims
    print(f"[..] Discovering claims from: {args.input}")
    try:
        claims = discover_claims(args.input)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(f"[ERROR] {e}")
        return 1

    total_docs = sum(len(c.documents) for c in claims)
    print(f"[OK] Found {len(claims)} claims with {total_docs} documents")

    # Filter claims
    claims = filter_claims(
        claims,
        args.output,
        args.claim_id,
        args.limit,
        args.force,
    )

    if not claims:
        print("[OK] No claims to process")
        return 0

    filtered_docs = sum(len(c.documents) for c in claims)
    print(f"[OK] {len(claims)} claims need processing ({filtered_docs} documents)")

    # Dry run mode
    if args.dry_run:
        print("\n[DRY RUN] Would process:")
        for claim in claims:
            print(f"  {claim.claim_id}: {len(claim.documents)} docs")
            for doc in claim.documents[:3]:
                # Handle encoding issues on Windows console
                try:
                    print(f"    - {doc.original_filename}")
                except UnicodeEncodeError:
                    safe_name = doc.original_filename.encode("ascii", "replace").decode()
                    print(f"    - {safe_name}")
            if len(claim.documents) > 3:
                print(f"    ... and {len(claim.documents) - 3} more")
        return 0

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Initialize classifier once
    print("[..] Initializing classifier...")
    classifier = ClassifierFactory.create("openai")

    # Generate run ID for this batch
    run_id = generate_run_id()
    print(f"[OK] Run ID: {run_id}")

    # Process claims
    print(f"\n[..] Processing {len(claims)} claims...")
    results: List[ClaimResult] = []

    for i, claim in enumerate(claims, 1):
        print(f"\n[{i}/{len(claims)}] Processing: {claim.claim_id} ({len(claim.documents)} docs)")

        result = process_claim(
            claim=claim,
            output_base=args.output,
            classifier=classifier,
            run_id=run_id,
            force=args.force,
        )
        results.append(result)

    # Print summary
    print_summary(results)
    print(f"\nOutput: {args.output.absolute()}")

    # Return non-zero if any failures
    has_failures = any(r.status == "failed" for r in results)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
