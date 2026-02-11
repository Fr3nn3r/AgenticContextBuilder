"""
Collect and merge per-claim eval data from 5 sources into a single dataset.

Sources:
  1. ground_truth.json          — 54 claims with decision, payout, vehicle info
  2. assessment_eval_*.json     — 6 eval files with AI vs expected per claim
  3. *-claim-eval-report.json   — 3 detailed claim eval reports
  4. confidence_summary.json    — 60+ CCI files (per claim run)
  5. decisions.jsonl             — decision log with assessment outcomes

Output: plans/cci-analysis/merged_eval_data.json
"""

import json
import glob
import os
import sys
from pathlib import Path
from collections import defaultdict

# ── paths ────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent.parent          # repo root
WS   = BASE / "workspaces" / "nsa"
OUT  = BASE / "plans" / "cci-analysis" / "merged_eval_data.json"


# ── 1. Ground truth ─────────────────────────────────────────────────────

def load_ground_truth() -> dict:
    """Return {claim_id: {decision, payout fields, vehicle, ...}}."""
    path = WS / "config" / "ground_truth.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    by_id = {}
    for c in data["claims"]:
        cid = str(c["claim_id"])
        by_id[cid] = {
            "gt_decision": c.get("decision"),
            "gt_total_approved_amount": c.get("total_approved_amount"),
            "gt_parts_approved": c.get("parts_approved"),
            "gt_labor_approved": c.get("labor_approved"),
            "gt_total_material_labor_approved": c.get("total_material_labor_approved"),
            "gt_vat_rate_pct": c.get("vat_rate_pct"),
            "gt_deductible": c.get("deductible"),
            "gt_reimbursement_rate_pct": c.get("reimbursement_rate_pct"),
            "gt_currency": c.get("currency"),
            "gt_vehicle": c.get("vehicle"),
            "gt_language": c.get("language"),
            "gt_denial_reason": c.get("denial_reason"),
        }
    print(f"[ground_truth]  {len(by_id)} claims loaded")
    return by_id


# ── 2. Assessment eval results ──────────────────────────────────────────

def load_assessment_evals() -> dict:
    """Merge all assessment_eval_*.json files.

    When the same claim appears in multiple eval files, keep the entry
    from the most recent file (by filename timestamp).
    """
    pattern = str(WS / "eval" / "assessment_eval_*.json")
    files = sorted(glob.glob(pattern))  # sorted = chronological by filename
    by_id = {}
    total_entries = 0
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        eval_mode = data.get("eval_mode", data.get("schema_version", ""))
        for r in data.get("results", []):
            cid = str(r["claim_id"])
            total_entries += 1
            by_id[cid] = {
                "eval_ai_decision": r.get("ai_decision"),
                "eval_expected_decision": r.get("expected_decision"),
                "eval_decision_match": r.get("decision_match"),
                "eval_decision_acceptable": r.get("decision_acceptable"),
                "eval_passed": r.get("passed"),
                "eval_ai_payout": r.get("ai_payout"),
                "eval_ai_payout_raw": r.get("ai_payout_raw"),
                "eval_expected_payout": r.get("expected_payout"),
                "eval_payout_diff": r.get("payout_diff"),
                "eval_payout_match": r.get("payout_match"),
                "eval_component": r.get("component"),
                "eval_expected_rejection_reason": r.get("expected_rejection_reason"),
                "eval_ai_rationale": r.get("ai_rationale"),
                "eval_confidence_score": r.get("confidence_score"),
                "eval_mode": r.get("eval_mode", eval_mode),
                "eval_source_file": os.path.basename(fpath),
            }
    print(f"[assessment_eval] {len(by_id)} unique claims from {len(files)} files ({total_entries} total entries)")
    return by_id


# ── 3. Claim eval reports ───────────────────────────────────────────────

def load_claim_eval_reports() -> dict:
    """Load *-claim-eval-report.json files into {claim_id: {...}}."""
    pattern = str(WS / "eval" / "*-claim-eval-report.json")
    files = sorted(glob.glob(pattern))
    by_id = {}
    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        cid = str(data["claim_id"])

        # Coverage line item stats
        cov = data.get("coverage_analysis", {})
        totals = cov.get("totals", {})
        line_items = cov.get("line_items", [])
        num_line_items = len(line_items)

        # Count match methods
        match_methods = defaultdict(int)
        for li in line_items:
            mm = li.get("match_method", "unknown")
            match_methods[mm] += 1

        # Payout
        pay = data.get("payout_calculation", {})

        # Screening checks
        sc = data.get("screening_checks", {})
        checks_pass = sum(1 for v in sc.values() if isinstance(v, dict) and v.get("verdict") == "PASS")
        checks_fail = sum(1 for v in sc.values() if isinstance(v, dict) and v.get("verdict") == "FAIL")
        checks_skip = sum(1 for v in sc.values() if isinstance(v, dict) and v.get("verdict") == "SKIPPED")

        by_id[cid] = {
            "report_result": data.get("result"),
            "report_result_detail": data.get("result_detail"),
            "report_run_id": data.get("run_id"),
            "report_pipeline_decision": data.get("pipeline_output", {}).get("decision"),
            "report_pipeline_payout": data.get("pipeline_output", {}).get("final_payout"),
            "report_pipeline_confidence": data.get("pipeline_output", {}).get("confidence_score"),
            "report_gt_total_approved": data.get("ground_truth", {}).get("total_approved_amount"),
            "report_payout_diff_chf": data.get("comparison", {}).get("payout_diff_chf"),
            "report_payout_diff_pct": data.get("comparison", {}).get("payout_diff_pct"),
            "report_within_tolerance": data.get("comparison", {}).get("within_tolerance"),
            "report_primary_component": data.get("repair", {}).get("primary_component"),
            "report_coverage_category": data.get("repair", {}).get("coverage_category"),
            "report_shop_authorized": data.get("repair", {}).get("shop_authorized"),
            "report_num_line_items": num_line_items,
            "report_total_claimed": totals.get("total_claimed"),
            "report_total_covered": totals.get("total_covered_before_excess"),
            "report_total_not_covered": totals.get("total_not_covered"),
            "report_items_covered": totals.get("items_covered"),
            "report_items_not_covered": totals.get("items_not_covered"),
            "report_match_methods": dict(match_methods),
            "report_coverage_pct": pay.get("coverage_percent"),
            "report_max_coverage": pay.get("max_coverage"),
            "report_max_coverage_applied": pay.get("max_coverage_applied"),
            "report_deductible_amount": pay.get("deductible_amount"),
            "report_final_payout": pay.get("final_payout"),
            "report_checks_pass": checks_pass,
            "report_checks_fail": checks_fail,
            "report_checks_skip": checks_skip,
            "report_vehicle_km": data.get("vehicle", {}).get("odometer_km"),
            "report_vehicle_km_limit": data.get("vehicle", {}).get("km_limit"),
            "report_notes": data.get("notes"),
        }
    print(f"[claim_eval_reports] {len(by_id)} reports loaded from {len(files)} files")
    return by_id


# ── 4. Confidence summaries (CCI) ───────────────────────────────────────

def load_confidence_summaries() -> dict:
    """Load the most recent confidence_summary.json per claim.

    Multiple runs may exist; we pick the latest run (alphabetically last
    claim_run_id, which encodes timestamp).
    """
    pattern = str(WS / "claims" / "*" / "claim_runs" / "*" / "confidence_summary.json")
    files = sorted(glob.glob(pattern))

    # Group by claim_id, keep latest run
    by_claim = {}  # claim_id -> (run_id, path)
    for fpath in files:
        parts = Path(fpath).parts
        # .../claims/{claim_id}/claim_runs/{run_id}/confidence_summary.json
        claim_id = parts[-4]
        run_id = parts[-2]
        if claim_id not in by_claim or run_id > by_claim[claim_id][0]:
            by_claim[claim_id] = (run_id, fpath)

    by_id = {}
    for cid, (run_id, fpath) in by_claim.items():
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)

        # Component scores
        comp_scores = {}
        for comp in data.get("component_scores", []):
            name = comp["component"]
            comp_scores[name] = comp["score"]

        # Individual signals as flat dict
        signals = {}
        for sig in data.get("signals_collected", []):
            key = sig["signal_name"]
            signals[key] = {
                "raw": sig.get("raw_value"),
                "normalized": sig.get("normalized_value"),
            }

        by_id[str(cid)] = {
            "cci_composite_score": data.get("composite_score"),
            "cci_band": data.get("band"),
            "cci_run_id": data.get("claim_run_id"),
            "cci_document_quality": comp_scores.get("document_quality"),
            "cci_data_completeness": comp_scores.get("data_completeness"),
            "cci_consistency": comp_scores.get("consistency"),
            "cci_coverage_reliability": comp_scores.get("coverage_reliability"),
            "cci_decision_clarity": comp_scores.get("decision_clarity"),
            "cci_stages_available": data.get("stages_available", []),
            "cci_stages_missing": data.get("stages_missing", []),
            "cci_flags": data.get("flags", []),
            # Key individual signals
            "cci_sig_avg_field_confidence": signals.get("extraction.avg_field_confidence", {}).get("normalized"),
            "cci_sig_avg_doc_type_confidence": signals.get("extraction.avg_doc_type_confidence", {}).get("normalized"),
            "cci_sig_verified_evidence_rate": signals.get("extraction.verified_evidence_rate", {}).get("normalized"),
            "cci_sig_provenance_coverage": signals.get("reconciliation.provenance_coverage", {}).get("normalized"),
            "cci_sig_critical_facts_rate": signals.get("reconciliation.critical_facts_rate", {}).get("normalized"),
            "cci_sig_conflict_rate": signals.get("reconciliation.conflict_rate", {}).get("normalized"),
            "cci_sig_gate_status_score": signals.get("reconciliation.gate_status_score", {}).get("normalized"),
            "cci_sig_avg_match_confidence": signals.get("coverage.avg_match_confidence", {}).get("normalized"),
            "cci_sig_review_needed_rate": signals.get("coverage.review_needed_rate", {}).get("normalized"),
            "cci_sig_method_diversity": signals.get("coverage.method_diversity", {}).get("normalized"),
            "cci_sig_primary_repair_confidence": signals.get("coverage.primary_repair_confidence", {}).get("normalized"),
            "cci_sig_line_item_complexity": signals.get("coverage.line_item_complexity", {}).get("normalized"),
            "cci_sig_screening_pass_rate": signals.get("screening.pass_rate", {}).get("normalized"),
            "cci_sig_inconclusive_rate": signals.get("screening.inconclusive_rate", {}).get("normalized"),
            "cci_sig_hard_fail_clarity": signals.get("screening.hard_fail_clarity", {}).get("normalized"),
            "cci_sig_assessment_confidence": signals.get("assessment.confidence_score", {}).get("normalized"),
            "cci_sig_data_gap_penalty": signals.get("assessment.data_gap_penalty", {}).get("normalized"),
            "cci_sig_fraud_indicator_penalty": signals.get("assessment.fraud_indicator_penalty", {}).get("normalized"),
            "cci_sig_tier1_ratio": signals.get("decision.tier1_ratio", {}).get("normalized"),
            "cci_sig_assumption_reliance": signals.get("decision.assumption_reliance", {}).get("normalized"),
        }
    print(f"[confidence]    {len(by_id)} claims loaded from {len(files)} total files ({len(by_claim)} unique)")
    return by_id


# ── 5. Decision log ─────────────────────────────────────────────────────

def load_decisions_log() -> dict:
    """Load the latest assessment decision per claim from decisions.jsonl."""
    path = WS / "logs" / "decisions.jsonl"
    by_id = {}
    total = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            total += 1
            if rec.get("decision_type") != "assessment":
                continue
            cid = str(rec.get("claim_id", ""))
            if not cid:
                continue
            outcome = rec.get("outcome", {})
            payout = outcome.get("assessment_payout", {}) or {}
            checks = outcome.get("assessment_checks", []) or []

            # Count check results
            checks_pass = sum(1 for c in checks if c.get("result") == "PASS")
            checks_fail = sum(1 for c in checks if c.get("result") == "FAIL")
            checks_warn = sum(1 for c in checks if c.get("result") not in ("PASS", "FAIL"))

            by_id[cid] = {
                "log_decision": outcome.get("assessment_decision"),
                "log_confidence": outcome.get("assessment_confidence"),
                "log_final_payout": payout.get("final_payout"),
                "log_total_claimed": payout.get("total_claimed"),
                "log_covered_subtotal": payout.get("covered_subtotal"),
                "log_coverage_percent": payout.get("coverage_percent"),
                "log_deductible": payout.get("deductible"),
                "log_after_deductible": payout.get("after_deductible"),
                "log_capped_amount": payout.get("capped_amount"),
                "log_max_coverage_applied": payout.get("max_coverage_applied"),
                "log_currency": payout.get("currency"),
                "log_checks_pass": checks_pass,
                "log_checks_fail": checks_fail,
                "log_checks_warn": checks_warn,
                "log_rationale": rec.get("rationale", {}).get("summary"),
                "log_created_at": rec.get("created_at"),
                "log_model": rec.get("metadata", {}).get("model"),
            }
    print(f"[decisions_log] {len(by_id)} assessment decisions from {total} total log entries")
    return by_id


# ── Merge ────────────────────────────────────────────────────────────────

def merge_all():
    gt = load_ground_truth()
    ae = load_assessment_evals()
    cr = load_claim_eval_reports()
    cs = load_confidence_summaries()
    dl = load_decisions_log()

    # Union of all claim IDs
    all_ids = sorted(set(gt) | set(ae) | set(cr) | set(cs) | set(dl))
    print(f"\n[merge] {len(all_ids)} unique claim IDs across all sources")

    merged = []
    for cid in all_ids:
        row = {"claim_id": cid}
        # Merge each source (missing = empty dict -> no keys added)
        row.update(gt.get(cid, {}))
        row.update(ae.get(cid, {}))
        row.update(cr.get(cid, {}))
        row.update(cs.get(cid, {}))
        row.update(dl.get(cid, {}))

        # Derived fields
        # decision_correct: compare ground truth to best available predicted
        pred = row.get("eval_ai_decision") or row.get("log_decision") or row.get("report_pipeline_decision")
        gt_dec = row.get("gt_decision")
        if pred and gt_dec:
            # Normalize: APPROVED->APPROVE, DENIED->REJECT
            norm_gt = gt_dec.replace("APPROVED", "APPROVE").replace("DENIED", "REJECT")
            norm_pred = pred.replace("APPROVED", "APPROVE").replace("DENIED", "REJECT")
            row["decision_correct"] = norm_gt == norm_pred
        else:
            row["decision_correct"] = None

        # payout_error_pct
        gt_payout = row.get("gt_total_approved_amount")
        pred_payout = row.get("eval_ai_payout") or row.get("log_final_payout") or row.get("report_pipeline_payout")
        if gt_payout is not None and pred_payout is not None and gt_payout > 0:
            row["payout_error_pct"] = round((pred_payout - gt_payout) / gt_payout * 100, 4)
        elif gt_payout == 0 and pred_payout is not None:
            row["payout_error_pct"] = 0.0 if pred_payout == 0 else None
        else:
            row["payout_error_pct"] = None

        # Data source flags
        row["has_ground_truth"] = cid in gt
        row["has_assessment_eval"] = cid in ae
        row["has_claim_eval_report"] = cid in cr
        row["has_confidence_summary"] = cid in cs
        row["has_decision_log"] = cid in dl
        row["source_count"] = sum([
            cid in gt, cid in ae, cid in cr, cid in cs, cid in dl
        ])

        merged.append(row)

    return merged


# ── Summary stats ────────────────────────────────────────────────────────

def print_summary(merged):
    n = len(merged)
    print(f"\n{'='*60}")
    print(f"MERGED DATASET SUMMARY")
    print(f"{'='*60}")
    print(f"Total claims: {n}")

    # Source coverage
    for src in ["has_ground_truth", "has_assessment_eval", "has_claim_eval_report",
                 "has_confidence_summary", "has_decision_log"]:
        count = sum(1 for r in merged if r.get(src))
        print(f"  {src}: {count}/{n}")

    # Decision accuracy (where both GT and prediction exist)
    with_decision = [r for r in merged if r.get("decision_correct") is not None]
    correct = sum(1 for r in with_decision if r["decision_correct"])
    print(f"\nDecision accuracy: {correct}/{len(with_decision)} = {correct/len(with_decision)*100:.1f}%" if with_decision else "\nNo decision comparisons available")

    # Payout error stats
    payout_errors = [r["payout_error_pct"] for r in merged if r.get("payout_error_pct") is not None]
    if payout_errors:
        avg_err = sum(abs(e) for e in payout_errors) / len(payout_errors)
        max_err = max(abs(e) for e in payout_errors)
        within_1 = sum(1 for e in payout_errors if abs(e) <= 1)
        within_5 = sum(1 for e in payout_errors if abs(e) <= 5)
        print(f"\nPayout error (n={len(payout_errors)}):")
        print(f"  Mean absolute error: {avg_err:.2f}%")
        print(f"  Max absolute error:  {max_err:.2f}%")
        print(f"  Within 1%: {within_1}/{len(payout_errors)}")
        print(f"  Within 5%: {within_5}/{len(payout_errors)}")

    # CCI score distribution
    cci_scores = [r["cci_composite_score"] for r in merged if r.get("cci_composite_score") is not None]
    if cci_scores:
        avg_cci = sum(cci_scores) / len(cci_scores)
        min_cci = min(cci_scores)
        max_cci = max(cci_scores)
        print(f"\nCCI composite scores (n={len(cci_scores)}):")
        print(f"  Mean: {avg_cci:.4f}")
        print(f"  Min:  {min_cci:.4f}")
        print(f"  Max:  {max_cci:.4f}")

        # Band distribution
        bands = defaultdict(int)
        for r in merged:
            b = r.get("cci_band")
            if b:
                bands[b] += 1
        print(f"  Bands: {dict(bands)}")

    # CCI component score averages
    components = ["cci_document_quality", "cci_data_completeness", "cci_consistency",
                   "cci_coverage_reliability", "cci_decision_clarity"]
    print(f"\nCCI component averages:")
    for comp in components:
        vals = [r[comp] for r in merged if r.get(comp) is not None]
        if vals:
            print(f"  {comp.replace('cci_', '')}: {sum(vals)/len(vals):.4f} (n={len(vals)})")

    # CCI vs decision correctness
    cci_correct = [r["cci_composite_score"] for r in merged
                    if r.get("cci_composite_score") is not None and r.get("decision_correct") is True]
    cci_wrong = [r["cci_composite_score"] for r in merged
                  if r.get("cci_composite_score") is not None and r.get("decision_correct") is False]
    if cci_correct or cci_wrong:
        print(f"\nCCI vs decision correctness:")
        if cci_correct:
            print(f"  Correct decisions: mean CCI = {sum(cci_correct)/len(cci_correct):.4f} (n={len(cci_correct)})")
        if cci_wrong:
            print(f"  Wrong decisions:   mean CCI = {sum(cci_wrong)/len(cci_wrong):.4f} (n={len(cci_wrong)})")

    print(f"\n{'='*60}")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    merged = merge_all()

    # Write output
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nWrote {len(merged)} records to {OUT}")

    print_summary(merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
