"""Run Decision Dossier stage on existing claim runs (without re-running assessment).

Reads claim_facts.json, screening.json, assessment.json, and coverage_analysis.json
from the latest claim run for each claim, then runs the DecisionStage to produce
decision_dossier_v{N}.json.

Usage:
    python scripts/run_decision_dossiers.py                    # All claims
    python scripts/run_decision_dossiers.py --claim-ids 64166,64168
    python scripts/run_decision_dossiers.py --dry-run          # Preview only
    python scripts/run_decision_dossiers.py --parallel 4       # 4 workers
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

from context_builder.pipeline.claim_stages.context import ClaimContext  # noqa: E402
from context_builder.pipeline.claim_stages.decision import DecisionStage  # noqa: E402
from context_builder.storage.claim_run import ClaimRunStorage  # noqa: E402

logger = logging.getLogger(__name__)


def resolve_workspace_root() -> Path:
    """Resolve active workspace root using the startup module."""
    state = get_state()
    data_dir = state.data_dir
    if data_dir is None:
        raise ValueError("No active workspace set")
    # data_dir points to workspaces/{id}/claims — workspace root is its parent
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


def run_decision_for_claim(
    claim_id: str,
    workspace_root: Path,
    stage: DecisionStage,
) -> dict:
    """Run DecisionStage for a single claim using its latest claim run data."""
    claim_folder = workspace_root / "claims" / claim_id
    if not claim_folder.exists():
        return {"claim_id": claim_id, "status": "error", "error": "Claim folder not found"}

    crs = ClaimRunStorage(claim_folder)
    latest_run = crs.get_latest_claim_run_id()
    if not latest_run:
        return {"claim_id": claim_id, "status": "error", "error": "No claim runs found"}

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

    # Build context with existing data
    context = ClaimContext(
        claim_id=claim_id,
        workspace_path=workspace_root,
        run_id=latest_run,
        aggregated_facts=facts,
        screening_result=screening,
        processing_result=assessment,
    )

    # Run decision stage
    context = stage.run(context)

    if context.decision_result:
        verdict = context.decision_result.get("claim_verdict", "UNKNOWN")
        n_clauses = len(context.decision_result.get("clause_evaluations", []))
        n_failed = len(context.decision_result.get("failed_clauses", []))
        return {
            "claim_id": claim_id,
            "status": "ok",
            "run_id": latest_run,
            "verdict": verdict,
            "clauses_evaluated": n_clauses,
            "clauses_triggered": n_failed,
            "timing_ms": context.timings.decision_ms,
        }
    else:
        return {
            "claim_id": claim_id,
            "status": "warning",
            "run_id": latest_run,
            "error": "DecisionStage returned no result (engine may not be configured)",
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run Decision Dossier stage on existing claim runs"
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
        format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
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

    if args.dry_run:
        for cid in claim_ids:
            crs = ClaimRunStorage(workspace_root / "claims" / cid)
            latest = crs.get_latest_claim_run_id() if (workspace_root / "claims" / cid).exists() else None
            print(f"  {cid}  run={latest or '(none)'}")
        return

    # Run
    stage = DecisionStage()
    results = []
    start = time.time()

    if args.parallel <= 1:
        for i, cid in enumerate(claim_ids, 1):
            r = run_decision_for_claim(cid, workspace_root, stage)
            results.append(r)
            status = r["status"]
            detail = r.get("verdict", r.get("error", ""))
            print(f"  [{i}/{len(claim_ids)}] {cid}: {status} — {detail}")
    else:
        # Parallel: each thread gets its own DecisionStage instance
        def worker(cid):
            thread_stage = DecisionStage()
            return run_decision_for_claim(cid, workspace_root, thread_stage)

        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(worker, cid): cid for cid in claim_ids}
            done = 0
            for future in as_completed(futures):
                done += 1
                r = future.result()
                results.append(r)
                status = r["status"]
                detail = r.get("verdict", r.get("error", ""))
                print(f"  [{done}/{len(claim_ids)}] {r['claim_id']}: {status} — {detail}")

    elapsed = time.time() - start

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    warn = sum(1 for r in results if r["status"] == "warning")
    err = sum(1 for r in results if r["status"] == "error")

    print(f"\nDone in {elapsed:.1f}s — {ok} ok, {warn} warnings, {err} errors")

    if ok > 0:
        verdicts = {}
        for r in results:
            if r["status"] == "ok":
                v = r["verdict"]
                verdicts[v] = verdicts.get(v, 0) + 1
        print(f"Verdicts: {verdicts}")


if __name__ == "__main__":
    main()
