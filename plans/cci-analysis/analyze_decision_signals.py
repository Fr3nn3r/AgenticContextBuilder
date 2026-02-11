"""
Decision-level accuracy signal analysis for CCI tuning.

Compares CCI signals between correct and incorrect decisions to find
which signals best separate right from wrong.
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict

DATA_PATH = Path(__file__).parent / "merged_eval_data_enriched.json"


def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_numeric_signal_keys(claims):
    """Identify all numeric CCI signal keys."""
    numeric_keys = []
    skip_keys = {
        "claim_id", "gt_decision", "gt_denial_reason", "gt_currency",
        "gt_vehicle", "gt_language", "cci_band", "cci_run_id",
        "cci_stages_available", "cci_stages_missing", "cci_flags",
        "decision_correct", "has_ground_truth", "has_assessment_eval",
        "has_claim_eval_report", "has_confidence_summary", "has_decision_log",
        "pred_decision", "pred_decision_run_id", "error_type",
        "payout_direction", "failed_clauses", "match_methods",
        "primary_repair_component", "primary_repair_method", "has_prediction",
        "source_count",
    }
    sample = claims[0]
    for k, v in sample.items():
        if k in skip_keys:
            continue
        if isinstance(v, (int, float)) and v is not None:
            numeric_keys.append(k)
    return sorted(numeric_keys)


def safe_stats(values):
    """Compute mean, median, stdev for a list of numbers (handling None)."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None, None, None
    mean = statistics.mean(clean)
    median = statistics.median(clean)
    stdev = statistics.stdev(clean) if len(clean) > 1 else 0.0
    return mean, median, stdev


def print_separator(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def group_comparison(claims, numeric_keys):
    """Compare correct vs incorrect decisions on every numeric signal."""
    print_separator("1. GROUP COMPARISON: Correct vs Incorrect Decisions")

    correct = [c for c in claims if c["decision_correct"]]
    incorrect = [c for c in claims if not c["decision_correct"]]
    print(f"\nCorrect: {len(correct)} claims | Incorrect: {len(incorrect)} claims")

    rows = []
    for key in numeric_keys:
        c_vals = [c.get(key) for c in correct]
        i_vals = [c.get(key) for c in incorrect]
        c_mean, c_med, c_std = safe_stats(c_vals)
        i_mean, i_med, i_std = safe_stats(i_vals)
        if c_mean is not None and i_mean is not None:
            diff = abs(c_mean - i_mean)
            rows.append((key, c_mean, c_med, c_std, i_mean, i_med, i_std, diff))

    # Sort by absolute difference
    rows.sort(key=lambda r: r[7], reverse=True)

    print(f"\n{'Signal':<45} {'Correct Mean':>12} {'Incorrect Mean':>14} {'Diff':>8}")
    print("-" * 82)
    for key, c_mean, c_med, c_std, i_mean, i_med, i_std, diff in rows:
        marker = " ***" if diff > 0.1 else " **" if diff > 0.05 else ""
        print(f"{key:<45} {c_mean:>12.4f} {i_mean:>14.4f} {diff:>8.4f}{marker}")

    return rows


def error_deep_dive(claims):
    """Print all signals for each wrong claim."""
    print_separator("2. ERROR DEEP-DIVE: Wrong Claims Analysis")

    incorrect = [c for c in claims if not c["decision_correct"]]
    correct = [c for c in claims if c["decision_correct"]]

    # Compute correct-group means for comparison
    numeric_keys = get_numeric_signal_keys(claims)
    correct_means = {}
    for key in numeric_keys:
        vals = [c.get(key) for c in correct if c.get(key) is not None]
        if vals:
            correct_means[key] = statistics.mean(vals)

    for claim in incorrect:
        print(f"\n--- Claim {claim['claim_id']} ---")
        print(f"  GT Decision: {claim['gt_decision']} | Pred Decision: {claim.get('pred_decision', 'N/A')}")
        print(f"  Error Type: {claim.get('error_type', 'N/A')}")
        print(f"  CCI Score: {claim.get('cci_composite_score', 'N/A')} | Band: {claim.get('cci_band', 'N/A')}")
        print(f"  GT Approved Amount: {claim.get('gt_total_approved_amount', 'N/A')}")
        print(f"  Pred Net Payout: {claim.get('pred_net_payout', 'N/A')}")
        print(f"  Pred Total Claimed: {claim.get('pred_total_claimed', 'N/A')}")
        print(f"  Pred Total Covered: {claim.get('pred_total_covered', 'N/A')}")
        print(f"  Payout Error %: {claim.get('payout_error_pct', 'N/A')}")
        print(f"  Failed Clauses: {claim.get('failed_clauses', [])}")
        print(f"  Match Methods: {claim.get('match_methods', {})}")
        print(f"  Primary Repair: {claim.get('primary_repair_component', 'N/A')}")
        print(f"  Primary Repair Confidence: {claim.get('primary_repair_confidence', 'N/A')}")
        print(f"  Num Line Items: {claim.get('num_line_items', 'N/A')}")
        print(f"  Items Covered/Not/Review: {claim.get('num_items_covered', 0)}/{claim.get('num_items_not_covered', 0)}/{claim.get('num_items_review_needed', 0)}")
        print(f"  Clauses Eval/Pass/Fail: {claim.get('num_clauses_evaluated', 0)}/{claim.get('num_clauses_pass', 0)}/{claim.get('num_clauses_fail', 0)}")
        print(f"  Assumptions Used: {claim.get('num_assumptions_used', 0)} | Unresolved: {claim.get('num_unresolved_assumptions', 0)}")
        print(f"  Screening Hard/Soft/Inconclusive: {claim.get('screening_hard_fails', 0)}/{claim.get('screening_soft_fails', 0)}/{claim.get('screening_inconclusive', 0)}")

        # Show CCI signals with deviation from correct mean
        print(f"\n  CCI Signals (deviation from correct-group mean):")
        print(f"  {'Signal':<45} {'Value':>8} {'Correct Mean':>12} {'Deviation':>10}")
        print(f"  {'-'*78}")
        deviations = []
        for key in numeric_keys:
            if key.startswith("cci_") or key.startswith("num_") or key.startswith("screening_"):
                val = claim.get(key)
                cm = correct_means.get(key)
                if val is not None and cm is not None:
                    dev = val - cm
                    deviations.append((key, val, cm, dev))

        # Sort by absolute deviation
        deviations.sort(key=lambda x: abs(x[3]), reverse=True)
        for key, val, cm, dev in deviations:
            flag = " <<<" if abs(dev) > 0.15 else " <<" if abs(dev) > 0.08 else ""
            print(f"  {key:<45} {val:>8.4f} {cm:>12.4f} {dev:>+10.4f}{flag}")


def signal_ranking(rows):
    """Rank signals by separation power (abs diff in means)."""
    print_separator("3. SIGNAL RANKING: Best Separators of Correct vs Incorrect")

    print(f"\n{'Rank':<6} {'Signal':<45} {'Mean Diff':>10} {'Quality'}")
    print("-" * 75)
    for i, (key, c_mean, c_med, c_std, i_mean, i_med, i_std, diff) in enumerate(rows[:30], 1):
        if diff > 0.15:
            quality = "STRONG"
        elif diff > 0.08:
            quality = "MODERATE"
        elif diff > 0.03:
            quality = "WEAK"
        else:
            quality = "NOISE"
        direction = "correct > incorrect" if c_mean > i_mean else "incorrect > correct"
        print(f"{i:<6} {key:<45} {diff:>10.4f} {quality:<10} ({direction})")


def band_analysis(claims):
    """Cross-tab CCI band vs decision accuracy."""
    print_separator("4. BAND ANALYSIS: CCI Band vs Decision Accuracy")

    bands = defaultdict(lambda: {"correct": 0, "incorrect": 0, "total": 0})
    for c in claims:
        band = c.get("cci_band", "unknown")
        bands[band]["total"] += 1
        if c["decision_correct"]:
            bands[band]["correct"] += 1
        else:
            bands[band]["incorrect"] += 1

    print(f"\n{'Band':<15} {'Total':>6} {'Correct':>8} {'Incorrect':>10} {'Accuracy':>10}")
    print("-" * 52)
    for band in sorted(bands.keys()):
        d = bands[band]
        acc = d["correct"] / d["total"] * 100 if d["total"] > 0 else 0
        print(f"{band:<15} {d['total']:>6} {d['correct']:>8} {d['incorrect']:>10} {acc:>9.1f}%")

    # Also look at composite score distribution
    correct = [c["cci_composite_score"] for c in claims if c["decision_correct"] and c.get("cci_composite_score")]
    incorrect = [c["cci_composite_score"] for c in claims if not c["decision_correct"] and c.get("cci_composite_score")]
    print(f"\nComposite Score Distribution:")
    print(f"  Correct:   mean={statistics.mean(correct):.4f}, min={min(correct):.4f}, max={max(correct):.4f}")
    if incorrect:
        print(f"  Incorrect: mean={statistics.mean(incorrect):.4f}, min={min(incorrect):.4f}, max={max(incorrect):.4f}")
    print(f"\n  Overlap: Incorrect claims range [{min(incorrect):.4f} - {max(incorrect):.4f}]")
    print(f"           Correct claims range   [{min(correct):.4f} - {max(correct):.4f}]")
    low_correct = [c for c in correct if c < max(incorrect)]
    print(f"  {len(low_correct)} correct claims have composite score below worst incorrect ({max(incorrect):.4f})")


def threshold_analysis(claims, numeric_keys):
    """For key components, find thresholds where accuracy drops."""
    print_separator("5. THRESHOLD ANALYSIS: Component Thresholds and Accuracy")

    component_keys = [
        "cci_composite_score", "cci_document_quality", "cci_data_completeness",
        "cci_consistency", "cci_coverage_reliability", "cci_decision_clarity",
    ]
    # Also check key signals
    signal_keys = [
        "cci_sig_avg_match_confidence", "cci_sig_critical_facts_rate",
        "cci_sig_screening_pass_rate", "cci_sig_assumption_reliance",
        "cci_sig_tier1_ratio", "cci_sig_primary_repair_confidence",
        "cci_sig_conflict_rate", "cci_sig_data_gap_penalty",
        "cci_sig_gate_status_score", "cci_sig_review_needed_rate",
    ]

    all_keys = component_keys + signal_keys

    for key in all_keys:
        vals_with_truth = [(c.get(key), c["decision_correct"]) for c in claims if c.get(key) is not None]
        if not vals_with_truth:
            continue

        vals_with_truth.sort(key=lambda x: x[0])
        all_vals = [v[0] for v in vals_with_truth]

        # Try several thresholds
        thresholds = sorted(set([
            statistics.median(all_vals),
            statistics.mean(all_vals) - statistics.stdev(all_vals) if len(all_vals) > 1 else statistics.mean(all_vals),
            min(all_vals) + (max(all_vals) - min(all_vals)) * 0.25,
            min(all_vals) + (max(all_vals) - min(all_vals)) * 0.33,
        ]))

        best_threshold = None
        best_lift = 0

        for threshold in thresholds:
            below = [(v, t) for v, t in vals_with_truth if v < threshold]
            above = [(v, t) for v, t in vals_with_truth if v >= threshold]
            if len(below) < 1 or len(above) < 1:
                continue
            acc_below = sum(1 for _, t in below if t) / len(below) * 100
            acc_above = sum(1 for _, t in above if t) / len(above) * 100
            lift = acc_above - acc_below
            if lift > best_lift:
                best_lift = lift
                best_threshold = (threshold, len(below), acc_below, len(above), acc_above)

        if best_threshold:
            thr, n_below, acc_below, n_above, acc_above = best_threshold
            incorrect_below = [c for c in claims if not c["decision_correct"] and c.get(key) is not None and c[key] < thr]
            flag = " *** USEFUL" if acc_below < 85 and n_below >= 2 else ""
            print(f"\n{key}:")
            print(f"  Best threshold: {thr:.4f}")
            print(f"  Below: {n_below} claims, accuracy {acc_below:.1f}%")
            print(f"  Above: {n_above} claims, accuracy {acc_above:.1f}%")
            print(f"  Lift: {acc_above - acc_below:.1f} pp{flag}")
            if incorrect_below:
                print(f"  Wrong claims below threshold: {[c['claim_id'] for c in incorrect_below]}")


def red_flag_combinations(claims):
    """Look for signal combinations that predict errors."""
    print_separator("6. RED FLAG COMBINATIONS: Multi-Signal Error Patterns")

    correct = [c for c in claims if c["decision_correct"]]
    incorrect = [c for c in claims if not c["decision_correct"]]

    # Define conditions to test
    conditions = {
        "low_coverage_reliability": lambda c: c.get("cci_coverage_reliability", 1) < 0.75,
        "low_consistency": lambda c: c.get("cci_consistency", 1) < 0.55,
        "high_assumption_reliance": lambda c: c.get("cci_sig_assumption_reliance", 1) < 0.85,  # Lower means more assumptions
        "low_critical_facts": lambda c: c.get("cci_sig_critical_facts_rate", 1) < 0.70,
        "low_match_confidence": lambda c: c.get("cci_sig_avg_match_confidence", 1) < 0.80,
        "low_screening_pass": lambda c: c.get("cci_sig_screening_pass_rate", 1) < 0.85,
        "gate_zero": lambda c: c.get("cci_sig_gate_status_score", 1) == 0.0,
        "low_tier1_ratio": lambda c: c.get("cci_sig_tier1_ratio", 1) < 0.50,
        "low_data_completeness": lambda c: c.get("cci_data_completeness", 1) < 0.80,
        "has_hard_fails": lambda c: c.get("screening_hard_fails", 0) > 0,
        "many_assumptions": lambda c: c.get("num_assumptions_used", 0) > 10,
        "low_primary_repair_conf": lambda c: c.get("cci_sig_primary_repair_confidence", 1) < 0.80,
        "high_clause_fail_rate": lambda c: (c.get("num_clauses_fail", 0) / max(c.get("num_clauses_evaluated", 1), 1)) > 0.15,
    }

    # Test individual conditions
    print("\nIndividual Condition Prevalence:")
    print(f"{'Condition':<35} {'Correct':>8} {'Incorrect':>10} {'Error Rate':>10}")
    print("-" * 66)
    for name, cond in conditions.items():
        c_count = sum(1 for c in correct if cond(c))
        i_count = sum(1 for c in incorrect if cond(c))
        total = c_count + i_count
        err_rate = i_count / total * 100 if total > 0 else 0
        baseline = len(incorrect) / len(claims) * 100
        flag = " ***" if err_rate > baseline * 2 and total >= 2 else ""
        print(f"{name:<35} {c_count:>8} {i_count:>10} {err_rate:>9.1f}%{flag}")

    # Test pairs
    print(f"\nPairwise Combinations (showing those with elevated error rate):")
    print(f"Baseline error rate: {len(incorrect) / len(claims) * 100:.1f}%\n")
    cond_names = list(conditions.keys())
    for i in range(len(cond_names)):
        for j in range(i + 1, len(cond_names)):
            name1, cond1 = cond_names[i], conditions[cond_names[i]]
            name2, cond2 = cond_names[j], conditions[cond_names[j]]
            both_correct = sum(1 for c in correct if cond1(c) and cond2(c))
            both_incorrect = sum(1 for c in incorrect if cond1(c) and cond2(c))
            total = both_correct + both_incorrect
            if total >= 2:
                err_rate = both_incorrect / total * 100
                baseline = len(incorrect) / len(claims) * 100
                if err_rate > baseline * 1.5:
                    print(f"  {name1} + {name2}: {total} claims, {both_incorrect} wrong ({err_rate:.1f}%)")


def coverage_method_analysis(claims):
    """Analyze match method distributions vs errors."""
    print_separator("7. COVERAGE METHOD ANALYSIS: Match Methods vs Errors")

    correct = [c for c in claims if c["decision_correct"]]
    incorrect = [c for c in claims if not c["decision_correct"]]

    # Aggregate match method stats
    def method_stats(group, label):
        methods = defaultdict(list)
        total_items = []
        for c in group:
            mm = c.get("match_methods", {})
            total = sum(mm.values()) if mm else 0
            total_items.append(total)
            for method, count in mm.items():
                methods[method].append(count)
                # Also compute fraction
        print(f"\n{label} ({len(group)} claims):")
        for method in sorted(set(list(methods.keys()))):
            vals = methods[method]
            mean_count = statistics.mean(vals) if vals else 0
            prevalence = len(vals) / len(group) * 100
            print(f"  {method:<20} avg_count={mean_count:.1f}, present_in={prevalence:.0f}% of claims")

    method_stats(correct, "Correct Decisions")
    method_stats(incorrect, "Incorrect Decisions")

    # Per-claim method breakdown for wrong claims
    print("\nWrong Claims - Individual Method Breakdowns:")
    for c in incorrect:
        mm = c.get("match_methods", {})
        total = sum(mm.values()) if mm else 0
        print(f"  {c['claim_id']}: {mm} (total={total}), "
              f"tier1_ratio={c.get('cci_sig_tier1_ratio', 'N/A')}, "
              f"match_conf={c.get('cci_sig_avg_match_confidence', 'N/A'):.4f}")

    # LLM-heavy claims
    print("\nLLM-heavy analysis (claims where LLM is majority method):")
    for c in claims:
        mm = c.get("match_methods", {})
        total = sum(mm.values()) if mm else 0
        llm_count = mm.get("llm", 0)
        if total > 0 and llm_count / total > 0.5:
            status = "CORRECT" if c["decision_correct"] else "WRONG"
            print(f"  {c['claim_id']}: {status}, LLM={llm_count}/{total} ({llm_count/total*100:.0f}%), "
                  f"match_conf={c.get('cci_sig_avg_match_confidence', 'N/A')}")


def payout_materiality_analysis(claims):
    """Analyze payout materiality signal, especially for claim 65113."""
    print_separator("8. PAYOUT MATERIALITY: Trivial Payout on Large Claim Pattern")

    # Find claim 65113
    c65113 = next((c for c in claims if c["claim_id"] == "65113"), None)

    if c65113:
        print(f"\nClaim 65113 Deep Dive:")
        print(f"  GT Decision: {c65113['gt_decision']}")
        print(f"  Pred Decision: {c65113.get('pred_decision')}")
        print(f"  Error Type: {c65113.get('error_type')}")
        print(f"  GT Approved Amount: {c65113.get('gt_total_approved_amount')}")
        print(f"  Pred Net Payout: {c65113.get('pred_net_payout')}")
        print(f"  Pred Total Claimed: {c65113.get('pred_total_claimed')}")
        print(f"  Pred Total Covered: {c65113.get('pred_total_covered')}")
        print(f"  Coverage %: {c65113.get('coverage_pct')}")
        if c65113.get("pred_total_claimed") and c65113.get("pred_net_payout"):
            payout_ratio = c65113["pred_net_payout"] / c65113["pred_total_claimed"]
            print(f"  Payout/Claimed Ratio: {payout_ratio:.4f} ({payout_ratio*100:.2f}%)")
        print(f"  Num Line Items: {c65113.get('num_line_items')}")
        print(f"  Items Covered/Not/Review: {c65113.get('num_items_covered')}/{c65113.get('num_items_not_covered')}/{c65113.get('num_items_review_needed')}")
        print(f"  Clauses Fail: {c65113.get('num_clauses_fail')}")
        print(f"  Failed Clauses: {c65113.get('failed_clauses')}")
        print(f"  Match Methods: {c65113.get('match_methods')}")

    # Compute payout/claimed ratio for all claims
    print("\nPayout/Claimed Ratio Analysis:")
    ratios = []
    for c in claims:
        total_claimed = c.get("pred_total_claimed") or c.get("coverage_total_claimed")
        net_payout = c.get("pred_net_payout")
        if total_claimed and net_payout and total_claimed > 0:
            ratio = net_payout / total_claimed
            ratios.append((c["claim_id"], ratio, c["decision_correct"], c.get("error_type")))

    ratios.sort(key=lambda x: x[1])
    print(f"\n{'Claim':<10} {'Payout/Claimed':>15} {'Correct':>8} {'Error Type'}")
    print("-" * 48)
    for cid, ratio, correct, err in ratios[:10]:
        print(f"{cid:<10} {ratio:>14.4f} {'Y' if correct else 'N':>8} {err or ''}")

    # Coverage ratio analysis
    print("\nCoverage Percentage Distribution:")
    for c in claims:
        cov_pct = c.get("coverage_pct")
        if cov_pct is not None and not c["decision_correct"]:
            total_claimed = c.get("pred_total_claimed", 0)
            net_payout = c.get("pred_net_payout", 0)
            print(f"  WRONG - {c['claim_id']}: coverage_pct={cov_pct:.1f}%, "
                  f"claimed={total_claimed}, payout={net_payout}")

    # Check for small-payout-on-large-claim
    print("\nSmall Payout on Large Claim (<5% payout ratio):")
    for cid, ratio, correct, err in ratios:
        if ratio < 0.05:
            print(f"  {cid}: ratio={ratio:.4f}, correct={'Y' if correct else 'N'}, error={err or 'none'}")

    # Covered item ratio
    print("\nCovered Item Ratio (covered / total line items):")
    for c in claims:
        n_items = c.get("num_line_items", 0)
        n_covered = c.get("num_items_covered", 0)
        if n_items > 0:
            ratio = n_covered / n_items
            if not c["decision_correct"]:
                print(f"  WRONG - {c['claim_id']}: {n_covered}/{n_items} = {ratio:.2f}")


def summary_statistics(claims):
    """Print overall summary."""
    print_separator("SUMMARY STATISTICS")

    correct = [c for c in claims if c["decision_correct"]]
    incorrect = [c for c in claims if not c["decision_correct"]]

    print(f"\nTotal claims with ground truth: {len(claims)}")
    print(f"Correct decisions: {len(correct)} ({len(correct)/len(claims)*100:.1f}%)")
    print(f"Incorrect decisions: {len(incorrect)} ({len(incorrect)/len(claims)*100:.1f}%)")

    false_rejects = [c for c in incorrect if c.get("error_type") == "false_reject"]
    false_approves = [c for c in incorrect if c.get("error_type") == "false_approve"]
    print(f"  False rejects: {len(false_rejects)} {[c['claim_id'] for c in false_rejects]}")
    print(f"  False approves: {len(false_approves)} {[c['claim_id'] for c in false_approves]}")


def main():
    claims = load_data()

    # Filter to only claims with ground truth and predictions
    claims = [c for c in claims if c.get("has_ground_truth") and c.get("has_prediction")]
    numeric_keys = get_numeric_signal_keys(claims)

    summary_statistics(claims)
    rows = group_comparison(claims, numeric_keys)
    error_deep_dive(claims)
    signal_ranking(rows)
    band_analysis(claims)
    threshold_analysis(claims, numeric_keys)
    red_flag_combinations(claims)
    coverage_method_analysis(claims)
    payout_materiality_analysis(claims)


if __name__ == "__main__":
    main()
