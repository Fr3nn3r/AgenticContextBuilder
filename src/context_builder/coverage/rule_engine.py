"""Rule engine for deterministic coverage matching.

The rule engine provides fast, high-confidence (1.0) matching for line items
that can be definitively categorized without semantic analysis.

Rules are applied in order:
1. Fee items -> NOT_COVERED
2. Exclusion patterns (known non-covered items) -> NOT_COVERED
3. Consumable patterns (if configured) -> NOT_COVERED
4. Zero-price items -> COVERED
5. Non-covered labor patterns (labor only) -> NOT_COVERED
6. Generic/empty descriptions -> NOT_COVERED
7. Standalone fastener items -> REVIEW_NEEDED
7.5. Standalone seal/gasket items -> REVIEW_NEEDED
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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

    # Patterns that override consumable detection (indicates a component, not a consumable)
    # Example: "Kühlmittelpumpe" contains KÜHLMITTEL but is a pump.
    component_override_patterns: List[str]

    # Rule 6: Generic/empty descriptions with no semantic content
    generic_description_patterns: List[str]

    # Rule 7: Standalone fastener items (screws, nuts, bolts)
    fastener_patterns: List[str]

    # Rule 7.5: Standalone seal/gasket items (DICHTUNG, O-RING, etc.)
    seal_gasket_standalone_patterns: List[str]

    # Confidence assigned to REVIEW_NEEDED items (fasteners, seals).
    review_needed_confidence: float = 0.45

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "RuleConfig":
        """Create config from dictionary."""
        return cls(
            fee_item_types=config.get("fee_item_types", ["fee"]),
            exclusion_patterns=config.get("exclusion_patterns", []),
            consumable_patterns=config.get("consumable_patterns", []),
            non_covered_labor_patterns=config.get("non_covered_labor_patterns", []),
            component_override_patterns=config.get("component_override_patterns", []),
            generic_description_patterns=config.get("generic_description_patterns", []),
            fastener_patterns=config.get("fastener_patterns", []),
            seal_gasket_standalone_patterns=config.get("seal_gasket_standalone_patterns", []),
            review_needed_confidence=config.get("review_needed_confidence", 0.45),
        )

    @classmethod
    def default(cls) -> "RuleConfig":
        """Create empty default config (no customer-specific patterns)."""
        return cls(
            fee_item_types=["fee"],
            exclusion_patterns=[],
            consumable_patterns=[],
            non_covered_labor_patterns=[],
            component_override_patterns=[],
            generic_description_patterns=[],
            fastener_patterns=[],
            seal_gasket_standalone_patterns=[],
            review_needed_confidence=0.45,
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
        self._component_override_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.config.component_override_patterns
        ]

        # Build combined generic description pattern (anchored ^...$)
        if self.config.generic_description_patterns:
            joined = "|".join(self.config.generic_description_patterns)
            self._generic_description_pattern = re.compile(
                f"^({joined})$", re.IGNORECASE
            )
        else:
            self._generic_description_pattern = None

        # Build combined fastener pattern (anchored ^...$)
        if self.config.fastener_patterns:
            joined = "|".join(self.config.fastener_patterns)
            self._fastener_pattern = re.compile(
                f"^({joined})$", re.IGNORECASE
            )
        else:
            self._fastener_pattern = None

        # Build combined seal/gasket standalone pattern (anchored ^...$)
        if self.config.seal_gasket_standalone_patterns:
            joined = "|".join(self.config.seal_gasket_standalone_patterns)
            self._seal_gasket_pattern = re.compile(
                f"^({joined})$", re.IGNORECASE
            )
        else:
            self._seal_gasket_pattern = None

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
        tb = TraceBuilder()

        # Rule 1: Fee items are never covered
        if item_type.lower() in [t.lower() for t in self.config.fee_item_types]:
            tb.add("rule_engine", TraceAction.EXCLUDED,
                   f"Fee items ({item_type}) are not covered by policy",
                   verdict=CoverageStatus.NOT_COVERED, confidence=1.0,
                   detail={"rule": "fee_item", "item_type": item_type},
                   decision_source=DecisionSource.RULE)
            return self._create_not_covered(
                description=description,
                item_type=item_type,
                item_code=item_code,
                total_price=total_price,
                reasoning=f"Fee items ({item_type}) are not covered by policy",
                exclusion_reason="fee",
                trace=tb.build(),
            )

        # Rule 2: Check exclusion patterns
        for pattern in self._exclusion_patterns:
            if pattern.search(description):
                tb.add("rule_engine", TraceAction.EXCLUDED,
                       f"Item matches exclusion pattern: {pattern.pattern}",
                       verdict=CoverageStatus.NOT_COVERED, confidence=1.0,
                       detail={"rule": "exclusion_pattern", "pattern": pattern.pattern},
                       decision_source=DecisionSource.RULE)
                return self._create_not_covered(
                    description=description,
                    item_type=item_type,
                    item_code=item_code,
                    total_price=total_price,
                    reasoning=f"Item matches exclusion pattern: {pattern.pattern}",
                    exclusion_reason="exclusion_pattern",
                    trace=tb.build(),
                )

        # Rule 3: Check consumable patterns (parts only)
        # Skip if repair context indicates a covered component
        if item_type.lower() == "parts" and not skip_consumable_check:
            for pattern in self._consumable_patterns:
                if pattern.search(description):
                    # Check if description also indicates a component (not consumable)
                    is_component = any(
                        cp.search(description)
                        for cp in self._component_override_patterns
                    )
                    if is_component:
                        logger.info(
                            f"Consumable pattern matched but component override "
                            f"detected for '{description}' - skipping exclusion"
                        )
                        break  # Don't exclude, let it fall through
                    tb.add("rule_engine", TraceAction.EXCLUDED,
                           f"Consumable item not covered: {pattern.pattern}",
                           verdict=CoverageStatus.NOT_COVERED, confidence=1.0,
                           detail={"rule": "consumable", "pattern": pattern.pattern},
                           decision_source=DecisionSource.RULE)
                    return self._create_not_covered(
                        description=description,
                        item_type=item_type,
                        item_code=item_code,
                        total_price=total_price,
                        reasoning=f"Consumable item not covered: {pattern.pattern}",
                        exclusion_reason="consumable",
                        trace=tb.build(),
                    )
        elif item_type.lower() == "parts" and skip_consumable_check:
            # Log that we skipped consumable check due to repair context
            for pattern in self._consumable_patterns:
                if pattern.search(description):
                    tb.add("rule_engine", TraceAction.SKIPPED,
                           f"Consumable check skipped - repair context: {repair_context_component}",
                           detail={"rule": "consumable_override_by_repair_context",
                                   "repair_component": repair_context_component},
                           decision_source=DecisionSource.RULE)
                    logger.info(
                        f"Skipped consumable exclusion for '{description}' - "
                        f"repair context indicates '{repair_context_component}' (covered)"
                    )
                    break

        # Rule 4: Zero-price items (labor) - likely complimentary, skip coverage
        if total_price == 0.0:
            tb.add("rule_engine", TraceAction.MATCHED,
                   "Zero-price item - no coverage calculation needed",
                   verdict=CoverageStatus.COVERED, confidence=1.0,
                   detail={"rule": "zero_price"},
                   decision_source=DecisionSource.RULE)
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
                decision_trace=tb.build(),
                covered_amount=0.0,
                not_covered_amount=0.0,
            )

        # Rule 5: Non-covered labor patterns (labor only)
        if item_type.lower() == "labor":
            for pattern in self._non_covered_labor_patterns:
                if pattern.search(description):
                    tb.add("rule_engine", TraceAction.EXCLUDED,
                           f"Labor matches non-covered pattern: {pattern.pattern}",
                           verdict=CoverageStatus.NOT_COVERED, confidence=1.0,
                           detail={"rule": "non_covered_labor", "pattern": pattern.pattern},
                           decision_source=DecisionSource.RULE)
                    return self._create_not_covered(
                        description=description,
                        item_type=item_type,
                        item_code=item_code,
                        total_price=total_price,
                        reasoning=f"Labor matches non-covered pattern: {pattern.pattern}",
                        exclusion_reason="non_covered_labor",
                        trace=tb.build(),
                    )

        # Rule 6: Generic/empty descriptions with no semantic content
        stripped = description.strip()
        if self._generic_description_pattern and self._generic_description_pattern.match(stripped):
            tb.add("rule_engine", TraceAction.EXCLUDED,
                   "Generic description - insufficient detail for coverage determination",
                   verdict=CoverageStatus.NOT_COVERED, confidence=1.0,
                   detail={"rule": "generic_description"},
                   decision_source=DecisionSource.RULE)
            return self._create_not_covered(
                description=description,
                item_type=item_type,
                item_code=item_code,
                total_price=total_price,
                reasoning="Generic description - insufficient detail for coverage determination",
                exclusion_reason="generic_description",
                trace=tb.build(),
            )

        # Rule 7: Standalone fastener items -> REVIEW_NEEDED
        if self._fastener_pattern and self._fastener_pattern.match(stripped):
            tb.add("rule_engine", TraceAction.MATCHED,
                   "Standalone fastener - requires context to determine coverage",
                   verdict=CoverageStatus.REVIEW_NEEDED,
                   confidence=self.config.review_needed_confidence,
                   detail={"rule": "standalone_fastener"},
                   decision_source=DecisionSource.RULE)
            return self._create_review_needed(
                description=description,
                item_type=item_type,
                item_code=item_code,
                total_price=total_price,
                reasoning="Standalone fastener - requires context to determine coverage",
                confidence=self.config.review_needed_confidence,
                trace=tb.build(),
            )

        # Rule 7.5: Standalone seal/gasket items -> REVIEW_NEEDED
        # Compound terms like ZYLINDERKOPFDICHTUNG are NOT caught (anchored pattern).
        # LLM labor linkage may promote gaskets supporting a covered repair;
        # standalone gaskets stay REVIEW_NEEDED for human review.
        if self._seal_gasket_pattern and self._seal_gasket_pattern.match(stripped):
            tb.add("rule_engine", TraceAction.MATCHED,
                   "Standalone seal/gasket - requires context to determine coverage",
                   verdict=CoverageStatus.REVIEW_NEEDED,
                   confidence=self.config.review_needed_confidence,
                   detail={"rule": "standalone_seal_gasket"},
                   decision_source=DecisionSource.RULE)
            return self._create_review_needed(
                description=description,
                item_type=item_type,
                item_code=item_code,
                total_price=total_price,
                reasoning="Standalone seal/gasket - requires context to determine coverage",
                confidence=self.config.review_needed_confidence,
                trace=tb.build(),
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
        exclusion_reason: Optional[str] = None,
        trace: Optional[List] = None,
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
            exclusion_reason=exclusion_reason,
            decision_trace=trace,
            covered_amount=0.0,
            not_covered_amount=total_price,
        )

    def _create_review_needed(
        self,
        description: str,
        item_type: str,
        item_code: Optional[str],
        total_price: float,
        reasoning: str,
        confidence: float = 0.45,
        trace: Optional[List] = None,
    ) -> LineItemCoverage:
        """Create a REVIEW_NEEDED result."""
        return LineItemCoverage(
            item_code=item_code,
            description=description,
            item_type=item_type,
            total_price=total_price,
            coverage_status=CoverageStatus.REVIEW_NEEDED,
            coverage_category=None,
            matched_component=None,
            match_method=MatchMethod.RULE,
            match_confidence=confidence,
            match_reasoning=reasoning,
            decision_trace=trace,
            covered_amount=0.0,
            not_covered_amount=total_price,
        )

    def check_non_covered_labor(self, description: str) -> Optional[LineItemCoverage]:
        """Check if a labor description matches non-covered patterns.

        This is used by the analyzer to re-check labor items after keyword
        matching, since the keyword matcher may mark diagnostic labor as
        COVERED based on the component keyword in the description.

        Args:
            description: Labor item description

        Returns:
            LineItemCoverage (NOT_COVERED) if pattern matches, None otherwise
        """
        for pattern in self._non_covered_labor_patterns:
            if pattern.search(description):
                return self._create_not_covered(
                    description=description,
                    item_type="labor",
                    item_code=None,
                    total_price=0.0,
                    reasoning=f"Labor matches non-covered pattern: {pattern.pattern}",
                    exclusion_reason="non_covered_labor",
                )
        return None

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
