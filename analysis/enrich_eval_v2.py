"""
Extract enriched metadata from eval-v2 provenance decision PDFs.

Uses pymupdf (fitz) for text extraction (better spacing than pdfplumber).

Reads each Claim_Decision_for_Claim_Number_*.pdf and extracts:
  language, date, garage_name, garage_city, parts_approved, labor_approved,
  total_material_labor_approved, vat_rate_pct, deductible, total_approved_amount,
  reimbursement_rate_pct, coverage_notes

Then updates ground_truth.json to match eval-v1 schema.
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import fitz  # pymupdf

DATA_ROOT = Path(__file__).parent.parent / "data" / "datasets" / "nsa-motor-eval-v2"
PROVENANCE_DIR = DATA_ROOT / "provenance"
GT_PATH = DATA_ROOT / "ground_truth.json"

# Narrow-no-break-space and other Unicode whitespace that appears in PDFs
WHITESPACE_CHARS = "\u202f\u00a0\u2009\u2019"


def clean_text(text: str) -> str:
    """Normalize Unicode whitespace but preserve newlines."""
    for ch in WHITESPACE_CHARS:
        text = text.replace(ch, " ")
    return text


def parse_swiss_number(s: str) -> float | None:
    """Parse Swiss-formatted number: '3 666,68' or '213,70' or '150.00'."""
    if not s:
        return None
    s = s.strip().lstrip("-")
    # Remove thousands separators (space, apostrophe, narrow no-break space)
    s = re.sub(r"[\s'\u2019\u202f\u00a0]", "", s)
    # Handle comma as decimal
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def detect_language(text: str) -> str:
    if "Schaden Nr" in text:
        return "de"
    if "Sinistre No" in text:
        return "fr"
    if "Numero di reclamo" in text or "Numerodireclamo" in text:
        return "it"
    return "unknown"


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from all pages of a PDF using pymupdf."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return clean_text(text)


def find_line_after(lines: list[str], keyword: str, offset: int = 1) -> str | None:
    """Find the line N positions after a line containing keyword."""
    for i, line in enumerate(lines):
        if keyword in line and i + offset < len(lines):
            return lines[i + offset].strip()
    return None


def extract_header(text: str) -> dict:
    """Extract garage name, city, language, date from PDF header."""
    lines = text.split("\n")
    result = {}

    # Skip NSA/ERV footer lines that appear at top of pymupdf output
    # Find first non-NSA line (handles both DE and FR footers)
    content_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if any(kw in stripped for kw in [
            "NSA Services", "Tel (", "Tél (", "Internet:", "ERV,",
        ]):
            continue
        content_start = i
        break

    # Garage name: first meaningful line after header
    result["garage_name"] = lines[content_start].strip() if content_start < len(lines) else None

    # City: look for CH-XXXX or IT-XXXXX pattern in garage address lines only
    # (skip first line which is the garage name)
    for line in lines[content_start + 1:content_start + 5]:
        # Skip if this is the claim number line
        if any(kw in line for kw in ["Schaden Nr", "Sinistre No", "Numero di reclamo"]):
            break
        m = re.search(r"CH-\d{4}\s+(.+)", line)
        if m:
            result["garage_city"] = m.group(1).strip()
            break
        m = re.search(r"IT-\d{5}\s+(.+)", line)
        if m:
            result["garage_city"] = m.group(1).strip()
            break
        # Luxembourg: L-XXXX
        m = re.search(r"L-\d{4}\s+(.+)", line)
        if m:
            result["garage_city"] = m.group(1).strip()
            break

    # Language
    result["language"] = detect_language(text)

    # Date: line after "Datum :", "Date :", or "Dattero:"
    for label in ["Datum :", "Datum:", "Date :", "Date:", "Dattero:", "Dattero :"]:
        date_val = find_line_after(lines, label)
        if date_val and re.match(r"\d{1,2}[./]\d{2}[./]\d{4}", date_val):
            result["date"] = date_val
            break

    return result


def extract_amounts_line_by_line(lines: list[str], lang: str) -> dict:
    """Extract financial data from the line-by-line table format (pymupdf output).

    pymupdf puts each table cell on its own line:
        Total pièces + main d'oeuvre
        4 397,48          (estimate)
        2 638,49          (approved)
        TVA (8.10%)
        213,70
        ...
    """
    result = {}

    # --- Total material + labor ---
    total_labels_fr = ["Total pièces + main d'oeuvre", "Total pi\u00e8ces + main d'oeuvre",
                       "Total pièces + main d'œuvre"]
    total_labels_de = ["Total Material + Arbeit"]
    total_labels = total_labels_fr + total_labels_de

    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(label.lower() in stripped.lower() for label in total_labels):
            # Next two lines should be estimate and approved
            if i + 2 < len(lines):
                est = parse_swiss_number(lines[i + 1])
                appr = parse_swiss_number(lines[i + 2])
                if est is not None:
                    result["total_material_labor_estimate"] = est
                if appr is not None:
                    result["total_material_labor_approved"] = appr
            break

    # --- Labor ---
    # Case-insensitive matching for FR labels (PDF may have "MAIN D'OEUVRE" or "main d'oeuvre")
    labor_labels_fr = ["main d'oeuvre", "main d'œuvre", "travail"]
    labor_labels_de = ["Arbeit"]

    for i, line in enumerate(lines):
        stripped = line.strip()
        stripped_lower = stripped.lower()
        # Skip if this is the "Total" line
        if any(t.lower() in stripped_lower for t in total_labels):
            continue
        # Check FR labels (case-insensitive)
        matched_fr = any(
            stripped_lower == label or stripped_lower.startswith(label)
            for label in labor_labels_fr
        )
        # Check DE labels (exact match only — "Arbeit" but not "Querlenker Arbeit")
        matched_de = stripped in labor_labels_de
        if matched_fr or matched_de:
            # Next two lines: estimate and approved
            if i + 2 < len(lines):
                est = parse_swiss_number(lines[i + 1])
                appr = parse_swiss_number(lines[i + 2])
                if appr is not None:
                    result["labor_approved"] = appr
                    result["labor_estimate"] = est
            break

    # Compute parts_approved = total - labor
    if result.get("total_material_labor_approved") is not None and result.get("labor_approved") is not None:
        result["parts_approved"] = round(
            result["total_material_labor_approved"] - result["labor_approved"], 2
        )

    # --- VAT ---
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"(?:TVA|MwSt)\s*\((\d+[.,]\d+)\s*%?\)", stripped)
        if m:
            result["vat_rate_pct"] = parse_swiss_number(m.group(1))
            # VAT amount is the next line
            if i + 1 < len(lines):
                vat_amt = parse_swiss_number(lines[i + 1])
                if vat_amt is not None:
                    result["vat_amount"] = vat_amt
            break

    # --- Deductible ---
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("Franchise", "Selbstbehalt"):
            if i + 1 < len(lines):
                val = lines[i + 1].strip().lstrip("-")
                result["deductible"] = parse_swiss_number(val)
            break

    # --- TOTAL ---
    # Find the last "TOTAL" line (to avoid matching sub-totals)
    total_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "TOTAL":
            total_idx = i
    if total_idx is not None and total_idx + 1 < len(lines):
        result["total_approved_amount"] = parse_swiss_number(lines[total_idx + 1])

    # --- Reimbursement rate ---
    full_text = "\n".join(lines)
    # FR: "à partir de 80 000 Km, 60 %"
    m = re.search(r"[àa]\s*partir\s*de\s*([\d\s.]+)\s*Km[,.]?\s*(\d+)\s*%", full_text)
    if m:
        result["reimbursement_rate_pct"] = int(m.group(2))
    else:
        # DE: "ab 80.000 Km zu 60 %"  or "ab 80 000 Km zu 60%"
        m = re.search(r"ab\s*([\d\s.]+)\s*Km\s*zu\s*(\d+)\s*%", full_text)
        if m:
            result["reimbursement_rate_pct"] = int(m.group(2))

    # --- Coverage notes ---
    # Only search text AFTER the TOTAL line to avoid capturing table content
    total_line_idx = None
    for i, line in enumerate(lines):
        if line.strip() == "TOTAL":
            total_line_idx = i
    post_table_text = "\n".join(lines[total_line_idx + 2:]) if total_line_idx is not None else full_text

    # Also check the intro text (between greeting and table header) for coverage info
    table_header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("Rubrique", "Material + Arbeit"):
            table_header_idx = i
            break
    intro_text = "\n".join(lines[:table_header_idx]) if table_header_idx is not None else ""
    search_text = intro_text + "\n" + post_table_text

    # Use \.(?!\d) to avoid matching periods inside numbers like "160.000"
    coverage_patterns = [
        # FR
        r"(La police couvre les pi[èe]ces.+?\.(?!\d))",
        r"(Les positions? barr[ée]es? ne sont pas couvert.+?\.(?!\d))",
        r"(Les postes? supprim[ée]s? ne sont pas couverts?.+?\.(?!\d))",
        r"(Le liquide n.est pas couvert.+?\.(?!\d))",
        r"(Depuis l.introduction de la loi.+?remboursable\.)",
        # DE
        r"(Die gestrichenen Positionen.+?\.(?!\d))",
        r"(Gew[äa]hrleistungspflichtige Materialkosten.+?\.(?!\d))",
        r"(Die Kostengutsprache erfolgt.+?\.(?!\d))",
        r"(Die Diagnose ist nicht.+?\.(?!\d))",
    ]
    notes = []
    for pat in coverage_patterns:
        for found in re.finditer(pat, search_text, re.DOTALL):
            note = found.group(1).strip().replace("\n", " ")
            notes.append(note)
    if notes:
        result["coverage_notes"] = " ".join(notes)

    return result


def extract_claim_metadata(pdf_path: str) -> dict:
    """Extract all metadata from a single decision PDF."""
    text = extract_text_from_pdf(pdf_path)
    lines = text.split("\n")

    # Header info
    result = extract_header(text)

    # Check if approved or denied
    is_denied = any(
        kw in text
        for kw in [
            "Nicht gewährter",
            "Nicht gew\u00e4hrter",  # encoded ä
            "Sinistre refusé",
            "Sinistre refus\u00e9",
            "Richiesta respinta",
        ]
    )

    if not is_denied:
        amounts = extract_amounts_line_by_line(lines, result.get("language", ""))
        result.update(amounts)

    return result


def main():
    # Restore ground truth from git first (undo previous run)
    # Actually, re-read the file as-is — the previous run already wrote to it
    # We need the original. Let's restore it from git.
    import subprocess
    subprocess.run(
        ["git", "checkout", "HEAD", "--", str(GT_PATH)],
        cwd=str(DATA_ROOT.parent.parent.parent),
        capture_output=True,
    )

    with open(GT_PATH, "r", encoding="utf-8") as f:
        gt = json.load(f)

    # Build claim_id → provenance PDF mapping
    pdf_map = {}
    for fname in os.listdir(PROVENANCE_DIR):
        if not fname.endswith(".pdf"):
            continue
        m = re.search(r"Claim_Decision_for_Claim_Number_(\d+)", fname)
        if m:
            pdf_map[m.group(1)] = PROVENANCE_DIR / fname

    print(f"Found {len(pdf_map)} provenance PDFs")
    print(f"Ground truth has {len(gt['claims'])} claims\n")

    # Process each claim
    for claim in gt["claims"]:
        cid = str(claim["claim_id"])
        pdf_path = pdf_map.get(cid)
        if not pdf_path:
            print(f"  WARNING: No provenance PDF for claim {cid}")
            continue

        try:
            meta = extract_claim_metadata(str(pdf_path))
        except Exception as e:
            print(f"  ERROR extracting {cid}: {e}")
            import traceback; traceback.print_exc()
            continue

        # Merge extracted metadata
        claim["language"] = meta.get("language")
        claim["date"] = meta.get("date")
        claim["garage_name"] = meta.get("garage_name")
        claim["garage_city"] = meta.get("garage_city")

        if claim["decision"] == "APPROVED":
            for field in [
                "parts_approved", "labor_approved", "total_material_labor_approved",
                "vat_rate_pct", "reimbursement_rate_pct", "coverage_notes",
            ]:
                val = meta.get(field)
                if val is not None:
                    claim[field] = val

            # Cross-check amounts against existing ground truth
            if meta.get("total_approved_amount") is not None:
                existing = claim.get("approved_amount")
                extracted = meta["total_approved_amount"]
                if existing is not None and abs(existing - extracted) > 0.50:
                    print(
                        f"  WARNING {cid}: approved_amount mismatch — "
                        f"existing={existing}, extracted={extracted}"
                    )
                claim["total_approved_amount"] = extracted

            if meta.get("deductible") is not None:
                existing_ded = claim.get("deductible")
                extracted_ded = meta["deductible"]
                if existing_ded is not None and abs(existing_ded - extracted_ded) > 0.50:
                    print(
                        f"  WARNING {cid}: deductible mismatch — "
                        f"existing={existing_ded}, extracted={extracted_ded}"
                    )
                claim["deductible"] = extracted_ded

        # Print summary
        lang = meta.get("language", "??")
        date = meta.get("date", "??")
        garage = (meta.get("garage_name") or "??")[:45]
        city = meta.get("garage_city", "??")
        rate = meta.get("reimbursement_rate_pct", "")
        rate_str = f" rate={rate}%" if rate else ""
        total = meta.get("total_approved_amount", "")
        total_str = f" CHF {total:,.2f}" if isinstance(total, float) else ""
        print(f"  {cid} | {lang} | {date:>10} | {garage:<45} | {city or '??'}{rate_str}{total_str}")

    # --- Rename fields to match eval-v1 schema ---
    for claim in gt["claims"]:
        if "approved_amount" in claim:
            if "total_approved_amount" in claim:
                del claim["approved_amount"]
            else:
                claim["total_approved_amount"] = claim.pop("approved_amount")

    # Add currency field where missing (all claims are CHF)
    for claim in gt["claims"]:
        if "currency" not in claim:
            claim["currency"] = "CHF"

    # --- Reorder fields to match eval-v1 ---
    field_order = [
        "claim_id", "decision", "language", "date", "guarantee_number",
        "vehicle", "garage_name", "garage_city",
        "parts_approved", "labor_approved", "total_material_labor_approved",
        "vat_rate_pct", "deductible", "total_approved_amount",
        "total_amount",
        "currency", "reimbursement_rate_pct", "coverage_notes",
        "denial_reason",
    ]

    reordered_claims = []
    for claim in gt["claims"]:
        ordered = {}
        for key in field_order:
            if key in claim:
                ordered[key] = claim[key]
        for key in claim:
            if key not in ordered:
                ordered[key] = claim[key]
        reordered_claims.append(ordered)

    gt["claims"] = reordered_claims

    # --- Update metadata ---
    gt["metadata"]["ground_truth_schema"] = "v2"
    gt["metadata"]["enriched_from"] = "provenance decision PDFs"
    gt["metadata"]["enriched_date"] = "2026-02-03"

    langs = [c.get("language") for c in gt["claims"] if c.get("language")]
    lang_counts = Counter(langs)
    print(f"\nLanguage distribution: {dict(lang_counts)}")

    # --- Write ---
    with open(GT_PATH, "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2, ensure_ascii=False)

    print(f"\nWrote enriched ground truth to {GT_PATH}")

    # --- Verification summary ---
    print("\n=== Verification ===")
    approved = [c for c in gt["claims"] if c["decision"] == "APPROVED"]
    denied = [c for c in gt["claims"] if c["decision"] == "DENIED"]
    print(f"Approved: {len(approved)}, Denied: {len(denied)}")

    missing_fields = {"garage_name": 0, "garage_city": 0, "date": 0, "language": 0}
    for c in gt["claims"]:
        for f in missing_fields:
            if not c.get(f):
                missing_fields[f] += 1
    print(f"Missing fields: {missing_fields}")

    approved_missing = {"parts_approved": 0, "labor_approved": 0, "total_material_labor_approved": 0,
                        "reimbursement_rate_pct": 0, "coverage_notes": 0, "total_approved_amount": 0}
    for c in approved:
        for f in approved_missing:
            if not c.get(f):
                approved_missing[f] += 1
    print(f"Approved claims missing: {approved_missing}")


if __name__ == "__main__":
    main()
