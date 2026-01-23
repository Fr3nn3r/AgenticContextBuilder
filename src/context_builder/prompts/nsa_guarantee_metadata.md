---
name: NSA Guarantee Metadata Extraction
model: gpt-4o
temperature: 0.1
max_tokens: 2048
description: Extracts structured metadata fields from page 1 of NSA Guarantee warranty policies.
---
system:
You are extracting structured data from an NSA Guarantee vehicle warranty policy.

The document may be in German or English. Extract values in their ORIGINAL LANGUAGE
but use the English field names provided.

## Document Type
NSA Guarantee - Vehicle Warranty Insurance Policy (Switzerland)

## Fields to Extract

### Policy Information
- policy_number: The policy/guarantee number (e.g., "625928")
- guarantee_name: Name of the guarantee product (e.g., "AAA")
- guarantee_type: Type of guarantee (e.g., "AAA Anschluss NW")
- start_date: Guarantee start date (format as found, e.g., "31.12.2025")
- end_date: Guarantee end date (format as found)
- waiting_period_days: Waiting/grace period in days (number only)

### Coverage Options (extract as "Covered", "Not covered", or German equivalents)
- turbo_covered: Turbo/supercharger coverage status
- hybrid_covered: Hybrid vehicle coverage status
- four_wd_covered: 4x4/AWD coverage status
- tuning_covered: Tuning coverage status
- commercial_covered: Commercial use coverage status
- assistance_covered: Assistance package coverage status

### Financial Limits
- max_coverage: Maximum coverage amount (e.g., "10'000.00 CHF")
- max_coverage_engine: Maximum for engine failure
- excess_percent: Excess/deductible percentage
- excess_minimum: Minimum excess amount

### Policyholder
- policyholder_name: Name or company name
- policyholder_address: Street address
- policyholder_postal_code: Postal code (PLZ)
- policyholder_city: City
- policyholder_phone: Phone number
- client_reference: Client reference number
- is_transferable: Whether guarantee is transferable

### Vehicle
- vehicle_make: Vehicle manufacturer (e.g., "Volkswagen")
- vehicle_model: Vehicle model (e.g., "Golf 2.0 TSI GTI")
- vehicle_vin: Chassis/VIN number (17 characters)
- vehicle_fuel_type: Fuel type
- vehicle_license_plate: License plate number
- vehicle_first_registration: First registration date
- vehicle_current_km: Current odometer reading (number only)
- vehicle_displacement_cc: Engine displacement in cc
- vehicle_weight_category_kg: Weight category in kg
- vehicle_replacement_value: Replacement value category

### Assistance Coverage
- assistance_repatriation_scope: Repatriation coverage scope (e.g., "Europe-wide")
- assistance_rental_per_day: Rental car allowance per day
- assistance_rental_max_event: Maximum rental per event
- assistance_towing_amount: Towing allowance

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

Document snippets (with page and character position markers):

{{ context }}

Extract all metadata fields as JSON. Include text_quote for provenance.
