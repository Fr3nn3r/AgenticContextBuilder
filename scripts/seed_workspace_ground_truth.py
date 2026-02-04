"""
One-time script: seed the NSA workspace with ground truth data from the
nsa-motor-seed-v1 dataset (4 claims: 65128, 65157, 65196, 65258).

Actions:
  1. Transform seed ground_truth.json (v1 schema) → workspace v2 schema
  2. Merge into workspaces/nsa/config/ground_truth.json (skip duplicates)
  3. Copy + rename provenance PDFs into workspace claim directories
"""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "data" / "datasets" / "nsa-motor-seed-v1"
WORKSPACE_DIR = ROOT / "workspaces" / "nsa"
SEED_GT = SEED_DIR / "ground_truth.json"
WS_GT = WORKSPACE_DIR / "config" / "ground_truth.json"

# Map seed claim_id → provenance PDF filename (note: 65196 has a trailing " 1")
PDF_MAP = {
    "65128": "Claim_Decision_for_Claim_Number_65128.pdf",
    "65157": "Claim_Decision_for_Claim_Number_65157.pdf",
    "65196": "Claim_Decision_for_Claim_Number_65196 1.pdf",
    "65258": "Claim_Decision_for_Claim_Number_65258.pdf",
}


def transform_v1_to_v2(claim: dict) -> dict:
    """Convert a seed v1 ground truth entry to the workspace v2 flat schema."""
    line_items = claim.get("line_items", [])

    # Compute parts_approved / labor_approved from line_items
    has_combined = any(li.get("type") == "material_and_labor" for li in line_items)
    if has_combined:
        # Cannot split combined items — leave as null
        parts_approved = None
        labor_approved = None
    else:
        mat_sum = sum(li["approved_chf"] for li in line_items if li.get("type") == "material")
        lab_sum = sum(li["approved_chf"] for li in line_items if li.get("type") == "labor")
        parts_approved = mat_sum if mat_sum else None
        labor_approved = lab_sum if lab_sum else None

    garage = claim.get("garage", {})

    v2 = {
        "claim_id": claim["claim_id"],
        "decision": claim["decision"],
        "language": claim.get("language"),
        "date": claim.get("date"),
        "guarantee_number": claim.get("guarantee_number"),
        "vehicle": claim.get("vehicle"),
        "garage_name": garage.get("name"),
        "garage_city": garage.get("city"),
        "parts_approved": parts_approved,
        "labor_approved": labor_approved,
        "total_material_labor_approved": claim.get("total_material_labor_approved"),
        "vat_rate_pct": claim.get("vat_rate_pct"),
        "deductible": claim.get("deductible"),
        "total_approved_amount": claim.get("total_approved_amount"),
        "currency": claim.get("currency"),
        "reimbursement_rate_pct": claim.get("reimbursement_rate_pct"),
        "coverage_notes": claim.get("coverage_notes"),
        "denial_reason": claim.get("denial_reason"),
    }

    # Strip keys with None values that aren't standard in v2 denied claims
    # but keep explicit nulls for core fields
    return {k: v for k, v in v2.items() if v is not None or k in (
        "denial_reason", "coverage_notes", "total_approved_amount",
        "deductible", "parts_approved", "labor_approved",
    )}


def main():
    # --- Load source data ---
    seed_data = json.loads(SEED_GT.read_text(encoding="utf-8"))
    ws_data = json.loads(WS_GT.read_text(encoding="utf-8"))

    existing_ids = {c["claim_id"] for c in ws_data["claims"]}
    added = []
    skipped = []

    for claim in seed_data["claims"]:
        cid = claim["claim_id"]
        if cid in existing_ids:
            skipped.append(cid)
            continue
        ws_data["claims"].append(transform_v1_to_v2(claim))
        added.append(cid)

    # --- Update metadata ---
    approved = sum(1 for c in ws_data["claims"] if c["decision"] == "APPROVED")
    denied = sum(1 for c in ws_data["claims"] if c["decision"] == "DENIED")
    ws_data["metadata"]["total_claims"] = len(ws_data["claims"])
    ws_data["metadata"]["approved_count"] = approved
    ws_data["metadata"]["denied_count"] = denied

    # --- Write updated ground truth ---
    WS_GT.write_text(json.dumps(ws_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # --- Copy + rename provenance PDFs ---
    copied_pdfs = []
    for cid, pdf_name in PDF_MAP.items():
        src = SEED_DIR / "provenance" / pdf_name
        dest_dir = WORKSPACE_DIR / "claims" / cid / "ground_truth"
        dest = dest_dir / "Claim_Decision.pdf"
        if dest.exists():
            print(f"  PDF already exists: {dest.relative_to(ROOT)}")
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied_pdfs.append(cid)

    # --- Summary ---
    print(f"\n=== Seed Workspace Ground Truth ===")
    print(f"Claims added to ground_truth.json: {len(added)} {added}")
    if skipped:
        print(f"Claims skipped (already present):  {len(skipped)} {skipped}")
    print(f"PDFs copied: {len(copied_pdfs)} {copied_pdfs}")
    print(f"Total claims in workspace GT:      {ws_data['metadata']['total_claims']}")
    print(f"  Approved: {approved}  Denied: {denied}")


if __name__ == "__main__":
    main()
