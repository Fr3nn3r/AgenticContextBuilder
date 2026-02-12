"""Shared test data factories for coverage analysis tests.

Centralizes the `_make_item()` pattern scattered across test classes.
"""

from typing import Any, Dict, List, Optional

from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
    PrimaryRepairResult,
)


def make_line_item(**overrides: Any) -> LineItemCoverage:
    """Create a LineItemCoverage with sensible defaults.

    Default is a covered parts item matched by keyword.  Override any field
    by passing keyword arguments.
    """
    defaults: Dict[str, Any] = dict(
        item_code="P001",
        description="test part",
        item_type="parts",
        total_price=100.0,
        coverage_status=CoverageStatus.COVERED,
        coverage_category="engine",
        matched_component="timing_belt",
        match_method=MatchMethod.KEYWORD,
        match_confidence=0.90,
        match_reasoning="Keyword match",
        covered_amount=100.0,
        not_covered_amount=0.0,
    )
    defaults.update(overrides)
    return LineItemCoverage(**defaults)


def make_covered_part(**overrides: Any) -> LineItemCoverage:
    """Shorthand for a covered parts item."""
    return make_line_item(
        item_type="parts",
        coverage_status=CoverageStatus.COVERED,
        **overrides,
    )


def make_uncovered_labor(**overrides: Any) -> LineItemCoverage:
    """Shorthand for an uncovered labor item (LLM-classified)."""
    defaults = dict(
        item_code=None,
        description="test labor",
        item_type="labor",
        total_price=100.0,
        coverage_status=CoverageStatus.NOT_COVERED,
        coverage_category=None,
        matched_component=None,
        match_method=MatchMethod.LLM,
        match_confidence=0.80,
        match_reasoning="LLM: not covered",
        covered_amount=0.0,
        not_covered_amount=100.0,
    )
    defaults.update(overrides)
    return LineItemCoverage(**defaults)


def make_policy(
    categories: Optional[List[str]] = None,
    components: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    """Create a policy coverage dict (covered_components by category).

    Defaults to engine with a few common components.
    """
    if components is not None:
        return components
    cats = categories or ["engine"]
    result: Dict[str, List[str]] = {}
    default_components = {
        "engine": ["Motor", "Kolben", "Steuerkette", "Wasserpumpe"],
        "automatic_transmission": ["Mechatronik", "Drehmomentwandler"],
        "cooling_system": ["Kuehler", "Thermostat"],
        "electrical_system": ["Lichtmaschine", "Anlasser"],
        "brakes": ["Bremssattel"],
    }
    for cat in cats:
        result[cat] = default_components.get(cat, [])
    return result


def make_primary_repair(**overrides: Any) -> PrimaryRepairResult:
    """Create a PrimaryRepairResult with sensible defaults."""
    defaults = dict(
        component="timing_chain",
        category="engine",
        is_covered=True,
        confidence=0.9,
        determination_method="deterministic",
    )
    defaults.update(overrides)
    return PrimaryRepairResult(**defaults)


def make_input_item(**overrides: Any) -> Dict[str, Any]:
    """Create a raw input item dict (before coverage analysis).

    Used for feeding into the analyzer's analyze() or matching methods.
    """
    defaults = dict(
        item_code="P001",
        description="Test part",
        item_type="parts",
        total_price=100.0,
    )
    defaults.update(overrides)
    return defaults
