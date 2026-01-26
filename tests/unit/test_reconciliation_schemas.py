"""Unit tests for reconciliation schemas."""

import json
import pytest
from datetime import datetime
from pydantic import ValidationError

from context_builder.schemas.reconciliation import (
    FactConflict,
    FactFrequency,
    GateStatus,
    GateThresholds,
    ReconciliationClaimResult,
    ReconciliationEvalSummary,
    ReconciliationGate,
    ReconciliationReport,
    ReconciliationResult,
    ReconciliationRunEval,
)


class TestGateStatus:
    """Tests for GateStatus enum."""

    def test_pass_value(self):
        """Test PASS enum value."""
        assert GateStatus.PASS.value == "pass"

    def test_warn_value(self):
        """Test WARN enum value."""
        assert GateStatus.WARN.value == "warn"

    def test_fail_value(self):
        """Test FAIL enum value."""
        assert GateStatus.FAIL.value == "fail"

    def test_from_string(self):
        """Test creating enum from string value."""
        assert GateStatus("pass") == GateStatus.PASS
        assert GateStatus("warn") == GateStatus.WARN
        assert GateStatus("fail") == GateStatus.FAIL


class TestFactConflict:
    """Tests for FactConflict schema."""

    def test_required_fields(self):
        """Test that required fields are enforced."""
        conflict = FactConflict(
            fact_name="vehicle_vin",
            values=["VIN-AAA", "VIN-BBB"],
            sources=[["doc1"], ["doc2"]],
            selected_value="VIN-AAA",
            selected_confidence=0.9,
        )

        assert conflict.fact_name == "vehicle_vin"
        assert len(conflict.values) == 2
        assert conflict.selected_confidence == 0.9

    def test_default_selection_reason(self):
        """Test that selection_reason has default value."""
        conflict = FactConflict(
            fact_name="test",
            values=["a", "b"],
            sources=[["doc1"], ["doc2"]],
            selected_value="a",
            selected_confidence=0.9,
        )

        assert conflict.selection_reason == "highest_confidence"

    def test_custom_selection_reason(self):
        """Test setting custom selection reason."""
        conflict = FactConflict(
            fact_name="test",
            values=["a", "b"],
            sources=[["doc1"], ["doc2"]],
            selected_value="a",
            selected_confidence=0.9,
            selection_reason="most_recent",
        )

        assert conflict.selection_reason == "most_recent"

    def test_serialization(self):
        """Test that conflict serializes to JSON correctly."""
        conflict = FactConflict(
            fact_name="vehicle_vin",
            values=["VIN-AAA", "VIN-BBB"],
            sources=[["doc1", "doc2"], ["doc3"]],
            selected_value="VIN-AAA",
            selected_confidence=0.95,
        )

        data = conflict.model_dump(mode="json")

        assert data["fact_name"] == "vehicle_vin"
        assert data["values"] == ["VIN-AAA", "VIN-BBB"]
        assert data["sources"] == [["doc1", "doc2"], ["doc3"]]
        assert data["selected_confidence"] == 0.95


class TestGateThresholds:
    """Tests for GateThresholds schema."""

    def test_default_values(self):
        """Test that defaults are set correctly."""
        thresholds = GateThresholds()

        assert thresholds.missing_critical_warn == 2
        assert thresholds.missing_critical_fail == 2
        assert thresholds.conflict_warn == 2
        assert thresholds.conflict_fail == 2
        assert thresholds.token_warn == 40000
        assert thresholds.token_fail == 60000

    def test_custom_values(self):
        """Test setting custom threshold values."""
        thresholds = GateThresholds(
            missing_critical_warn=1,
            missing_critical_fail=3,
            conflict_warn=5,
            conflict_fail=10,
            token_warn=50000,
            token_fail=80000,
        )

        assert thresholds.missing_critical_warn == 1
        assert thresholds.missing_critical_fail == 3
        assert thresholds.conflict_warn == 5
        assert thresholds.conflict_fail == 10
        assert thresholds.token_warn == 50000
        assert thresholds.token_fail == 80000


class TestReconciliationGate:
    """Tests for ReconciliationGate schema."""

    def test_required_status(self):
        """Test that status is required."""
        gate = ReconciliationGate(status=GateStatus.PASS)

        assert gate.status == GateStatus.PASS

    def test_default_values(self):
        """Test that defaults are set correctly."""
        gate = ReconciliationGate(status=GateStatus.PASS)

        assert gate.missing_critical_facts == []
        assert gate.conflict_count == 0
        assert gate.provenance_coverage == 0.0
        assert gate.estimated_tokens == 0
        assert gate.reasons == []

    def test_full_gate(self):
        """Test creating a gate with all values."""
        gate = ReconciliationGate(
            status=GateStatus.WARN,
            missing_critical_facts=["policy_number", "vin"],
            conflict_count=3,
            provenance_coverage=0.85,
            estimated_tokens=35000,
            reasons=["2 missing critical facts", "3 conflicts detected"],
        )

        assert gate.status == GateStatus.WARN
        assert len(gate.missing_critical_facts) == 2
        assert gate.conflict_count == 3
        assert gate.provenance_coverage == 0.85


class TestReconciliationReport:
    """Tests for ReconciliationReport schema."""

    def test_required_fields(self):
        """Test creating report with required fields."""
        report = ReconciliationReport(
            claim_id="CLM-001",
            run_id="run_001",
            gate=ReconciliationGate(status=GateStatus.PASS),
        )

        assert report.claim_id == "CLM-001"
        assert report.run_id == "run_001"
        assert report.gate.status == GateStatus.PASS

    def test_default_schema_version(self):
        """Test that schema version has default value."""
        report = ReconciliationReport(
            claim_id="CLM-001",
            run_id="run_001",
            gate=ReconciliationGate(status=GateStatus.PASS),
        )

        assert report.schema_version == "reconciliation_v1"

    def test_default_generated_at(self):
        """Test that generated_at is set automatically."""
        report = ReconciliationReport(
            claim_id="CLM-001",
            run_id="run_001",
            gate=ReconciliationGate(status=GateStatus.PASS),
        )

        assert report.generated_at is not None
        assert isinstance(report.generated_at, datetime)

    def test_full_report_serialization(self):
        """Test full report serializes correctly."""
        report = ReconciliationReport(
            claim_id="CLM-001",
            run_id="run_001",
            generated_at=datetime(2026, 1, 25, 12, 0, 0),
            gate=ReconciliationGate(
                status=GateStatus.WARN,
                missing_critical_facts=["vin"],
                conflict_count=1,
            ),
            conflicts=[
                FactConflict(
                    fact_name="amount",
                    values=["100", "150"],
                    sources=[["doc1"], ["doc2"]],
                    selected_value="150",
                    selected_confidence=0.9,
                )
            ],
            fact_count=25,
            critical_facts_spec=["policy_number", "vin", "amount"],
            critical_facts_present=["policy_number", "amount"],
        )

        data = report.model_dump(mode="json")

        assert data["claim_id"] == "CLM-001"
        assert data["gate"]["status"] == "warn"
        assert len(data["conflicts"]) == 1
        assert data["fact_count"] == 25


class TestReconciliationResult:
    """Tests for ReconciliationResult schema."""

    def test_successful_result(self):
        """Test creating a successful result."""
        report = ReconciliationReport(
            claim_id="CLM-001",
            run_id="run_001",
            gate=ReconciliationGate(status=GateStatus.PASS),
        )
        result = ReconciliationResult(
            claim_id="CLM-001",
            success=True,
            report=report,
        )

        assert result.success is True
        assert result.report is not None
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed result."""
        result = ReconciliationResult(
            claim_id="CLM-001",
            success=False,
            error="Aggregation failed: no extractions found",
        )

        assert result.success is False
        assert result.report is None
        assert result.error is not None


class TestReconciliationClaimResult:
    """Tests for ReconciliationClaimResult schema (run-level)."""

    def test_required_fields(self):
        """Test creating with required fields."""
        result = ReconciliationClaimResult(
            claim_id="CLM-001",
            gate_status=GateStatus.PASS,
        )

        assert result.claim_id == "CLM-001"
        assert result.gate_status == GateStatus.PASS

    def test_default_values(self):
        """Test default values are set."""
        result = ReconciliationClaimResult(
            claim_id="CLM-001",
            gate_status=GateStatus.PASS,
        )

        assert result.fact_count == 0
        assert result.conflict_count == 0
        assert result.missing_critical_count == 0
        assert result.missing_critical_facts == []
        assert result.provenance_coverage == 0.0
        assert result.reasons == []


class TestFactFrequency:
    """Tests for FactFrequency schema."""

    def test_required_fields(self):
        """Test creating with required fields."""
        freq = FactFrequency(
            fact_name="policy_number",
            count=5,
        )

        assert freq.fact_name == "policy_number"
        assert freq.count == 5
        assert freq.claim_ids == []

    def test_with_claim_ids(self):
        """Test including claim IDs."""
        freq = FactFrequency(
            fact_name="vin",
            count=3,
            claim_ids=["CLM-001", "CLM-002", "CLM-003"],
        )

        assert len(freq.claim_ids) == 3


class TestReconciliationEvalSummary:
    """Tests for ReconciliationEvalSummary schema."""

    def test_default_values(self):
        """Test that all defaults are zero/empty."""
        summary = ReconciliationEvalSummary()

        assert summary.total_claims == 0
        assert summary.passed == 0
        assert summary.warned == 0
        assert summary.failed == 0
        assert summary.pass_rate == 0.0
        assert summary.pass_rate_percent == "0.0%"
        assert summary.avg_fact_count == 0.0
        assert summary.avg_conflicts == 0.0
        assert summary.avg_missing_critical == 0.0
        assert summary.total_conflicts == 0

    def test_full_summary(self):
        """Test creating a full summary."""
        summary = ReconciliationEvalSummary(
            total_claims=10,
            passed=7,
            warned=2,
            failed=1,
            pass_rate=0.7,
            pass_rate_percent="70.0%",
            avg_fact_count=25.5,
            avg_conflicts=1.2,
            avg_missing_critical=0.5,
            total_conflicts=12,
        )

        assert summary.total_claims == 10
        assert summary.passed == 7
        assert summary.pass_rate == 0.7
        assert summary.pass_rate_percent == "70.0%"


class TestReconciliationRunEval:
    """Tests for ReconciliationRunEval schema."""

    def test_default_schema_version(self):
        """Test that schema version has default value."""
        eval_result = ReconciliationRunEval()

        assert eval_result.schema_version == "reconciliation_eval_v1"

    def test_default_evaluated_at(self):
        """Test that evaluated_at is set automatically."""
        eval_result = ReconciliationRunEval()

        assert eval_result.evaluated_at is not None
        assert isinstance(eval_result.evaluated_at, datetime)

    def test_empty_results(self):
        """Test creating with empty results."""
        eval_result = ReconciliationRunEval()

        assert eval_result.run_id is None
        assert eval_result.summary.total_claims == 0
        assert eval_result.top_missing_facts == []
        assert eval_result.top_conflicts == []
        assert eval_result.results == []

    def test_full_evaluation(self):
        """Test creating a full evaluation."""
        eval_result = ReconciliationRunEval(
            run_id="run_001",
            summary=ReconciliationEvalSummary(
                total_claims=5,
                passed=3,
                warned=1,
                failed=1,
            ),
            top_missing_facts=[
                FactFrequency(fact_name="vin", count=2),
            ],
            top_conflicts=[
                FactFrequency(fact_name="amount", count=3),
            ],
            results=[
                ReconciliationClaimResult(
                    claim_id="CLM-001",
                    gate_status=GateStatus.PASS,
                ),
                ReconciliationClaimResult(
                    claim_id="CLM-002",
                    gate_status=GateStatus.FAIL,
                ),
            ],
        )

        assert eval_result.run_id == "run_001"
        assert eval_result.summary.total_claims == 5
        assert len(eval_result.top_missing_facts) == 1
        assert len(eval_result.top_conflicts) == 1
        assert len(eval_result.results) == 2

    def test_serialization_round_trip(self):
        """Test that evaluation survives JSON round-trip."""
        eval_result = ReconciliationRunEval(
            run_id="run_001",
            summary=ReconciliationEvalSummary(
                total_claims=3,
                passed=2,
                warned=1,
                failed=0,
                pass_rate=0.667,
                pass_rate_percent="66.7%",
            ),
            results=[
                ReconciliationClaimResult(
                    claim_id="CLM-001",
                    gate_status=GateStatus.PASS,
                    fact_count=20,
                ),
            ],
        )

        # Serialize to JSON
        json_str = eval_result.model_dump_json()

        # Parse back
        data = json.loads(json_str)

        assert data["run_id"] == "run_001"
        assert data["summary"]["total_claims"] == 3
        assert data["summary"]["pass_rate_percent"] == "66.7%"
        assert data["results"][0]["claim_id"] == "CLM-001"
        assert data["results"][0]["gate_status"] == "pass"
