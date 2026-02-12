# Plan: Fix Eurotax Cost Estimate Extraction

## Problem

Claim 65055 (and likely other Eurotax/EC2 format cost estimates) has two extraction bugs:

1. **Labor column completely lost** — CHF 1,696 in labor not extracted
2. **Parts duplicated across pages** — Items extracted from both detailed calc (page 4) and replacement parts table (page 5)

This causes total_claimed to be wrong (CHF 1,587 vs actual CHF 2,597) and covered amount to be wrong (CHF 40 vs ground truth CHF 910), cascading into a false REJECT.

## Root Cause

The LLM prompt (`src/context_builder/prompts/nsa_cost_estimate_page.md`) was designed for AMAG/Kestenholz format where each row is either labor OR parts with a single price. Eurotax/EC2 format is different:

- **Page 4 (Calcul)**: Each row has TWO price columns — `Travail` (labor) and `Matériel` (parts)
- **Page 5 (Résumé)**: Contains a "Désignation pièce / Désignation pièce précédente" cross-reference table that lists the same parts again with replacement part numbers

### Example: Timing belt row on page 4

| Part # | Description | Temps de travail | Travail | Matériel |
|--------|-------------|-----------------|---------|----------|
| 213040 | Courroie crantée/chaîne de distribution | 7.00 | 1,120.00 | 342.02 |

Current extraction: ONE item with total_price=342.02 (labor lost)
Correct extraction: TWO items — labor CHF 1,120.00 + parts CHF 342.02

## Fix: Prompt Changes Only

File: `src/context_builder/prompts/nsa_cost_estimate_page.md`

No schema changes, no code changes — just two new notes in the prompt.

### Change 1: Add note 8 — Eurotax dual-column format

Insert after line 90 (after note 7 about part number prefixes):

```markdown
8. **Eurotax dual-column format (Travail + Matériel)**: Some cost estimates (EurotaxGlass's / EC2) show
   a `Travail` (labor) column AND a `Matériel` (material/parts) column on the SAME row. When a row has
   BOTH a Travail amount and a Matériel amount, emit TWO line items:
   - One with `item_type: "labor"` and `total_price` = the Travail amount
   - One with `item_type: "parts"` and `total_price` = the Matériel amount
   Both items share the same `item_code` and `description`. If a row has only Travail (no Matériel) or
   only Matériel (no Travail), emit a single item. The `Temps de travail` column is hours worked — do NOT
   use it as a price. Labor price is in the `Travail` column (hours × hourly rate).
```

### Change 2: Add note 9 — Skip replacement parts cross-reference tables

Insert after the new note 8:

```markdown
9. **Replacement parts cross-reference tables (DO NOT extract)**: Eurotax/EC2 documents include a
   "Désignation pièce / Désignation pièce précédente" table that maps original part numbers to
   replacement part numbers. This is a cross-reference for ordering, NOT additional line items. Do NOT
   extract items from these tables — they duplicate the items already extracted from the detailed
   calculation page. Similarly, skip "Désignation pièce / Position / Désignation position" tables.
```

## Expected Impact

### Before fix (claim 65055):
- 33 items: 1 labor, 32 parts
- Total extracted: CHF 1,591 (parts only, doubled)
- Covered: CHF 40.25 → payout CHF 0 → REJECT

### After fix (expected):
- ~18 unique items: labor + parts properly split
- Total extracted: ~CHF 2,512 (labor CHF 1,696 + material CHF 816)
- Covered amount should align closer to ground truth CHF 910

## Validation

1. Re-run extraction for claim 65055: `python -m context_builder.cli pipeline data/09-Claims-Motor-NSA-2/65055 --force --stages ingest,classify,extract`
2. Check line_items in claim_facts.json — should have labor items and no duplicates
3. Re-run full pipeline and eval to check for regressions

## Risks

- Other non-Eurotax cost estimates should be unaffected (notes only trigger on Eurotax-specific patterns)
- The LLM might over-apply the dual-column rule to other formats — mitigated by specifying "EurotaxGlass's / EC2" explicitly
- Page 5 cross-reference skip might miss legitimate items on summary pages — mitigated by specifying exact table header patterns
