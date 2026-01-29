"""Coverage analyzer that orchestrates the full analysis pipeline.

The analyzer coordinates rule engine, keyword matcher, and LLM matcher
to determine coverage for all line items in a claim.

Pipeline order:
1. Rules (fast, deterministic, confidence=1.0)
2. Keywords (German mapping, confidence=0.70-0.90)
3. LLM (fallback, confidence=0.60-0.85)
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from context_builder.coverage.keyword_matcher import KeywordConfig, KeywordMatcher
from context_builder.coverage.llm_matcher import LLMMatcher, LLMMatcherConfig
from context_builder.coverage.part_number_lookup import PartLookupResult, PartNumberLookup
from context_builder.coverage.rule_engine import RuleConfig, RuleEngine
from context_builder.coverage.schemas import (
    CoverageAnalysisResult,
    CoverageInputs,
    CoverageMetadata,
    CoverageStatus,
    CoverageSummary,
    LineItemCoverage,
    MatchMethod,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalyzerConfig:
    """Configuration for the coverage analyzer."""

    # Minimum confidence for keyword match to be accepted
    keyword_min_confidence: float = 0.80

    # Whether to use LLM fallback for unmatched items
    use_llm_fallback: bool = True

    # Maximum items to process with LLM (cost control)
    llm_max_items: int = 20

    # Config version for metadata
    config_version: str = "1.0"

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AnalyzerConfig":
        """Create config from dictionary."""
        return cls(
            keyword_min_confidence=config.get("keyword_min_confidence", 0.80),
            use_llm_fallback=config.get("use_llm_fallback", True),
            llm_max_items=config.get("llm_max_items", 20),
            config_version=config.get("config_version", "1.0"),
        )


class CoverageAnalyzer:
    """Orchestrates the coverage analysis pipeline.

    The analyzer processes line items through three matching stages:
    1. Rule engine: Fast, deterministic matching
    2. Keyword matcher: German term to category mapping
    3. LLM matcher: Fallback for ambiguous items

    Usage:
        analyzer = CoverageAnalyzer.from_config(config_path)
        result = analyzer.analyze(
            claim_id="65196",
            line_items=items_from_claim_facts,
            covered_components=policy_coverage,
            vehicle_km=74359,
            coverage_scale=[{"km_threshold": 80000, "coverage_percent": 60}],
        )
    """

    def __init__(
        self,
        config: Optional[AnalyzerConfig] = None,
        rule_engine: Optional[RuleEngine] = None,
        keyword_matcher: Optional[KeywordMatcher] = None,
        llm_matcher: Optional[LLMMatcher] = None,
        workspace_path: Optional[Path] = None,
    ):
        """Initialize the coverage analyzer.

        Args:
            config: Analyzer configuration
            rule_engine: Pre-configured rule engine
            keyword_matcher: Pre-configured keyword matcher
            llm_matcher: Pre-configured LLM matcher
            workspace_path: Path to workspace for part number lookup
        """
        self.config = config or AnalyzerConfig()
        self.rule_engine = rule_engine or RuleEngine()
        self.keyword_matcher = keyword_matcher or KeywordMatcher()
        self.llm_matcher = llm_matcher
        self.workspace_path = workspace_path
        self.part_lookup = PartNumberLookup(workspace_path) if workspace_path else None

    @classmethod
    def from_config_path(
        cls, config_path: Path, workspace_path: Optional[Path] = None
    ) -> "CoverageAnalyzer":
        """Create an analyzer from a YAML configuration file.

        Args:
            config_path: Path to YAML config file
            workspace_path: Path to workspace for part number lookup

        Returns:
            Configured CoverageAnalyzer instance
        """
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls(workspace_path=workspace_path)

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        # Parse sub-configs
        analyzer_config = AnalyzerConfig.from_dict(config_data.get("analyzer", {}))
        rule_config = RuleConfig.from_dict(config_data.get("rules", {}))
        keyword_config = KeywordConfig.from_dict(config_data.get("keywords", {}))
        llm_config = LLMMatcherConfig.from_dict(config_data.get("llm", {}))

        return cls(
            config=analyzer_config,
            rule_engine=RuleEngine(rule_config),
            keyword_matcher=KeywordMatcher(keyword_config),
            llm_matcher=LLMMatcher(llm_config),
            workspace_path=workspace_path,
        )

    def _determine_coverage_percent(
        self,
        vehicle_km: Optional[int],
        coverage_scale: Optional[List[Dict[str, Any]]],
    ) -> Optional[float]:
        """Determine coverage percentage from scale based on vehicle km.

        The coverage scale uses "A partir de X km" (from X km onwards) semantics:
        - Below first threshold: 100% coverage (full coverage before any reduction)
        - At or above a threshold: that tier's percentage applies

        Example scale:
        - A partir de 80,000 km = 80% -> vehicle at 51,134 km gets 100%
        - A partir de 100,000 km = 70% -> vehicle at 85,000 km gets 80%
        - A partir de 120,000 km = 60% -> vehicle at 105,000 km gets 70%

        Args:
            vehicle_km: Current vehicle odometer in km
            coverage_scale: List of {km_threshold, coverage_percent} dicts

        Returns:
            Coverage percentage (e.g., 60.0 for 60%), or None if not determinable
        """
        if not vehicle_km or not coverage_scale:
            return None

        # Sort by km_threshold ascending
        sorted_scale = sorted(coverage_scale, key=lambda x: x.get("km_threshold", 0))

        # "A partir de" means "from X km onwards"
        # Below the first threshold = 100% coverage (full coverage)
        # At or above a threshold = that tier's percentage applies
        first_threshold = sorted_scale[0].get("km_threshold", 0)
        if vehicle_km < first_threshold:
            return 100.0  # Full coverage before first reduction tier

        # Find the highest applicable tier (last one where km >= threshold)
        coverage_percent = sorted_scale[0].get("coverage_percent")  # Default to first tier
        for tier in sorted_scale:
            threshold = tier.get("km_threshold", 0)
            if vehicle_km >= threshold:
                coverage_percent = tier.get("coverage_percent")
            else:
                break  # Sorted ascending, so no need to check further

        return coverage_percent

    def _extract_covered_categories(
        self, covered_components: Dict[str, List[str]]
    ) -> List[str]:
        """Extract list of category names that have covered components.

        Args:
            covered_components: Dict mapping category to list of parts

        Returns:
            List of category names with non-empty parts lists
        """
        return [cat for cat, parts in covered_components.items() if parts]

    def _is_system_covered(self, system: str, covered_categories: List[str]) -> bool:
        """Check if a system/category is covered by the policy.

        Args:
            system: System name from part lookup (e.g., "electric")
            covered_categories: Categories covered by the policy

        Returns:
            True if system matches any covered category
        """
        if not system:
            return False
        system_lower = system.lower()
        for cat in covered_categories:
            cat_lower = cat.lower()
            if (
                system_lower == cat_lower
                or system_lower in cat_lower
                or cat_lower in system_lower
            ):
                return True
        return False

    def _match_by_part_number(
        self,
        items: List[Dict[str, Any]],
        covered_categories: List[str],
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Match items by part number lookup.

        First tries exact part number lookup, then falls back to
        description-based keyword lookup from assumptions.json.

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
            description = item.get("description", "")

            # Try exact part number lookup first
            result = None
            if item_code:
                result = self.part_lookup.lookup(item_code)

            # If no exact match, try description-based keyword lookup
            if (not result or not result.found) and description:
                result = self.part_lookup.lookup_by_description(description)

            if not result or not result.found:
                unmatched.append(item)
                continue

            # Check if the part's system matches a covered category
            is_covered = self._is_system_covered(result.system, covered_categories)

            # Use part_number from result (could be item_code or keyword match)
            part_ref = item_code or result.part_number

            if result.covered is False:
                # Part is explicitly excluded (e.g., accessory)
                status = CoverageStatus.NOT_COVERED
                reasoning = (
                    f"Part {part_ref} is excluded: "
                    f"{result.note or result.component}"
                )
            elif is_covered:
                status = CoverageStatus.COVERED
                reasoning = (
                    f"Part {part_ref} identified as "
                    f"'{result.component_description or result.component}' "
                    f"in category '{result.system}' (lookup: {result.lookup_source})"
                )
            else:
                status = CoverageStatus.NOT_COVERED
                reasoning = (
                    f"Part {part_ref} is '{result.component}' in category "
                    f"'{result.system}' which is not covered by this policy"
                )

            matched.append(
                LineItemCoverage(
                    item_code=item_code,
                    description=item.get("description", ""),
                    item_type=item.get("item_type", ""),
                    total_price=item.get("total_price") or 0.0,
                    coverage_status=status,
                    coverage_category=result.system,
                    matched_component=result.component_description or result.component,
                    match_method=MatchMethod.PART_NUMBER,
                    match_confidence=0.95,  # High confidence for part number matches
                    match_reasoning=reasoning,
                    covered_amount=(
                        item.get("total_price") or 0.0
                        if status == CoverageStatus.COVERED
                        else 0.0
                    ),
                    not_covered_amount=(
                        0.0
                        if status == CoverageStatus.COVERED
                        else item.get("total_price") or 0.0
                    ),
                )
            )

            logger.debug(
                f"Part lookup match: {part_ref} -> {result.system}/{result.component} "
                f"({status.value}, source={result.lookup_source})"
            )

        return matched, unmatched

    def _calculate_summary(
        self,
        line_items: List[LineItemCoverage],
        coverage_percent: Optional[float],
        excess_percent: Optional[float],
        excess_minimum: Optional[float],
    ) -> CoverageSummary:
        """Calculate summary statistics from analyzed line items.

        Args:
            line_items: List of analyzed line items
            coverage_percent: Policy coverage percentage
            excess_percent: Excess/deductible percentage
            excess_minimum: Minimum excess amount

        Returns:
            CoverageSummary with totals and counts
        """
        total_claimed = 0.0
        total_covered_before_excess = 0.0
        total_not_covered = 0.0
        items_covered = 0
        items_not_covered = 0
        items_review_needed = 0

        for item in line_items:
            total_claimed += item.total_price

            if item.coverage_status == CoverageStatus.COVERED:
                # Apply coverage percentage if available
                if coverage_percent is not None:
                    covered_amount = item.total_price * (coverage_percent / 100.0)
                else:
                    covered_amount = item.total_price
                item.covered_amount = covered_amount
                item.not_covered_amount = item.total_price - covered_amount
                total_covered_before_excess += covered_amount
                items_covered += 1

            elif item.coverage_status == CoverageStatus.NOT_COVERED:
                item.covered_amount = 0.0
                item.not_covered_amount = item.total_price
                total_not_covered += item.total_price
                items_not_covered += 1

            else:  # REVIEW_NEEDED
                # Conservatively assume not covered until reviewed
                item.covered_amount = 0.0
                item.not_covered_amount = item.total_price
                total_not_covered += item.total_price
                items_review_needed += 1

        # Calculate excess
        excess_amount = 0.0
        if excess_percent is not None and total_covered_before_excess > 0:
            excess_amount = total_covered_before_excess * (excess_percent / 100.0)
            if excess_minimum is not None:
                excess_amount = max(excess_amount, excess_minimum)

        # Final payable
        total_payable = max(0.0, total_covered_before_excess - excess_amount)

        return CoverageSummary(
            total_claimed=total_claimed,
            total_covered_before_excess=total_covered_before_excess,
            total_not_covered=total_not_covered,
            excess_amount=excess_amount,
            total_payable=total_payable,
            items_covered=items_covered,
            items_not_covered=items_not_covered,
            items_review_needed=items_review_needed,
            coverage_percent=coverage_percent,
        )

    def _apply_labor_follows_parts(
        self, items: List[LineItemCoverage]
    ) -> List[LineItemCoverage]:
        """Promote labor items to COVERED if they reference covered parts by part number.

        When a labor item is NOT_COVERED or REVIEW_NEEDED but references a covered part's
        part number in its description, it should be promoted to COVERED since the labor
        is for installing/replacing that covered component.

        This is a conservative matching approach that only links labor to parts when
        the part number explicitly appears in the labor description. Generic keyword
        matching (like "MODULE", "SYNC") was removed to prevent false positives.

        Args:
            items: List of analyzed line items

        Returns:
            Updated list with labor items potentially promoted
        """
        # Build index of covered parts by part number only (no keyword extraction)
        # This prevents false positives from generic keywords like MODULE, SYNC, POWER
        covered_parts_by_code: Dict[str, LineItemCoverage] = {}
        for item in items:
            if (
                item.coverage_status == CoverageStatus.COVERED
                and item.item_type in ("parts", "part", "piece")
            ):
                # Index by part number only (e.g., "F2237471")
                if item.item_code:
                    clean_code = "".join(c for c in item.item_code if c.isalnum()).upper()
                    if len(clean_code) >= 4:
                        covered_parts_by_code[clean_code] = item

        if not covered_parts_by_code:
            return items

        # Check labor items for part number references
        for item in items:
            if item.item_type not in ("labor", "labour", "main d'oeuvre", "arbeit"):
                continue

            if item.coverage_status == CoverageStatus.COVERED:
                continue

            # Check if labor description contains a covered part number as substring
            desc_upper = item.description.upper()
            desc_alphanum = "".join(c for c in desc_upper if c.isalnum() or c.isspace())

            for part_code, covered_part in covered_parts_by_code.items():
                if part_code in desc_alphanum:
                    # Promote labor to COVERED
                    item.coverage_status = CoverageStatus.COVERED
                    item.coverage_category = covered_part.coverage_category
                    item.matched_component = covered_part.matched_component
                    item.match_confidence = 0.85  # Higher confidence for part number match
                    item.match_reasoning = (
                        f"Labor for covered part: {covered_part.description} "
                        f"(matched part number: {part_code})"
                    )

                    logger.debug(
                        f"Promoted labor '{item.description}' to COVERED "
                        f"(linked to part number: {part_code})"
                    )
                    break

        return items

    def analyze(
        self,
        claim_id: str,
        line_items: List[Dict[str, Any]],
        covered_components: Optional[Dict[str, List[str]]] = None,
        vehicle_km: Optional[int] = None,
        coverage_scale: Optional[List[Dict[str, Any]]] = None,
        excess_percent: Optional[float] = None,
        excess_minimum: Optional[float] = None,
        claim_run_id: Optional[str] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
        on_llm_start: Optional[Callable[[int], None]] = None,
    ) -> CoverageAnalysisResult:
        """Analyze coverage for all line items in a claim.

        Args:
            claim_id: Claim identifier
            line_items: List of line item dicts from claim_facts
            covered_components: Dict of category -> list of covered parts
            vehicle_km: Current vehicle odometer reading
            coverage_scale: List of {km_threshold, coverage_percent}
            excess_percent: Excess percentage from policy
            excess_minimum: Minimum excess amount
            claim_run_id: Optional claim run ID for output
            on_llm_progress: Callback for LLM progress updates (increment)
            on_llm_start: Callback when LLM matching starts (total count)

        Returns:
            CoverageAnalysisResult with all analysis data
        """
        start_time = time.time()
        covered_components = covered_components or {}

        # Determine coverage percentage from scale
        coverage_percent = self._determine_coverage_percent(vehicle_km, coverage_scale)

        # Extract covered categories
        covered_categories = self._extract_covered_categories(covered_components)

        logger.info(
            f"Analyzing {len(line_items)} items for claim {claim_id} "
            f"(coverage={coverage_percent}%, km={vehicle_km})"
        )

        # Stage 1: Rule engine
        rule_matched, remaining = self.rule_engine.batch_match(line_items)
        logger.debug(f"Rules matched: {len(rule_matched)}/{len(line_items)}")

        # Stage 1.5: Part number lookup (if workspace configured)
        part_matched = []
        if self.part_lookup and remaining:
            part_matched, remaining = self._match_by_part_number(
                remaining, covered_categories
            )
            logger.debug(f"Part numbers matched: {len(part_matched)}/{len(line_items)}")

        # Stage 2: Keyword matcher
        keyword_matched, remaining = self.keyword_matcher.batch_match(
            remaining,
            covered_categories=covered_categories,
            min_confidence=self.config.keyword_min_confidence,
        )
        logger.debug(f"Keywords matched: {len(keyword_matched)}/{len(line_items)}")

        # Stage 3: LLM fallback (if enabled and items remain)
        llm_matched = []
        if remaining and self.config.use_llm_fallback:
            # Limit LLM calls
            items_for_llm = remaining[: self.config.llm_max_items]
            skipped = remaining[self.config.llm_max_items :]

            # Warn if items exceed LLM limit
            if len(remaining) > self.config.llm_max_items:
                logger.warning(
                    f"LLM item limit exceeded: {len(remaining)} items need LLM processing "
                    f"but limit is {self.config.llm_max_items}. "
                    f"{len(skipped)} items will be skipped and marked as review_needed. "
                    f"Consider adding keyword rules for frequently skipped item types."
                )

            if items_for_llm:
                if self.llm_matcher is None:
                    self.llm_matcher = LLMMatcher()

                # Notify about LLM work starting
                if on_llm_start:
                    on_llm_start(len(items_for_llm))

                # Collect covered parts from prior stages to give LLM context
                # This helps LLM make nuanced labor decisions based on what parts are covered
                covered_parts_in_claim = []
                for item in rule_matched + part_matched + keyword_matched:
                    if (
                        item.coverage_status == CoverageStatus.COVERED
                        and item.item_type in ("parts", "part", "piece")
                    ):
                        covered_parts_in_claim.append({
                            "item_code": item.item_code or "",
                            "description": item.description,
                            "matched_component": item.matched_component or "",
                        })

                llm_matched = self.llm_matcher.batch_match(
                    items_for_llm,
                    covered_categories=covered_categories,
                    covered_components=covered_components,
                    claim_id=claim_id,
                    on_progress=on_llm_progress,
                    covered_parts_in_claim=covered_parts_in_claim,
                )

            # Mark skipped items as review needed
            for item in skipped:
                llm_matched.append(
                    LineItemCoverage(
                        item_code=item.get("item_code"),
                        description=item.get("description", ""),
                        item_type=item.get("item_type", ""),
                        total_price=item.get("total_price") or 0.0,
                        coverage_status=CoverageStatus.REVIEW_NEEDED,
                        coverage_category=None,
                        matched_component=None,
                        match_method=MatchMethod.LLM,
                        match_confidence=0.0,
                        match_reasoning="Skipped due to LLM item limit",
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price") or 0.0,
                    )
                )
        elif remaining:
            # LLM disabled, mark all remaining as review needed
            for item in remaining:
                llm_matched.append(
                    LineItemCoverage(
                        item_code=item.get("item_code"),
                        description=item.get("description", ""),
                        item_type=item.get("item_type", ""),
                        total_price=item.get("total_price") or 0.0,
                        coverage_status=CoverageStatus.REVIEW_NEEDED,
                        coverage_category=None,
                        matched_component=None,
                        match_method=MatchMethod.KEYWORD,
                        match_confidence=0.0,
                        match_reasoning="No rule or keyword match; LLM fallback disabled",
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price") or 0.0,
                    )
                )

        # Combine all results
        all_items = rule_matched + part_matched + keyword_matched + llm_matched

        # Apply labor-follows-parts linking
        all_items = self._apply_labor_follows_parts(all_items)

        # Calculate summary
        summary = self._calculate_summary(
            all_items,
            coverage_percent=coverage_percent,
            excess_percent=excess_percent,
            excess_minimum=excess_minimum,
        )

        # Build metadata
        processing_time_ms = (time.time() - start_time) * 1000
        llm_calls = self.llm_matcher.get_llm_call_count() if self.llm_matcher else 0

        metadata = CoverageMetadata(
            rules_applied=len(rule_matched),
            part_numbers_applied=len(part_matched),
            keywords_applied=len(keyword_matched),
            llm_calls=llm_calls,
            processing_time_ms=processing_time_ms,
            config_version=self.config.config_version,
        )

        # Build inputs record
        inputs = CoverageInputs(
            vehicle_km=vehicle_km,
            coverage_percent=coverage_percent,
            excess_percent=excess_percent,
            excess_minimum=excess_minimum,
            covered_categories=covered_categories,
        )

        logger.info(
            f"Coverage analysis complete: "
            f"{summary.items_covered} covered, "
            f"{summary.items_not_covered} not covered, "
            f"{summary.items_review_needed} review needed "
            f"({processing_time_ms:.0f}ms)"
        )

        return CoverageAnalysisResult(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            generated_at=datetime.utcnow(),
            inputs=inputs,
            line_items=all_items,
            summary=summary,
            metadata=metadata,
        )
