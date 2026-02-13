"""Post-processing functions for coverage analysis results.

These functions run after the main coverage classification pipeline
(rules, part numbers, keywords, LLM) to apply labor linkage, safety
nets, and audit flags.

All functions are standalone (no class state) and accept only the
data they need, making them easy to test and reason about.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    DecisionSource,
    LineItemCoverage,
    MatchMethod,
    PrimaryRepairResult,
    TraceAction,
)
from context_builder.coverage.trace import TraceBuilder

logger = logging.getLogger(__name__)

LABOR_TYPES = ("labor", "labour", "main d'oeuvre", "arbeit")


def build_excluded_parts_index(
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


def apply_labor_linkage(
    items: List[LineItemCoverage],
    llm_matcher: Any,
    repair_context: Any = None,
    primary_repair: Optional[PrimaryRepairResult] = None,
    claim_id: str = "",
) -> List[LineItemCoverage]:
    """Link labor items to covered parts (LLM-first, 2 strategies).

    1. **Part-number matching** (deterministic): If a labor description
       contains a covered part's item_code, the labor is linked to that
       part.

    2. **LLM labor linkage**: For all remaining uncovered labor, make ONE
       batch LLM call that sees ALL parts and ALL labor together and
       determines which labor is necessary for which covered parts.

    Args:
        items: List of analyzed line items
        llm_matcher: LLM matcher instance (or None to skip LLM step)
        repair_context: Detected repair context from labor descriptions
        primary_repair: Primary repair result for LLM context
        claim_id: Claim ID for audit trail

    Returns:
        Updated list with labor items potentially promoted
    """
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

    # Strategy 1: Part-number matching (deterministic)
    if covered_parts_by_code:
        for item in items:
            if item.item_type not in LABOR_TYPES:
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
                                       "linked_part_code": part_code},
                               decision_source=DecisionSource.PROMOTION)
                    item.decision_trace = lfp_tb.build()
                    logger.debug(
                        f"Promoted labor '{item.description}' to COVERED "
                        f"(linked to part number: {part_code})"
                    )
                    break

    # Strategy 2: LLM labor linkage for remaining uncovered labor
    if not covered_parts or llm_matcher is None:
        return items

    # Collect uncovered labor candidates for LLM evaluation
    candidates = []
    for idx, item in enumerate(items):
        if item.item_type not in LABOR_TYPES:
            continue
        if item.coverage_status == CoverageStatus.COVERED:
            continue
        if item.match_method != MatchMethod.LLM:
            continue
        if item.exclusion_reason:
            continue
        candidates.append((idx, item))

    if not candidates:
        return items

    # Build parts context for LLM
    parts_payload = []
    for idx, item in enumerate(items):
        if item.item_type in ("parts", "part", "piece"):
            parts_payload.append({
                "index": idx,
                "description": item.description,
                "item_code": item.item_code,
                "total_price": item.total_price or 0.0,
                "coverage_status": item.coverage_status.value,
                "coverage_category": item.coverage_category,
                "matched_component": item.matched_component,
            })

    labor_payload = [
        {
            "index": idx,
            "description": item.description,
            "item_code": item.item_code,
            "total_price": item.total_price or 0.0,
        }
        for idx, item in candidates
    ]

    # Build primary repair context for LLM
    primary_ctx = None
    if primary_repair and primary_repair.component:
        primary_ctx = {
            "component": primary_repair.component,
            "category": primary_repair.category,
            "is_covered": primary_repair.is_covered,
        }

    try:
        verdicts = llm_matcher.classify_labor_linkage(
            labor_items=labor_payload,
            parts_items=parts_payload,
            primary_repair=primary_ctx,
            claim_id=claim_id,
        )
    except Exception as e:
        logger.warning(
            "LLM labor linkage failed for claim %s: %s. "
            "Leaving all labor candidates as NOT_COVERED.",
            claim_id, e,
        )
        for idx, item in candidates:
            fail_tb = TraceBuilder()
            fail_tb.extend(item.decision_trace)
            fail_tb.add(
                "labor_linkage_llm", TraceAction.SKIPPED,
                f"LLM labor linkage failed: {e}",
                detail={"strategy": "llm_labor_linkage", "error": str(e)},
                decision_source=DecisionSource.PROMOTION,
            )
            item.decision_trace = fail_tb.build()
        return items

    # Apply verdicts
    verdict_by_idx = {v["index"]: v for v in verdicts}

    for idx, item in candidates:
        verdict = verdict_by_idx.get(idx)
        if verdict and verdict.get("is_covered"):
            linked_part_idx = verdict.get("linked_part_index")
            linked_part = items[linked_part_idx] if (
                linked_part_idx is not None
                and 0 <= linked_part_idx < len(items)
            ) else None

            # Guard: do not promote labor if the linked part is not COVERED.
            # The LLM determines mechanical necessity (e.g. "wheel removal is
            # needed for CV boot replacement") but that does not mean the
            # labor is covered -- coverage depends on the part being covered.
            if linked_part and linked_part.coverage_status != CoverageStatus.COVERED:
                reasoning = (
                    f"Labor is mechanically linked to "
                    f"'{linked_part.description}' but that part is "
                    f"{linked_part.coverage_status.value} -- skipping promotion"
                )
                skip_tb = TraceBuilder()
                skip_tb.extend(item.decision_trace)
                skip_tb.add(
                    "labor_linkage_llm", TraceAction.SKIPPED,
                    reasoning,
                    detail={
                        "strategy": "llm_labor_linkage",
                        "linked_part_index": linked_part_idx,
                        "linked_part_status": linked_part.coverage_status.value,
                        "llm_confidence": verdict.get("confidence", 0),
                        "llm_reasoning": verdict.get("reasoning", ""),
                    },
                    decision_source=DecisionSource.PROMOTION,
                )
                item.decision_trace = skip_tb.build()
                logger.info(
                    "Skipped labor promotion '%s': linked part '%s' is %s",
                    item.description,
                    linked_part.description,
                    linked_part.coverage_status.value,
                )
                continue

            item.coverage_status = CoverageStatus.COVERED
            if linked_part:
                item.coverage_category = linked_part.coverage_category
                item.matched_component = linked_part.matched_component
            elif primary_repair:
                item.coverage_category = primary_repair.category
                item.matched_component = primary_repair.component
            item.covered_amount = item.total_price
            item.not_covered_amount = 0.0
            item.match_reasoning += (
                f" [PROMOTED: LLM labor linkage confirmed necessary: "
                f"{verdict.get('reasoning', '')}]"
            )
            link_tb = TraceBuilder()
            link_tb.extend(item.decision_trace)
            link_tb.add(
                "labor_linkage_llm", TraceAction.PROMOTED,
                f"LLM labor linkage: necessary for covered parts",
                verdict=CoverageStatus.COVERED,
                detail={
                    "strategy": "llm_labor_linkage",
                    "linked_part_index": linked_part_idx,
                    "llm_confidence": verdict.get("confidence", 0),
                    "llm_reasoning": verdict.get("reasoning", ""),
                },
                decision_source=DecisionSource.PROMOTION,
            )
            item.decision_trace = link_tb.build()
            logger.info(
                "Promoted labor '%s' to COVERED via LLM labor linkage",
                item.description,
            )
        else:
            reasoning = (
                verdict.get("reasoning", "Not linked to covered parts")
                if verdict else "Missing from LLM response"
            )
            skip_tb = TraceBuilder()
            skip_tb.extend(item.decision_trace)
            skip_tb.add(
                "labor_linkage_llm", TraceAction.SKIPPED,
                f"LLM labor linkage: not necessary: {reasoning}",
                detail={
                    "strategy": "llm_labor_linkage",
                    "llm_confidence": (
                        verdict.get("confidence", 0) if verdict else 0
                    ),
                    "llm_reasoning": reasoning,
                },
                decision_source=DecisionSource.PROMOTION,
            )
            item.decision_trace = skip_tb.build()

    return items


def demote_labor_for_excluded_parts(
    items: List[LineItemCoverage],
    excluded_components: Optional[Dict[str, Any]] = None,
    primary_repair: Optional[PrimaryRepairResult] = None,
) -> List[LineItemCoverage]:
    """Demote covered labor when it serves an excluded (NOT_COVERED) part.

    After labor linkage, labor can end up COVERED via LLM category mapping
    even though the part it actually serves is excluded by policy.  Example:
    valve-cover replacement labor mapped to "culasses" (cylinder heads) even
    though the valve cover itself is excluded.

    This step catches that inconsistency and demotes the labor.

    Skips demotion when:
    - primary_repair is covered (labor is anchored to a legitimate repair)
    - no excluded parts exist at all
    - covered parts exist on the invoice (mixed invoice -- demote_orphan_labor
      or per-item matching handles these)

    Args:
        items: Line items after labor linkage.
        excluded_components: Policy excluded components dict (category -> parts).
        primary_repair: Primary repair determination result.

    Returns:
        Updated list with labor for excluded parts demoted.
    """
    # If primary repair is legitimately covered, labor is anchored -- skip.
    # But cross-validate: if the source item is not covered, the anchor
    # is unreliable (e.g. LLM picked a covered category but the actual
    # part is a consumable/excluded).
    if primary_repair and primary_repair.is_covered:
        source_idx = primary_repair.source_item_index
        source_ok = True
        if source_idx is not None and 0 <= source_idx < len(items):
            if items[source_idx].coverage_status != CoverageStatus.COVERED:
                source_ok = False
        if source_ok:
            return items

    excluded_components = excluded_components or {}

    # Build sets of excluded part info from actual line items
    excluded_parts_on_invoice: List[LineItemCoverage] = []
    excluded_categories: set = set()
    excluded_matched_components: set = set()
    for item in items:
        if item.coverage_status != CoverageStatus.NOT_COVERED:
            continue
        if item.item_type not in ("parts", "part", "piece"):
            continue
        if not item.exclusion_reason:
            continue
        # Only consider policy-excluded parts (not just "not matched")
        if item.exclusion_reason in (
            "component_excluded", "exclusion_pattern", "consumable",
        ):
            excluded_parts_on_invoice.append(item)
            if item.coverage_category:
                excluded_categories.add(item.coverage_category.lower())
            if item.matched_component:
                excluded_matched_components.add(item.matched_component.lower())

    if not excluded_parts_on_invoice:
        return items

    # Check if any covered parts exist on the invoice
    has_covered_parts = any(
        item.coverage_status == CoverageStatus.COVERED
        and item.item_type in ("parts", "part", "piece")
        for item in items
    )

    # If no covered parts at all, demote_orphan_labor handles it -- skip
    if not has_covered_parts:
        return items

    # Mixed invoice: covered + excluded parts both present.
    # Demote labor whose category/component maps to an excluded part.
    demoted_count = 0
    for item in items:
        if item.item_type not in LABOR_TYPES:
            continue
        if item.coverage_status != CoverageStatus.COVERED:
            continue

        # Check if this labor's category or component matches an excluded part
        labor_category = (item.coverage_category or "").lower()
        labor_component = (item.matched_component or "").lower()

        matches_excluded = False
        if labor_component and labor_component in excluded_matched_components:
            matches_excluded = True
        elif labor_category and labor_category in excluded_categories:
            # Category match -- but only if no covered part shares that category
            has_covered_part_in_category = any(
                p.coverage_status == CoverageStatus.COVERED
                and p.item_type in ("parts", "part", "piece")
                and (p.coverage_category or "").lower() == labor_category
                for p in items
            )
            if not has_covered_part_in_category:
                matches_excluded = True

        if not matches_excluded:
            continue

        original_category = item.coverage_category
        item.coverage_status = CoverageStatus.NOT_COVERED
        item.exclusion_reason = "labor_for_excluded_part"
        item.covered_amount = 0.0
        item.not_covered_amount = item.total_price
        item.match_reasoning += (
            " [DEMOTED: labor serves an excluded part -- "
            "labor coverage follows the part it serves]"
        )
        dem_tb = TraceBuilder()
        dem_tb.extend(item.decision_trace)
        dem_tb.add(
            "excluded_part_labor_demotion", TraceAction.DEMOTED,
            f"Labor linked to excluded part (category: {original_category})",
            verdict=CoverageStatus.NOT_COVERED,
            detail={
                "reason": "labor_for_excluded_part",
                "excluded_categories": sorted(excluded_categories),
                "excluded_components": sorted(excluded_matched_components),
            },
            decision_source=DecisionSource.DEMOTION,
        )
        item.decision_trace = dem_tb.build()
        demoted_count += 1
        logger.info(
            "Demoted labor '%s' (%s) from COVERED to NOT_COVERED: "
            "serves excluded part",
            item.description,
            original_category,
        )

    if demoted_count:
        logger.info(
            "Demoted %d labor item(s) linked to excluded parts", demoted_count,
        )

    return items


def demote_orphan_labor(
    items: List[LineItemCoverage],
    primary_repair: Optional[PrimaryRepairResult] = None,
    repair_context: Any = None,
) -> List[LineItemCoverage]:
    """Demote labor items to NOT_COVERED when no parts are covered.

    Labor is ancillary -- it is only covered when it supports a covered
    part.  If zero parts ended up covered (e.g. the primary part was
    excluded by a rule), any covered labor has no anchor and should
    be demoted.

    Exception: when the primary repair or repair context component is
    covered by policy, labor is anchored to that repair even if no
    explicit parts line item exists on the invoice.  This handles
    labor-only invoices where the garage bills labor without listing
    the replaced part separately, and cases where the primary repair
    part is REVIEW_NEEDED but the repair context confirms coverage.

    Args:
        items: List of analyzed line items (after all promotion stages).
        primary_repair: Primary repair determination result (optional).
        repair_context: Repair context from labor descriptions (optional).

    Returns:
        Updated list with orphaned labor items demoted.
    """
    has_covered_parts = any(
        item.coverage_status == CoverageStatus.COVERED
        and item.item_type in ("parts", "part", "piece")
        for item in items
    )
    has_non_ancillary_covered_part = any(
        item.coverage_status == CoverageStatus.COVERED
        and item.item_type in ("parts", "part", "piece")
        and (item.matched_component or "").lower() != "ancillary hardware"
        for item in items
    )

    # Ancillary hardware (nuts, bolts, screws) should not count as a
    # covered-parts anchor by themselves -- they accompany a repair but
    # don't establish that a repair is covered.
    if has_non_ancillary_covered_part:
        return items
    if has_covered_parts:
        logger.info(
            "Only ancillary hardware covered -- not counting as parts anchor"
        )

    # Primary repair is covered — labor has a policy-level anchor even
    # without an explicit parts line item on the invoice.
    # Two cross-validations:
    # (a) If the source item is NOT covered, the anchor is unreliable.
    # (b) If only ancillary hardware is covered (no real parts), and no
    #     source item is set, the anchor is also unreliable.
    if primary_repair and primary_repair.is_covered:
        anchor_valid = True
        source_idx = primary_repair.source_item_index
        if source_idx is not None and 0 <= source_idx < len(items):
            src = items[source_idx]
            if src.coverage_status != CoverageStatus.COVERED:
                anchor_valid = False
                logger.info(
                    "Primary repair '%s' is_covered=True but source item "
                    "[%d] '%s' is %s -- ignoring anchor",
                    primary_repair.component,
                    source_idx,
                    src.description,
                    src.coverage_status.value,
                )
            elif src.item_type in LABOR_TYPES:
                # Source item is labor, not a part -- the LLM picked a
                # labor description as the primary repair.  If no real
                # non-ancillary parts are covered, this is not a valid
                # parts anchor.
                if not has_non_ancillary_covered_part:
                    anchor_valid = False
                    logger.info(
                        "Primary repair '%s' source is labor item [%d] '%s' "
                        "and no non-ancillary parts covered -- ignoring anchor",
                        primary_repair.component,
                        source_idx,
                        src.description,
                    )
        elif has_covered_parts and not has_non_ancillary_covered_part:
            # No source item set AND only ancillary hardware covered --
            # parts exist on the invoice but none are real covered parts.
            anchor_valid = False
            logger.info(
                "Primary repair '%s' is_covered=True but no source item "
                "and only ancillary hardware covered -- ignoring anchor",
                primary_repair.component,
            )
        if anchor_valid:
            logger.info(
                "Skipping orphan labor demotion: primary repair '%s' is covered",
                primary_repair.component,
            )
            return items

    # Repair context is covered — labor describes work on a covered
    # component even when the parts line item is REVIEW_NEEDED.
    if repair_context and repair_context.is_covered:
        ctx_name = getattr(repair_context, "primary_component", None) or getattr(repair_context, "component", None)
        logger.info(
            "Skipping orphan labor demotion: repair context '%s' is covered",
            ctx_name,
        )
        return items

    for item in items:
        if item.item_type not in LABOR_TYPES:
            continue
        if item.coverage_status != CoverageStatus.COVERED:
            continue
        # When zero parts are covered, ALL labor is access work --
        # regardless of how it was matched. Labor requires a covered
        # parts anchor.

        original_category = item.coverage_category
        item.coverage_status = CoverageStatus.NOT_COVERED
        item.exclusion_reason = "demoted_no_anchor"
        item.covered_amount = 0.0
        item.not_covered_amount = item.total_price
        item.match_reasoning += (
            " [DEMOTED: no covered parts in claim -- "
            "labor cannot be covered without an anchoring part]"
        )
        dem_tb = TraceBuilder()
        dem_tb.extend(item.decision_trace)
        dem_tb.add("labor_demotion", TraceAction.DEMOTED,
                   "No covered parts in claim -- labor has no anchor",
                   verdict=CoverageStatus.NOT_COVERED,
                   detail={"reason": "no_covered_parts_anchor"},
                   decision_source=DecisionSource.DEMOTION)
        item.decision_trace = dem_tb.build()
        logger.info(
            "Demoted labor '%s' (%s) from COVERED to NOT_COVERED: "
            "no covered parts to anchor it",
            item.description,
            original_category,
        )

    return items


def flag_nominal_price_labor(
    items: List[LineItemCoverage],
    threshold: float = 2.0,
) -> List[LineItemCoverage]:
    """Flag nominal-price labor items as REVIEW_NEEDED.

    Mercedes-format invoices list labor operations with a nominal price
    (e.g. 1.00 CHF per operation code) where the real cost should be
    hours x hourly rate.  Since labor-hours parsing is not yet supported,
    these items are demoted to REVIEW_NEEDED so they don't silently enter
    the payout at incorrect amounts.

    Only affects labor items that:
    - have total_price > 0 and <= threshold
    - have an item_code (indicating an operation code, not generic labor)
    - are currently COVERED (leaves NOT_COVERED and REVIEW_NEEDED alone)

    Args:
        items: List of analyzed line items.
        threshold: Maximum price to consider "nominal" (default 2.0).

    Returns:
        Updated list with nominal-price labor flagged.
    """
    flagged_count = 0

    for item in items:
        if item.item_type not in LABOR_TYPES:
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
            decision_source=DecisionSource.DEMOTION,
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


def validate_llm_coverage_decision(
    item: LineItemCoverage,
    covered_components: Dict[str, List[str]],
    excluded_components: Dict[str, List[str]],
    repair_context: Any = None,
    is_in_excluded_list: Optional[Callable[[LineItemCoverage, Dict[str, List[str]]], bool]] = None,
    is_system_covered: Optional[Callable[[str, List[str]], bool]] = None,
    ancillary_keywords: Optional[List[str]] = None,
) -> LineItemCoverage:
    """Validate and potentially override LLM coverage decision.

    Simplified safety net for LLM-first mode.  The LLM now receives the
    full policy matrix and per-item hints, so synonym-based overrides and
    category checks are no longer needed.  One check remains:

    1. **Exclusion check** -- force NOT_COVERED when the item is in the
       excluded components list (unless it is labor or an ancillary part
       supporting a covered repair).

    Args:
        item: Line item coverage result from LLM
        covered_components: Dict of category -> list of covered parts
        excluded_components: Dict of category -> list of excluded parts
        repair_context: Detected repair context (if any)
        is_in_excluded_list: Callable to check if item is excluded
        is_system_covered: Callable to check if a system/category is covered
        ancillary_keywords: Keywords identifying ancillary parts

    Returns:
        Validated/corrected LineItemCoverage
    """
    if item.match_method != MatchMethod.LLM:
        return item

    val_tb = TraceBuilder()
    val_tb.extend(item.decision_trace)

    # Check 1: Exclusion list -- force NOT_COVERED
    # Skip for labor items (excluded list targets replacement parts,
    # not access/disassembly labor) and for ancillary parts supporting
    # a covered repair.
    is_labor = item.item_type in LABOR_TYPES
    if not is_labor and is_in_excluded_list and is_in_excluded_list(item, excluded_components):
        anc_kw = ancillary_keywords or []
        is_ancillary = repair_context and repair_context.is_covered and any(
            kw in item.description.lower() for kw in anc_kw
        )
        if is_ancillary:
            logger.info(
                f"Skipping exclusion for '{item.description}': "
                f"ancillary to covered repair '{repair_context.primary_component}'"
            )
            val_tb.add("llm_validation", TraceAction.VALIDATED,
                       f"Exclusion skipped: ancillary to covered repair '{repair_context.primary_component}'",
                       detail={"check": "excluded_list_ancillary_skip"},
                       decision_source=DecisionSource.VALIDATION)
        else:
            original_status = item.coverage_status
            item.coverage_status = CoverageStatus.NOT_COVERED
            item.exclusion_reason = "component_excluded"
            item.match_reasoning += " [OVERRIDE: Component is in excluded list]"
            val_tb.add("llm_validation", TraceAction.OVERRIDDEN,
                       "Component is in excluded list",
                       verdict=CoverageStatus.NOT_COVERED,
                       detail={"check": "excluded_list"},
                       decision_source=DecisionSource.VALIDATION)
            item.decision_trace = val_tb.build()
            logger.info(
                f"LLM validation override: '{item.description}' changed from "
                f"{original_status.value} to NOT_COVERED (in excluded list)"
            )
            return item

    val_tb.add("llm_validation", TraceAction.VALIDATED,
               "LLM coverage decision confirmed",
               verdict=item.coverage_status,
               decision_source=DecisionSource.VALIDATION)

    item.decision_trace = val_tb.build()
    return item
