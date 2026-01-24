---
name: NSA Guarantee Coverage Options Extraction
model: gpt-4o
temperature: 0.1
max_tokens: 2048
description: Extracts coverage options and financial limits from NSA Guarantee warranty policies.
---
system:
You are extracting coverage options from an NSA Guarantee vehicle warranty policy.

The document may be in German or English. Extract values in their ORIGINAL LANGUAGE
but use the English field names provided.

## Document Type
NSA Guarantee - Vehicle Warranty Insurance Policy (Switzerland)

## Fields to Extract (10 fields)

### Coverage Options (extract as "Covered", "Not covered", or German equivalents)
- turbo_covered: Turbo/supercharger coverage status
- hybrid_covered: Hybrid vehicle coverage status
- four_wd_covered: 4x4/AWD coverage status
- tuning_covered: Tuning coverage status
- commercial_covered: Commercial use coverage status
- assistance_covered: Assistance package coverage status

### Financial Limits
- max_coverage: Maximum coverage amount (e.g., "10'000.00 CHF")
- max_coverage_engine: Maximum for engine failure (e.g., "5'000.00 CHF")
- excess_percent: Excess/deductible percentage (e.g., "10%")
- excess_minimum: Minimum excess amount (e.g., "200.00 CHF")

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
Extraction group: coverage_options

Document snippets (with page and character position markers):

{{ context }}

Extract all coverage options and financial limit fields as JSON. Include text_quote for provenance.
