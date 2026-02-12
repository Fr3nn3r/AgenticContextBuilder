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
    DecisionSource,
    LineItemCoverage,
    MatchMethod,
    PrimaryRepairResult,
    TraceAction,
    TraceStep,
)
from context_builder.coverage.post_processing import (
    apply_labor_linkage,
    build_excluded_parts_index,
    demote_orphan_labor,
    flag_nominal_price_labor,
    validate_llm_coverage_decision,
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

    # Items per LLM call in batch classification (default 15).
    # All items are classified -- no hard cap.  The batching is handled
    # inside classify_items(); this value is forwarded to LLMMatcherConfig.
    llm_classification_batch_size: int = 15

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
    use_llm_primary_repair: bool = True

    # Nominal-price labor threshold: labor items at or below this price
    # with an item_code are flagged REVIEW_NEEDED (suspected operation
    # codes where the real cost is hours x rate, not yet supported).
    nominal_price_threshold: float = 2.0

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AnalyzerConfig":
        """Create config from dictionary."""
        kwargs: Dict[str, Any] = dict(
            keyword_min_confidence=config.get("keyword_min_confidence", 0.80),
            use_llm_fallback=config.get("use_llm_fallback", True),
            llm_classification_batch_size=config.get(
                "llm_classification_batch_size",
                config.get("llm_max_items", 15),  # backwards-compat with old key
            ),
            llm_max_concurrent=config.get("llm_max_concurrent", 3),
            config_version=config.get("config_version", "1.0"),
            default_coverage_percent=config.get("default_coverage_percent"),
            use_llm_primary_repair=config.get("use_llm_primary_repair", True),
            nominal_price_threshold=config.get("nominal_price_threshold", 2.0),
        )
        return cls(**kwargs)


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
        # Forward batch size from analyzer config to LLM config
        llm_config.classification_batch_size = analyzer_config.llm_classification_batch_size

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
                             detail={"part": item_code},
                             decision_source=DecisionSource.PART_NUMBER)
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
                                    "component": result.component},
                            decision_source=DecisionSource.PART_NUMBER)
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
                       verdict=status, confidence=0.95, detail=pn_trace_detail,
                       decision_source=DecisionSource.PART_NUMBER)

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
        """Determine the primary repair component (LLM-first, 2-tier).

        Tier 1: LLM-based determination (most accurate, 1 LLM call).
        Tier 2: Deterministic fallback -- highest-value covered part.

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
        primary_result: Optional[PrimaryRepairResult] = None

        # Tier 1: LLM-based determination
        if self.config.use_llm_primary_repair and self.llm_matcher:
            primary_result = self._llm_determine_primary(
                all_items, covered_components, claim_id,
                repair_description=repair_description,
            )

        # Tier 2: Deterministic fallback -- highest-value covered part
        if primary_result is None:
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
                    "Primary repair (deterministic fallback): '%s' (%s, %.0f CHF) for claim %s",
                    best_covered_part.description,
                    best_covered_part.coverage_category,
                    best_covered_part.total_price,
                    claim_id,
                )
                primary_result = PrimaryRepairResult(
                    component=best_covered_part.matched_component,
                    category=best_covered_part.coverage_category,
                    description=best_covered_part.description,
                    is_covered=True,
                    confidence=best_covered_part.match_confidence or 0.90,
                    determination_method="deterministic",
                    source_item_index=best_covered_part_idx,
                )

        # Fallback: could not determine primary repair
        if primary_result is None:
            logger.info(
                "Primary repair: could not determine for claim %s -- will REFER",
                claim_id,
            )
            return PrimaryRepairResult(determination_method="none")

        # Post-check: override coverage if primary repair matches an exclusion pattern
        if primary_result.is_covered:
            matched = self.rule_engine.matches_exclusion_pattern(primary_result.component)
            if matched is None:
                matched = self.rule_engine.matches_exclusion_pattern(primary_result.description)
            if matched is not None:
                logger.warning(
                    "Primary repair exclusion override for claim %s: component='%s' "
                    "matches exclusion pattern '%s' -- setting is_covered=False",
                    claim_id, primary_result.component, matched,
                )
                primary_result = primary_result.model_copy(update={"is_covered": False})

        return primary_result

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

        # Stage 2: Generate advisory hints (no coverage decisions)
        # Part-number and keyword hints are passed to the LLM as context.
        keyword_hints = self.keyword_matcher.generate_hints(remaining)
        keyword_hints_count = sum(1 for h in keyword_hints if h is not None)
        logger.debug(
            f"Keyword hints generated: {keyword_hints_count}/{len(remaining)}"
        )

        part_number_hints = []
        if self.part_lookup:
            for item in remaining:
                hint = self.part_lookup.lookup_as_hint(
                    item_code=item.get("item_code"),
                    description=item.get("description", ""),
                )
                part_number_hints.append(hint)
        else:
            part_number_hints = [None] * len(remaining)
        pn_hints_count = sum(1 for h in part_number_hints if h is not None)
        logger.debug(
            f"Part-number hints generated: {pn_hints_count}/{len(remaining)}"
        )

        # Stage 3: LLM-first classification (all remaining items)
        llm_matched = []
        keyword_matched = []  # No keyword-level decisions in LLM-first mode
        part_matched = []  # No part-number-level decisions in LLM-first mode

        if remaining and self.config.use_llm_fallback:
            if self.llm_matcher is None:
                self.llm_matcher = LLMMatcher(
                    config=LLMMatcherConfig(
                        max_concurrent=self.config.llm_max_concurrent,
                        classification_batch_size=self.config.llm_classification_batch_size,
                    ),
                )

            if on_llm_start:
                on_llm_start(len(remaining))

            # Collect covered parts from rule stage for LLM context
            covered_parts_in_claim = []
            for item in rule_matched:
                if (
                    item.coverage_status == CoverageStatus.COVERED
                    and item.item_type in ("parts", "part", "piece")
                ):
                    covered_parts_in_claim.append({
                        "item_code": item.item_code or "",
                        "description": item.description,
                        "matched_component": item.matched_component or "",
                    })

            # Enrich items with repair context description
            labor_context_desc = repair_context.source_description
            for item in remaining:
                if not item.get("repair_context_description"):
                    item["repair_context_description"] = (
                        item.get("repair_description")
                        or labor_context_desc
                        or None
                    )

            llm_matched = self.llm_matcher.classify_items(
                items=remaining,
                covered_components=covered_components,
                excluded_components=excluded_components,
                keyword_hints=keyword_hints,
                part_number_hints=part_number_hints,
                claim_id=claim_id,
                on_progress=on_llm_progress,
                covered_parts_in_claim=covered_parts_in_claim,
                repair_context_description=labor_context_desc,
            )

            # Validate LLM decisions against explicit policy lists
            llm_matched = [
                validate_llm_coverage_decision(
                    item, covered_components, excluded_components,
                    repair_context=repair_context,
                    is_in_excluded_list=self._is_in_excluded_list,
                    is_system_covered=self._is_system_covered,
                    ancillary_keywords=self.component_config.ancillary_keywords,
                )
                for item in llm_matched
            ]
        elif remaining:
            # LLM disabled, mark all remaining as review needed
            for item in remaining:
                dis_tb = TraceBuilder()
                dis_tb.add("llm", TraceAction.SKIPPED,
                            "LLM classification disabled",
                            verdict=CoverageStatus.REVIEW_NEEDED, confidence=0.0,
                            detail={"reason": "llm_disabled"},
                            decision_source=DecisionSource.LLM)
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
                        match_reasoning="LLM classification disabled",
                        decision_trace=dis_tb.build(),
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price") or 0.0,
                    )
                )

        # Combine all results
        all_items = rule_matched + part_matched + keyword_matched + llm_matched

        # Post-processing pipeline (LLM-first):
        # 1. Primary repair determination
        primary_repair = self._determine_primary_repair(
            all_items, covered_components, repair_context, claim_id,
            repair_description=repair_description,
        )

        # 2. LLM labor linkage (part-number matching + LLM for rest)
        all_items = apply_labor_linkage(
            all_items, llm_matcher=self.llm_matcher,
            repair_context=repair_context,
            primary_repair=primary_repair, claim_id=claim_id,
        )

        # 3. Orphan labor demotion (safety net)
        all_items = demote_orphan_labor(all_items, primary_repair=primary_repair)

        # 4. Nominal-price labor flagging (audit rule)
        all_items = flag_nominal_price_labor(
            all_items, threshold=self.config.nominal_price_threshold,
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
            keyword_hints_generated=keyword_hints_count,
            part_number_hints_generated=pn_hints_count,
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
