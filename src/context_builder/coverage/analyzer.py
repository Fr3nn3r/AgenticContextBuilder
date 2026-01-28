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
from typing import Any, Dict, List, Optional

import yaml

from context_builder.coverage.keyword_matcher import KeywordConfig, KeywordMatcher
from context_builder.coverage.llm_matcher import LLMMatcher, LLMMatcherConfig
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
    ):
        """Initialize the coverage analyzer.

        Args:
            config: Analyzer configuration
            rule_engine: Pre-configured rule engine
            keyword_matcher: Pre-configured keyword matcher
            llm_matcher: Pre-configured LLM matcher
        """
        self.config = config or AnalyzerConfig()
        self.rule_engine = rule_engine or RuleEngine()
        self.keyword_matcher = keyword_matcher or KeywordMatcher()
        self.llm_matcher = llm_matcher

    @classmethod
    def from_config_path(cls, config_path: Path) -> "CoverageAnalyzer":
        """Create an analyzer from a YAML configuration file.

        Args:
            config_path: Path to YAML config file

        Returns:
            Configured CoverageAnalyzer instance
        """
        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return cls()

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
        )

    def _determine_coverage_percent(
        self,
        vehicle_km: Optional[int],
        coverage_scale: Optional[List[Dict[str, Any]]],
    ) -> Optional[float]:
        """Determine coverage percentage from scale based on vehicle km.

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

        # Find applicable coverage percent
        coverage_percent = None
        for tier in sorted_scale:
            threshold = tier.get("km_threshold", 0)
            if vehicle_km <= threshold:
                coverage_percent = tier.get("coverage_percent")
                break

        # If vehicle_km exceeds all thresholds, use the last tier
        if coverage_percent is None and sorted_scale:
            coverage_percent = sorted_scale[-1].get("coverage_percent")

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

            if items_for_llm:
                if self.llm_matcher is None:
                    self.llm_matcher = LLMMatcher()

                llm_matched = self.llm_matcher.batch_match(
                    items_for_llm,
                    covered_categories=covered_categories,
                    covered_components=covered_components,
                    claim_id=claim_id,
                )

            # Mark skipped items as review needed
            for item in skipped:
                llm_matched.append(
                    LineItemCoverage(
                        item_code=item.get("item_code"),
                        description=item.get("description", ""),
                        item_type=item.get("item_type", ""),
                        total_price=item.get("total_price", 0.0),
                        coverage_status=CoverageStatus.REVIEW_NEEDED,
                        coverage_category=None,
                        matched_component=None,
                        match_method=MatchMethod.LLM,
                        match_confidence=0.0,
                        match_reasoning="Skipped due to LLM item limit",
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price", 0.0),
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
                        total_price=item.get("total_price", 0.0),
                        coverage_status=CoverageStatus.REVIEW_NEEDED,
                        coverage_category=None,
                        matched_component=None,
                        match_method=MatchMethod.KEYWORD,
                        match_confidence=0.0,
                        match_reasoning="No rule or keyword match; LLM fallback disabled",
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price", 0.0),
                    )
                )

        # Combine all results
        all_items = rule_matched + keyword_matched + llm_matched

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
