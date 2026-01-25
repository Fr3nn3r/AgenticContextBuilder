#!/usr/bin/env python3
"""
Claims Assessment Evaluation Script

Runs the assessment on all test claims and compares results against
expected outcomes from human adjusters (ground truth).

Usage:
    python scripts/eval_assessment.py                    # Run assessment + evaluate
    python scripts/eval_assessment.py --eval-only        # Evaluate existing results only
    python scripts/eval_assessment.py --dry-run          # Show what would be done
    python scripts/eval_assessment.py --claim 65258      # Run single claim

Output:
    - Console: Summary table with pass/fail status
    - File: workspaces/{workspace}/eval/assessment_eval_{timestamp}.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context_builder.storage.workspace_paths import get_active_workspace_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Ground truth from human adjusters
# Source: data/08-NSA-Supporting-docs/{claim_id}/Thoughts on claim {claim_id}.docx
GROUND_TRUTH = {
    "65258": {
        "expected_decision": "APPROVE",
        "expected_payout": 4500.0,
        "component": "cylinder head",
        "rejection_reason": None,
        "notes": "Cylinder head is covered. Max coverage CHF 5,000 - 10% deductible = CHF 4,500",
        "truth_file": "data/08-NSA-Supporting-docs/65258/Thoughts on claim 65258.docx"
    },
    "65196": {
        "expected_decision": "APPROVE",
        "expected_payout": None,  # Payout amount not specified in truth doc
        "component": "hydraulic valve (height control)",
        "rejection_reason": None,
        "notes": "Valve is covered under suspension/chassis. No rejection triggers found.",
        "truth_file": "data/08-NSA-Supporting-docs/65196/Thoughts on claim 65196.docx"
    },
    "65157": {
        "expected_decision": "REJECT",
        "expected_payout": 0.0,
        "component": "transmission",
        "rejection_reason": "fraud - damage occurred before warranty start date",
        "notes": "Damage first apparent Dec 29, 2025. Warranty starts Dec 31, 2025. Pre-existing damage.",
        "truth_file": "data/08-NSA-Supporting-docs/65157/Thoughts on claim 65157.docx"
    },
    "65128": {
        "expected_decision": "REJECT",
        "expected_payout": 0.0,
        "component": "trunk lock",
        "rejection_reason": "not covered - accessory component",
        "notes": "Trunk lock is not listed in the scope of coverage.",
        "truth_file": "data/08-NSA-Supporting-docs/65128/Thoughts on claim 65128.docx"
    },
}


# Evaluation modes
EVAL_MODES = {
    "lenient": {
        # Current behavior - REFER_TO_HUMAN counts as acceptable for REJECT
        "refer_as_reject": True,
        "require_exact_payout": False,
        "payout_tolerance_percent": 1.0,  # 1% tolerance
    },
    "strict": {
        # Production behavior - exact decision match required
        "refer_as_reject": False,  # REFER_TO_HUMAN is its own category
        "require_exact_payout": True,
        "payout_tolerance_percent": 0.1,  # 0.1% tolerance (basically exact)
    }
}


def compute_confusion_matrix(results: list[dict]) -> dict:
    """
    Compute confusion matrix for decisions.

    Returns a matrix showing:
    - Rows: Expected decisions (ground truth)
    - Columns: AI decisions (predictions)
    """
    # Initialize matrix with all possible decision types
    decisions = ["APPROVE", "REJECT", "REFER_TO_HUMAN"]
    matrix = {expected: {actual: 0 for actual in decisions} for expected in decisions}

    for r in results:
        if "error" in r:
            continue
        expected = r.get("expected_decision", "UNKNOWN")
        actual = r.get("ai_decision", "UNKNOWN")
        if expected in matrix and actual in matrix[expected]:
            matrix[expected][actual] += 1

    # Compute summary metrics
    total = sum(sum(row.values()) for row in matrix.values())
    correct = sum(matrix[d][d] for d in decisions if d in matrix)

    return {
        "matrix": matrix,
        "total_evaluated": total,
        "correct_decisions": correct,
        "decision_accuracy": correct / total if total > 0 else 0.0,
    }


def load_assessment_result(claim_id: str) -> dict | None:
    """Load the assessment.json for a claim."""
    workspace_path = get_active_workspace_path()
    assessment_path = workspace_path / "claims" / claim_id / "context" / "assessment.json"

    if not assessment_path.exists():
        logger.warning(f"No assessment found for claim {claim_id} at {assessment_path}")
        return None

    with open(assessment_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_claim(
    claim_id: str,
    assessment: dict,
    ground_truth: dict,
    mode: str = "lenient"
) -> dict:
    """
    Evaluate a single claim's assessment against ground truth.

    Args:
        claim_id: The claim identifier
        assessment: The AI assessment result
        ground_truth: The expected result from human adjusters
        mode: Evaluation mode - "lenient" or "strict"

    Returns evaluation result with pass/fail status and details.
    """
    config = EVAL_MODES.get(mode, EVAL_MODES["lenient"])

    ai_decision = assessment.get("decision", "UNKNOWN")
    ai_payout_raw = assessment.get("payout", {}).get("final_payout", 0.0)

    expected_decision = ground_truth["expected_decision"]
    expected_payout = ground_truth["expected_payout"]

    # Effective payout: If AI rejects or refers, payout is effectively 0
    if ai_decision in ("REJECT", "REFER_TO_HUMAN"):
        ai_payout = 0.0
    else:
        ai_payout = ai_payout_raw

    # Decision match logic depends on mode
    decision_match = ai_decision == expected_decision

    if config["refer_as_reject"]:
        # Lenient: REFER_TO_HUMAN is acceptable when expected is REJECT
        decision_acceptable = decision_match or (
            expected_decision == "REJECT" and ai_decision == "REFER_TO_HUMAN"
        )
    else:
        # Strict: Only exact match is acceptable
        decision_acceptable = decision_match

    # Payout match (if expected payout is specified)
    payout_match = True
    payout_diff = None
    if expected_payout is not None:
        payout_diff = abs(ai_payout - expected_payout)
        tolerance_percent = config["payout_tolerance_percent"]
        # Allow tolerance for rounding differences, minimum $1
        payout_match = payout_diff <= max(expected_payout * tolerance_percent / 100, 1.0)

    # Overall pass: decision must be acceptable AND payout must match
    passed = decision_acceptable and payout_match

    return {
        "claim_id": claim_id,
        "passed": passed,
        "decision_match": decision_match,
        "decision_acceptable": decision_acceptable,
        "payout_match": payout_match,
        "ai_decision": ai_decision,
        "expected_decision": expected_decision,
        "ai_payout": ai_payout,
        "ai_payout_raw": ai_payout_raw,
        "expected_payout": expected_payout,
        "payout_diff": payout_diff,
        "component": ground_truth["component"],
        "expected_rejection_reason": ground_truth.get("rejection_reason"),
        "ai_rationale": assessment.get("decision_rationale", ""),
        "confidence_score": assessment.get("confidence_score", 0.0),
        "truth_file": ground_truth["truth_file"],
        "eval_mode": mode,
    }


def run_assessments(claims: list[str], dry_run: bool = False) -> dict[str, dict]:
    """Run assessments for the specified claims."""
    # Import run_assessment from the other script
    from run_assessment import run_assessment

    results = {}
    for claim_id in claims:
        logger.info(f"Running assessment for claim {claim_id}...")
        try:
            result = run_assessment(claim_id, dry_run=dry_run)
            results[claim_id] = result
        except Exception as e:
            logger.error(f"Failed to run assessment for {claim_id}: {e}")
            results[claim_id] = {"status": "error", "error": str(e)}

    return results


def evaluate_all(claims: list[str] | None = None, mode: str = "lenient") -> dict:
    """
    Evaluate all claims against ground truth.

    Args:
        claims: List of claim IDs to evaluate (default: all ground truth claims)
        mode: Evaluation mode - "lenient" or "strict"

    Returns evaluation summary with individual results, metrics, and confusion matrix.
    """
    if claims is None:
        claims = list(GROUND_TRUTH.keys())

    results = []
    passed_count = 0

    for claim_id in claims:
        if claim_id not in GROUND_TRUTH:
            logger.warning(f"No ground truth for claim {claim_id}, skipping evaluation")
            continue

        assessment = load_assessment_result(claim_id)
        if assessment is None:
            results.append({
                "claim_id": claim_id,
                "passed": False,
                "error": "No assessment found",
            })
            continue

        eval_result = evaluate_claim(claim_id, assessment, GROUND_TRUTH[claim_id], mode)
        results.append(eval_result)

        if eval_result["passed"]:
            passed_count += 1

    total = len(results)
    accuracy = passed_count / total if total > 0 else 0.0

    # Compute confusion matrix
    confusion = compute_confusion_matrix(results)

    return {
        "schema_version": "assessment_eval_v2",
        "evaluated_at": datetime.now().isoformat(),
        "eval_mode": mode,
        "summary": {
            "total_claims": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "accuracy": accuracy,
            "accuracy_percent": f"{accuracy * 100:.1f}%",
        },
        "confusion_matrix": confusion,
        "results": results,
        "ground_truth_sources": {
            claim_id: gt["truth_file"]
            for claim_id, gt in GROUND_TRUTH.items()
            if claim_id in claims
        },
    }


def print_summary(evaluation: dict) -> None:
    """Print evaluation summary to console."""
    summary = evaluation["summary"]
    results = evaluation["results"]
    mode = evaluation.get("eval_mode", "lenient")

    print("\n" + "=" * 70)
    print(f"CLAIMS ASSESSMENT EVALUATION (mode: {mode})")
    print("=" * 70)

    # Header
    print(f"\n{'Claim':<10} {'Component':<25} {'AI':<10} {'Expected':<10} {'Status'}")
    print("-" * 70)

    for r in results:
        if "error" in r:
            status = "ERROR"
            ai_dec = "N/A"
        else:
            status = "PASS" if r["passed"] else "FAIL"
            ai_dec = r["ai_decision"]

        component = r.get("component", "unknown")[:24]
        expected = r.get("expected_decision", "N/A")

        # Color coding (ANSI)
        if status == "PASS":
            status_str = f"\033[92m{status}\033[0m"  # Green
        elif status == "FAIL":
            status_str = f"\033[91m{status}\033[0m"  # Red
        else:
            status_str = f"\033[93m{status}\033[0m"  # Yellow

        print(f"{r['claim_id']:<10} {component:<25} {ai_dec:<10} {expected:<10} {status_str}")

        # Show mismatch details
        if not r.get("passed", False) and "error" not in r:
            if not r.get("decision_acceptable"):
                print(f"           -> Decision mismatch: AI={ai_dec}, Expected={expected}")
            if not r.get("payout_match") and r.get("payout_diff") is not None:
                print(f"           -> Payout mismatch: AI={r['ai_payout']}, Expected={r['expected_payout']}")
        # Show when REFER_TO_HUMAN was accepted as alternative to REJECT
        elif r.get("passed") and not r.get("decision_match") and r.get("decision_acceptable"):
            print(f"           (REFER_TO_HUMAN accepted as conservative alternative to REJECT)")

    print("-" * 70)
    print(f"\nAccuracy: {summary['passed']}/{summary['total_claims']} ({summary['accuracy_percent']})")

    # Print confusion matrix
    confusion = evaluation.get("confusion_matrix", {})
    if confusion:
        print("\n" + "-" * 70)
        print("CONFUSION MATRIX (Expected vs AI Decision)")
        print("-" * 70)
        matrix = confusion.get("matrix", {})
        decisions = ["APPROVE", "REJECT", "REFER_TO_HUMAN"]

        # Header row
        print(f"{'Expected':<18} | {'APPROVE':>10} {'REJECT':>10} {'REFER':>10}")
        print("-" * 52)

        for expected in decisions:
            row = matrix.get(expected, {})
            approve = row.get("APPROVE", 0)
            reject = row.get("REJECT", 0)
            refer = row.get("REFER_TO_HUMAN", 0)
            print(f"{expected:<18} | {approve:>10} {reject:>10} {refer:>10}")

        print("-" * 52)
        print(f"Decision accuracy: {confusion.get('decision_accuracy', 0):.1%}")

    print("=" * 70)


def save_evaluation(evaluation: dict) -> Path:
    """Save evaluation results to file."""
    workspace_path = get_active_workspace_path()
    eval_dir = workspace_path / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    eval_path = eval_dir / f"assessment_eval_{timestamp}.json"

    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(evaluation, f, indent=2)

    logger.info(f"Saved evaluation to: {eval_path}")
    return eval_path


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Claims Assessment against human adjuster ground truth"
    )
    parser.add_argument(
        "--claim",
        type=str,
        help="Specific claim ID to evaluate"
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Only evaluate existing results (don't run new assessments)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without calling API"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save evaluation results to file"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["lenient", "strict"],
        default="lenient",
        help="Evaluation mode: 'lenient' (REFER_TO_HUMAN accepted for REJECT) or 'strict' (exact match required)"
    )

    args = parser.parse_args()

    # Determine which claims to process
    if args.claim:
        claims = [args.claim]
    else:
        claims = list(GROUND_TRUTH.keys())

    # Run assessments if not eval-only
    if not args.eval_only:
        logger.info(f"Running assessments for {len(claims)} claims...")
        run_assessments(claims, dry_run=args.dry_run)

        if args.dry_run:
            print("\n[DRY RUN] Would evaluate the following claims:")
            for claim_id in claims:
                gt = GROUND_TRUTH.get(claim_id, {})
                print(f"  - {claim_id}: {gt.get('component', 'unknown')} -> expected {gt.get('expected_decision', '?')}")
            return

    # Evaluate results
    logger.info(f"Evaluating results against ground truth (mode: {args.mode})...")
    evaluation = evaluate_all(claims, mode=args.mode)

    # Print summary
    print_summary(evaluation)

    # Save results
    if not args.no_save:
        eval_path = save_evaluation(evaluation)
        print(f"\nEvaluation saved to: {eval_path}")

    # Exit with non-zero if any failures
    if evaluation["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
