"""Tests for DashboardService workbench enrichment fields."""

import json
from pathlib import Path

import pytest

from context_builder.api.services.dashboard import DashboardService


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace with claims directory."""
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()
    return tmp_path


def _make_claim(workspace, claim_id="CLM-001", run_id="run-001",
                facts=None, dossier=None, screening=None, assessment=None):
    """Helper to create a claim with optional data files.

    Always writes a minimal assessment.json so _load_latest_assessment
    returns a valid claim_run_id (required for enrichment).
    """
    claims_dir = workspace / "claims"
    claim_dir = claims_dir / claim_id
    claim_dir.mkdir(exist_ok=True)

    if run_id:
        run_dir = claim_dir / "claim_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        if facts is not None:
            with open(run_dir / "claim_facts.json", "w") as f:
                json.dump(facts, f)

        if dossier is not None:
            version = dossier.get("version", 1)
            with open(run_dir / f"decision_dossier_v{version}.json", "w") as f:
                json.dump(dossier, f)

        if screening is not None:
            with open(run_dir / "screening.json", "w") as f:
                json.dump(screening, f)

        # Always write assessment so claim_run_id is resolved
        assess = assessment or {"decision": "REFER", "checks": []}
        with open(run_dir / "assessment.json", "w") as f:
            json.dump(assess, f)


class TestListClaimsWorkbenchFields:
    """Test that list_claims includes workbench enrichment fields."""

    def test_includes_workbench_fields(self, workspace):
        """Verify new fields populated from facts/dossier/screening."""
        facts = {
            "facts": [
                {"name": "policy_number", "value": "POL-12345"},
                {"name": "vehicle_make", "value": "Toyota"},
                {"name": "vehicle_model", "value": "Corolla"},
                {"name": "cost_estimate.document_date", "value": "2025-06-15"},
            ]
        }
        dossier = {
            "version": 1,
            "claim_verdict": "APPROVE",
            "verdict_reason": "All clauses passed",
            "clause_evaluations": [
                {"clause_reference": "2.1", "verdict": "PASS"},
            ],
            "confidence_index": {
                "composite_score": 0.85,
                "band": "high",
            },
        }
        screening = {
            "payout": {"final_payout": 1234.56},
        }
        _make_claim(workspace, facts=facts, dossier=dossier, screening=screening)

        svc = DashboardService(workspace / "claims")
        results = svc.list_claims()
        assert len(results) == 1

        claim = results[0]
        assert claim["policy_number"] == "POL-12345"
        assert claim["vehicle"] == "Toyota Corolla"
        assert claim["event_date"] == "2025-06-15"
        assert claim["verdict"] == "APPROVE"
        assert claim["verdict_reason"] == "All clauses passed"
        assert claim["cci_score"] == 0.85
        assert claim["cci_band"] == "high"
        assert claim["has_dossier"] is True
        # screening_payout populated because payout (from assessment) is None
        assert claim["screening_payout"] == 1234.56

    def test_no_dossier(self, workspace):
        """When no dossier exists, has_dossier=False, verdict/rationale None."""
        facts = {
            "facts": [
                {"name": "policy_number", "value": "POL-999"},
            ]
        }
        _make_claim(workspace, facts=facts, dossier=None)

        svc = DashboardService(workspace / "claims")
        results = svc.list_claims()
        claim = results[0]

        assert claim["has_dossier"] is False
        assert claim["verdict"] is None
        assert claim["verdict_reason"] is None
        assert claim["cci_score"] is None
        assert claim["cci_band"] is None

    def test_no_facts(self, workspace):
        """When no claim_facts.json exists, policy/vehicle/event_date are None."""
        dossier = {
            "version": 1,
            "claim_verdict": "REFER",
            "verdict_reason": "Insufficient data",
            "clause_evaluations": [],
            "confidence_index": {"composite_score": 0.5, "band": "low"},
        }
        _make_claim(workspace, facts=None, dossier=dossier)

        svc = DashboardService(workspace / "claims")
        results = svc.list_claims()
        claim = results[0]

        assert claim["policy_number"] is None
        assert claim["vehicle"] is None
        assert claim["event_date"] is None
        assert claim["has_dossier"] is True
        assert claim["verdict"] == "REFER"

    def test_deny_no_screening_payout(self, workspace):
        """When verdict is DENY, screening_payout should be None."""
        dossier = {
            "version": 1,
            "claim_verdict": "DENY",
            "verdict_reason": "Claim denied. Coverage exclusion applies.",
            "clause_evaluations": [
                {"clause_reference": "3.1", "verdict": "FAIL"},
            ],
            "failed_clauses": [{"clause_reference": "3.1"}],
            "confidence_index": {"composite_score": 0.9, "band": "high"},
        }
        screening = {
            "payout": {"final_payout": 500.00},
        }
        _make_claim(workspace, dossier=dossier, screening=screening)

        svc = DashboardService(workspace / "claims")
        results = svc.list_claims()
        claim = results[0]

        assert claim["verdict"] == "DENY"
        assert claim["screening_payout"] is None

    def test_no_run_id(self, workspace):
        """When claim has no runs, all workbench fields are defaults."""
        claims_dir = workspace / "claims"
        (claims_dir / "CLM-NORUN").mkdir()

        svc = DashboardService(claims_dir)
        results = svc.list_claims()
        claim = results[0]

        assert claim["has_dossier"] is False
        assert claim["policy_number"] is None
        assert claim["vehicle"] is None
        assert claim["verdict"] is None

    def test_screening_payout_skipped_when_assessment_payout_exists(self, workspace):
        """When assessment already has payout, screening_payout stays None."""
        dossier = {
            "version": 1,
            "claim_verdict": "APPROVE",
            "verdict_reason": "OK",
            "clause_evaluations": [],
            "confidence_index": {"composite_score": 0.8, "band": "moderate"},
        }
        assessment = {
            "decision": "APPROVE",
            "confidence_score": 0.8,
            "checks": [],
            "payout": {"final_payout": 2000.0, "currency": "CHF"},
        }
        screening = {
            "payout": {"final_payout": 1800.0},
        }
        _make_claim(workspace, dossier=dossier, assessment=assessment, screening=screening)

        svc = DashboardService(workspace / "claims")
        results = svc.list_claims()
        claim = results[0]

        # Assessment payout exists, so screening_payout should not be loaded
        assert claim["payout"] == 2000.0
        assert claim["screening_payout"] is None


class TestBuildRationale:
    """Test _build_rationale helper."""

    def test_verdict_reason_preferred(self, workspace):
        svc = DashboardService(workspace / "claims")
        dossier = {"verdict_reason": "All checks passed"}
        assert svc._build_rationale(dossier, "APPROVE") == "All checks passed"

    def test_verdict_reason_strips_prefix(self, workspace):
        svc = DashboardService(workspace / "claims")
        dossier = {"verdict_reason": "Claim approved. Coverage confirmed."}
        result = svc._build_rationale(dossier, "APPROVE")
        assert result == "Coverage confirmed."

    def test_deny_fallback_to_failed_clauses(self, workspace):
        svc = DashboardService(workspace / "claims")
        dossier = {
            "failed_clauses": [
                {"clause_reference": "3.1"},
                {"clause_reference": "4.2"},
            ],
            "clause_evaluations": [],
        }
        result = svc._build_rationale(dossier, "DENY")
        assert result == "3.1, 4.2"

    def test_general_fallback_clause_evals(self, workspace):
        svc = DashboardService(workspace / "claims")
        dossier = {
            "clause_evaluations": [
                {"clause_reference": "1.1", "verdict": "PASS"},
                {"clause_reference": "1.2", "verdict": "PASS"},
                {"clause_reference": "1.3", "verdict": "FAIL", "assumption_used": True},
            ],
        }
        result = svc._build_rationale(dossier, "REFER")
        assert result == "2/3 passed, 1 assumed"

    def test_empty_dossier(self, workspace):
        svc = DashboardService(workspace / "claims")
        dossier = {"clause_evaluations": []}
        assert svc._build_rationale(dossier, "REFER") is None


class TestGetFactValue:
    """Test _get_fact_value helper."""

    def test_returns_value(self, workspace):
        svc = DashboardService(workspace / "claims")
        facts = {"facts": [{"name": "policy_number", "value": "POL-123"}]}
        assert svc._get_fact_value(facts, "policy_number") == "POL-123"

    def test_returns_normalized_value(self, workspace):
        svc = DashboardService(workspace / "claims")
        facts = {"facts": [{"name": "km", "normalized_value": "50000"}]}
        assert svc._get_fact_value(facts, "km") == "50000"

    def test_returns_none_for_missing(self, workspace):
        svc = DashboardService(workspace / "claims")
        facts = {"facts": [{"name": "other", "value": "x"}]}
        assert svc._get_fact_value(facts, "policy_number") is None

    def test_returns_none_for_none_input(self, workspace):
        svc = DashboardService(workspace / "claims")
        assert svc._get_fact_value(None, "anything") is None


class TestFindLatestDossier:
    """Test _find_latest_dossier helper."""

    def test_finds_latest_version(self, workspace):
        svc = DashboardService(workspace / "claims")
        run_dir = workspace / "test_run"
        run_dir.mkdir()
        (run_dir / "decision_dossier_v1.json").write_text("{}")
        (run_dir / "decision_dossier_v2.json").write_text("{}")
        (run_dir / "decision_dossier_v3.json").write_text("{}")

        result = svc._find_latest_dossier(run_dir)
        assert result is not None
        assert result.name == "decision_dossier_v3.json"

    def test_returns_none_when_no_dossier(self, workspace):
        svc = DashboardService(workspace / "claims")
        run_dir = workspace / "empty_run"
        run_dir.mkdir()

        assert svc._find_latest_dossier(run_dir) is None
