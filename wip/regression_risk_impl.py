#!/usr/bin/env python3
import glob, json, os, re
from collections import defaultdict

BASE = "C:/Users/fbrun/Documents/GitHub/AgenticContextBuilder"
CLAIMS = BASE + "/workspaces/nsa/claims"
GT = BASE + "/data/datasets/nsa-motor-eval-v1/ground_truth.json"
RUN1 = "clm_20260201_194254_72d3fb"
RUN0 = "clm_20260201_141514_37c2af"
SQ = chr(39)

def cid_from_path(fp):
    n = fp.replace(os.sep, "/")
    parts = n.split("/")
    for i, x in enumerate(parts):
        if x == "claims" and i+1 < len(parts): return parts[i+1]
    return "unknown"

def parse_reason(r):
    pat1 = "in category " + SQ + "([^" + SQ + "]+)" + SQ
    m1 = re.search(pat1, r)
    oc = m1.group(1) if m1 else "unknown"
    pat2 = "found in policy list as " + SQ + "([^" + SQ + "]+)" + SQ
    m2 = re.search(pat2, r)
    pl = m2.group(1) if m2 else "unknown"
    return oc, pl

def prev_item(cid, desc, ic):
    pp = CLAIMS + "/" + cid + "/claim_runs/" + RUN0 + "/coverage_analysis.json"
    if not os.path.exists(pp): return {}
    with open(pp) as f: d = json.load(f)
    for it in d.get("line_items", []):
        if it.get("description") == desc: return it
        if ic and it.get("item_code") == ic: return it
    return {}

def main():
    with open(GT) as f: gd = json.load(f)
    gt = {c["claim_id"]: c for c in gd["claims"]}
    lf = sorted(glob.glob(CLAIMS + "/*/claim_runs/" + RUN1 + "/coverage_analysis.json"))
    pf = sorted(glob.glob(CLAIMS + "/*/claim_runs/" + RUN0 + "/coverage_analysis.json"))
    ms = []; cc = set(); ti = 0; tc = 0
    for fp in lf:
        with open(fp) as f: d = json.load(f)
        cid = d.get("claim_id", cid_from_path(fp))
        for it in d.get("line_items", []):
            ti += 1
            if it.get("coverage_status") == "covered": tc += 1
            r = it.get("match_reasoning") or ""
            if "cross-category" not in r.lower(): continue
            oc, pl = parse_reason(r)
            m = dict(cid=cid, desc=it.get("description",""), ic=it.get("item_code"),
                price=it.get("total_price",0) or 0, cs=it.get("coverage_status",""),
                ccat=it.get("coverage_category",""), comp=it.get("matched_component",""),
                meth=it.get("match_method",""), conf=it.get("match_confidence",0),
                reason=r, ocat=oc, pmatch=pl)
            if cid in gt:
                g = gt[cid]
                m["gd"] = g.get("decision")
                m["gdr"] = g.get("denial_reason")
                m["gn"] = g.get("coverage_notes")
                m["ga"] = g.get("total_approved_amount")
            pi = prev_item(cid, m["desc"], m["ic"])
            m["ps"] = pi.get("coverage_status") if pi else None
            m["pc"] = pi.get("coverage_category") if pi else None
            m["pco"] = pi.get("matched_component") if pi else None
            gde = m.get("gd")
            if not gde:
                m["ok"] = None; m["w"] = "No GT"
            elif m["cs"] != "covered":
                m["ok"] = None; m["w"] = "Not covered"
            elif gde == "DENIED":
                m["ok"] = False
                m["w"] = "DENIED: " + (m.get("gdr") or "")[:120]
            elif gde == "APPROVED":
                m["ok"] = True
                m["w"] = "APPROVED. Prev=" + str(m["ps"])
            else:
                m["ok"] = None; m["w"] = "Unexpected"
            ms.append(m); cc.add(cid)
    tp = [m for m in ms if m["ok"] is True]
    fpos = [m for m in ms if m["ok"] is False]
    unk = [m for m in ms if m["ok"] is None]
    S = "=" * 90; D = "-" * 90; P = print
    P(S); P("REGRESSION RISK ANALYSIS: Cross-Category Matching")
    P("Latest run:   " + RUN1); P("Previous run: " + RUN0); P(S); P("")
    P("Ground truth: %d claims" % len(gt))
    P("Latest run files: %d" % len(lf)); P("Previous run files: %d" % len(pf))
    P(""); P(D); P("DETAILED CROSS-CATEGORY MATCHES"); P(D)
    for i, m in enumerate(ms, 1):
        lbl = {True:"CORRECT", False:"INCORRECT", None:"UNKNOWN"}[m["ok"]]
        P(""); P("[%d] Claim %s -- %s" % (i, m["cid"], lbl))
        P("    Item:           %s (code: %s)" % (m["desc"], m["ic"]))
        P("    Price:          %.2f" % m["price"])
        P("    Status:         %s" % m["cs"])
        P("    Category flow:  %s --> %s" % (m["ocat"], m["ccat"]))
        P("    Component:      %s" % m["comp"])
        P("    Policy match:   " + repr(m["pmatch"]))
        P("    Confidence:     %s" % m["conf"])
        P("    GT Decision:    %s" % m.get("gd", "N/A"))
        if m.get("gdr"): P("    GT Denial:      %s" % m["gdr"][:120])
        if m.get("gn"): P("    GT Notes:       %s" % m["gn"][:120])
        P("    Prev run:       status=%s, cat=%s, comp=%s" % (m["ps"], m["pc"], m["pco"]))
        P("    Assessment:     %s" % m["w"])
    P(""); P(S); P("SUMMARY"); P(S)
    P("Total claims in run:           %d" % len(lf))
    P("Total line items in run:       %d" % ti)
    P("Total covered items:           %d" % tc)
    P("Claims with cross-cat match:   %d / %d" % (len(cc), len(lf)))
    P("Cross-category match items:    %d" % len(ms)); P("")
    P("TRUE POSITIVES  (correct):     %d" % len(tp))
    for m in tp: P("    %s: %s (%s -> %s)" % (m["cid"], m["desc"], m["ocat"], m["ccat"]))
    P("FALSE POSITIVES (incorrect):   %d" % len(fpos))
    for m in fpos:
        P("    %s: %s (%s -> %s)" % (m["cid"], m["desc"], m["ocat"], m["ccat"]))
        P("        Matched " + repr(m["comp"]) + " as " + repr(m["pmatch"]) + " -- WRONG")
    P("UNKNOWN / NEEDS REVIEW:        %d" % len(unk))
    for m in unk: P("    %s: %s (%s -> %s)" % (m["cid"], m["desc"], m["ocat"], m["ccat"]))
    P(""); P(D); P("FINANCIAL IMPACT"); P(D)
    tv = sum(m["price"] for m in ms)
    tpv = sum(m["price"] for m in tp)
    fpv = sum(m["price"] for m in fpos)
    P("Total cross-category match value:  %10.2f CHF" % tv)
    P("True positive value:               %10.2f CHF" % tpv)
    P("False positive value:              %10.2f CHF" % fpv)
    P(""); P(S)
    P("RISK ASSESSMENT: What if we disable/fix cross-category matching?"); P(S); P("")
    P("SCENARIO A: Completely disable cross-category matching")
    P("-------------------------------------------------------")
    P("- %d line items would revert to previous run status" % len(ms))
    P("- RISK: %d currently-correct matches would BREAK" % len(tp))
    P("  In APPROVED claims where cross-category correctly expanded coverage:")
    for m in tp:
        P("    * Claim %s: " % m["cid"] + repr(m["desc"]) + " was " + repr(m.get("ps","N/A")) + ", now covered via %s->%s" % (m["ocat"], m["ccat"]))
    P("")
    P("- BENEFIT: %d incorrect matches would be FIXED" % len(fpos))
    P("  In DENIED claims where cross-category incorrectly marked as covered:")
    for m in fpos:
        P("    * Claim %s: " % m["cid"] + repr(m["desc"]) + " matched " + repr(m["comp"]) + " as " + repr(m["pmatch"]))
    P("")
    P("SCENARIO B: Fix the matching logic (recommended)")
    P("-------------------------------------------------")
    P("False positive patterns:")
    fpp = defaultdict(list)
    for m in fpos: fpp[m["comp"] + " -> " + m["pmatch"]].append(m)
    for pat, items in fpp.items():
        P("  Pattern: " + pat)
        for m in items: P("    Claim %s: " % m["cid"] + repr(m["desc"]) + " (%s -> %s)" % (m["ocat"], m["ccat"]))
    P("")
    P("True positive patterns (preserve these):")
    tpp = defaultdict(list)
    for m in tp: tpp[m["comp"] + " -> " + m["pmatch"]].append(m)
    for pat, items in tpp.items():
        P("  Pattern: " + pat)
        for m in items: P("    Claim %s: " % m["cid"] + repr(m["desc"]) + " (%s -> %s)" % (m["ocat"], m["ccat"]))
    P(""); P(S); P("ROOT CAUSE ANALYSIS"); P(S); P("")
    P("The cross-category matching bug occurs when:")
    P("1. Component identified in correct category (e.g., egr_valve in engine)")
    P("2. Component NOT found in that category policy coverage list")
    P("3. System searches ALL other categories for a fuzzy match")
    P("4. Finds false match in unrelated category")
    P("")
    P("FALSE POSITIVE PATTERN (EGR bug):")
    P("- egr_valve (engine) matched to bremskraftbegrenzer (brakes)")
    P("  STRING SIMILARITY: egr appears in bremskraftbe[gr]enzer")
    P("  Bremskraftbegrenzer = brake force limiter - unrelated to EGR!")
    P("")
    P("TRUE POSITIVE PATTERNS:")
    for m in tp:
        P("  " + repr(m["comp"]) + " (" + m["ocat"] + ") -> " + repr(m["pmatch"]) + " (" + m["ccat"] + ")")
        c = m["comp"].lower(); pl = m["pmatch"].lower()
        if "turbo" in c and "turbo" in pl: P("    SEMANTIC: turbocharger - VALID")
        elif "steuer" in c or "control" in c: P("    SEMANTIC: Control unit - check validity")
        elif "hub" in c or "nabe" in c or "rad" in c: P("    SEMANTIC: Wheel hub/suspension - VALID")
        else: P("    SEMANTIC: Needs manual review")
    risk = "HIGH" if len(tp) > len(fpos) else ("MEDIUM" if tp else "LOW")
    P(""); P("RECOMMENDED FIX:")
    P("1. Add SEMANTIC SIMILARITY threshold (not just string matching)")
    P("2. EGR->Bremskraftbegrenzer fails semantic check (zero overlap)")
    P("3. turbo->turbo and wheel_hub->suspension PASS (category overlap)")
    P("4. Require >50pct component-name overlap (not just substring)")
    P(""); P("REGRESSION RISK SCORE: " + risk)
    P("- Disabling entirely: %d correct decisions would regress" % len(tp))
    P("- Fixing matching logic: 0 correct decisions should regress")
    P("- Net improvement from fix: %d false positives eliminated" % len(fpos))
    P(""); P(S); P("CLAIM-LEVEL IMPACT SUMMARY"); P(S)
    for cid in sorted(cc):
        cms = [m for m in ms if m["cid"] == cid]
        gi = gt.get(cid, {}); gde = gi.get("decision", "N/A")
        ntpc = sum(1 for m in cms if m["ok"] is True)
        nfpc = sum(1 for m in cms if m["ok"] is False)
        nuc = sum(1 for m in cms if m["ok"] is None)
        if nfpc > 0 and ntpc == 0: imp = "FIX NEEDED (only false positives)"
        elif nfpc > 0 and ntpc > 0: imp = "CAREFUL FIX (mixed)"
        elif ntpc > 0: imp = "PRESERVE (only true positives)"
        else: imp = "NO CHANGE NEEDED"
        P(""); P("  Claim %s (%s): %s" % (cid, gde, imp))
        P("    TP: %d, FP: %d, Unknown: %d" % (ntpc, nfpc, nuc))
        for m in cms:
            s = {True:"TP", False:"FP", None:"??"}[m["ok"]]
            P("    [%s] %s: %s->%s (prev: %s)" % (s, m["desc"], m["ocat"], m["ccat"], m.get("ps")))

if __name__ == "__main__": main()
