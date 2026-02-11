"""
Payout-level accuracy analysis: Which CCI signals separate claims with
accurate payouts from those with large payout errors?

Focuses on correctly-approved claims (decision_correct=True AND gt_decision=APPROVED)
where payout_error_pct is meaningful.
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

DATA_PATH = Path(__file__).parent / "merged_eval_data_enriched.json"

def load_data():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def bucket(pct):
    if pct is None:
        return None
    if pct < 10:
        return "low (<10%)"
    elif pct < 30:
        return "medium (10-30%)"
    else:
        return "high (>30%)"

def safe_mean(values):
    if not values:
        return None
    return statistics.mean(values)

def safe_median(values):
    if not values:
        return None
    return statistics.median(values)

def safe_stdev(values):
    if len(values) < 2:
        return 0
    return statistics.stdev(values)

def main():
    data = load_data()

    # 1. Filter to correctly-approved claims
    approved_correct = [
        r for r in data
        if r.get("decision_correct") is True
        and r.get("gt_decision") == "APPROVED"
        and r.get("payout_error_pct") is not None
    ]
    print("=" * 80)
    print("PAYOUT ACCURACY SIGNAL ANALYSIS")
    print("=" * 80)
    print(f"\nTotal claims in dataset: {len(data)}")
    print(f"Correctly-approved claims with payout data: {len(approved_correct)}")

    # Also compute for ALL approved claims (including decision_correct=False) for context
    all_approved = [
        r for r in data
        if r.get("gt_decision") == "APPROVED"
        and r.get("payout_error_pct") is not None
    ]
    print(f"All approved claims with payout data: {len(all_approved)}")

    # 2. Error distribution
    print("\n" + "=" * 80)
    print("SECTION 1: PAYOUT ERROR DISTRIBUTION")
    print("=" * 80)
    errors = [r["payout_error_pct"] for r in approved_correct]
    errors_abs = [r.get("payout_error_abs", 0) for r in approved_correct]

    buckets = defaultdict(list)
    for r in approved_correct:
        b = bucket(r["payout_error_pct"])
        buckets[b].append(r)

    print(f"\nOverall stats (correctly-approved, n={len(approved_correct)}):")
    print(f"  Mean error %:   {safe_mean(errors):.1f}%")
    print(f"  Median error %: {safe_median(errors):.1f}%")
    print(f"  Stdev error %:  {safe_stdev(errors):.1f}%")
    print(f"  Min error %:    {min(errors):.1f}%")
    print(f"  Max error %:    {max(errors):.1f}%")
    print(f"  Mean abs error: {safe_mean(errors_abs):.2f}")
    print(f"  Median abs:     {safe_median(errors_abs):.2f}")

    print("\nHistogram (payout_error_pct buckets):")
    for b_name in ["low (<10%)", "medium (10-30%)", "high (>30%)"]:
        claims = buckets.get(b_name, [])
        bar = "#" * len(claims)
        ids = [c["claim_id"] for c in claims]
        print(f"  {b_name:18s} | {bar} ({len(claims)}) claims: {ids}")

    # 3. Signal comparison across error buckets
    print("\n" + "=" * 80)
    print("SECTION 2: SIGNAL COMPARISON ACROSS ERROR BUCKETS")
    print("=" * 80)

    signal_keys = [k for k in approved_correct[0].keys() if k.startswith("cci_sig_")]
    component_keys = [k for k in approved_correct[0].keys() if k.startswith("cci_") and not k.startswith("cci_sig_") and k not in ("cci_composite_score", "cci_band", "cci_run_id", "cci_stages_available", "cci_stages_missing", "cci_flags")]

    all_keys = ["cci_composite_score"] + component_keys + signal_keys
    # Add derived keys
    derived_keys = ["num_line_items", "num_items_covered", "num_items_not_covered",
                    "num_items_review_needed", "coverage_pct", "coverage_total_claimed",
                    "coverage_total_covered_gross", "coverage_total_not_covered",
                    "num_clauses_evaluated", "num_clauses_fail", "num_assumptions_used"]
    all_keys += derived_keys

    # Compute means per bucket
    bucket_names = ["low (<10%)", "medium (10-30%)", "high (>30%)"]
    print(f"\n{'Signal':<42s} | {'Low (<10%)':<14s} | {'Med (10-30%)':<14s} | {'High (>30%)':<14s} | {'Spread':>8s}")
    print("-" * 105)

    signal_spreads = []
    for key in all_keys:
        means = {}
        for b_name in bucket_names:
            vals = [r.get(key) for r in buckets.get(b_name, []) if r.get(key) is not None and isinstance(r.get(key), (int, float))]
            means[b_name] = safe_mean(vals)

        # Compute spread (diff between low and high bucket means)
        if means.get("low (<10%)") is not None and means.get("high (>30%)") is not None:
            spread = means["low (<10%)"] - means["high (>30%)"]
        else:
            spread = None

        row = f"{key:<42s}"
        for b_name in bucket_names:
            v = means.get(b_name)
            if v is not None:
                row += f" | {v:<14.4f}"
            else:
                row += f" | {'N/A':<14s}"
        if spread is not None:
            row += f" | {spread:>+8.4f}"
            signal_spreads.append((key, spread, abs(spread)))
        else:
            row += f" | {'N/A':>8s}"
        print(row)

    # Sort by absolute spread to find most discriminative signals
    signal_spreads.sort(key=lambda x: x[2], reverse=True)
    print("\n--- TOP 15 MOST DISCRIMINATIVE SIGNALS (Low vs High bucket spread) ---")
    print(f"{'Rank':<5s} {'Signal':<42s} {'Spread (Low-High)':>18s}")
    print("-" * 70)
    for i, (key, spread, _) in enumerate(signal_spreads[:15], 1):
        direction = "higher=better" if spread > 0 else "higher=worse"
        print(f"{i:<5d} {key:<42s} {spread:>+18.4f}  ({direction})")

    # 4. Coverage reliability deep-dive
    print("\n" + "=" * 80)
    print("SECTION 3: COVERAGE RELIABILITY DEEP-DIVE")
    print("=" * 80)

    coverage_signals = [
        "cci_sig_avg_match_confidence",
        "cci_sig_review_needed_rate",
        "cci_sig_method_diversity",
        "cci_sig_line_item_complexity",
        "cci_sig_primary_repair_confidence",
        "cci_sig_tier1_ratio",
    ]

    for sig in coverage_signals:
        print(f"\n--- {sig} vs payout_error_pct ---")
        pairs = [(r.get(sig), r["payout_error_pct"], r["claim_id"]) for r in approved_correct if r.get(sig) is not None]
        pairs.sort(key=lambda x: x[0])
        # Compute correlation (Pearson)
        if len(pairs) >= 3:
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            mean_x = safe_mean(xs)
            mean_y = safe_mean(ys)
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
            std_x = safe_stdev(xs)
            std_y = safe_stdev(ys)
            if std_x > 0 and std_y > 0:
                corr = cov / (std_x * std_y)
            else:
                corr = 0
            print(f"  Pearson correlation: {corr:.4f}")
        for val, err, cid in pairs:
            print(f"  {sig}={val:.4f}  error={err:.1f}%  claim={cid}")

    # Coverage: items covered vs not covered vs payout error
    print("\n--- Line item coverage breakdown vs payout error ---")
    print(f"{'Claim':<10s} {'Items':<6s} {'Covered':<8s} {'NotCov':<8s} {'Review':<8s} {'CovPct':<8s} {'ErrPct':<8s} {'ErrAbs':<10s} {'Direction':<10s}")
    for r in sorted(approved_correct, key=lambda x: x["payout_error_pct"], reverse=True):
        print(f"{r['claim_id']:<10s} {r.get('num_line_items', 0):<6d} {r.get('num_items_covered', 0):<8d} {r.get('num_items_not_covered', 0):<8d} {r.get('num_items_review_needed', 0):<8d} {r.get('coverage_pct', 0):<8.1f} {r['payout_error_pct']:<8.1f} {r.get('payout_error_abs', 0):<10.2f} {r.get('payout_direction', 'N/A'):<10s}")

    # 5. Match method analysis
    print("\n" + "=" * 80)
    print("SECTION 4: MATCH METHOD ANALYSIS")
    print("=" * 80)

    print("\n--- Match method distribution vs payout error ---")
    for r in sorted(approved_correct, key=lambda x: x["payout_error_pct"], reverse=True):
        methods = r.get("match_methods", {})
        total = sum(methods.values()) if methods else 0
        llm_count = methods.get("llm", 0)
        kw_count = methods.get("keyword", 0)
        pn_count = methods.get("part_number", 0)
        rule_count = methods.get("rule", 0)
        llm_pct = (llm_count / total * 100) if total > 0 else 0
        print(f"  Claim {r['claim_id']:<8s} err={r['payout_error_pct']:.1f}%  methods={methods}  llm_pct={llm_pct:.0f}%  total_items={total}")

    # Compute correlation: llm proportion vs payout error
    llm_pairs = []
    for r in approved_correct:
        methods = r.get("match_methods", {})
        total = sum(methods.values()) if methods else 0
        if total > 0:
            llm_pct = methods.get("llm", 0) / total
            llm_pairs.append((llm_pct, r["payout_error_pct"]))
    if len(llm_pairs) >= 3:
        xs = [p[0] for p in llm_pairs]
        ys = [p[1] for p in llm_pairs]
        mean_x = safe_mean(xs)
        mean_y = safe_mean(ys)
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
        std_x = safe_stdev(xs)
        std_y = safe_stdev(ys)
        corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0
        print(f"\n  Pearson correlation (LLM proportion vs error %): {corr:.4f}")

    # Avg error by primary match method
    print("\n--- Avg payout error by dominant match method ---")
    dominant_groups = defaultdict(list)
    for r in approved_correct:
        methods = r.get("match_methods", {})
        if methods:
            dominant = max(methods, key=methods.get)
            dominant_groups[dominant].append(r["payout_error_pct"])
    for method, errs in sorted(dominant_groups.items()):
        print(f"  Dominant method={method:<15s}  n={len(errs):<3d}  mean_err={safe_mean(errs):.1f}%  median_err={safe_median(errs):.1f}%")

    # 6. Overshoot vs undershoot patterns
    print("\n" + "=" * 80)
    print("SECTION 5: OVERSHOOT VS UNDERSHOOT PATTERNS")
    print("=" * 80)

    overshoots = [r for r in approved_correct if r.get("payout_direction") == "overshoot"]
    undershoots = [r for r in approved_correct if r.get("payout_direction") == "undershoot"]
    print(f"\n  Overshoots: {len(overshoots)}")
    print(f"  Undershoots: {len(undershoots)}")

    # Compare signals between overshoot and undershoot
    print(f"\n{'Signal':<42s} | {'Overshoot Mean':<15s} | {'Undershoot Mean':<15s} | {'Diff':>10s}")
    print("-" * 90)
    direction_spreads = []
    for key in all_keys:
        o_vals = [r.get(key) for r in overshoots if r.get(key) is not None and isinstance(r.get(key), (int, float))]
        u_vals = [r.get(key) for r in undershoots if r.get(key) is not None and isinstance(r.get(key), (int, float))]
        o_mean = safe_mean(o_vals)
        u_mean = safe_mean(u_vals)
        if o_mean is not None and u_mean is not None:
            diff = o_mean - u_mean
            direction_spreads.append((key, diff, abs(diff)))
            print(f"{key:<42s} | {o_mean:<15.4f} | {u_mean:<15.4f} | {diff:>+10.4f}")
        else:
            print(f"{key:<42s} | {'N/A':<15s} | {'N/A':<15s} | {'N/A':>10s}")

    direction_spreads.sort(key=lambda x: x[2], reverse=True)
    print("\n--- TOP 10 SIGNALS DIFFERENTIATING OVERSHOOT VS UNDERSHOOT ---")
    for i, (key, diff, _) in enumerate(direction_spreads[:10], 1):
        direction_label = "higher in overshoot" if diff > 0 else "higher in undershoot"
        print(f"  {i}. {key}: diff={diff:+.4f} ({direction_label})")

    # 7. Line item count effect
    print("\n" + "=" * 80)
    print("SECTION 6: LINE ITEM COUNT VS PAYOUT ERROR")
    print("=" * 80)

    li_pairs = [(r.get("num_line_items", 0), r["payout_error_pct"], r["claim_id"]) for r in approved_correct]
    li_pairs.sort(key=lambda x: x[0])

    # Group by line item count
    li_groups = defaultdict(list)
    for li, err, cid in li_pairs:
        li_groups[li].append(err)

    print(f"\n{'Line Items':<12s} {'n':<5s} {'Mean Err%':<12s} {'Median Err%':<12s} {'Stdev':<10s}")
    print("-" * 55)
    for li_count in sorted(li_groups.keys()):
        errs = li_groups[li_count]
        print(f"{li_count:<12d} {len(errs):<5d} {safe_mean(errs):<12.1f} {safe_median(errs):<12.1f} {safe_stdev(errs):<10.1f}")

    # Correlation
    xs = [p[0] for p in li_pairs]
    ys = [p[1] for p in li_pairs]
    mean_x = safe_mean(xs)
    mean_y = safe_mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
    std_x = safe_stdev(xs)
    std_y = safe_stdev(ys)
    corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0
    print(f"\n  Pearson correlation (line_item_count vs error %): {corr:.4f}")

    # Also: complexity buckets
    print("\n  Complexity buckets:")
    simple = [r["payout_error_pct"] for r in approved_correct if r.get("num_line_items", 0) <= 3]
    moderate = [r["payout_error_pct"] for r in approved_correct if 4 <= r.get("num_line_items", 0) <= 7]
    complex_ = [r["payout_error_pct"] for r in approved_correct if r.get("num_line_items", 0) >= 8]
    print(f"    Simple (<=3 items):   n={len(simple):<3d}  mean_err={safe_mean(simple) if simple else 'N/A'}")
    print(f"    Moderate (4-7 items): n={len(moderate):<3d}  mean_err={safe_mean(moderate) if moderate else 'N/A'}")
    print(f"    Complex (>=8 items):  n={len(complex_):<3d}  mean_err={safe_mean(complex_) if complex_ else 'N/A'}")

    # 8. Missing signals analysis
    print("\n" + "=" * 80)
    print("SECTION 7: MISSING / CANDIDATE SIGNALS ANALYSIS")
    print("=" * 80)

    # Compute candidate signals not currently in CCI
    print("\n--- Candidate signals computed from data ---")
    for r in approved_correct:
        # Covered ratio
        total_claimed = r.get("coverage_total_claimed", 0)
        total_covered = r.get("coverage_total_covered_gross", 0)
        r["_candidate_covered_ratio"] = total_covered / total_claimed if total_claimed > 0 else 0

        # Not-covered ratio
        total_not_covered = r.get("coverage_total_not_covered", 0)
        r["_candidate_not_covered_ratio"] = total_not_covered / total_claimed if total_claimed > 0 else 0

        # Clause fail ratio
        clauses_eval = r.get("num_clauses_evaluated", 0)
        clauses_fail = r.get("num_clauses_fail", 0)
        r["_candidate_clause_fail_ratio"] = clauses_fail / clauses_eval if clauses_eval > 0 else 0

        # Assumption density
        assumptions = r.get("num_assumptions_used", 0)
        r["_candidate_assumption_density"] = assumptions / r.get("num_line_items", 1)

        # LLM match proportion
        methods = r.get("match_methods", {})
        total_m = sum(methods.values()) if methods else 0
        r["_candidate_llm_match_pct"] = methods.get("llm", 0) / total_m if total_m > 0 else 0
        r["_candidate_rule_match_pct"] = methods.get("rule", 0) / total_m if total_m > 0 else 0
        r["_candidate_keyword_match_pct"] = methods.get("keyword", 0) / total_m if total_m > 0 else 0
        r["_candidate_part_number_match_pct"] = methods.get("part_number", 0) / total_m if total_m > 0 else 0

        # Review-needed item ratio
        li = r.get("num_line_items", 0)
        r["_candidate_review_item_ratio"] = r.get("num_items_review_needed", 0) / li if li > 0 else 0

        # Pred vs GT deductible (if both available)
        gt_ded = r.get("gt_deductible")
        # We don't have pred_deductible in the data, so flag this as missing

        # Payout-to-parts ratio (how much of payout is from parts vs labor)
        pred_parts = r.get("pred_parts_total", 0)
        pred_labor = r.get("pred_labor_total", 0)
        pred_payout = r.get("pred_net_payout", 0)
        r["_candidate_parts_ratio"] = pred_parts / pred_payout if pred_payout > 0 else 0
        r["_candidate_labor_ratio"] = pred_labor / pred_payout if pred_payout > 0 else 0

    candidate_keys = [k for k in approved_correct[0].keys() if k.startswith("_candidate_")]
    print(f"\n{'Candidate Signal':<42s} | {'Corr w/ Err%':<14s} | {'Low Bucket':<14s} | {'High Bucket':<14s}")
    print("-" * 90)

    candidate_results = []
    for key in candidate_keys:
        pairs = [(r[key], r["payout_error_pct"]) for r in approved_correct if r.get(key) is not None]
        if len(pairs) >= 3:
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            mean_x = safe_mean(xs)
            mean_y = safe_mean(ys)
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
            std_x = safe_stdev(xs)
            std_y = safe_stdev(ys)
            corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0
        else:
            corr = 0

        low_vals = [r[key] for r in buckets.get("low (<10%)", []) if r.get(key) is not None]
        high_vals = [r[key] for r in buckets.get("high (>30%)", []) if r.get(key) is not None]
        low_mean = safe_mean(low_vals)
        high_mean = safe_mean(high_vals)
        candidate_results.append((key, corr, low_mean, high_mean))
        print(f"{key:<42s} | {corr:<14.4f} | {low_mean if low_mean else 'N/A':<14} | {high_mean if high_mean else 'N/A':<14}")

    # 9. Claim-level deep-dives (top 5 highest error)
    print("\n" + "=" * 80)
    print("SECTION 8: DEEP-DIVE -- TOP 5 HIGHEST PAYOUT ERROR CLAIMS")
    print("=" * 80)

    top5 = sorted(approved_correct, key=lambda x: x["payout_error_pct"], reverse=True)[:5]
    for rank, r in enumerate(top5, 1):
        print(f"\n{'=' * 60}")
        print(f"RANK {rank}: Claim {r['claim_id']}  (error={r['payout_error_pct']:.1f}%, abs={r.get('payout_error_abs', 0):.2f}, direction={r.get('payout_direction', 'N/A')})")
        print(f"{'=' * 60}")
        print(f"  GT approved amount:    {r['gt_total_approved_amount']}")
        print(f"  Pred net payout:       {r.get('pred_net_payout')}")
        print(f"  GT parts/labor/total:  {r.get('gt_parts_approved')} / {r.get('gt_labor_approved')} / {r.get('gt_total_material_labor_approved')}")
        print(f"  Pred parts/labor:      {r.get('pred_parts_total')} / {r.get('pred_labor_total')}")
        print(f"  GT VAT rate:           {r.get('gt_vat_rate_pct')}%")
        print(f"  GT deductible:         {r.get('gt_deductible')}")
        print(f"  GT reimbursement rate: {r.get('gt_reimbursement_rate_pct')}")
        print(f"  GT vehicle:            {r.get('gt_vehicle')}")
        print(f"  GT language:           {r.get('gt_language')}")
        print(f"  Coverage total claimed:    {r.get('coverage_total_claimed')}")
        print(f"  Coverage total covered:    {r.get('coverage_total_covered_gross')}")
        print(f"  Coverage total not covered: {r.get('coverage_total_not_covered')}")
        print(f"  Coverage %:                {r.get('coverage_pct')}")
        print(f"  Line items:                {r.get('num_line_items')}")
        print(f"  Items covered/not/review:  {r.get('num_items_covered')}/{r.get('num_items_not_covered')}/{r.get('num_items_review_needed')}")
        print(f"  Match methods:             {r.get('match_methods')}")
        print(f"  Primary repair:            {r.get('primary_repair_component')}")
        print(f"  Clauses eval/pass/fail:    {r.get('num_clauses_evaluated')}/{r.get('num_clauses_pass')}/{r.get('num_clauses_fail')}")
        print(f"  Failed clauses:            {r.get('failed_clauses')}")
        print(f"  Assumptions used:          {r.get('num_assumptions_used')}")
        print(f"  Unresolved assumptions:    {r.get('num_unresolved_assumptions')}")
        print(f"\n  CCI Composite:     {r.get('cci_composite_score')}")
        print(f"  CCI Band:          {r.get('cci_band')}")
        for key in component_keys:
            print(f"  {key}: {r.get(key)}")
        print(f"\n  CCI Signals:")
        for key in signal_keys:
            print(f"    {key}: {r.get(key)}")

        # Root cause analysis
        print(f"\n  --- ROOT CAUSE ANALYSIS ---")
        gt_total = r.get("gt_total_approved_amount", 0)
        pred_total = r.get("pred_net_payout", 0)
        diff = pred_total - gt_total
        print(f"  Absolute diff: {diff:+.2f} ({r.get('payout_direction', 'N/A')})")

        # Check if deductible/VAT/reimbursement explains it
        gt_mat_labor = r.get("gt_total_material_labor_approved", 0)
        gt_ded = r.get("gt_deductible", 0)
        gt_vat = r.get("gt_vat_rate_pct", 0)
        gt_reimb = r.get("gt_reimbursement_rate_pct")

        if gt_mat_labor and gt_ded is not None and gt_vat is not None:
            # Expected: (material_labor + VAT) - deductible
            expected_with_vat = gt_mat_labor * (1 + gt_vat / 100)
            expected_after_ded = expected_with_vat - gt_ded
            if gt_reimb:
                expected_after_reimb = expected_after_ded * (gt_reimb / 100)
            else:
                expected_after_reimb = expected_after_ded
            print(f"  GT computation check:")
            print(f"    mat_labor={gt_mat_labor}, +VAT({gt_vat}%)={expected_with_vat:.2f}, -ded({gt_ded})={expected_after_ded:.2f}", end="")
            if gt_reimb:
                print(f", *reimb({gt_reimb}%)={expected_after_reimb:.2f}")
            else:
                print()
            print(f"    GT approved={gt_total}, Our check={expected_after_reimb:.2f}, diff={gt_total - expected_after_reimb:.2f}")

        # Check: is the error from coverage (wrong items covered) or from post-coverage math (deductible/VAT)?
        pred_covered = r.get("coverage_total_covered_gross", 0)
        print(f"  Pred covered gross: {pred_covered:.2f}, pred net payout: {pred_total:.2f}")
        if pred_covered > 0 and pred_total > 0:
            coverage_to_payout_ratio = pred_total / pred_covered
            print(f"  Payout/Covered ratio: {coverage_to_payout_ratio:.4f} (1.0 means no deductible/VAT adjustment applied)")
            if abs(coverage_to_payout_ratio - 1.0) < 0.01:
                print(f"  ** WARNING: Payout equals gross covered -- deductible/VAT may not be applied! **")

    # 10. Summary statistics
    print("\n" + "=" * 80)
    print("SECTION 9: SUMMARY -- KEY FINDINGS")
    print("=" * 80)

    print("\n--- Correlation ranking (existing signals vs payout_error_pct) ---")
    corr_results = []
    for key in all_keys:
        pairs = [(r.get(key), r["payout_error_pct"]) for r in approved_correct if r.get(key) is not None and isinstance(r.get(key), (int, float))]
        if len(pairs) >= 3:
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            mean_x = safe_mean(xs)
            mean_y = safe_mean(ys)
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)
            std_x = safe_stdev(xs)
            std_y = safe_stdev(ys)
            corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0
            corr_results.append((key, corr))
    corr_results.sort(key=lambda x: abs(x[1]), reverse=True)
    print(f"\n{'Rank':<5s} {'Signal':<42s} {'Correlation':>12s} {'Direction':<20s}")
    print("-" * 85)
    for i, (key, corr) in enumerate(corr_results[:20], 1):
        direction = "more signal = more error" if corr > 0 else "more signal = less error"
        print(f"{i:<5d} {key:<42s} {corr:>+12.4f} ({direction})")

    # Candidate signals correlation ranking
    print("\n--- Correlation ranking (CANDIDATE signals vs payout_error_pct) ---")
    candidate_results.sort(key=lambda x: abs(x[1]), reverse=True)
    for key, corr, low_m, high_m in candidate_results:
        direction = "more signal = more error" if corr > 0 else "more signal = less error"
        print(f"  {key:<42s} corr={corr:>+.4f} ({direction})")


if __name__ == "__main__":
    main()
