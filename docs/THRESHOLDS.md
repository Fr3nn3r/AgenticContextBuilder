# Thresholds and Business Constants

Catalog of all configurable thresholds, caps, and business constants used in the
NSA customer configuration. After REFACTOR-04 Phase 4, all values below are loaded
from YAML/JSON config files at runtime (no hardcoded magic numbers in Python code).

## Fee Caps (Decision Engine)

| Threshold | Value | Config Location | Clause | Rationale |
|-----------|-------|-----------------|--------|-----------|
| Max diagnostic fee | 250.00 CHF | `config/decision/fee_caps.yaml` | 2.4.A.f | Caps reimbursable diagnostic/inspection fees per claim |
| Max towing fee | 500.00 CHF | `config/decision/fee_caps.yaml` | 2.4.A.g | Caps reimbursable towing/recovery charges per claim |

## Service Compliance (Screener)

| Threshold | Value | Config Location | Check | Rationale |
|-----------|-------|-----------------|-------|-----------|
| Fallback km interval | 30,000 km | `config/screening/service_interval_fallbacks.yaml` | 4b | Conservative fallback when vehicle brand is unknown |
| Fallback months interval | 24 months | `config/screening/service_interval_fallbacks.yaml` | 4b | Conservative fallback when vehicle brand is unknown |
| Time compliance PASS | ratio <= 1.0 | screener.py (logic) | 4b | Service gap within manufacturer interval |
| Time compliance INCONCLUSIVE | 1.0 < ratio <= 1.5 | screener.py (logic) | 4b | Service gap approaching/slightly exceeding interval |
| Time compliance FAIL | ratio > 1.5 | screener.py (logic) | 4b | Service gap clearly exceeds manufacturer interval |
| Chronic non-maintenance | >= 2 gaps > 2.0x | screener.py (logic) | 4b | Pattern of repeated missed services |
| VIN minimum length | 13 chars | screener.py (logic) | 2 | VINs shorter than 13 chars treated as OCR fragments |

## Coverage Analysis (Screener)

| Threshold | Value | Config Location | Check | Rationale |
|-----------|-------|-----------------|-------|-----------|
| Primary repair high confidence | >= 0.80 | screener.py (logic) | 5 | Confidence threshold for deterministic FAIL on uncovered primary repair |
| Vehicle age calculation | 365.25 days/year | screener.py (logic) | coverage | Standard leap-year-averaged year length |

## Payout Calculation (Screener)

| Threshold | Value | Config Location | Rationale |
|-----------|-------|-----------------|-----------|
| Swiss VAT rate | 8.1% (0.081) | screener.py `SWISS_VAT_RATE` | Current Swiss standard VAT rate |
| Reporting deadline | 30 days | denial_clauses.json clause 2.6.C.a | Policy contractual reporting deadline |

## Labor Rate Validation (Decision Engine)

| Threshold | Value | Config Location | Clause | Rationale |
|-----------|-------|-----------------|--------|-----------|
| Default max hourly rate | 180.00 CHF | `config/decision/services/labor_rates.json` | 2.4.A.d | Default cap when no brand-specific rate is configured |
| Default flat-rate hours | 4.0 hours | `config/decision/services/labor_rates.json` | 2.4.A.c | Default max labor hours for standard operations |

## Keyword Lists

| List | Count | Config Location | Used By |
|------|-------|-----------------|---------|
| Assistance keywords | 8 | `config/keyword_lists.yaml` | Screener check 5b |
| Diagnostic keywords | 9 | `config/keyword_lists.yaml` | Engine clause 2.4.A.f |
| Towing keywords | 7 | `config/keyword_lists.yaml` | Engine clause 2.4.A.g |
| Admin keywords | 7 | `config/keyword_lists.yaml` | Engine clause 2.4.A.h |

## Manufacturer Service Intervals

Brand-specific intervals are defined in `config/screening/service_requirements.json`.
Representative examples:

| Brand | System | km | Months | Notes |
|-------|--------|----|--------|-------|
| VW Group | Dual (fixed) | 15,000 | 12 | Conservative; LongLife not verifiable |
| Mercedes | Flexible (service_a) | 25,000 | 12 | Service A interval |
| Ford | Flexible (ecoboost) | 24,000 | 12 | Petrol EcoBoost interval |
| Generic fallback | -- | 30,000 | 24 | Used when brand is unknown |

## Assumption Defaults

All clause assumptions default to `true` (non-rejecting) unless overridden per-claim.
See `denial_clauses.json` for the full clause registry with `default_assumption` values.

## Config File Summary

| File | Location | Contents |
|------|----------|----------|
| `fee_caps.yaml` | `config/decision/` | Diagnostic and towing fee caps |
| `service_interval_fallbacks.yaml` | `config/screening/` | Default service interval when brand unknown |
| `keyword_lists.yaml` | `config/` | All keyword lists for item type detection |
| `denial_clauses.json` | `decision/` | Clause registry with assumption questions |
| `service_requirements.json` | `screening/` | Manufacturer-specific service intervals |
| `labor_rates.json` | `decision/services/` | Labor rate caps and flat-rate hours |
| `parts_keywords.yaml` | `decision/services/` | Parts classification keywords |
| `dtc_exclusion_mappings.yaml` | `screening/` | DTC-to-component exclusion mappings |
| `rejected_policies.json` | `screening/` | Policy enforcement blacklist |
| `assumptions.json` | root | Shop authorization, part mappings |
