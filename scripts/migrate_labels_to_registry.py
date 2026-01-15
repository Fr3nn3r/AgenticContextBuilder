#!/usr/bin/env python3
"""
Migrate labels from claim-scoped storage to global registry.

This script moves labels from:
  claims/{claim}/docs/{doc_id}/labels/latest.json
  claims/{claim}/docs/{doc_id}/labels/history.jsonl

To:
  registry/labels/{doc_id}.json
  registry/labels/{doc_id}_history.jsonl

This fixes the bug where the same doc_id in multiple claims causes labels
to be saved/loaded from the wrong location.
"""

import json
import shutil
from pathlib import Path


def migrate_workspace(workspace_path: Path) -> dict:
    """Migrate labels for a single workspace.

    Returns dict with migration stats.
    """
    claims_dir = workspace_path / "claims"
    registry_dir = workspace_path / "registry"
    labels_registry_dir = registry_dir / "labels"

    stats = {
        "workspace": str(workspace_path),
        "labels_found": 0,
        "labels_migrated": 0,
        "history_migrated": 0,
        "already_exists": 0,
        "errors": [],
    }

    if not claims_dir.exists():
        print(f"  No claims directory at {claims_dir}")
        return stats

    # Ensure registry/labels directory exists
    labels_registry_dir.mkdir(parents=True, exist_ok=True)

    # Find all label files
    for claim_folder in claims_dir.iterdir():
        if not claim_folder.is_dir():
            continue

        docs_dir = claim_folder / "docs"
        if not docs_dir.exists():
            continue

        for doc_folder in docs_dir.iterdir():
            if not doc_folder.is_dir():
                continue

            doc_id = doc_folder.name
            old_labels_dir = doc_folder / "labels"
            old_latest = old_labels_dir / "latest.json"
            old_history = old_labels_dir / "history.jsonl"

            new_latest = labels_registry_dir / f"{doc_id}.json"
            new_history = labels_registry_dir / f"{doc_id}_history.jsonl"

            if old_latest.exists():
                stats["labels_found"] += 1

                if new_latest.exists():
                    # Already migrated - skip
                    stats["already_exists"] += 1
                    continue

                try:
                    # Copy latest.json
                    shutil.copy2(old_latest, new_latest)
                    stats["labels_migrated"] += 1
                    print(f"  Migrated: {doc_id} (from {claim_folder.name})")

                    # Copy history.jsonl if exists
                    if old_history.exists():
                        shutil.copy2(old_history, new_history)
                        stats["history_migrated"] += 1

                except Exception as e:
                    stats["errors"].append(f"{doc_id}: {e}")
                    print(f"  ERROR: {doc_id} - {e}")

    return stats


def main():
    """Migrate labels for all workspaces."""
    project_root = Path(__file__).parent.parent
    workspaces_config = project_root / ".contextbuilder" / "workspaces.json"

    if not workspaces_config.exists():
        print(f"Workspaces config not found: {workspaces_config}")
        return

    with open(workspaces_config, "r", encoding="utf-8") as f:
        config = json.load(f)

    workspaces = config.get("workspaces", [])

    print("=" * 60)
    print("Label Migration: claim-scoped -> registry")
    print("=" * 60)
    print()

    all_stats = []

    for ws in workspaces:
        ws_path = Path(ws["path"])
        ws_name = ws["name"]

        print(f"Workspace: {ws_name}")
        print(f"  Path: {ws_path}")

        if not ws_path.exists():
            print(f"  SKIPPED: Path does not exist")
            print()
            continue

        stats = migrate_workspace(ws_path)
        all_stats.append(stats)

        print(f"  Found: {stats['labels_found']}")
        print(f"  Migrated: {stats['labels_migrated']}")
        print(f"  History: {stats['history_migrated']}")
        print(f"  Already existed: {stats['already_exists']}")
        if stats["errors"]:
            print(f"  Errors: {len(stats['errors'])}")
        print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    total_found = sum(s["labels_found"] for s in all_stats)
    total_migrated = sum(s["labels_migrated"] for s in all_stats)
    total_history = sum(s["history_migrated"] for s in all_stats)
    total_existed = sum(s["already_exists"] for s in all_stats)
    total_errors = sum(len(s["errors"]) for s in all_stats)

    print(f"Total labels found: {total_found}")
    print(f"Total migrated: {total_migrated}")
    print(f"Total history migrated: {total_history}")
    print(f"Already existed (skipped): {total_existed}")
    print(f"Total errors: {total_errors}")

    if total_errors > 0:
        print("\nErrors:")
        for stats in all_stats:
            for error in stats["errors"]:
                print(f"  - {error}")


if __name__ == "__main__":
    main()
