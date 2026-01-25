# Assumptions.json Configuration Format

The `assumptions.json` file provides deterministic lookup tables for claims assessment, eliminating LLM hallucination risk for part coverage and shop authorization decisions.

## Location

```
workspaces/{workspace}/config/assumptions.json
```

## Schema Overview

```json
{
  "schema_version": "assumptions_v1",
  "updated_at": "2026-01-25T00:00:00Z",
  "updated_by": "human",

  "part_system_mapping": { ... },
  "authorized_partners": { ... },
  "business_rules": { ... },
  "coverage_tiers": { ... },
  "excluded_items": { ... }
}
```

## Sections

### 1. part_system_mapping

Maps parts to coverage status using two lookup methods:

#### By Part Number (highest priority)
```json
"by_part_number": {
  "8W0616887": {
    "system": "suspension",
    "component": "height_control_valve",
    "covered": true
  },
  "4M0827506F": {
    "system": "body",
    "component": "trunk_lock",
    "covered": false,
    "reason": "accessory"
  }
}
```

#### By Keyword (case-insensitive match in description)
```json
"by_keyword": {
  "zylinderkopf": {
    "system": "engine",
    "component": "cylinder_head",
    "covered": true
  },
  "serrure": {
    "system": "body",
    "component": "lock",
    "covered": false,
    "reason": "accessory"
  }
}
```

**Fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| system | string | Yes | System category (engine, transmission, suspension, etc.) |
| component | string | Yes | Specific component name |
| covered | boolean | Yes | Whether the part is covered under warranty |
| reason | string | No | Reason for exclusion (wear_part, accessory, etc.) |
| note | string | No | Additional context for edge cases |

### 2. authorized_partners

Identifies authorized repair shops:

#### By Name (exact or partial match)
```json
"by_name": {
  "AMAG": {"authorized": true, "regions": ["CH"]},
  "AMAG Bern Wankdorf": {"authorized": true},
  "Kestenholz Automobil AG": {"authorized": true}
}
```

#### By Pattern (regex)
```json
"by_pattern": [
  {"pattern": "^AMAG.*", "authorized": true, "note": "All AMAG locations"},
  {"pattern": ".*Audi Service Partner.*", "authorized": true}
]
```

**Default behavior for unknown shops:**
```json
"_default_if_unknown": "REFER_TO_HUMAN"
```

### 3. business_rules

Configurable policy defaults:

```json
"business_rules": {
  "unknown_authorization": {
    "action": "REFER_TO_HUMAN",
    "reason": "Shop authorization status could not be verified"
  },
  "unknown_part_coverage": {
    "action": "REFER_TO_HUMAN",
    "reason": "Part not found in coverage lookup table"
  },
  "missing_damage_date": {
    "action": "REFER_TO_HUMAN",
    "reason": "Cannot verify damage occurred within policy period"
  },
  "payout_near_max_coverage": {
    "threshold_percent": 90,
    "action": "use_max_coverage",
    "reason": "Adjuster policy: close claim at max to prevent follow-ups"
  }
}
```

### 4. coverage_tiers

Mileage-based coverage percentages (fallback if not in policy):

```json
"coverage_tiers": {
  "default": [
    {"max_km": 50000, "parts_percent": 80, "labor_percent": 100},
    {"max_km": 80000, "parts_percent": 60, "labor_percent": 100},
    {"max_km": 110000, "parts_percent": 40, "labor_percent": 100},
    {"max_km": 999999, "parts_percent": 20, "labor_percent": 100}
  ]
}
```

### 5. excluded_items

Items never covered regardless of part mapping:

```json
"excluded_items": {
  "categories": ["rental_fee", "towing_fee", "environmental_fee", "diagnostic_fee"],
  "keywords": ["ERSATZFAHRZEUG", "MIETWAGEN", "ENTSORGUNG", "ABSCHLEPP", "ÉLIMINATION"]
}
```

## Lookup Priority

The enrichment process checks in this order:

1. **excluded_items.keywords** - If description matches, `covered: false`
2. **part_system_mapping.by_part_number** - Exact part number match
3. **part_system_mapping.by_keyword** - Keyword found in description
4. **Fallback** - `covered: null` with `action: REFER_TO_HUMAN`

## Enrichment Output

After enrichment, each line item includes:

```json
{
  "description": "ZYLINDERKOPF",
  "total_price": 982.00,
  "_coverage_lookup": {
    "lookup_method": "keyword",
    "matched_keyword": "zylinderkopf",
    "system": "engine",
    "component": "cylinder_head",
    "covered": true
  }
}
```

And the claim includes:

```json
{
  "_shop_authorization_lookup": {
    "lookup_method": "exact_name",
    "matched_name": "AMAG",
    "authorized": true
  },
  "_enrichment_summary": {
    "total_line_items": 194,
    "covered_count": 20,
    "covered_amount": 8698.40,
    "not_covered_count": 0,
    "not_covered_amount": 0,
    "unknown_count": 174,
    "unknown_amount": 4921.00
  }
}
```

## Adding New Parts

### Adding a Part Number

1. Find the part number from the invoice/cost estimate
2. Identify the system (engine, transmission, suspension, etc.)
3. Determine if it's covered under warranty
4. Add to `by_part_number`:

```json
"NEW_PART_123": {
  "system": "engine",
  "component": "oil_pump",
  "covered": true
}
```

### Adding a Keyword

1. Identify a unique keyword from part descriptions
2. Ensure it won't match unintended parts
3. Add to `by_keyword`:

```json
"ölpumpe": {
  "system": "engine",
  "component": "oil_pump",
  "covered": true
}
```

### Adding an Authorized Partner

1. Get the exact shop name from invoices
2. Add to `by_name` or create a pattern:

```json
"New Dealer Name": {"authorized": true}
```

## Versioning

Always update these fields when modifying:

```json
{
  "schema_version": "assumptions_v1",
  "updated_at": "2026-01-25T12:00:00Z",
  "updated_by": "john.doe"
}
```

The assessment output includes this version for traceability:
```json
"_meta": {
  "assumptions_version": "assumptions_v1",
  "assumptions_updated_at": "2026-01-25T00:00:00Z"
}
```

## Testing Changes

After modifying assumptions.json:

```bash
# Dry run to see enrichment without API call
python workspaces/nsa/config/scripts/run_assessment.py --claim 65128 --dry-run

# Run assessment and evaluate
python workspaces/nsa/config/scripts/run_assessment.py --all
python workspaces/nsa/config/scripts/eval_assessment.py --eval-only
```

Check the logs for:
- `Coverage lookup: X covered, Y not covered, Z unknown`
- `Unknown coverage for N high-value items`
- `Shop authorization: AUTHORIZED/NOT AUTHORIZED/UNKNOWN`
