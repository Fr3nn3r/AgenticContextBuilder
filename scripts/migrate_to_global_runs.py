#!/usr/bin/env python3
"""One-time migration script to create global run from existing claim-scoped runs."""

import json
import sys
from datetime import datetime
from pathlib import Path

def migrate_run(output_base: Path, run_id: str):
    """Create global run structure from existing claim-scoped runs."""

    claims_dir = output_base / "claims"
    global_runs_dir = output_base / "runs"

    if not claims_dir.exists():
        print(f"ERROR: Claims directory not found: {claims_dir}")
        sys.exit(1)

    # Find all claims that have this run
    claims_with_run = []
    for claim_dir in claims_dir.iterdir():
        if not claim_dir.is_dir() or claim_dir.name.startswith("."):
            continue
        run_dir = claim_dir / "runs" / run_id
        if run_dir.exists():
            claims_with_run.append({
                "claim_id": claim_dir.name,
                "claim_dir": claim_dir,
                "run_dir": run_dir,
            })

    if not claims_with_run:
        print(f"ERROR: No claims found with run_id: {run_id}")
        sys.exit(1)

    print(f"Found {len(claims_with_run)} claims with run {run_id}")

    # Create global run directory
    global_run_dir = global_runs_dir / run_id
    global_run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = global_run_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Aggregate data from all claims
    total_docs = 0
    success_docs = 0
    model = None
    earliest_start = None
    latest_end = None

    claim_entries = []
    per_claim_metrics = []

    for claim_info in claims_with_run:
        claim_id = claim_info["claim_id"]
        run_dir = claim_info["run_dir"]

        # Read claim's summary
        summary_path = run_dir / "logs" / "summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
                stats = summary.get("stats", {})
                total_docs += stats.get("total", 0)
                success_docs += stats.get("success", 0)

                completed = summary.get("completed_at")
                if completed:
                    if latest_end is None or completed > latest_end:
                        latest_end = completed

        # Read claim's manifest for model info
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                if model is None:
                    model = manifest.get("pipeline_versions", {}).get("model_name")
                started = manifest.get("started_at")
                if started:
                    if earliest_start is None or started < earliest_start:
                        earliest_start = started

        # Read claim's metrics
        metrics_path = run_dir / "logs" / "metrics.json"
        if metrics_path.exists():
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)
                per_claim_metrics.append({
                    "claim_id": claim_id,
                    "metrics": metrics,
                })

        claim_entries.append({
            "claim_id": claim_id,
            "status": "success",
            "docs_count": stats.get("total", 0) if summary_path.exists() else 0,
            "claim_run_path": str(run_dir),
        })

    # Write global manifest
    global_manifest = {
        "run_id": run_id,
        "started_at": earliest_start or datetime.now().isoformat() + "Z",
        "ended_at": latest_end or datetime.now().isoformat() + "Z",
        "command": "migrated from claim-scoped runs",
        "model": model or "gpt-4o",
        "claims_count": len(claims_with_run),
        "claims": claim_entries,
    }

    manifest_path = global_run_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(global_manifest, f, indent=2, ensure_ascii=False)
    print(f"  Created: {manifest_path}")

    # Write global summary
    global_summary = {
        "run_id": run_id,
        "status": "success",
        "claims_discovered": len(claims_with_run),
        "claims_processed": len(claims_with_run),
        "claims_failed": 0,
        "docs_total": total_docs,
        "docs_success": success_docs,
        "completed_at": latest_end or datetime.now().isoformat() + "Z",
    }

    summary_path = global_run_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(global_summary, f, indent=2, ensure_ascii=False)
    print(f"  Created: {summary_path}")

    # Write aggregated metrics
    if per_claim_metrics:
        aggregated_metrics = {
            "run_id": run_id,
            "claims_count": len(claims_with_run),
            "docs_total": total_docs,
            "docs_success": success_docs,
            "per_claim": per_claim_metrics,
        }

        metrics_path = global_run_dir / "metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(aggregated_metrics, f, indent=2, ensure_ascii=False)
        print(f"  Created: {metrics_path}")

    # Write .complete marker
    complete_path = global_run_dir / ".complete"
    complete_path.touch()
    print(f"  Created: {complete_path}")

    print(f"\nGlobal run created at: {global_run_dir}")
    print(f"  Claims: {len(claims_with_run)}")
    print(f"  Docs: {success_docs}/{total_docs}")
    print(f"  Model: {model}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_to_global_runs.py <run_id>")
        print("Example: python migrate_to_global_runs.py run_20260106_210516_a1784ec")
        sys.exit(1)

    run_id = sys.argv[1]
    output_base = Path(__file__).parent.parent / "output"

    print(f"Migrating run: {run_id}")
    print(f"Output base: {output_base}")

    migrate_run(output_base, run_id)
