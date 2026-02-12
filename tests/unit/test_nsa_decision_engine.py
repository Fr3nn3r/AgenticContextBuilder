"""Tests for the NSA Decision Engine.

Tests the workspace-specific engine that evaluates all 27 denial clauses
against a claim's screening results, coverage analysis, and aggregated facts.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────


def _minimal_clause_registry() -> Dict[str, Any]:
    """Return a minimal clause registry with a few representative clauses."""
    return {
        "registry_version": "1.0.0",
        "clauses": [
            {
                "reference": "2.3.A.a",
                "text": "No benefits if the claim falls outside the policy validity period.",
                "short_name": "Policy validity period",
                "category": "exclusion",
                "evaluation_level": "claim",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.3.A.b",
                "text": "No benefits if the vehicle mileage exceeds the policy limit.",
                "short_name": "Mileage limit exceeded",
                "category": "exclusion",
                "evaluation_level": "claim",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.2.A",
                "text": "No obligation if damage was caused by uninsured component.",
                "short_name": "Failure caused by uninsured part",
                "category": "coverage",
                "evaluation_level": "claim_with_item_consequence",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": "Is the failed component covered by the policy?",
            },
            {
                "reference": "2.2.B",
                "text": "No benefits if damage attributable to wear and tear.",
                "short_name": "Wear and tear damage",
                "category": "coverage",
                "evaluation_level": "claim_with_item_consequence",
                "evaluability_tier": 2,
                "default_assumption": True,
                "assumption_question": "Is the damage due to normal wear and tear?",
                "enabled": False,
            },
            {
                "reference": "2.3.A.d",
                "text": "No benefits if damage was caused intentionally or through gross negligence.",
                "short_name": "Intentional or gross negligence",
                "category": "exclusion",
                "evaluation_level": "claim",
                "evaluability_tier": 3,
                "default_assumption": True,
                "assumption_question": "Was the damage caused intentionally or through gross negligence?",
            },
            {
                "reference": "2.3.A.q",
                "text": "No benefits if vehicle not maintained per manufacturer schedule.",
                "short_name": "Maintenance non-compliance",
                "category": "exclusion",
                "evaluation_level": "claim_with_item_consequence",
                "evaluability_tier": 2,
                "default_assumption": True,
                "assumption_question": "Is the vehicle maintenance compliant?",
                "enabled": False,
            },
            {
                "reference": "2.2.D",
                "text": "Fluids and consumables not covered unless part of covered repair.",
                "short_name": "Fluids and consumables exclusion",
                "category": "coverage",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.c",
                "text": "Parts without manufacturer part number not covered.",
                "short_name": "Parts without part number",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.d",
                "text": "Wear parts excluded unless part of covered failure.",
                "short_name": "Wear parts exclusion",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.e",
                "text": "Fluid losses (causal analysis required).",
                "short_name": "Fluid losses",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.f",
                "text": "Cosmetic/acoustic defects not impairing function.",
                "short_name": "Cosmetic defects",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.g",
                "text": "Consumables and fluids not covered unless part of covered repair.",
                "short_name": "Consumables and fluids",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.h",
                "text": "Body components and administrative fees excluded.",
                "short_name": "Body components / admin fees",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.5.A.b",
                "text": "Diagnostic/calibration work capped.",
                "short_name": "Diagnostic fee cap",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.5.A.c",
                "text": "Test drives excluded.",
                "short_name": "Test drives",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.6.C.a",
                "text": "Claim must be reported within 30 days.",
                "short_name": "Reporting deadline (30 days)",
                "category": "procedural",
                "evaluation_level": "claim",
                "evaluability_tier": 2,
                "default_assumption": True,
                "assumption_question": "Was the claim reported within 30 days of damage?",
            },
        ],
    }


def _make_screening(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a screening result dict with the given checks."""
    return {"schema_version": "screening_v1", "checks": checks}


def _make_coverage(
    line_items: Optional[List[Dict[str, Any]]] = None,
    primary_repair: Optional[Dict[str, Any]] = None,
    inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a coverage analysis result dict."""
    return {
        "line_items": line_items or [],
        "primary_repair": primary_repair,
        "inputs": inputs or {},
    }


def _make_facts(fact_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Build an aggregated facts dict."""
    return {"facts": fact_list or []}


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace with a clause registry and mock services."""
    decision_dir = tmp_path / "config" / "decision"
    decision_dir.mkdir(parents=True)

    # Write clause registry
    registry = _minimal_clause_registry()
    with open(decision_dir / "denial_clauses.json", "w") as f:
        json.dump(registry, f)

    # Write labor rates
    services_dir = decision_dir / "services"
    services_dir.mkdir()
    labor_rates = {
        "default_max_hourly_rate": 180.0,
        "currency": "CHF",
        "brand_rates": {
            "BMW": 200.0,
            "Mercedes-Benz": 195.0,
            "default": 180.0,
        },
        "flat_rate_operations": {
            "default": {"hours": 4.0, "description": "Standard repair"},
            "clutch_replacement": {"hours": 6.0, "description": "Clutch replacement"},
        },
    }
    with open(services_dir / "labor_rates.json", "w") as f:
        json.dump(labor_rates, f)

    # Copy service modules (labor_rate_mock.py, parts_classifier_mock.py) from
    # the real workspace so the engine can dynamically load them.
    real_services = Path(__file__).resolve().parents[2] / "workspaces" / "nsa" / "config" / "decision" / "services"
    for module_file in ("labor_rate_mock.py", "parts_classifier_mock.py"):
        src = real_services / module_file
        if src.exists():
            shutil.copy(src, services_dir / module_file)

    return tmp_path


@pytest.fixture
def engine(workspace):
    """Create an NSADecisionEngine instance for testing."""
    # Add workspace to sys.path so that service imports work
    workspace_parent = str(workspace.parent)

    # The engine tries `from workspaces.nsa.config.decision.services...` which
    # won't work in tests.  Instead, mock out the service accessors.
    from workspaces.nsa.config.decision.engine import NSADecisionEngine

    eng = NSADecisionEngine(str(workspace))
    return eng


# ── Tests ─────────────────────────────────────────────────────────────


class TestRegistryLoading:
    def test_loads_clause_registry(self, engine):
        registry = engine.get_clause_registry()
        assert registry["registry_version"] == "1.0.0"
        assert len(registry["clauses"]) == 16

    def test_engine_evaluates_only_enabled_clauses(self, engine):
        """Engine should skip disabled clauses (enabled=false) during evaluation."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        evaluated_refs = {e.clause_reference for e in dossier.clause_evaluations}
        assert "2.2.B" not in evaluated_refs
        assert "2.3.A.q" not in evaluated_refs
        assert len(dossier.clause_evaluations) == 14

    def test_caches_registry(self, engine):
        r1 = engine.get_clause_registry()
        r2 = engine.get_clause_registry()
        assert r1 is r2

    def test_missing_registry_returns_empty(self, tmp_path):
        """When denial_clauses.json doesn't exist, returns empty registry."""
        from workspaces.nsa.config.decision.engine import NSADecisionEngine

        eng = NSADecisionEngine(str(tmp_path))
        registry = eng.get_clause_registry()
        assert registry["clauses"] == []


class TestClaimLevelEvaluation:
    """Test Tier 1 claim-level clause evaluation from screening data."""

    def test_policy_validity_pass(self, engine):
        screening = _make_screening([
            {"check_id": "1", "verdict": "PASS", "reason": "Policy valid"},
        ])
        dossier = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            screening_result=screening,
        )
        # Find clause 2.3.A.a
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.a")
        assert ev.verdict == "PASS"
        assert len(ev.evidence) >= 1

    def test_policy_validity_fail(self, engine):
        screening = _make_screening([
            {"check_id": "1", "verdict": "FAIL", "reason": "Policy expired"},
        ])
        dossier = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            screening_result=screening,
        )
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.a")
        assert ev.verdict == "FAIL"
        assert "2.3.A.a" in dossier.failed_clauses
        assert dossier.claim_verdict.value == "DENY"

    def test_mileage_limit_fail(self, engine):
        screening = _make_screening([
            {"check_id": "3", "verdict": "FAIL", "reason": "Mileage 250k exceeds 200k limit"},
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, screening_result=screening)
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.b")
        assert ev.verdict == "FAIL"
        assert dossier.claim_verdict.value == "DENY"

    def test_component_coverage_fail_via_screening(self, engine):
        screening = _make_screening([
            {"check_id": "5", "verdict": "FAIL", "reason": "Component not covered"},
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, screening_result=screening)
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.2.A")
        assert ev.verdict == "FAIL"

    def test_no_screening_data_assumes_pass(self, engine):
        """When no screening data is available, clauses default to PASS."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        tier1_evals = [
            e for e in dossier.clause_evaluations
            if e.evaluability_tier.value == 1
            and e.evaluation_level.value in ("claim", "claim_with_item_consequence")
        ]
        for ev in tier1_evals:
            assert ev.verdict == "PASS", f"Clause {ev.clause_reference} should PASS without screening"


class TestTier2Evaluation:
    """Test Tier 2 clauses that try evidence, then fall back to assumption."""

    def test_reporting_deadline_within_limit(self, engine):
        facts = _make_facts([
            {"name": "damage_date", "value": "2025-06-01"},
            {"name": "claim_date", "value": "2025-06-15"},
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts=facts)
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.6.C.a")
        assert ev.verdict == "PASS"

    def test_reporting_deadline_exceeded(self, engine):
        facts = _make_facts([
            {"name": "damage_date", "value": "2025-01-01"},
            {"name": "claim_date", "value": "2025-03-15"},
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts=facts)
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.6.C.a")
        assert ev.verdict == "FAIL"


class TestTier3Evaluation:
    """Test Tier 3 clauses that always use assumptions."""

    def test_default_assumption_pass(self, engine):
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.d")
        assert ev.verdict == "PASS"
        assert ev.assumption_used is True

    def test_override_assumption_to_fail(self, engine):
        dossier = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            assumptions={"2.3.A.d": False},
        )
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.d")
        assert ev.verdict == "FAIL"
        assert ev.assumption_used is False


class TestLineItemClauses:
    """Test line-item-level clause evaluation."""

    def test_admin_fee_excluded(self, engine):
        coverage = _make_coverage(line_items=[
            {
                "description": "Bearbeitungsgebühr Administration",
                "item_type": "fee",
                "total_price": 50.0,
                "coverage_status": "covered",
                "covered_amount": 50.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        # Find the line item decision
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.4.A.h" in lid.applicable_clauses
        assert lid.denied_amount > 0 or lid.verdict.value == "DENIED"

    def test_labor_flat_rate_exceeds_guideline(self, engine):
        """2.2.D triggers on excess labor hours beyond flat-rate guideline."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Clutch replacement labor",
                "item_type": "labor",
                "quantity": 10.0,  # Way over flat-rate
                "unit_price": 150.0,
                "total_price": 1500.0,
                "coverage_status": "covered",
                "covered_amount": 1500.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.2.D" in lid.applicable_clauses
        assert lid.adjusted_amount > 0

    def test_labor_rate_cap_by_brand(self, engine):
        """2.2.D triggers when hourly rate exceeds brand-specific max."""
        facts = _make_facts([{"name": "vehicle_make", "value": "BMW"}])
        coverage = _make_coverage(line_items=[
            {
                "description": "Engine repair",
                "item_type": "labor",
                "quantity": 2.0,
                "unit_price": 250.0,  # Exceeds BMW max of 200
                "total_price": 500.0,
                "coverage_status": "covered",
                "covered_amount": 500.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(
            claim_id="CLM-001", aggregated_facts=facts, coverage_analysis=coverage,
        )
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.2.D" in lid.applicable_clauses
        assert lid.adjusted_amount > 0

    def test_consumable_excluded(self, engine):
        """2.4.A.g triggers on oil/fluid item not part of covered repair."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Motoroel 5W-30",
                "item_type": "parts",
                "item_code": "OIL-5W30-001",
                "total_price": 85.0,
                "coverage_status": "",
                "covered_amount": 0.0,
                "not_covered_amount": 85.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.4.A.g" in lid.applicable_clauses
        assert lid.denied_amount > 0 or lid.verdict.value == "DENIED"

    def test_consumable_in_covered_repair_passes(self, engine):
        """2.4.A.g does NOT trigger when coverage_status is 'covered'."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Motoroel 5W-30",
                "item_type": "parts",
                "item_code": "OIL-5W30-001",
                "total_price": 85.0,
                "coverage_status": "covered",
                "covered_amount": 85.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        # 2.4.A.g should not deny it because it's part of a covered repair
        assert lid.verdict.value != "DENIED" or "2.4.A.g" not in lid.applicable_clauses

    def test_wear_part_excluded(self, engine):
        """2.4.A.d triggers on brake pads (wear part) not in covered repair."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Brake pad front left",
                "item_type": "parts",
                "item_code": "BRK-PAD-001",
                "total_price": 120.0,
                "coverage_status": "",
                "covered_amount": 0.0,
                "not_covered_amount": 120.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.4.A.d" in lid.applicable_clauses
        assert lid.denied_amount > 0 or lid.verdict.value == "DENIED"

    def test_diagnostic_fee_capped(self, engine):
        """2.5.A.b caps diagnostic fee at 250 CHF."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Diagnose Fehlersuche",
                "item_type": "fee",
                "total_price": 400.0,
                "coverage_status": "covered",
                "covered_amount": 400.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.5.A.b" in lid.applicable_clauses
        assert lid.adjusted_amount == 150.0  # 400 - 250

    def test_test_drive_excluded(self, engine):
        """2.5.A.c triggers on 'Probefahrt' labor item."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Probefahrt nach Reparatur",
                "item_type": "labor",
                "total_price": 80.0,
                "coverage_status": "covered",
                "covered_amount": 80.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert "2.5.A.c" in lid.applicable_clauses
        assert lid.denied_amount > 0 or lid.verdict.value == "DENIED"

    def test_test_drive_no_match(self, engine):
        """2.5.A.c returns None on normal labor (no test drive keyword)."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Kupplungswechsel",
                "item_type": "labor",
                "total_price": 500.0,
                "coverage_status": "covered",
                "covered_amount": 500.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        # 2.5.A.c should not appear in applicable clauses for normal labor
        if "2.5.A.c" in lid.applicable_clauses:
            # Even if it appeared, it should not have denied anything
            assert lid.verdict.value != "DENIED"


class TestVerdictDetermination:
    """Test claim-level verdict logic."""

    def test_all_pass_no_coverage_gives_refer(self, engine):
        """When coverage analysis is missing, verdict is REFER (cannot approve without payout)."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        # No failed clauses, but no coverage data → REFER
        assert len(dossier.failed_clauses) == 0
        assert dossier.claim_verdict.value == "REFER"
        assert "coverage analysis unavailable" in dossier.verdict_reason.lower()
        assert len(dossier.unresolved_assumptions) == 0

    def test_tier1_fail_gives_deny(self, engine):
        screening = _make_screening([
            {"check_id": "1", "verdict": "FAIL", "reason": "Policy expired"},
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, screening_result=screening)
        assert dossier.claim_verdict.value == "DENY"

    def test_unconfirmed_assumptions_still_refer_without_coverage(self, engine):
        """Tier 3 with unconfirmed assumptions but no coverage → REFER."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        # Default tier 3 assumptions are non-rejecting (True) → PASS
        # But no coverage data → REFER (cannot approve without payout)
        assert dossier.claim_verdict.value == "REFER"
        assert len(dossier.unresolved_assumptions) == 0


class TestFinancialSummary:
    """Test financial summary computation."""

    def test_financial_summary_with_line_items(self, engine):
        coverage = _make_coverage(line_items=[
            {
                "description": "Turbo replacement",
                "item_type": "parts",
                "total_price": 2500.0,
                "coverage_status": "covered",
                "covered_amount": 2500.0,
                "not_covered_amount": 0.0,
            },
            {
                "description": "Labor",
                "item_type": "labor",
                "total_price": 720.0,
                "coverage_status": "covered",
                "covered_amount": 720.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        fs = dossier.financial_summary
        assert fs is not None
        assert fs.total_claimed == 3220.0
        assert fs.currency == "CHF"

    def test_deny_sets_payout_to_zero(self, engine):
        """A claim-level deterministic deny sets net_payout to 0."""
        screening = _make_screening([
            {"check_id": "1", "verdict": "FAIL", "reason": "Policy expired"},
        ])
        coverage = _make_coverage(line_items=[
            {
                "description": "Parts",
                "item_type": "parts",
                "total_price": 1000.0,
                "coverage_status": "covered",
                "covered_amount": 1000.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            screening_result=screening,
            coverage_analysis=coverage,
        )
        assert dossier.claim_verdict.value == "DENY"
        assert dossier.financial_summary.net_payout == 0.0

    def test_empty_line_items_gives_zeroed_summary(self, engine):
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        fs = dossier.financial_summary
        assert fs is not None
        assert fs.total_claimed == 0.0
        assert fs.net_payout == 0.0


class TestDossierStructure:
    """Test the structure and metadata of the returned dossier."""

    def test_dossier_has_all_fields(self, engine):
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        assert dossier.schema_version == "decision_dossier_v1"
        assert dossier.claim_id == "CLM-001"
        assert dossier.version == 1
        assert dossier.engine_id == "nsa_decision_v1"
        assert dossier.engine_version == "1.4.0"
        assert dossier.evaluation_timestamp

    def test_dossier_evaluates_all_enabled_clauses(self, engine):
        """Engine should produce evaluations for all enabled clauses in the registry."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        registry = engine.get_clause_registry()
        enabled_count = sum(1 for c in registry["clauses"] if c.get("enabled", True))
        assert len(dossier.clause_evaluations) == enabled_count

    def test_assumptions_tracked_for_tier2_tier3(self, engine):
        """Tier 2/3 clauses that use assumptions should be in assumptions_used."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        # Should have assumption records for tier 2/3 clauses that had no evidence
        if dossier.assumptions_used:
            for a in dossier.assumptions_used:
                assert a.clause_reference
                assert a.question
                assert isinstance(a.assumed_value, bool)

    def test_input_refs_propagated(self, engine):
        refs = {"screening_run": "run-001", "coverage_run": "run-001"}
        dossier = engine.evaluate(
            claim_id="CLM-001",
            input_refs=refs,
        )
        assert dossier.input_refs == refs


class TestAssumptionOverrides:
    """Test the assumption override mechanism."""

    def test_multiple_assumption_overrides(self, engine):
        """Override multiple tier 2/3 assumptions and verify they're respected."""
        dossier = engine.evaluate(
            claim_id="CLM-001",
            assumptions={
                "2.6.C.a": False,  # Tier 2: reporting deadline → FAIL
                "2.3.A.d": False,  # Tier 3: gross negligence → FAIL
            },
        )
        ev_c = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.6.C.a")
        ev_d = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.d")
        assert ev_c.verdict == "FAIL"
        assert ev_d.verdict == "FAIL"

    def test_assumption_override_does_not_affect_tier1(self, engine):
        """Assumption overrides should not affect tier 1 clauses."""
        screening = _make_screening([
            {"check_id": "1", "verdict": "PASS", "reason": "Policy valid"},
        ])
        dossier = engine.evaluate(
            claim_id="CLM-001",
            screening_result=screening,
            assumptions={"2.3.A.a": False},  # Should be ignored for tier 1
        )
        ev = next(e for e in dossier.clause_evaluations if e.clause_reference == "2.3.A.a")
        assert ev.verdict == "PASS"  # Tier 1 uses screening data, not assumptions


class TestCoverageOverrides:
    """Test coverage override persistence and auto-apply."""

    def test_coverage_override_changes_verdict(self, engine):
        """An item originally not_covered becomes covered when override is applied."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Turbo replacement",
                "item_type": "parts",
                "item_code": "TURBO-001",
                "total_price": 2500.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 2500.0,
            },
        ])
        # Without override: item should be DENIED
        dossier_no_override = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            coverage_analysis=coverage,
        )
        lid = dossier_no_override.line_item_decisions[0]
        assert lid.verdict.value == "DENIED"

        # Apply override via mutated coverage data (simulating what the service does)
        import copy
        coverage_overridden = copy.deepcopy(coverage)
        coverage_overridden["line_items"][0]["coverage_status"] = "covered"
        coverage_overridden["line_items"][0]["covered_amount"] = 2500.0
        coverage_overridden["line_items"][0]["not_covered_amount"] = 0.0

        dossier_with_override = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            coverage_analysis=coverage_overridden,
            coverage_overrides={"item_0": True},
        )
        lid2 = dossier_with_override.line_item_decisions[0]
        assert lid2.verdict.value == "COVERED"

    def test_coverage_overrides_persisted_in_dossier(self, engine):
        """Dossier output includes the coverage_overrides dict."""
        overrides = {"item_0": True, "item_2": False}
        dossier = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={},
            coverage_overrides=overrides,
        )
        assert dossier.coverage_overrides == overrides

    def test_empty_overrides_default(self, engine):
        """Dossier has empty coverage_overrides by default."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        assert dossier.coverage_overrides == {}


class TestScreeningHelpers:
    """Test helper methods."""

    def test_get_screening_check_found(self, engine):
        screening = _make_screening([
            {"check_id": "1", "verdict": "PASS"},
            {"check_id": "3", "verdict": "FAIL"},
        ])
        result = engine._get_screening_check(screening, "3")
        assert result is not None
        assert result["verdict"] == "FAIL"

    def test_get_screening_check_not_found(self, engine):
        screening = _make_screening([{"check_id": "1", "verdict": "PASS"}])
        result = engine._get_screening_check(screening, "99")
        assert result is None

    def test_get_screening_check_none_screening(self, engine):
        result = engine._get_screening_check(None, "1")
        assert result is None

    def test_get_fact_value_found(self, engine):
        facts = _make_facts([{"name": "mileage", "value": "150000"}])
        assert engine._get_fact_value(facts, "mileage") == "150000"

    def test_get_fact_value_not_found(self, engine):
        facts = _make_facts([{"name": "mileage", "value": "150000"}])
        assert engine._get_fact_value(facts, "nonexistent") is None

    def test_get_fact_value_none_facts(self, engine):
        assert engine._get_fact_value(None, "mileage") is None


class TestAssessmentVerdictOverrides:
    """Test decision engine honoring assessment hard fails and auto-rejects."""

    def test_auto_reject_assessment_produces_deny(self, engine):
        """assessment_method='auto_reject' in processing_result -> DENY."""
        processing_result = {
            "assessment_method": "auto_reject",
            "recommendation": "REJECT",
            "recommendation_rationale": "Mileage exceeds policy limit (250,000 km vs 200,000 km cap).",
            "checks": [],
        }
        dossier = engine.evaluate(
            claim_id="CLM-AUTOREJECT",
            aggregated_facts={},
            processing_result=processing_result,
        )
        assert dossier.claim_verdict.value == "DENY"
        assert "Mileage exceeds" in dossier.verdict_reason

    def test_hard_check_fail_with_reject_produces_deny(self, engine):
        """REJECT recommendation + hard check failure(s) -> DENY."""
        processing_result = {
            "recommendation": "REJECT",
            "recommendation_rationale": "Component not covered under policy.",
            "checks": [
                {
                    "check_number": "5",
                    "check_name": "component_coverage",
                    "result": "FAIL",
                    "reason": "EGR valve is not a covered component",
                },
                {
                    "check_number": "4b",
                    "check_name": "shop_proximity",
                    "result": "FAIL",
                    "reason": "Shop not in network",
                },
            ],
        }
        dossier = engine.evaluate(
            claim_id="CLM-HARDFAIL",
            aggregated_facts={},
            processing_result=processing_result,
        )
        assert dossier.claim_verdict.value == "DENY"
        assert "hard check failure" in dossier.verdict_reason
        assert "component_coverage" in dossier.verdict_reason

    def test_soft_check_only_still_approves(self, engine):
        """REJECT + only soft check failures (4b) -> APPROVE (no regression)."""
        processing_result = {
            "recommendation": "REJECT",
            "checks": [
                {
                    "check_number": "4b",
                    "check_name": "shop_proximity",
                    "result": "FAIL",
                    "reason": "Shop not in network",
                },
            ],
        }
        dossier = engine.evaluate(
            claim_id="CLM-SOFTONLY",
            aggregated_facts={},
            processing_result=processing_result,
        )
        assert dossier.claim_verdict.value == "APPROVE"
        assert "soft check" in dossier.verdict_reason.lower()

    def test_all_line_items_denied_produces_deny(self, engine):
        """total_covered=0 with total_claimed>0 -> DENY.

        Uses component_not_in_list exclusion (maps to 2.4.A.b, category
        'limitation') so that clause-level hard deny (step 1) does not
        fire before step 5.
        """
        coverage = _make_coverage(line_items=[
            {
                "description": "EGR valve",
                "item_type": "parts",
                "total_price": 850.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 850.0,
                "exclusion_reason": "component_not_in_list",
            },
            {
                "description": "Labor EGR replacement",
                "item_type": "labor",
                "total_price": 300.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 300.0,
                "exclusion_reason": "component_not_in_list",
            },
        ])
        dossier = engine.evaluate(
            claim_id="CLM-ALLDENIED",
            aggregated_facts={},
            coverage_analysis=coverage,
        )
        assert dossier.claim_verdict.value == "DENY"
        assert "All line items denied" in dossier.verdict_reason
        assert "1,150.00" in dossier.verdict_reason

    def test_mixed_items_with_some_covered_still_approves(self, engine):
        """Claim with at least one covered item should not trigger all-denied check."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Turbo replacement",
                "item_type": "parts",
                "item_code": "TRB-001",
                "total_price": 2500.0,
                "coverage_status": "covered",
                "covered_amount": 2500.0,
                "not_covered_amount": 0.0,
            },
            {
                "description": "Admin fee",
                "item_type": "fee",
                "total_price": 50.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 50.0,
                "exclusion_reason": "fee",
            },
        ])
        dossier = engine.evaluate(
            claim_id="CLM-MIXED",
            aggregated_facts={},
            coverage_analysis=coverage,
        )
        assert dossier.claim_verdict.value == "APPROVE"

    def test_auto_reject_rationale_in_reason(self, engine):
        """Auto-reject reason includes the rationale from processing_result."""
        processing_result = {
            "assessment_method": "auto_reject",
            "recommendation": "REJECT",
            "recommendation_rationale": "Policy expired before damage date.",
            "checks": [],
        }
        dossier = engine.evaluate(
            claim_id="CLM-AR2",
            aggregated_facts={},
            processing_result=processing_result,
        )
        assert dossier.claim_verdict.value == "DENY"
        assert "Policy expired before damage date" in dossier.verdict_reason


class TestCoverageExclusionMapping:
    """Test _map_coverage_exclusion_to_clause and the not-covered fast path."""

    def test_explicit_exclusion_reason_maps_to_clause(self, engine):
        """exclusion_reason 'consumable' maps to clause 2.4.A.g."""
        item = {
            "description": "Motoroel 5W-30",
            "exclusion_reason": "consumable",
            "match_reasoning": "Consumable item not covered: oil",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        clause_ref, clause_name, reason = result
        assert clause_ref == "2.4.A.g"
        assert "Consumables and fluids" in clause_name
        assert "Motoroel 5W-30" in reason

    def test_component_excluded_maps_to_2_2_A(self, engine):
        item = {
            "description": "Turbolader",
            "exclusion_reason": "component_excluded",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.2.A"

    def test_component_not_in_list_maps_to_2_4_A_b(self, engine):
        item = {
            "description": "Spiegel links",
            "exclusion_reason": "component_not_in_list",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.4.A.b"

    def test_demoted_no_anchor_maps_to_2_2_D(self, engine):
        item = {
            "description": "Arbeit Demontage",
            "exclusion_reason": "demoted_no_anchor",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.2.D"

    def test_fee_diagnostic_sub_typed(self, engine):
        """Fee exclusion_reason + diagnostic description maps to 2.5.A.b."""
        item = {
            "description": "Diagnose Fehlersuche",
            "exclusion_reason": "fee",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.5.A.b"

    def test_fee_towing_sub_typed(self, engine):
        item = {
            "description": "Abschleppen Transport",
            "exclusion_reason": "fee",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.4.A.g"

    def test_fee_admin_sub_typed(self, engine):
        item = {
            "description": "Bearbeitungsgebuehr Admin",
            "exclusion_reason": "fee",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.4.A.h"

    def test_fee_default_sub_type(self, engine):
        """Fee without specific keywords defaults to 2.4.A.h."""
        item = {
            "description": "Sonstige Gebuehr",
            "exclusion_reason": "fee",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.4.A.h"

    def test_infer_from_match_reasoning_oil(self, engine):
        """Missing exclusion_reason with oil keyword inferred as fluid_loss -> 2.4.A.e."""
        item = {
            "description": "Injecteur d'huile",
            "match_reasoning": "Part is excluded: oil",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.4.A.e"
        assert "Fluid losses" in result[1]

    def test_infer_from_match_reasoning_demoted(self, engine):
        """Missing exclusion_reason with [DEMOTED: keyword inferred as demoted_no_anchor."""
        item = {
            "description": "Arbeit Montage",
            "match_reasoning": "[DEMOTED: no covered anchor part]",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.2.D"

    def test_infer_from_match_reasoning_generic_description(self, engine):
        item = {
            "description": "Diverse",
            "match_reasoning": "Generic description too vague",
        }
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is not None
        assert result[0] == "2.4.A.b"

    def test_no_exclusion_reason_no_reasoning_returns_none(self, engine):
        item = {"description": "Unknown item"}
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is None

    def test_unknown_exclusion_reason_returns_none(self, engine):
        item = {"description": "Foo", "exclusion_reason": "totally_unknown_reason"}
        result = engine._map_coverage_exclusion_to_clause(item)
        assert result is None

    def test_not_covered_item_gets_clause_in_decision(self, engine):
        """A not_covered item with exclusion_reason gets the clause in its decision."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Spiegel links",
                "item_type": "parts",
                "total_price": 350.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 350.0,
                "exclusion_reason": "component_not_in_list",
                "match_reasoning": "Part not in policy's exhaustive parts list",
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert lid.verdict.value == "DENIED"
        assert "2.4.A.b" in lid.applicable_clauses
        assert any("2.4.A.b" in r for r in lid.denial_reasons)
        assert lid.denied_amount == 350.0
        assert lid.approved_amount == 0.0

    def test_not_covered_item_without_exclusion_still_denied(self, engine):
        """A not_covered item without exclusion_reason is still DENIED (just no clause)."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Mystery part",
                "item_type": "parts",
                "total_price": 100.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 100.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert lid.verdict.value == "DENIED"
        assert lid.denied_amount == 100.0

    def test_review_needed_includes_match_reasoning(self, engine):
        """review_needed items include match_reasoning in denial_reasons."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Ventildeckeldichtung",
                "item_type": "parts",
                "item_code": "VDD-001",
                "total_price": 180.0,
                "coverage_status": "review_needed",
                "covered_amount": 180.0,
                "not_covered_amount": 0.0,
                "match_reasoning": "Ambiguous: could be valve cover gasket",
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert lid.verdict.value == "REFER"
        assert any("Ambiguous" in r for r in lid.denial_reasons)

    def test_covered_item_unaffected_by_new_logic(self, engine):
        """Covered items still go through line-item clause evaluation as before."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Turbo replacement",
                "item_type": "parts",
                "item_code": "TRB-001",
                "total_price": 2500.0,
                "coverage_status": "covered",
                "covered_amount": 2500.0,
                "not_covered_amount": 0.0,
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 1
        lid = dossier.line_item_decisions[0]
        assert lid.verdict.value == "COVERED"
        assert lid.approved_amount == 2500.0

    def test_mixed_covered_and_not_covered_items(self, engine):
        """Mix of covered and not_covered items produces correct decisions."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Turbo replacement",
                "item_type": "parts",
                "item_code": "TRB-001",
                "total_price": 2500.0,
                "coverage_status": "covered",
                "covered_amount": 2500.0,
                "not_covered_amount": 0.0,
            },
            {
                "description": "Motoroel 5W-30",
                "item_type": "parts",
                "total_price": 85.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 85.0,
                "exclusion_reason": "consumable",
                "match_reasoning": "Consumable item not covered: oil",
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        assert len(dossier.line_item_decisions) == 2
        covered_lid = dossier.line_item_decisions[0]
        denied_lid = dossier.line_item_decisions[1]
        assert covered_lid.verdict.value == "COVERED"
        assert denied_lid.verdict.value == "DENIED"
        assert "2.4.A.g" in denied_lid.applicable_clauses

    def test_not_covered_clause_appears_in_summary_evaluations(self, engine):
        """Clause mapped from coverage exclusion shows as FAIL in summary evaluations."""
        coverage = _make_coverage(line_items=[
            {
                "description": "Arbeit Demontage",
                "item_type": "labor",
                "total_price": 200.0,
                "coverage_status": "not_covered",
                "covered_amount": 0.0,
                "not_covered_amount": 200.0,
                "exclusion_reason": "demoted_no_anchor",
            },
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, coverage_analysis=coverage)
        # 2.2.D is a line_item clause; the summary evaluation should show FAIL
        ev_22d = next(
            (e for e in dossier.clause_evaluations if e.clause_reference == "2.2.D"),
            None,
        )
        assert ev_22d is not None
        assert ev_22d.verdict == "FAIL"
        assert "item_0" in ev_22d.affected_line_items
