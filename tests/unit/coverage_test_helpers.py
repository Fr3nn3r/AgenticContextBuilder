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


# ---------------------------------------------------------------------------
# Screening helpers (shared with assessment tests)
# ---------------------------------------------------------------------------

def make_screening_check(**overrides: Any) -> Dict[str, Any]:
    """Build a screening check dict (as from ScreeningResult.model_dump())."""
    defaults: Dict[str, Any] = {
        "check_id": "1",
        "check_name": "policy_validity",
        "verdict": "PASS",
        "reason": "OK",
        "evidence": {},
        "is_hard_fail": False,
        "requires_llm": False,
    }
    defaults.update(overrides)
    return defaults


def make_screening_payout(**overrides: Any) -> Dict[str, Any]:
    """Build a screening payout dict."""
    defaults: Dict[str, Any] = {
        "covered_total": 4500.0,
        "not_covered_total": 500.0,
        "coverage_percent": 80.0,
        "max_coverage": 10000.0,
        "max_coverage_applied": False,
        "capped_amount": 4500.0,
        "deductible_percent": 10.0,
        "deductible_minimum": 200.0,
        "deductible_amount": 450.0,
        "after_deductible": 4050.0,
        "policyholder_type": "individual",
        "vat_adjusted": False,
        "vat_deduction": 0.0,
        "final_payout": 4050.0,
        "currency": "CHF",
    }
    defaults.update(overrides)
    return defaults


ALL_SCREENING_CHECK_IDS = [
    ("1", "policy_validity"),
    ("1b", "damage_date_validity"),
    ("2", "vehicle_id_consistency"),
    ("2b", "owner_policyholder_match"),
    ("3", "mileage_compliance"),
    ("4a", "shop_authorization"),
    ("4b", "service_compliance"),
    ("5", "component_coverage"),
    ("5b", "assistance_package_items"),
]


def make_all_screening_checks() -> List[Dict[str, Any]]:
    """Return all screening checks with PASS verdicts."""
    return [
        make_screening_check(check_id=cid, check_name=cname)
        for cid, cname in ALL_SCREENING_CHECK_IDS
    ]


def make_auto_reject_screening(
    hard_fail_check_id: str = "3",
    with_payout: bool = True,
) -> Dict[str, Any]:
    """Build a complete auto-reject screening result dict."""
    checks = make_all_screening_checks()
    for c in checks:
        if c["check_id"] == hard_fail_check_id:
            c["verdict"] = "FAIL"
            c["is_hard_fail"] = True
            c["reason"] = f"Check {hard_fail_check_id} failed deterministically"
            c["evidence"] = {"key1": "val1", "key2": "val2"}

    screening: Dict[str, Any] = {
        "schema_version": "screening_v1",
        "claim_id": "CLM-TEST",
        "screening_timestamp": "2026-01-28T10:00:00Z",
        "checks": checks,
        "checks_passed": 8,
        "checks_failed": 1,
        "checks_inconclusive": 0,
        "checks_for_llm": [],
        "coverage_analysis_ref": None,
        "auto_reject": True,
        "auto_reject_reason": f"Hard fail on check(s): {hard_fail_check_id}",
        "hard_fails": [hard_fail_check_id],
    }

    if with_payout:
        screening["payout"] = make_screening_payout()
        screening["payout_error"] = None
    else:
        screening["payout"] = None
        screening["payout_error"] = "Missing policy terms"

    return screening


def make_non_auto_reject_screening() -> Dict[str, Any]:
    """Build a screening result that does NOT auto-reject (LLM path)."""
    checks = make_all_screening_checks()
    for c in checks:
        if c["check_id"] == "2b":
            c["verdict"] = "INCONCLUSIVE"
            c["requires_llm"] = True
            c["reason"] = "Owner name needs LLM review"

    return {
        "schema_version": "screening_v1",
        "claim_id": "CLM-TEST",
        "screening_timestamp": "2026-01-28T10:00:00Z",
        "checks": checks,
        "checks_passed": 8,
        "checks_failed": 0,
        "checks_inconclusive": 1,
        "checks_for_llm": ["2b"],
        "coverage_analysis_ref": None,
        "payout": make_screening_payout(),
        "payout_error": None,
        "auto_reject": False,
        "auto_reject_reason": None,
        "hard_fails": [],
    }
