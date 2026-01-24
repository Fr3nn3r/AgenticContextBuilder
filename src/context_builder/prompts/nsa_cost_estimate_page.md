---
name: NSA Cost Estimate Page Extraction
model: gpt-4o
temperature: 0.1
max_tokens: 4096
description: Extracts line items and metadata from a single page of a Swiss automotive repair cost estimate.
---
system:
You are extracting structured data from ONE PAGE of a Swiss automotive repair cost estimate (Kostenvoranschlag/Offerte).

The document may be in German or French. Extract values in their ORIGINAL LANGUAGE.

## Document Type
Cost Estimate / Quote from Swiss automotive dealers (AMAG, Kestenholz, etc.)

## Page Context
- page_number: {{ page_number }}
- is_first_page: {{ is_first_page }}
- is_last_page: {{ is_last_page }}
- total_pages: {{ total_pages }}

## What to Extract

### If First Page (page 1): Extract Header
- document_number: Order/Quote number (e.g., "217126907", "244203", "01418775")
- document_date: Document date (format as found, e.g., "07 janvier 2026", "12.01.2026")
- document_type: Type (Offerte, Kostenvoranschlag, Kontrollauftrag, Ordre contrôle)
- license_plate: Vehicle plate (e.g., "VS 147831", "ZH 293885", "BL216305")
- chassis_number: VIN/Chassis number (17+ chars, e.g., "VSSZZZKMZMR025337")
- vehicle_description: Vehicle description (e.g., "CUPRA FORMENTOR 4DRIVE", "VW Golf 2.0 TSI GTI")
- garage_name: Garage/dealer name (e.g., "AMAG", "Kestenholz Automobil AG")

### On Every Page: Extract Line Items
Extract ALL line items visible on THIS PAGE. Each item needs:

- item_code: Part/labor code if present (e.g., "01500060", "MA270 015 02 00", "4M0827506F")
  - May be blank for flat-rate labor items
- description: Item description in original language
- quantity: Number of units (may be blank for labor)
- unit: Unit type if shown (ST, Pce, L, etc.)
- unit_price: Price per unit before discount (may be blank)
- total_price: Final line total - THIS IS REQUIRED for every item
- item_type: Classify as one of:
  - "labor": Work codes, items with AUS-/EINBAUEN, PRUEFEN, DIAGNOSE, GEFUEHRTE FUNKTION
  - "parts": Part numbers, SCHRAUBE, DICHTRING, VENTIL, OEL, physical components
  - "fee": ENTSORGUNG, UMWELT, ERSATZFAHRZEUG, disposal fees, rental

### Page Totals (if present)
- carry_forward_amount: "Übertrag" amount at TOP of page (from previous page)
- page_subtotal: "Übertrag" or subtotal at BOTTOM of page

### If Last Page: Extract Financial Summary
- labor_total: Summe Arbeitsleistungen / Total labor
- parts_total: Summe Teilepositionen / Total parts
- subtotal_before_vat: Summe Positionen / Somme des positions (before VAT)
- vat_rate: VAT percentage (usually 8.1% in Switzerland)
- vat_amount: VAT amount (MwSt / TVA)
- total_amount_incl_vat: Final total including VAT
- currency: Currency (CHF)

## Important Notes

1. **Strikethrough prices**: Some documents show crossed-out prices with discounts ("Kulanz"). Extract the FINAL price, not the crossed-out one.

2. **Line item classification**:
   - Labor codes often start with 01..., 54..., 61..., 43..., etc.
   - Part numbers often have formats like "MA270 015 02 00" or "4M0827506F"
   - Fees have codes like "ZCHQS114", "ZCHQS382"

3. **Multi-line descriptions**: Some items span multiple lines. Combine them into one item.

4. **Category headers**: Ignore category headers like "GERÄUSCHE HINTERACHSE" or "COFFRE ÉLECTRIQUE" - extract only the actual line items.

5. **Zero-price items**: Include items with 0.00 price (e.g., "für Sie kostenlos").

## Output Format

Return JSON:

```json
{
  "page_number": 1,
  "header": {
    "document_number": "244203",
    "document_date": "12.01.2026",
    "document_type": "Offerte",
    "license_plate": "ZH 293885",
    "chassis_number": "WVWZZZCD5RW127448",
    "vehicle_description": "VW Golf 2.0 TSI GTI Club DSG",
    "garage_name": "Kestenholz Automobil AG"
  },
  "carry_forward_amount": null,
  "line_items": [
    {
      "item_code": "01500060",
      "description": "GFS/GEFUEHRTE FUNKTION DIAGNOSE",
      "quantity": null,
      "unit": null,
      "unit_price": null,
      "total_price": 240.00,
      "item_type": "labor"
    },
    {
      "item_code": "8W0616887",
      "description": "VENTIL",
      "quantity": 2,
      "unit": "ST",
      "unit_price": 883.45,
      "total_price": 1766.90,
      "item_type": "parts"
    }
  ],
  "page_subtotal": 4415.40,
  "summary": null
}
```

For first page, include "header". For last page, include "summary":

```json
{
  "summary": {
    "labor_total": 4526.90,
    "parts_total": 2789.05,
    "subtotal_before_vat": 7315.95,
    "vat_rate": 8.1,
    "vat_amount": 592.59,
    "total_amount_incl_vat": 7908.55,
    "currency": "CHF"
  }
}
```

user:
Extracting page {{ page_number }} of {{ total_pages }}.
{% if is_first_page %}This is the FIRST page - extract header information.{% endif %}
{% if is_last_page %}This is the LAST page - extract financial summary.{% endif %}

Page content:

{{ context }}

Extract all data as JSON. Every line item must have total_price and item_type.
