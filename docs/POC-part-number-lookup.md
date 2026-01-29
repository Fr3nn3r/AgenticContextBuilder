# POC: Part Number Lookup for Coverage Matching

## Problem Statement

Vague descriptions like "ARRIVEE" (part F2237471) cannot be matched to coverage categories by keyword or LLM because the description doesn't indicate what the part actually is. However, the **part number** (e.g., F2237471) could be looked up to determine the actual component.

**Example from Claim 64166:**
- Part: F2237471 "ARRIVEE" (1,270 CHF)
- Our system: `review_needed` (description too vague)
- NSA approved: ✅ Covered under "Electro Deluxe" policy
- Reason: NSA adjuster knows F2237471 is a power supply module for electronic systems

## POC Goal

Create a **hardcoded mapping** of known part numbers to categories that:
1. Immediately improves accuracy for known parts
2. Is designed to be replaceable with a real lookup service later

## Implementation Plan

### Step 1: Add Part Number Mapping to assumptions.json

**File:** `workspaces/nsa/config/assumptions.json`

The structure already exists. Add Ford part F2237471 to the `by_part_number` section:

```json
"part_system_mapping": {
  "_description": "Maps part descriptions/numbers to covered systems...",
  "_lookup_order": ["part_number", "description_keyword"],

  "by_part_number": {
    "8W0616887": {"system": "suspension", "component": "height_control_valve", "covered": true},
    "G 052731A2": {"system": "consumables", "component": "hydraulic_oil", "covered": true},
    "4M0827506F": {"system": "body", "component": "trunk_lock", "covered": false, "reason": "accessory"},

    // ADD THIS - Ford SYNC power supply module
    "F2237471": {
      "system": "electric",
      "component": "power_supply_module",
      "component_description": "APIM Power Supply Module (Ford SYNC)",
      "covered": true,
      "manufacturer": "Ford",
      "note": "Power supply for infotainment/diagnostic modules - covered under electric category"
    }
  }
}
```

**Category Mapping Logic:**
- `system` must match one of the policy's `covered_categories` (e.g., "electric", "axle_drive", "brakes")
- `covered: true` means the part type is generally coverable (subject to policy having that category)
- `covered: false` means the part is explicitly excluded (e.g., accessories, wear parts)

### Step 2: Create Part Number Lookup Module

**New File:** `src/context_builder/coverage/part_number_lookup.py`

```python
"""Part number lookup for coverage matching.

This module provides part number to category mapping. Currently uses
a static lookup from assumptions.json, but is designed to be replaced
with a real parts database lookup in the future.

Integration point for future enhancement:
- Ford ETK/ETIS API
- Manufacturer parts catalogs
- Third-party parts databases (TecDoc, etc.)
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


@dataclass
class PartLookupResult:
    """Result of a part number lookup."""

    part_number: str
    found: bool
    system: Optional[str] = None  # Maps to policy category (e.g., "electric")
    component: Optional[str] = None  # Specific component type
    component_description: Optional[str] = None  # Human-readable description
    covered: Optional[bool] = None  # Whether this part type is coverable
    manufacturer: Optional[str] = None
    lookup_source: str = "unknown"  # "assumptions", "ford_etk", "tecdoc", etc.
    note: Optional[str] = None


class PartLookupProvider(Protocol):
    """Protocol for part number lookup providers.

    Implement this protocol to add new lookup sources (e.g., Ford ETK API).
    """

    def lookup(self, part_number: str) -> Optional[PartLookupResult]:
        """Look up a part number and return its category mapping."""
        ...

    @property
    def source_name(self) -> str:
        """Name of this lookup source for audit trail."""
        ...


class AssumptionsLookupProvider:
    """Part lookup from assumptions.json (static mappings).

    This is the POC implementation using hardcoded mappings.
    Replace with real API lookups in production.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._mappings: Optional[Dict[str, Any]] = None

    @property
    def source_name(self) -> str:
        return "assumptions"

    def _load_mappings(self) -> Dict[str, Any]:
        """Load part mappings from assumptions.json (cached)."""
        if self._mappings is not None:
            return self._mappings

        assumptions_path = self.workspace_path / "config" / "assumptions.json"
        if not assumptions_path.exists():
            logger.warning(f"No assumptions.json at {assumptions_path}")
            self._mappings = {}
            return self._mappings

        try:
            with open(assumptions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._mappings = data.get("part_system_mapping", {}).get("by_part_number", {})
        except Exception as e:
            logger.error(f"Failed to load part mappings: {e}")
            self._mappings = {}

        return self._mappings

    def lookup(self, part_number: str) -> Optional[PartLookupResult]:
        """Look up a part number in assumptions.json mappings."""
        if not part_number:
            return None

        mappings = self._load_mappings()

        # Normalize part number (remove spaces, uppercase)
        normalized = part_number.replace(" ", "").upper()

        # Try exact match first
        for stored_pn, info in mappings.items():
            stored_normalized = stored_pn.replace(" ", "").upper()
            if normalized == stored_normalized:
                return PartLookupResult(
                    part_number=part_number,
                    found=True,
                    system=info.get("system"),
                    component=info.get("component"),
                    component_description=info.get("component_description"),
                    covered=info.get("covered"),
                    manufacturer=info.get("manufacturer"),
                    lookup_source=self.source_name,
                    note=info.get("note"),
                )

        return PartLookupResult(
            part_number=part_number,
            found=False,
            lookup_source=self.source_name,
        )


class PartNumberLookup:
    """Main part number lookup service.

    Chains multiple lookup providers and returns the first match.
    Designed for extensibility - add new providers as they become available.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._providers: list[PartLookupProvider] = []

        # Initialize default providers
        self._providers.append(AssumptionsLookupProvider(workspace_path))

        # FUTURE: Add more providers here
        # self._providers.append(FordETKProvider(api_key=...))
        # self._providers.append(TecDocProvider(api_key=...))

    def add_provider(self, provider: PartLookupProvider) -> None:
        """Add a lookup provider to the chain."""
        self._providers.append(provider)

    def lookup(self, part_number: str) -> PartLookupResult:
        """Look up a part number using all available providers.

        Returns the first successful match, or a not-found result.
        """
        if not part_number:
            return PartLookupResult(
                part_number=part_number or "",
                found=False,
                lookup_source="none",
                note="No part number provided",
            )

        for provider in self._providers:
            try:
                result = provider.lookup(part_number)
                if result and result.found:
                    logger.debug(
                        f"Part {part_number} found via {provider.source_name}: "
                        f"system={result.system}, component={result.component}"
                    )
                    return result
            except Exception as e:
                logger.warning(f"Provider {provider.source_name} failed: {e}")
                continue

        logger.debug(f"Part {part_number} not found in any provider")
        return PartLookupResult(
            part_number=part_number,
            found=False,
            lookup_source="all_providers",
            note="Part not found in any lookup source",
        )
```

### Step 3: Integrate into Coverage Analyzer

**File:** `src/context_builder/coverage/analyzer.py`

Add part number lookup as a new stage between rules and keywords:

```python
# In CoverageAnalyzer.__init__, add:
from context_builder.coverage.part_number_lookup import PartNumberLookup

def __init__(self, ..., workspace_path: Optional[Path] = None):
    ...
    self.part_lookup = PartNumberLookup(workspace_path) if workspace_path else None

# In CoverageAnalyzer.analyze(), add after rule matching:

# Stage 1: Rule engine
rule_matched, remaining = self.rule_engine.batch_match(line_items)

# Stage 1.5: Part number lookup (NEW)
part_matched = []
still_remaining = []
if self.part_lookup:
    part_matched, still_remaining = self._match_by_part_number(
        remaining, covered_categories
    )
    remaining = still_remaining

# Stage 2: Keyword matcher (now receives items not matched by rules OR part numbers)
keyword_matched, remaining = self.keyword_matcher.batch_match(...)
```

Add the part number matching method:

```python
def _match_by_part_number(
    self,
    items: List[Dict[str, Any]],
    covered_categories: List[str],
) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
    """Match items by part number lookup.

    Args:
        items: Line items to match
        covered_categories: Categories covered by the policy

    Returns:
        Tuple of (matched items, unmatched items)
    """
    matched = []
    unmatched = []

    for item in items:
        item_code = item.get("item_code")
        if not item_code:
            unmatched.append(item)
            continue

        result = self.part_lookup.lookup(item_code)

        if not result.found:
            unmatched.append(item)
            continue

        # Check if the part's system matches a covered category
        is_covered = self._is_system_covered(result.system, covered_categories)

        if result.covered is False:
            # Part is explicitly excluded (e.g., accessory)
            status = CoverageStatus.NOT_COVERED
            reasoning = f"Part {item_code} is excluded: {result.note or result.component}"
        elif is_covered:
            status = CoverageStatus.COVERED
            reasoning = (
                f"Part {item_code} identified as '{result.component_description or result.component}' "
                f"in category '{result.system}' (lookup: {result.lookup_source})"
            )
        else:
            status = CoverageStatus.NOT_COVERED
            reasoning = (
                f"Part {item_code} is '{result.component}' in category '{result.system}' "
                f"which is not covered by this policy"
            )

        matched.append(LineItemCoverage(
            item_code=item_code,
            description=item.get("description", ""),
            item_type=item.get("item_type", ""),
            total_price=item.get("total_price", 0.0),
            coverage_status=status,
            coverage_category=result.system,
            matched_component=result.component_description or result.component,
            match_method=MatchMethod.PART_NUMBER,  # Add this to MatchMethod enum
            match_confidence=0.95,  # High confidence for part number matches
            match_reasoning=reasoning,
            covered_amount=item.get("total_price", 0.0) if status == CoverageStatus.COVERED else 0.0,
            not_covered_amount=0.0 if status == CoverageStatus.COVERED else item.get("total_price", 0.0),
        ))

    return matched, unmatched

def _is_system_covered(self, system: str, covered_categories: List[str]) -> bool:
    """Check if a system/category is covered by the policy."""
    if not system:
        return False
    system_lower = system.lower()
    for cat in covered_categories:
        if system_lower == cat.lower() or system_lower in cat.lower() or cat.lower() in system_lower:
            return True
    return False
```

### Step 4: Add MatchMethod.PART_NUMBER

**File:** `src/context_builder/coverage/schemas.py`

```python
class MatchMethod(str, Enum):
    """How a coverage match was determined."""

    RULE = "rule"
    KEYWORD = "keyword"
    PART_NUMBER = "part_number"  # ADD THIS
    LLM = "llm"
```

## Testing the POC

After implementing:

```bash
# Re-run assessment for claim 64166
python -m context_builder.cli assess --claim-id 64166

# Check coverage_analysis.json for F2237471 "ARRIVEE"
# Should now show:
# - coverage_status: "covered"
# - match_method: "part_number"
# - coverage_category: "electric"
# - match_reasoning: "Part F2237471 identified as 'APIM Power Supply Module'..."
```

## Expected Results

| Item | Before | After |
|------|--------|-------|
| F2237471 "ARRIVEE" | review_needed | **covered** (part_number match) |
| Module labor 472.07 | not_covered | not_covered (needs labor linkage - future work) |

## Future Enhancements

1. **Real Part Lookups**: Implement `FordETKProvider`, `TecDocProvider`, etc.
2. **Labor Linkage**: If a part is covered, associated labor should also be covered
3. **Caching**: Cache lookup results for performance
4. **Admin UI**: Allow adjusters to add part mappings through the UI

## File Summary

| File | Action |
|------|--------|
| `workspaces/nsa/config/assumptions.json` | Add F2237471 mapping |
| `src/context_builder/coverage/part_number_lookup.py` | Create new (lookup service) |
| `src/context_builder/coverage/analyzer.py` | Add part lookup stage |
| `src/context_builder/coverage/schemas.py` | Add PART_NUMBER to MatchMethod |
