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
    PrimaryRepairResult,
)

logger = logging.getLogger(__name__)

# Gasket/seal indicators: when these terms appear in a description alongside a
# component keyword, the item is a sealing part FOR the component, not the
# component itself.  E.g. "Joint du vilebrequin" = crankshaft seal, not crankshaft.
# Used in _match_by_part_number to defer keyword matches to LLM verification.
_GASKET_SEAL_INDICATORS = {"JOINT", "DICHTUNG", "SOUFFLET", "GAINE"}


def _find_sibling(config_path: Path, pattern: str) -> Optional[Path]:
    """Find a sibling file matching a glob pattern."""
    matches = list(config_path.parent.glob(pattern))
    return matches[0] if matches else None


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

    @classmethod
    def default(cls) -> "ComponentConfig":
        """Return empty defaults (no vocabulary loaded)."""
        return cls(
            component_synonyms={},
            category_aliases={},
            repair_context_keywords={},
            distribution_catch_all_components=set(),
            distribution_catch_all_keywords=[],
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

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AnalyzerConfig":
        """Create config from dictionary."""
        return cls(
            keyword_min_confidence=config.get("keyword_min_confidence", 0.80),
            use_llm_fallback=config.get("use_llm_fallback", True),
            llm_max_items=config.get("llm_max_items", 35),
            llm_max_concurrent=config.get("llm_max_concurrent", 3),
            config_version=config.get("config_version", "1.0"),
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
            for keyword, (component, category) in self.component_config.repair_context_keywords.items():
                if keyword in description:
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
                            # If so, treat as uncertain (needs human review).
                            covered_cats = self._extract_covered_categories(covered_components)
                            cat_covered = self._is_system_covered(category, covered_cats)

                            if cat_covered and not self._is_component_excluded_by_policy(
                                component, category, item.get("description", ""),
                                excluded_components or {},
                            ):
                                context.is_covered = None  # uncertain
                                logger.info(
                                    "Repair context: '%s' in '%s' — category covered, "
                                    "part not listed, NOT excluded → uncertain",
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

        # Build lowered policy parts list for matching
        policy_parts_lower = [p.lower() for p in policy_parts_list]

        if not component:
            # No specific component (e.g., keyword match without component_name).
            # Check if any policy part name appears in the item description.
            desc_lower = description.lower()
            for policy_part in policy_parts_lower:
                if policy_part in desc_lower:
                    return True, f"Description contains policy part '{policy_part}'"
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
            for policy_part in policy_parts_lower:
                if variant in policy_part or policy_part in variant:
                    return True, f"Component '{component}' found in policy list as '{policy_part}'"

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
                for policy_part in policy_parts_lower:
                    if term in policy_part or policy_part in term:
                        return True, f"Component '{component}' found in policy list as '{policy_part}'"

        # Check distribution catch-all: if policy lists "Ensemble de distribution",
        # all timing/distribution components are implicitly covered
        if component_lower in self.component_config.distribution_catch_all_components:
            for policy_part in policy_parts_lower:
                for keyword in self.component_config.distribution_catch_all_keywords:
                    if keyword in policy_part:
                        return True, (
                            f"Component '{component}' covered by distribution "
                            f"catch-all '{policy_part}'"
                        )

        # Also check if the original description contains any policy part name
        desc_lower = description.lower()
        for policy_part in policy_parts_lower:
            if policy_part in desc_lower:
                return True, f"Description contains policy part '{policy_part}'"

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
    ) -> Tuple[List[LineItemCoverage], List[Dict[str, Any]]]:
        """Match items by part number lookup.

        First tries exact part number lookup, then falls back to
        description-based keyword lookup from assumptions.json.

        Args:
            items: Line items to match
            covered_categories: Categories covered by the policy
            covered_components: Dict mapping category to list of covered parts
                               (used to verify specific components are covered)

        Returns:
            Tuple of (matched items, unmatched items)
        """
        matched = []
        unmatched = []
        covered_components = covered_components or {}

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

            # If description keyword lookup fails, try item_code keyword lookup
            # This catches cases like "ZAHNRIEMENKIT" where the part name is in item_code
            # but the description only contains part numbers like "INA 13938585..."
            if (not result or not result.found) and item_code:
                result = self.part_lookup.lookup_by_description(item_code)

            if not result or not result.found:
                unmatched.append(item)
                continue

            # Gasket/seal check: when a keyword-based match contains a gasket
            # indicator (JOINT, DICHTUNG, etc.), the item is a sealing part FOR
            # the component, not the component itself.  Defer to LLM.
            if result.lookup_source and "keyword" in result.lookup_source:
                desc_upper = description.upper()
                gasket_indicator = next(
                    (ind for ind in _GASKET_SEAL_INDICATORS if ind in desc_upper),
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

            if result.covered is False:
                # Part is explicitly excluded (e.g., accessory)
                status = CoverageStatus.NOT_COVERED
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
                # Category is covered but synonym check didn't confirm the
                # component in the policy's specific list.  This does NOT mean
                # the component is excluded — the policy may simply not
                # enumerate every part.  Defer to LLM for verification.
                logger.info(
                    f"Deferring {part_ref} ({result.component}) to LLM: "
                    f"category '{result.system}' covered but synonym check "
                    f"inconclusive. {policy_check_reason}"
                )
                item["_part_lookup_system"] = result.system
                item["_part_lookup_component"] = result.component or result.component_description
                unmatched.append(item)
                continue
            elif is_category_covered and is_in_policy_list is None:
                # Category covered but can't verify specific component
                # Defer to LLM for policy list verification
                logger.info(
                    f"Deferring {part_ref} ({result.component}) to LLM: "
                    f"category '{result.system}' covered but component unverifiable. "
                    f"{policy_check_reason}"
                )
                # Enrich item with context for LLM
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

    # Generic labor descriptions that mean "work" without referencing specific parts
    _GENERIC_LABOR_DESCRIPTIONS = {
        "main d'oeuvre", "main d'œuvre", "main-d'oeuvre", "main-d'œuvre",
        "arbeit", "arbeitszeit",
        "labor", "labour",
        "travail", "manodopera",
    }

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
                        logger.debug(
                            f"Promoted labor '{item.description}' to COVERED "
                            f"(linked to part number: {part_code})"
                        )
                        break

        # Strategy 2: Simple invoice rule
        if covered_parts:
            uncovered_generic_labor = [
                item for item in items
                if item.item_type in labor_types
                and item.coverage_status != CoverageStatus.COVERED
                and item.description.lower().strip() in self._GENERIC_LABOR_DESCRIPTIONS
            ]

            if len(uncovered_generic_labor) == 1:
                labor_item = uncovered_generic_labor[0]
                linked_part = covered_parts[0]
                labor_item.coverage_status = CoverageStatus.COVERED
                labor_item.coverage_category = linked_part.coverage_category
                labor_item.matched_component = linked_part.matched_component
                labor_item.match_confidence = 0.75
                labor_item.match_reasoning = (
                    f"Simple invoice rule: generic labor linked to covered part "
                    f"'{linked_part.description}' ({linked_part.coverage_category})"
                )
                logger.debug(
                    f"Promoted labor '{labor_item.description}' to COVERED "
                    f"via simple invoice rule (linked to '{linked_part.description}')"
                )

        # Strategy 3: Repair-context keyword matching
        # If labor description matches REPAIR_CONTEXT_KEYWORDS and covered parts
        # exist in the same category, promote the labor.
        if covered_parts:
            for item in items:
                if item.item_type not in labor_types:
                    continue
                if item.coverage_status == CoverageStatus.COVERED:
                    continue

                desc_lower = item.description.lower()
                for keyword, (component, category) in self.component_config.repair_context_keywords.items():
                    if keyword in desc_lower:
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
                            logger.debug(
                                f"Promoted labor '{item.description}' to COVERED "
                                f"via repair context (keyword: '{keyword}')"
                            )
                            break

        return items

    # Ancillary part keywords promoted when they support a covered repair
    _ANCILLARY_KEYWORDS = {
        "vis", "boulon", "écrou", "schraube",       # fasteners
        "joint", "dichtung",                         # gaskets
        "bague", "o-ring", "o ring",                 # seals
        "bouchon",                                   # plugs
        "jeu mont", "jeu de mont",                   # mounting kits
        "kit de repose",                             # install kits
    }

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
            for pattern in self._ANCILLARY_KEYWORDS:
                if pattern in desc_lower:
                    item.coverage_status = CoverageStatus.COVERED
                    item.coverage_category = repair_context.primary_category
                    item.matched_component = repair_context.primary_component
                    item.match_confidence = 0.70
                    item.match_reasoning = (
                        f"Ancillary part for covered repair: "
                        f"'{pattern}' linked to {repair_context.primary_component}"
                    )
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
            if item.match_method != MatchMethod.LLM:
                continue

            original_category = item.coverage_category
            item.coverage_status = CoverageStatus.NOT_COVERED
            item.covered_amount = 0.0
            item.not_covered_amount = item.total_price
            item.match_reasoning += (
                " [DEMOTED: no covered parts in claim — "
                "labor cannot be covered without an anchoring part]"
            )
            logger.info(
                "Demoted labor '%s' (%s) from COVERED to NOT_COVERED: "
                "no covered parts to anchor it",
                item.description,
                original_category,
            )

        return items

    def _determine_primary_repair(
        self,
        all_items: List[LineItemCoverage],
        covered_components: Dict[str, List[str]],
        repair_context: Optional["RepairContext"] = None,
        claim_id: str = "",
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

        Returns:
            PrimaryRepairResult describing the primary component
        """
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
            logger.info(
                "Primary repair (tier 2): '%s' (%s, covered=%s) from repair context for claim %s",
                repair_context.primary_component,
                repair_context.primary_category,
                repair_context.is_covered,
                claim_id,
            )
            return PrimaryRepairResult(
                component=repair_context.primary_component,
                category=repair_context.primary_category,
                description=repair_context.source_description,
                is_covered=repair_context.is_covered,
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

        # Check if item is in excluded list -> force NOT_COVERED
        # BUT skip exclusion when the item is ancillary to a covered repair
        if self._is_in_excluded_list(item, excluded_components):
            is_ancillary = repair_context and repair_context.is_covered and any(
                kw in item.description.lower() for kw in self._ANCILLARY_KEYWORDS
            )
            if is_ancillary:
                logger.info(
                    f"Skipping exclusion for '{item.description}': "
                    f"ancillary to covered repair '{repair_context.primary_component}'"
                )
            else:
                original_status = item.coverage_status
                item.coverage_status = CoverageStatus.NOT_COVERED
                item.match_reasoning += " [OVERRIDE: Component is in excluded list]"
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
                                        f" matches '{synonym}' → '{comp_type}',"
                                        f" confirmed in policy: {reason}]"
                                    )
                                    logger.info(
                                        "Post-LLM synonym override: '%s' changed"
                                        " from %s to COVERED (synonym '%s' →"
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
                item.match_confidence = 0.45
                item.match_reasoning += (
                    f" [REVIEW: category '{category}' is not covered by policy]"
                )
                logger.info(
                    f"LLM validation override: '{item.description}' changed from "
                    f"COVERED to REVIEW_NEEDED (category '{category}' not covered)"
                )

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
                remaining, covered_categories, covered_components
            )
            logger.debug(f"Part numbers matched: {len(part_matched)}/{len(line_items)}")

        # Stage 2: Keyword matcher
        keyword_matched, remaining = self.keyword_matcher.batch_match(
            remaining,
            covered_categories=covered_categories,
            min_confidence=self.config.keyword_min_confidence,
        )
        logger.debug(f"Keywords matched: {len(keyword_matched)}/{len(line_items)}")

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
                    remaining.append({
                        "item_code": item.item_code,
                        "description": item.description,
                        "item_type": item.item_type,
                        "total_price": item.total_price,
                    })
                elif is_in_list is None and not item.matched_component:
                    # Category-level keyword match only, description doesn't
                    # match any specific policy part — demote to LLM for
                    # component-level verification.
                    logger.info(
                        "Keyword match '%s' (no component) demoted to LLM: %s",
                        item.description,
                        reason,
                    )
                    remaining.append({
                        "item_code": item.item_code,
                        "description": item.description,
                        "item_type": item.item_type,
                        "total_price": item.total_price,
                    })
                else:
                    # True (confirmed) or None with specific component — keep
                    if is_in_list is True:
                        item.match_reasoning += f". Policy check: {reason}"
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

                llm_matched = self.llm_matcher.batch_match(
                    items_for_llm,
                    covered_categories=covered_categories,
                    covered_components=covered_components,
                    excluded_components=excluded_components,
                    claim_id=claim_id,
                    on_progress=on_llm_progress,
                    covered_parts_in_claim=covered_parts_in_claim,
                )

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
        all_items = self._apply_labor_follows_parts(all_items, repair_context=repair_context)

        # Promote ancillary parts for covered repairs
        all_items = self._promote_ancillary_parts(all_items, repair_context=repair_context)

        # Promote parts when covered labor exists for the same repair
        all_items = self._promote_parts_for_covered_repair(all_items, repair_context=repair_context)

        # Demote orphaned labor: if no parts are covered, labor has no anchor
        all_items = self._demote_labor_without_covered_parts(all_items)

        # Determine primary repair component (three-tier approach)
        primary_repair = self._determine_primary_repair(
            all_items, covered_components, repair_context, claim_id,
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

        return CoverageAnalysisResult(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            generated_at=datetime.utcnow(),
            inputs=inputs,
            line_items=all_items,
            summary=summary,
            primary_repair=primary_repair,
            metadata=metadata,
        )
