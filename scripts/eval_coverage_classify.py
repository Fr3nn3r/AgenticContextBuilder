"""
Coverage Classification Prompt Evaluation

Runs the batch classification prompt against a ground truth dataset in isolation
(no full pipeline) and reports detailed accuracy metrics.

Reuses LLMMatcher._build_batch_classify_prompt() and _parse_batch_classify_response()
directly to ensure we test the EXACT same prompt the pipeline uses.

Usage:
    python scripts/eval_coverage_classify.py                          # Full eval
    python scripts/eval_coverage_classify.py --claim 64393            # Single claim
    python scripts/eval_coverage_classify.py --dry-run                # Show prompts, no LLM calls
    python scripts/eval_coverage_classify.py --no-covered-parts       # Test without covered parts context
    python scripts/eval_coverage_classify.py --gt-file path/to/gt.json  # Custom GT file
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("ERROR: rich not installed. Run: pip install rich")
    sys.exit(1)

from context_builder.startup import ensure_initialized
ensure_initialized()

from context_builder.coverage.llm_matcher import LLMMatcher, LLMMatcherConfig, LLMMatchResult

console = Console(stderr=True)

# Default paths
DEFAULT_GT_DIR = Path("data/datasets/nsa-coverage-classify-v1")
DEFAULT_GT_FILE = DEFAULT_GT_DIR / "ground_truth.json"
DEFAULT_DRAFT_GT_FILE = DEFAULT_GT_DIR / "ground_truth_draft.json"
EVAL_RESULTS_DIR = DEFAULT_GT_DIR / "eval_results"


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------

def load_ground_truth(gt_path: Path) -> Dict[str, Any]:
    """Load the ground truth dataset."""
    if not gt_path.exists():
        console.print(f"[red]Ground truth not found: {gt_path}[/red]")
        sys.exit(1)

    with open(gt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    schema = data.get("metadata", {}).get("schema_version", "")
    if schema != "coverage_classify_gt_v1":
        console.print(f"[yellow]Warning: unexpected schema version '{schema}'[/yellow]")

    return data


# ------------------------------------------------------------------
# Running classification
# ------------------------------------------------------------------

def run_classification_for_claim(
    matcher: LLMMatcher,
    claim: Dict[str, Any],
    include_covered_parts: bool = True,
) -> Tuple[List[LLMMatchResult], List[Dict[str, str]], float]:
    """Run batch classification for a single claim.

    Args:
        matcher: The LLMMatcher instance.
        claim: Claim dict from the ground truth.
        include_covered_parts: Whether to include covered_parts_in_claim context.

    Returns:
        Tuple of (predicted results, prompt messages, elapsed_seconds).
    """
    policy = claim["policy_context"]
    covered_components = policy.get("covered_components", {})
    excluded_components = policy.get("excluded_components", {})
    covered_parts = claim.get("covered_parts_in_claim", []) if include_covered_parts else []

    # Build items list matching the format expected by _build_batch_classify_prompt
    items = []
    for li in claim["line_items"]:
        items.append({
            "description": li.get("description", ""),
            "item_type": li.get("item_type", "unknown"),
            "item_code": li.get("item_code"),
            "total_price": li.get("total_price", 0.0),
            "repair_context_description": li.get("hints") or None,
        })

    # Build prompt (always, for inspection/logging)
    messages = matcher._build_batch_classify_prompt(
        items=items,
        covered_components=covered_components,
        excluded_components=excluded_components,
        covered_parts_in_claim=covered_parts,
    )

    # Call LLM
    from context_builder.services.llm_audit import create_audited_client

    client = create_audited_client()
    client.set_context(
        claim_id=claim["claim_id"],
        call_purpose="coverage_classify_eval",
    )

    start = time.time()
    response = client.chat_completions_create(
        model=matcher.config.model,
        messages=messages,
        temperature=matcher.config.temperature,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    elapsed = time.time() - start

    content = response.choices[0].message.content
    results = matcher._parse_batch_classify_response(content, items)

    return results, messages, elapsed


def build_prompt_for_claim(
    matcher: LLMMatcher,
    claim: Dict[str, Any],
    include_covered_parts: bool = True,
) -> List[Dict[str, str]]:
    """Build the prompt without calling the LLM (for dry-run)."""
    policy = claim["policy_context"]
    items = []
    for li in claim["line_items"]:
        items.append({
            "description": li.get("description", ""),
            "item_type": li.get("item_type", "unknown"),
            "item_code": li.get("item_code"),
            "total_price": li.get("total_price", 0.0),
            "repair_context_description": li.get("hints") or None,
        })

    covered_parts = claim.get("covered_parts_in_claim", []) if include_covered_parts else []
    return matcher._build_batch_classify_prompt(
        items=items,
        covered_components=policy.get("covered_components", {}),
        excluded_components=policy.get("excluded_components", {}),
        covered_parts_in_claim=covered_parts,
    )


# ------------------------------------------------------------------
# Metrics computation
# ------------------------------------------------------------------

def compare_item(
    expected: Dict[str, Any],
    predicted: LLMMatchResult,
    line_item: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare expected vs predicted for a single item.

    Returns a detailed comparison dict.
    """
    exp_covered = expected.get("is_covered", False)
    pred_covered = predicted.is_covered

    coverage_match = exp_covered == pred_covered

    # Category match (only relevant when both say covered)
    category_match = None
    if exp_covered and pred_covered:
        exp_cat = (expected.get("category") or "").lower()
        pred_cat = (predicted.category or "").lower()
        category_match = exp_cat == pred_cat

    # Component match (only relevant when both say covered)
    component_match = None
    if exp_covered and pred_covered:
        exp_comp = (expected.get("matched_component") or "").lower()
        pred_comp = (predicted.matched_component or "").lower()
        # Fuzzy: check containment in either direction
        if exp_comp and pred_comp:
            component_match = exp_comp in pred_comp or pred_comp in exp_comp
        elif not exp_comp and not pred_comp:
            component_match = True
        else:
            component_match = False

    return {
        "index": line_item.get("index", 0),
        "description": line_item.get("description", ""),
        "item_type": line_item.get("item_type", ""),
        "total_price": line_item.get("total_price", 0.0),
        "expected_covered": exp_covered,
        "predicted_covered": pred_covered,
        "coverage_match": coverage_match,
        "expected_category": expected.get("category"),
        "predicted_category": predicted.category,
        "category_match": category_match,
        "expected_component": expected.get("matched_component"),
        "predicted_component": predicted.matched_component,
        "component_match": component_match,
        "predicted_confidence": predicted.confidence,
        "predicted_reasoning": predicted.reasoning,
        "labeling_confidence": expected.get("labeling_confidence", "unknown"),
        "labeling_source": expected.get("labeling_source", "unknown"),
    }


def compute_metrics(
    all_comparisons: List[Dict[str, Any]],
    claim_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute aggregate metrics from all item comparisons.

    Args:
        all_comparisons: Flat list of per-item comparison dicts.
        claim_results: Per-claim result dicts with timing info.

    Returns:
        Summary metrics dict.
    """
    n = len(all_comparisons)
    if n == 0:
        return {"error": "No items to evaluate"}

    # Coverage accuracy
    correct = sum(1 for c in all_comparisons if c["coverage_match"])
    coverage_accuracy = correct / n

    # Confusion matrix: covered/not-covered
    tp = sum(1 for c in all_comparisons if c["expected_covered"] and c["predicted_covered"])
    fp = sum(1 for c in all_comparisons if not c["expected_covered"] and c["predicted_covered"])
    fn = sum(1 for c in all_comparisons if c["expected_covered"] and not c["predicted_covered"])
    tn = sum(1 for c in all_comparisons if not c["expected_covered"] and not c["predicted_covered"])

    # Precision/recall for "covered"
    covered_precision = tp / (tp + fp) if (tp + fp) > 0 else None
    covered_recall = tp / (tp + fn) if (tp + fn) > 0 else None

    # Precision/recall for "not_covered"
    not_covered_precision = tn / (tn + fn) if (tn + fn) > 0 else None
    not_covered_recall = tn / (tn + fp) if (tn + fp) > 0 else None

    # Category accuracy (among correctly predicted covered items)
    both_covered = [c for c in all_comparisons if c["expected_covered"] and c["predicted_covered"]]
    cat_correct = sum(1 for c in both_covered if c["category_match"]) if both_covered else 0
    category_accuracy = cat_correct / len(both_covered) if both_covered else None

    # Component accuracy (among correctly predicted covered items)
    comp_correct = sum(1 for c in both_covered if c["component_match"]) if both_covered else 0
    component_accuracy = comp_correct / len(both_covered) if both_covered else None

    # By item_type
    by_type = {}
    for item_type in ["parts", "labor", "fee"]:
        items_of_type = [c for c in all_comparisons if c["item_type"] == item_type]
        if items_of_type:
            by_type[item_type] = {
                "total": len(items_of_type),
                "correct": sum(1 for c in items_of_type if c["coverage_match"]),
                "accuracy": sum(1 for c in items_of_type if c["coverage_match"]) / len(items_of_type),
            }

    # By language (from claim_results)
    by_language = {}
    for cr in claim_results:
        lang = cr.get("language", "unknown")
        if lang not in by_language:
            by_language[lang] = {"total": 0, "correct": 0}
        for comp in cr.get("comparisons", []):
            by_language[lang]["total"] += 1
            if comp["coverage_match"]:
                by_language[lang]["correct"] += 1
    for lang in by_language:
        stats = by_language[lang]
        stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] > 0 else 0

    # Confidence calibration
    correct_items = [c for c in all_comparisons if c["coverage_match"]]
    incorrect_items = [c for c in all_comparisons if not c["coverage_match"]]
    mean_conf_correct = (
        sum(c["predicted_confidence"] for c in correct_items) / len(correct_items)
        if correct_items else None
    )
    mean_conf_incorrect = (
        sum(c["predicted_confidence"] for c in incorrect_items) / len(incorrect_items)
        if incorrect_items else None
    )

    # Error list
    errors = [
        {
            "claim_id": c.get("claim_id", ""),
            "index": c["index"],
            "description": c["description"],
            "item_type": c["item_type"],
            "expected_covered": c["expected_covered"],
            "predicted_covered": c["predicted_covered"],
            "predicted_confidence": c["predicted_confidence"],
            "predicted_reasoning": c["predicted_reasoning"],
            "labeling_confidence": c["labeling_confidence"],
        }
        for c in all_comparisons
        if not c["coverage_match"]
    ]

    # Timing
    total_time = sum(cr.get("elapsed_seconds", 0) for cr in claim_results)
    total_llm_calls = len(claim_results)

    return {
        "total_items": n,
        "coverage_accuracy": round(coverage_accuracy, 4),
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
        },
        "covered_precision": round(covered_precision, 4) if covered_precision is not None else None,
        "covered_recall": round(covered_recall, 4) if covered_recall is not None else None,
        "not_covered_precision": round(not_covered_precision, 4) if not_covered_precision is not None else None,
        "not_covered_recall": round(not_covered_recall, 4) if not_covered_recall is not None else None,
        "category_accuracy": round(category_accuracy, 4) if category_accuracy is not None else None,
        "component_accuracy": round(component_accuracy, 4) if component_accuracy is not None else None,
        "by_item_type": by_type,
        "by_language": by_language,
        "confidence_calibration": {
            "mean_confidence_correct": round(mean_conf_correct, 4) if mean_conf_correct is not None else None,
            "mean_confidence_incorrect": round(mean_conf_incorrect, 4) if mean_conf_incorrect is not None else None,
        },
        "errors": errors,
        "total_errors": len(errors),
        "total_llm_calls": total_llm_calls,
        "total_time_seconds": round(total_time, 2),
    }


# ------------------------------------------------------------------
# Output / reporting
# ------------------------------------------------------------------

def print_summary(metrics: Dict[str, Any], claim_results: List[Dict[str, Any]]):
    """Print a Rich summary to the console."""
    console.print()
    console.print("[bold]=" * 60)
    console.print("[bold]Coverage Classification Evaluation Results")
    console.print("[bold]=" * 60)
    console.print()

    if "error" in metrics:
        console.print(f"[red]{metrics['error']}[/red]")
        return

    # Overall accuracy
    table = Table(title="Overall Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total items", str(metrics["total_items"]))
    table.add_row("Coverage accuracy", f"{metrics['coverage_accuracy']:.1%}")
    table.add_row("Total errors", str(metrics["total_errors"]))
    table.add_row("", "")
    table.add_row("Covered precision", _fmt_pct(metrics.get("covered_precision")))
    table.add_row("Covered recall", _fmt_pct(metrics.get("covered_recall")))
    table.add_row("Not-covered precision", _fmt_pct(metrics.get("not_covered_precision")))
    table.add_row("Not-covered recall", _fmt_pct(metrics.get("not_covered_recall")))
    table.add_row("", "")
    table.add_row("Category accuracy", _fmt_pct(metrics.get("category_accuracy")))
    table.add_row("Component accuracy", _fmt_pct(metrics.get("component_accuracy")))
    table.add_row("", "")
    table.add_row("LLM calls", str(metrics["total_llm_calls"]))
    table.add_row("Total time", f"{metrics['total_time_seconds']:.1f}s")

    console.print(table)
    console.print()

    # Confusion matrix
    cm = metrics["confusion_matrix"]
    cm_table = Table(title="Confusion Matrix")
    cm_table.add_column("")
    cm_table.add_column("Pred: Covered", justify="right")
    cm_table.add_column("Pred: Not Covered", justify="right")
    cm_table.add_row("Actual: Covered", f"[green]{cm['true_positive']}[/green]", f"[red]{cm['false_negative']}[/red]")
    cm_table.add_row("Actual: Not Covered", f"[red]{cm['false_positive']}[/red]", f"[green]{cm['true_negative']}[/green]")
    console.print(cm_table)
    console.print()

    # By item type
    by_type = metrics.get("by_item_type", {})
    if by_type:
        type_table = Table(title="Accuracy by Item Type")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Total", justify="right")
        type_table.add_column("Correct", justify="right")
        type_table.add_column("Accuracy", justify="right")
        for t in ["parts", "labor", "fee"]:
            if t in by_type:
                s = by_type[t]
                type_table.add_row(t, str(s["total"]), str(s["correct"]), f"{s['accuracy']:.1%}")
        console.print(type_table)
        console.print()

    # By language
    by_lang = metrics.get("by_language", {})
    if by_lang:
        lang_table = Table(title="Accuracy by Language")
        lang_table.add_column("Language", style="cyan")
        lang_table.add_column("Total", justify="right")
        lang_table.add_column("Correct", justify="right")
        lang_table.add_column("Accuracy", justify="right")
        for lang, s in sorted(by_lang.items()):
            lang_table.add_row(lang, str(s["total"]), str(s["correct"]), f"{s['accuracy']:.1%}")
        console.print(lang_table)
        console.print()

    # Confidence calibration
    cal = metrics.get("confidence_calibration", {})
    console.print("[bold]Confidence Calibration:[/bold]")
    console.print(f"  Mean confidence (correct):   {_fmt_pct(cal.get('mean_confidence_correct'))}")
    console.print(f"  Mean confidence (incorrect): {_fmt_pct(cal.get('mean_confidence_incorrect'))}")
    console.print()

    # Per-claim summary
    per_claim_table = Table(title="Per-Claim Results")
    per_claim_table.add_column("Claim", style="cyan")
    per_claim_table.add_column("Lang")
    per_claim_table.add_column("Items", justify="right")
    per_claim_table.add_column("Correct", justify="right")
    per_claim_table.add_column("Accuracy", justify="right")
    per_claim_table.add_column("Time", justify="right")

    for cr in claim_results:
        comps = cr.get("comparisons", [])
        n_correct = sum(1 for c in comps if c["coverage_match"])
        acc = n_correct / len(comps) if comps else 0
        per_claim_table.add_row(
            cr["claim_id"],
            cr.get("language", "?"),
            str(len(comps)),
            str(n_correct),
            f"{acc:.0%}",
            f"{cr.get('elapsed_seconds', 0):.1f}s",
        )
    console.print(per_claim_table)
    console.print()

    # Errors
    errors = metrics.get("errors", [])
    if errors:
        err_table = Table(title=f"Errors ({len(errors)} items)")
        err_table.add_column("Claim", style="cyan")
        err_table.add_column("Idx", justify="right")
        err_table.add_column("Description", max_width=35)
        err_table.add_column("Type")
        err_table.add_column("Expected")
        err_table.add_column("Predicted")
        err_table.add_column("Conf", justify="right")
        err_table.add_column("GT Conf")

        for err in errors:
            err_table.add_row(
                str(err.get("claim_id", "")),
                str(err["index"]),
                err["description"][:35],
                err["item_type"],
                "[green]covered[/green]" if err["expected_covered"] else "[red]not_covered[/red]",
                "[green]covered[/green]" if err["predicted_covered"] else "[red]not_covered[/red]",
                f"{err['predicted_confidence']:.2f}",
                err.get("labeling_confidence", "?"),
            )
        console.print(err_table)
    else:
        console.print("[green]No errors - perfect accuracy![/green]")


def _fmt_pct(value: Optional[float]) -> str:
    """Format a float as percentage or N/A."""
    if value is None:
        return "N/A"
    return f"{value:.1%}"


def save_results(
    metrics: Dict[str, Any],
    claim_results: List[Dict[str, Any]],
    gt_path: Path,
    include_covered_parts: bool,
) -> Path:
    """Save evaluation results to disk."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = EVAL_RESULTS_DIR / f"eval_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Summary
    summary = {
        "eval_timestamp": datetime.now().isoformat(),
        "ground_truth_file": str(gt_path),
        "include_covered_parts": include_covered_parts,
        "model": LLMMatcherConfig().model,
        **metrics,
    }
    # Remove errors from summary (they go in details)
    summary.pop("errors", None)

    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Details (per-claim with all comparisons)
    details = {
        "eval_timestamp": datetime.now().isoformat(),
        "claims": [],
    }
    for cr in claim_results:
        details["claims"].append({
            "claim_id": cr["claim_id"],
            "language": cr.get("language", "unknown"),
            "elapsed_seconds": cr.get("elapsed_seconds", 0),
            "items": cr.get("comparisons", []),
        })

    with open(output_dir / "details.json", "w", encoding="utf-8") as f:
        json.dump(details, f, indent=2, ensure_ascii=False)

    return output_dir


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Coverage Classification Prompt Evaluation"
    )
    parser.add_argument(
        "--claim", type=str, default=None,
        help="Evaluate a single claim ID"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show prompts without making LLM calls"
    )
    parser.add_argument(
        "--no-covered-parts", action="store_true",
        help="Test without covered_parts_in_claim context"
    )
    parser.add_argument(
        "--gt-file", type=Path, default=None,
        help="Custom ground truth file path"
    )
    args = parser.parse_args()

    # Resolve GT path: explicit > reviewed > draft
    if args.gt_file:
        gt_path = args.gt_file
    elif DEFAULT_GT_FILE.exists():
        gt_path = DEFAULT_GT_FILE
    elif DEFAULT_DRAFT_GT_FILE.exists():
        gt_path = DEFAULT_DRAFT_GT_FILE
        console.print(f"[yellow]Using draft GT (no reviewed ground_truth.json found)[/yellow]")
    else:
        console.print(f"[red]No ground truth file found. Run harvest_coverage_gt.py first.[/red]")
        sys.exit(1)

    include_covered_parts = not args.no_covered_parts

    console.print("[bold]Coverage Classification Prompt Evaluation[/bold]")
    console.print(f"  GT file: {gt_path}")
    console.print(f"  Include covered parts: {include_covered_parts}")
    if args.dry_run:
        console.print("  [yellow]DRY RUN - no LLM calls[/yellow]")
    console.print()

    # Load data
    gt_data = load_ground_truth(gt_path)
    claims = gt_data.get("claims", [])

    # Filter to single claim if requested
    if args.claim:
        claims = [c for c in claims if c["claim_id"] == args.claim]
        if not claims:
            console.print(f"[red]Claim {args.claim} not found in ground truth[/red]")
            sys.exit(1)

    console.print(f"Evaluating {len(claims)} claims, {sum(len(c['line_items']) for c in claims)} items")
    console.print()

    # Create matcher (reuses production prompt-building logic)
    matcher = LLMMatcher(config=LLMMatcherConfig())

    if args.dry_run:
        # Show prompts only
        for claim in claims:
            messages = build_prompt_for_claim(matcher, claim, include_covered_parts)
            console.print(f"[bold cyan]Claim {claim['claim_id']}[/bold cyan] ({len(claim['line_items'])} items)")
            console.print(f"[dim]System prompt length: {len(messages[0]['content'])} chars[/dim]")
            console.print(f"[dim]User prompt length: {len(messages[1]['content'])} chars[/dim]")
            console.print()
            console.print("[bold]System:[/bold]")
            console.print(messages[0]["content"][:500] + "..." if len(messages[0]["content"]) > 500 else messages[0]["content"])
            console.print()
            console.print("[bold]User:[/bold]")
            console.print(messages[1]["content"][:1000] + "..." if len(messages[1]["content"]) > 1000 else messages[1]["content"])
            console.print()
            console.print("-" * 60)
            console.print()
        return

    # Run evaluation
    all_comparisons = []
    claim_results = []

    for claim in claims:
        claim_id = claim["claim_id"]
        console.print(f"Evaluating {claim_id} ({len(claim['line_items'])} items)...", end=" ")

        try:
            predictions, messages, elapsed = run_classification_for_claim(
                matcher, claim, include_covered_parts
            )
        except Exception as e:
            console.print(f"[red]FAILED: {e}[/red]")
            claim_results.append({
                "claim_id": claim_id,
                "language": claim.get("language", "unknown"),
                "error": str(e),
                "comparisons": [],
                "elapsed_seconds": 0,
            })
            continue

        # Compare predictions vs expected
        comparisons = []
        for li, pred in zip(claim["line_items"], predictions):
            comp = compare_item(li["expected"], pred, li)
            comp["claim_id"] = claim_id
            comparisons.append(comp)

        n_correct = sum(1 for c in comparisons if c["coverage_match"])
        acc = n_correct / len(comparisons) if comparisons else 0
        console.print(f"[green]{n_correct}/{len(comparisons)}[/green] ({acc:.0%}) in {elapsed:.1f}s")

        all_comparisons.extend(comparisons)
        claim_results.append({
            "claim_id": claim_id,
            "language": claim.get("language", "unknown"),
            "comparisons": comparisons,
            "elapsed_seconds": elapsed,
        })

    # Compute metrics
    metrics = compute_metrics(all_comparisons, claim_results)

    # Print summary
    print_summary(metrics, claim_results)

    # Save results
    output_dir = save_results(metrics, claim_results, gt_path, include_covered_parts)
    console.print(f"[green]Results saved to: {output_dir}[/green]")


if __name__ == "__main__":
    main()
