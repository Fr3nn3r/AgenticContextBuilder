"""Unit tests for NSA screening payout calculation.

Tests the deterministic payout calculation in the NSAScreener:
- Coverage totals from CoverageAnalysisResult
- Max coverage cap
- Deductible (percent + minimum)
- VAT adjustment for companies
- Edge cases (missing data, zero amounts)

Skipped automatically if the NSA workspace screener is not present.
"""

import importlib.util
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock

import pytest

from context_builder.coverage.schemas import (
    CoverageAnalysisResult,
    CoverageStatus,
    CoverageSummary,
    LineItemCoverage,
    MatchMethod,
)
from context_builder.schemas.screening import ScreeningPayoutCalculation

# ── Dynamic import of NSAScreener from workspace config ──────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKSPACE_NSA = _PROJECT_ROOT / "workspaces" / "nsa"
_SCREENER_FILE = _WORKSPACE_NSA / "config" / "screening" / "screener.py"

_nsa_available = _SCREENER_FILE.exists()

if _nsa_available:
    _spec = importlib.util.spec_from_file_location("nsa_screener", _SCREENER_FILE)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NSAScreener = _mod.NSAScreener
    SWISS_VAT_RATE = _mod.SWISS_VAT_RATE
else:
    NSAScreener = None  # type: ignore[assignment,misc]
    SWISS_VAT_RATE = 0.081

pytestmark = pytest.mark.skipif(
    not _nsa_available,
    reason="NSA workspace screener not available",
)


# ── Helpers ──────────────────────────────────────────────────────────


def _screener() -> "NSAScreener":
    return NSAScreener(_WORKSPACE_NSA)


def _make_facts(*name_value_pairs):
    return [{"name": n, "value": v} for n, v in name_value_pairs]


def _make_coverage_result(
    covered_total: float = 4500.0,
    not_covered_total: float = 500.0,
    coverage_percent: Optional[float] = 80.0,
) -> CoverageAnalysisResult:
    """Build a minimal CoverageAnalysisResult with summary totals."""
    line_items = []
    if covered_total > 0:
        line_items.append(
            LineItemCoverage(
                description="Covered part",
                item_type="parts",
                total_price=covered_total,
                coverage_status=CoverageStatus.COVERED,
                match_method=MatchMethod.KEYWORD,
                match_confidence=0.85,
                match_reasoning="Covered",
                covered_amount=covered_total,
            )
        )
    if not_covered_total > 0:
        line_items.append(
            LineItemCoverage(
                description="Not covered part",
                item_type="parts",
                total_price=not_covered_total,
                coverage_status=CoverageStatus.NOT_COVERED,
                match_method=MatchMethod.RULE,
                match_confidence=1.0,
                match_reasoning="Not covered",
                not_covered_amount=not_covered_total,
            )
        )

    return CoverageAnalysisResult(
        claim_id="CLM-TEST",
        line_items=line_items,
        summary=CoverageSummary(
            total_covered_before_excess=covered_total,
            total_covered_gross=covered_total,
            parts_covered_gross=covered_total,  # helper uses "parts" item_type
            labor_covered_gross=0.0,
            total_not_covered=not_covered_total,
            items_covered=1 if covered_total > 0 else 0,
            items_not_covered=1 if not_covered_total > 0 else 0,
            coverage_percent=coverage_percent,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# BASIC PAYOUT CALCULATION
# ═══════════════════════════════════════════════════════════════════════


class TestPayoutBasic:
    """Basic payout calculation tests."""

    def test_basic_payout_no_cap_no_deductible(self):
        """No max coverage, no deductible → final = subtotal_with_vat after rate."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
        )
        coverage = _make_coverage_result(covered_total=4500.0, not_covered_total=500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout is not None
        assert payout.covered_total == 4500.0
        assert payout.not_covered_total == 500.0
        # Rate applied first: 4500 * 80% = 3600, no cap → capped_amount = 3600
        assert payout.capped_amount == 3600.0
        assert payout.max_coverage_applied is False
        assert payout.deductible_amount == 0.0
        # +VAT: 3600 * 1.081 = 3891.6
        assert payout.after_deductible == 3891.6
        assert payout.final_payout == 3891.6
        assert payout.policyholder_type == "individual"
        assert payout.vat_adjusted is False

    def test_returns_none_without_coverage(self):
        """No coverage result → payout is None."""
        facts = _make_facts(("policyholder_name", "Hans Muster"))
        payout = _screener()._calculate_payout(facts, None)
        assert payout is None

    def test_zero_covered_total(self):
        facts = _make_facts(("policyholder_name", "Hans Muster"))
        coverage = _make_coverage_result(covered_total=0.0, not_covered_total=1000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout is not None
        assert payout.covered_total == 0.0
        assert payout.final_payout == 0.0

    def test_currency_is_chf(self):
        facts = _make_facts(("policyholder_name", "Hans Muster"))
        coverage = _make_coverage_result()
        payout = _screener()._calculate_payout(facts, coverage)
        assert payout.currency == "CHF"

    def test_parts_labor_breakdown_populated(self):
        """Verify parts_covered_gross, labor_covered_gross, vat_rate_pct are set."""
        facts = _make_facts(("policyholder_name", "Hans Muster"))
        coverage = _make_coverage_result(covered_total=4500.0, not_covered_total=500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.parts_covered_gross == 4500.0
        assert payout.labor_covered_gross == 0.0
        assert payout.vat_rate_pct == 8.1

    def test_amounts_are_rounded(self):
        """Verify amounts are rounded to 2 decimal places."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_percent", "10"),
            ("excess_minimum", "200"),
        )
        # rate_adjusted = 3333.33 * 80% = 2666.664
        # subtotal_with_vat = 2666.664 * 1.081 = 2882.66
        # deductible = subtotal * 10% = 288.27
        coverage = _make_coverage_result(covered_total=3333.33)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.deductible_amount == round(3333.33 * 0.80 * (1 + SWISS_VAT_RATE) * 0.10, 2)
        assert payout.final_payout == round(payout.final_payout, 2)


# ═══════════════════════════════════════════════════════════════════════
# MAX COVERAGE CAP
# ═══════════════════════════════════════════════════════════════════════


class TestPayoutMaxCoverage:
    """Tests for max coverage cap."""

    def test_cap_applied_when_exceeded(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("max_coverage", "3000"),
        )
        coverage = _make_coverage_result(covered_total=5000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.max_coverage_applied is True
        assert payout.max_coverage == 3000.0
        assert payout.capped_amount == 3000.0

    def test_cap_not_applied_when_under(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("max_coverage", "10000"),
        )
        coverage = _make_coverage_result(covered_total=5000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.max_coverage_applied is False
        # Rate first: 5000 * 80% = 4000, 4000 < 10000 → no cap
        assert payout.capped_amount == 4000.0

    def test_cap_at_exact_amount(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("max_coverage", "5000"),
        )
        coverage = _make_coverage_result(covered_total=5000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # Rate first: 5000 * 80% = 4000, 4000 < 5000 → no cap
        assert payout.max_coverage_applied is False
        assert payout.capped_amount == 4000.0

    def test_no_cap_when_not_specified(self):
        facts = _make_facts(("policyholder_name", "Hans Muster"))
        coverage = _make_coverage_result(covered_total=50000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.max_coverage is None
        assert payout.max_coverage_applied is False
        # Rate first: 50000 * 80% = 40000, no cap
        assert payout.capped_amount == 40000.0


# ═══════════════════════════════════════════════════════════════════════
# DEDUCTIBLE CALCULATION
# ═══════════════════════════════════════════════════════════════════════


class TestPayoutDeductible:
    """Tests for deductible (excess) calculation."""

    def test_percent_deductible(self):
        """Deductible = subtotal_with_vat * percent/100."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_percent", "10"),
        )
        coverage = _make_coverage_result(covered_total=4500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # rate = 4500 * 80% = 3600, subtotal = 3600 * 1.081 = 3891.6, deductible = 389.16
        assert payout.deductible_percent == 10.0
        assert payout.deductible_amount == 389.16
        assert payout.after_deductible == 3502.44

    def test_minimum_deductible(self):
        """Deductible = MAX(percent * subtotal, minimum)."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_percent", "5"),     # 5% of 1081 = 54.05
            ("excess_minimum", "200"),   # minimum 200 → use 200
        )
        coverage = _make_coverage_result(covered_total=1000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # rate = 1000 * 80% = 800, subtotal = 800 * 1.081 = 864.8, 5% = 43.24, min 200 wins
        assert payout.deductible_amount == 200.0
        assert payout.after_deductible == 664.8

    def test_percent_deductible_wins_over_minimum(self):
        """When percent produces higher amount, it wins."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_percent", "10"),    # 10% of 5405 = 540.5
            ("excess_minimum", "200"),   # minimum 200 → use 540.5
        )
        coverage = _make_coverage_result(covered_total=5000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # rate = 5000 * 80% = 4000, subtotal = 4000 * 1.081 = 4324.0, 10% = 432.4
        assert payout.deductible_amount == 432.4

    def test_only_minimum_deductible(self):
        """When only minimum is specified (no percent)."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_minimum", "300"),
        )
        coverage = _make_coverage_result(covered_total=4500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # rate = 4500 * 80% = 3600, subtotal = 3600 * 1.081 = 3891.6, min deductible 300
        assert payout.deductible_amount == 300.0
        assert payout.after_deductible == 3591.6

    def test_no_deductible(self):
        """No excess fields → deductible = 0, after_deductible = subtotal_with_vat."""
        facts = _make_facts(("policyholder_name", "Hans Muster"))
        coverage = _make_coverage_result(covered_total=4500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.deductible_amount == 0.0
        # rate = 4500 * 80% = 3600, subtotal = 3600 * 1.081 = 3891.6
        assert payout.after_deductible == 3891.6

    def test_after_deductible_never_negative(self):
        """After deductible should not go below zero."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_minimum", "5000"),
        )
        coverage = _make_coverage_result(covered_total=1000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.after_deductible == 0.0
        assert payout.final_payout == 0.0

    def test_deductible_with_max_coverage_cap(self):
        """Deductible applies to VAT-inclusive capped amount."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("max_coverage", "3000"),
            ("excess_percent", "10"),
        )
        coverage = _make_coverage_result(covered_total=5000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # Rate first: 5000 * 80% = 4000, cap at 3000 (4000 > 3000)
        # When capped, cap IS the VAT-inclusive ceiling (no VAT added on top)
        # subtotal = 3000, deductible = 3000 * 10% = 300
        assert payout.capped_amount == 3000.0
        assert payout.deductible_amount == 300.0
        assert payout.after_deductible == 2700.0


# ═══════════════════════════════════════════════════════════════════════
# VAT ADJUSTMENT (COMPANY)
# ═══════════════════════════════════════════════════════════════════════


class TestPayoutVAT:
    """Tests for VAT adjustment on company policyholders."""

    def test_company_vat_deducted(self):
        facts = _make_facts(
            ("policyholder_name", "Muster AG"),
            ("excess_percent", "10"),
        )
        coverage = _make_coverage_result(covered_total=4500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.policyholder_type == "company"
        assert payout.vat_adjusted is True
        assert payout.vat_deduction > 0

        # Rate already applied; for company remove VAT from after_deductible
        expected_final = round(payout.after_deductible / (1 + SWISS_VAT_RATE), 2)
        assert payout.final_payout == expected_final

    def test_individual_no_vat(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_percent", "10"),
        )
        coverage = _make_coverage_result(covered_total=4500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.policyholder_type == "individual"
        assert payout.vat_adjusted is False
        assert payout.vat_deduction == 0.0
        # Rate already applied; final = after_deductible for individuals
        assert payout.final_payout == payout.after_deductible

    def test_company_zero_payout_no_vat(self):
        """Company with zero after_deductible should have no VAT adjustment."""
        facts = _make_facts(
            ("policyholder_name", "Muster GmbH"),
            ("excess_minimum", "5000"),
        )
        coverage = _make_coverage_result(covered_total=1000.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.policyholder_type == "company"
        assert payout.after_deductible == 0.0
        assert payout.vat_adjusted is False
        assert payout.final_payout == 0.0

    def test_vat_deduction_amount_correct(self):
        """Verify exact VAT deduction amount."""
        facts = _make_facts(("policyholder_name", "Muster SA"))
        coverage = _make_coverage_result(covered_total=10810.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # rate = 10810 * 80% = 8648, subtotal = 8648 * 1.081 = 9348.49 (no deductible)
        # vat_deduction = after_deductible - after_deductible/1.081
        assert payout.vat_adjusted is True
        assert payout.after_deductible == 9348.49
        expected_vat = round(payout.after_deductible - (payout.after_deductible / (1 + SWISS_VAT_RATE)), 2)
        assert payout.vat_deduction == expected_vat


# ═══════════════════════════════════════════════════════════════════════
# FULL PAYOUT FLOW
# ═══════════════════════════════════════════════════════════════════════


class TestPayoutFullFlow:
    """End-to-end payout calculation scenarios."""

    def test_typical_individual_claim(self):
        """Typical claim: individual, deductible, no cap.

        Formula: gross → *rate → (cap check) → +VAT → -deductible
        """
        facts = _make_facts(
            ("policyholder_name", "Anna Muster"),
            ("excess_percent", "10"),
            ("excess_minimum", "200"),
        )
        coverage = _make_coverage_result(
            covered_total=4500.0, not_covered_total=500.0, coverage_percent=80.0
        )
        payout = _screener()._calculate_payout(facts, coverage)

        assert payout.covered_total == 4500.0
        assert payout.not_covered_total == 500.0
        # Rate first: 4500 * 80% = 3600, no cap → capped_amount = 3600
        assert payout.capped_amount == 3600.0
        # subtotal = 3600 * 1.081 = 3891.6, deductible = 389.16
        assert payout.deductible_amount == 389.16
        assert payout.after_deductible == 3502.44
        assert payout.vat_adjusted is False
        assert payout.final_payout == 3502.44

    def test_company_claim_with_cap(self):
        """Company claim: capped, deductible, VAT deduction.

        Formula: gross → *rate → cap → +VAT → -deductible → -company VAT
        """
        facts = _make_facts(
            ("policyholder_name", "Muster AG"),
            ("max_coverage", "3000"),
            ("excess_percent", "10"),
            ("excess_minimum", "200"),
        )
        coverage = _make_coverage_result(covered_total=5000.0, not_covered_total=200.0)
        payout = _screener()._calculate_payout(facts, coverage)

        # Step 1: Rate first: 5000 * 80% = 4000, cap at 3000 (4000 > 3000)
        assert payout.max_coverage_applied is True
        assert payout.capped_amount == 3000.0

        # Step 2: When capped, cap IS the VAT-inclusive ceiling (no VAT added)
        # subtotal = 3000, Deductible = max(3000*10%, 200) = max(300, 200) = 300
        assert payout.deductible_amount == 300.0
        assert payout.after_deductible == 2700.0

        # Step 3: Remove VAT for company
        assert payout.vat_adjusted is True
        expected_final = round(payout.after_deductible / (1 + SWISS_VAT_RATE), 2)
        assert payout.final_payout == expected_final

    def test_payout_is_valid_pydantic_model(self):
        """Payout result should validate against ScreeningPayoutCalculation."""
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("excess_percent", "10"),
            ("excess_minimum", "200"),
            ("max_coverage", "10000"),
        )
        coverage = _make_coverage_result(covered_total=4500.0, not_covered_total=500.0)
        payout = _screener()._calculate_payout(facts, coverage)

        assert isinstance(payout, ScreeningPayoutCalculation)
        # Verify serialization roundtrip
        data = payout.model_dump()
        restored = ScreeningPayoutCalculation(**data)
        assert restored.final_payout == payout.final_payout

    def test_payout_via_screen_method(self):
        """Payout is computed when running full screen()."""
        screener = _screener()
        screener._run_coverage_analysis = MagicMock(
            return_value=_make_coverage_result(covered_total=3000.0, not_covered_total=200.0)
        )

        facts = {
            "facts": _make_facts(
                ("start_date", "2025-01-01"),
                ("end_date", "2027-12-31"),
                ("document_date", "2026-06-15"),
                ("km_limited_to", "150000"),
                ("odometer_km", "74359"),
                ("policyholder_name", "Hans Muster"),
                ("excess_percent", "10"),
                ("excess_minimum", "200"),
            ),
            "structured_data": {},
        }
        result, _ = screener.screen("CLM-TEST", facts)

        assert result.payout is not None
        assert result.payout.covered_total == 3000.0
        # rate = 3000 * 80% = 2400, subtotal = 2400 * 1.081 = 2594.4, deductible = 259.44
        assert result.payout.deductible_amount == 259.44
        assert result.payout.after_deductible == 2334.96
        # Rate already applied; final = after_deductible for individuals
        assert result.payout.final_payout == 2334.96
        assert result.payout_error is None

    def test_payout_error_captured(self):
        """Payout calculation errors are captured, not raised."""
        screener = _screener()

        # Mock _calculate_payout to raise, simulating a payout failure
        # (coverage analysis may succeed but payout math could fail)
        screener._run_coverage_analysis = MagicMock(return_value=None)
        original_calculate = screener._calculate_payout
        screener._calculate_payout = MagicMock(side_effect=RuntimeError("broken payout"))

        facts = {
            "facts": _make_facts(
                ("start_date", "2025-01-01"),
                ("end_date", "2027-12-31"),
                ("document_date", "2026-06-15"),
                ("km_limited_to", "150000"),
                ("odometer_km", "74359"),
            ),
            "structured_data": {},
        }
        result, _ = screener.screen("CLM-TEST", facts)

        assert result.payout is None
        assert result.payout_error is not None
