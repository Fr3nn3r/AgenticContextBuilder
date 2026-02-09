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
                "text": "Flat-rate labor hours limit.",
                "short_name": "Flat-rate labor hours",
                "category": "limitation",
                "evaluation_level": "line_item",
                "evaluability_tier": 1,
                "default_assumption": True,
                "assumption_question": None,
            },
            {
                "reference": "2.4.A.h",
                "text": "Administrative fees excluded.",
                "short_name": "Administrative fees exclusion",
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
        assert len(registry["clauses"]) == 10

    def test_engine_evaluates_only_enabled_clauses(self, engine):
        """Engine should skip disabled clauses (enabled=false) during evaluation."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        evaluated_refs = {e.clause_reference for e in dossier.clause_evaluations}
        assert "2.2.B" not in evaluated_refs
        assert "2.3.A.q" not in evaluated_refs
        assert len(dossier.clause_evaluations) == 8

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


class TestVerdictDetermination:
    """Test claim-level verdict logic."""

    def test_all_pass_no_data_gives_approve(self, engine):
        """When everything passes, verdict is APPROVE (assumptions are treated as facts)."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        # No failed clauses, assumptions treated as accepted facts → APPROVE
        assert len(dossier.failed_clauses) == 0
        assert dossier.claim_verdict.value == "APPROVE"
        assert len(dossier.unresolved_assumptions) == 0

    def test_tier1_fail_gives_deny(self, engine):
        screening = _make_screening([
            {"check_id": "1", "verdict": "FAIL", "reason": "Policy expired"},
        ])
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={}, screening_result=screening)
        assert dossier.claim_verdict.value == "DENY"

    def test_unconfirmed_assumptions_still_approves(self, engine):
        """Tier 3 with unconfirmed assumption → APPROVE (assumptions are accepted facts)."""
        dossier = engine.evaluate(claim_id="CLM-001", aggregated_facts={})
        # Default tier 3 assumptions are non-rejecting (True) → PASS
        # Assumptions are treated as facts, no REFER
        assert dossier.claim_verdict.value == "APPROVE"
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
        assert dossier.engine_version == "1.1.0"
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
