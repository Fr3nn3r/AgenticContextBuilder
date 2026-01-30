# Implementation: Extraction Improvements for Coverage Accuracy

**Date**: 2026-01-30
**Goal**: Fix 4 extraction/aggregation gaps that cause `refer_should_approve` errors
**Claims affected**: 64358, 64535, 64959, 65150

## Overview

Investigation of 5 `refer_should_approve:no_fails` claims revealed that 4 are caused by extraction or aggregation gaps. The coverage analyzer receives incomplete data, cannot confidently match parts to the covered components list, and falls back to INCONCLUSIVE, which triggers REFER_TO_HUMAN.

| # | Change | Root Cause | Fixes Claim | Files to Modify |
|---|--------|------------|-------------|-----------------|
| 1 | Pass `repair_description` through aggregation | Field stripped by schema | All 5 claims | `schemas/claim_facts.py`, `api/services/aggregation.py` |
| 2 | Exclude footer summary rows from extraction | Summary rows extracted as line items | 64959 | `src/context_builder/prompts/nsa_cost_estimate_page.md` |
| 3 | Carry forward `repair_description` across pages | Cross-page context lost in merge | 64535 | `workspaces/nsa/config/extractors/nsa_cost_estimate.py` |
| 4 | Strip GRU/Grundteil prefix from item_code | Prefix pollutes part number matching | 65150 | `src/context_builder/prompts/nsa_cost_estimate_page.md` |

---

## Change 1: Pass `repair_description` Through Aggregation

### Problem

The extraction prompt already captures `repair_description` (the section header above a line item, e.g., "NIVEAUREGELUNG DEFEKT" or "Roulement de roue AR G"). This field provides critical context for the coverage analyzer to match generic parts like "VENTIL" or "Roulement" to specific covered components.

However, the `AggregatedLineItem` schema in `schemas/claim_facts.py` does not include this field, so it gets silently dropped during fact aggregation. The coverage analyzer never sees it.

### Files to Modify

#### File 1: `src/context_builder/schemas/claim_facts.py` (line ~195)

Add `repair_description` field to `AggregatedLineItem`:

```python
class AggregatedLineItem(BaseModel):
    # ... existing fields ...
    item_code: Optional[str] = Field(None, description="Part/labor code")
    description: str = Field(..., description="Item description")
    quantity: Optional[float] = Field(None, description="Quantity")
    unit: Optional[str] = Field(None, description="Unit of measure")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    total_price: Optional[float] = Field(None, description="Total price for this item")
    item_type: Optional[str] = Field(None, description="Item type (labor, parts, fee)")
    page_number: Optional[int] = Field(None, description="Page number where item was found")
    repair_description: Optional[str] = Field(None, description="Section header / repair context for this item")  # <-- ADD THIS
    source: LineItemProvenance = Field(..., description="Provenance of this line item")
```

Add the field **before** `source` to keep the provenance field last.

#### File 2: `src/context_builder/api/services/aggregation.py` (line ~548)

Pass the field through in the `collect_structured_data` method where `AggregatedLineItem` is constructed:

```python
for item in line_items:
    all_line_items.append(
        AggregatedLineItem(
            item_code=item.get("item_code"),
            description=item.get("description", ""),
            quantity=safe_float(item.get("quantity"), default=None),
            unit=item.get("unit"),
            unit_price=safe_float(item.get("unit_price"), default=None),
            total_price=safe_float(item.get("total_price"), default=None),
            item_type=item.get("item_type"),
            page_number=item.get("page_number"),
            repair_description=item.get("repair_description"),  # <-- ADD THIS
            source=provenance,
        )
    )
```

### How to Verify

After making the change, re-run extraction + aggregation for any claim and check `claim_facts.json`:
```bash
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2/65150 --stages ingest,classify,extract
```

In the resulting `claim_facts.json`, line items should now include:
```json
{
  "description": "VENTIL",
  "repair_description": "NIVEAUREGELUNG DEFEKT",
  ...
}
```

### Impact on Downstream

The coverage analyzer already accepts `repair_description` via the `repair_context_description` template variable in `nsa_coverage.md` (line 176-178). The field flows from `claim_facts.json` -> coverage analysis -> LLM prompt. No changes needed downstream.

---

## Change 2: Exclude Footer Summary Rows from Extraction

### Problem

Claim 64959 (Emil Frey, Ford Mustang GT) has a cost estimate where the last page includes summary footer rows like:

```
Travail      2'880.00
Pièces       1'455.75
Divers         181.00
```

These are **category totals**, not individual line items. The LLM extracts them as line items with `item_type: "parts"` or `"labor"`, which inflates the line item count and confuses coverage analysis.

### File to Modify

**`src/context_builder/prompts/nsa_cost_estimate_page.md`** — Add a new note after existing note 5 (zero-price items):

Add this as note 6 (renumber subsequent notes if any are added later):

```markdown
6. **Footer summary rows (DO NOT extract)**: Cost estimates often end with a summary block listing category totals. These are NOT line items. Do NOT extract rows that are merely category subtotals, such as:
   - "Travail" / "Arbeitsleistungen" followed by a total (this is labor subtotal)
   - "Pièces" / "Teilepositionen" followed by a total (this is parts subtotal)
   - "Divers" / "Diverses" followed by a total (this is fees subtotal)
   - "Sous-total" / "Zwischensumme" (subtotal)
   - "TVA" / "MwSt" (VAT line)
   - "Total" / "Gesamtbetrag" (grand total)
   These belong in the `summary` section (labor_total, parts_total, etc.), not in `line_items`.
```

### Where to Insert

After the existing note 5 on line 76:
```
5. **Zero-price items**: Include items with 0.00 price (e.g., "für Sie kostenlos").
```

Add the new note 6 right after it (before the `## Output Format` section).

### How to Verify

Re-extract claim 64959:
```bash
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2/64959 --stages ingest,classify,extract
```

Check that the resulting extraction does NOT contain line items for "Travail", "Pièces", or "Divers" as standalone entries. These values should only appear in the `summary` block.

---

## Change 3: Carry Forward `repair_description` Across Pages

### Problem

Claim 64535 (Emil Frey Crissier, Land Rover) has a cost estimate where:
- **Page 1**: Contains the repair description section header (e.g., "Roulement de roue AR G")
- **Page 2**: Contains the parts for that repair, but the LLM on page 2 has no context about the section header from page 1

The `_merge_page_results()` method in the extractor merges all line items but does NOT carry forward the last `repair_description` from page N to items on page N+1 that have no `repair_description`.

### File to Modify

**`workspaces/nsa/config/extractors/nsa_cost_estimate.py`** — method `_merge_page_results()` (lines 365-422)

### Current Code (lines 385-391)

```python
# Combine all line items with page numbers
all_items = []
for page_result in page_results:
    page_num = page_result.get("page_number", 0)
    for item in page_result.get("line_items", []):
        item["page_number"] = page_num
        all_items.append(item)
```

### New Code

```python
# Combine all line items with page numbers, carrying forward repair_description
all_items = []
last_repair_description = None
for page_result in page_results:
    page_num = page_result.get("page_number", 0)
    for item in page_result.get("line_items", []):
        item["page_number"] = page_num
        # Track the latest non-null repair_description
        if item.get("repair_description"):
            last_repair_description = item["repair_description"]
        elif last_repair_description:
            # Carry forward from previous page/item
            item["repair_description"] = last_repair_description
        all_items.append(item)
```

### Logic

- As we iterate through items across all pages, we track the most recent non-null `repair_description`.
- If an item on page N+1 has no `repair_description` (because the LLM on that page didn't see the section header), we fill it in from the last known value.
- This correctly handles multi-page repairs where the header is only on the first page.

### Edge Cases

- If a new section header appears on page 2, that becomes the new `last_repair_description` and is carried forward from there.
- Items before any section header (null `repair_description`) remain null — we don't backfill.

### How to Verify

Re-extract claim 64535:
```bash
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2/64535 --stages ingest,classify,extract
```

Check that parts on page 2 now have `repair_description` populated with the section header from page 1 (e.g., "Roulement de roue AR G").

---

## Change 4: Strip GRU/Grundteil Prefix from item_code

### Problem

Claim 65150 (AMAG Sursee, Audi A8) uses the AMAG cost estimate format where part numbers have a "GRU" (Grundteil) prefix:

```
GRU 4N0 407 613 A    RADNABE
GRU 4N0 407 615 A    RADNABE
```

The actual part number is `4N0 407 613 A`, but extraction captures `GRU 4N0 407 613 A`. The "GRU" prefix prevents the part number from matching against known part catalogs.

### File to Modify

**`src/context_builder/prompts/nsa_cost_estimate_page.md`** — Add a note about prefix stripping.

Add this as a new note (after note 6 from Change 2):

```markdown
7. **Part number prefixes (strip them)**: Some cost estimates prefix part numbers with codes like "GRU" (Grundteil/base part), "ZUB" (Zubehör/accessory), or "POS". These prefixes are NOT part of the actual part number. Strip them:
   - "GRU 4N0 407 613 A" → item_code: "4N0 407 613 A"
   - "ZUB 8W0616887" → item_code: "8W0616887"
   - The prefix can optionally be noted in the description if relevant
```

### Where to Insert

After the new note 6 (footer summary rows from Change 2), before the `## Output Format` section.

### How to Verify

Re-extract claim 65150:
```bash
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2/65150 --stages ingest,classify,extract
```

Check that item codes no longer start with "GRU ":
```json
{"item_code": "4N0 407 613 A", "description": "RADNABE", ...}
```

Not:
```json
{"item_code": "GRU 4N0 407 613 A", "description": "RADNABE", ...}
```

---

## Implementation Order

Recommended order (each change is independent, but this order minimizes re-testing):

1. **Change 2 + 4** (prompt changes) — Edit `nsa_cost_estimate_page.md` once with both additions
2. **Change 3** (merge logic) — Edit `nsa_cost_estimate.py` `_merge_page_results()`
3. **Change 1** (schema + aggregation) — Edit `claim_facts.py` and `aggregation.py`

After all 4 changes:

```bash
# Re-run full pipeline on all 50 eval claims
python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2

# Find the new run ID
ls workspaces/nsa/claim_runs/

# Evaluate
python scripts/eval_pipeline.py --run-id <new_run_id>
```

## Expected Impact

| Metric | Current (eval_20260130_032512) | Expected After |
|--------|-------------------------------|----------------|
| `refer_should_approve:no_fails` | 5 | 1-2 (4 caused by extraction gaps) |
| `false_reject:component_coverage` | 1 | 0-1 (better context improves matching) |
| Overall accuracy | 60% (30/50) | 64-68% (34/50 target) |

The `amount_mismatch` errors (10 claims) are a separate issue related to payout calculation, not extraction.

## Customer Config Note

Changes 2 and 4 modify `src/context_builder/prompts/nsa_cost_estimate_page.md` which is in the main repo.
Change 3 modifies `workspaces/nsa/config/extractors/nsa_cost_estimate.py` which is in the **customer config repo**.

After implementing, remember to sync customer config:
```bash
powershell -ExecutionPolicy Bypass -File "C:\Users\fbrun\Documents\GitHub\context-builder-nsa\copy-from-workspace.ps1"
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" add -A
git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" commit -m "feat: improve extraction context for coverage accuracy"
```
