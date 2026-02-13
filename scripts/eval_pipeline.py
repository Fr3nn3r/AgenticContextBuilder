"""
Pipeline Evaluation Script

Compares pipeline assessment output against ground truth and generates Excel reports.
Auto-detects which datasets are involved via workspace config/datasets.json.

Usage:
    python scripts/eval_pipeline.py                           # Latest claim run, auto-detect datasets
    python scripts/eval_pipeline.py --run-id <claim_run_id>   # Specific claim run
    python scripts/eval_pipeline.py --dataset nsa-motor-eval-v1  # Override: single dataset (legacy)

Outputs:
    workspaces/nsa/eval/eval_YYYYMMDD_HHMMSS/
        - summary.xlsx       # High-level metrics
        - details.xlsx       # Per-claim breakdown (includes dataset_id column)
        - errors.xlsx        # Only mismatches (for investigation)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
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


# Default workspace
DEFAULT_WORKSPACE_PATH = Path("workspaces/nsa")


# ---------------------------------------------------------------------------
# Dataset & claim-run discovery helpers
# ---------------------------------------------------------------------------

def load_dataset_assignments(workspace_path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load dataset assignments and labels from workspace config.

    Returns (assignments, labels) where:
      assignments maps claim_id -> dataset_id
      labels maps dataset_id -> human-readable label
    If file is missing or malformed, returns ({}, {}).
    """
    ds_path = workspace_path / "config" / "datasets.json"
    if not ds_path.exists():
        return {}, {}
    try:
        with open(ds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        labels = {d["id"]: d["label"] for d in data.get("datasets", [])}
        assignments = data.get("assignments", {})
        return assignments, labels
    except (json.JSONDecodeError, IOError, KeyError):
        return {}, {}


def load_multi_dataset_ground_truth(dataset_ids: Set[str]) -> Dict[str, dict]:
    """Load ground truth from multiple datasets and merge into a single dict.

    Returns dict keyed by claim_id. Each entry gets a ``_dataset_id`` field.
    Skips datasets whose ground_truth.json doesn't exist (with a warning).
    """
    merged = {}
    for dataset_id in sorted(dataset_ids):
        gt_path = Path(f"data/datasets/{dataset_id}/ground_truth.json")
        if not gt_path.exists():
            print(f"  WARNING: Ground truth not found for {dataset_id}: {gt_path}")
            continue
        with open(gt_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for claim in data.get("claims", []):
            cid = claim["claim_id"]
            claim["_dataset_id"] = dataset_id
            merged[cid] = claim
            count += 1
        print(f"  Loaded {count} GT claims from {dataset_id}")
    return merged


def discover_run_claims(workspace_path: Path, run_id: str) -> Optional[List[str]]:
    """Read manifest.json for a claim run and return list of claim IDs.

    Uses ``claims_succeeded`` if present, falls back to ``claims_assessed``.
    Returns None if manifest not found.
    """
    manifest_path = workspace_path / "claim_runs" / run_id / "manifest.json"
    if not manifest_path.exists():
        return None
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest.get("claims_succeeded") or manifest.get("claims_assessed") or []


def find_latest_claim_run(workspace_path: Path) -> Optional[str]:
    """Find the most recent claim run folder (sorted by name, which is timestamp-based)."""
    claim_runs_dir = workspace_path / "claim_runs"
    if not claim_runs_dir.exists():
        return None
    folders = sorted(
        [d.name for d in claim_runs_dir.iterdir() if d.is_dir()],
        reverse=True,
    )
    return folders[0] if folders else None


def load_single_ground_truth(gt_path: Path) -> Dict[str, dict]:
    """Load ground truth from a single file (legacy mode)."""
    with open(gt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {claim["claim_id"]: claim for claim in data["claims"]}


# ---------------------------------------------------------------------------
# Assessment loading
# ---------------------------------------------------------------------------

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


def _load_routing_decision(run_folder: Path) -> Optional[dict]:
    """Load routing_decision.json from a run folder."""
    path = run_folder / "routing_decision.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def find_latest_assessment(
    claim_id: str,
    workspace_path: Path,
    target_run_id: Optional[str] = None,
) -> Optional[dict]:
    """Find the assessment for a claim from a specific run, or the most recent.

    Also loads the decision dossier (if available) and stores the
    authoritative verdict under ``_dossier_verdict`` for eval comparison.
    Loads routing decision data if available.
    """
    claim_runs_path = workspace_path / "claims" / claim_id / "claim_runs"

    if not claim_runs_path.exists():
        return None

    if target_run_id:
        run_folder = claim_runs_path / target_run_id
        assessment_file = run_folder / "assessment.json"
        if assessment_file.exists():
            with open(assessment_file, "r", encoding="utf-8") as f:
                assessment = json.load(f)
            assessment["_run_id"] = run_folder.name
            dossier = _find_latest_dossier(run_folder)
            if dossier:
                assessment["_dossier_verdict"] = dossier.get("claim_verdict")
            routing = _load_routing_decision(run_folder)
            if routing:
                assessment["_routing"] = routing
            return assessment
        return None

    # No specific run -- get most recent
    run_folders = sorted(claim_runs_path.iterdir(), reverse=True)

    for run_folder in run_folders:
        assessment_file = run_folder / "assessment.json"
        if assessment_file.exists():
            with open(assessment_file, "r", encoding="utf-8") as f:
                assessment = json.load(f)
            assessment["_run_id"] = run_folder.name
            dossier = _find_latest_dossier(run_folder)
            if dossier:
                assessment["_dossier_verdict"] = dossier.get("claim_verdict")
            routing = _load_routing_decision(run_folder)
            if routing:
                assessment["_routing"] = routing
            return assessment

    return None


# ---------------------------------------------------------------------------
# Evaluation helpers (unchanged logic)
# ---------------------------------------------------------------------------

def normalize_decision(decision: str) -> str:
    """Normalize decision values for comparison."""
    decision = decision.upper().strip()
    if decision in ["APPROVED", "APPROVE"]:
        return "APPROVED"
    elif decision in ["DENIED", "DENY", "REJECT", "REJECTED"]:
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
    # Use dossier verdict (authoritative) if available, fall back to recommendation
    pred_decision_raw = pred.get("_dossier_verdict") or pred.get("recommendation", "")
    pred_decision = normalize_decision(pred_decision_raw)

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


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _extract_routing_fields(assessment: Optional[dict]) -> dict:
    """Extract routing fields from assessment (if routing data exists)."""
    if not assessment:
        return {"routing_tier": None, "triggers_fired": None, "structural_cci": None}
    routing = assessment.get("_routing")
    if not routing:
        return {"routing_tier": None, "triggers_fired": None, "structural_cci": None}
    fired = routing.get("triggers_fired") or []
    trigger_names = ", ".join(t.get("name", "") for t in fired) if fired else "-"
    return {
        "routing_tier": routing.get("routing_tier"),
        "triggers_fired": trigger_names,
        "structural_cci": routing.get("structural_cci"),
    }


def run_evaluation(
    claim_ids: List[str],
    ground_truth: Dict[str, dict],
    dataset_assignments: Dict[str, str],
    workspace_path: Path,
    target_run_id: Optional[str] = None,
) -> List[dict]:
    """Run evaluation by iterating run claims, looking up GT for each.

    Claims without GT are recorded with error_category='no_ground_truth'
    and excluded from accuracy metrics downstream.
    """
    results = []

    for claim_id in claim_ids:
        gt = ground_truth.get(claim_id)
        dataset_id = dataset_assignments.get(claim_id, "unknown")
        assessment = find_latest_assessment(
            claim_id, workspace_path, target_run_id=target_run_id,
        )

        if gt is None:
            # Claim has no ground truth -- record but don't evaluate
            row = {
                "claim_id": claim_id,
                "dataset_id": dataset_id,
                "gt_decision": None,
                "gt_amount": None,
                "gt_deductible": None,
                "gt_denial_reason": None,
                "gt_vehicle": None,
                "pred_decision": assessment.get("_dossier_verdict") or assessment.get("recommendation", "N/A") if assessment else "NOT_PROCESSED",
                "pred_amount": assessment.get("payout", {}).get("final_payout") if assessment else None,
                "pred_deductible": assessment.get("payout", {}).get("deductible") if assessment else None,
                "decision_match": None,
                "amount_diff": None,
                "amount_diff_pct": None,
                "deductible_match": None,
                "failed_checks": get_failed_checks(assessment) if assessment else "-",
                "error_category": "no_ground_truth",
                "run_id": assessment.get("_run_id") if assessment else None,
                "decision_rationale": assessment.get("recommendation_rationale") if assessment else None,
            }
            row.update(_extract_routing_fields(assessment))
            results.append(row)
            continue

        # GT exists -- use dataset_id from GT if tagged, else from assignments
        dataset_id = gt.get("_dataset_id", dataset_id)

        # Support both v1 (total_approved_amount) and v2 (approved_amount) GT schemas
        gt_amount = gt.get("total_approved_amount") or gt.get("approved_amount")

        row = {
            "claim_id": claim_id,
            "dataset_id": dataset_id,
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
                "routing_tier": None,
                "triggers_fired": None,
                "structural_cci": None,
            })
        else:
            gt_decision_norm = normalize_decision(gt.get("decision", ""))
            # Use dossier verdict (authoritative) if available
            pred_decision_raw = assessment.get("_dossier_verdict") or assessment.get("recommendation", "")
            pred_decision_norm = normalize_decision(pred_decision_raw)
            decision_match = gt_decision_norm == pred_decision_norm

            pred_amount = assessment.get("payout", {}).get("final_payout", 0)
            pred_deductible = assessment.get("payout", {}).get("deductible", 0)

            # Amount comparison (only meaningful for approved claims)
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
            row.update(_extract_routing_fields(assessment))

        results.append(row)

    return results


# ---------------------------------------------------------------------------
# Summary / metrics
# ---------------------------------------------------------------------------

def calculate_summary(results: List[dict]) -> dict:
    """Calculate summary metrics. Excludes no_ground_truth claims from accuracy."""
    # Separate claims with GT from those without
    with_gt = [r for r in results if r["error_category"] != "no_ground_truth"]
    no_gt_count = len(results) - len(with_gt)

    total = len(with_gt)
    processed = sum(1 for r in with_gt if r["pred_decision"] != "NOT_PROCESSED")

    decision_correct = sum(1 for r in with_gt if r["decision_match"])

    # Split by ground truth decision
    gt_approved = [r for r in with_gt if normalize_decision(r["gt_decision"] or "") == "APPROVED"]
    gt_denied = [r for r in with_gt if normalize_decision(r["gt_decision"] or "") == "DENIED"]

    approved_correct = sum(1 for r in gt_approved if r["decision_match"])
    denied_correct = sum(1 for r in gt_denied if r["decision_match"])

    # Amount accuracy (for correctly approved claims)
    approved_with_amounts = [r for r in gt_approved if r["decision_match"] and r["amount_diff_pct"] is not None]
    amount_within_5pct = sum(1 for r in approved_with_amounts if abs(r["amount_diff_pct"]) <= 5)

    # Error category distribution
    error_categories = {}
    for r in with_gt:
        cat = r["error_category"]
        if cat != "-":
            error_categories[cat] = error_categories.get(cat, 0) + 1

    return {
        "total_claims": total,
        "total_in_run": len(results),
        "no_ground_truth": no_gt_count,
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


def calculate_routing_summary(results: List[dict]) -> Optional[Dict[str, Any]]:
    """Calculate per-routing-tier accuracy breakdown.

    Returns None if no routing data is available.
    """
    # Only consider claims with GT
    with_gt = [r for r in results if r.get("error_category") != "no_ground_truth"]
    routed = [r for r in with_gt if r.get("routing_tier") is not None]

    if not routed:
        return None

    tiers = {"GREEN": [], "YELLOW": [], "RED": []}
    for r in routed:
        tier = r.get("routing_tier", "").upper()
        if tier in tiers:
            tiers[tier].append(r)

    summary = {}
    total_routed = len(routed)
    for tier_name, tier_results in tiers.items():
        n = len(tier_results)
        processed = [r for r in tier_results if r.get("pred_decision") != "NOT_PROCESSED"]
        correct = sum(1 for r in processed if r.get("decision_match"))
        accuracy = correct / len(processed) if processed else None
        summary[tier_name] = {
            "count": n,
            "pct": round(n / total_routed * 100, 1) if total_routed else 0,
            "processed": len(processed),
            "correct": correct,
            "wrong": len(processed) - correct,
            "accuracy": round(accuracy, 3) if accuracy is not None else None,
        }

    return summary


def calculate_per_dataset_summary(results: List[dict]) -> Dict[str, dict]:
    """Group results by dataset_id and calculate summary per dataset."""
    by_dataset: Dict[str, List[dict]] = {}
    for r in results:
        ds = r.get("dataset_id", "unknown")
        by_dataset.setdefault(ds, []).append(r)

    per_dataset = {}
    for ds_id, ds_results in sorted(by_dataset.items()):
        per_dataset[ds_id] = calculate_summary(ds_results)

    return per_dataset


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_results(results: List[dict], summary: dict, workspace_path: Path) -> Path:
    """Save results to Excel files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = workspace_path / "eval" / f"eval_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to DataFrame
    df = pd.DataFrame(results)

    # Reorder columns for readability
    column_order = [
        "claim_id",
        "dataset_id",
        "gt_decision", "pred_decision", "decision_match",
        "routing_tier", "triggers_fired", "structural_cci",
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

    # Save errors only (exclude no_ground_truth from errors sheet)
    errors_df = df[(df["error_category"] != "-") & (df["error_category"] != "no_ground_truth")]
    if not errors_df.empty:
        errors_path = output_dir / "errors.xlsx"
        errors_df.to_excel(errors_path, index=False, sheet_name="Errors")
        print(f"Saved: {errors_path}")

    # Save summary
    summary_data = [
        ["Metric", "Value"],
        ["Total Claims (with GT)", summary["total_claims"]],
        ["Claims in Run", summary["total_in_run"]],
        ["Without Ground Truth", summary["no_ground_truth"]],
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
        ["Amount Accuracy (+/-5%)", f"{summary['amount_accuracy_5pct']:.1%}" if summary['amount_accuracy_5pct'] else "N/A"],
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

    # Save routing summary if available
    routing_summary = calculate_routing_summary(results)
    if routing_summary:
        routing_json_path = output_dir / "routing_summary.json"
        with open(routing_json_path, "w", encoding="utf-8") as f:
            json.dump(routing_summary, f, indent=2)
        print(f"Saved: {routing_json_path}")

    return output_dir


def update_metrics_history(
    output_dir: Path,
    summary: dict,
    workspace_path: Path,
    claim_run_id: str = "",
    datasets_evaluated: List[str] = None,
    per_dataset: Dict[str, dict] = None,
    routing_summary: Optional[Dict[str, Any]] = None,
    description: str = "",
):
    """Append this run to metrics_history.json for tracking over time."""
    history_path = workspace_path / "eval" / "metrics_history.json"

    # Load existing history or create new
    if history_path.exists():
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    else:
        history = {
            "schema_version": "metrics_history_v2",
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

    # Build per-dataset metrics sub-object
    per_dataset_metrics = {}
    if per_dataset:
        for ds_id, ds_summary in per_dataset.items():
            per_dataset_metrics[ds_id] = {
                "claims_with_gt": ds_summary["total_claims"],
                "decision_accuracy": round(ds_summary["decision_accuracy"], 3),
                "decision_correct": ds_summary["decision_correct"],
                "decision_wrong": ds_summary["decision_wrong"],
                "false_reject_rate": round(ds_summary["false_reject_rate"], 3),
                "false_approve_rate": round(ds_summary["false_approve_rate"], 3),
            }

    # Create new run entry (backward-compatible: top-level aggregate + new per_dataset)
    run_entry = {
        "run_id": output_dir.name,
        "timestamp": datetime.now().isoformat(),
        "description": description or "Evaluation run",
        "claim_run_id": claim_run_id or None,
        "datasets_evaluated": datasets_evaluated or [],
        "claims_in_run": summary.get("total_in_run", summary["total_claims"]),
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
        "per_dataset": per_dataset_metrics,
        "routing": routing_summary or {},
        "top_errors": top_errors,
        "notes": ""
    }

    # Append to history
    history["runs"].append(run_entry)

    # Save updated history
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print(f"Updated: {history_path}")


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_per_dataset_report(per_dataset: Dict[str, dict], labels: Dict[str, str]):
    """Print per-dataset breakdown to console."""
    print("BY DATASET")
    print("-" * 60)
    for ds_id, ds_summary in per_dataset.items():
        label = labels.get(ds_id, ds_id)
        n = ds_summary["total_claims"]
        if n == 0:
            print(f"{label} ({ds_id}): 0 claims with GT")
            print()
            continue
        processed = ds_summary["processed_claims"]
        correct = ds_summary["decision_correct"]
        acc = ds_summary["decision_accuracy"]
        print(f"{label} -- {ds_id} ({n} claims):")
        print(f"  Decision Accuracy: {acc:.1%} ({correct}/{processed})")
        if ds_summary["gt_approved_total"] > 0:
            print(f"  False Reject Rate: {ds_summary['false_reject_rate']:.1%}")
        if ds_summary["gt_denied_total"] > 0:
            print(f"  False Approve Rate: {ds_summary['false_approve_rate']:.1%}")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Claims Assessment Evaluation")
    parser.add_argument("--run-id", type=str, default=None,
        help="Claim run ID to evaluate. If omitted, uses latest claim run.")
    gt_group = parser.add_mutually_exclusive_group()
    gt_group.add_argument("--ground-truth", type=Path, default=None,
        help="Path to ground truth JSON file (legacy override)")
    gt_group.add_argument("--dataset", type=str, default=None,
        help="Single dataset ID override (e.g., nsa-motor-eval-v1)")
    parser.add_argument("--workspace", type=Path, default=None,
        help="Workspace path (default: workspaces/nsa)")
    args = parser.parse_args()

    workspace_path = args.workspace or DEFAULT_WORKSPACE_PATH

    if not workspace_path.exists():
        print(f"ERROR: Workspace not found: {workspace_path}")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Determine claim run
    # ---------------------------------------------------------------
    claim_run_id = args.run_id
    if not claim_run_id:
        claim_run_id = find_latest_claim_run(workspace_path)
        if not claim_run_id:
            print("ERROR: No claim runs found. Run the pipeline first.")
            sys.exit(1)
        print(f"Auto-detected latest claim run: {claim_run_id}")

    # Discover claims from manifest
    run_claim_ids = discover_run_claims(workspace_path, claim_run_id)
    if run_claim_ids is None:
        print(f"ERROR: Manifest not found for claim run: {claim_run_id}")
        print(f"  Expected: {workspace_path / 'claim_runs' / claim_run_id / 'manifest.json'}")
        sys.exit(1)

    if not run_claim_ids:
        print(f"ERROR: No claims in manifest for {claim_run_id}")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Load ground truth
    # ---------------------------------------------------------------
    dataset_assignments: Dict[str, str] = {}
    dataset_labels: Dict[str, str] = {}
    datasets_used: List[str] = []

    if args.ground_truth:
        # Legacy: single GT file override
        if not args.ground_truth.exists():
            print(f"ERROR: Ground truth not found: {args.ground_truth}")
            sys.exit(1)
        ground_truth = load_single_ground_truth(args.ground_truth)
        datasets_used = ["custom"]
        print(f"Ground truth override: {args.ground_truth} ({len(ground_truth)} claims)")

    elif args.dataset:
        # Legacy: single dataset override
        gt_path = Path(f"data/datasets/{args.dataset}/ground_truth.json")
        if not gt_path.exists():
            print(f"ERROR: Ground truth not found: {gt_path}")
            sys.exit(1)
        ground_truth = load_single_ground_truth(gt_path)
        datasets_used = [args.dataset]
        print(f"Dataset override: {args.dataset} ({len(ground_truth)} claims)")

    else:
        # Auto-detect: load dataset assignments, figure out which datasets the run touches
        dataset_assignments, dataset_labels = load_dataset_assignments(workspace_path)
        if not dataset_assignments:
            print("ERROR: No dataset assignments found.")
            print(f"  Expected: {workspace_path / 'config' / 'datasets.json'}")
            print("  Use --ground-truth or --dataset to specify manually.")
            sys.exit(1)

        # Find which datasets are needed for the claims in this run
        needed_datasets: Set[str] = set()
        unmapped_claims = []
        for cid in run_claim_ids:
            ds = dataset_assignments.get(cid)
            if ds:
                needed_datasets.add(ds)
            else:
                unmapped_claims.append(cid)

        if not needed_datasets and not unmapped_claims:
            print("ERROR: Could not determine datasets for any claims in the run.")
            sys.exit(1)

        print(f"Loading ground truth for {len(needed_datasets)} dataset(s)...")
        ground_truth = load_multi_dataset_ground_truth(needed_datasets)
        datasets_used = sorted(needed_datasets)

        if unmapped_claims:
            print(f"  {len(unmapped_claims)} claim(s) not in datasets.json (will show as no_ground_truth)")

    # ---------------------------------------------------------------
    # Print header
    # ---------------------------------------------------------------
    print()
    print("=" * 60)
    print("Claims Assessment Evaluation")
    print("=" * 60)
    print(f"Claim Run:   {claim_run_id}")
    print(f"Workspace:   {workspace_path}")

    # Dataset summary line
    if datasets_used and datasets_used != ["custom"]:
        # Count how many run claims belong to each dataset
        ds_counts = {}
        for cid in run_claim_ids:
            ds = dataset_assignments.get(cid, "unknown")
            ds_counts[ds] = ds_counts.get(ds, 0) + 1
        ds_parts = []
        for ds_id in datasets_used:
            label = dataset_labels.get(ds_id, ds_id)
            count = ds_counts.get(ds_id, 0)
            ds_parts.append(f"{label} ({count})")
        print(f"Datasets:    {', '.join(ds_parts)}")
    elif datasets_used == ["custom"]:
        print(f"Ground Truth: {args.ground_truth}")

    gt_count = sum(1 for cid in run_claim_ids if cid in ground_truth)
    no_gt_count = len(run_claim_ids) - gt_count
    print(f"Claims:      {len(run_claim_ids)} total, {gt_count} with GT, {no_gt_count} without GT")
    print()

    # ---------------------------------------------------------------
    # Run evaluation
    # ---------------------------------------------------------------
    print("Running evaluation...")
    results = run_evaluation(
        claim_ids=run_claim_ids,
        ground_truth=ground_truth,
        dataset_assignments=dataset_assignments,
        workspace_path=workspace_path,
        target_run_id=claim_run_id,
    )

    # Calculate summaries
    summary = calculate_summary(results)
    per_dataset = calculate_per_dataset_summary(results)
    routing_summary = calculate_routing_summary(results)

    # ---------------------------------------------------------------
    # Console output
    # ---------------------------------------------------------------
    print()
    if len(per_dataset) > 1:
        print_per_dataset_report(per_dataset, dataset_labels)

    print(f"AGGREGATE ({summary['total_claims']} claims with GT)")
    print("-" * 60)
    print(f"Decision Accuracy:   {summary['decision_accuracy']:.1%} ({summary['decision_correct']}/{summary['processed_claims']})")
    print()
    print(f"Approved Claims:     {summary['gt_approved_correct']}/{summary['gt_approved_total']} correct")
    print(f"  False Reject Rate: {summary['false_reject_rate']:.1%}")
    print()
    print(f"Denied Claims:       {summary['gt_denied_correct']}/{summary['gt_denied_total']} correct")
    print(f"  False Approve Rate: {summary['false_approve_rate']:.1%}")
    print()

    # Routing tier breakdown
    if routing_summary:
        print("ROUTING TIER BREAKDOWN")
        print("-" * 60)
        for tier_name in ["GREEN", "YELLOW", "RED"]:
            ts = routing_summary.get(tier_name, {})
            count = ts.get("count", 0)
            pct = ts.get("pct", 0)
            acc = ts.get("accuracy")
            correct = ts.get("correct", 0)
            processed = ts.get("processed", 0)
            acc_str = f"{acc:.1%}" if acc is not None else "N/A"
            print(f"  {tier_name:6s}: {count:3d} claims ({pct:5.1f}%)  Accuracy: {acc_str} ({correct}/{processed})")
        print()

    if summary.get("amount_accuracy_5pct") is not None:
        print(f"Amount Accuracy:     {summary['amount_accuracy_5pct']:.1%} (within +/-5%)")
        print()

    if summary.get("error_categories"):
        print("Error Categories:")
        for cat, count in sorted(summary["error_categories"].items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    if summary.get("no_ground_truth", 0) > 0:
        no_gt_claims = [r["claim_id"] for r in results if r["error_category"] == "no_ground_truth"]
        print()
        print(f"Claims without GT ({len(no_gt_claims)}): {', '.join(no_gt_claims[:10])}")
        if len(no_gt_claims) > 10:
            print(f"  ... and {len(no_gt_claims) - 10} more")

    print()

    # ---------------------------------------------------------------
    # Save results
    # ---------------------------------------------------------------
    output_dir = save_results(results, summary, workspace_path)

    update_metrics_history(
        output_dir=output_dir,
        summary=summary,
        workspace_path=workspace_path,
        claim_run_id=claim_run_id,
        datasets_evaluated=datasets_used,
        per_dataset=per_dataset,
        routing_summary=routing_summary,
    )

    print()
    print(f"Results saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
