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
from typing import Any, Dict, List, Optional, Protocol

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
            # Skip comment keys
            if stored_pn.startswith("_"):
                continue

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
        self._providers: List[PartLookupProvider] = []

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
