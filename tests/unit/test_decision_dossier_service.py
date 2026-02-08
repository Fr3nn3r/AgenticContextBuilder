"""Tests for DecisionDossierService."""

import json
from pathlib import Path

import pytest

from context_builder.api.services.decision_dossier import DecisionDossierService


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace with a claim and dossier files."""
    # Claim folder structure
    claim_dir = tmp_path / "claims" / "CLM-001" / "claim_runs" / "run-001"
    claim_dir.mkdir(parents=True)

    # Write claim facts
    facts = {"facts": [{"name": "policy_start_date", "value": "2025-01-01"}]}
    with open(claim_dir / "claim_facts.json", "w") as f:
        json.dump(facts, f)

    # Write two dossier versions
    dossier_v1 = {
        "schema_version": "decision_dossier_v1",
        "claim_id": "CLM-001",
        "version": 1,
        "claim_verdict": "REFER",
        "verdict_reason": "Unconfirmed assumptions",
        "clause_evaluations": [],
        "line_item_decisions": [],
        "assumptions_used": [],
        "financial_summary": None,
        "engine_id": "test",
        "engine_version": "1.0.0",
        "evaluation_timestamp": "2026-02-08T10:00:00",
        "input_refs": {},
        "failed_clauses": [],
        "unresolved_assumptions": ["2.3.A.q"],
    }
    with open(claim_dir / "decision_dossier_v1.json", "w") as f:
        json.dump(dossier_v1, f)

    dossier_v2 = dossier_v1.copy()
    dossier_v2["version"] = 2
    dossier_v2["claim_verdict"] = "APPROVE"
    dossier_v2["verdict_reason"] = "All clauses passed"
    dossier_v2["unresolved_assumptions"] = []
    with open(claim_dir / "decision_dossier_v2.json", "w") as f:
        json.dump(dossier_v2, f)

    return tmp_path


@pytest.fixture
def service(workspace):
    """Create a DecisionDossierService."""
    claims_dir = workspace / "claims"
    return DecisionDossierService(claims_dir, workspace)


class TestGetLatestDossier:
    def test_returns_latest_version(self, service):
        result = service.get_latest_dossier("CLM-001", "run-001")
        assert result is not None
        assert result["version"] == 2
        assert result["claim_verdict"] == "APPROVE"

    def test_returns_none_for_missing_claim(self, service):
        result = service.get_latest_dossier("NONEXISTENT")
        assert result is None

    def test_auto_detects_latest_run(self, service):
        result = service.get_latest_dossier("CLM-001")
        assert result is not None
        assert result["version"] == 2


class TestListVersions:
    def test_lists_all_versions(self, service):
        versions = service.list_versions("CLM-001", "run-001")
        assert len(versions) == 2
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2

    def test_empty_for_missing_claim(self, service):
        versions = service.list_versions("NONEXISTENT")
        assert versions == []


class TestGetVersion:
    def test_gets_specific_version(self, service):
        result = service.get_version("CLM-001", 1, "run-001")
        assert result is not None
        assert result["version"] == 1
        assert result["claim_verdict"] == "REFER"

    def test_returns_none_for_missing_version(self, service):
        result = service.get_version("CLM-001", 99, "run-001")
        assert result is None


class TestEvaluateWithAssumptions:
    def test_creates_new_version(self, service, workspace):
        result = service.evaluate_with_assumptions(
            claim_id="CLM-001",
            assumptions={"2.3.A.q": False},
            claim_run_id="run-001",
        )
        assert result is not None
        assert result["version"] == 3

        # Verify file was written
        run_dir = workspace / "claims" / "CLM-001" / "claim_runs" / "run-001"
        assert (run_dir / "decision_dossier_v3.json").exists()

    def test_returns_none_for_missing_claim(self, service):
        result = service.evaluate_with_assumptions(
            claim_id="NONEXISTENT",
            assumptions={},
        )
        assert result is None


class TestGetClauseRegistry:
    def test_empty_when_no_engine(self, service):
        registry = service.get_clause_registry()
        assert registry == []

    def test_loads_from_engine(self, workspace):
        # Create a mock engine
        engine_dir = workspace / "config" / "decision"
        engine_dir.mkdir(parents=True)
        (engine_dir / "engine.py").write_text(
            '''
class TestEngine:
    engine_id = "test"
    engine_version = "1.0.0"

    def __init__(self, workspace_path):
        pass

    def evaluate(self, claim_id, aggregated_facts, **kwargs):
        return {}

    def get_clause_registry(self):
        return [{"reference": "2.2.A", "short_name": "Test clause"}]
'''
        )

        claims_dir = workspace / "claims"
        service = DecisionDossierService(claims_dir, workspace)
        registry = service.get_clause_registry()
        assert len(registry) == 1
        assert registry[0]["reference"] == "2.2.A"
