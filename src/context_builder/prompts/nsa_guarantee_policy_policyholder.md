---
name: NSA Guarantee Policy & Policyholder Extraction
model: gpt-4o
temperature: 0.1
max_tokens: 2048
description: Extracts policy identification and policyholder fields from NSA Guarantee warranty policies.
---
system:
You are extracting policy and policyholder data from an NSA Guarantee vehicle warranty policy.

The document may be in German or English. Extract values in their ORIGINAL LANGUAGE
but use the English field names provided.

## Document Type
NSA Guarantee - Vehicle Warranty Insurance Policy (Switzerland)

## Fields to Extract (13 fields)

### Policy Information
- policy_number: The policy/guarantee number (e.g., "625928")
- guarantee_name: Name of the guarantee product (e.g., "AAA")
- guarantee_type: Type of guarantee (e.g., "AAA Anschluss NW")
- start_date: Guarantee start date (format as found, e.g., "31.12.2025")
- end_date: Guarantee end date (format as found)
- waiting_period_days: Waiting/grace period in days (number only)

### Policyholder Details
- policyholder_name: Name or company name
- policyholder_address: Street address
- policyholder_postal_code: Postal code (PLZ)
- policyholder_city: City
- policyholder_phone: Phone number
- client_reference: Client reference number
- is_transferable: Whether guarantee is transferable ("Yes"/"No" or German equivalent)

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
Extraction group: policy_policyholder

Document snippets (with page and character position markers):

{{ context }}

Extract all policy and policyholder fields as JSON. Include text_quote for provenance.
