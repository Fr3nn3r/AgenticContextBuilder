"""Run the decision engine on specified claims.

Usage:
    python scripts/run_decision.py                    # Run on default 4 seed claims
    python scripts/run_decision.py 64166 64168        # Run on specific claims
    python scripts/run_decision.py --all              # Run on all claims with data

Loads the NSA decision engine, finds the latest claim run for each claim,
reads facts/screening/coverage/assessment data, evaluates, and writes
a versioned decision_dossier_v{N}.json to the claim run directory.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src and project root to path (project root needed for workspace imports)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from context_builder.pipeline.claim_stages.decision import load_engine_from_workspace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

WORKSPACE_PATH = Path(__file__).resolve().parent.parent / "workspaces" / "nsa"
SEED_CLAIMS = ["64166", "64168", "64288", "64297"]


def load_json(path: Path):
    """Load a JSON file, returning None if missing or broken."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load %s: %s", path.name, e)
        return None


def get_latest_run(claim_folder: Path) -> tuple:
    """Return (run_id, run_dir) for the most recent claim run, or (None, None)."""
    runs_dir = claim_folder / "claim_runs"
    if not runs_dir.exists():
        return None, None

    run_dirs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    if not run_dirs:
        return None, None
    return run_dirs[0].name, run_dirs[0]


def get_next_version(run_dir: Path) -> int:
    """Find next dossier version number by scanning existing files."""
    existing = list(run_dir.glob("decision_dossier_v*.json"))
    if not existing:
        return 1

    max_v = 0
    for f in existing:
        try:
            v = int(f.stem.split("_v")[-1])
            max_v = max(max_v, v)
        except (ValueError, IndexError):
            continue
    return max_v + 1


def run_decision(claim_ids: list[str]):
    """Run the decision engine on the given claim IDs."""
    claims_dir = WORKSPACE_PATH / "claims"

    # Load engine
    logger.info("Loading NSA decision engine from %s", WORKSPACE_PATH)
    engine = load_engine_from_workspace(WORKSPACE_PATH)
    if engine is None:
        logger.error("Failed to load decision engine — check workspace config")
        sys.exit(1)

    logger.info(
        "Engine: %s v%s (%d clauses)",
        engine.engine_id,
        engine.engine_version,
        len(engine.get_clause_registry()),
    )

    results = []

    for claim_id in claim_ids:
        claim_folder = claims_dir / claim_id
        if not claim_folder.exists():
            logger.warning("Claim %s — folder not found, skipping", claim_id)
            continue

        run_id, run_dir = get_latest_run(claim_folder)
        if not run_dir:
            logger.warning("Claim %s — no claim runs, skipping", claim_id)
            continue

        # Load input data
        facts = load_json(run_dir / "claim_facts.json")
        screening = load_json(run_dir / "screening.json")
        coverage = load_json(run_dir / "coverage_analysis.json")
        processing = load_json(run_dir / "assessment.json")

        if not facts:
            logger.warning("Claim %s — no claim_facts.json in %s, skipping", claim_id, run_id)
            continue

        logger.info(
            "Claim %s — run %s | facts=%s screening=%s coverage=%s assessment=%s",
            claim_id,
            run_id,
            "YES" if facts else "no",
            "YES" if screening else "no",
            "YES" if coverage else "no",
            "YES" if processing else "no",
        )

        # Evaluate
        try:
            dossier = engine.evaluate(
                claim_id=claim_id,
                aggregated_facts=facts,
                screening_result=screening,
                coverage_analysis=coverage,
                processing_result=processing,
                assumptions=None,
            )
        except Exception as e:
            logger.error("Claim %s — engine.evaluate() failed: %s", claim_id, e)
            continue

        # Serialize
        dossier_dict = dossier.model_dump(mode="json")

        # Version and write
        version = get_next_version(run_dir)
        dossier_dict["version"] = version
        out_path = run_dir / f"decision_dossier_v{version}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(dossier_dict, f, indent=2, ensure_ascii=False, default=str)

        # Summarize
        verdict = dossier_dict.get("claim_verdict", "?")
        n_clauses = len(dossier_dict.get("clause_evaluations", []))
        failed = [
            e.get("clause_reference", "?")
            for e in dossier_dict.get("clause_evaluations", [])
            if e.get("verdict") == "FAIL"
        ]
        n_items = len(dossier_dict.get("line_item_decisions", []))
        n_assumptions = len(dossier_dict.get("assumptions_used", []))
        fin = dossier_dict.get("financial_summary", {})
        net = fin.get("net_payout", 0)

        logger.info(
            "Claim %s — verdict=%s | clauses=%d (failed=%d) | items=%d | assumptions=%d | payout=%.2f",
            claim_id,
            verdict,
            n_clauses,
            len(failed),
            n_items,
            n_assumptions,
            net,
        )
        if failed:
            logger.info("  Failed clauses: %s", ", ".join(failed))

        logger.info("  Wrote %s", out_path.name)

        results.append({
            "claim_id": claim_id,
            "verdict": verdict,
            "version": version,
            "failed_clauses": failed,
            "line_items": n_items,
            "net_payout": net,
            "file": str(out_path),
        })

    # Print summary table
    print("\n" + "=" * 80)
    print("DECISION DOSSIER SUMMARY")
    print("=" * 80)
    print(f"{'Claim':<10} {'Verdict':<10} {'Ver':<5} {'Clauses Failed':<20} {'Items':<7} {'Payout':>10}")
    print("-" * 80)
    for r in results:
        failed_str = ", ".join(r["failed_clauses"]) if r["failed_clauses"] else "none"
        print(
            f"{r['claim_id']:<10} {r['verdict']:<10} v{r['version']:<4} {failed_str:<20} {r['line_items']:<7} {r['net_payout']:>10.2f}"
        )
    print("=" * 80)
    print(f"\nProcessed {len(results)} / {len(claim_ids)} claims")


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    if "--all" in sys.argv:
        claims_dir = WORKSPACE_PATH / "claims"
        claim_ids = sorted(
            [d.name for d in claims_dir.iterdir() if d.is_dir()]
        )
    elif len(sys.argv) > 1:
        claim_ids = [a for a in sys.argv[1:] if not a.startswith("-")]
    else:
        claim_ids = SEED_CLAIMS

    if not claim_ids:
        logger.error("No claims to process")
        sys.exit(1)

    logger.info("Running decision engine on %d claims: %s", len(claim_ids), ", ".join(claim_ids))
    run_decision(claim_ids)


if __name__ == "__main__":
    main()
