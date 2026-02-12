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
from dataclasses import dataclass, replace as _dc_replace
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
    PrimaryRepairResult,
    TraceAction,
    TraceStep,
)
from context_builder.coverage.trace import TraceBuilder

logger = logging.getLogger(__name__)


def _find_sibling(config_path: Path, pattern: str) -> Optional[Path]:
    """Find a sibling file matching a glob pattern."""
    matches = list(config_path.parent.glob(pattern))
    return matches[0] if matches else None


# German umlaut / accent normalization table for substring matching.
_UMLAUT_TABLE = str.maketrans({
    "ä": "a", "ö": "o", "ü": "u",
    "Ä": "A", "Ö": "O", "Ü": "U",
    "é": "e", "è": "e", "ê": "e",
    "à": "a", "â": "a",
    "î": "i", "ï": "i",
    "ô": "o", "û": "u", "ù": "u",
    "ç": "c", "ß": "ss",
})


def _normalize_umlauts(text: str) -> str:
    """Normalize umlauts and accents for fuzzy substring matching."""
    return text.translate(_UMLAUT_TABLE)


def _normalize_coverage_scale(
    raw_scale: Any,
) -> Tuple[Optional[int], Optional[List[Dict[str, Any]]]]:
    """Normalize coverage_scale from either old or new format.

    Old format (list): [{"km_threshold": 50000, "coverage_percent": 90}, ...]
    New format (dict): {"age_threshold_years": 8, "tiers": [{"km_threshold": 50000, "coverage_percent": 90, "age_coverage_percent": 80}, ...]}

    Returns:
        Tuple of (age_threshold_years, tiers_list).
        age_threshold_years is None if not present (old format or policy without age rule).
        tiers_list is None if raw_scale is invalid/missing.
    """
    if isinstance(raw_scale, list):
        # Old format — no age data
        return None, raw_scale
    elif isinstance(raw_scale, dict):
        age_threshold = raw_scale.get("age_threshold_years")
        tiers = raw_scale.get("tiers", [])
        return age_threshold, tiers
    return None, None


@dataclass
class ComponentConfig:
    """Customer-specific component vocabulary for coverage matching.

    Loaded from *_component_config.yaml in the coverage config directory.
    """

    component_synonyms: Dict[str, List[str]]
    category_aliases: Dict[str, List[str]]
    repair_context_keywords: Dict[str, Tuple[str, str]]
    distribution_catch_all_components: set
    distribution_catch_all_keywords: List[str]
    gasket_seal_indicators: set
    ancillary_keywords: set
    additional_policy_parts: Dict[str, List[str]]

    @classmethod
    def default(cls) -> "ComponentConfig":
        """Return empty defaults (no vocabulary loaded)."""
        return cls(
            component_synonyms={},
            category_aliases={},
            repair_context_keywords={},
            distribution_catch_all_components=set(),
            distribution_catch_all_keywords=[],
            gasket_seal_indicators=set(),
            ancillary_keywords=set(),
            additional_policy_parts={},
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComponentConfig":
        """Create from a parsed YAML dict."""
        # Parse repair_context_keywords: {keyword: {component, category}} → {keyword: (component, category)}
        raw_rck = data.get("repair_context_keywords", {})
        repair_kw: Dict[str, Tuple[str, str]] = {}
        for kw, val in raw_rck.items():
            if isinstance(val, dict):
                repair_kw[kw] = (val["component"], val["category"])
            elif isinstance(val, (list, tuple)) and len(val) == 2:
                repair_kw[kw] = (val[0], val[1])

        return cls(
            component_synonyms=data.get("component_synonyms", {}),
            category_aliases=data.get("category_aliases", {}),
            repair_context_keywords=repair_kw,
            distribution_catch_all_components=set(
                data.get("distribution_catch_all_components", [])
            ),
            distribution_catch_all_keywords=data.get(
                "distribution_catch_all_keywords", []
            ),
            gasket_seal_indicators=set(
                data.get("gasket_seal_indicators", [])
            ),
            ancillary_keywords=set(
                data.get("ancillary_keywords", [])
            ),
            additional_policy_parts=data.get("additional_policy_parts", {}),
        )


@dataclass
class AnalyzerConfig:
    """Configuration for the coverage analyzer."""

    # Minimum confidence for keyword match to be accepted
    keyword_min_confidence: float = 0.80

    # Whether to use LLM fallback for unmatched items
    use_llm_fallback: bool = True

    # Maximum items to process with LLM (cost control)
    llm_max_items: int = 35

    # Max concurrent LLM calls (1 = sequential, >1 = parallel)
    llm_max_concurrent: int = 3

    # Config version for metadata
    config_version: str = "1.0"

    # Default coverage percent when no coverage_scale is extracted
    # (e.g., policies with full coverage that have no mileage-based tiering)
    default_coverage_percent: Optional[float] = None

    # Use LLM to identify the primary repair component (Tier 0).
    # When True, an LLM call reads all line items and picks the main repair
    # before falling back to the value-based heuristic (Tier 1a-1c).
    use_llm_primary_repair: bool = False

    # Nominal-price labor threshold: labor items at or below this price
    # with an item_code are flagged REVIEW_NEEDED (suspected operation
    # codes where the real cost is hours x rate, not yet supported).
    nominal_price_threshold: float = 2.0

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AnalyzerConfig":
        """Create config from dictionary."""
        return cls(
            keyword_min_confidence=config.get("keyword_min_confidence", 0.80),
            use_llm_fallback=config.get("use_llm_fallback", True),
            llm_max_items=config.get("llm_max_items", 35),
            llm_max_concurrent=config.get("llm_max_concurrent", 3),
            config_version=config.get("config_version", "1.0"),
            default_coverage_percent=config.get("default_coverage_percent"),
            use_llm_primary_repair=config.get("use_llm_primary_repair", False),
            nominal_price_threshold=config.get("nominal_price_threshold", 2.0),
        )


@dataclass
class RepairContext:
    """Context about the primary repair being performed.

    Extracted from labor descriptions to provide context for parts coverage.
    When labor clearly indicates a specific component (e.g., "Ölkühler defekt"),
    this context helps avoid false consumable matches on related parts.
    """

    # Primary component being repaired (e.g., "oil_cooler")
    primary_component: Optional[str] = None

    # Category of the primary component (e.g., "engine")
    primary_category: Optional[str] = None

    # Whether the primary component is covered by policy
    # True = confirmed covered, False = confirmed not covered, None = uncertain
    is_covered: Optional[bool] = False

    # Labor description that established the context
    source_description: Optional[str] = None

    # Components detected in all labor items
    all_detected_components: List[str] = None

    def __post_init__(self):
        if self.all_detected_components is None:
            self.all_detected_components = []


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
        component_config: Optional[ComponentConfig] = None,
    ):
        """Initialize the coverage analyzer.

        Args:
            config: Analyzer configuration
            rule_engine: Pre-configured rule engine
            keyword_matcher: Pre-configured keyword matcher
            llm_matcher: Pre-configured LLM matcher
            workspace_path: Path to workspace for part number lookup
            component_config: Customer-specific component vocabulary
        """
        self.config = config or AnalyzerConfig()
        self.component_config = component_config or ComponentConfig.default()
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

        # Load keyword config: from main YAML, or from sibling keyword mappings file
        keyword_data = config_data.get("keywords", {})
        if not keyword_data.get("mappings"):
            keyword_file = _find_sibling(config_path, "*_keyword_mappings.yaml")
            if keyword_file:
                with open(keyword_file, "r", encoding="utf-8") as f:
                    keyword_data = yaml.safe_load(f) or {}
                logger.info(f"Loaded keyword mappings from {keyword_file.name}")
        keyword_config = KeywordConfig.from_dict(keyword_data)

        llm_config = LLMMatcherConfig.from_dict(config_data.get("llm", {}))

        # Load component config from sibling *_component_config.yaml
        comp_config = ComponentConfig.default()
        comp_file = _find_sibling(config_path, "*_component_config.yaml")
        if comp_file:
            with open(comp_file, "r", encoding="utf-8") as f:
                comp_data = yaml.safe_load(f) or {}
            comp_config = ComponentConfig.from_dict(comp_data)
            logger.info(f"Loaded component config from {comp_file.name}")

        return cls(
            config=analyzer_config,
            rule_engine=RuleEngine(rule_config),
            keyword_matcher=KeywordMatcher(keyword_config),
            llm_matcher=LLMMatcher(llm_config),
            workspace_path=workspace_path,
            component_config=comp_config,
        )

    def _determine_coverage_percent(
        self,
        vehicle_km: Optional[int],
        coverage_scale: Optional[List[Dict[str, Any]]],
        vehicle_age_years: Optional[float] = None,
        age_threshold_years: Optional[int] = None,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Determine coverage percentage from scale based on vehicle km and age.

        The coverage scale uses "A partir de X km" (from X km onwards) semantics:
        - Below first threshold: 100% coverage (full coverage before any reduction)
        - At or above a threshold: that tier's percentage applies

        Per-tier age-based reduction (e.g., "Dès 8 ans 80%" at the 50k tier):
        - If vehicle age >= age_threshold_years AND the matching tier has an
          age_coverage_percent, use the tier's age rate instead of the normal rate
        - If the policy has no age column (age_coverage_percent is null/missing),
          no age adjustment is applied

        Args:
            vehicle_km: Current vehicle odometer in km
            coverage_scale: List of {km_threshold, coverage_percent, age_coverage_percent?} dicts
            vehicle_age_years: Vehicle age in years
            age_threshold_years: Age threshold for reduced coverage (e.g., 8)

        Returns:
            Tuple of (mileage_based_percent, effective_percent after age adjustment)
        """
        if not vehicle_km or not coverage_scale:
            return None, None

        # Sort by km_threshold ascending
        sorted_scale = sorted(coverage_scale, key=lambda x: x.get("km_threshold", 0))

        # "A partir de" means "from X km onwards"
        # Below the first threshold = 100% coverage (full coverage)
        # At or above a threshold = that tier's percentage applies
        first_threshold = sorted_scale[0].get("km_threshold", 0)
        if vehicle_km < first_threshold:
            mileage_percent = 100.0  # Full coverage before first reduction tier
            tier_age_percent = None  # Below first tier — no age rate defined
        else:
            # Find the highest applicable tier (last one where km >= threshold)
            applicable_tier = sorted_scale[0]
            for tier in sorted_scale:
                if vehicle_km >= tier.get("km_threshold", 0):
                    applicable_tier = tier
                else:
                    break  # Sorted ascending, no need to check further
            mileage_percent = applicable_tier.get("coverage_percent")
            tier_age_percent = applicable_tier.get("age_coverage_percent")

        # Apply per-tier age-based reduction if applicable
        effective_percent = mileage_percent
        if (
            vehicle_age_years is not None
            and age_threshold_years is not None
            and vehicle_age_years >= age_threshold_years
            and tier_age_percent is not None
        ):
            effective_percent = tier_age_percent
            logger.info(
                f"Age-based coverage reduction: vehicle is {vehicle_age_years:.1f} years old "
                f"(>= {age_threshold_years}), using tier age rate {tier_age_percent}% "
                f"instead of {mileage_percent}%"
            )

        return mileage_percent, effective_percent

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

    def _extract_repair_context(
        self,
        line_items: List[Dict[str, Any]],
        covered_components: Dict[str, List[str]],
        excluded_components: Optional[Dict[str, List[str]]] = None,
    ) -> RepairContext:
        """Extract repair context from labor descriptions.

        Analyzes labor items to identify the primary component being repaired.
        This context is used to avoid false consumable matches - e.g., when
        labor says "Ölkühler defekt", parts shouldn't match "Ölfilter" exclusion.

        Args:
            line_items: All line items from the claim
            covered_components: Policy's covered components by category
            excluded_components: Policy's excluded components by category

        Returns:
            RepairContext with detected component info
        """
        context = RepairContext()
        detected = []

        # Scan labor items for repair keywords
        for item in line_items:
            item_type = item.get("item_type", "").lower()
            if item_type not in ("labor", "labour", "arbeit", "main d'oeuvre"):
                continue

            description = item.get("description", "").lower()
            if not description:
                continue

            # Check for known repair keywords
            desc_upper = item.get("description", "").upper()
            for keyword, (component, category) in self.component_config.repair_context_keywords.items():
                if keyword in description:
                    # Check if description matches an exclusion pattern — if so,
                    # the item is excluded and the keyword match is a false positive
                    # (e.g. "culasse" in "couvre culasse")
                    if any(p.search(desc_upper) for p in self.rule_engine._exclusion_patterns):
                        logger.info(
                            "Repair context: skipping keyword '%s' in '%s' — "
                            "matches exclusion pattern",
                            keyword, description[:60],
                        )
                        continue
                    detected.append(component)

                    # Use the first detected component as primary
                    if context.primary_component is None:
                        context.primary_component = component
                        context.primary_category = category
                        context.source_description = item.get("description", "")

                        # Check if this component is covered by policy
                        is_covered, _reason = self._is_component_in_policy_list(
                            component, category, covered_components,
                            strict=True,
                        )

                        if is_covered:
                            context.is_covered = True
                        else:
                            # Part not in covered list — check if category is
                            # covered and part is NOT explicitly excluded.
                            # Policy lists are representative, not exhaustive:
                            # if a category is covered and the part isn't
                            # excluded, the part is covered.
                            covered_cats = self._extract_covered_categories(covered_components)
                            cat_covered = self._is_system_covered(category, covered_cats)

                            if cat_covered and excluded_components and not self._is_component_excluded_by_policy(
                                component, category, item.get("description", ""),
                                excluded_components,
                            ):
                                context.is_covered = True
                                logger.info(
                                    "Repair context: '%s' in '%s' — category covered, "
                                    "part not listed, NOT excluded → covered",
                                    component, category,
                                )
                            else:
                                context.is_covered = False

                        logger.debug(
                            f"Repair context: '{component}' in '{category}' "
                            f"(covered={context.is_covered}) from '{description[:50]}...'"
                        )
                    break  # Found a match for this item, move to next

        context.all_detected_components = list(set(detected))

        if context.primary_component:
            logger.info(
                f"Extracted repair context: {context.primary_component} "
                f"({context.primary_category}), covered={context.is_covered}"
            )

        return context

    def _is_component_excluded_by_policy(
        self,
        component: str,
        category: str,
        description: str,
        excluded_components: Dict[str, List[str]],
    ) -> bool:
        """Check if a component is explicitly in the policy's exclusion list.

        Uses the component's synonyms and the item description to match
        against excluded parts for the relevant category (including aliases).

        Args:
            component: Component type (e.g., "angle_gearbox")
            category: Category name (e.g., "axle_drive")
            description: Original item description
            excluded_components: Policy's excluded components by category

        Returns:
            True if the component is explicitly excluded
        """
        if not excluded_components:
            return False

        # Collect excluded parts for this category (and its aliases)
        category_lower = category.lower()
        search_names = [category_lower]
        search_names.extend(
            self.component_config.category_aliases.get(category_lower, [])
        )

        excluded_parts: List[str] = []
        for search_name in search_names:
            for cat, parts in excluded_components.items():
                cat_lower = cat.lower()
                if (
                    search_name == cat_lower
                    or search_name in cat_lower
                    or cat_lower in search_name
                ):
                    excluded_parts.extend(parts)

        if not excluded_parts:
            return False

        excluded_lower = [p.lower() for p in excluded_parts]

        # Check component name and synonyms against exclusion list
        component_lower = component.lower().replace(" ", "_")
        synonyms = (
            self.component_config.component_synonyms.get(component_lower)
            or self.component_config.component_synonyms.get(
                component_lower.replace("_", " ")
            )
            or []
        )

        check_terms = [component_lower, component_lower.replace("_", " ")]
        check_terms.extend(synonyms)

        for term in check_terms:
            for excl in excluded_lower:
                if term in excl or excl in term:
                    logger.debug(
                        "Component '%s' matched exclusion '%s' (term='%s')",
                        component, excl, term,
                    )
                    return True

        # Check original description against exclusion list
        desc_lower = description.lower()
        for excl in excluded_lower:
            if excl in desc_lower or desc_lower in excl:
                logger.debug(
                    "Description '%s' matched exclusion '%s'",
                    description[:60], excl,
                )
                return True

        return False

    def _is_system_covered(self, system: str, covered_categories: List[str]) -> bool:
        """Check if a system/category is covered by the policy.

        Uses substring matching first, then checks CATEGORY_ALIASES for
        equivalent category names (e.g. axle_drive ↔ four_wd).

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

        # Check category aliases
        aliases = self.component_config.category_aliases.get(system_lower, [])
        for alias in aliases:
            for cat in covered_categories:
                cat_lower = cat.lower()
                if (
                    alias == cat_lower
                    or alias in cat_lower
                    or cat_lower in alias
                ):
                    return True

        return False

    def _find_component_across_categories(
        self,
        component: Optional[str],
        primary_system: Optional[str],
        covered_components: Dict[str, List[str]],
        excluded_components: Dict[str, List[str]],
        description: str = "",
    ) -> Tuple[bool, Optional[str], str]:
        """Search all covered categories for a component that wasn't found in its primary category.

        When a part maps to category X via part number lookup but is not in X's
        policy list, this checks every *other* covered category for a match.
        Example: height_control_valve → suspension (not listed) → found in chassis
        via "Height control" substring match.

        Returns:
            (found, category, reason) — found is True if the component was matched
            in another category; category is the name of that category; reason is
            a human-readable explanation.
        """
        primary_lower = (primary_system or "").lower()
        for category, parts_list in covered_components.items():
            if category.lower() == primary_lower:
                continue
            if not parts_list:
                continue

            is_in_list, reason = self._is_component_in_policy_list(
                component=component,
                system=category,
                covered_components=covered_components,
                description=description,
            )
            if is_in_list is True:
                # Found — but also check if it's excluded in that category
                is_excluded = self._is_component_excluded_by_policy(
                    component or "", category, description, excluded_components,
                )
                if is_excluded:
                    logger.debug(
                        "Cross-category match: '%s' found in '%s' but excluded",
                        component, category,
                    )
                    continue
                return True, category, (
                    f"Cross-category match: component not in '{primary_system}' "
                    f"list but found in '{category}' ({reason})"
                )

        return False, None, (
            f"Component '{component}' not found in any other category's policy list"
        )

    def _is_component_in_policy_list(
        self,
        component: Optional[str],
        system: Optional[str],
        covered_components: Dict[str, List[str]],
        description: str = "",
        strict: bool = False,
    ) -> Tuple[Optional[bool], str]:
        """Check if a specific component is in the policy's covered parts list.

        This prevents false approvals where a category (e.g., "engine") is covered
        but the specific component (e.g., "timing_belt") is not in the policy's
        list of covered parts for that category.

        Args:
            component: Component type from lookup (e.g., "timing_belt")
            system: System/category name (e.g., "engine")
            covered_components: Dict mapping category to list of covered parts
            description: Original item description for fallback matching
            strict: If True, return False for unknown components (no safe fallback).
                    If False (default), return None for uncertain (needs LLM verification).

        Returns:
            Tuple of (is_in_list, reason) where is_in_list is:
              True  - confirmed in policy list (synonym matched)
              False - confirmed NOT in list (synonym found, no match)
              None  - uncertain (no synonym available, needs LLM verification)
        """
        if not system:
            return True, "No system to verify"

        # Find the matching category in covered_components
        system_lower = system.lower()
        matching_category = None
        policy_parts_list = None

        # Build list of names to search: the system itself + its aliases
        search_names = [system_lower]
        search_names.extend(self.component_config.category_aliases.get(system_lower, []))

        for search_name in search_names:
            for cat, parts in covered_components.items():
                cat_lower = cat.lower()
                if (
                    search_name == cat_lower
                    or search_name in cat_lower
                    or cat_lower in search_name
                ):
                    matching_category = cat
                    policy_parts_list = parts
                    break
            if matching_category:
                break

        if not matching_category or not policy_parts_list:
            # No specific parts list for this category - can't determine, needs verification
            return None, f"No specific parts list for category '{system}' - needs verification"

        # Merge additional_policy_parts from customer config (extends the
        # extracted guarantee parts list with modern components not in older
        # policy documents).
        extra = self.component_config.additional_policy_parts.get(system_lower, [])
        if extra:
            policy_parts_list = list(policy_parts_list) + extra

        # Build lowered + umlaut-normalized policy parts lists for matching.
        # We keep both the raw-lower list (for display) and the normalized list
        # (for substring comparison) so that ü/u, ö/o, ä/a, accents don't
        # cause false negatives.
        policy_parts_lower = [p.lower() for p in policy_parts_list]
        policy_parts_norm = [_normalize_umlauts(p) for p in policy_parts_lower]

        if not component:
            # No specific component (e.g., keyword match without component_name).
            # Check if any policy part name appears in the item description.
            desc_norm = _normalize_umlauts(description.lower())
            for idx, policy_norm in enumerate(policy_parts_norm):
                if policy_norm in desc_norm:
                    return True, f"Description contains policy part '{policy_parts_lower[idx]}'"
            return None, (
                f"No specific component; description doesn't match "
                f"any of {len(policy_parts_list)} policy parts for '{system}'"
            )

        component_lower = component.lower()
        underscore_key = component_lower.replace(" ", "_")
        space_key = component_lower.replace("_", " ")

        # First: check if the component name itself directly matches a policy part.
        # This catches cases where the LLM returns the German name (e.g., "Ölpumpe")
        # that appears verbatim in the policy's covered parts list.
        for variant in (component_lower, underscore_key, space_key):
            variant_norm = _normalize_umlauts(variant)
            for idx, policy_norm in enumerate(policy_parts_norm):
                # Guard: short strings (≤3 chars) on EITHER side must be exact
                # matches — prevents cross-category false positives like
                # "asr" (3 chars) substring-matching "abgasrueckfuehrung"
                if len(variant_norm) <= 3 or len(policy_norm) <= 3:
                    if variant_norm == policy_norm:
                        return True, f"Component '{component}' found in policy list as '{policy_parts_lower[idx]}'"
                    continue
                if variant_norm in policy_norm or policy_norm in variant_norm:
                    return True, f"Component '{component}' found in policy list as '{policy_parts_lower[idx]}'"

        # Look up synonyms for this component type
        # Try multiple key variants: "egr valve" → "egr_valve", "egr valve"
        synonyms = (
            self.component_config.component_synonyms.get(component_lower)
            or self.component_config.component_synonyms.get(underscore_key)
            or self.component_config.component_synonyms.get(space_key)
        )

        # If synonyms exist, check them against the policy parts list
        if synonyms:
            for term in synonyms:
                term_norm = _normalize_umlauts(term.lower())
                for idx, policy_norm in enumerate(policy_parts_norm):
                    # Guard: short strings (≤3 chars) on EITHER side must be exact
                    # matches — prevents cross-category false positives like
                    # "asr" (3 chars) substring-matching "abgasrueckfuehrung"
                    if len(term_norm) <= 3 or len(policy_norm) <= 3:
                        if term_norm == policy_norm:
                            return True, f"Component '{component}' found in policy list as '{policy_parts_lower[idx]}'"
                        continue
                    if term_norm in policy_norm or policy_norm in term_norm:
                        return True, f"Component '{component}' found in policy list as '{policy_parts_lower[idx]}'"

        # Check distribution catch-all: if policy lists "Ensemble de distribution",
        # all timing/distribution components are implicitly covered
        if component_lower in self.component_config.distribution_catch_all_components:
            for idx, policy_norm in enumerate(policy_parts_norm):
                for keyword in self.component_config.distribution_catch_all_keywords:
                    if _normalize_umlauts(keyword) in policy_norm:
                        return True, (
                            f"Component '{component}' covered by distribution "
                            f"catch-all '{policy_parts_lower[idx]}'"
                        )

        # Also check if the original description contains any policy part name
        desc_norm = _normalize_umlauts(description.lower())
        for idx, policy_norm in enumerate(policy_parts_norm):
            if policy_norm in desc_norm:
                return True, f"Description contains policy part '{policy_parts_lower[idx]}'"

        # No match found through any method
        if not synonyms:
            if strict:
                return False, f"No synonym mapping for component '{component}' - strict mode"
            logger.info(
                "No COMPONENT_SYNONYMS entry for '%s' (system='%s') "
                "- needs LLM verification. Add synonyms to close this gap.",
                component,
                system,
            )
            return None, f"No synonym mapping for component '{component}' - needs LLM verification"

        # Component not found in policy list (synonyms exist but none matched)
        return False, (
            f"Component '{component}' (synonyms: {list(synonyms)[:3]}) "
            f"not found in policy's {matching_category} parts list "
            f"({len(policy_parts_list)} parts)"
        )

    def _match_labor_by_component_extraction(
        self,
        remaining: List[Dict[str, Any]],
        keyword_matched: List[LineItemCoverage],
        covered_categories: List[str],
        covered_components: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Extract component nouns from labor descriptions and match deterministically.

        Labor items like "AUS-/EINBAUEN OELKUEHLER" contain the component noun
        (OELKUEHLER) which can be matched against repair_context_keywords without
        needing the LLM.

        Only processes labor items in `remaining` (unmatched by prior stages).
        Matched items are appended to keyword_matched; unmatched stay in remaining.

        Args:
            remaining: Unmatched items (dicts) from prior stages.
            keyword_matched: Already-matched keyword items (labor matches appended here).
            covered_categories: Categories covered by the policy.
            covered_components: Dict mapping category to list of covered parts.

        Returns:
            Tuple of (updated keyword_matched, updated remaining).
        """
        if not self.component_config.repair_context_keywords:
            return keyword_matched, remaining

        labor_types = {"labor", "labour", "main d'oeuvre", "arbeit"}
        new_remaining = []
        covered_cats_lower = [c.lower() for c in covered_categories]

        for item in remaining:
            item_type = item.get("item_type", "").lower()
            if item_type not in labor_types:
                new_remaining.append(item)
                continue

            description = item.get("description", "")
            desc_lower = description.lower()
            if not desc_lower:
                new_remaining.append(item)
                continue

            # Find the longest matching keyword (longest = most specific)
            best_keyword = None
            best_component = None
            best_category = None
            for keyword, (component, category) in self.component_config.repair_context_keywords.items():
                if keyword in desc_lower and (best_keyword is None or len(keyword) > len(best_keyword)):
                    best_keyword = keyword
                    best_component = component
                    best_category = category

            if best_keyword is None:
                new_remaining.append(item)
                continue

            # Check if the category is covered
            if best_category.lower() not in covered_cats_lower:
                new_remaining.append(item)
                continue

            # Verify against policy list if available
            if covered_components:
                is_in_list, reason = self._is_component_in_policy_list(
                    component=best_component,
                    system=best_category,
                    covered_components=covered_components,
                    description=description,
                )
                if is_in_list is False:
                    # Confirmed not in policy list — leave for LLM
                    new_remaining.append(item)
                    continue
                if is_in_list is None:
                    # Uncertain — leave for LLM
                    new_remaining.append(item)
                    continue

            # Match: create a LineItemCoverage for this labor item
            tb = TraceBuilder()
            if item.get("_deferred_trace"):
                tb.extend(item["_deferred_trace"])
            tb.add("labor_component_extraction", TraceAction.MATCHED,
                   f"Labor description contains component keyword '{best_keyword}' "
                   f"-> {best_component} in {best_category}",
                   verdict=CoverageStatus.COVERED, confidence=0.80,
                   detail={"keyword": best_keyword,
                           "component": best_component,
                           "category": best_category})

            matched_item = LineItemCoverage(
                item_code=item.get("item_code"),
                description=description,
                item_type=item.get("item_type", ""),
                total_price=item.get("total_price") or 0.0,
                coverage_status=CoverageStatus.COVERED,
                coverage_category=best_category,
                matched_component=best_component,
                match_method=MatchMethod.KEYWORD,
                match_confidence=0.80,
                match_reasoning=(
                    f"Labor component extraction: '{best_keyword}' in description "
                    f"-> {best_component} ({best_category})"
                ),
                decision_trace=tb.build(),
                covered_amount=item.get("total_price") or 0.0,
                not_covered_amount=0.0,
            )
            keyword_matched.append(matched_item)
            logger.debug(
                "Labor component extraction: '%s' -> %s (%s) at 0.80",
                description[:60], best_component, best_category,
            )

        logger.debug(
            f"Labor component extraction: {len(remaining) - len(new_remaining)} "
            f"labor items matched out of {len(remaining)} remaining"
        )
        return keyword_matched, new_remaining

    def _match_by_part_number(
        self,
        items: List[Dict[str, Any]],
        covered_categories: List[str],
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Match items by exact part number lookup.

        Uses exact part number matching only (no keyword fallback).
        Keyword-based matching is handled by Stage 2 (KeywordMatcher)
        to ensure all keyword matches pass through Stage 2.5 policy
        list verification.

        Args:
            items: Line items to match
            covered_categories: Categories covered by the policy
            covered_components: Dict mapping category to list of covered parts
                               (used to verify specific components are covered)
            excluded_components: Dict mapping category to list of excluded parts

        Returns:
            Tuple of (matched items, unmatched items)
        """
        matched = []
        unmatched = []
        covered_components = covered_components or {}
        excluded_components = excluded_components or {}

        for item in items:
            item_code = item.get("item_code")
            description = item.get("description", "")

            # Stage 1.5 is pure part-number lookup only.
            # Keyword-based matching (lookup_by_description) has been moved to
            # Stage 2 so that all keyword matches pass through Stage 2.5 policy
            # list verification. This eliminates category conflicts between the
            # former by_keyword system and nsa_keyword_mappings.yaml.
            result = None
            if item_code:
                result = self.part_lookup.lookup(item_code)

            if not result or not result.found:
                _skip_tb = TraceBuilder()
                _skip_tb.add("part_number", TraceAction.SKIPPED,
                             "No part number match found",
                             detail={"part": item_code})
                item["_deferred_trace"] = _skip_tb.build()
                unmatched.append(item)
                continue

            # Gasket/seal check: when a keyword-based match contains a gasket
            # indicator (JOINT, DICHTUNG, etc.), the item is a sealing part FOR
            # the component, not the component itself.  Defer to LLM.
            if result.lookup_source and "keyword" in result.lookup_source:
                desc_upper = description.upper()
                gasket_indicator = next(
                    (ind for ind in self.component_config.gasket_seal_indicators if ind in desc_upper),
                    None,
                )
                if gasket_indicator:
                    logger.info(
                        "Gasket/seal indicator '%s' in '%s' — "
                        "deferring keyword match (%s/%s) to LLM",
                        gasket_indicator,
                        description,
                        result.system,
                        result.component,
                    )
                    item["_part_lookup_system"] = result.system
                    item["_part_lookup_component"] = (
                        result.component or result.component_description
                    )
                    # Stash deferred trace step for later stages to pick up
                    _tb = TraceBuilder()
                    _tb.add("part_number", TraceAction.DEFERRED,
                            f"Gasket/seal indicator '{gasket_indicator}' — deferred to LLM",
                            detail={"part": item_code, "lookup_source": result.lookup_source,
                                    "reason": "gasket_seal_deferral",
                                    "system": result.system,
                                    "component": result.component})
                    item["_deferred_trace"] = _tb.build()
                    unmatched.append(item)
                    continue

            # Check if the part's system matches a covered category
            is_category_covered = self._is_system_covered(result.system, covered_categories)

            # NEW: Check if the specific component is in the policy's parts list
            is_in_policy_list, policy_check_reason = self._is_component_in_policy_list(
                component=result.component,
                system=result.system,
                covered_components=covered_components,
                description=description,
            )

            # Use part_number from result (could be item_code or keyword match)
            part_ref = item_code or result.part_number

            exclusion_reason = None  # Set for NOT_COVERED branches

            if result.covered is False:
                # Part is explicitly excluded (e.g., accessory)
                status = CoverageStatus.NOT_COVERED
                exclusion_reason = "component_excluded"
                reasoning = (
                    f"Part {part_ref} is excluded: "
                    f"{result.note or result.component}"
                )
            elif is_category_covered and is_in_policy_list is True:
                # Category is covered AND component confirmed in policy's specific list
                status = CoverageStatus.COVERED
                reasoning = (
                    f"Part {part_ref} identified as "
                    f"'{result.component_description or result.component}' "
                    f"in category '{result.system}' (lookup: {result.lookup_source}). "
                    f"Policy check: {policy_check_reason}"
                )
            elif is_category_covered and is_in_policy_list is False:
                # Category is covered but the component is definitively NOT
                # in the policy's exhaustive parts list.  Before rejecting,
                # check if the component appears in another covered category's
                # list (cross-category match).
                cross_found, cross_category, cross_reason = (
                    self._find_component_across_categories(
                        component=result.component,
                        primary_system=result.system,
                        covered_components=covered_components,
                        excluded_components=excluded_components,
                        description=description,
                    )
                )
                if cross_found:
                    status = CoverageStatus.COVERED
                    reasoning = (
                        f"Part {part_ref} identified as "
                        f"'{result.component_description or result.component}' "
                        f"in category '{result.system}' (lookup: {result.lookup_source}). "
                        f"{cross_reason}"
                    )
                    # Override coverage_category to the cross-matched category
                    result = _dc_replace(result, system=cross_category)
                else:
                    # Component is in a covered category but not in the
                    # policy's specific parts list.  Defer to LLM — the
                    # policy list is representative, not exhaustive for
                    # component variants (e.g., Haldex fluid → axle_drive,
                    # trunk ECU → Motorsteuergerät family).
                    logger.info(
                        f"Deferring {part_ref} ({result.component}) to LLM: "
                        f"category '{result.system}' covered but component "
                        f"not in policy parts list. {policy_check_reason}"
                    )
                    item["_part_lookup_system"] = result.system
                    item["_part_lookup_component"] = result.component or result.component_description
                    unmatched.append(item)
                    continue
            elif is_category_covered and is_in_policy_list is None:
                # Category is covered but we couldn't determine whether the
                # component is in the policy list (synonym gap, no mapping).
                is_exact_pn = result.lookup_source and "keyword" not in result.lookup_source
                if is_exact_pn:
                    # High-trust part number match but can't verify against
                    # policy list.  Check exclusion list first.
                    is_excluded = self._is_component_excluded_by_policy(
                        result.component or "", result.system or "",
                        description, excluded_components,
                    )
                    if is_excluded:
                        status = CoverageStatus.NOT_COVERED
                        exclusion_reason = "component_excluded"
                        reasoning = (
                            f"Part {part_ref} identified as "
                            f"'{result.component_description or result.component}' "
                            f"in category '{result.system}' (exact part number) "
                            f"but explicitly excluded by policy"
                        )
                    else:
                        # Can't verify against policy list — defer to LLM
                        logger.info(
                            f"Deferring {part_ref} ({result.component}) to LLM: "
                            f"category '{result.system}' covered but policy list "
                            f"inconclusive (synonym gap). {policy_check_reason}"
                        )
                        item["_part_lookup_system"] = result.system
                        item["_part_lookup_component"] = result.component or result.component_description
                        unmatched.append(item)
                        continue
                else:
                    # Keyword-based match — defer to LLM for verification
                    logger.info(
                        f"Deferring {part_ref} ({result.component}) to LLM: "
                        f"category '{result.system}' covered but policy list "
                        f"inconclusive (keyword match). {policy_check_reason}"
                    )
                    item["_part_lookup_system"] = result.system
                    item["_part_lookup_component"] = result.component or result.component_description
                    unmatched.append(item)
                    continue
            else:
                # Category is not covered. Defer to LLM when:
                # 1. Item belongs to an ancillary category (labor,
                #    consumables, parts) whose coverage depends on
                #    whether it supports a covered repair, OR
                # 2. Item has repair context, OR
                # 3. The category has known aliases that might match.
                ancillary_categories = {"labor", "consumables", "parts"}
                is_ancillary = (
                    result.system and result.system.lower() in ancillary_categories
                )
                has_repair_ctx = bool(
                    item.get("repair_description")
                    or item.get("repair_context_description")
                )
                has_aliases = bool(
                    self.component_config.category_aliases.get(result.system.lower() if result.system else "")
                )
                if is_ancillary or has_repair_ctx or has_aliases:
                    logger.info(
                        f"Deferring {part_ref} ({result.system}) to LLM: "
                        f"ancillary={is_ancillary}, "
                        f"repair_ctx={has_repair_ctx}, aliases={has_aliases}"
                    )
                    item["_part_lookup_system"] = result.system
                    item["_part_lookup_component"] = (
                        result.component or result.component_description
                    )
                    unmatched.append(item)
                    continue

                status = CoverageStatus.NOT_COVERED
                exclusion_reason = "category_not_covered"
                reasoning = (
                    f"Part {part_ref} is '{result.component}' in category "
                    f"'{result.system}' which is not covered by this policy"
                )

            # Re-check: if keyword match marked a labor item as COVERED,
            # verify it doesn't match non-covered labor patterns (e.g. diagnostic)
            item_type_lower = (item.get("item_type") or "").lower()
            if status == CoverageStatus.COVERED and item_type_lower == "labor":
                labor_check = self.rule_engine.check_non_covered_labor(description)
                if labor_check is not None:
                    status = CoverageStatus.NOT_COVERED
                    exclusion_reason = "non_covered_labor"
                    reasoning = (
                        f"Part {part_ref} keyword-matched as "
                        f"'{result.component_description or result.component}' "
                        f"but labor matches non-covered pattern. "
                        f"{labor_check.match_reasoning}"
                    )

            # Build trace step for part number match
            pn_tb = TraceBuilder()
            pn_trace_detail: Dict[str, Any] = {
                "part": part_ref,
                "lookup_source": result.lookup_source,
                "system": result.system,
                "component": result.component,
            }
            if is_in_policy_list is not None:
                pn_trace_detail["policy_check"] = is_in_policy_list
                pn_trace_detail["policy_check_reason"] = policy_check_reason
            pn_action = (TraceAction.MATCHED if status == CoverageStatus.COVERED
                         else TraceAction.EXCLUDED)
            pn_tb.add("part_number", pn_action, reasoning,
                       verdict=status, confidence=0.95, detail=pn_trace_detail)

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
                    exclusion_reason=exclusion_reason,
                    decision_trace=pn_tb.build(),
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
                f"({status.value}, source={result.lookup_source}, in_policy={is_in_policy_list})"
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

        Payout (VAT, deductible) is computed by the screener, not here.

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
        total_covered_gross = 0.0
        parts_covered_gross = 0.0
        labor_covered_gross = 0.0
        total_not_covered = 0.0
        items_covered = 0
        items_not_covered = 0
        items_review_needed = 0

        for item in line_items:
            total_claimed += item.total_price

            if item.coverage_status == CoverageStatus.COVERED:
                # Track gross (100%) before coverage_percent reduction
                total_covered_gross += item.total_price
                if item.item_type == "parts":
                    parts_covered_gross += item.total_price
                elif item.item_type == "labor":
                    labor_covered_gross += item.total_price
                # Apply coverage percentage if available
                if coverage_percent is not None:
                    covered_amount = item.total_price * (coverage_percent / 100.0)
                else:
                    # Unknown rate: don't silently pay 100%.
                    # Track gross for audit but set covered_amount to 0.
                    logger.warning(
                        "coverage_percent is None — item '%s' (%.2f) "
                        "tracked in gross but covered_amount set to 0",
                        item.description, item.total_price,
                    )
                    covered_amount = 0.0
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

        return CoverageSummary(
            total_claimed=total_claimed,
            total_covered_before_excess=total_covered_before_excess,
            total_covered_gross=total_covered_gross,
            parts_covered_gross=parts_covered_gross,
            labor_covered_gross=labor_covered_gross,
            total_not_covered=total_not_covered,
            vat_amount=0.0,
            excess_amount=0.0,
            total_payable=total_covered_before_excess,
            items_covered=items_covered,
            items_not_covered=items_not_covered,
            items_review_needed=items_review_needed,
            coverage_percent=coverage_percent,
            coverage_percent_missing=coverage_percent is None,
        )

    # Generic labor descriptions that mean "work" without referencing specific parts.
    # Matched after stripping trailing punctuation (colon, period) so that
    # invoice-level variants like "ARBEIT:" or "Arbeit." are recognised.
    _GENERIC_LABOR_DESCRIPTIONS = {
        "main d'oeuvre", "main d'œuvre", "main-d'oeuvre", "main-d'œuvre",
        "arbeit", "arbeitszeit",
        "labor", "labour",
        "travail", "manodopera",
        "mécanicien", "mecanicien",  # French: "mechanic" (generic labor line)
    }

    @staticmethod
    def _is_generic_labor_description(description: str) -> bool:
        """Check if a description is a generic labor term.

        Normalises the description by lower-casing and stripping trailing
        punctuation so that invoice variants like ``"ARBEIT:"`` match the
        canonical set entry ``"arbeit"``.
        """
        normalized = description.lower().strip().rstrip(":.")
        return normalized in CoverageAnalyzer._GENERIC_LABOR_DESCRIPTIONS

    @staticmethod
    def _build_excluded_parts_index(
        items: List[LineItemCoverage],
    ) -> Dict[str, set]:
        """Build an index of NOT_COVERED parts for excluded-part guards.

        Returns a dict with:
        - "codes": set of cleaned item_codes (alphanumeric, upper, 4+ chars)
        - "components": set of matched_component values (lower-cased)
        """
        codes: set = set()
        components: set = set()
        for item in items:
            if item.coverage_status != CoverageStatus.NOT_COVERED:
                continue
            if item.item_type not in ("parts", "part", "piece"):
                continue
            if item.item_code:
                clean = "".join(c for c in item.item_code if c.isalnum()).upper()
                if len(clean) >= 4:
                    codes.add(clean)
            if item.matched_component:
                components.add(item.matched_component.lower())
        return {"codes": codes, "components": components}

    def _apply_labor_follows_parts(
        self,
        items: List[LineItemCoverage],
        repair_context: Optional[RepairContext] = None,
    ) -> List[LineItemCoverage]:
        """Promote labor items to COVERED if they reference covered parts.

        Three strategies are applied in order:

        1. **Part-number matching**: If a labor description contains a covered
           part's item_code as a substring, the labor is linked to that part.

        2. **Simple invoice rule**: When there is exactly 1 uncovered generic
           labor item (e.g. "Main d'œuvre") and at least 1 covered part, the
           labor is automatically linked to the first covered part's category.

        3. **Repair-context matching**: If a labor description matches a
           REPAIR_CONTEXT_KEYWORDS entry and covered parts exist in the same
           category, the labor is linked to that category's covered parts.

        Args:
            items: List of analyzed line items
            repair_context: Detected repair context from labor descriptions

        Returns:
            Updated list with labor items potentially promoted
        """
        labor_types = ("labor", "labour", "main d'oeuvre", "arbeit")

        # Collect all covered parts
        covered_parts: List[LineItemCoverage] = []
        covered_parts_by_code: Dict[str, LineItemCoverage] = {}
        for item in items:
            if (
                item.coverage_status == CoverageStatus.COVERED
                and item.item_type in ("parts", "part", "piece")
            ):
                covered_parts.append(item)
                if item.item_code:
                    clean_code = "".join(c for c in item.item_code if c.isalnum()).upper()
                    if len(clean_code) >= 4:
                        covered_parts_by_code[clean_code] = item

        # Strategy 1: Part-number matching
        if covered_parts_by_code:
            for item in items:
                if item.item_type not in labor_types:
                    continue
                if item.coverage_status == CoverageStatus.COVERED:
                    continue

                desc_upper = item.description.upper()
                desc_alphanum = "".join(c for c in desc_upper if c.isalnum() or c.isspace())

                for part_code, covered_part in covered_parts_by_code.items():
                    if part_code in desc_alphanum:
                        item.coverage_status = CoverageStatus.COVERED
                        item.coverage_category = covered_part.coverage_category
                        item.matched_component = covered_part.matched_component
                        item.match_confidence = 0.85
                        item.match_reasoning = (
                            f"Labor for covered part: {covered_part.description} "
                            f"(matched part number: {part_code})"
                        )
                        lfp_tb = TraceBuilder()
                        lfp_tb.extend(item.decision_trace)
                        lfp_tb.add("labor_follows_parts", TraceAction.PROMOTED,
                                   f"Labor linked to covered part via part number {part_code}",
                                   verdict=CoverageStatus.COVERED, confidence=0.85,
                                   detail={"strategy": "part_number_in_description",
                                           "linked_part_code": part_code})
                        item.decision_trace = lfp_tb.build()
                        logger.debug(
                            f"Promoted labor '{item.description}' to COVERED "
                            f"(linked to part number: {part_code})"
                        )
                        break

        # Strategy 2: Simple invoice rule
        # When the invoice has covered parts and generic labor entries
        # (descriptions that just say "work" / "Arbeit" / "Main d'œuvre"),
        # promote the labor — it's clearly the labour cost for those parts.
        # Only promote the SINGLE highest-priced generic labor item to avoid
        # over-counting when invoices list multiple generic "Arbeit" entries.
        if covered_parts:
            uncovered_generic_labor = [
                item for item in items
                if item.item_type in labor_types
                and item.coverage_status != CoverageStatus.COVERED
                and self._is_generic_labor_description(item.description)
            ]

            if uncovered_generic_labor:
                linked_part = covered_parts[0]
                # Pick only the highest-priced generic labor entry
                labor_item = max(uncovered_generic_labor, key=lambda x: x.total_price)

                # Proportionality guard: labor must not exceed 2x the total
                # covered parts value. Disproportionate labor is left for
                # human review to prevent false approvals.
                total_covered_parts_value = sum(
                    p.total_price for p in covered_parts
                )
                if (total_covered_parts_value > 0
                        and labor_item.total_price > 2.0 * total_covered_parts_value):
                    logger.info(
                        "Simple invoice rule: labor %.2f > 2x parts %.2f, "
                        "skipping promotion for '%s'",
                        labor_item.total_price, total_covered_parts_value,
                        labor_item.description,
                    )
                    sir_skip_tb = TraceBuilder()
                    sir_skip_tb.extend(labor_item.decision_trace)
                    sir_skip_tb.add("labor_follows_parts", TraceAction.SKIPPED,
                                    f"Simple invoice rule: labor {labor_item.total_price:.2f} > "
                                    f"2x parts {total_covered_parts_value:.2f} (disproportionate)",
                                    detail={"strategy": "simple_invoice_rule",
                                            "skip_reason": "proportionality_guard",
                                            "labor_price": labor_item.total_price,
                                            "covered_parts_value": total_covered_parts_value})
                    labor_item.decision_trace = sir_skip_tb.build()
                else:
                    labor_item.coverage_status = CoverageStatus.COVERED
                    labor_item.coverage_category = linked_part.coverage_category
                    labor_item.matched_component = linked_part.matched_component
                    labor_item.match_confidence = 0.75
                    labor_item.match_reasoning = (
                        f"Simple invoice rule: generic labor linked to covered part "
                        f"'{linked_part.description}' ({linked_part.coverage_category})"
                    )
                    sir_tb = TraceBuilder()
                    sir_tb.extend(labor_item.decision_trace)
                    sir_tb.add("labor_follows_parts", TraceAction.PROMOTED,
                               f"Simple invoice rule: linked to '{linked_part.description}'",
                               verdict=CoverageStatus.COVERED, confidence=0.75,
                               detail={"strategy": "simple_invoice_rule",
                                       "linked_to": linked_part.description})
                    labor_item.decision_trace = sir_tb.build()
                    logger.debug(
                        f"Promoted labor '{labor_item.description}' to COVERED "
                        f"via simple invoice rule (linked to '{linked_part.description}')"
                    )
                if len(uncovered_generic_labor) > 1:
                    skipped = len(uncovered_generic_labor) - 1
                    logger.debug(
                        f"Simple invoice rule: skipped {skipped} additional "
                        f"generic labor item(s) (only highest-priced promoted)"
                    )

        # Strategy 3: Repair-context keyword matching
        # If labor description matches REPAIR_CONTEXT_KEYWORDS and covered parts
        # exist in the same category, promote the labor.
        if covered_parts:
            excluded_idx = self._build_excluded_parts_index(items)
            excluded_codes = excluded_idx["codes"]
            excluded_components = excluded_idx["components"]

            for item in items:
                if item.item_type not in labor_types:
                    continue
                if item.coverage_status == CoverageStatus.COVERED:
                    continue

                desc_lower = item.description.lower()
                for keyword, (component, category) in self.component_config.repair_context_keywords.items():
                    if keyword in desc_lower:
                        # Guard: skip if labor's own code matches an excluded part
                        if item.item_code:
                            clean_labor_code = "".join(
                                c for c in item.item_code if c.isalnum()
                            ).upper()
                            if clean_labor_code in excluded_codes:
                                logger.debug(
                                    "Skipped promotion of '%s' -- item_code %s "
                                    "matches excluded part",
                                    item.description, clean_labor_code,
                                )
                                skip_tb = TraceBuilder()
                                skip_tb.extend(item.decision_trace)
                                skip_tb.add(
                                    "labor_follows_parts", TraceAction.SKIPPED,
                                    f"Excluded-part guard: item_code {clean_labor_code} "
                                    f"matches a NOT_COVERED part",
                                    detail={"reason": "excluded_part_guard",
                                            "strategy": "repair_context_keyword",
                                            "blocked_by": "item_code_match"},
                                )
                                item.decision_trace = skip_tb.build()
                                continue

                        # Guard: skip if keyword's component matches an excluded
                        # part's matched_component
                        if component.lower() in excluded_components:
                            logger.debug(
                                "Skipped promotion of '%s' -- keyword component "
                                "'%s' matches excluded part",
                                item.description, component,
                            )
                            skip_tb = TraceBuilder()
                            skip_tb.extend(item.decision_trace)
                            skip_tb.add(
                                "labor_follows_parts", TraceAction.SKIPPED,
                                f"Excluded-part guard: component '{component}' "
                                f"matches a NOT_COVERED part's component",
                                detail={"reason": "excluded_part_guard",
                                        "strategy": "repair_context_keyword",
                                        "blocked_by": "component_match"},
                            )
                            item.decision_trace = skip_tb.build()
                            continue

                        matching_covered = [
                            p for p in covered_parts
                            if p.coverage_category
                            and p.coverage_category.lower() == category.lower()
                        ]
                        if matching_covered:
                            item.coverage_status = CoverageStatus.COVERED
                            item.coverage_category = category
                            item.matched_component = component
                            item.match_confidence = 0.80
                            item.match_reasoning = (
                                f"Labor for covered repair: '{keyword}' matches "
                                f"{len(matching_covered)} covered {category} parts"
                            )
                            rck_tb = TraceBuilder()
                            rck_tb.extend(item.decision_trace)
                            rck_tb.add("labor_follows_parts", TraceAction.PROMOTED,
                                       f"Repair context keyword '{keyword}' linked to {category}",
                                       verdict=CoverageStatus.COVERED, confidence=0.80,
                                       detail={"strategy": "repair_context_keyword",
                                               "keyword": keyword,
                                               "linked_to": category})
                            item.decision_trace = rck_tb.build()
                            logger.debug(
                                f"Promoted labor '{item.description}' to COVERED "
                                f"via repair context (keyword: '{keyword}')"
                            )
                            break

        return items

    def _promote_ancillary_parts(
        self,
        items: List[LineItemCoverage],
        repair_context: Optional[RepairContext] = None,
    ) -> List[LineItemCoverage]:
        """Promote ancillary parts to COVERED when supporting a covered repair.

        NSA treats repairs as grouped jobs: gaskets, screws, and seals used
        alongside covered parts are included in coverage. This replicates
        that behavior when a covered repair context is detected.

        Args:
            items: List of analyzed line items
            repair_context: Detected repair context

        Returns:
            Updated list with ancillary parts potentially promoted
        """
        if not repair_context or not repair_context.is_covered:
            return items

        has_covered_parts = any(
            item.coverage_status == CoverageStatus.COVERED
            and item.item_type in ("parts", "part", "piece")
            for item in items
        )
        if not has_covered_parts:
            return items

        for item in items:
            if item.coverage_status == CoverageStatus.COVERED:
                continue
            if item.item_type not in ("parts", "part", "piece"):
                continue

            desc_lower = item.description.lower()
            for pattern in self.component_config.ancillary_keywords:
                if pattern in desc_lower:
                    item.coverage_status = CoverageStatus.COVERED
                    item.coverage_category = repair_context.primary_category
                    item.matched_component = repair_context.primary_component
                    item.match_confidence = 0.70
                    item.match_reasoning = (
                        f"Ancillary part for covered repair: "
                        f"'{pattern}' linked to {repair_context.primary_component}"
                    )
                    anc_tb = TraceBuilder()
                    anc_tb.extend(item.decision_trace)
                    anc_tb.add("ancillary_promotion", TraceAction.PROMOTED,
                               f"Ancillary part '{pattern}' linked to {repair_context.primary_component}",
                               verdict=CoverageStatus.COVERED, confidence=0.70,
                               detail={"pattern": pattern,
                                       "repair_component": repair_context.primary_component})
                    item.decision_trace = anc_tb.build()
                    logger.debug(
                        f"Promoted ancillary '{item.description}' to COVERED "
                        f"(pattern: '{pattern}', repair: {repair_context.primary_component})"
                    )
                    break

        return items

    def _promote_parts_for_covered_repair(
        self,
        items: List[LineItemCoverage],
        repair_context: Optional[RepairContext] = None,
    ) -> List[LineItemCoverage]:
        """Promote parts to COVERED when covered labor exists for the same repair.

        NSA treats repairs as grouped jobs: if the labor for an oil cooler
        replacement is covered, the associated replacement part is covered too,
        even if its description is ambiguous (e.g. 'Gehäuse, Ölfilter' for an
        oil cooler part).

        Conditions (all must be true):
        1. Repair context identifies a covered component in a covered category
        2. At least one LABOR item is COVERED in that category
        3. The uncovered PARTS item was classified by LLM (not by deterministic
           rules), indicating it wasn't a clear exclusion
        4. The parts item is in the same category as the repair context

        Args:
            items: List of analyzed line items
            repair_context: Detected repair context from labor descriptions

        Returns:
            Updated list with primary repair parts potentially promoted
        """
        if not repair_context or not repair_context.is_covered:
            return items
        if not repair_context.primary_component or not repair_context.primary_category:
            return items

        # Check if covered labor exists in the repair category
        has_covered_labor = any(
            item.coverage_status == CoverageStatus.COVERED
            and item.item_type in ("labor", "labour", "arbeit")
            and item.coverage_category
            and item.coverage_category.lower() == repair_context.primary_category.lower()
            for item in items
        )
        if not has_covered_labor:
            return items

        for item in items:
            if item.coverage_status == CoverageStatus.COVERED:
                continue
            if item.item_type not in ("parts", "part", "piece"):
                continue
            # Only override LLM decisions, not deterministic rule exclusions
            if item.match_method != MatchMethod.LLM:
                continue
            # Item must have been classified in the same category as the repair
            if (
                not item.coverage_category
                or item.coverage_category.lower()
                != repair_context.primary_category.lower()
            ):
                continue

            item.coverage_status = CoverageStatus.COVERED
            item.coverage_category = repair_context.primary_category
            item.matched_component = repair_context.primary_component
            item.match_confidence = 0.85
            item.match_reasoning = (
                f"Part promoted: covered labor for "
                f"'{repair_context.primary_component}' exists in "
                f"'{repair_context.primary_category}'; "
                f"LLM classification overridden by repair context"
            )
            item.covered_amount = item.total_price
            item.not_covered_amount = 0.0
            pfr_tb = TraceBuilder()
            pfr_tb.extend(item.decision_trace)
            pfr_tb.add("parts_for_repair", TraceAction.PROMOTED,
                       f"Covered labor exists for '{repair_context.primary_component}'",
                       verdict=CoverageStatus.COVERED, confidence=0.85,
                       detail={"repair_component": repair_context.primary_component,
                               "repair_category": repair_context.primary_category})
            item.decision_trace = pfr_tb.build()
            logger.info(
                f"Promoted part '{item.description}' to COVERED "
                f"(repair context: {repair_context.primary_component} in "
                f"{repair_context.primary_category})"
            )

        return items

    def _demote_labor_without_covered_parts(
        self,
        items: List[LineItemCoverage],
    ) -> List[LineItemCoverage]:
        """Demote labor items to NOT_COVERED when no parts are covered.

        Labor is ancillary — it is only covered when it supports a covered
        part.  If zero parts ended up covered (e.g. the primary part was
        excluded by a rule), any LLM-covered labor has no anchor and should
        be demoted.  This is the logical inverse of _apply_labor_follows_parts.

        Only overrides LLM decisions; deterministic rule/keyword matches are
        left untouched.

        Args:
            items: List of analyzed line items (after all promotion stages).

        Returns:
            Updated list with orphaned labor items demoted.
        """
        labor_types = ("labor", "labour", "main d'oeuvre", "arbeit")

        has_covered_parts = any(
            item.coverage_status == CoverageStatus.COVERED
            and item.item_type in ("parts", "part", "piece")
            for item in items
        )
        if has_covered_parts:
            return items

        for item in items:
            if item.item_type not in labor_types:
                continue
            if item.coverage_status != CoverageStatus.COVERED:
                continue
            # When zero parts are covered, ALL labor is access work —
            # regardless of how it was matched. Labor requires a covered
            # parts anchor.

            original_category = item.coverage_category
            item.coverage_status = CoverageStatus.NOT_COVERED
            item.exclusion_reason = "demoted_no_anchor"
            item.covered_amount = 0.0
            item.not_covered_amount = item.total_price
            item.match_reasoning += (
                " [DEMOTED: no covered parts in claim — "
                "labor cannot be covered without an anchoring part]"
            )
            dem_tb = TraceBuilder()
            dem_tb.extend(item.decision_trace)
            dem_tb.add("labor_demotion", TraceAction.DEMOTED,
                       "No covered parts in claim — labor has no anchor",
                       verdict=CoverageStatus.NOT_COVERED,
                       detail={"reason": "no_covered_parts_anchor"})
            item.decision_trace = dem_tb.build()
            logger.info(
                "Demoted labor '%s' (%s) from COVERED to NOT_COVERED: "
                "no covered parts to anchor it",
                item.description,
                original_category,
            )

        return items

    def _flag_nominal_price_labor(
        self,
        items: List[LineItemCoverage],
    ) -> List[LineItemCoverage]:
        """Flag nominal-price labor items as REVIEW_NEEDED.

        Mercedes-format invoices list labor operations with a nominal price
        (e.g. 1.00 CHF per operation code) where the real cost should be
        hours x hourly rate.  Since labor-hours parsing is not yet supported,
        these items are demoted to REVIEW_NEEDED so they don't silently enter
        the payout at incorrect amounts.

        Only affects labor items that:
        - have total_price > 0 and <= nominal_price_threshold
        - have an item_code (indicating an operation code, not generic labor)
        - are currently COVERED (leaves NOT_COVERED and REVIEW_NEEDED alone)

        Component identification (coverage_category, matched_component) is
        preserved for human reviewers.
        """
        labor_types = ("labor", "labour", "main d'oeuvre", "arbeit")
        threshold = self.config.nominal_price_threshold
        flagged_count = 0

        for item in items:
            if item.item_type not in labor_types:
                continue
            if item.coverage_status != CoverageStatus.COVERED:
                continue
            if not item.item_code or not item.item_code.strip():
                continue
            if item.total_price <= 0 or item.total_price > threshold:
                continue

            item.coverage_status = CoverageStatus.REVIEW_NEEDED
            item.match_confidence = 0.30
            item.exclusion_reason = "nominal_price_labor"
            item.covered_amount = 0.0
            item.not_covered_amount = item.total_price

            trace_tb = TraceBuilder()
            trace_tb.extend(item.decision_trace)
            trace_tb.add(
                "nominal_price_audit",
                TraceAction.DEMOTED,
                f"Labor item has nominal price ({item.total_price:.2f} CHF) "
                f"with operation code -- likely missing hourly rate; "
                f"flagged for review",
                verdict=CoverageStatus.REVIEW_NEEDED,
                confidence=0.30,
            )
            item.decision_trace = trace_tb.build()
            flagged_count += 1

        if flagged_count:
            logger.info(
                "Flagged %d nominal-price labor item(s) as REVIEW_NEEDED "
                "(threshold: %.2f)",
                flagged_count,
                threshold,
            )

        return items

    def _promote_items_for_covered_primary_repair(
        self,
        items: List[LineItemCoverage],
        primary_repair: "PrimaryRepairResult",
        repair_context: Optional["RepairContext"] = None,
        claim_id: str = "",
    ) -> List[LineItemCoverage]:
        """Promote line items when the primary repair is confirmed covered.

        Two modes of operation:

        **Mode 1 -- Zero-payout rescue:** When the repair context identifies a
        covered primary component but the per-item LLM analysis didn't
        recognise individual items as covered (because the specific part isn't
        in the policy's explicit list), this step promotes ALL LLM-classified
        items.  Only activates when **zero** non-trivial items are currently
        covered.

        **Mode 2 -- LLM labor relevance:** When some parts ARE covered but
        labor items were classified as NOT_COVERED by the LLM (because it
        evaluated labor without knowing the primary repair), this step makes
        ONE batch LLM call asking which labor items are mechanically necessary
        for the specific primary repair.  Only promotes items the LLM
        confirms as relevant.

        Args:
            items: List of analysed line items (after all stages).
            primary_repair: The determined primary repair result.
            repair_context: Detected repair context from labor descriptions.
            claim_id: Claim identifier for LLM audit trail.

        Returns:
            Updated list with orphaned items promoted when appropriate.
        """
        if not primary_repair or not primary_repair.is_covered:
            return items
        if not primary_repair.category:
            return items

        category = primary_repair.category
        labor_types = ("labor", "labour", "main d'oeuvre", "arbeit")

        has_covered = any(
            item.coverage_status == CoverageStatus.COVERED
            and item.total_price > 0
            for item in items
        )

        if not has_covered:
            # Mode 1: Zero-payout rescue — promote LLM-classified items
            # that belong to the same category as the primary repair.
            category_lower = category.lower()
            for item in items:
                if item.coverage_status != CoverageStatus.NOT_COVERED:
                    continue
                if item.match_method != MatchMethod.LLM:
                    continue
                # Skip items already excluded by a prior deterministic stage
                if item.exclusion_reason:
                    _skip_tb = TraceBuilder()
                    _skip_tb.extend(item.decision_trace)
                    _skip_tb.add("primary_repair_boost", TraceAction.SKIPPED,
                                 f"Zero-payout rescue skipped: item has exclusion_reason='{item.exclusion_reason}'",
                                 detail={"mode": "zero_payout_rescue",
                                         "skip_reason": "exclusion_reason",
                                         "exclusion_reason": item.exclusion_reason})
                    item.decision_trace = _skip_tb.build()
                    logger.info(
                        "Zero-payout rescue: skipping '%s' — exclusion_reason='%s'",
                        item.description, item.exclusion_reason,
                    )
                    continue
                # Only promote items whose category matches the primary
                # repair's category, or items with no category assigned
                # (benefit of the doubt).
                item_cat = (item.coverage_category or "").lower()
                if item_cat and item_cat != category_lower:
                    _skip_tb = TraceBuilder()
                    _skip_tb.extend(item.decision_trace)
                    _skip_tb.add("primary_repair_boost", TraceAction.SKIPPED,
                                 f"Zero-payout rescue skipped: item category '{item.coverage_category}' "
                                 f"does not match primary repair category '{category}'",
                                 detail={"mode": "zero_payout_rescue",
                                         "skip_reason": "category_mismatch",
                                         "item_category": item.coverage_category,
                                         "primary_category": category})
                    item.decision_trace = _skip_tb.build()
                    logger.info(
                        "Zero-payout rescue: skipping '%s' — category '%s' != primary '%s'",
                        item.description, item.coverage_category, category,
                    )
                    continue

                item.coverage_status = CoverageStatus.COVERED
                item.coverage_category = category
                if not item.matched_component:
                    item.matched_component = primary_repair.component
                item.covered_amount = item.total_price
                item.not_covered_amount = 0.0
                item.match_reasoning += (
                    f" [PROMOTED: primary repair '{primary_repair.component}' "
                    f"in '{category}' is covered by policy]"
                )
                prb_tb = TraceBuilder()
                prb_tb.extend(item.decision_trace)
                prb_tb.add("primary_repair_boost", TraceAction.PROMOTED,
                           f"Zero-payout rescue: primary repair '{primary_repair.component}' is covered",
                           verdict=CoverageStatus.COVERED,
                           detail={"mode": "zero_payout_rescue",
                                   "primary_component": primary_repair.component})
                item.decision_trace = prb_tb.build()
                logger.info(
                    "Promoted '%s' to COVERED via primary repair anchor "
                    "(%s in %s)",
                    item.description,
                    primary_repair.component,
                    category,
                )
        else:
            # Mode 2: LLM labor relevance — ask the LLM which labor items
            # are mechanically necessary for the identified primary repair.
            has_covered_parts = any(
                item.coverage_status == CoverageStatus.COVERED
                and item.item_type in ("parts", "part", "piece")
                for item in items
            )
            if not has_covered_parts:
                return items

            # Collect candidate labor items for LLM evaluation
            candidates = []  # (list_index, item) pairs
            for idx, item in enumerate(items):
                if item.item_type not in labor_types:
                    continue
                if item.coverage_status != CoverageStatus.NOT_COVERED:
                    continue
                # Only override LLM decisions, not deterministic rules
                if item.match_method != MatchMethod.LLM:
                    continue
                # Skip items that were explicitly excluded by a prior stage
                if item.exclusion_reason:
                    continue
                candidates.append((idx, item))

            if not candidates or self.llm_matcher is None:
                return items

            # Build covered parts context
            covered_parts_context = []
            for item in items:
                if (
                    item.coverage_status == CoverageStatus.COVERED
                    and item.item_type in ("parts", "part", "piece")
                ):
                    covered_parts_context.append({
                        "item_code": item.item_code or "",
                        "description": item.description,
                        "matched_component": item.matched_component or "",
                    })

            # Build labor items payload for the LLM
            labor_payload = [
                {
                    "index": idx,
                    "description": item.description,
                    "item_code": item.item_code,
                    "total_price": item.total_price,
                }
                for idx, item in candidates
            ]

            try:
                verdicts = self.llm_matcher.classify_labor_for_primary_repair(
                    labor_items=labor_payload,
                    primary_component=primary_repair.component,
                    primary_category=category,
                    covered_parts_in_claim=covered_parts_context,
                    claim_id=claim_id,
                )
            except Exception as e:
                logger.warning(
                    "LLM labor relevance call failed for claim %s: %s. "
                    "Leaving all candidates as NOT_COVERED.",
                    claim_id, e,
                )
                # Record failure in trace for each candidate
                for idx, item in candidates:
                    fail_tb = TraceBuilder()
                    fail_tb.extend(item.decision_trace)
                    fail_tb.add(
                        "primary_repair_boost_llm", TraceAction.SKIPPED,
                        f"LLM labor relevance failed: {e}",
                        detail={"mode": "llm_labor_relevance",
                                "error": str(e)},
                    )
                    item.decision_trace = fail_tb.build()
                return items

            # Index verdicts by list index for lookup
            verdict_by_idx = {v["index"]: v for v in verdicts}

            for idx, item in candidates:
                verdict = verdict_by_idx.get(idx)
                if verdict and verdict.get("is_relevant"):
                    # Promote
                    item.coverage_status = CoverageStatus.COVERED
                    item.coverage_category = category
                    if not item.matched_component:
                        item.matched_component = primary_repair.component
                    item.covered_amount = item.total_price
                    item.not_covered_amount = 0.0
                    item.match_reasoning += (
                        f" [PROMOTED: LLM confirmed labor is necessary for "
                        f"primary repair '{primary_repair.component}' in "
                        f"'{category}': {verdict.get('reasoning', '')}]"
                    )
                    prb2_tb = TraceBuilder()
                    prb2_tb.extend(item.decision_trace)
                    prb2_tb.add(
                        "primary_repair_boost_llm", TraceAction.PROMOTED,
                        f"LLM labor relevance: necessary for "
                        f"'{primary_repair.component}'",
                        verdict=CoverageStatus.COVERED,
                        detail={
                            "mode": "llm_labor_relevance",
                            "primary_component": primary_repair.component,
                            "llm_confidence": verdict.get("confidence", 0),
                            "llm_reasoning": verdict.get("reasoning", ""),
                        },
                    )
                    item.decision_trace = prb2_tb.build()
                    logger.info(
                        "Promoted labor '%s' to COVERED via LLM labor "
                        "relevance (%s in %s)",
                        item.description,
                        primary_repair.component,
                        category,
                    )
                else:
                    # Not promoted — record trace
                    reasoning = (
                        verdict.get("reasoning", "Not relevant")
                        if verdict else "Missing from LLM response"
                    )
                    skip_tb = TraceBuilder()
                    skip_tb.extend(item.decision_trace)
                    skip_tb.add(
                        "primary_repair_boost_llm", TraceAction.SKIPPED,
                        f"LLM labor relevance: not necessary for "
                        f"'{primary_repair.component}': {reasoning}",
                        detail={
                            "mode": "llm_labor_relevance",
                            "primary_component": primary_repair.component,
                            "llm_confidence": (
                                verdict.get("confidence", 0) if verdict else 0
                            ),
                            "llm_reasoning": reasoning,
                        },
                    )
                    item.decision_trace = skip_tb.build()
                    logger.debug(
                        "Labor '%s' NOT promoted — LLM says not relevant "
                        "for %s: %s",
                        item.description,
                        primary_repair.component,
                        reasoning,
                    )

        return items

    def _llm_determine_primary(
        self,
        all_items: List[LineItemCoverage],
        covered_components: Dict[str, List[str]],
        claim_id: str = "",
        repair_description: Optional[str] = None,
    ) -> Optional[PrimaryRepairResult]:
        """Use LLM to identify the primary repair component.

        Formats all line items for the LLM, calls determine_primary_repair(),
        then cross-checks the returned item's coverage_status from our own
        deterministic/LLM per-item analysis (we do NOT trust the LLM's coverage
        judgment for is_covered).

        Args:
            all_items: All analyzed line items
            covered_components: Policy's covered components by category
            claim_id: Claim identifier for logging
            repair_description: Damage/diagnostic context from claim documents

        Returns:
            PrimaryRepairResult on success, None on failure (triggers fallback).
        """
        # Format items for the LLM
        items_for_llm = []
        for idx, item in enumerate(all_items):
            items_for_llm.append({
                "index": idx,
                "description": item.description,
                "item_type": item.item_type,
                "total_price": item.total_price or 0.0,
                "coverage_status": item.coverage_status.value if item.coverage_status else "UNKNOWN",
                "coverage_category": item.coverage_category,
            })

        try:
            result = self.llm_matcher.determine_primary_repair(
                all_items=items_for_llm,
                covered_components=covered_components,
                claim_id=claim_id,
                repair_description=repair_description,
            )
        except Exception as e:
            logger.warning(
                "LLM primary repair determination failed for claim %s: %s",
                claim_id, e,
            )
            return None

        if result is None:
            return None

        primary_idx = result["primary_item_index"]
        source_item = all_items[primary_idx]

        # Cross-check: use OUR coverage_status, not the LLM's opinion
        is_covered = source_item.coverage_status == CoverageStatus.COVERED

        logger.info(
            "Primary repair (tier 0 LLM): '%s' (%s, %s, %.0f CHF, covered=%s) "
            "for claim %s",
            source_item.description,
            result.get("component") or source_item.matched_component,
            result.get("category") or source_item.coverage_category,
            source_item.total_price or 0,
            is_covered,
            claim_id,
        )

        return PrimaryRepairResult(
            component=result.get("component") or source_item.matched_component,
            category=result.get("category") or source_item.coverage_category,
            description=source_item.description,
            is_covered=is_covered,
            confidence=result.get("confidence", 0.80),
            determination_method="llm",
            source_item_index=primary_idx,
        )

    def _determine_primary_repair(
        self,
        all_items: List[LineItemCoverage],
        covered_components: Dict[str, List[str]],
        repair_context: Optional["RepairContext"] = None,
        claim_id: str = "",
        repair_description: Optional[str] = None,
    ) -> PrimaryRepairResult:
        """Determine the primary repair component using a three-tier approach.

        Tier 1a: highest-value COVERED parts item
        Tier 1b: highest-value COVERED item of any type
        Tier 1c: highest-value NOT_COVERED/REVIEW_NEEDED item with matched_component
        Tier 2:  repair context (from labor keyword detection)
        Tier 3:  LLM fallback (reserved for future use)

        Fallback: returns PrimaryRepairResult(determination_method="none"),
            which signals the screener to REFER.

        Args:
            all_items: All analyzed line items
            covered_components: Policy's covered components by category
            repair_context: Detected repair context from labor descriptions
            claim_id: Claim identifier for logging
            repair_description: Damage/diagnostic context from claim documents

        Returns:
            PrimaryRepairResult describing the primary component
        """
        # Tier 0: LLM-based determination (most accurate, 1 LLM call)
        if self.config.use_llm_primary_repair and self.llm_matcher:
            llm_primary = self._llm_determine_primary(
                all_items, covered_components, claim_id,
                repair_description=repair_description,
            )
            if llm_primary is not None:
                return llm_primary

        # Tier 1a: highest-value COVERED parts item
        best_covered_part: Optional[LineItemCoverage] = None
        best_covered_part_idx: Optional[int] = None
        for idx, item in enumerate(all_items):
            if (
                item.coverage_status == CoverageStatus.COVERED
                and item.item_type in ("parts", "part", "piece")
            ):
                if best_covered_part is None or (item.total_price or 0) > (best_covered_part.total_price or 0):
                    best_covered_part = item
                    best_covered_part_idx = idx

        if best_covered_part is not None:
            logger.info(
                "Primary repair (tier 1a): '%s' (%s, %.0f CHF) for claim %s",
                best_covered_part.description,
                best_covered_part.coverage_category,
                best_covered_part.total_price,
                claim_id,
            )
            return PrimaryRepairResult(
                component=best_covered_part.matched_component,
                category=best_covered_part.coverage_category,
                description=best_covered_part.description,
                is_covered=True,
                confidence=best_covered_part.match_confidence or 0.90,
                determination_method="deterministic",
                source_item_index=best_covered_part_idx,
            )

        # Tier 1b: highest-value COVERED item (any type, e.g. labor)
        best_covered_any: Optional[LineItemCoverage] = None
        best_covered_any_idx: Optional[int] = None
        for idx, item in enumerate(all_items):
            if item.coverage_status == CoverageStatus.COVERED and item.matched_component:
                if best_covered_any is None or (item.total_price or 0) > (best_covered_any.total_price or 0):
                    best_covered_any = item
                    best_covered_any_idx = idx

        if best_covered_any is not None:
            logger.info(
                "Primary repair (tier 1b): '%s' (%s, %.0f CHF) for claim %s",
                best_covered_any.description,
                best_covered_any.coverage_category,
                best_covered_any.total_price,
                claim_id,
            )
            return PrimaryRepairResult(
                component=best_covered_any.matched_component,
                category=best_covered_any.coverage_category,
                description=best_covered_any.description,
                is_covered=True,
                confidence=best_covered_any.match_confidence or 0.85,
                determination_method="deterministic",
                source_item_index=best_covered_any_idx,
            )

        # Tier 2: repair context (works even if component is not covered)
        if repair_context and repair_context.primary_component:
            # Cross-check: if no line items are covered, the repair context's
            # coverage determination was wrong (likely a false keyword match).
            effective_covered = repair_context.is_covered
            if effective_covered:
                any_covered = any(
                    item.coverage_status == CoverageStatus.COVERED
                    for item in all_items
                )
                if not any_covered:
                    logger.warning(
                        "Primary repair (tier 2): overriding is_covered=True→False "
                        "for claim %s — no covered line items", claim_id,
                    )
                    effective_covered = False

            logger.info(
                "Primary repair (tier 2): '%s' (%s, covered=%s) from repair context for claim %s",
                repair_context.primary_component,
                repair_context.primary_category,
                effective_covered,
                claim_id,
            )
            return PrimaryRepairResult(
                component=repair_context.primary_component,
                category=repair_context.primary_category,
                description=repair_context.source_description,
                is_covered=effective_covered,
                confidence=0.80,
                determination_method="repair_context",
            )

        # Tier 1c: highest-value NOT_COVERED or REVIEW_NEEDED item with
        # a matched_component — so the screener can make a verdict even
        # when nothing is covered.
        best_uncovered: Optional[LineItemCoverage] = None
        best_uncovered_idx: Optional[int] = None
        for idx, item in enumerate(all_items):
            if (
                item.coverage_status in (CoverageStatus.NOT_COVERED, CoverageStatus.REVIEW_NEEDED)
                and item.matched_component
            ):
                if best_uncovered is None or (item.total_price or 0) > (best_uncovered.total_price or 0):
                    best_uncovered = item
                    best_uncovered_idx = idx

        if best_uncovered is not None:
            logger.info(
                "Primary repair (tier 1c): '%s' (%s, %.0f CHF, NOT_COVERED) for claim %s",
                best_uncovered.description,
                best_uncovered.coverage_category,
                best_uncovered.total_price,
                claim_id,
            )
            return PrimaryRepairResult(
                component=best_uncovered.matched_component,
                category=best_uncovered.coverage_category,
                description=best_uncovered.description,
                is_covered=False,
                confidence=best_uncovered.match_confidence or 0.70,
                determination_method="deterministic",
                source_item_index=best_uncovered_idx,
            )

        # Tier 3: LLM fallback (reserved for future implementation)
        # For now, fall through to "none"

        # Fallback: could not determine primary repair
        logger.info(
            "Primary repair: could not determine for claim %s — will REFER",
            claim_id,
        )
        return PrimaryRepairResult(determination_method="none")

    def _is_in_excluded_list(
        self,
        item: LineItemCoverage,
        excluded_components: Dict[str, List[str]],
    ) -> bool:
        """Check if an item is in the excluded components list.

        Args:
            item: Line item to check
            excluded_components: Dict of category -> list of excluded parts

        Returns:
            True if the item matches an excluded component
        """
        if not excluded_components:
            return False

        description_lower = item.description.lower()

        for category, excluded_parts in excluded_components.items():
            for part in excluded_parts:
                part_lower = part.lower()
                # Check for substring match in description
                if part_lower in description_lower or description_lower in part_lower:
                    logger.debug(
                        f"Item '{item.description}' matches excluded part '{part}' "
                        f"in category '{category}'"
                    )
                    return True

        return False

    def _validate_llm_coverage_decision(
        self,
        item: LineItemCoverage,
        covered_components: Dict[str, List[str]],
        excluded_components: Dict[str, List[str]],
        repair_context: Optional[RepairContext] = None,
    ) -> LineItemCoverage:
        """Validate and potentially override LLM coverage decision.

        This method provides a safety net against LLM category inference errors.
        If the LLM approved a part based on category membership rather than
        explicit list matching, this validation will catch it.

        When a covered repair context is active, exclusion overrides are
        skipped for ancillary parts (gaskets, plugs, etc.) that support
        the covered repair.

        Args:
            item: Line item coverage result from LLM
            covered_components: Dict of category -> list of covered parts
            excluded_components: Dict of category -> list of excluded parts
            repair_context: Detected repair context (if any)

        Returns:
            Validated/corrected LineItemCoverage
        """
        if item.match_method != MatchMethod.LLM:
            return item

        val_tb = TraceBuilder()
        val_tb.extend(item.decision_trace)

        # Check if item is in excluded list -> force NOT_COVERED
        # BUT skip exclusion for labor items (excluded list targets replacement
        # parts, not access/disassembly labor) and for ancillary parts
        # supporting a covered repair.
        labor_types = ("labor", "labour", "main d'oeuvre", "arbeit")
        is_labor = item.item_type in labor_types
        if not is_labor and self._is_in_excluded_list(item, excluded_components):
            is_ancillary = repair_context and repair_context.is_covered and any(
                kw in item.description.lower() for kw in self.component_config.ancillary_keywords
            )
            if is_ancillary:
                logger.info(
                    f"Skipping exclusion for '{item.description}': "
                    f"ancillary to covered repair '{repair_context.primary_component}'"
                )
                val_tb.add("llm_validation", TraceAction.VALIDATED,
                           f"Exclusion skipped: ancillary to covered repair '{repair_context.primary_component}'",
                           detail={"check": "excluded_list_ancillary_skip"})
            else:
                original_status = item.coverage_status
                item.coverage_status = CoverageStatus.NOT_COVERED
                item.exclusion_reason = "component_excluded"
                item.match_reasoning += " [OVERRIDE: Component is in excluded list]"
                val_tb.add("llm_validation", TraceAction.OVERRIDDEN,
                           "Component is in excluded list",
                           verdict=CoverageStatus.NOT_COVERED,
                           detail={"check": "excluded_list"})
                item.decision_trace = val_tb.build()
                logger.info(
                    f"LLM validation override: '{item.description}' changed from "
                    f"{original_status.value} to NOT_COVERED (in excluded list)"
                )
                return item

        # If LLM said NOT_COVERED, check if a known synonym from
        # COMPONENT_SYNONYMS matches the description AND is confirmed
        # in the policy's parts list.  This catches cases where the LLM
        # missed a synonym that the deterministic lookup would have found.
        if item.coverage_status == CoverageStatus.NOT_COVERED:
            category = item.coverage_category
            if category:
                covered_categories = list(covered_components.keys())
                category_is_covered = self._is_system_covered(
                    category, covered_categories
                )

                if category_is_covered:
                    desc_lower = item.description.lower()
                    for comp_type, synonyms in self.component_config.component_synonyms.items():
                        for synonym in synonyms:
                            # Skip short synonyms to avoid false positives
                            if len(synonym) < 4:
                                continue
                            if synonym in desc_lower or desc_lower in synonym:
                                # Guard: if description contains a gasket/seal
                                # indicator, the synonym match is for a sealing
                                # part (e.g. "joint de soupape") not the
                                # component itself.  Don't override the LLM.
                                gasket_hit = any(
                                    ind.lower() in desc_lower
                                    for ind in self.component_config.gasket_seal_indicators
                                )
                                if gasket_hit:
                                    logger.info(
                                        "Synonym override blocked: gasket/seal"
                                        " indicator in '%s'",
                                        item.description,
                                    )
                                    continue

                                is_in_list, reason = (
                                    self._is_component_in_policy_list(
                                        comp_type,
                                        category,
                                        covered_components,
                                        item.description,
                                    )
                                )
                                if is_in_list is True:
                                    original_status = item.coverage_status
                                    item.coverage_status = CoverageStatus.COVERED
                                    item.matched_component = comp_type
                                    item.match_confidence = max(
                                        item.match_confidence or 0, 0.75
                                    )
                                    item.match_reasoning += (
                                        f" [SYNONYM OVERRIDE: '{item.description}'"
                                        f" matches '{synonym}' -> '{comp_type}',"
                                        f" confirmed in policy: {reason}]"
                                    )
                                    val_tb.add("llm_validation", TraceAction.OVERRIDDEN,
                                               f"Synonym override: '{synonym}' -> '{comp_type}', {reason}",
                                               verdict=CoverageStatus.COVERED,
                                               confidence=item.match_confidence,
                                               detail={"check": "synonym_override",
                                                       "component": comp_type,
                                                       "synonym": synonym,
                                                       "policy_reason": reason})
                                    item.decision_trace = val_tb.build()
                                    logger.info(
                                        "Post-LLM synonym override: '%s' changed"
                                        " from %s to COVERED (synonym '%s' ->"
                                        " '%s', %s)",
                                        item.description,
                                        original_status.value,
                                        synonym,
                                        comp_type,
                                        reason,
                                    )
                                    return item

        # If LLM said COVERED, only override when the category itself is
        # NOT covered.  The explicit component list is a known-incomplete
        # reference — absence from it does not mean the part is excluded.
        if item.coverage_status == CoverageStatus.COVERED:
            category = item.coverage_category
            covered_categories = list(covered_components.keys())
            category_is_covered = self._is_system_covered(category, covered_categories)

            if not category_is_covered:
                # LLM assigned a category that isn't in the policy at all
                item.coverage_status = CoverageStatus.REVIEW_NEEDED
                item.exclusion_reason = "category_not_covered"
                item.match_confidence = 0.45
                item.match_reasoning += (
                    f" [REVIEW: category '{category}' is not covered by policy]"
                )
                val_tb.add("llm_validation", TraceAction.OVERRIDDEN,
                           f"Category '{category}' is not covered by policy",
                           verdict=CoverageStatus.REVIEW_NEEDED,
                           confidence=0.45,
                           detail={"check": "category_not_covered", "category": category})
                logger.info(
                    f"LLM validation override: '{item.description}' changed from "
                    f"COVERED to REVIEW_NEEDED (category '{category}' not covered)"
                )
            else:
                val_tb.add("llm_validation", TraceAction.VALIDATED,
                           "LLM coverage decision confirmed",
                           verdict=item.coverage_status)
        else:
            val_tb.add("llm_validation", TraceAction.VALIDATED,
                       "No override needed",
                       verdict=item.coverage_status)

        item.decision_trace = val_tb.build()
        return item

    def analyze(
        self,
        claim_id: str,
        line_items: List[Dict[str, Any]],
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        vehicle_km: Optional[int] = None,
        coverage_scale: Optional[List[Dict[str, Any]]] = None,
        excess_percent: Optional[float] = None,
        excess_minimum: Optional[float] = None,
        claim_run_id: Optional[str] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
        on_llm_start: Optional[Callable[[int], None]] = None,
        vehicle_age_years: Optional[float] = None,
        age_threshold_years: Optional[int] = None,
        repair_description: Optional[str] = None,
    ) -> CoverageAnalysisResult:
        """Analyze coverage for all line items in a claim.

        Args:
            claim_id: Claim identifier
            line_items: List of line item dicts from claim_facts
            covered_components: Dict of category -> list of covered parts
            excluded_components: Dict of category -> list of excluded parts
            vehicle_km: Current vehicle odometer reading
            coverage_scale: List of {km_threshold, coverage_percent, age_coverage_percent?}
            excess_percent: Excess percentage from policy
            excess_minimum: Minimum excess amount
            claim_run_id: Optional claim run ID for output
            on_llm_progress: Callback for LLM progress updates (increment)
            on_llm_start: Callback when LLM matching starts (total count)
            vehicle_age_years: Vehicle age in years (for age-based coverage reduction)
            age_threshold_years: Age threshold for reduced coverage (from policy extraction, e.g., 8)

        Returns:
            CoverageAnalysisResult with all analysis data
        """
        start_time = time.time()
        covered_components = covered_components or {}
        excluded_components = excluded_components or {}

        # Determine coverage percentage from scale (with per-tier age adjustment)
        mileage_percent, effective_percent = self._determine_coverage_percent(
            vehicle_km,
            coverage_scale,
            vehicle_age_years=vehicle_age_years,
            age_threshold_years=age_threshold_years,
        )

        # Fall back to config default when no coverage_scale was extracted
        # (e.g., "Elite" policies with full coverage — no mileage tiering)
        if effective_percent is None and self.config.default_coverage_percent is not None:
            logger.info(
                "No coverage_scale for claim %s — using config default %s%%",
                claim_id,
                self.config.default_coverage_percent,
            )
            mileage_percent = self.config.default_coverage_percent
            effective_percent = self.config.default_coverage_percent

        # Extract covered categories
        covered_categories = self._extract_covered_categories(covered_components)

        # Extract repair context from labor descriptions
        # This helps avoid false consumable matches (e.g., "Ölkühler" vs "Ölfilter")
        repair_context = self._extract_repair_context(
            line_items, covered_components, excluded_components
        )

        # Log with age info if relevant
        age_info = ""
        if vehicle_age_years is not None and effective_percent != mileage_percent:
            age_info = f", age={vehicle_age_years:.1f}y, age-adjusted"
        logger.info(
            f"Analyzing {len(line_items)} items for claim {claim_id} "
            f"(coverage={effective_percent}%, km={vehicle_km}{age_info})"
        )

        # Stage 1: Rule engine
        # Skip consumable check if repair context indicates a covered component
        skip_consumable = repair_context.is_covered and repair_context.primary_component is not None
        rule_matched, remaining = self.rule_engine.batch_match(
            line_items,
            skip_consumable_check=skip_consumable,
            repair_context_component=repair_context.primary_component,
        )
        logger.debug(f"Rules matched: {len(rule_matched)}/{len(line_items)}")

        # Stage 1.5: Part number lookup (if workspace configured)
        part_matched = []
        if self.part_lookup and remaining:
            part_matched, remaining = self._match_by_part_number(
                remaining, covered_categories, covered_components,
                excluded_components,
            )
            logger.debug(f"Part numbers matched: {len(part_matched)}/{len(line_items)}")

        # Stage 2: Keyword matcher
        keyword_matched, remaining = self.keyword_matcher.batch_match(
            remaining,
            covered_categories=covered_categories,
            min_confidence=self.config.keyword_min_confidence,
        )
        logger.debug(f"Keywords matched: {len(keyword_matched)}/{len(line_items)}")

        # Stage 2+ : Labor component extraction
        # Extract component nouns from unmatched labor descriptions and match
        # deterministically (e.g., "AUS-/EINBAUEN OELKUEHLER" -> OELKUEHLER).
        if remaining and self.component_config.repair_context_keywords:
            keyword_matched, remaining = self._match_labor_by_component_extraction(
                remaining, keyword_matched, covered_categories, covered_components,
            )

        # Stage 2.5: Policy list verification for keyword matches
        # The keyword matcher only checks category-level coverage (e.g., "engine"
        # is covered). But some guarantees cover only specific parts within a
        # category. Verify keyword-matched items against the policy's parts list
        # and demote to LLM any item whose component is confirmed NOT in the list.
        if covered_components and keyword_matched:
            verified_keyword = []
            for item in keyword_matched:
                if item.coverage_status != CoverageStatus.COVERED:
                    verified_keyword.append(item)
                    continue

                is_in_list, reason = self._is_component_in_policy_list(
                    component=item.matched_component,
                    system=item.coverage_category,
                    covered_components=covered_components,
                    description=item.description,
                )

                if is_in_list is False:
                    # Confirmed NOT in policy list — demote to LLM
                    logger.info(
                        "Keyword match '%s' (%s) demoted to LLM: %s",
                        item.description,
                        item.matched_component,
                        reason,
                    )
                    # Carry existing trace forward and add deferral step
                    _plv_tb = TraceBuilder()
                    _plv_tb.extend(item.decision_trace)
                    _plv_tb.add("policy_list_check", TraceAction.DEFERRED,
                                f"Demoted to LLM: {reason}",
                                detail={"result": False, "reason": reason})
                    demoted_item = {
                        "item_code": item.item_code,
                        "description": item.description,
                        "item_type": item.item_type,
                        "total_price": item.total_price,
                        "_deferred_trace": _plv_tb.build(),
                    }
                    remaining.append(demoted_item)
                elif is_in_list is None:
                    # Uncertain — component not found in policy list synonyms.
                    # Demote to LLM regardless of whether matched_component
                    # is set, to close the synonym-gap false-approval pathway.
                    logger.info(
                        "Keyword match '%s' (%s) demoted to LLM (uncertain): %s",
                        item.description,
                        item.matched_component or "no component",
                        reason,
                    )
                    _plv_tb2 = TraceBuilder()
                    _plv_tb2.extend(item.decision_trace)
                    _plv_tb2.add("policy_list_check", TraceAction.DEFERRED,
                                 f"Uncertain (synonym gap), demoted to LLM: {reason}",
                                 detail={"result": None, "reason": reason,
                                         "matched_component": item.matched_component})
                    demoted_item2 = {
                        "item_code": item.item_code,
                        "description": item.description,
                        "item_type": item.item_type,
                        "total_price": item.total_price,
                        "_deferred_trace": _plv_tb2.build(),
                    }
                    remaining.append(demoted_item2)
                else:
                    # is_in_list is True — confirmed in policy list, keep
                    if is_in_list is True:
                        item.match_reasoning += f". Policy check: {reason}"
                        # Append validation trace step
                        plv_tb = TraceBuilder()
                        plv_tb.extend(item.decision_trace)
                        plv_tb.add("policy_list_check", TraceAction.VALIDATED,
                                   f"Confirmed in policy list: {reason}",
                                   detail={"result": True, "reason": reason})
                        item.decision_trace = plv_tb.build()
                    verified_keyword.append(item)

            demoted = len(keyword_matched) - len(verified_keyword)
            if demoted:
                logger.info(
                    f"Policy list verification: {demoted} keyword match(es) "
                    f"demoted to LLM out of {len(keyword_matched)}"
                )
            keyword_matched = verified_keyword

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
                    self.llm_matcher = LLMMatcher(
                        config=LLMMatcherConfig(max_concurrent=self.config.llm_max_concurrent),
                    )

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

                # Enrich items with repair context description for LLM
                # Priority: extraction-level repair_description > labor keyword context
                labor_context_desc = repair_context.source_description
                # Collect deferred trace steps (from prior stages) before LLM
                deferred_traces = []
                for item in items_for_llm:
                    if not item.get("repair_context_description"):
                        item["repair_context_description"] = (
                            item.get("repair_description")
                            or labor_context_desc
                            or None
                        )

                    # Pass part-lookup context so the LLM knows the item
                    # was already identified as belonging to a category.
                    lookup_sys = item.pop("_part_lookup_system", None)
                    lookup_comp = item.pop("_part_lookup_component", None)
                    if lookup_sys:
                        hint = (
                            f"Pre-identified as '{lookup_comp}' "
                            f"in category '{lookup_sys}'."
                        )
                        existing = item.get("repair_context_description") or ""
                        item["repair_context_description"] = (
                            f"{hint} {existing}".strip()
                        )
                    # Extract deferred trace for merge after LLM
                    deferred_traces.append(item.pop("_deferred_trace", None))

                llm_matched = self.llm_matcher.batch_match(
                    items_for_llm,
                    covered_categories=covered_categories,
                    covered_components=covered_components,
                    excluded_components=excluded_components,
                    claim_id=claim_id,
                    on_progress=on_llm_progress,
                    covered_parts_in_claim=covered_parts_in_claim,
                )

                # Merge deferred trace steps from prior stages into LLM results
                for idx, llm_item in enumerate(llm_matched):
                    prior = deferred_traces[idx] if idx < len(deferred_traces) else None
                    if prior:
                        merged_tb = TraceBuilder()
                        merged_tb.extend(prior)
                        merged_tb.extend(llm_item.decision_trace)
                        llm_item.decision_trace = merged_tb.build()

                # Validate LLM decisions against explicit policy lists
                llm_matched = [
                    self._validate_llm_coverage_decision(
                        item, covered_components, excluded_components,
                        repair_context=repair_context,
                    )
                    for item in llm_matched
                ]

            # Mark skipped items as review needed
            for item in skipped:
                skip_tb = TraceBuilder()
                skip_tb.extend(item.get("_deferred_trace") if isinstance(item, dict) else None)
                skip_tb.add("llm", TraceAction.SKIPPED,
                            "Skipped due to LLM item limit",
                            verdict=CoverageStatus.REVIEW_NEEDED, confidence=0.0,
                            detail={"reason": "llm_item_limit", "limit": self.config.llm_max_items})
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
                        decision_trace=skip_tb.build(),
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price") or 0.0,
                    )
                )
        elif remaining:
            # LLM disabled, mark all remaining as review needed
            for item in remaining:
                dis_tb = TraceBuilder()
                dis_tb.extend(item.get("_deferred_trace") if isinstance(item, dict) else None)
                dis_tb.add("llm", TraceAction.SKIPPED,
                            "LLM fallback disabled",
                            verdict=CoverageStatus.REVIEW_NEEDED, confidence=0.0,
                            detail={"reason": "llm_disabled"})
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
                        decision_trace=dis_tb.build(),
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price") or 0.0,
                    )
                )

        # Combine all results
        all_items = rule_matched + part_matched + keyword_matched + llm_matched

        # Apply labor-follows-parts linking
        all_items = self._apply_labor_follows_parts(all_items, repair_context=repair_context)

        # Promote ancillary parts for covered repairs
        all_items = self._promote_ancillary_parts(all_items, repair_context=repair_context)

        # Promote parts when covered labor exists for the same repair
        all_items = self._promote_parts_for_covered_repair(all_items, repair_context=repair_context)

        # Demote orphaned labor: if no parts are covered, labor has no anchor
        all_items = self._demote_labor_without_covered_parts(all_items)

        # Flag nominal-price labor (suspected operation codes without real pricing)
        all_items = self._flag_nominal_price_labor(all_items)

        # Determine primary repair component (three-tier approach)
        primary_repair = self._determine_primary_repair(
            all_items, covered_components, repair_context, claim_id,
            repair_description=repair_description,
        )

        # Promote orphaned items when the primary repair is confirmed covered.
        # This reverses demotion cascades where the LLM couldn't match
        # individual items to the policy's explicit parts list but the
        # repair-context tier identifies the repair as covered.
        all_items = self._promote_items_for_covered_primary_repair(
            all_items, primary_repair, repair_context, claim_id=claim_id,
        )

        # Calculate summary using effective (age-adjusted) coverage percent
        summary = self._calculate_summary(
            all_items,
            coverage_percent=effective_percent,
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
            vehicle_age_years=vehicle_age_years,
            coverage_percent=mileage_percent,
            coverage_percent_effective=effective_percent,
            age_threshold_years=age_threshold_years,
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

        # Convert internal RepairContext to PrimaryRepairResult for persistence
        repair_context_result = None
        if repair_context and repair_context.primary_component:
            repair_context_result = PrimaryRepairResult(
                component=repair_context.primary_component,
                category=repair_context.primary_category,
                is_covered=repair_context.is_covered,
                description=repair_context.source_description,
                determination_method="repair_context",
            )

        return CoverageAnalysisResult(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            generated_at=datetime.utcnow(),
            inputs=inputs,
            line_items=all_items,
            summary=summary,
            primary_repair=primary_repair,
            repair_context=repair_context_result,
            metadata=metadata,
        )
