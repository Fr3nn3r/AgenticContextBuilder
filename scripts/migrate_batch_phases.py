#!/usr/bin/env python3
"""Migration script to backfill aggregated phases in global run summary.json files.

This script reads per-claim summaries and aggregates their phases data into the
global run summary.json, enabling the batch overview cards to show correct counts.

Usage:
    python scripts/migrate_batch_phases.py [workspace_path] [--dry-run]

Options:
    workspace_path  Path to workspace (default: uses active workspace)
    --dry-run       Preview changes without writing files
"""

import argparse
import json
import sys
from pathlib import Path


def get_active_workspace() -> Path:
    """Get active workspace path from .contextbuilder/workspaces.json."""
    # Walk up to find repo root (where .contextbuilder/ lives)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    workspaces_config = repo_root / ".contextbuilder" / "workspaces.json"
    if not workspaces_config.exists():
        print(f"ERROR: Workspaces config not found: {workspaces_config}")
        sys.exit(1)

    with open(workspaces_config, "r", encoding="utf-8") as f:
        config = json.load(f)

    active_id = config.get("active_workspace")
    if not active_id:
        print("ERROR: No active workspace set in workspaces.json")
        sys.exit(1)

    for ws in config.get("workspaces", []):
        if ws.get("id") == active_id:
            ws_path = Path(ws.get("path", ""))
            if ws_path.is_absolute():
                return ws_path
            return repo_root / ws_path

    print(f"ERROR: Active workspace '{active_id}' not found in config")
    sys.exit(1)


def aggregate_phases_for_run(workspace: Path, run_id: str) -> dict:
    """Aggregate phases from per-claim summaries for a run.

    Args:
        workspace: Path to workspace directory.
        run_id: Run identifier.

    Returns:
        Aggregated phases dict with ingestion, classification,
        extraction, and quality_gate metrics.
    """
    phases = {
        "ingestion": {"discovered": 0, "ingested": 0, "skipped": 0, "failed": 0},
        "classification": {"classified": 0, "low_confidence": 0, "distribution": {}},
        "extraction": {"attempted": 0, "succeeded": 0, "failed": 0},
        "quality_gate": {"pass": 0, "warn": 0, "fail": 0},
    }

    claims_dir = workspace / "claims"
    if not claims_dir.exists():
        return phases

    claims_found = 0

    # Find all claims that have this run
    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue

        summary_path = claim_dir / "runs" / run_id / "logs" / "summary.json"
        if not summary_path.exists():
            continue

        claims_found += 1

        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                claim_summary = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: Could not read {summary_path}: {e}")
            continue

        if "phases" not in claim_summary:
            continue

        claim_phases = claim_summary["phases"]

        # Ingestion
        ing = claim_phases.get("ingestion", {})
        phases["ingestion"]["discovered"] += ing.get("discovered", 0)
        phases["ingestion"]["ingested"] += ing.get("ingested", 0)
        phases["ingestion"]["skipped"] += ing.get("skipped", 0)
        phases["ingestion"]["failed"] += ing.get("failed", 0)

        # Classification
        clf = claim_phases.get("classification", {})
        phases["classification"]["classified"] += clf.get("classified", 0)
        phases["classification"]["low_confidence"] += clf.get("low_confidence", 0)
        for doc_type, count in clf.get("distribution", {}).items():
            phases["classification"]["distribution"][doc_type] = (
                phases["classification"]["distribution"].get(doc_type, 0) + count
            )

        # Extraction
        ext = claim_phases.get("extraction", {})
        phases["extraction"]["attempted"] += ext.get("attempted", 0)
        phases["extraction"]["succeeded"] += ext.get("succeeded", 0)
        phases["extraction"]["failed"] += ext.get("failed", 0)

        # Quality gate
        qg = claim_phases.get("quality_gate", {})
        phases["quality_gate"]["pass"] += qg.get("pass", 0)
        phases["quality_gate"]["warn"] += qg.get("warn", 0)
        phases["quality_gate"]["fail"] += qg.get("fail", 0)

    return phases


def migrate_run(workspace: Path, run_id: str, dry_run: bool) -> tuple[bool, str]:
    """Migrate a single run's summary.json to include aggregated phases.

    Args:
        workspace: Path to workspace directory.
        run_id: Run identifier.
        dry_run: If True, preview changes without writing.

    Returns:
        Tuple of (success, message).
    """
    summary_path = workspace / "runs" / run_id / "summary.json"

    if not summary_path.exists():
        return False, "summary.json not found"

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return False, f"Could not read summary.json: {e}"

    # Check if already migrated
    if "phases" in summary:
        # Check if phases has actual data (not all zeros)
        phases = summary["phases"]
        ing = phases.get("ingestion", {})
        clf = phases.get("classification", {})
        ext = phases.get("extraction", {})
        has_data = (
            ing.get("ingested", 0) > 0
            or clf.get("classified", 0) > 0
            or ext.get("succeeded", 0) > 0
        )
        if has_data:
            return False, "Already has phases data"

    # Aggregate phases from per-claim summaries
    aggregated_phases = aggregate_phases_for_run(workspace, run_id)

    # Check if we found any data
    total_ingested = aggregated_phases["ingestion"]["ingested"]
    total_classified = aggregated_phases["classification"]["classified"]
    total_extracted = aggregated_phases["extraction"]["succeeded"]

    if total_ingested == 0 and total_classified == 0 and total_extracted == 0:
        return False, "No per-claim phases data found"

    # Update summary with phases
    summary["phases"] = aggregated_phases

    if dry_run:
        return True, f"Would add phases (ing={total_ingested}, clf={total_classified}, ext={total_extracted})"

    # Write updated summary
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        return True, f"Added phases (ing={total_ingested}, clf={total_classified}, ext={total_extracted})"
    except IOError as e:
        return False, f"Could not write summary.json: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="Backfill aggregated phases in global run summary.json files."
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        help="Path to workspace (default: uses active workspace)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    args = parser.parse_args()

    # Determine workspace path
    if args.workspace:
        workspace = Path(args.workspace)
        if not workspace.is_absolute():
            workspace = Path.cwd() / workspace
    else:
        workspace = get_active_workspace()

    if not workspace.exists():
        print(f"ERROR: Workspace not found: {workspace}")
        sys.exit(1)

    runs_dir = workspace / "runs"
    if not runs_dir.exists():
        print(f"No runs directory found: {runs_dir}")
        sys.exit(0)

    print(f"Workspace: {workspace}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'MIGRATE'}")
    print()

    migrated = 0
    skipped = 0
    errors = 0

    # Process all runs
    run_dirs = sorted(runs_dir.iterdir(), key=lambda p: p.name)
    for run_dir in run_dirs:
        if not run_dir.is_dir() or run_dir.name.startswith("."):
            continue

        run_id = run_dir.name
        success, message = migrate_run(workspace, run_id, args.dry_run)

        if success:
            print(f"  [MIGRATE] {run_id}: {message}")
            migrated += 1
        elif "not found" in message.lower() or "no per-claim" in message.lower():
            print(f"  [SKIP] {run_id}: {message}")
            skipped += 1
        elif "already" in message.lower():
            print(f"  [OK] {run_id}: {message}")
            skipped += 1
        else:
            print(f"  [ERROR] {run_id}: {message}")
            errors += 1

    print()
    print(f"Summary: {migrated} migrated, {skipped} skipped, {errors} errors")

    if args.dry_run and migrated > 0:
        print()
        print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
