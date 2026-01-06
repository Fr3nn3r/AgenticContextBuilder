#!/usr/bin/env python3
"""
Migration script: Move labels from runs/{run_id}/labels/ to docs/{doc_id}/labels/

This script:
1. Scans all runs for label files
2. For each doc_id, finds the most recent label (by reviewed_at timestamp)
3. Copies to docs/{doc_id}/labels/latest.json
4. Creates labels/ folder if needed

Usage:
    python scripts/migrate_labels_to_docs.py [--dry-run] [--output-dir PATH]
"""

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_timestamp(ts: str) -> datetime:
    """Parse ISO timestamp string to datetime."""
    try:
        # Handle both with and without timezone
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return datetime.min


def find_all_labels(claims_dir: Path) -> dict[str, list[dict]]:
    """
    Find all label files across all runs.

    Returns dict: doc_id -> list of {path, data, timestamp}
    """
    labels_by_doc: dict[str, list[dict]] = defaultdict(list)

    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        runs_dir = claim_dir / "runs"
        if not runs_dir.exists():
            continue

        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir() or not run_dir.name.startswith("run_"):
                continue

            labels_dir = run_dir / "labels"
            if not labels_dir.exists():
                continue

            for label_file in labels_dir.glob("*.labels.json"):
                doc_id = label_file.stem.replace(".labels", "")

                try:
                    with open(label_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Extract timestamp
                    reviewed_at = data.get("review", {}).get("reviewed_at", "")
                    timestamp = parse_timestamp(reviewed_at)

                    labels_by_doc[doc_id].append({
                        "path": label_file,
                        "data": data,
                        "timestamp": timestamp,
                        "claim_dir": claim_dir,
                    })
                except (json.JSONDecodeError, IOError) as e:
                    print(f"  Warning: Could not read {label_file}: {e}")

    return labels_by_doc


def find_doc_folder(claims_dir: Path, doc_id: str) -> Path | None:
    """Find the docs/{doc_id} folder for a given doc_id."""
    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        doc_folder = claim_dir / "docs" / doc_id
        if doc_folder.exists():
            return doc_folder

    return None


def migrate_labels(claims_dir: Path, dry_run: bool = False) -> dict:
    """
    Migrate labels from run-scoped to doc-scoped storage.

    Returns migration stats.
    """
    stats = {
        "docs_processed": 0,
        "labels_migrated": 0,
        "labels_skipped": 0,
        "errors": [],
    }

    print(f"Scanning for labels in {claims_dir}...")
    labels_by_doc = find_all_labels(claims_dir)

    print(f"Found labels for {len(labels_by_doc)} documents")

    for doc_id, label_entries in labels_by_doc.items():
        stats["docs_processed"] += 1

        # Sort by timestamp descending to get most recent first
        label_entries.sort(key=lambda x: x["timestamp"], reverse=True)

        most_recent = label_entries[0]

        # Find the doc folder
        doc_folder = find_doc_folder(claims_dir, doc_id)
        if not doc_folder:
            # Try using the claim_dir from the label entry
            doc_folder = most_recent["claim_dir"] / "docs" / doc_id

        if not doc_folder.exists():
            stats["errors"].append(f"Doc folder not found for {doc_id}")
            continue

        # Target path
        labels_folder = doc_folder / "labels"
        target_path = labels_folder / "latest.json"

        # Check if already migrated
        if target_path.exists():
            print(f"  {doc_id}: Already has latest.json, skipping")
            stats["labels_skipped"] += 1
            continue

        print(f"  {doc_id}: Migrating from {most_recent['path'].parent.parent.name}")
        if len(label_entries) > 1:
            print(f"    (had {len(label_entries)} versions, using most recent)")

        if not dry_run:
            # Create labels folder
            labels_folder.mkdir(parents=True, exist_ok=True)

            # Write the label file
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(most_recent["data"], f, indent=2, ensure_ascii=False)

        stats["labels_migrated"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate labels from runs/ to docs/ structure"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/claims"),
        help="Path to claims directory (default: output/claims)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    claims_dir = args.output_dir
    if not claims_dir.exists():
        print(f"Error: Claims directory not found: {claims_dir}")
        return 1

    if args.dry_run:
        print("=== DRY RUN MODE ===\n")

    stats = migrate_labels(claims_dir, dry_run=args.dry_run)

    print("\n=== Migration Summary ===")
    print(f"Documents processed: {stats['docs_processed']}")
    print(f"Labels migrated: {stats['labels_migrated']}")
    print(f"Labels skipped (already migrated): {stats['labels_skipped']}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats["errors"]:
            print(f"  - {error}")

    if args.dry_run:
        print("\n(No changes made - dry run mode)")

    return 0


if __name__ == "__main__":
    exit(main())
