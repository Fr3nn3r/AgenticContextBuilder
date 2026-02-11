"""
Enrich merged_eval_data.json with predicted decisions and payouts from decision dossiers.
Reads from the latest run (clm_20260211_162539_654ce3) and also tries the most recent
confidence run (clm_20260211_184521_96ec30).
"""
import json
import glob
import os

WORKSPACE = "workspaces/nsa"
MERGED_PATH = "plans/cci-analysis/merged_eval_data.json"
OUTPUT_PATH = "plans/cci-analysis/merged_eval_data_enriched.json"

# Priority order of runs to check for decision dossiers
RUN_IDS = [
    "clm_20260211_162539_654ce3",  # eval #48 run (the one with 92% accuracy)
    "clm_20260211_184521_96ec30",  # latest CCI run
    "clm_20260211_105352_c56208",  # earlier run
]

def load_merged():
    with open(MERGED_PATH) as f:
        return json.load(f)


def find_latest_dossier(claim_id):
    """Find the latest decision dossier for a claim across all runs."""
    for run_id in RUN_IDS:
        path = f"{WORKSPACE}/claims/{claim_id}/claim_runs/{run_id}/decision_dossier_v1.json"
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f), run_id
    # Fallback: glob for any decision dossier
    pattern = f"{WORKSPACE}/claims/{claim_id}/claim_runs/*/decision_dossier_v1.json"
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if files:
        with open(files[0]) as f:
            return json.load(f), os.path.basename(os.path.dirname(files[0]))
    return None, None


def find_coverage_analysis(claim_id):
    """Find the latest coverage analysis for a claim."""
    for run_id in RUN_IDS:
        path = f"{WORKSPACE}/claims/{claim_id}/claim_runs/{run_id}/coverage_analysis.json"
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    pattern = f"{WORKSPACE}/claims/{claim_id}/claim_runs/*/coverage_analysis.json"
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    if files:
        with open(files[0]) as f:
            return json.load(f)
    return None


def find_screening_result(claim_id):
    """Find the latest screening result for a claim."""
    for run_id in RUN_IDS:
        path = f"{WORKSPACE}/claims/{claim_id}/claim_runs/{run_id}/screening_result.json"
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


def enrich():
    data = load_merged()
    enriched_count = 0
    errors_found = []

    for claim in data:
        cid = claim["claim_id"]

        # --- Decision dossier ---
        dossier, run_id = find_latest_dossier(cid)
        if dossier:
            # Predicted decision
            verdict = dossier.get("claim_verdict", "").upper()
            # Normalize: APPROVE -> APPROVED, DENY -> DENIED
            if verdict == "APPROVE":
                pred_decision = "APPROVED"
            elif verdict in ("DENY", "REJECT"):
                pred_decision = "DENIED"
            elif verdict == "REFER":
                pred_decision = "REFER"
            else:
                pred_decision = verdict

            claim["pred_decision"] = pred_decision
            claim["pred_decision_run_id"] = run_id

            # Financial summary
            fin = dossier.get("financial_summary", {})
            claim["pred_net_payout"] = fin.get("net_payout")
            claim["pred_total_claimed"] = fin.get("total_claimed")
            claim["pred_total_covered"] = fin.get("total_covered")
            claim["pred_total_denied"] = fin.get("total_denied")
            claim["pred_parts_total"] = fin.get("parts_total")
            claim["pred_labor_total"] = fin.get("labor_total")

            # Decision accuracy
            gt_dec = claim.get("gt_decision")
            if gt_dec and pred_decision:
                claim["decision_correct"] = (gt_dec == pred_decision)
                if not claim["decision_correct"]:
                    if gt_dec == "APPROVED" and pred_decision == "DENIED":
                        claim["error_type"] = "false_reject"
                    elif gt_dec == "DENIED" and pred_decision == "APPROVED":
                        claim["error_type"] = "false_approve"
                    else:
                        claim["error_type"] = f"mismatch_{gt_dec}_{pred_decision}"
                    errors_found.append(cid)
                else:
                    claim["error_type"] = None

            # Payout accuracy (only for approved claims with GT payout)
            gt_payout = claim.get("gt_total_approved_amount")
            pred_payout = claim.get("pred_net_payout")
            if gt_payout and pred_payout and gt_payout > 0:
                claim["payout_error_abs"] = abs(pred_payout - gt_payout)
                claim["payout_error_pct"] = abs(pred_payout - gt_payout) / gt_payout * 100
                claim["payout_direction"] = "overshoot" if pred_payout > gt_payout else "undershoot" if pred_payout < gt_payout else "exact"
            elif gt_dec == "DENIED" and pred_decision == "DENIED":
                # Both denied, payout accuracy is perfect
                claim["payout_error_abs"] = 0
                claim["payout_error_pct"] = 0
                claim["payout_direction"] = "exact"

            # Clause evaluation stats
            clauses = dossier.get("clause_evaluations", [])
            claim["num_clauses_evaluated"] = len(clauses)
            claim["num_clauses_pass"] = sum(1 for c in clauses if c.get("verdict") == "PASS")
            claim["num_clauses_fail"] = sum(1 for c in clauses if c.get("verdict") in ("FAIL", "LIMITATION"))
            claim["num_assumptions_used"] = sum(1 for c in clauses if c.get("assumption_used"))
            claim["failed_clauses"] = dossier.get("failed_clauses", [])

            # Unresolved assumptions
            unresolved = dossier.get("unresolved_assumptions", [])
            claim["num_unresolved_assumptions"] = len(unresolved)

            enriched_count += 1

        # --- Coverage analysis ---
        coverage = find_coverage_analysis(cid)
        if coverage:
            line_items = coverage.get("line_items", [])
            summary = coverage.get("summary", {})
            claim["num_line_items"] = len(line_items)
            claim["num_items_covered"] = summary.get("items_covered", 0)
            claim["num_items_not_covered"] = summary.get("items_not_covered", 0)
            claim["num_items_review_needed"] = summary.get("items_review_needed", 0)
            claim["coverage_total_claimed"] = summary.get("total_claimed")
            claim["coverage_total_covered_gross"] = summary.get("total_covered_gross")
            claim["coverage_total_not_covered"] = summary.get("total_not_covered")
            claim["coverage_pct"] = summary.get("coverage_percent")

            # Match method breakdown
            methods = {}
            for item in line_items:
                m = item.get("match_method", "unknown")
                methods[m] = methods.get(m, 0) + 1
            claim["match_methods"] = methods

            # Primary repair info
            pr = coverage.get("primary_repair", {})
            claim["primary_repair_component"] = pr.get("component")
            claim["primary_repair_method"] = pr.get("method")
            claim["primary_repair_confidence"] = pr.get("confidence")

        # --- Screening result ---
        screening = find_screening_result(cid)
        if screening:
            checks = screening.get("checks", [])
            claim["num_screening_checks"] = len(checks)
            claim["screening_hard_fails"] = [c.get("check_name") for c in checks if c.get("result") == "FAIL" and c.get("severity") == "hard"]
            claim["screening_soft_fails"] = [c.get("check_name") for c in checks if c.get("result") == "FAIL" and c.get("severity") == "soft"]
            claim["screening_inconclusive"] = [c.get("check_name") for c in checks if c.get("result") == "INCONCLUSIVE"]

    # Add has_prediction flag
    for claim in data:
        claim["has_prediction"] = claim.get("pred_decision") is not None

    # Write enriched data
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)

    # Print summary
    print(f"Enriched {enriched_count}/{len(data)} claims with decision dossier data")
    print(f"Errors found: {len(errors_found)} claims: {errors_found}")
    print()

    # Decision accuracy
    with_decision = [c for c in data if c.get("decision_correct") is not None]
    correct = sum(1 for c in with_decision if c["decision_correct"])
    print(f"Decision accuracy: {correct}/{len(with_decision)} ({correct/len(with_decision)*100:.1f}%)")

    false_rejects = [c for c in data if c.get("error_type") == "false_reject"]
    false_approves = [c for c in data if c.get("error_type") == "false_approve"]
    print(f"  False rejects: {len(false_rejects)} - claims {[c['claim_id'] for c in false_rejects]}")
    print(f"  False approves: {len(false_approves)} - claims {[c['claim_id'] for c in false_approves]}")
    print()

    # CCI distribution by accuracy
    correct_claims = [c for c in data if c.get("decision_correct") == True]
    wrong_claims = [c for c in data if c.get("decision_correct") == False]

    if correct_claims:
        scores = [c["cci_composite_score"] for c in correct_claims if c.get("cci_composite_score")]
        print(f"CCI for CORRECT decisions (n={len(scores)}): mean={sum(scores)/len(scores):.3f}, min={min(scores):.3f}, max={max(scores):.3f}")
    if wrong_claims:
        scores = [c["cci_composite_score"] for c in wrong_claims if c.get("cci_composite_score")]
        print(f"CCI for WRONG decisions (n={len(scores)}):   mean={sum(scores)/len(scores):.3f}, min={min(scores):.3f}, max={max(scores):.3f}")

    print()

    # Payout accuracy distribution
    with_payout = [c for c in data if c.get("payout_error_pct") is not None and c.get("gt_decision") == "APPROVED" and c.get("decision_correct")]
    if with_payout:
        errors = [c["payout_error_pct"] for c in with_payout]
        print(f"Payout error (correctly approved, n={len(with_payout)}): mean={sum(errors)/len(errors):.1f}%, min={min(errors):.1f}%, max={max(errors):.1f}%")
        low = sum(1 for e in errors if e < 10)
        med = sum(1 for e in errors if 10 <= e < 30)
        high = sum(1 for e in errors if e >= 30)
        print(f"  Low (<10%): {low}, Medium (10-30%): {med}, High (>30%): {high}")

    print(f"\nOutput written to {OUTPUT_PATH}")


if __name__ == "__main__":
    enrich()
