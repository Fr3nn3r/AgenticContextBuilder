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
import re
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
        self._part_number_mappings: Optional[Dict[str, Any]] = None
        self._keyword_mappings: Optional[Dict[str, Any]] = None

    @property
    def source_name(self) -> str:
        return "assumptions"

    def _load_mappings(self) -> None:
        """Load part mappings from assumptions.json (cached)."""
        if self._part_number_mappings is not None:
            return

        assumptions_path = self.workspace_path / "config" / "assumptions.json"
        if not assumptions_path.exists():
            logger.warning(f"No assumptions.json at {assumptions_path}")
            self._part_number_mappings = {}
            self._keyword_mappings = {}
            return

        try:
            with open(assumptions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            part_mapping = data.get("part_system_mapping", {})
            self._part_number_mappings = part_mapping.get("by_part_number", {})
            self._keyword_mappings = part_mapping.get("by_keyword", {})
        except Exception as e:
            logger.error(f"Failed to load part mappings: {e}")
            self._part_number_mappings = {}
            self._keyword_mappings = {}

    def lookup(self, part_number: str) -> Optional[PartLookupResult]:
        """Look up a part number in assumptions.json mappings."""
        if not part_number:
            return None

        self._load_mappings()

        # Normalize part number (remove spaces, uppercase)
        normalized = part_number.replace(" ", "").upper()

        # Try exact match first
        for stored_pn, info in self._part_number_mappings.items():
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

    def _is_whole_word_match(self, keyword: str, text: str) -> bool:
        """Check if keyword appears as a whole word in text.

        Uses word boundaries to avoid matching 'guide' inside 'guidee'.
        A word boundary is defined as: the keyword must not be immediately
        preceded or followed by a letter (to avoid partial word matches).

        Args:
            keyword: The keyword to search for
            text: The text to search in

        Returns:
            True if keyword appears as a complete word
        """
        # Escape special regex characters in keyword
        escaped_keyword = re.escape(keyword)
        # Use negative lookbehind/lookahead to ensure keyword is not part of a larger word
        # (?<![a-zA-ZÀ-ÿ]) = not preceded by a letter (including accented chars)
        # (?![a-zA-ZÀ-ÿ]) = not followed by a letter
        pattern = rf'(?<![a-zA-ZÀ-ÿ]){escaped_keyword}(?![a-zA-ZÀ-ÿ])'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def lookup_by_description(self, description: str) -> Optional[PartLookupResult]:
        """Look up a part by matching keywords in its description.

        This is a fallback when exact part number lookup fails.
        Uses the by_keyword section of assumptions.json.

        Matching rules:
        1. Keywords must match as whole words (not substrings within words)
        2. Longer keyword matches are preferred (more specific)
        3. Labor/diagnostic keywords take precedence to avoid false positives

        Args:
            description: Item description to match

        Returns:
            PartLookupResult if keyword match found, None otherwise
        """
        if not description:
            return None

        self._load_mappings()

        if not self._keyword_mappings:
            return None

        # Find all matching keywords using whole-word matching
        matches: List[tuple] = []

        for keyword, info in self._keyword_mappings.items():
            # Skip comment keys
            if keyword.startswith("_"):
                continue

            # Only match whole words to avoid false positives
            # e.g., "guide" should not match "guidee" in "fonction guidee"
            if self._is_whole_word_match(keyword, description):
                matches.append((keyword, info, len(keyword)))

        if not matches:
            return None

        # Sort matches: prefer labor/diagnostic (to exclude), then by length (longer = more specific)
        def match_priority(m):
            keyword, info, length = m
            # Labor/diagnostic items get highest priority (should be excluded from coverage)
            is_labor = info.get("system") == "labor"
            # Then prefer longer matches (more specific)
            return (is_labor, length)

        matches.sort(key=match_priority, reverse=True)
        keyword, info, _ = matches[0]

        return PartLookupResult(
            part_number=f"keyword:{keyword}",
            found=True,
            system=info.get("system"),
            component=info.get("component"),
            component_description=info.get("component_description"),
            covered=info.get("covered"),
            manufacturer=info.get("manufacturer"),
            lookup_source=f"{self.source_name}_keyword",
            note=info.get("note"),
        )


class PartNumberLookup:
    """Main part number lookup service.

    Chains multiple lookup providers and returns the first match.
    Designed for extensibility - add new providers as they become available.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self._providers: List[PartLookupProvider] = []
        self._assumptions_provider: Optional[AssumptionsLookupProvider] = None

        # Initialize default providers
        assumptions_provider = AssumptionsLookupProvider(workspace_path)
        self._providers.append(assumptions_provider)
        self._assumptions_provider = assumptions_provider

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

    def lookup_by_description(self, description: str) -> Optional[PartLookupResult]:
        """Look up a part by matching keywords in its description.

        This is a fallback when exact part number lookup fails.
        Currently only supported by AssumptionsLookupProvider.

        Args:
            description: Item description to match

        Returns:
            PartLookupResult if keyword match found, None otherwise
        """
        if not description:
            return None

        # Use assumptions provider for keyword-based lookup
        if self._assumptions_provider:
            try:
                result = self._assumptions_provider.lookup_by_description(description)
                if result and result.found:
                    logger.debug(
                        f"Description '{description[:50]}...' matched via keyword: "
                        f"system={result.system}, component={result.component}"
                    )
                    return result
            except Exception as e:
                logger.warning(f"Keyword lookup failed: {e}")

        return None
