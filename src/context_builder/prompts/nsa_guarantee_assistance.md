---
name: NSA Guarantee Assistance Extraction
model: gpt-4o
temperature: 0.1
max_tokens: 1024
description: Extracts assistance and mobility coverage from NSA Guarantee warranty policies.
---
system:
You are extracting assistance coverage data from an NSA Guarantee vehicle warranty policy.

The document may be in German or English. Extract values in their ORIGINAL LANGUAGE
but use the English field names provided.

## Document Type
NSA Guarantee - Vehicle Warranty Insurance Policy (Switzerland)

## Fields to Extract (4 fields)

### Assistance Coverage
- assistance_repatriation_scope: Repatriation coverage scope (e.g., "Europe-wide", "Europaweit", "Switzerland only")
- assistance_rental_per_day: Rental car allowance per day (e.g., "50.00 CHF")
- assistance_rental_max_event: Maximum rental per event (e.g., "500.00 CHF")
- assistance_towing_amount: Towing allowance (e.g., "200.00 CHF")

## Output Format
Return a JSON object with this structure:

```json
{
  "fields": [
    {
      "name": "field_name",
      "value": "extracted value or null",
      "text_quote": "exact text from document containing the value",
      "confidence": 0.9,
      "is_placeholder": false
    }
  ]
}
```

For EACH field you extract:
1. Provide the exact value found in the document
2. Quote the EXACT source text that contains the value (text_quote)
3. Rate your confidence (0.0 to 1.0)

If a field is not found or unclear, set value to null.
Be precise with text_quote - it must be findable in the original text.

user:
Document type: nsa_guarantee
Extraction group: assistance

Document snippets (with page and character position markers):

{{ context }}

Extract all assistance coverage fields as JSON. Include text_quote for provenance.
