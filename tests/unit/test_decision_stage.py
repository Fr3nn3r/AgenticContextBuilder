"""Tests for the decision pipeline stage."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context_builder.pipeline.claim_stages.context import (
    ClaimContext,
    ClaimStageConfig,
    ClaimStageTimings,
)
from context_builder.pipeline.claim_stages.decision import (
    DecisionEngine,
    DecisionStage,
    DefaultDecisionEngine,
    load_engine_from_workspace,
)
from context_builder.schemas.decision_dossier import ClaimVerdict


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def workspace(tmp_path):
    """Create a minimal workspace structure."""
    claims_dir = tmp_path / "claims" / "CLM-001" / "claim_runs" / "run-001"
    claims_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def context(workspace):
    """Create a basic ClaimContext for testing."""
    return ClaimContext(
        claim_id="CLM-001",
        workspace_path=workspace,
        run_id="run-001",
        aggregated_facts={
            "facts": [
                {"name": "policy_start_date", "value": "2025-01-01"},
                {"name": "policy_end_date", "value": "2026-12-31"},
                {"name": "claim_date", "value": "2026-02-01"},
            ]
        },
        screening_result={"checks": [], "auto_reject": False},
    )


@pytest.fixture
def sample_dossier():
    """Return a sample dossier dict."""
    return {
        "schema_version": "decision_dossier_v1",
        "claim_id": "CLM-001",
        "version": 1,
        "claim_verdict": ClaimVerdict.APPROVE,
        "verdict_reason": "All clauses passed",
        "clause_evaluations": [
            {
                "clause_reference": "2.2.A",
                "clause_short_name": "Uninsured part",
                "category": "coverage",
                "evaluation_level": "claim_with_item_consequence",
                "evaluability_tier": 1,
                "verdict": "PASS",
                "reason": "Component is covered",
                "evidence": [],
                "affected_line_items": [],
            }
        ],
        "line_item_decisions": [],
        "assumptions_used": [],
        "financial_summary": {
            "total_claimed": 5000.0,
            "total_covered": 4000.0,
            "total_denied": 800.0,
            "total_adjusted": 200.0,
            "net_payout": 4000.0,
            "currency": "CHF",
        },
        "engine_id": "test_engine",
        "engine_version": "1.0.0",
        "evaluation_timestamp": "2026-02-08T10:00:00",
        "input_refs": {},
        "failed_clauses": [],
        "unresolved_assumptions": [],
    }


# ── DefaultDecisionEngine tests ────────────────────────────────────


class TestDefaultDecisionEngine:
    def test_engine_attributes(self, workspace):
        engine = DefaultDecisionEngine(workspace)
        assert engine.engine_id == "default"
        assert engine.engine_version == "0.1.0"

    def test_evaluate_returns_refer_without_processing_result(self, workspace):
        """Without processing_result, verdict is REFER (no data to decide)."""
        engine = DefaultDecisionEngine(workspace)
        result = engine.evaluate(
            claim_id="CLM-001",
            aggregated_facts={"facts": []},
        )
        assert result["claim_verdict"] == ClaimVerdict.REFER
        assert result["schema_version"] == "decision_dossier_v1"
        assert result["claim_id"] == "CLM-001"
        assert result["clause_evaluations"] == []

    def test_evaluate_approve_when_all_checks_pass(self, workspace):
        """All checks PASS + APPROVE -> APPROVE."""
        engine = DefaultDecisionEngine(workspace)
        processing = {
            "recommendation": "APPROVE",
            "recommendation_rationale": "All good",
            "checks": [
                {"check_number": "1", "check_name": "policy_validity", "result": "PASS"},
                {"check_number": "5", "check_name": "component_coverage", "result": "PASS"},
                {"check_number": "7", "check_name": "final_decision", "result": "PASS"},
            ],
            "payout": {"final_payout": 1000.0},
        }
        result = engine.evaluate("CLM-001", {"facts": []}, processing_result=processing)
        assert result["claim_verdict"] == ClaimVerdict.APPROVE

    def test_evaluate_deny_on_hard_check_fail(self, workspace):
        """Hard check FAIL -> DENY."""
        engine = DefaultDecisionEngine(workspace)
        processing = {
            "recommendation": "APPROVE",
            "checks": [
                {"check_number": "1", "check_name": "policy_validity", "result": "FAIL"},
                {"check_number": "7", "check_name": "final_decision", "result": "FAIL"},
            ],
            "payout": {"final_payout": 1000.0},
        }
        result = engine.evaluate("CLM-001", {"facts": []}, processing_result=processing)
        assert result["claim_verdict"] == ClaimVerdict.DENY
        assert "policy_validity" in result["verdict_reason"]

    def test_evaluate_refer_on_inconclusive(self, workspace):
        """INCONCLUSIVE check -> REFER."""
        engine = DefaultDecisionEngine(workspace)
        processing = {
            "recommendation": "REFER_TO_HUMAN",
            "recommendation_rationale": "Mileage unclear",
            "checks": [
                {"check_number": "1", "check_name": "policy_validity", "result": "PASS"},
                {"check_number": "3", "check_name": "mileage_compliance", "result": "INCONCLUSIVE"},
                {"check_number": "7", "check_name": "final_decision", "result": "FAIL"},
            ],
            "payout": {"final_payout": 1000.0},
        }
        result = engine.evaluate("CLM-001", {"facts": []}, processing_result=processing)
        assert result["claim_verdict"] == ClaimVerdict.REFER
        assert "mileage_compliance" in result["verdict_reason"]

    def test_evaluate_deny_on_zero_payout(self, workspace):
        """APPROVE + zero payout -> DENY."""
        engine = DefaultDecisionEngine(workspace)
        processing = {
            "recommendation": "APPROVE",
            "checks": [
                {"check_number": "1", "check_name": "policy_validity", "result": "PASS"},
                {"check_number": "7", "check_name": "final_decision", "result": "PASS"},
            ],
            "payout": {
                "final_payout": 0.0,
                "covered_subtotal": 80.0,
                "deductible": 150.0,
                "currency": "CHF",
            },
        }
        result = engine.evaluate("CLM-001", {"facts": []}, processing_result=processing)
        assert result["claim_verdict"] == ClaimVerdict.DENY
        assert "deductible" in result["verdict_reason"]

    def test_evaluate_refer_from_llm(self, workspace):
        """REFER_TO_HUMAN from LLM with no INCONCLUSIVE checks -> REFER."""
        engine = DefaultDecisionEngine(workspace)
        processing = {
            "recommendation": "REFER_TO_HUMAN",
            "recommendation_rationale": "Uncertain about claim",
            "checks": [
                {"check_number": "1", "check_name": "policy_validity", "result": "PASS"},
            ],
            "payout": {"final_payout": 1000.0},
        }
        result = engine.evaluate("CLM-001", {"facts": []}, processing_result=processing)
        assert result["claim_verdict"] == ClaimVerdict.REFER

    def test_soft_check_ids_empty_by_default(self, workspace):
        """Default engine has no soft checks."""
        engine = DefaultDecisionEngine(workspace)
        assert engine.SOFT_CHECK_IDS == set()

    def test_get_clause_registry_empty(self, workspace):
        engine = DefaultDecisionEngine(workspace)
        assert engine.get_clause_registry() == []


# ── load_engine_from_workspace tests ────────────────────────────────


class TestLoadEngineFromWorkspace:
    def test_no_engine_file(self, workspace):
        engine = load_engine_from_workspace(workspace)
        assert engine is None

    def test_loads_engine_from_file(self, workspace):
        engine_dir = workspace / "config" / "decision"
        engine_dir.mkdir(parents=True)
        engine_file = engine_dir / "engine.py"
        engine_file.write_text(
            '''
class TestEngine:
    engine_id = "test"
    engine_version = "1.0.0"

    def __init__(self, workspace_path):
        self.workspace_path = workspace_path

    def evaluate(self, claim_id, aggregated_facts, **kwargs):
        return {"claim_id": claim_id, "claim_verdict": "APPROVE"}

    def get_clause_registry(self):
        return []
'''
        )

        engine = load_engine_from_workspace(workspace)
        assert engine is not None
        assert engine.engine_id == "test"
        result = engine.evaluate("CLM-001", {"facts": []})
        assert result["claim_verdict"] == ClaimVerdict.APPROVE

    def test_handles_import_error(self, workspace):
        engine_dir = workspace / "config" / "decision"
        engine_dir.mkdir(parents=True)
        engine_file = engine_dir / "engine.py"
        engine_file.write_text("raise ImportError('test')")

        engine = load_engine_from_workspace(workspace)
        assert engine is None


# ── DecisionStage tests ────────────────────────────────────────────


class TestDecisionStage:
    def test_name(self):
        stage = DecisionStage()
        assert stage.name == "decision"

    def test_skip_when_disabled(self, context):
        context.stage_config.run_decision = False
        stage = DecisionStage()
        result = stage.run(context)
        assert result.decision_result is None
        assert result.timings.decision_ms == 0

    def test_skip_when_no_facts(self, workspace):
        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=workspace,
            run_id="run-001",
            aggregated_facts=None,
        )
        stage = DecisionStage()
        result = stage.run(context)
        assert result.decision_result is None

    def test_run_with_default_engine_no_processing(self, context):
        """Without processing_result, default engine returns REFER."""
        stage = DecisionStage()
        result = stage.run(context)
        assert result.decision_result is not None
        assert result.decision_result["claim_verdict"] == ClaimVerdict.REFER
        assert result.decision_result["engine_id"] == "default"

    def test_run_with_default_engine_derives_verdict(self, context):
        """With processing_result, default engine derives verdict from checks."""
        context.processing_result = {
            "recommendation": "APPROVE",
            "checks": [
                {"check_number": "1", "check_name": "policy_validity", "result": "PASS"},
                {"check_number": "7", "check_name": "final_decision", "result": "PASS"},
            ],
            "payout": {"final_payout": 1000.0},
        }
        stage = DecisionStage()
        result = stage.run(context)
        assert result.decision_result is not None
        assert result.decision_result["claim_verdict"] == ClaimVerdict.APPROVE
        assert result.decision_result["engine_id"] == "default"

    def test_run_writes_dossier_file(self, context, workspace):
        stage = DecisionStage()
        result = stage.run(context)

        dossier_path = (
            workspace
            / "claims"
            / "CLM-001"
            / "claim_runs"
            / "run-001"
            / "decision_dossier_v1.json"
        )
        assert dossier_path.exists()
        with open(dossier_path, "r") as f:
            written = json.load(f)
        assert written["claim_id"] == "CLM-001"

    def test_version_increments(self, context, workspace):
        stage = DecisionStage()

        # First run
        result = stage.run(context)
        assert result.decision_result["version"] == 1

        # Second run (simulate by running again)
        context.decision_result = None
        result = stage.run(context)
        assert result.decision_result["version"] == 2

        # Verify both files exist
        run_dir = (
            workspace / "claims" / "CLM-001" / "claim_runs" / "run-001"
        )
        assert (run_dir / "decision_dossier_v1.json").exists()
        assert (run_dir / "decision_dossier_v2.json").exists()

    def test_loads_coverage_analysis(self, context, workspace):
        # Write a coverage_analysis.json for the engine to find
        run_dir = (
            workspace / "claims" / "CLM-001" / "claim_runs" / "run-001"
        )
        coverage = {"summary": {"total_claimed": 5000}}
        with open(run_dir / "coverage_analysis.json", "w") as f:
            json.dump(coverage, f)

        stage = DecisionStage()
        result = stage.run(context)
        assert result.decision_result is not None

    def test_non_fatal_on_engine_error(self, workspace):
        """Engine errors should be caught and logged, not crash pipeline."""
        engine_dir = workspace / "config" / "decision"
        engine_dir.mkdir(parents=True)
        engine_file = engine_dir / "engine.py"
        engine_file.write_text(
            '''
class BrokenEngine:
    engine_id = "broken"
    engine_version = "0.0.0"

    def __init__(self, workspace_path):
        pass

    def evaluate(self, claim_id, aggregated_facts, **kwargs):
        raise RuntimeError("Engine exploded")

    def get_clause_registry(self):
        return []
'''
        )

        context = ClaimContext(
            claim_id="CLM-001",
            workspace_path=workspace,
            run_id="run-001",
            aggregated_facts={"facts": []},
        )
        stage = DecisionStage()
        result = stage.run(context)
        # Should NOT raise — error is caught
        assert result.decision_result is None
        assert result.timings.decision_ms >= 0

    def test_records_timing(self, context):
        stage = DecisionStage()
        result = stage.run(context)
        assert result.timings.decision_ms >= 0

    def test_engine_caching(self, context):
        """Engine should be cached for same workspace."""
        stage = DecisionStage()
        engine1 = stage._get_engine(context.workspace_path)
        engine2 = stage._get_engine(context.workspace_path)
        assert engine1 is engine2

    def test_find_claim_folder_exact(self, workspace):
        stage = DecisionStage()
        folder = stage._find_claim_folder(workspace, "CLM-001")
        assert folder is not None
        assert folder.name == "CLM-001"

    def test_find_claim_folder_partial(self, workspace):
        # Create a folder with prefix
        (workspace / "claims" / "claim_65258").mkdir(parents=True)
        stage = DecisionStage()
        folder = stage._find_claim_folder(workspace, "65258")
        assert folder is not None
        assert "65258" in folder.name

    def test_find_claim_folder_missing(self, workspace):
        stage = DecisionStage()
        folder = stage._find_claim_folder(workspace, "NONEXISTENT")
        assert folder is None

    def test_get_next_version_no_existing(self, workspace):
        stage = DecisionStage()
        claim_folder = workspace / "claims" / "CLM-001"
        version = stage._get_next_version(claim_folder, "run-001")
        assert version == 1

    def test_get_next_version_with_existing(self, workspace):
        run_dir = (
            workspace / "claims" / "CLM-001" / "claim_runs" / "run-001"
        )
        (run_dir / "decision_dossier_v1.json").write_text("{}")
        (run_dir / "decision_dossier_v2.json").write_text("{}")

        stage = DecisionStage()
        claim_folder = workspace / "claims" / "CLM-001"
        version = stage._get_next_version(claim_folder, "run-001")
        assert version == 3


# ── Context integration tests ──────────────────────────────────────


class TestContextIntegration:
    def test_decision_result_field(self):
        ctx = ClaimContext(
            claim_id="CLM-001",
            workspace_path=Path("/tmp"),
            run_id="run-001",
        )
        assert ctx.decision_result is None
        ctx.decision_result = {"claim_verdict": "APPROVE"}
        assert ctx.decision_result["claim_verdict"] == ClaimVerdict.APPROVE

    def test_decision_ms_timing(self):
        timings = ClaimStageTimings()
        assert timings.decision_ms == 0
        timings.decision_ms = 150
        assert timings.decision_ms == 150

    def test_run_decision_config(self):
        config = ClaimStageConfig()
        assert config.run_decision is True
        config.run_decision = False
        assert config.run_decision is False
