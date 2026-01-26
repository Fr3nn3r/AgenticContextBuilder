"""Unit tests for the ReconciliationService."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from context_builder.api.services.reconciliation import (
    ReconciliationError,
    ReconciliationService,
)
from context_builder.schemas.claim_facts import ClaimFacts, AggregatedFact, FactProvenance
from context_builder.schemas.reconciliation import (
    FactConflict,
    GateStatus,
    GateThresholds,
    ReconciliationGate,
    ReconciliationReport,
)


class TestDetectConflicts:
    """Tests for ReconciliationService.detect_conflicts()."""

    @pytest.fixture
    def service(self):
        """Create a ReconciliationService with mocked dependencies."""
        storage = MagicMock()
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    def test_no_conflicts_single_candidate(self, service):
        """Test that single candidates don't produce conflicts."""
        candidates = {
            "policy_number": [
                {"value": "POL-123", "doc_id": "doc1", "confidence": 0.9}
            ],
            "claim_date": [
                {"value": "2026-01-15", "doc_id": "doc2", "confidence": 0.8}
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        assert len(conflicts) == 0

    def test_no_conflicts_same_values(self, service):
        """Test that matching values don't produce conflicts."""
        candidates = {
            "policy_number": [
                {"value": "POL-123", "doc_id": "doc1", "confidence": 0.9},
                {"value": "POL-123", "doc_id": "doc2", "confidence": 0.85},
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        assert len(conflicts) == 0

    def test_detects_single_conflict(self, service):
        """Test detection of a single fact conflict."""
        candidates = {
            "vehicle_vin": [
                {"value": "VIN-AAA", "doc_id": "doc1", "confidence": 0.9},
                {"value": "VIN-BBB", "doc_id": "doc2", "confidence": 0.7},
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.fact_name == "vehicle_vin"
        assert set(conflict.values) == {"VIN-AAA", "VIN-BBB"}
        assert conflict.selected_value == "VIN-AAA"  # Higher confidence
        assert conflict.selected_confidence == 0.9

    def test_detects_multiple_conflicts(self, service):
        """Test detection of multiple fact conflicts."""
        candidates = {
            "vehicle_vin": [
                {"value": "VIN-AAA", "doc_id": "doc1", "confidence": 0.9},
                {"value": "VIN-BBB", "doc_id": "doc2", "confidence": 0.7},
            ],
            "damage_amount": [
                {"value": "5000", "doc_id": "doc1", "confidence": 0.8},
                {"value": "4500", "doc_id": "doc2", "confidence": 0.85},
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        assert len(conflicts) == 2
        fact_names = {c.fact_name for c in conflicts}
        assert fact_names == {"vehicle_vin", "damage_amount"}

    def test_selects_highest_confidence_value(self, service):
        """Test that the highest confidence value is selected."""
        candidates = {
            "repair_cost": [
                {"value": "1000", "doc_id": "doc1", "confidence": 0.6},
                {"value": "1500", "doc_id": "doc2", "confidence": 0.95},
                {"value": "1200", "doc_id": "doc3", "confidence": 0.7},
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        assert len(conflicts) == 1
        assert conflicts[0].selected_value == "1500"
        assert conflicts[0].selected_confidence == 0.95

    def test_handles_normalized_values(self, service):
        """Test that normalized values are used when available."""
        candidates = {
            "incident_date": [
                {
                    "value": "Jan 15, 2026",
                    "normalized_value": "2026-01-15",
                    "doc_id": "doc1",
                    "confidence": 0.9,
                },
                {
                    "value": "15/01/2026",
                    "normalized_value": "2026-01-15",
                    "doc_id": "doc2",
                    "confidence": 0.85,
                },
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        # Same normalized value = no conflict
        assert len(conflicts) == 0

    def test_handles_none_values(self, service):
        """Test that None values are skipped."""
        candidates = {
            "optional_field": [
                {"value": None, "doc_id": "doc1", "confidence": 0.5},
                {"value": "actual_value", "doc_id": "doc2", "confidence": 0.9},
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        # Only one non-None value, no conflict
        assert len(conflicts) == 0

    def test_tracks_sources_per_value(self, service):
        """Test that sources are tracked per distinct value."""
        candidates = {
            "policy_holder": [
                {"value": "John Doe", "doc_id": "doc1", "confidence": 0.9},
                {"value": "John Doe", "doc_id": "doc2", "confidence": 0.85},
                {"value": "Jane Doe", "doc_id": "doc3", "confidence": 0.7},
            ],
        }

        conflicts = service.detect_conflicts(candidates)

        assert len(conflicts) == 1
        conflict = conflicts[0]
        # Should have 2 distinct values
        assert len(conflict.values) == 2
        # Sources should be grouped by value
        assert len(conflict.sources) == 2


class TestEvaluateGate:
    """Tests for ReconciliationService.evaluate_gate()."""

    @pytest.fixture
    def service(self):
        """Create a ReconciliationService with mocked dependencies."""
        storage = MagicMock()
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    @pytest.fixture
    def default_thresholds(self):
        """Return default gate thresholds."""
        return GateThresholds()

    def _make_claim_facts(self, fact_names: list) -> ClaimFacts:
        """Helper to create ClaimFacts with given fact names."""
        facts = []
        for name in fact_names:
            facts.append(
                AggregatedFact(
                    name=name,
                    value="test_value",
                    confidence=0.9,
                    selected_from=FactProvenance(
                        doc_id="doc1",
                        doc_type="test",
                        run_id="run_001",
                    ),
                )
            )
        return ClaimFacts(
            claim_id="test_claim",
            run_id="run_001",
            facts=facts,
            sources=[],
        )

    def test_pass_all_present_no_conflicts(self, service, default_thresholds):
        """Test PASS when all critical facts present and no conflicts."""
        claim_facts = self._make_claim_facts(["policy_number", "claim_date", "amount"])
        conflicts = []
        critical_facts = ["policy_number", "claim_date", "amount"]

        gate = service.evaluate_gate(
            claim_facts, conflicts, critical_facts, default_thresholds
        )

        assert gate.status == GateStatus.PASS
        assert gate.missing_critical_facts == []
        assert gate.conflict_count == 0

    def test_warn_missing_critical_within_threshold(self, service, default_thresholds):
        """Test WARN when missing critical facts within threshold."""
        claim_facts = self._make_claim_facts(["policy_number", "amount"])
        conflicts = []
        critical_facts = ["policy_number", "claim_date", "amount"]  # claim_date missing

        gate = service.evaluate_gate(
            claim_facts, conflicts, critical_facts, default_thresholds
        )

        assert gate.status == GateStatus.WARN
        assert "claim_date" in gate.missing_critical_facts

    def test_warn_conflicts_within_threshold(self, service, default_thresholds):
        """Test WARN when conflicts within threshold."""
        claim_facts = self._make_claim_facts(["policy_number", "claim_date"])
        conflicts = [
            FactConflict(
                fact_name="vin",
                values=["A", "B"],
                sources=[["doc1"], ["doc2"]],
                selected_value="A",
                selected_confidence=0.9,
            )
        ]
        critical_facts = ["policy_number", "claim_date"]

        gate = service.evaluate_gate(
            claim_facts, conflicts, critical_facts, default_thresholds
        )

        assert gate.status == GateStatus.WARN
        assert gate.conflict_count == 1

    def test_fail_exceeds_missing_critical_threshold(self, service):
        """Test FAIL when missing critical facts exceed threshold."""
        thresholds = GateThresholds(missing_critical_fail=1)
        claim_facts = self._make_claim_facts(["policy_number"])
        conflicts = []
        critical_facts = ["policy_number", "claim_date", "amount", "vin"]  # 3 missing

        gate = service.evaluate_gate(claim_facts, conflicts, critical_facts, thresholds)

        assert gate.status == GateStatus.FAIL
        assert len(gate.missing_critical_facts) == 3

    def test_fail_exceeds_conflict_threshold(self, service):
        """Test FAIL when conflicts exceed threshold."""
        thresholds = GateThresholds(conflict_fail=1)
        claim_facts = self._make_claim_facts(["policy_number", "claim_date"])
        conflicts = [
            FactConflict(
                fact_name="vin",
                values=["A", "B"],
                sources=[["doc1"], ["doc2"]],
                selected_value="A",
                selected_confidence=0.9,
            ),
            FactConflict(
                fact_name="amount",
                values=["100", "200"],
                sources=[["doc1"], ["doc2"]],
                selected_value="200",
                selected_confidence=0.95,
            ),
            FactConflict(
                fact_name="date",
                values=["2026-01-01", "2026-01-02"],
                sources=[["doc1"], ["doc2"]],
                selected_value="2026-01-01",
                selected_confidence=0.8,
            ),
        ]
        critical_facts = ["policy_number", "claim_date"]

        gate = service.evaluate_gate(claim_facts, conflicts, critical_facts, thresholds)

        assert gate.status == GateStatus.FAIL
        assert gate.conflict_count == 3

    def test_fail_token_estimate_exceeds_threshold(self, service):
        """Test FAIL when token estimate exceeds fail threshold."""
        thresholds = GateThresholds(token_fail=10)  # Very low threshold
        # Create facts with long values to exceed token threshold
        facts = []
        for i in range(100):
            facts.append(
                AggregatedFact(
                    name=f"fact_{i}",
                    value="x" * 100,  # Long value
                    confidence=0.9,
                    selected_from=FactProvenance(
                        doc_id="doc1", doc_type="test", run_id="run_001"
                    ),
                )
            )
        claim_facts = ClaimFacts(
            claim_id="test", run_id="run_001", facts=facts, sources=[]
        )

        gate = service.evaluate_gate(claim_facts, [], [], thresholds)

        assert gate.status == GateStatus.FAIL
        assert "token" in gate.reasons[0].lower()

    def test_warn_token_estimate_exceeds_warn_threshold(self, service):
        """Test WARN when token estimate exceeds warn threshold."""
        thresholds = GateThresholds(token_warn=10, token_fail=1000000)
        facts = []
        for i in range(50):
            facts.append(
                AggregatedFact(
                    name=f"fact_{i}",
                    value="x" * 50,
                    confidence=0.9,
                    selected_from=FactProvenance(
                        doc_id="doc1", doc_type="test", run_id="run_001"
                    ),
                )
            )
        claim_facts = ClaimFacts(
            claim_id="test", run_id="run_001", facts=facts, sources=[]
        )

        gate = service.evaluate_gate(claim_facts, [], [], thresholds)

        assert gate.status == GateStatus.WARN

    def test_calculates_provenance_coverage(self, service, default_thresholds):
        """Test that provenance coverage is calculated correctly."""
        facts = [
            AggregatedFact(
                name="fact1",
                value="val1",
                confidence=0.9,
                selected_from=FactProvenance(
                    doc_id="doc1",
                    doc_type="test",
                    run_id="run_001",
                    text_quote="quote here",  # Has provenance
                ),
            ),
            AggregatedFact(
                name="fact2",
                value="val2",
                confidence=0.8,
                selected_from=FactProvenance(
                    doc_id="doc1",
                    doc_type="test",
                    run_id="run_001",
                    text_quote=None,  # No provenance
                ),
            ),
        ]
        claim_facts = ClaimFacts(
            claim_id="test", run_id="run_001", facts=facts, sources=[]
        )

        gate = service.evaluate_gate(claim_facts, [], [], default_thresholds)

        # 1 out of 2 facts have provenance = 0.5
        assert gate.provenance_coverage == 0.5


class TestLoadGateThresholds:
    """Tests for ReconciliationService.load_gate_thresholds()."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create a temporary workspace directory."""
        return tmp_path

    @pytest.fixture
    def service(self, temp_workspace):
        """Create a ReconciliationService with real storage."""
        storage = MagicMock()
        storage.output_root = temp_workspace
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    def test_returns_defaults_when_no_config(self, service):
        """Test that defaults are returned when no config file exists."""
        thresholds = service.load_gate_thresholds()

        assert thresholds.missing_critical_warn == 2
        assert thresholds.missing_critical_fail == 2
        assert thresholds.conflict_warn == 2
        assert thresholds.conflict_fail == 2
        assert thresholds.token_warn == 40000
        assert thresholds.token_fail == 60000

    def test_loads_from_config_file(self, service, temp_workspace):
        """Test loading thresholds from config file."""
        config_dir = temp_workspace / "config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "reconciliation_gate.yaml"
        config_path.write_text(
            """
thresholds:
  missing_critical_warn: 1
  missing_critical_fail: 3
  conflict_warn: 1
  conflict_fail: 5
  token_warn: 30000
  token_fail: 50000
"""
        )

        thresholds = service.load_gate_thresholds()

        assert thresholds.missing_critical_warn == 1
        assert thresholds.missing_critical_fail == 3
        assert thresholds.conflict_warn == 1
        assert thresholds.conflict_fail == 5
        assert thresholds.token_warn == 30000
        assert thresholds.token_fail == 50000

    def test_handles_partial_config(self, service, temp_workspace):
        """Test that partial config uses defaults for missing values."""
        config_dir = temp_workspace / "config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "reconciliation_gate.yaml"
        config_path.write_text(
            """
thresholds:
  missing_critical_warn: 5
"""
        )

        thresholds = service.load_gate_thresholds()

        assert thresholds.missing_critical_warn == 5
        # Others should be defaults
        assert thresholds.missing_critical_fail == 2

    def test_handles_invalid_yaml(self, service, temp_workspace):
        """Test that invalid YAML returns defaults."""
        config_dir = temp_workspace / "config"
        config_dir.mkdir(parents=True)
        config_path = config_dir / "reconciliation_gate.yaml"
        config_path.write_text("not: valid: yaml: content:")

        thresholds = service.load_gate_thresholds()

        # Should return defaults
        assert thresholds.missing_critical_warn == 2


class TestLoadCriticalFactsSpec:
    """Tests for ReconciliationService.load_critical_facts_spec()."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create a temporary workspace directory."""
        return tmp_path

    @pytest.fixture
    def service(self, temp_workspace):
        """Create a ReconciliationService with real storage."""
        storage = MagicMock()
        storage.output_root = temp_workspace
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    def test_returns_empty_when_no_specs_dir(self, service):
        """Test that empty dict is returned when specs directory doesn't exist."""
        result = service.load_critical_facts_spec()

        assert result == {}

    def test_loads_single_spec(self, service, temp_workspace):
        """Test loading a single extraction spec."""
        specs_dir = temp_workspace / "config" / "extraction_specs"
        specs_dir.mkdir(parents=True)
        spec_path = specs_dir / "fnol_form.yaml"
        spec_path.write_text(
            """
doc_type: fnol_form
required_fields:
  - policy_number
  - incident_date
  - claimant_name
"""
        )

        result = service.load_critical_facts_spec()

        assert "fnol_form" in result
        assert set(result["fnol_form"]) == {"policy_number", "incident_date", "claimant_name"}

    def test_loads_multiple_specs(self, service, temp_workspace):
        """Test loading multiple extraction specs."""
        specs_dir = temp_workspace / "config" / "extraction_specs"
        specs_dir.mkdir(parents=True)

        (specs_dir / "fnol_form.yaml").write_text(
            """
doc_type: fnol_form
required_fields:
  - policy_number
"""
        )
        (specs_dir / "police_report.yaml").write_text(
            """
doc_type: police_report
required_fields:
  - incident_date
  - officer_name
"""
        )

        result = service.load_critical_facts_spec()

        assert len(result) == 2
        assert "fnol_form" in result
        assert "police_report" in result

    def test_skips_specs_without_required_fields(self, service, temp_workspace):
        """Test that specs without required_fields are skipped."""
        specs_dir = temp_workspace / "config" / "extraction_specs"
        specs_dir.mkdir(parents=True)
        spec_path = specs_dir / "optional_doc.yaml"
        spec_path.write_text(
            """
doc_type: optional_doc
# No required_fields
"""
        )

        result = service.load_critical_facts_spec()

        assert "optional_doc" not in result


class TestBuildCriticalFactsSet:
    """Tests for ReconciliationService._build_critical_facts_set()."""

    @pytest.fixture
    def service(self):
        """Create a ReconciliationService with mocked dependencies."""
        storage = MagicMock()
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    def test_builds_union_of_critical_facts(self, service):
        """Test that union of critical facts is built correctly."""
        critical_by_doctype = {
            "fnol_form": ["policy_number", "incident_date"],
            "police_report": ["incident_date", "officer_name"],
        }
        doc_types_present = {"fnol_form", "police_report"}

        result = service._build_critical_facts_set(critical_by_doctype, doc_types_present)

        assert result == {"policy_number", "incident_date", "officer_name"}

    def test_filters_by_present_doc_types(self, service):
        """Test that only present doc types are included."""
        critical_by_doctype = {
            "fnol_form": ["policy_number"],
            "police_report": ["officer_name"],
            "invoice": ["amount"],
        }
        doc_types_present = {"fnol_form"}  # Only fnol_form present

        result = service._build_critical_facts_set(critical_by_doctype, doc_types_present)

        assert result == {"policy_number"}

    def test_handles_empty_doc_types(self, service):
        """Test handling of empty doc types present."""
        critical_by_doctype = {
            "fnol_form": ["policy_number"],
        }
        doc_types_present = set()

        result = service._build_critical_facts_set(critical_by_doctype, doc_types_present)

        assert result == set()


class TestAggregateRunEvaluation:
    """Tests for ReconciliationService.aggregate_run_evaluation()."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create a temporary workspace directory."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def service(self, temp_workspace):
        """Create a ReconciliationService with real storage."""
        storage = MagicMock()
        storage.claims_dir = temp_workspace / "claims"
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    def _create_reconciliation_report(
        self,
        claims_dir: Path,
        claim_id: str,
        gate_status: str = "pass",
        fact_count: int = 10,
        conflict_count: int = 0,
        missing_critical: list = None,
        conflicts: list = None,
    ):
        """Helper to create a reconciliation report file."""
        claim_dir = claims_dir / claim_id / "context"
        claim_dir.mkdir(parents=True)

        report = {
            "claim_id": claim_id,
            "run_id": "run_001",
            "gate": {
                "status": gate_status,
                "missing_critical_facts": missing_critical or [],
                "conflict_count": conflict_count,
                "provenance_coverage": 0.8,
                "reasons": [],
            },
            "fact_count": fact_count,
            "conflicts": conflicts or [],
        }

        report_path = claim_dir / "reconciliation_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f)

    def test_empty_when_no_reports(self, service, temp_workspace):
        """Test that empty evaluation is returned when no reports exist."""
        evaluation = service.aggregate_run_evaluation()

        assert evaluation.summary.total_claims == 0
        assert evaluation.results == []

    def test_aggregates_single_claim(self, service, temp_workspace):
        """Test aggregation of a single claim."""
        self._create_reconciliation_report(
            temp_workspace / "claims",
            "CLM-001",
            gate_status="pass",
            fact_count=15,
        )

        evaluation = service.aggregate_run_evaluation()

        assert evaluation.summary.total_claims == 1
        assert evaluation.summary.passed == 1
        assert evaluation.summary.pass_rate == 1.0
        assert len(evaluation.results) == 1
        assert evaluation.results[0].claim_id == "CLM-001"

    def test_aggregates_multiple_claims(self, service, temp_workspace):
        """Test aggregation of multiple claims with different statuses."""
        claims_dir = temp_workspace / "claims"
        self._create_reconciliation_report(claims_dir, "CLM-001", gate_status="pass")
        self._create_reconciliation_report(claims_dir, "CLM-002", gate_status="warn")
        self._create_reconciliation_report(claims_dir, "CLM-003", gate_status="fail")

        evaluation = service.aggregate_run_evaluation()

        assert evaluation.summary.total_claims == 3
        assert evaluation.summary.passed == 1
        assert evaluation.summary.warned == 1
        assert evaluation.summary.failed == 1
        assert abs(evaluation.summary.pass_rate - 1/3) < 0.01

    def test_tracks_top_missing_facts(self, service, temp_workspace):
        """Test that top missing facts are tracked."""
        claims_dir = temp_workspace / "claims"
        self._create_reconciliation_report(
            claims_dir, "CLM-001", missing_critical=["policy_number", "vin"]
        )
        self._create_reconciliation_report(
            claims_dir, "CLM-002", missing_critical=["policy_number"]
        )
        self._create_reconciliation_report(
            claims_dir, "CLM-003", missing_critical=["policy_number", "vin", "amount"]
        )

        evaluation = service.aggregate_run_evaluation()

        # policy_number missing in 3 claims, vin in 2, amount in 1
        assert len(evaluation.top_missing_facts) > 0
        top_fact = evaluation.top_missing_facts[0]
        assert top_fact.fact_name == "policy_number"
        assert top_fact.count == 3

    def test_tracks_top_conflicts(self, service, temp_workspace):
        """Test that top conflicting facts are tracked."""
        claims_dir = temp_workspace / "claims"
        self._create_reconciliation_report(
            claims_dir,
            "CLM-001",
            conflicts=[{"fact_name": "vin"}, {"fact_name": "amount"}],
        )
        self._create_reconciliation_report(
            claims_dir,
            "CLM-002",
            conflicts=[{"fact_name": "vin"}],
        )

        evaluation = service.aggregate_run_evaluation()

        # vin conflicts in 2 claims, amount in 1
        assert len(evaluation.top_conflicts) > 0
        top_conflict = evaluation.top_conflicts[0]
        assert top_conflict.fact_name == "vin"
        assert top_conflict.count == 2

    def test_respects_top_n_limit(self, service, temp_workspace):
        """Test that top_n parameter limits results."""
        claims_dir = temp_workspace / "claims"
        # Create many different missing facts
        for i in range(5):
            self._create_reconciliation_report(
                claims_dir,
                f"CLM-{i:03d}",
                missing_critical=[f"fact_{j}" for j in range(10)],
            )

        evaluation = service.aggregate_run_evaluation(top_n=3)

        assert len(evaluation.top_missing_facts) <= 3

    def test_calculates_averages(self, service, temp_workspace):
        """Test that averages are calculated correctly."""
        claims_dir = temp_workspace / "claims"
        self._create_reconciliation_report(
            claims_dir, "CLM-001", fact_count=10, conflict_count=2
        )
        self._create_reconciliation_report(
            claims_dir, "CLM-002", fact_count=20, conflict_count=4
        )

        evaluation = service.aggregate_run_evaluation()

        assert evaluation.summary.avg_fact_count == 15.0  # (10 + 20) / 2
        assert evaluation.summary.avg_conflicts == 3.0  # (2 + 4) / 2
        assert evaluation.summary.total_conflicts == 6


class TestWriteReconciliationReport:
    """Tests for ReconciliationService.write_reconciliation_report()."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create a temporary workspace directory."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def service(self, temp_workspace):
        """Create a ReconciliationService with mocked storage."""
        storage = MagicMock()
        storage.output_root = temp_workspace
        storage._find_claim_folder = MagicMock(
            return_value=temp_workspace / "claims" / "CLM-001"
        )
        aggregation = MagicMock()
        return ReconciliationService(storage, aggregation)

    def test_writes_report_to_context_dir(self, service, temp_workspace):
        """Test that report is written to claim context directory."""
        claim_dir = temp_workspace / "claims" / "CLM-001"
        claim_dir.mkdir(parents=True)

        report = ReconciliationReport(
            claim_id="CLM-001",
            run_id="run_001",
            gate=ReconciliationGate(status=GateStatus.PASS),
            fact_count=10,
        )

        output_path = service.write_reconciliation_report("CLM-001", report)

        assert output_path.exists()
        assert output_path.name == "reconciliation_report.json"

        # Verify content
        with open(output_path) as f:
            data = json.load(f)
        assert data["claim_id"] == "CLM-001"
        assert data["gate"]["status"] == "pass"

    def test_raises_error_when_claim_not_found(self, service):
        """Test that error is raised when claim folder not found."""
        service.storage._find_claim_folder.return_value = None

        report = ReconciliationReport(
            claim_id="NONEXISTENT",
            run_id="run_001",
            gate=ReconciliationGate(status=GateStatus.PASS),
        )

        with pytest.raises(ReconciliationError, match="Claim not found"):
            service.write_reconciliation_report("NONEXISTENT", report)
