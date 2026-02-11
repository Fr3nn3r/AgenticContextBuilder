"""Backfill confidence scores for existing claim runs.

Loads extraction, reconciliation, coverage, screening, assessment, and decision
data from disk, then runs ConfidenceStage to produce confidence_summary.json
and patch the decision dossier with confidence_index.

Does NOT re-run any upstream stages -- purely reads existing data and scores it.

Usage:
    python scripts/backfill_confidence.py                    # All claims
    python scripts/backfill_confidence.py --claim-ids 64166,64168
    python scripts/backfill_confidence.py --dry-run          # Preview only
    python scripts/backfill_confidence.py --parallel 4       # 4 workers
    python scripts/backfill_confidence.py --force             # Overwrite existing
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from context_builder.startup import ensure_initialized, get_state  # noqa: E402

ensure_initialized()

from context_builder.confidence.stage import ConfidenceStage  # noqa: E402
from context_builder.pipeline.claim_stages.context import ClaimContext  # noqa: E402
from context_builder.storage.claim_run import ClaimRunStorage  # noqa: E402

logger = logging.getLogger(__name__)


def resolve_workspace_root() -> Path:
    """Resolve active workspace root using the startup module."""
    state = get_state()
    data_dir = state.data_dir
    if data_dir is None:
        raise ValueError("No active workspace set")
    return data_dir.parent


def get_all_claim_ids(workspace_root: Path) -> list[str]:
    """List all claim folder names in the workspace."""
    claims_dir = workspace_root / "claims"
    if not claims_dir.exists():
        return []
    return sorted(
        f.name for f in claims_dir.iterdir()
        if f.is_dir() and not f.name.startswith(".")
    )


def run_confidence_for_claim(
    claim_id: str,
    workspace_root: Path,
    force: bool = False,
) -> dict:
    """Run ConfidenceStage for a single claim using its latest claim run data."""
    claim_folder = workspace_root / "claims" / claim_id
    if not claim_folder.exists():
        return {"claim_id": claim_id, "status": "error", "error": "Claim folder not found"}

    crs = ClaimRunStorage(claim_folder)
    latest_run = crs.get_latest_claim_run_id()
    if not latest_run:
        return {"claim_id": claim_id, "status": "error", "error": "No claim runs found"}

    # Check if already has confidence_summary (skip unless --force)
    existing = crs.read_from_claim_run(latest_run, "confidence_summary.json")
    if existing and not force:
        score = existing.get("composite_score", "?")
        band = existing.get("band", "?")
        return {
            "claim_id": claim_id,
            "status": "skipped",
            "run_id": latest_run,
            "detail": f"Already has CCI={score} ({band})",
        }

    # Load existing data from the claim run
    facts = crs.read_from_claim_run(latest_run, "claim_facts.json")
    if not facts:
        return {
            "claim_id": claim_id,
            "status": "error",
            "error": f"No claim_facts.json in run {latest_run}",
        }

    screening = crs.read_from_claim_run(latest_run, "screening.json")
    assessment = crs.read_from_claim_run(latest_run, "assessment.json")
    reconciliation = crs.read_from_claim_run(latest_run, "reconciliation_report.json")

    # Load decision dossier (latest version)
    decision = None
    run_dir = claim_folder / "claim_runs" / latest_run
    dossier_files = sorted(run_dir.glob("decision_dossier_v*.json"))
    if dossier_files:
        try:
            with open(dossier_files[-1], "r", encoding="utf-8") as f:
                decision = json.load(f)
        except Exception:
            pass

    # Build context with existing data
    context = ClaimContext(
        claim_id=claim_id,
        workspace_path=workspace_root,
        run_id=latest_run,
        aggregated_facts=facts,
        screening_result=screening,
        reconciliation_report=reconciliation,
        processing_result=assessment,
        decision_result=decision,
    )

    # Run confidence stage
    stage = ConfidenceStage()
    context = stage.run(context)

    # Check result
    summary = crs.read_from_claim_run(latest_run, "confidence_summary.json")
    if summary:
        score = summary.get("composite_score", 0)
        band = summary.get("band", "?")
        n_signals = len(summary.get("signals_collected", []))
        return {
            "claim_id": claim_id,
            "status": "ok",
            "run_id": latest_run,
            "score": round(score, 3),
            "band": band,
            "signals": n_signals,
            "timing_ms": context.timings.confidence_ms,
        }
    else:
        return {
            "claim_id": claim_id,
            "status": "warning",
            "run_id": latest_run,
            "detail": "Stage ran but no confidence_summary.json produced",
        }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill confidence scores for existing claim runs"
    )
    parser.add_argument(
        "--claim-ids", type=str, default=None,
        help="Comma-separated claim IDs (default: all claims)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview which claims would be processed",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing confidence scores",
    )
    parser.add_argument(
        "--parallel", type=int, default=1,
        help="Number of parallel workers (default: 1)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s -- %(message)s",
        datefmt="%H:%M:%S",
    )

    workspace_root = resolve_workspace_root()
    print(f"Workspace: {workspace_root}")

    # Determine claims
    if args.claim_ids:
        claim_ids = [c.strip() for c in args.claim_ids.split(",") if c.strip()]
    else:
        claim_ids = get_all_claim_ids(workspace_root)

    print(f"Claims: {len(claim_ids)}")
    if args.force:
        print("Mode: force (overwrite existing)")

    if args.dry_run:
        for cid in claim_ids:
            folder = workspace_root / "claims" / cid
            crs = ClaimRunStorage(folder) if folder.exists() else None
            latest = crs.get_latest_claim_run_id() if crs else None
            has_cci = False
            if latest and crs:
                has_cci = crs.read_from_claim_run(latest, "confidence_summary.json") is not None
            marker = " [has CCI]" if has_cci else ""
            print(f"  {cid}  run={latest or '(none)'}{marker}")
        return

    # Run
    results = []
    start = time.time()

    if args.parallel <= 1:
        for i, cid in enumerate(claim_ids, 1):
            r = run_confidence_for_claim(cid, workspace_root, force=args.force)
            results.append(r)
            status = r["status"]
            if status == "ok":
                detail = f"CCI={r['score']} ({r['band']}, {r['signals']} signals, {r['timing_ms']}ms)"
            else:
                detail = r.get("detail", r.get("error", ""))
            print(f"  [{i}/{len(claim_ids)}] {cid}: {status} -- {detail}")
    else:
        def worker(cid):
            return run_confidence_for_claim(cid, workspace_root, force=args.force)

        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(worker, cid): cid for cid in claim_ids}
            done = 0
            for future in as_completed(futures):
                done += 1
                r = future.result()
                results.append(r)
                status = r["status"]
                if status == "ok":
                    detail = f"CCI={r['score']} ({r['band']}, {r['signals']} signals)"
                else:
                    detail = r.get("detail", r.get("error", ""))
                print(f"  [{done}/{len(claim_ids)}] {r['claim_id']}: {status} -- {detail}")

    elapsed = time.time() - start

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    warn = sum(1 for r in results if r["status"] == "warning")
    err = sum(1 for r in results if r["status"] == "error")

    print(f"\nDone in {elapsed:.1f}s -- {ok} scored, {skipped} skipped, {warn} warnings, {err} errors")

    if ok > 0:
        bands = {}
        scores = []
        for r in results:
            if r["status"] == "ok":
                b = r["band"]
                bands[b] = bands.get(b, 0) + 1
                scores.append(r["score"])
        avg = sum(scores) / len(scores)
        print(f"Bands: {bands}")
        print(f"Avg CCI: {avg:.3f}  Min: {min(scores):.3f}  Max: {max(scores):.3f}")


if __name__ == "__main__":
    main()
