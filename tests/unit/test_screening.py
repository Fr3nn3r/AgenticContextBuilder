"""Unit tests for NSA screening checks (deterministic checks 1-5b).

Tests each individual check method of the NSAScreener against crafted
aggregated facts data.  Skipped automatically if the NSA workspace
screener is not present (e.g. CI without customer config).
"""

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from context_builder.schemas.screening import CheckVerdict, ScreeningCheck, ScreeningResult

# ── Dynamic import of NSAScreener from workspace config ──────────────

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_WORKSPACE_NSA = _PROJECT_ROOT / "workspaces" / "nsa"
_SCREENER_FILE = _WORKSPACE_NSA / "config" / "screening" / "screener.py"

_nsa_available = _SCREENER_FILE.exists()

if _nsa_available:
    import importlib.util

    _spec = importlib.util.spec_from_file_location("nsa_screener", _SCREENER_FILE)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    NSAScreener = _mod.NSAScreener
else:
    NSAScreener = None  # type: ignore[assignment,misc]

pytestmark = pytest.mark.skipif(
    not _nsa_available,
    reason="NSA workspace screener not available",
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_facts(*name_value_pairs) -> List[Dict[str, Any]]:
    """Build a facts list from (name, value) pairs."""
    return [{"name": n, "value": v} for n, v in name_value_pairs]


def _screener() -> "NSAScreener":
    """Create an NSAScreener instance (no coverage analyzer needed for check-level tests)."""
    return NSAScreener(_WORKSPACE_NSA)


# ── Reconciliation report helpers ────────────────────────────────────


def _make_recon_report(conflicts=None):
    """Build a minimal ReconciliationReport-like object for VIN checks."""
    from context_builder.schemas.reconciliation import (
        FactConflict,
        GateStatus,
        ReconciliationGate,
        ReconciliationReport,
    )

    return ReconciliationReport(
        claim_id="CLM-TEST",
        claim_run_id="run_test",
        gate=ReconciliationGate(status=GateStatus.PASS),
        conflicts=conflicts or [],
    )


def _make_vin_conflict(fact_name="vehicle_vin", values=None):
    """Build a FactConflict for VIN-related tests."""
    from context_builder.schemas.reconciliation import ConflictSource, FactConflict

    vals = values or ["WVWZZZ1JZ3W123456", "WVWZZZ1JZ3W789012"]
    return FactConflict(
        fact_name=fact_name,
        values=vals,
        sources=[
            [ConflictSource(doc_id="DOC-001", doc_type="cost_estimate", filename="cost.pdf")],
            [ConflictSource(doc_id="DOC-002", doc_type="service_history", filename="service.pdf")],
        ],
        selected_value=vals[0],
        selected_confidence=0.9,
    )


# ═══════════════════════════════════════════════════════════════════════
# CHECK 1: POLICY VALIDITY
# ═══════════════════════════════════════════════════════════════════════


class TestCheck1PolicyValidity:
    """Tests for _check_1_policy_validity."""

    def test_pass_claim_date_within_period(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2026-12-31"),
            ("document_date", "2026-06-15"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.PASS
        assert check.is_hard_fail is True
        assert check.check_id == "1"

    def test_fail_claim_date_after_policy_end(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2025-12-31"),
            ("document_date", "2026-06-15"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.FAIL
        assert check.is_hard_fail is True

    def test_fail_claim_date_before_policy_start(self):
        facts = _make_facts(
            ("start_date", "2026-01-01"),
            ("end_date", "2027-12-31"),
            ("document_date", "2025-06-15"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.FAIL

    def test_pass_claim_date_on_start_boundary(self):
        facts = _make_facts(
            ("start_date", "2025-06-01"),
            ("end_date", "2026-06-01"),
            ("document_date", "2025-06-01"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_pass_claim_date_on_end_boundary(self):
        facts = _make_facts(
            ("start_date", "2025-06-01"),
            ("end_date", "2026-06-01"),
            ("document_date", "2026-06-01"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_skipped_missing_start_date(self):
        facts = _make_facts(
            ("end_date", "2026-12-31"),
            ("document_date", "2026-06-15"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_missing_end_date(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("document_date", "2026-06-15"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_missing_claim_date(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2026-12-31"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_european_date_format(self):
        facts = _make_facts(
            ("start_date", "01.01.2025"),
            ("end_date", "31.12.2026"),
            ("document_date", "15.06.2026"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_evidence_contains_dates(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2026-12-31"),
            ("document_date", "2026-06-15"),
        )
        check = _screener()._check_1_policy_validity(facts)
        assert "policy_start" in check.evidence
        assert "policy_end" in check.evidence
        assert "claim_date" in check.evidence


# ═══════════════════════════════════════════════════════════════════════
# CHECK 1b: DAMAGE DATE
# ═══════════════════════════════════════════════════════════════════════


class TestCheck1bDamageDate:
    """Tests for _check_1b_damage_date."""

    def test_pass_damage_date_within_period(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2026-12-31"),
            ("damage_date", "2026-03-15"),
        )
        check = _screener()._check_1b_damage_date(facts)
        assert check.verdict == CheckVerdict.PASS
        assert check.check_id == "1b"
        assert check.is_hard_fail is True

    def test_fail_damage_date_before_policy(self):
        facts = _make_facts(
            ("start_date", "2026-01-01"),
            ("end_date", "2027-12-31"),
            ("damage_date", "2025-06-15"),
        )
        check = _screener()._check_1b_damage_date(facts)
        assert check.verdict == CheckVerdict.FAIL

    def test_fail_damage_date_after_policy(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2025-12-31"),
            ("damage_date", "2026-06-15"),
        )
        check = _screener()._check_1b_damage_date(facts)
        assert check.verdict == CheckVerdict.FAIL

    def test_skipped_no_damage_date(self):
        facts = _make_facts(
            ("start_date", "2025-01-01"),
            ("end_date", "2026-12-31"),
        )
        check = _screener()._check_1b_damage_date(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_no_policy_dates(self):
        facts = _make_facts(
            ("damage_date", "2026-03-15"),
        )
        check = _screener()._check_1b_damage_date(facts)
        assert check.verdict == CheckVerdict.SKIPPED


# ═══════════════════════════════════════════════════════════════════════
# CHECK 2: VIN CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════


class TestCheck2VinConsistency:
    """Tests for _check_2_vin_consistency."""

    def test_pass_no_vin_conflicts(self):
        report = _make_recon_report(conflicts=[])
        check = _screener()._check_2_vin_consistency(report)
        assert check.verdict == CheckVerdict.PASS
        assert check.is_hard_fail is False
        assert check.check_id == "2"

    def test_fail_vin_conflict(self):
        conflict = _make_vin_conflict()
        report = _make_recon_report(conflicts=[conflict])
        check = _screener()._check_2_vin_consistency(report)
        assert check.verdict == CheckVerdict.FAIL
        assert check.requires_llm is True
        assert check.is_hard_fail is False

    def test_pass_non_vin_conflict_ignored(self):
        """Conflicts not related to VIN should not trigger failure."""
        from context_builder.schemas.reconciliation import ConflictSource, FactConflict

        non_vin_conflict = FactConflict(
            fact_name="policyholder_name",
            values=["Hans Muster", "Hans Mueller"],
            sources=[
                [ConflictSource(doc_id="DOC-001", doc_type="policy", filename="p.pdf")],
                [ConflictSource(doc_id="DOC-002", doc_type="claim", filename="c.pdf")],
            ],
            selected_value="Hans Muster",
            selected_confidence=0.8,
        )
        report = _make_recon_report(conflicts=[non_vin_conflict])
        check = _screener()._check_2_vin_consistency(report)
        assert check.verdict == CheckVerdict.PASS

    def test_skipped_no_recon_report(self):
        check = _screener()._check_2_vin_consistency(None)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_chassis_keyword_detected(self):
        """Fact names with 'chassis' or 'fahrgestell' should be treated as VIN."""
        conflict = _make_vin_conflict(fact_name="fahrgestellnummer")
        report = _make_recon_report(conflicts=[conflict])
        check = _screener()._check_2_vin_consistency(report)
        assert check.verdict == CheckVerdict.FAIL


# ═══════════════════════════════════════════════════════════════════════
# CHECK 2b: OWNER MATCH
# ═══════════════════════════════════════════════════════════════════════


class TestCheck2bOwnerMatch:
    """Tests for _check_2b_owner_match."""

    def test_pass_exact_match(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("owner_name", "Hans Muster"),
        )
        check = _screener()._check_2b_owner_match(facts)
        assert check.verdict == CheckVerdict.PASS
        assert check.check_id == "2b"

    def test_pass_case_insensitive(self):
        facts = _make_facts(
            ("policyholder_name", "HANS MUSTER"),
            ("owner_name", "hans muster"),
        )
        check = _screener()._check_2b_owner_match(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_pass_substring_match(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster AG"),
            ("owner_name", "Hans Muster"),
        )
        check = _screener()._check_2b_owner_match(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_inconclusive_no_match(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
            ("owner_name", "Fritz Meier"),
        )
        check = _screener()._check_2b_owner_match(facts)
        assert check.verdict == CheckVerdict.INCONCLUSIVE
        assert check.requires_llm is True
        assert check.is_hard_fail is False

    def test_skipped_missing_policyholder(self):
        facts = _make_facts(
            ("owner_name", "Hans Muster"),
        )
        check = _screener()._check_2b_owner_match(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_missing_owner(self):
        facts = _make_facts(
            ("policyholder_name", "Hans Muster"),
        )
        check = _screener()._check_2b_owner_match(facts)
        assert check.verdict == CheckVerdict.SKIPPED


# ═══════════════════════════════════════════════════════════════════════
# CHECK 3: MILEAGE
# ═══════════════════════════════════════════════════════════════════════


class TestCheck3Mileage:
    """Tests for _check_3_mileage."""

    def test_pass_within_limit(self):
        facts = _make_facts(
            ("km_limited_to", "150000"),
            ("odometer_km", "74359"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.PASS
        assert check.is_hard_fail is True
        assert check.check_id == "3"

    def test_pass_at_exact_limit(self):
        facts = _make_facts(
            ("km_limited_to", "150000"),
            ("odometer_km", "150000"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_fail_exceeds_limit(self):
        facts = _make_facts(
            ("km_limited_to", "150000"),
            ("odometer_km", "160000"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.FAIL
        assert check.is_hard_fail is True

    def test_swiss_number_format(self):
        facts = _make_facts(
            ("km_limited_to", "150'000"),
            ("odometer_km", "74'359"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_km_suffix_stripped(self):
        facts = _make_facts(
            ("km_limited_to", "150000 km"),
            ("odometer_km", "74359 km"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_skipped_missing_limit(self):
        facts = _make_facts(
            ("odometer_km", "74359"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_missing_odometer(self):
        facts = _make_facts(
            ("km_limited_to", "150000"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_fallback_to_vehicle_current_km(self):
        """When odometer_km is missing, falls back to vehicle_current_km."""
        facts = _make_facts(
            ("km_limited_to", "150000"),
            ("vehicle_current_km", "74359"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_evidence_contains_values(self):
        facts = _make_facts(
            ("km_limited_to", "150000"),
            ("odometer_km", "74359"),
        )
        check = _screener()._check_3_mileage(facts)
        assert check.evidence["km_limited_to"] == 150000
        assert check.evidence["current_odometer"] == 74359


# ═══════════════════════════════════════════════════════════════════════
# CHECK 4a: SHOP AUTHORIZATION
# ═══════════════════════════════════════════════════════════════════════


class TestCheck4aShopAuth:
    """Tests for _check_4a_shop_auth.

    Note: These tests now verify the integrated shop authorization lookup
    (merged from enrichment stage in Phase 6 cleanup). The method now takes
    a facts list and does its own lookup from assumptions.json.
    """

    def test_pass_authorized(self):
        """Shop matching authorized partner (AMAG) should pass."""
        facts = [{"name": "garage_name", "value": "AMAG Bern Wankdorf"}]
        check = _screener()._check_4a_shop_auth(facts)
        assert check.verdict == CheckVerdict.PASS
        assert check.check_id == "4a"
        assert check.is_hard_fail is False
        assert "AMAG" in check.reason

    def test_pass_authorized_by_pattern(self):
        """Shop matching authorized pattern should pass."""
        facts = [{"name": "garage_name", "value": "AMAG Zürich Altstetten"}]
        check = _screener()._check_4a_shop_auth(facts)
        assert check.verdict == CheckVerdict.PASS

    def test_inconclusive_unknown(self):
        """Shop not in authorized list should be inconclusive (unknown)."""
        facts = [{"name": "garage_name", "value": "Random Garage GmbH"}]
        check = _screener()._check_4a_shop_auth(facts)
        assert check.verdict == CheckVerdict.INCONCLUSIVE
        assert check.requires_llm is True

    def test_skipped_no_garage_name(self):
        """Missing garage_name should skip the check."""
        facts = []
        check = _screener()._check_4a_shop_auth(facts)
        assert check.verdict == CheckVerdict.SKIPPED


# ═══════════════════════════════════════════════════════════════════════
# CHECK 4b: SERVICE COMPLIANCE
# ═══════════════════════════════════════════════════════════════════════


class TestCheck4bServiceCompliance:
    """Tests for _check_4b_service_compliance."""

    def test_pass_recent_service(self):
        facts = _make_facts(("document_date", "2026-06-15"))
        structured = {
            "service_entries": [
                {"service_date": "2026-01-10"},
                {"service_date": "2025-06-01"},
            ]
        }
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert check.verdict == CheckVerdict.PASS
        assert check.check_id == "4b"

    def test_fail_service_gap_exceeds_36_months(self):
        facts = _make_facts(("document_date", "2026-06-15"))
        structured = {
            "service_entries": [
                {"service_date": "2022-01-01"},
            ]
        }
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert check.verdict == CheckVerdict.FAIL
        assert check.requires_llm is True
        assert check.is_hard_fail is False

    def test_skipped_no_service_entries(self):
        facts = _make_facts(("document_date", "2026-06-15"))
        structured = {}
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_no_claim_date(self):
        facts = []
        structured = {"service_entries": [{"service_date": "2026-01-10"}]}
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_skipped_unparseable_service_dates(self):
        facts = _make_facts(("document_date", "2026-06-15"))
        structured = {
            "service_entries": [
                {"service_date": "invalid"},
                {"service_date": "also bad"},
            ]
        }
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_uses_most_recent_service(self):
        """Should use the most recent service date, not the first one."""
        facts = _make_facts(("document_date", "2026-06-15"))
        structured = {
            "service_entries": [
                {"service_date": "2024-01-01"},  # Old
                {"service_date": "2026-03-01"},  # Recent
                {"service_date": "2025-01-01"},  # Middle
            ]
        }
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert check.verdict == CheckVerdict.PASS  # 2026-06-15 - 2026-03-01 = ~106 days

    def test_evidence_contains_gap_days(self):
        facts = _make_facts(("document_date", "2026-06-15"))
        structured = {"service_entries": [{"service_date": "2026-01-10"}]}
        check = _screener()._check_4b_service_compliance(facts, structured)
        assert "days_since_last_service" in check.evidence


# ═══════════════════════════════════════════════════════════════════════
# CHECK 5: COMPONENT COVERAGE
# ═══════════════════════════════════════════════════════════════════════


class TestCheck5ComponentCoverage:
    """Tests for _check_5_component_coverage."""

    def _make_coverage_result(
        self,
        items_covered=1,
        items_not_covered=0,
        items_review_needed=0,
        line_items=None,
    ):
        """Build a minimal CoverageAnalysisResult."""
        from context_builder.coverage.schemas import (
            CoverageAnalysisResult,
            CoverageInputs,
            CoverageMetadata,
            CoverageSummary,
            CoverageStatus,
            LineItemCoverage,
            MatchMethod,
            PrimaryRepairResult,
        )

        if line_items is None:
            line_items = []
            if items_covered > 0:
                line_items.append(
                    LineItemCoverage(
                        description="Motorblock reparatur",
                        item_type="parts",
                        total_price=3500.0,
                        coverage_status=CoverageStatus.COVERED,
                        coverage_category="engine",
                        matched_component="engine",
                        match_method=MatchMethod.KEYWORD,
                        match_confidence=0.85,
                        match_reasoning="Matched engine keyword",
                        covered_amount=3500.0,
                    )
                )
            if items_not_covered > 0:
                line_items.append(
                    LineItemCoverage(
                        description="Felgenreinigung",
                        item_type="parts",
                        total_price=200.0,
                        coverage_status=CoverageStatus.NOT_COVERED,
                        coverage_category=None,
                        match_method=MatchMethod.RULE,
                        match_confidence=1.0,
                        match_reasoning="Consumable item",
                        not_covered_amount=200.0,
                    )
                )
            if items_review_needed > 0:
                line_items.append(
                    LineItemCoverage(
                        description="Ambiguous part",
                        item_type="parts",
                        total_price=800.0,
                        coverage_status=CoverageStatus.REVIEW_NEEDED,
                        coverage_category=None,
                        match_method=MatchMethod.LLM,
                        match_confidence=0.5,
                        match_reasoning="Unclear coverage",
                    )
                )

        # Build primary_repair based on line items (mirrors analyzer logic)
        primary_repair = None
        covered_parts = [
            i for i in line_items
            if i.coverage_status == CoverageStatus.COVERED
            and i.item_type in ("parts", "part", "piece")
        ]
        if covered_parts:
            best = max(covered_parts, key=lambda x: x.total_price or 0)
            primary_repair = PrimaryRepairResult(
                component=best.matched_component,
                category=best.coverage_category,
                description=best.description,
                is_covered=True,
                confidence=best.match_confidence or 0.90,
                determination_method="deterministic",
            )
        else:
            not_covered_parts = [
                i for i in line_items
                if i.coverage_status == CoverageStatus.NOT_COVERED
                and i.item_type in ("parts", "part", "piece")
            ]
            if not_covered_parts:
                best = max(not_covered_parts, key=lambda x: x.total_price or 0)
                primary_repair = PrimaryRepairResult(
                    component=best.matched_component,
                    category=best.coverage_category,
                    description=best.description,
                    is_covered=False,
                    confidence=best.match_confidence or 0.90,
                    determination_method="deterministic",
                )

        return CoverageAnalysisResult(
            claim_id="CLM-TEST",
            line_items=line_items,
            summary=CoverageSummary(
                items_covered=items_covered,
                items_not_covered=items_not_covered,
                items_review_needed=items_review_needed,
                total_covered_before_excess=sum(
                    i.covered_amount for i in line_items
                ),
                total_not_covered=sum(i.not_covered_amount for i in line_items),
            ),
            primary_repair=primary_repair,
        )

    def test_pass_covered_items_exist(self):
        coverage = self._make_coverage_result(items_covered=1)
        check = _screener()._check_5_component_coverage(coverage)
        assert check.verdict == CheckVerdict.PASS
        assert check.check_id == "5"
        assert check.is_hard_fail is True

    def test_fail_no_covered_items(self):
        coverage = self._make_coverage_result(items_covered=0, items_not_covered=2)
        check = _screener()._check_5_component_coverage(coverage)
        assert check.verdict == CheckVerdict.FAIL

    def test_inconclusive_review_needed(self):
        coverage = self._make_coverage_result(
            items_covered=0, items_not_covered=0, items_review_needed=1
        )
        check = _screener()._check_5_component_coverage(coverage)
        assert check.verdict == CheckVerdict.INCONCLUSIVE
        assert check.requires_llm is True

    def test_skipped_no_coverage_result(self):
        check = _screener()._check_5_component_coverage(None)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_pass_with_mixed_covered_and_uncovered(self):
        """If there are both covered and uncovered items, PASS (primary is covered)."""
        coverage = self._make_coverage_result(items_covered=1, items_not_covered=1)
        check = _screener()._check_5_component_coverage(coverage)
        assert check.verdict == CheckVerdict.PASS

    def test_evidence_includes_counts(self):
        coverage = self._make_coverage_result(items_covered=2, items_not_covered=1)
        check = _screener()._check_5_component_coverage(coverage)
        assert check.evidence["items_covered"] == 2
        assert check.evidence["items_not_covered"] == 1


# ═══════════════════════════════════════════════════════════════════════
# CHECK 5b: ASSISTANCE ITEMS
# ═══════════════════════════════════════════════════════════════════════


class TestCheck5bAssistanceItems:
    """Tests for _check_5b_assistance_items."""

    def test_pass_no_assistance_items(self):
        structured = {
            "line_items": [
                {"description": "Motorblock reparatur", "total_price": 3500.0},
                {"description": "Dichtung Zylinderkopf", "total_price": 450.0},
            ]
        }
        check = _screener()._check_5b_assistance_items(structured)
        assert check.verdict == CheckVerdict.PASS
        assert check.check_id == "5b"
        assert check.is_hard_fail is False

    def test_inconclusive_rental_car_found(self):
        structured = {
            "line_items": [
                {"description": "Ersatzfahrzeug 5 Tage", "total_price": 500.0},
            ]
        }
        check = _screener()._check_5b_assistance_items(structured)
        assert check.verdict == CheckVerdict.INCONCLUSIVE
        assert check.requires_llm is True

    def test_inconclusive_towing_found(self):
        structured = {
            "line_items": [
                {"description": "Abschleppkosten", "total_price": 250.0},
            ]
        }
        check = _screener()._check_5b_assistance_items(structured)
        assert check.verdict == CheckVerdict.INCONCLUSIVE

    def test_skipped_no_line_items(self):
        structured = {}
        check = _screener()._check_5b_assistance_items(structured)
        assert check.verdict == CheckVerdict.SKIPPED

    def test_multiple_assistance_items(self):
        structured = {
            "line_items": [
                {"description": "Ersatzfahrzeug", "total_price": 500.0},
                {"description": "Abschleppkosten", "total_price": 200.0},
                {"description": "Motorblock", "total_price": 3500.0},
            ]
        }
        check = _screener()._check_5b_assistance_items(structured)
        assert check.verdict == CheckVerdict.INCONCLUSIVE
        assert check.evidence["assistance_items_found"] == 2

    def test_case_insensitive_keyword_match(self):
        structured = {
            "line_items": [
                {"description": "ersatzfahrzeug miete", "total_price": 300.0},
            ]
        }
        check = _screener()._check_5b_assistance_items(structured)
        assert check.verdict == CheckVerdict.INCONCLUSIVE


# ═══════════════════════════════════════════════════════════════════════
# FULL SCREENING FLOW (screen method)
# ═══════════════════════════════════════════════════════════════════════


class TestScreenFullFlow:
    """Tests for NSAScreener.screen() top-level orchestration."""

    def test_all_checks_present(self):
        """screen() should produce exactly 9 checks."""
        screener = _screener()
        # Prevent actual coverage analysis
        screener._run_coverage_analysis = MagicMock(return_value=None)

        facts = {
            "facts": _make_facts(
                ("start_date", "2025-01-01"),
                ("end_date", "2026-12-31"),
                ("document_date", "2026-06-15"),
                ("damage_date", "2026-05-01"),
                ("km_limited_to", "150000"),
                ("odometer_km", "74359"),
                ("policyholder_name", "Hans Muster"),
                ("owner_name", "Hans Muster"),
            ),
            "structured_data": {},
        }
        result, coverage = screener.screen("CLM-TEST", facts)

        assert len(result.checks) == 9
        check_ids = {c.check_id for c in result.checks}
        assert check_ids == {"1", "1b", "2", "2b", "3", "4a", "4b", "5", "5b"}

    def test_auto_reject_on_hard_fail(self):
        """A hard-fail check should trigger auto_reject."""
        screener = _screener()
        screener._run_coverage_analysis = MagicMock(return_value=None)

        facts = {
            "facts": _make_facts(
                ("start_date", "2025-01-01"),
                ("end_date", "2025-12-31"),  # Expired
                ("document_date", "2026-06-15"),
                ("km_limited_to", "150000"),
                ("odometer_km", "74359"),
            ),
            "structured_data": {},
        }
        result, _ = screener.screen("CLM-TEST", facts)

        assert result.auto_reject is True
        assert "1" in result.hard_fails

    def test_no_auto_reject_all_pass(self):
        """No hard-fail checks → no auto-reject."""
        screener = _screener()
        screener._run_coverage_analysis = MagicMock(return_value=None)

        facts = {
            "facts": _make_facts(
                ("start_date", "2025-01-01"),
                ("end_date", "2027-12-31"),
                ("document_date", "2026-06-15"),
                ("damage_date", "2026-05-01"),
                ("km_limited_to", "150000"),
                ("odometer_km", "74359"),
                ("policyholder_name", "Hans Muster"),
                ("owner_name", "Hans Muster"),
            ),
            "structured_data": {},
        }
        result, _ = screener.screen("CLM-TEST", facts)

        assert result.auto_reject is False
        assert result.hard_fails == []

    def test_counts_computed(self):
        screener = _screener()
        screener._run_coverage_analysis = MagicMock(return_value=None)

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

        total = result.checks_passed + result.checks_failed + result.checks_inconclusive
        skipped = sum(1 for c in result.checks if c.verdict == CheckVerdict.SKIPPED)
        assert total + skipped == 9


# ═══════════════════════════════════════════════════════════════════════
# POLICYHOLDER TYPE DETECTION
# ═══════════════════════════════════════════════════════════════════════


class TestPolicyholderTypeDetection:
    """Tests for _determine_policyholder_type."""

    def test_individual(self):
        assert _screener()._determine_policyholder_type("Hans Muster") == "individual"

    def test_company_ag(self):
        assert _screener()._determine_policyholder_type("Muster AG") == "company"

    def test_company_gmbh(self):
        assert _screener()._determine_policyholder_type("Muster GmbH") == "company"

    def test_company_sa(self):
        assert _screener()._determine_policyholder_type("Muster SA") == "company"

    def test_company_sarl(self):
        assert _screener()._determine_policyholder_type("Muster Sàrl") == "company"

    def test_empty_name_defaults_individual(self):
        assert _screener()._determine_policyholder_type("") == "individual"
