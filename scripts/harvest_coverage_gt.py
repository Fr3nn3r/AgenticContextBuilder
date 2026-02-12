"""
Harvest Coverage Classification Ground Truth

Reads data from the most recent claim run for selected claims and assembles
a draft ground truth JSON for evaluating the batch coverage classification prompt.

Usage:
    python scripts/harvest_coverage_gt.py

Output:
    data/datasets/nsa-coverage-classify-v1/ground_truth_draft.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("ERROR: rich not installed. Run: pip install rich")
    sys.exit(1)


# Configuration
WORKSPACE_PATH = Path("workspaces/nsa")
GROUND_TRUTH_PATH = Path("data/datasets/nsa-motor-eval-v1/ground_truth.json")
OUTPUT_DIR = Path("data/datasets/nsa-coverage-classify-v1")
OUTPUT_FILE = OUTPUT_DIR / "ground_truth_draft.json"

# Selected claims: 9 APPROVED + 5 DENIED, mix of FR/DE, range of item counts
SELECTED_CLAIMS = [
    # APPROVED
    "64166",  # fr, 7 items
    "64393",  # de, 5 items
    "64354",  # de, 12 items
    "64659",  # fr, 26 items
    "65055",  # fr, 23 items
    "64288",  # fr, ~35 items - timing chain, Land Rover
    "64792",  # de, ~60 items - piston replacement, Peugeot
    "65027",  # de, ~11 items - coolant pump, Alpina B3
    "64836",  # de, ~11 items - door lock + I-Drive, Rolls Royce Phantom
    # DENIED
    "64951",  # de, 17 items
    "64980",  # fr, 13 items
    "65002",  # de, 10 items
    "65113",  # de, 30 items
    "65211",  # fr, 22 items
]

console = Console(stderr=True)


def find_latest_run(claim_id: str) -> Optional[Path]:
    """Find the most recent claim run folder for a claim."""
    claim_runs_path = WORKSPACE_PATH / "claims" / claim_id / "claim_runs"
    if not claim_runs_path.exists():
        return None
    runs = sorted(claim_runs_path.iterdir())
    return runs[-1] if runs else None


def get_fact_value(facts: List[Dict], name: str) -> Any:
    """Get a fact's value (prefers structured_value, falls back to value)."""
    for fact in facts:
        if fact["name"] == name:
            if fact.get("structured_value") is not None:
                return fact["structured_value"]
            return fact.get("value")
    return None


def compute_labeling_confidence(
    match_method: str, match_confidence: float
) -> Dict[str, str]:
    """Determine labeling confidence and source from match method/confidence.

    Returns dict with labeling_confidence and labeling_source.
    """
    if match_method == "rule":
        return {"labeling_confidence": "high", "labeling_source": "rule"}

    if match_method == "part_number":
        return {"labeling_confidence": "high", "labeling_source": "part_number"}

    # LLM-based matches
    if match_confidence >= 0.80:
        return {"labeling_confidence": "medium", "labeling_source": "system_draft"}

    return {"labeling_confidence": "low", "labeling_source": "system_draft"}


def harvest_claim(claim_id: str, gt_claim: Optional[Dict]) -> Optional[Dict]:
    """Harvest ground truth data for a single claim.

    Args:
        claim_id: The claim identifier.
        gt_claim: Claim-level ground truth data (from nsa-motor-eval-v1).

    Returns:
        Claim dict for the coverage classification GT, or None on error.
    """
    run_path = find_latest_run(claim_id)
    if run_path is None:
        console.print(f"[red]No claim runs found for {claim_id}[/red]")
        return None

    # Load files
    facts_path = run_path / "claim_facts.json"
    cov_path = run_path / "coverage_analysis.json"

    if not facts_path.exists() or not cov_path.exists():
        console.print(f"[red]Missing files for {claim_id} in {run_path.name}[/red]")
        return None

    with open(facts_path, "r", encoding="utf-8") as f:
        facts_data = json.load(f)
    with open(cov_path, "r", encoding="utf-8") as f:
        cov_data = json.load(f)

    facts = facts_data.get("facts", [])

    # Extract policy context
    covered_components = get_fact_value(facts, "covered_components") or {}
    excluded_components = get_fact_value(facts, "excluded_components") or {}
    covered_categories = cov_data.get("inputs", {}).get("covered_categories", [])

    # Build covered_parts_in_claim from line items that are covered parts
    covered_parts_in_claim = []
    for item in cov_data.get("line_items", []):
        if (
            item.get("coverage_status") == "covered"
            and item.get("item_type") == "parts"
        ):
            covered_parts_in_claim.append({
                "item_code": item.get("item_code"),
                "description": item.get("description", ""),
                "matched_component": item.get("matched_component"),
            })

    # Build line items with expected labels
    line_items = []
    for idx, item in enumerate(cov_data.get("line_items", [])):
        coverage_status = item.get("coverage_status", "")
        is_covered = coverage_status == "covered"
        match_method = item.get("match_method", "unknown")
        match_confidence = item.get("match_confidence", 0.0)

        labeling = compute_labeling_confidence(match_method, match_confidence)

        # Build notes from reasoning
        notes = ""
        reasoning = item.get("match_reasoning", "")
        if match_method == "rule":
            rule_info = ""
            for trace in item.get("decision_trace", []):
                if trace.get("stage") == "rule_engine":
                    rule_detail = trace.get("detail", {})
                    rule_info = rule_detail.get("rule", "")
            notes = f"{rule_info}: {reasoning}" if rule_info else reasoning
        elif not is_covered and match_confidence >= 0.80:
            notes = reasoning[:120] if reasoning else ""
        elif is_covered and match_confidence >= 0.80:
            notes = reasoning[:120] if reasoning else ""
        else:
            notes = f"Low confidence ({match_confidence:.2f}): needs manual review"

        line_item = {
            "index": idx,
            "item_code": item.get("item_code"),
            "description": item.get("description", ""),
            "item_type": item.get("item_type", "unknown"),
            "total_price": item.get("total_price", 0.0),
            "hints": item.get("repair_context_description") or "",
            "expected": {
                "is_covered": is_covered,
                "category": item.get("coverage_category") if is_covered else None,
                "matched_component": item.get("matched_component") if is_covered else None,
                "labeling_confidence": labeling["labeling_confidence"],
                "labeling_source": labeling["labeling_source"],
                "notes": notes,
            },
        }
        line_items.append(line_item)

    # Determine language and GT decision from claim-level ground truth
    language = gt_claim.get("language", "unknown") if gt_claim else "unknown"
    gt_decision = gt_claim.get("decision", "UNKNOWN") if gt_claim else "UNKNOWN"
    coverage_notes = gt_claim.get("coverage_notes") if gt_claim else None

    return {
        "claim_id": claim_id,
        "language": language,
        "gt_decision": gt_decision,
        "source_run_id": run_path.name,
        "coverage_notes": coverage_notes,
        "policy_context": {
            "covered_categories": covered_categories,
            "covered_components": covered_components,
            "excluded_components": excluded_components,
        },
        "covered_parts_in_claim": covered_parts_in_claim,
        "line_items": line_items,
    }


def main():
    console.print("[bold]Coverage Classification Ground Truth Harvester[/bold]")
    console.print()

    # Load claim-level ground truth
    if GROUND_TRUTH_PATH.exists():
        with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as f:
            gt_data = json.load(f)
        gt_by_id = {c["claim_id"]: c for c in gt_data.get("claims", [])}
    else:
        console.print(f"[yellow]Warning: Ground truth not found at {GROUND_TRUTH_PATH}[/yellow]")
        gt_by_id = {}

    # Harvest each claim
    claims = []
    total_items = 0
    items_needing_review = 0

    for claim_id in SELECTED_CLAIMS:
        gt_claim = gt_by_id.get(claim_id)
        result = harvest_claim(claim_id, gt_claim)
        if result:
            claims.append(result)
            for item in result["line_items"]:
                total_items += 1
                if item["expected"]["labeling_confidence"] == "low":
                    items_needing_review += 1

    # Build output
    output = {
        "metadata": {
            "schema_version": "coverage_classify_gt_v1",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "total_claims": len(claims),
            "total_items": total_items,
            "items_needing_review": items_needing_review,
            "review_status": "draft",
            "source_ground_truth": str(GROUND_TRUTH_PATH),
        },
        "claims": claims,
    }

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    console.print(f"[green]Saved: {OUTPUT_FILE}[/green]")
    console.print()

    # Print summary table
    table = Table(title="Coverage Classification Ground Truth - Draft")
    table.add_column("Claim", style="cyan")
    table.add_column("Lang")
    table.add_column("Decision")
    table.add_column("Items", justify="right")
    table.add_column("Covered", justify="right")
    table.add_column("Not Covered", justify="right")
    table.add_column("High Conf", justify="right", style="green")
    table.add_column("Medium", justify="right", style="yellow")
    table.add_column("Low (review)", justify="right", style="red")

    for claim in claims:
        items = claim["line_items"]
        n_covered = sum(1 for i in items if i["expected"]["is_covered"])
        n_not_covered = len(items) - n_covered
        n_high = sum(1 for i in items if i["expected"]["labeling_confidence"] == "high")
        n_med = sum(1 for i in items if i["expected"]["labeling_confidence"] == "medium")
        n_low = sum(1 for i in items if i["expected"]["labeling_confidence"] == "low")

        table.add_row(
            claim["claim_id"],
            claim["language"],
            claim["gt_decision"],
            str(len(items)),
            str(n_covered),
            str(n_not_covered),
            str(n_high),
            str(n_med),
            str(n_low),
        )

    # Totals row
    all_items = [i for c in claims for i in c["line_items"]]
    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        f"[bold]{len(all_items)}[/bold]",
        f"[bold]{sum(1 for i in all_items if i['expected']['is_covered'])}[/bold]",
        f"[bold]{sum(1 for i in all_items if not i['expected']['is_covered'])}[/bold]",
        f"[bold]{sum(1 for i in all_items if i['expected']['labeling_confidence'] == 'high')}[/bold]",
        f"[bold]{sum(1 for i in all_items if i['expected']['labeling_confidence'] == 'medium')}[/bold]",
        f"[bold]{sum(1 for i in all_items if i['expected']['labeling_confidence'] == 'low')}[/bold]",
    )

    console.print(table)
    console.print()
    console.print(f"Total items: {total_items}")
    console.print(f"Items needing manual review (low confidence): {items_needing_review}")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Review {OUTPUT_FILE}")
    console.print("  2. Correct per-item labels, set labeling_source='human_corrected' where changed")
    console.print("  3. Set review_status='reviewed' and save as ground_truth.json")


if __name__ == "__main__":
    main()
