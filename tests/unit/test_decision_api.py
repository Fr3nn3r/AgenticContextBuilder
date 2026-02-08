"""Tests for the decision dossier API router."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from context_builder.api.services.decision_dossier import DecisionDossierService


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace with dossier files."""
    claim_dir = tmp_path / "claims" / "CLM-001" / "claim_runs" / "run-001"
    claim_dir.mkdir(parents=True)

    # Write claim facts
    facts = {"facts": [{"name": "policy_start_date", "value": "2025-01-01"}]}
    with open(claim_dir / "claim_facts.json", "w") as f:
        json.dump(facts, f)

    # Write a dossier
    dossier = {
        "schema_version": "decision_dossier_v1",
        "claim_id": "CLM-001",
        "version": 1,
        "claim_verdict": "APPROVE",
        "verdict_reason": "All clauses passed",
        "clause_evaluations": [],
        "line_item_decisions": [],
        "assumptions_used": [],
        "financial_summary": None,
        "engine_id": "test",
        "engine_version": "1.0.0",
        "evaluation_timestamp": "2026-02-08T10:00:00",
        "input_refs": {},
        "failed_clauses": [],
        "unresolved_assumptions": [],
    }
    with open(claim_dir / "decision_dossier_v1.json", "w") as f:
        json.dump(dossier, f)

    return tmp_path


@pytest.fixture
def service(workspace):
    """Create a DecisionDossierService backed by the tmp workspace."""
    return DecisionDossierService(workspace / "claims", workspace)


@pytest.fixture
def client(service):
    """Create a test client that patches the dependency at the router module level."""
    from context_builder.api.routers import decision as decision_module
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(decision_module.router)

    with patch.object(
        decision_module,
        "get_decision_dossier_service",
        return_value=service,
    ):
        yield TestClient(app)


class TestGetLatestDossier:
    def test_returns_dossier(self, client):
        resp = client.get("/api/claims/CLM-001/decision-dossier?claim_run_id=run-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["claim_id"] == "CLM-001"
        assert data["claim_verdict"] == "APPROVE"

    def test_404_for_missing_claim(self, client):
        resp = client.get("/api/claims/NONEXISTENT/decision-dossier")
        assert resp.status_code == 404


class TestListVersions:
    def test_returns_versions(self, client):
        resp = client.get("/api/claims/CLM-001/decision-dossier/versions?claim_run_id=run-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["version"] == 1


class TestGetVersion:
    def test_returns_specific_version(self, client):
        resp = client.get("/api/claims/CLM-001/decision-dossier/1?claim_run_id=run-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1

    def test_404_for_missing_version(self, client):
        resp = client.get("/api/claims/CLM-001/decision-dossier/99?claim_run_id=run-001")
        assert resp.status_code == 404


class TestEvaluateDecision:
    def test_creates_new_version(self, client):
        resp = client.post(
            "/api/claims/CLM-001/decision-dossier/evaluate",
            json={"assumptions": {}, "claim_run_id": "run-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 2  # New version created

    def test_500_for_missing_claim(self, client):
        resp = client.post(
            "/api/claims/NONEXISTENT/decision-dossier/evaluate",
            json={"assumptions": {}},
        )
        assert resp.status_code == 500


class TestGetDenialClauses:
    def test_returns_empty_without_engine(self, client):
        resp = client.get("/api/denial-clauses")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []
