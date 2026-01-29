# Coverage Analysis Implementation Plan

## Overview

This document describes the plan for implementing automated coverage analysis for insurance claims. The system will analyze line items from cost estimates against policy coverage to determine what is covered, what is not, and calculate the payable amounts.

## Problem Statement

Currently, the assessment process (LLM-based) handles coverage matching as part of claim decision-making. This is too much for the LLM to do accurately and consistently. We need a preprocessing step that:

1. Analyzes each line item from cost estimates
2. Matches items against policy coverage (from `nsa_guarantee`)
3. Calculates coverage amounts based on mileage-based scales
4. Outputs structured data for the assessment to consume

## Data Flow

```
                          ┌─────────────────────┐
                          │   claim_facts.json  │
                          │  - line_items       │
                          │  - covered_components│
                          │  - coverage_scale   │
                          │  - vehicle_km       │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │  Coverage Analysis  │
                          │   (preprocessing)   │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │coverage_analysis.json│
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │     Assessment      │
                          │  (uses analysis)    │
                          └─────────────────────┘
```

## Input Requirements

From `claim_facts.json`, the coverage analyzer requires:

| Field | Source Document | Required | Purpose |
|-------|-----------------|----------|---------|
| `structured_data.line_items` | cost_estimate | Yes | Items to analyze |
| `covered_components` | nsa_guarantee | Yes | What's covered |
| `excluded_components` | nsa_guarantee | No | Explicit exclusions |
| `coverage_scale` | nsa_guarantee | Yes | % coverage by km |
| `vehicle_current_km` or `odometer_km` | nsa_guarantee / dashboard_image | Yes | Determine coverage % |
| `max_coverage` | nsa_guarantee | Yes | Claim limit |
| `excess_percent` | nsa_guarantee | Yes | Deductible % |
| `excess_minimum` | nsa_guarantee | No | Minimum deductible |
| `turbo_covered`, `four_wd_covered`, etc. | nsa_guarantee | No | Optional coverage flags |

If required fields are missing, the analysis will fail with a clear error.

## Output Schema

The output will be saved as `coverage_analysis.json` in the claim context folder:
`claims/{claim_id}/context/coverage_analysis.json`

```json
{
    "schema_version": "coverage_analysis_v1",
    "claim_id": "65196",
    "generated_at": "2026-01-28T12:00:00Z",
    "claim_run_id": "clm_20260128_...",

    "inputs": {
        "line_items_count": 14,
        "vehicle_km": 74359,
        "coverage_percent": 60,
        "max_coverage": 10000.00,
        "excess_percent": 10,
        "excess_minimum": 150.00
    },

    "line_items": [
        {
            "item_code": "8W0616887",
            "description": "VENTIL",
            "item_type": "parts",
            "total_price": 1766.90,

            "coverage_status": "covered",
            "coverage_category": "chassis",
            "matched_component": "Height control",
            "match_method": "keyword",
            "match_confidence": 0.85,
            "match_reasoning": "VENTIL + HYDRAULIK context → air suspension valve → Chassis/Height control",

            "covered_amount": 1060.14,
            "not_covered_amount": 706.76
        }
    ],

    "summary": {
        "total_claimed": 3520.55,
        "total_covered_before_excess": 2100.00,
        "total_not_covered": 1420.55,
        "excess_amount": 210.00,
        "total_payable": 1890.00,
        "coverage_limit_used": 1890.00,
        "coverage_limit_remaining": 8110.00,
        "items_covered": 8,
        "items_not_covered": 4,
        "items_review_needed": 2,
        "confidence_avg": 0.82
    },

    "analysis_metadata": {
        "rules_applied": 6,
        "keyword_matches": 5,
        "llm_calls": 3,
        "processing_time_ms": 1250
    }
}
```

## Architecture: Core vs Customer Separation

The implementation follows the same pattern as extractors: generic core framework with customer-specific configuration.

### Core Framework (Generic)

Location: `src/context_builder/coverage/`

```
src/context_builder/coverage/
├── __init__.py
├── analyzer.py           # CoverageAnalyzer base class
├── schemas.py            # Pydantic models (CoverageAnalysisResult, etc.)
├── rule_engine.py        # Execute rules from config
├── keyword_matcher.py    # Match using keyword config
└── llm_matcher.py        # LLM fallback (reads prompt from config)
```

The core provides:
- Generic orchestration logic
- Standard output schemas
- Config loading from workspace
- Rule/keyword/LLM execution engines

### Customer Configuration (NSA-Specific)

Location: `workspaces/nsa/config/coverage/`

```
workspaces/nsa/config/coverage/
├── nsa_coverage_config.yaml      # Main configuration
├── nsa_keyword_mappings.yaml     # German→English→Category mappings
├── nsa_exclusions.yaml           # NSA-specific exclusions
└── prompts/
    └── nsa_coverage_prompt.md    # LLM prompt template
```

The customer config provides:
- Language-specific keyword mappings (German for NSA)
- Policy-specific exclusion rules
- Coverage category definitions
- LLM prompt templates

## Matching Pipeline

For each line item, the analyzer applies methods in order:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. RULES (fast, deterministic, confidence=1.0)              │
│    ├─ item_type == "fee" → NOT_COVERED                      │
│    ├─ description matches EXCLUSION_PATTERNS → NOT_COVERED  │
│    └─ description matches CONSUMABLE_PATTERNS → NOT_COVERED │
│                          │                                   │
│                          ▼ (if no rule matched)              │
│ 2. KEYWORD MAPPING (confidence=0.7-0.9)                     │
│    ├─ Translate German → English                            │
│    ├─ Map to component category                             │
│    ├─ Consider context hints (nearby items)                 │
│    └─ Check if category in covered_components               │
│                          │                                   │
│                          ▼ (if no keyword matched)           │
│ 3. LLM FALLBACK (confidence=0.6-0.85)                       │
│    ├─ Send: item + context + covered_components list        │
│    ├─ Receive: category + reasoning                         │
│    └─ Validate against covered_components                   │
│                          │                                   │
│                          ▼ (if LLM uncertain)                │
│ 4. REVIEW_NEEDED (confidence < threshold)                   │
└─────────────────────────────────────────────────────────────┘
```

### Why This Order?

1. **Rules first**: Fast, deterministic, handles obvious cases (fees, known exclusions)
2. **Keywords second**: Handles most repair terminology without LLM cost
3. **LLM last**: Only for genuinely ambiguous items, controls cost

## Configuration Examples

### Main Config (`nsa_coverage_config.yaml`)

```yaml
version: "1.0"
analyzer_class: "default"

rules:
  never_covered:
    item_types: ["fee"]
    description_patterns:
      - "ENTSORGUNG.*"
      - "UMWELT.*"
      - "ERSATZFAHRZEUG.*"

  consumables:
    patterns:
      - ".*OEL.*"
      - ".*FILTER.*"
      - ".*DICHTUNG.*"

thresholds:
  keyword_match_confidence: 0.80
  llm_match_confidence: 0.70
  review_needed_below: 0.60

llm:
  enabled: true
  model: "gpt-4o"
  prompt_template: "prompts/nsa_coverage_prompt.md"
  max_tokens: 500
```

### Keyword Mappings (`nsa_keyword_mappings.yaml`)

```yaml
version: "1.0"

mappings:
  # Engine components
  MOTOR: { en: "Engine", category: "engine" }
  KOLBEN: { en: "Piston", category: "engine" }
  KURBELWELLE: { en: "Crankshaft", category: "engine" }
  VENTIL: { en: "Valve", category: "engine", ambiguous: true }
  TURBO: { en: "Turbo", category: "turbo_supercharger" }

  # Transmission
  GETRIEBE: { en: "Transmission", category: "mechanical_transmission" }
  KUPPLUNG: { en: "Clutch", category: "mechanical_transmission" }

  # Chassis/Suspension
  FAHRWERK: { en: "Suspension", category: "suspension" }
  LUFTFEDERUNG: { en: "Air suspension", category: "chassis" }

  # Body (typically NOT covered in powertrain warranties)
  SERRURE: { en: "Lock", category: "body", typically_excluded: true }
  TUER: { en: "Door", category: "body", typically_excluded: true }

context_hints:
  VENTIL:
    - { context: "HYDRAULIK", prefer_category: "chassis" }
    - { context: "MOTOR", prefer_category: "engine" }
    - { context: "BREMSE", prefer_category: "brakes" }
```

## Implementation Phases

| Phase | Scope | Deliverables |
|-------|-------|--------------|
| **1. Foundation** | Schemas + analyzer skeleton | `coverage/schemas.py`, `coverage/analyzer.py` |
| **2. Config Loading** | Load customer config from workspace | Config loader + validation |
| **3. Rules Engine** | Rule-based matching | `coverage/rule_engine.py` |
| **4. Keyword Matching** | German→Category mapping | `coverage/keyword_matcher.py` |
| **5. LLM Fallback** | Azure OpenAI for ambiguous items | `coverage/llm_matcher.py` |
| **6. NSA Config** | Create NSA-specific configs | `workspaces/nsa/config/coverage/*` |
| **7. Integration** | CLI command + assessment hook | CLI + integration |
| **8. Testing** | Unit tests + validation on claims | Tests |

## CLI Usage

```bash
# Run coverage analysis for a claim
python -m context_builder.cli coverage analyze --claim-id 65196

# Run with verbose output
python -m context_builder.cli coverage analyze --claim-id 65196 --verbose

# Dry run (don't save output)
python -m context_builder.cli coverage analyze --claim-id 65196 --dry-run
```

## Integration with Assessment

The assessment process will:
1. Check if `coverage_analysis.json` exists
2. If not, trigger coverage analysis first
3. Read the analysis results
4. Use pre-calculated coverage amounts in decision-making

This reduces the cognitive load on the assessment LLM and improves accuracy.

## POC Findings: Part Number Databases

During scoping, we tested TecDoc and Part Number Cross Reference APIs (via Apify) for OEM part number lookup. Key findings:

- **TecDoc is aftermarket-focused**: Doesn't index OEM part numbers (like Audi `8W0616887`)
- **Cross-reference limited**: OEM→aftermarket mappings not available for all parts
- **Conclusion**: Cannot rely on part number database for categorization

This is why the implementation uses:
1. Rule-based matching (for obvious cases)
2. Keyword/description matching (for repair terminology)
3. LLM fallback (for ambiguous cases)

Rather than part number lookup.

## Open Questions

1. **Assessment trigger**: Should coverage analysis run automatically when assessment runs, or be a manual prerequisite?

2. **Caching**: Should we cache coverage analysis results, or regenerate each time?

3. **Partial analysis**: If some items can't be matched, should we still output partial results?

## Related Documents

- `docs/APIFY.md` - TecDoc API integration guide (reference only, not used)
- `.claude/docs/customer-config.md` - Customer configuration workflow
- `workspaces/nsa/config/extraction_specs/nsa_guarantee.yaml` - Guarantee extraction spec
- `workspaces/nsa/config/extraction_specs/cost_estimate.yaml` - Cost estimate extraction spec
