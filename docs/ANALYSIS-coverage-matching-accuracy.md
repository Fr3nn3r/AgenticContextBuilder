# Coverage Matching Accuracy Analysis

**Date**: 2026-02-11
**Dataset**: Latest eval run `clm_20260211_105352_c56208` (54 claims, 603 line items)

## Executive Summary

Only 34% of line items are resolved deterministically (rules + part_number + keyword) while 49% go to LLM -- but analysis shows only 23% truly need LLM. That is a 26-percentage-point gap representing wasted LLM calls, lower confidence, and non-deterministic behavior.

Two fixes were already committed:
- **Normalization bug** (`part_number_lookup.py`): dashes/dots now stripped during comparison
- **14 component synonyms** added to `nsa_component_config.yaml` to close synonym gap

This document covers the broader analysis and roadmap for reducing LLM dependency further.

---

## 1. Current Match Method Distribution

| Method | Items | % | Avg Confidence | Role |
|--------|------:|--:|---------------:|------|
| Rule | 185 | 30.7% | 0.86 | Deterministic exclusions |
| Part Number | 103 | 17.1% | 0.95 | Exact part lookup + description keyword |
| Keyword | 20 | 3.3% | 0.85 | German/French term matching |
| LLM | 295 | 48.9% | 0.83 | GPT-4o fallback |

### Evolution Over Time

| Date | Rule % | Part# % | Keyword % | LLM % |
|------|-------:|--------:|----------:|------:|
| Jan 29 | 9.1 | 0.0 | 0.0 | 90.9 |
| Jan 30 | 25.6 | 9.0 | 4.1 | 61.3 |
| Feb 01 | 26.5 | 17.7 | 3.4 | 52.4 |
| Feb 10 | 30.7 | 17.1 | 3.3 | 48.9 |

---

## 2. Parts Lookup Impact Analysis

### 2.1 Current State

The parts lookup table (`assumptions.json`) contains:
- **168 part numbers** in `by_part_number` (engine parts dominate at 41%)
- **131 keywords** in `by_keyword`

Part number matching resolves 17.1% of items at 0.95 confidence (deterministic, same result every run).

### 2.2 Leaked Items Analysis

33 items that exist in the part_number table were being resolved by LLM instead ("leaks"). Root causes:

| Leak Path | Items | Fix |
|-----------|------:|-----|
| Space/dash normalization mismatch | ~15-20 | **FIXED** -- `_normalize_part_number()` now strips spaces, dashes, dots, slashes |
| Synonym gap (component not in policy list) | ~8-10 | **FIXED** -- 14 synonym entries added |
| Ancillary category deferral (consumables/labor) | ~14 | By design -- conservative, keep as-is |

### 2.3 Accuracy Comparison: Part Lookup vs LLM

Of the 33 leaked items:
- **22 (67%)** -- LLM agreed with what the table would have said (wasted LLM call)
- **10 (30%)** -- LLM disagreed (potential decision error)
- **1 (3%)** -- ambiguous

Of the 10 disagreements, **9 were false denials** -- the LLM said NOT_COVERED for parts the table correctly identifies as covered:

| Claim | Part | Table Says | LLM Said | LLM Conf |
|-------|------|-----------|----------|------:|
| 65113 | Druckleitung DMDC/RDC (x4) | engine/fuel_line -> covered | not_covered | 0.70 |
| 64354 | ARRETIERUNG | auto_transmission/locking_mechanism -> covered | not_covered | 0.80 |
| 64535 | Couvercle (oil sep cover) | engine/oil_separator_cover -> covered | not_covered | 0.70 |
| 64818 | VERBINDER | electrical/connector -> covered | not_covered | 0.85 |
| 64980 | FILT. HUIL AUTOM | auto_transmission/oil_filter -> covered | not_covered | 0.90 |
| 65056 | ROHR | auto_transmission/pipe -> covered | not_covered | 0.50 |

**Key insight**: The LLM is systematically too conservative on German/French part descriptions it is unsure about, defaulting to "not covered."

### 2.4 Blast Radius of Removing Parts Lookup

If parts lookup were removed entirely:
- 103 items would fall to keyword/LLM
- ~31 items (30%) would likely get wrong decisions (false denials)
- 5-9 additional claims would have incorrect coverage determinations
- Payout amounts would systematically underestimate on affected claims
- CCI scores would drop (0.83 avg vs 0.95 deterministic)

**Conclusion**: Parts lookup is high-value. Removing it would hurt accuracy significantly. Expanding it (more part numbers, better normalization) is the better direction.

---

## 3. Why Keyword Matching Only Catches 3.3%

### 3.1 Two Parallel Keyword Systems

The system has two independent keyword matchers that evolved separately:

| System | Location | Entries | Runs In |
|--------|----------|--------:|---------|
| `by_keyword` | `assumptions.json` | 131 | Stage 1.5 (`lookup_by_description`) |
| Keyword mappings | `nsa_keyword_mappings.yaml` | 176 | Stage 2 (`KeywordMatcher.batch_match`) |

55 keywords overlap between the two systems. 7 map to different categories.

### 3.2 Compounding Leak Paths

Six factors compound to starve Stage 2:

1. **Stage 1.5 consumes keyword-matchable items first** -- `lookup_by_description` runs 131 keywords before Stage 2 sees anything
2. **Stage 1.5 deferrals skip Stage 2** -- items deferred from Stage 1.5 go directly to LLM (Stage 3), never reaching Stage 2
3. **Stage 1 (rules) strips items containing keywords** -- e.g., "DIAGNOSE MOTOR" caught by DIAGNOSE labor rule before MOTOR keyword can match
4. **Confidence threshold filters** -- gasket/seal indicators (JOINT, DICHTUNG) reduce confidence by 0.7x, dropping below the 0.80 threshold
5. **Stage 2.5 demotes matches back to LLM** -- if `_is_component_in_policy_list` returns None or False, keyword matches are clawed back
6. **Category conflicts** -- 7 keywords map to different categories between the two systems

### 3.3 Example Flow

Item: `"TURBOLADER ERSETZEN"` (replace turbocharger)
1. Stage 1 (Rules): no match, passes through
2. Stage 1.5: `lookup_by_description` matches `turbo` from `by_keyword` -> system=engine, component=turbocharger
3. Checks policy list -> resolves or defers to LLM
4. **Stage 2 never sees this item**

---

## 4. What the 295 LLM Items Actually Are

| Category | Items | % of LLM | CHF Value | Rule-Replaceable? |
|----------|------:|----------:|----------:|:-:|
| Install/remove labor | 62 | 21.0% | 10,572 | Partially |
| Seals/gaskets/O-rings | 41 | 13.9% | 1,228 | YES |
| Diagnostic labor | 37 | 12.5% | 3,611 | YES |
| Fasteners/hardware | 36 | 12.2% | 1,228 | YES |
| Fluids/oils | 32 | 10.8% | 5,247 | YES |
| Consumables/misc | 7 | 2.4% | 188 | YES |
| Filters | 5 | 1.7% | 872 | YES (with care) |
| Cleaning labor | 5 | 1.7% | 540 | YES |
| Generic labor | 3 | 1.0% | 1,359 | YES |
| **Genuinely ambiguous** | **67** | **22.7%** | **20,692** | **NO** |

**56% of LLM items (166/295) could be fully handled by deterministic rules.**
Only 23% genuinely need LLM semantic understanding.

---

## 5. Improvement Roadmap

### Tier 1: Config-Only Changes (high impact, zero code risk)

All changes in `nsa_coverage_config.yaml` (customer config).

#### A. Expand Consumable Patterns -- catches ~32 fluid/oil items

Currently only matches `MOTOROEL`, `OELFILTER`, etc. Missing common variants:

```yaml
# Proposed additions to consumable_patterns:
- \bOEL\b|OEL\s\d        # Standalone oil (e.g., "OEL 1 L") -- with component override for PUMPE/KUEHLER
- \bHUILE\b               # French: standalone oil
- FROSTSCHUTZ             # Antifreeze
- HYDRAULIKOEL|HYDRAULIK.?OEL
- ANTIGEL                 # French: antifreeze
- \bLIQUIDE\b             # French: liquid (coolant, brake fluid)
- VIDANGE                 # French: oil change/drain
- KRAFTSTOFFFILTER|FILTRE.*CARBURANT|FUEL FILTER
- POLLENFILTER|INNENRAUMFILTER|FILTRE.*HABITACLE|CABIN FILTER
- ZUENDKERZE|BOUGIE       # Spark plugs (wear item)
```

#### B. Expand Non-Covered Labor Patterns -- catches ~37 diagnostic items

```yaml
# Proposed additions to non_covered_labor_patterns:
- KURZTEST                              # Short test (DE)
- PRUEFEN|PRUFEN                        # Test/check -- umlaut-less variants
- GEFUEHRTE.?FUNKTION                   # Guided function (spelled out GFS)
- SOFTWAREUPDATE                        # Software update
- BATTERIE.*GELADEN|BATTERIE.*LADEN|CHARG.*BATTERIE  # Battery charging
- LAVAGE|NETTOYAGE                      # Cleaning/washing (FR)
- PROBEFAHRT|ESSAI.*ROUTE               # Test drive
- ENDKONTROLLE|CONTR[OO]LE.*FINAL      # Final inspection
- ACHSVERMESSUNG|G[EE]OM[EE]TRIE       # Wheel alignment
- WAGENWAESCHE                          # Car wash (DE)
- AUSLEUCHTEN                           # Bore inspection
- FAHRZEUGTEST                          # Vehicle test
```

#### C. Add French Exclusion Patterns

```yaml
# Proposed additions to exclusion_patterns:
- LOCATION                          # Rental (FR for MIETE)
- NETTOYAGE                         # Cleaning (FR for REINIGUNG)
- ELIMINATION|EVACUATION            # Disposal (FR for ENTSORGUNG)
- ENVIRONNEMENT                     # Environmental (FR for UMWELT)
- V[EE]HICULE.*REMPLACEMENT        # Replacement vehicle (FR for ERSATZFAHRZEUG)
```

#### D. Fix Fastener Pattern Anchoring -- catches ~36 items

Current patterns use `^SCHRAUBE$` which misses compounds like `ZYLINDERKOPFSCHRAUBE`.

Options:
1. Remove anchoring, use substring match (broader, may need override list)
2. Add compound forms explicitly:

```yaml
# Proposed additions to fastener_patterns:
- .*SCHRAUBE$             # Any compound ending in -SCHRAUBE
- .*MUTTER$               # Any compound ending in -MUTTER
- HALTEFEDER              # Retaining spring
- CIRCLIP|CIRCLIPS        # Circlips
- AGRAFFE|AGRAFE          # Staple/clip (FR)
- RONDELLE                # Washer (FR)
- UNTERLEGSCHEIBE         # Washer (DE)
- SPLINT                  # Split pin (DE)
- NIETE|RIVET             # Rivet
- KLAMMER|CLIP            # Clamp/clip
```

### Tier 2: New Rule Categories (small code + config)

#### E. Seals/Gaskets Rule -- catches ~41 items

Standalone `DICHTUNG`, `JOINT`, `O-RING` items are ancillary parts. Options:

- **Conservative** (recommended for current iteration): Mark as REVIEW_NEEDED like fasteners -- context-dependent (a gasket supporting a covered repair should be covered)
- **Simple**: Mark as NOT_COVERED

```yaml
# Proposed new section in rules:
seal_gasket_patterns:   # -> REVIEW_NEEDED
  - "^DICHTUNG$|^JOINT$|^O-RING$|^DICHTRING$"
  - "^PROFILDICHTUNG$|^FLANSCHDICHTUNG$"
  - "^SATZ DICHTUNGEN$|^JEU DE JOINTS$"
```

#### F. Wear-and-Tear Rule -- catches brake pads, clutch discs, etc.

The LLM prompt explicitly says these are NOT COVERED. Should be deterministic:

```yaml
# Proposed new section in rules:
wear_part_patterns:     # -> NOT_COVERED
  - BREMSBELAG|PLAQUETTE.*FREIN|BRAKE PAD
  - KUPPLUNGSSCHEIBE|DISQUE.*EMBRAYAGE|CLUTCH DISC
  - BREMSSCHEIBE|DISQUE.*FREIN|BRAKE DISC
```

### Tier 3: Architecture Improvements (bigger changes, highest long-term value)

#### G. Unify Keyword Systems or Fix Deferral Path

**Option A (merge)**: Move all `by_keyword` entries into `nsa_keyword_mappings.yaml`. Stage 1.5 becomes pure part-number lookup, Stage 2 handles all keywords.

**Option B (fix deferral, less disruptive)**: When Stage 1.5 defers an item, route it to Stage 2 (keyword matcher) instead of directly to LLM.

#### H. Two-Step Labor Matching

For items like `WINKELGETRIEBE AUS- U.EINBAUEN`:
1. Detect the action verb pattern (AUS-/EINBAUEN, DEPOSE/REPOSE, REMPLACEMENT)
2. Extract the component noun and match against existing keyword/synonym dictionaries
3. If the component is covered, the labor is covered -- no LLM needed

---

## 6. Projected Impact

| Scenario | Rule % | Part# % | Keyword % | LLM % |
|----------|-------:|--------:|----------:|------:|
| **Current** | 30.7 | 17.1 | 3.3 | 48.9 |
| **After Tier 1** (config only) | 48-52 | 17.1 | 3.3 | ~28-32 |
| **After Tier 1+2** (+new rules) | 55-58 | 17.1 | 3.3 | ~21-25 |
| **After Tier 1+2+3** (+architecture) | 55-58 | 17.1 | 8-12 | ~13-17 |

Tier 1 alone would cut LLM calls nearly in half. All tiers combined could bring LLM dependency down to ~15% -- close to the theoretical minimum.

---

## 7. Fixes Already Applied (2026-02-11)

### Normalization Bug Fix

**File**: `src/context_builder/coverage/part_number_lookup.py`
**Commit**: `c47c24f` (main repo)

Added `_normalize_part_number()` that strips spaces, dashes, dots, and slashes before comparison. Previously only spaces were stripped, causing mismatches for part numbers like `2S6Q-6K682-AF`.

### Component Synonym Expansion

**File**: `workspaces/nsa/config/coverage/nsa_component_config.yaml`
**Commit**: `c9c07db` (customer repo)

Added 14 synonym entries: `fuel_line`, `oil_jet`, `gear_selector_actuator`, `locking_mechanism`, `transmission_cover`, `sliding_sleeve`, `oil_filter`, `oil_separator_cover`, `connector`, `camshaft_kit`, `exhaust_clamp`, `trunk_lock`, `haldex_fluid`, `pipe`.

Expected to close the synonym gap for ~19 of the 33 leaked items.

---

## Appendix A: Existing Config Reference

### Rule Engine Patterns (`nsa_coverage_config.yaml`)

| Rule | Patterns | Language Coverage |
|------|------:|---|
| Exclusion | 9 | DE (8), FR (1) |
| Consumable | 10 | DE (8), EN (2) |
| Component override | 4 | DE/EN |
| Generic description | 6 | DE (3), FR (1), EN (1) |
| Fastener | 10 | DE (6), FR (4) |
| Non-covered labor | 17 | DE (10), FR (7) |
| **Total** | **56** | **French significantly underrepresented** |

### Keyword Mappings (`nsa_keyword_mappings.yaml`)

176 keywords mapping German/French automotive terms to coverage categories. Overlaps with 55 of the 131 `by_keyword` entries in `assumptions.json`.

### Component Synonyms (`nsa_component_config.yaml`)

~84 component types with multilingual synonyms (DE/FR/EN). Used by `_is_component_in_policy_list()` to verify part-number and keyword matches against the specific policy's covered components list.

### Assumptions Part Database (`assumptions.json`)

168 part numbers + 131 keywords. Engine parts dominate (41%). No entries have explicit `covered: false` flag -- exclusion notes are advisory only.
