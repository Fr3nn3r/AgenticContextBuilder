"""
Pipeline Evaluation Script

Compares pipeline assessment output against ground truth and generates Excel reports.

Usage:
    python scripts/eval_pipeline.py

Outputs:
    workspaces/nsa/eval/eval_YYYYMMDD_HHMMSS/
        - summary.xlsx       # High-level metrics
        - details.xlsx       # Per-claim breakdown
        - errors.xlsx        # Only mismatches (for investigation)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Run: pip install pandas openpyxl")
    sys.exit(1)

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)


# Configuration
WORKSPACE_PATH = Path("workspaces/nsa")
GROUND_TRUTH_PATH = Path("data/datasets/nsa-motor-eval-v1/ground_truth.json")


def load_ground_truth() -> dict:
    """Load ground truth and return as dict keyed by claim_id."""
    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert to dict keyed by claim_id
    return {claim["claim_id"]: claim for claim in data["claims"]}


def _find_latest_dossier(run_folder: Path) -> Optional[dict]:
    """Find the latest decision_dossier_v*.json in a run folder."""
    candidates = sorted(run_folder.glob("decision_dossier_v*.json"))
    if not candidates:
        return None
    try:
        with open(candidates[-1], "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def find_latest_assessment(claim_id: str, target_run_id: Optional[str] = None, target_run_ids: Optional[list] = None) -> Optional[dict]:
    """Find the most recent assessment for a claim, or from specific run(s).

    Also loads the decision dossier (if available) and stores the
    authoritative verdict under ``_dossier_verdict`` for eval comparison.
    """
    claim_runs_path = WORKSPACE_PATH / "claims" / claim_id / "claim_runs"

    if not claim_runs_path.exists():
        return None

    # Support multiple run IDs — try each in order, return first hit
    run_ids_to_try = []
    if target_run_ids:
        run_ids_to_try = target_run_ids
    elif target_run_id:
        run_ids_to_try = [target_run_id]

    if run_ids_to_try:
        for rid in run_ids_to_try:
            run_folder = claim_runs_path / rid
            assessment_file = run_folder / "assessment.json"
            if assessment_file.exists():
                with open(assessment_file, "r", encoding="utf-8") as f:
                    assessment = json.load(f)
                assessment["_run_id"] = run_folder.name
                # Load dossier verdict (authoritative)
                dossier = _find_latest_dossier(run_folder)
                if dossier:
                    assessment["_dossier_verdict"] = dossier.get("claim_verdict")
                return assessment
        return None

    # Get all run folders, sorted by name (timestamp-based)
    run_folders = sorted(claim_runs_path.iterdir(), reverse=True)

    for run_folder in run_folders:
        assessment_file = run_folder / "assessment.json"
        if assessment_file.exists():
            with open(assessment_file, "r", encoding="utf-8") as f:
                assessment = json.load(f)
            assessment["_run_id"] = run_folder.name
            # Load dossier verdict (authoritative)
            dossier = _find_latest_dossier(run_folder)
            if dossier:
                assessment["_dossier_verdict"] = dossier.get("claim_verdict")
            return assessment

    return None


def normalize_decision(decision: str) -> str:
    """Normalize decision values for comparison."""
    decision = decision.upper().strip()
    if decision in ["APPROVED", "APPROVE"]:
        return "APPROVED"
    elif decision in ["DENIED", "REJECT", "REJECTED"]:
        return "DENIED"
    elif decision in ["REFER_TO_HUMAN", "REFER", "INCONCLUSIVE"]:
        return "REFER_TO_HUMAN"
    return decision


def get_failed_checks(assessment: dict) -> str:
    """Get comma-separated list of failed check names."""
    failed = []
    for check in assessment.get("checks", []):
        if check.get("result") == "FAIL":
            failed.append(check.get("check_name", "unknown"))
    return ", ".join(failed) if failed else "-"


def categorize_error(gt: dict, pred: dict, decision_match: bool) -> str:
    """Categorize the type of error."""
    if decision_match:
        # Decision correct but amounts differ
        gt_amount = gt.get("total_approved_amount") or gt.get("approved_amount")
        pred_amount = pred.get("payout", {}).get("final_payout", 0)
        if gt_amount and pred_amount:
            diff_pct = abs(gt_amount - pred_amount) / gt_amount * 100
            if diff_pct > 5:
                return "amount_mismatch"
        return "-"

    # Decision wrong - categorize by what failed
    gt_decision = normalize_decision(gt.get("decision", ""))
    pred_decision = normalize_decision(pred.get("decision", ""))

    # Handle REFER_TO_HUMAN
    if pred_decision == "REFER_TO_HUMAN":
        failed_checks = get_failed_checks(pred)
        if gt_decision == "APPROVED":
            if failed_checks != "-":
                return f"refer_should_approve:{failed_checks.split(',')[0].strip()}"
            return "refer_should_approve:no_fails"
        else:
            if failed_checks != "-":
                return f"refer_should_deny:{failed_checks.split(',')[0].strip()}"
            return "refer_should_deny:no_fails"

    if gt_decision == "APPROVED" and pred_decision == "DENIED":
        # False rejection - look at what checks failed
        failed_checks = get_failed_checks(pred)
        if "service_compliance" in failed_checks:
            return "false_reject:service_compliance"
        elif "component_coverage" in failed_checks:
            return "false_reject:component_coverage"
        elif "policy_validity" in failed_checks:
            return "false_reject:policy_validity"
        else:
            return "false_reject:other"

    elif gt_decision == "DENIED" and pred_decision == "APPROVED":
        # False approval
        return "false_approve"

    return "unknown"


def run_evaluation(target_run_id: Optional[str] = None, target_run_ids: Optional[list] = None) -> dict:
    """Run the full evaluation and return results."""
    ground_truth = load_ground_truth()

    results = []

    for claim_id, gt in ground_truth.items():
        assessment = find_latest_assessment(claim_id, target_run_id=target_run_id, target_run_ids=target_run_ids)

        # Support both v1 (total_approved_amount) and v2 (approved_amount) ground truth schemas
        gt_amount = gt.get("total_approved_amount") or gt.get("approved_amount")

        row = {
            "claim_id": claim_id,
            "gt_decision": gt.get("decision"),
            "gt_amount": gt_amount,
            "gt_deductible": gt.get("deductible"),
            "gt_denial_reason": gt.get("denial_reason"),
            "gt_vehicle": gt.get("vehicle"),
        }

        if assessment is None:
            row.update({
                "pred_decision": "NOT_PROCESSED",
                "pred_amount": None,
                "pred_deductible": None,
                "decision_match": False,
                "amount_diff": None,
                "amount_diff_pct": None,
                "deductible_match": None,
                "failed_checks": "-",
                "error_category": "not_processed",
                "run_id": None,
                "decision_rationale": None,
            })
        else:
            gt_decision_norm = normalize_decision(gt.get("decision", ""))
            # Use dossier verdict (authoritative) if available, fall back to assessment
            pred_decision_raw = assessment.get("_dossier_verdict") or assessment.get("recommendation", "")
            pred_decision_norm = normalize_decision(pred_decision_raw)
            decision_match = gt_decision_norm == pred_decision_norm

            pred_amount = assessment.get("payout", {}).get("final_payout", 0)
            pred_deductible = assessment.get("payout", {}).get("deductible", 0)

            # Amount comparison (only meaningful for approved claims)
            gt_amount = gt.get("total_approved_amount") or gt.get("approved_amount")
            if gt_amount and gt_amount > 0:
                amount_diff = pred_amount - gt_amount
                amount_diff_pct = (amount_diff / gt_amount) * 100
            else:
                amount_diff = None
                amount_diff_pct = None

            # Deductible comparison
            gt_deductible = gt.get("deductible")
            if gt_deductible is not None and pred_deductible is not None:
                deductible_match = abs(gt_deductible - pred_deductible) < 0.01
            else:
                deductible_match = None

            row.update({
                "pred_decision": pred_decision_raw,
                "pred_amount": pred_amount,
                "pred_deductible": pred_deductible,
                "decision_match": decision_match,
                "amount_diff": amount_diff,
                "amount_diff_pct": amount_diff_pct,
                "deductible_match": deductible_match,
                "failed_checks": get_failed_checks(assessment),
                "error_category": categorize_error(gt, assessment, decision_match),
                "run_id": assessment.get("_run_id"),
                "decision_rationale": assessment.get("recommendation_rationale"),
            })

        results.append(row)

    return results


def calculate_summary(results: list) -> dict:
    """Calculate summary metrics."""
    total = len(results)
    processed = sum(1 for r in results if r["pred_decision"] != "NOT_PROCESSED")

    decision_correct = sum(1 for r in results if r["decision_match"])

    # Split by ground truth decision
    gt_approved = [r for r in results if normalize_decision(r["gt_decision"]) == "APPROVED"]
    gt_denied = [r for r in results if normalize_decision(r["gt_decision"]) == "DENIED"]

    approved_correct = sum(1 for r in gt_approved if r["decision_match"])
    denied_correct = sum(1 for r in gt_denied if r["decision_match"])

    # Amount accuracy (for correctly approved claims)
    approved_with_amounts = [r for r in gt_approved if r["decision_match"] and r["amount_diff_pct"] is not None]
    amount_within_5pct = sum(1 for r in approved_with_amounts if abs(r["amount_diff_pct"]) <= 5)

    # Error category distribution
    error_categories = {}
    for r in results:
        cat = r["error_category"]
        if cat != "-":
            error_categories[cat] = error_categories.get(cat, 0) + 1

    return {
        "total_claims": total,
        "processed_claims": processed,
        "not_processed": total - processed,
        "decision_accuracy": decision_correct / processed if processed > 0 else 0,
        "decision_correct": decision_correct,
        "decision_wrong": processed - decision_correct,
        "gt_approved_total": len(gt_approved),
        "gt_approved_correct": approved_correct,
        "gt_approved_wrong": len(gt_approved) - approved_correct,
        "gt_denied_total": len(gt_denied),
        "gt_denied_correct": denied_correct,
        "gt_denied_wrong": len(gt_denied) - denied_correct,
        "false_reject_rate": (len(gt_approved) - approved_correct) / len(gt_approved) if gt_approved else 0,
        "false_approve_rate": (len(gt_denied) - denied_correct) / len(gt_denied) if gt_denied else 0,
        "amount_accuracy_5pct": amount_within_5pct / len(approved_with_amounts) if approved_with_amounts else None,
        "error_categories": error_categories,
    }


def save_results(results: list, summary: dict):
    """Save results to Excel files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = WORKSPACE_PATH / "eval" / f"eval_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to DataFrame
    df = pd.DataFrame(results)

    # Reorder columns for readability
    column_order = [
        "claim_id",
        "gt_decision", "pred_decision", "decision_match",
        "gt_amount", "pred_amount", "amount_diff", "amount_diff_pct",
        "gt_deductible", "pred_deductible", "deductible_match",
        "error_category", "failed_checks",
        "decision_rationale",
        "gt_denial_reason",
        "gt_vehicle",
        "run_id",
    ]
    df = df[[c for c in column_order if c in df.columns]]

    # Save details
    details_path = output_dir / "details.xlsx"
    df.to_excel(details_path, index=False, sheet_name="All Claims")
    print(f"Saved: {details_path}")

    # Save errors only
    errors_df = df[df["error_category"] != "-"]
    if not errors_df.empty:
        errors_path = output_dir / "errors.xlsx"
        errors_df.to_excel(errors_path, index=False, sheet_name="Errors")
        print(f"Saved: {errors_path}")

    # Save summary
    summary_data = [
        ["Metric", "Value"],
        ["Total Claims", summary["total_claims"]],
        ["Processed Claims", summary["processed_claims"]],
        ["Not Processed", summary["not_processed"]],
        ["", ""],
        ["Decision Accuracy", f"{summary['decision_accuracy']:.1%}"],
        ["Decision Correct", summary["decision_correct"]],
        ["Decision Wrong", summary["decision_wrong"]],
        ["", ""],
        ["Ground Truth Approved", summary["gt_approved_total"]],
        ["  - Correctly Approved", summary["gt_approved_correct"]],
        ["  - Wrongly Rejected", summary["gt_approved_wrong"]],
        ["False Reject Rate", f"{summary['false_reject_rate']:.1%}"],
        ["", ""],
        ["Ground Truth Denied", summary["gt_denied_total"]],
        ["  - Correctly Denied", summary["gt_denied_correct"]],
        ["  - Wrongly Approved", summary["gt_denied_wrong"]],
        ["False Approve Rate", f"{summary['false_approve_rate']:.1%}"],
        ["", ""],
        ["Amount Accuracy (±5%)", f"{summary['amount_accuracy_5pct']:.1%}" if summary['amount_accuracy_5pct'] else "N/A"],
        ["", ""],
        ["Error Categories", ""],
    ]

    for cat, count in summary.get("error_categories", {}).items():
        summary_data.append([f"  - {cat}", count])

    summary_df = pd.DataFrame(summary_data, columns=["Metric", "Value"])
    summary_path = output_dir / "summary.xlsx"
    summary_df.to_excel(summary_path, index=False, sheet_name="Summary")
    print(f"Saved: {summary_path}")

    # Also save as JSON for programmatic access
    summary_json_path = output_dir / "summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {summary_json_path}")

    return output_dir


def update_metrics_history(output_dir: Path, summary: dict, description: str = "", ground_truth_path: Path = None):
    """Append this run to metrics_history.json for tracking over time."""
    history_path = WORKSPACE_PATH / "eval" / "metrics_history.json"

    # Load existing history or create new
    if history_path.exists():
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = {
            "schema_version": "metrics_history_v1",
            "ground_truth_path": str(ground_truth_path or GROUND_TRUTH_PATH),
            "ground_truth_claims": summary["total_claims"],
            "runs": []
        }

    # Build top errors list
    top_errors = [
        {"category": cat, "count": count}
        for cat, count in sorted(
            summary.get("error_categories", {}).items(),
            key=lambda x: -x[1]
        )[:5]
    ]

    # Create new run entry
    run_entry = {
        "run_id": output_dir.name,
        "timestamp": datetime.now().isoformat(),
        "description": description or "Evaluation run",
        "git_commit": None,
        "pipeline_version": None,
        "metrics": {
            "decision_accuracy": round(summary["decision_accuracy"], 3),
            "decision_correct": summary["decision_correct"],
            "decision_wrong": summary["decision_wrong"],
            "approved_correct": summary["gt_approved_correct"],
            "approved_total": summary["gt_approved_total"],
            "denied_correct": summary["gt_denied_correct"],
            "denied_total": summary["gt_denied_total"],
            "false_reject_rate": round(summary["false_reject_rate"], 3),
            "false_approve_rate": round(summary["false_approve_rate"], 3)
        },
        "top_errors": top_errors,
        "notes": ""
    }

    # Append to history
    history["runs"].append(run_entry)

    # Save updated history
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print(f"Updated: {history_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Evaluation")
    parser.add_argument("--run-id", nargs="+", default=None, help="Evaluate specific run ID(s). Multiple IDs: tries each in order per claim, uses first hit.")
    gt_group = parser.add_mutually_exclusive_group()
    gt_group.add_argument("--ground-truth", type=Path, default=None,
        help="Path to ground truth JSON file")
    gt_group.add_argument("--dataset", type=str, default=None,
        help="Dataset ID from data/datasets/ (e.g., nsa-motor-eval-v1)")
    parser.add_argument("--workspace", type=Path, default=None,
        help="Workspace path (default: workspaces/nsa)")
    args = parser.parse_args()

    global GROUND_TRUTH_PATH, WORKSPACE_PATH
    if args.ground_truth:
        GROUND_TRUTH_PATH = args.ground_truth
    elif args.dataset:
        GROUND_TRUTH_PATH = Path(f"data/datasets/{args.dataset}/ground_truth.json")
    if args.workspace:
        WORKSPACE_PATH = args.workspace

    print("=" * 60)
    print("Pipeline Evaluation")
    print("=" * 60)
    print(f"Ground Truth: {GROUND_TRUTH_PATH}")
    print(f"Workspace: {WORKSPACE_PATH}")
    if args.run_id:
        if len(args.run_id) == 1:
            print(f"Target Run:  {args.run_id[0]}")
        else:
            print(f"Target Runs: {', '.join(args.run_id)} (priority order)")
    print()

    # Check paths exist
    if not GROUND_TRUTH_PATH.exists():
        print(f"ERROR: Ground truth not found: {GROUND_TRUTH_PATH}")
        sys.exit(1)

    if not WORKSPACE_PATH.exists():
        print(f"ERROR: Workspace not found: {WORKSPACE_PATH}")
        sys.exit(1)

    # Run evaluation
    print("Running evaluation...")
    if args.run_id and len(args.run_id) == 1:
        results = run_evaluation(target_run_id=args.run_id[0])
    elif args.run_id:
        results = run_evaluation(target_run_ids=args.run_id)
    else:
        results = run_evaluation()

    # Calculate summary
    summary = calculate_summary(results)

    # Print summary to console
    print()
    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Claims:        {summary['total_claims']}")
    print(f"Processed:           {summary['processed_claims']}")
    print(f"Not Processed:       {summary['not_processed']}")
    print()
    print(f"Decision Accuracy:   {summary['decision_accuracy']:.1%} ({summary['decision_correct']}/{summary['processed_claims']})")
    print()
    print(f"Approved Claims:     {summary['gt_approved_correct']}/{summary['gt_approved_total']} correct")
    print(f"  False Reject Rate: {summary['false_reject_rate']:.1%}")
    print()
    print(f"Denied Claims:       {summary['gt_denied_correct']}/{summary['gt_denied_total']} correct")
    print(f"  False Approve Rate: {summary['false_approve_rate']:.1%}")
    print()

    if summary.get("error_categories"):
        print("Error Categories:")
        for cat, count in sorted(summary["error_categories"].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    print()

    # Save results
    output_dir = save_results(results, summary)

    # Update metrics history for tracking
    update_metrics_history(output_dir, summary, ground_truth_path=GROUND_TRUTH_PATH)

    print()
    print(f"Results saved to: {output_dir}")
    print("=" * 60)
    print()
    print("Remember to update EVAL_LOG.md with your findings!")
    print(f"  {WORKSPACE_PATH / 'eval' / 'EVAL_LOG.md'}")


if __name__ == "__main__":
    main()
