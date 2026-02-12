"""Keyword matcher for German automotive terms to policy categories.

The keyword matcher maps German automotive repair terms to policy coverage
categories using configurable keyword mappings. It uses context hints to
improve matching accuracy (e.g., VENTIL + HYDRAULIK -> chassis).

Confidence levels:
- Exact keyword match: 0.85-0.90
- Partial/context match: 0.70-0.85
- Ambiguous match: 0.60-0.70 (may still trigger LLM fallback)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    DecisionSource,
    LineItemCoverage,
    MatchMethod,
    TraceAction,
)
from context_builder.coverage.trace import TraceBuilder

logger = logging.getLogger(__name__)


@dataclass
class KeywordMapping:
    """A mapping from keywords to a policy category."""

    category: str  # Policy category (e.g., "engine", "chassis")
    keywords: List[str]  # German keywords that map to this category
    context_hints: List[str] = field(default_factory=list)  # Contextual modifiers
    confidence: float = 0.85  # Base confidence for this mapping
    component_name: Optional[str] = None  # Specific component if known


@dataclass
class KeywordConfig:
    """Configuration for keyword matcher."""

    mappings: List[KeywordMapping]
    min_confidence_threshold: float = 0.70
    labor_coverage_categories: List[str] = field(default_factory=list)
    consumable_indicators: List[str] = field(default_factory=list)

    # Multiplier applied to confidence when a consumable indicator is
    # found alongside a component keyword (e.g. gasket + engine).
    consumable_confidence_penalty: float = 0.7

    # Additive boost applied to confidence when a context hint matches
    # in addition to the primary keyword.
    context_confidence_boost: float = 0.05

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "KeywordConfig":
        """Create config from dictionary (loaded from YAML)."""
        mappings = []
        for mapping in config.get("mappings", []):
            mappings.append(
                KeywordMapping(
                    category=mapping["category"],
                    keywords=mapping["keywords"],
                    context_hints=mapping.get("context_hints", []),
                    confidence=mapping.get("confidence", 0.85),
                    component_name=mapping.get("component_name"),
                )
            )
        return cls(
            mappings=mappings,
            min_confidence_threshold=config.get("min_confidence_threshold", 0.70),
            labor_coverage_categories=config.get("labor_coverage_categories", []),
            consumable_indicators=config.get("consumable_indicators", []),
            consumable_confidence_penalty=config.get("consumable_confidence_penalty", 0.7),
            context_confidence_boost=config.get("context_confidence_boost", 0.05),
        )


class KeywordMatcher:
    """German keyword-based coverage matching.

    The keyword matcher is the second matcher in the coverage analysis pipeline,
    handling items that passed through the rule engine. It maps German automotive
    terms to policy coverage categories.
    """

    def __init__(self, config: Optional[KeywordConfig] = None):
        """Initialize the keyword matcher.

        Args:
            config: Keyword configuration. Uses empty config if not provided.
        """
        if not (config and config.mappings):
            logger.warning("No keyword mappings provided, matcher will not match any items")
            self.config = KeywordConfig(mappings=[])
        else:
            self.config = config

        # Build lookup structures for fast matching
        self._build_lookup_tables()

    def _build_lookup_tables(self) -> None:
        """Build keyword lookup tables for efficient matching."""
        self._keyword_to_mapping: Dict[str, KeywordMapping] = {}
        self._context_hints: Dict[str, Set[str]] = {}

        for mapping in self.config.mappings:
            for keyword in mapping.keywords:
                # Store uppercase for case-insensitive matching
                self._keyword_to_mapping[keyword.upper()] = mapping

            # Build context hint lookup
            for hint in mapping.context_hints:
                hint_upper = hint.upper()
                if hint_upper not in self._context_hints:
                    self._context_hints[hint_upper] = set()
                self._context_hints[hint_upper].add(mapping.category)

    def match(
        self,
        description: str,
        item_type: str,
        item_code: Optional[str] = None,
        total_price: float = 0.0,
        covered_categories: Optional[List[str]] = None,
    ) -> Optional[LineItemCoverage]:
        """Attempt to match a line item using keyword mappings.

        Args:
            description: Item description (usually in German)
            item_type: Item type (parts, labor, fee)
            item_code: Optional item code
            total_price: Item total price
            covered_categories: List of categories covered by the policy

        Returns:
            LineItemCoverage if matched by keywords, None otherwise
        """
        covered_categories = covered_categories or []
        description_upper = description.upper()

        # Find all matching keywords in the description
        matches: List[Tuple[str, KeywordMapping, float]] = []

        for keyword, mapping in self._keyword_to_mapping.items():
            if keyword in description_upper:
                # Base confidence from mapping
                confidence = mapping.confidence

                # Boost confidence if context hints match
                for hint in mapping.context_hints:
                    if hint.upper() in description_upper:
                        confidence = min(0.95, confidence + self.config.context_confidence_boost)
                        break

                matches.append((keyword, mapping, confidence))

        if not matches:
            return None

        # Select the best match (highest confidence)
        matches.sort(key=lambda x: x[2], reverse=True)
        keyword, best_mapping, confidence = matches[0]

        # Reduce confidence when description contains consumable terms
        # (gasket, seal, boot) alongside a component keyword.
        # These items need LLM judgment to determine if the item IS
        # the component or is a consumable FOR the component.
        for indicator in self.config.consumable_indicators:
            if indicator.upper() in description_upper:
                confidence *= self.config.consumable_confidence_penalty
                logger.debug(
                    f"Consumable indicator '{indicator}' found in '{description}', "
                    f"reduced confidence to {confidence:.2f}"
                )
                break

        # Check if the category is covered by policy
        category = best_mapping.category
        is_covered = self._is_category_covered(category, covered_categories)

        # Labor items may be covered if they relate to covered components
        if item_type.lower() == "labor":
            # Labor is covered if working on covered components
            if category in self.config.labor_coverage_categories and is_covered:
                pass  # Keep as covered
            else:
                # Labor for non-covered categories
                confidence *= 0.9  # Reduce confidence

        # Check if consumable penalty was applied
        consumable_penalty = confidence != matches[0][2]

        # Build trace step
        tb = TraceBuilder()
        trace_detail = {
            "keyword": keyword,
            "category": category,
            "base_confidence": matches[0][2],
        }
        if consumable_penalty:
            trace_detail["consumable_penalty"] = True

        if is_covered:
            tb.add("keyword", TraceAction.MATCHED,
                   f"Keyword '{keyword}' maps to covered category '{category}'",
                   verdict=CoverageStatus.COVERED, confidence=confidence,
                   detail=trace_detail,
                   decision_source=DecisionSource.KEYWORD)
            return LineItemCoverage(
                item_code=item_code,
                description=description,
                item_type=item_type,
                total_price=total_price,
                coverage_status=CoverageStatus.COVERED,
                coverage_category=category,
                matched_component=best_mapping.component_name,
                match_method=MatchMethod.KEYWORD,
                match_confidence=confidence,
                match_reasoning=f"Keyword '{keyword}' maps to covered category '{category}'",
                decision_trace=tb.build(),
                covered_amount=total_price,
                not_covered_amount=0.0,
            )
        else:
            tb.add("keyword", TraceAction.MATCHED,
                   f"Keyword '{keyword}' maps to category '{category}' which is not covered",
                   verdict=CoverageStatus.NOT_COVERED, confidence=confidence,
                   detail=trace_detail,
                   decision_source=DecisionSource.KEYWORD)
            return LineItemCoverage(
                item_code=item_code,
                description=description,
                item_type=item_type,
                total_price=total_price,
                coverage_status=CoverageStatus.NOT_COVERED,
                coverage_category=category,
                matched_component=best_mapping.component_name,
                match_method=MatchMethod.KEYWORD,
                match_confidence=confidence,
                match_reasoning=f"Keyword '{keyword}' maps to category '{category}' which is not covered",
                exclusion_reason="category_not_covered",
                decision_trace=tb.build(),
                covered_amount=0.0,
                not_covered_amount=total_price,
            )

    def _is_category_covered(
        self, category: str, covered_categories: List[str]
    ) -> bool:
        """Check if a category is covered by the policy.

        Args:
            category: Category name (e.g., "engine", "chassis")
            covered_categories: List of categories from policy

        Returns:
            True if the category is covered
        """
        # Normalize category names for comparison
        category_lower = category.lower().replace("_", " ")
        for covered in covered_categories:
            covered_lower = covered.lower().replace("_", " ")
            if category_lower == covered_lower:
                return True
            # Handle variations
            if category_lower in covered_lower or covered_lower in category_lower:
                return True
        return False

    def batch_match(
        self,
        items: List[Dict[str, Any]],
        covered_categories: Optional[List[str]] = None,
        min_confidence: Optional[float] = None,
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Match multiple items, returning matched and unmatched lists.

        Args:
            items: List of line item dictionaries
            covered_categories: List of categories from policy
            min_confidence: Minimum confidence to accept match (defaults to config)

        Returns:
            Tuple of (matched items, unmatched items for LLM processing)
        """
        min_conf = min_confidence or self.config.min_confidence_threshold
        matched = []
        unmatched = []

        for item in items:
            result = self.match(
                description=item.get("description", ""),
                item_type=item.get("item_type", ""),
                item_code=item.get("item_code"),
                total_price=item.get("total_price") or 0.0,
                covered_categories=covered_categories,
            )

            if result and result.match_confidence >= min_conf:
                matched.append(result)
            else:
                unmatched.append(item)

        logger.debug(
            f"Keyword matcher: {len(matched)} matched, {len(unmatched)} unmatched"
        )
        return matched, unmatched
