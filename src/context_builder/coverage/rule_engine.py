"""Rule engine for deterministic coverage matching.

The rule engine provides fast, high-confidence (1.0) matching for line items
that can be definitively categorized without semantic analysis.

Rules are applied in order:
1. Fee items -> NOT_COVERED
2. Exclusion patterns (known non-covered items) -> NOT_COVERED
3. Consumable patterns (if configured) -> NOT_COVERED
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
)

logger = logging.getLogger(__name__)


@dataclass
class RuleConfig:
    """Configuration for the rule engine."""

    # Fee items are always not covered
    fee_item_types: List[str]

    # Patterns that indicate exclusion (case-insensitive regex)
    exclusion_patterns: List[str]

    # Patterns for consumables (oil, filters, etc.) - not covered
    consumable_patterns: List[str]

    # Patterns that indicate labor for non-covered items
    non_covered_labor_patterns: List[str]

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "RuleConfig":
        """Create config from dictionary."""
        return cls(
            fee_item_types=config.get("fee_item_types", ["fee"]),
            exclusion_patterns=config.get("exclusion_patterns", []),
            consumable_patterns=config.get("consumable_patterns", []),
            non_covered_labor_patterns=config.get("non_covered_labor_patterns", []),
        )

    @classmethod
    def default(cls) -> "RuleConfig":
        """Create default NSA config."""
        return cls(
            fee_item_types=["fee"],
            exclusion_patterns=[
                r"ENTSORGUNG",  # Disposal fees
                r"UMWELT",  # Environmental fees
                r"ERSATZFAHRZEUG",  # Rental car
                r"MIETE",  # Rental
                r"REINIGUNG",  # Cleaning
                r"BRONZE",  # Bronze service (warranty-related cleaning)
            ],
            consumable_patterns=[
                r"MOTOROEL|MOTORÖL|ENGINE OIL",  # Engine oil
                r"OELFILTER|ÖLFILTER|OIL FILTER",  # Oil filters
                r"LUFTFILTER|AIR FILTER",  # Air filters
                r"BREMSFLÜSSIGKEIT|BRAKE FLUID",  # Brake fluid
                r"KÜHLMITTEL|COOLANT",  # Coolant
                r"SCHEIBENWISCHERBLÄTTER|WIPER BLADES",  # Wiper blades
            ],
            non_covered_labor_patterns=[
                r"DIAGNOSE",  # Diagnostic work
                r"KONTROLLE",  # Inspection/control
                r"PRÜFUNG",  # Testing
            ],
        )


class RuleEngine:
    """Fast, deterministic rule-based coverage matching.

    The rule engine is the first matcher in the coverage analysis pipeline.
    It handles clear-cut cases with 100% confidence, reducing the number
    of items that need keyword or LLM analysis.
    """

    def __init__(self, config: Optional[RuleConfig] = None):
        """Initialize the rule engine.

        Args:
            config: Rule configuration. Uses defaults if not provided.
        """
        self.config = config or RuleConfig.default()

        # Pre-compile regex patterns for performance
        self._exclusion_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.exclusion_patterns
        ]
        self._consumable_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.consumable_patterns
        ]
        self._non_covered_labor_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.non_covered_labor_patterns
        ]

    def match(
        self,
        description: str,
        item_type: str,
        item_code: Optional[str] = None,
        total_price: float = 0.0,
        skip_consumable_check: bool = False,
        repair_context_component: Optional[str] = None,
    ) -> Optional[LineItemCoverage]:
        """Attempt to match a line item using rules.

        Args:
            description: Item description (usually in German)
            item_type: Item type (parts, labor, fee)
            item_code: Optional item code
            total_price: Item total price
            skip_consumable_check: If True, skip consumable pattern matching
                (used when repair context indicates a covered component)
            repair_context_component: The component from repair context (for logging)

        Returns:
            LineItemCoverage if matched by a rule, None otherwise
        """
        # Rule 1: Fee items are never covered
        if item_type.lower() in [t.lower() for t in self.config.fee_item_types]:
            return self._create_not_covered(
                description=description,
                item_type=item_type,
                item_code=item_code,
                total_price=total_price,
                reasoning=f"Fee items ({item_type}) are not covered by policy",
            )

        # Rule 2: Check exclusion patterns
        for pattern in self._exclusion_patterns:
            if pattern.search(description):
                return self._create_not_covered(
                    description=description,
                    item_type=item_type,
                    item_code=item_code,
                    total_price=total_price,
                    reasoning=f"Item matches exclusion pattern: {pattern.pattern}",
                )

        # Rule 3: Check consumable patterns (parts only)
        # Skip if repair context indicates a covered component
        if item_type.lower() == "parts" and not skip_consumable_check:
            for pattern in self._consumable_patterns:
                if pattern.search(description):
                    return self._create_not_covered(
                        description=description,
                        item_type=item_type,
                        item_code=item_code,
                        total_price=total_price,
                        reasoning=f"Consumable item not covered: {pattern.pattern}",
                    )
        elif item_type.lower() == "parts" and skip_consumable_check:
            # Log that we skipped consumable check due to repair context
            for pattern in self._consumable_patterns:
                if pattern.search(description):
                    logger.info(
                        f"Skipped consumable exclusion for '{description}' - "
                        f"repair context indicates '{repair_context_component}' (covered)"
                    )
                    break

        # Rule 4: Zero-price items (labor) - likely complimentary, skip coverage
        if total_price == 0.0:
            return LineItemCoverage(
                item_code=item_code,
                description=description,
                item_type=item_type,
                total_price=total_price,
                coverage_status=CoverageStatus.COVERED,
                coverage_category=None,
                matched_component=None,
                match_method=MatchMethod.RULE,
                match_confidence=1.0,
                match_reasoning="Zero-price item - no coverage calculation needed",
                covered_amount=0.0,
                not_covered_amount=0.0,
            )

        # No rule matched
        return None

    def _create_not_covered(
        self,
        description: str,
        item_type: str,
        item_code: Optional[str],
        total_price: float,
        reasoning: str,
    ) -> LineItemCoverage:
        """Create a NOT_COVERED result."""
        return LineItemCoverage(
            item_code=item_code,
            description=description,
            item_type=item_type,
            total_price=total_price,
            coverage_status=CoverageStatus.NOT_COVERED,
            coverage_category=None,
            matched_component=None,
            match_method=MatchMethod.RULE,
            match_confidence=1.0,
            match_reasoning=reasoning,
            covered_amount=0.0,
            not_covered_amount=total_price,
        )

    def batch_match(
        self,
        items: List[Dict[str, Any]],
        skip_consumable_check: bool = False,
        repair_context_component: Optional[str] = None,
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Match multiple items, returning matched and unmatched lists.

        Args:
            items: List of line item dictionaries with description, item_type, etc.
            skip_consumable_check: If True, skip consumable pattern matching for parts
                (used when repair context indicates a covered component)
            repair_context_component: The component from repair context (for logging)

        Returns:
            Tuple of (matched items, unmatched items for further processing)
        """
        matched = []
        unmatched = []

        for item in items:
            result = self.match(
                description=item.get("description", ""),
                item_type=item.get("item_type", ""),
                item_code=item.get("item_code"),
                total_price=item.get("total_price") or 0.0,
                skip_consumable_check=skip_consumable_check,
                repair_context_component=repair_context_component,
            )
            if result:
                matched.append(result)
            else:
                unmatched.append(item)

        logger.debug(
            f"Rule engine: {len(matched)} matched, {len(unmatched)} unmatched"
        )
        return matched, unmatched
