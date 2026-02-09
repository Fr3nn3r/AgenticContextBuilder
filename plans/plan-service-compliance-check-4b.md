# Plan: Manufacturer-Aware Service Compliance Check (4b)

## Goal

Replace the crude 5-year time-gap check in screening check 4b with a manufacturer-aware service interval validator that uses brand-specific and fuel-type-specific recommended intervals from `service-requirements.json`.

## Current State

- **Check 4b in screener.py** (lines 821-900): Finds last service date, checks if within 1825 days (5 years). No brand, fuel type, or mileage awareness.
- **Test reimplementation** (test_nsa_screener.py, lines 268-309): Uses 365-day threshold (simplified).
- Both are too coarse — a 4-year service gap PASSes today even though most manufacturers recommend 12-24 months.

## Files to Change

| File | Action |
|------|--------|
| `workspaces/nsa/config/screening/service_requirements.json` | **CREATE** — Copy brands data from `service-requirements.json` |
| `workspaces/nsa/config/screening/screener.py` | **MODIFY** — Enhanced check 4b with helpers |
| `tests/unit/test_nsa_screener.py` | **MODIFY** — Update reimplemented check + new test cases |

No core code changes (`src/` untouched).

## Implementation Steps

### Step 1: Create config file

Copy `service-requirements.json` to `workspaces/nsa/config/screening/service_requirements.json`. Keep the full structure (brands + metadata).

### Step 2: Add constants to screener.py

Two new module-level dicts:

**BRAND_NORMALIZATION** — Maps extracted brand names (lowercase) to JSON keys:
- `"volkswagen"/"vw"` → `"volkswagen"`
- `"mercedes"/"mercedes-benz"` → `"mercedes_benz"`
- `"cupra"/"seat"` → `"seat_cupra"`
- `"škoda"/"skoda"` → `"skoda"`
- Direct matches for: bmw, audi, opel, ford, hyundai, toyota, dacia, renault, kia, peugeot, citroen/citroën, volvo, fiat, nissan, mazda, mini
- Substring fallback for partial matches

**FUEL_TYPE_NORMALIZATION** — Maps French/German fuel terms to interval keys:
- `"bleifrei"/"sans plomb"/"essence"/"benzin"/"super"` → `"petrol"`
- `"diesel"` → `"diesel"`
- `"electrique"/"électrique"/"elektrisch"/"elektro"` → `"electric"`
- `"hybride"/"hybride essence"/"hybrid"` → `"hybrid"`
- Default when unknown: `"petrol"`

### Step 3: Add helper methods to NSAScreener

1. **`_load_service_requirements()`** — Cached loader (same pattern as `_load_assumptions`)
2. **`_normalize_brand(make)`** — Normalize extracted brand to JSON key, with substring fallback
3. **`_normalize_fuel_type(fuel)`** — Normalize fuel term to interval key, with substring fallback
4. **`_resolve_service_interval(brand_data, fuel_type)`** — Navigate the JSON structure to get `{km_max, months_max, system_type}`:
   - Electric → use `intervals.electric`
   - Hybrid → use `intervals.hybrid`
   - Dual systems (VW Group) → use `intervals.fixed` (conservative; LongLife can't be verified)
   - Flexible systems → use max advertised values
   - Mercedes → use `intervals.service_a`
   - Ford petrol → use `intervals.ecoboost_petrol`
   - Fallback to first available interval

### Step 4: Replace _check_4b_service_compliance

New algorithm:

```
1. Gather inputs: claim_date, service_entries, vehicle_make, vehicle_fuel_type
2. Early exits (SKIPPED): no entries, no claim date, no parseable dates
3. Sort entries by date, find last service before claim
4. Resolve manufacturer interval:
   - Normalize brand → look up in service_requirements.json
   - Normalize fuel type → select correct interval
   - Fallback: 30,000 km / 24 months if brand unknown
5. Check time compliance:
   - months_gap / months_max ratio
   - PASS if ratio <= 1.0
   - INCONCLUSIVE if 1.0 < ratio <= 1.5
   - FAIL if ratio > 1.5
6. Check mileage compliance (if both odometer and service mileage available):
   - km_gap / km_max ratio, same thresholds
7. Combined verdict = worst of time and mileage verdicts
8. If brand unknown: downgrade PASS → INCONCLUSIVE
9. Inter-service gap analysis: flag chronic_non_maintenance if 2+ gaps > 2x interval
10. Build rich evidence dict with all context
```

**Verdict thresholds (1.5x tolerance):**
- Compensates for flexible/adaptive systems where actual interval may be longer
- Example: VW fixed = 12 months → FAIL only after 18+ months
- Example: BMW CBS = 24 months → FAIL only after 36+ months

### Step 5: Update tests

Update `check_4b_service_compliance` reimplementation in test file to mirror the new logic, plus add test cases:

- Brand normalization (6 tests)
- Fuel type normalization (6 tests)
- Interval resolution per system type (7 tests)
- Full check 4b integration (12 tests covering: known/unknown brands, different fuel types, mileage compliance, chronic non-maintenance, missing data)
- Keep existing SKIPPED tests

## Evidence Structure

```json
{
  "last_service_date": "2024-06-15",
  "claim_date": "2025-06-15",
  "days_since_last_service": 365,
  "months_since_last_service": 12.0,
  "service_count": 5,
  "vehicle_make": "Volkswagen",
  "vehicle_fuel_type": "Diesel",
  "brand_key": "volkswagen",
  "fuel_key": "diesel",
  "brand_known": true,
  "fallback_interval_used": false,
  "manufacturer_interval": {
    "km_max": 15000,
    "months_max": 12,
    "system_type": "dual",
    "note": "Using fixed interval (LongLife cannot be verified)"
  },
  "time_compliance": {
    "months_gap": 12.0,
    "months_limit": 12,
    "ratio": 1.0,
    "verdict": "PASS"
  },
  "mileage_compliance": null,
  "inter_service_gaps": [...],
  "chronic_non_maintenance": false
}
```

## Confirmed Decisions

- **Fallback interval** (unknown brands): 30,000 km / 24 months, verdict auto-downgrades PASS → INCONCLUSIVE
- **Tolerance threshold**: 1.5x (PASS ≤1.0x, INCONCLUSIVE 1.0–1.5x, FAIL >1.5x)

## Verification

1. Run existing tests first: `python -m pytest tests/unit/test_nsa_screener.py -v --tb=short --no-cov`
2. Run updated tests after changes
3. Full test suite: `python -m pytest tests/unit/ --no-cov -q`
4. Manual spot-check: Run assessment on 1-2 claims and verify screening.json shows new evidence structure
