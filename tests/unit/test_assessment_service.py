"""Unit tests for the AssessmentService."""

import json
import pytest
from pathlib import Path

from context_builder.api.services.assessment import AssessmentService


class TestAssessmentService:
    """Tests for AssessmentService."""

    @pytest.fixture
    def temp_claims_dir(self, tmp_path):
        """Create a temporary claims directory."""
        return tmp_path

    @pytest.fixture
    def service(self, temp_claims_dir):
        """Create an AssessmentService instance."""
        return AssessmentService(temp_claims_dir)

    @pytest.fixture
    def sample_assessment(self):
        """Return a sample assessment in file format."""
        return {
            "schema_version": "claims_assessment_v1",
            "claim_id": "12345",
            "assessment_timestamp": "2026-01-24T22:14:20.485908",
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "checks": [
                {
                    "check_number": 1,
                    "check_name": "policy_validity",
                    "result": "PASS",
                    "details": "Policy is valid.",
                    "evidence_refs": ["start_date", "end_date"],
                },
                {
                    "check_number": "1b",
                    "check_name": "damage_date_validity",
                    "result": "PASS",
                    "details": "No pre-existing damage.",
                    "evidence_refs": ["diagnostic_report"],
                },
                {
                    "check_number": 2,
                    "check_name": "vehicle_id_consistency",
                    "result": "FAIL",
                    "details": "VINs do not match.",
                    "evidence_refs": ["vin"],
                },
            ],
            "payout": {
                "total_claimed": 5000.0,
                "final_payout": 4500.0,
                "currency": "CHF",
            },
            "assumptions": [
                {
                    "check_number": 1,
                    "field": "policy_start_date",
                    "assumed_value": "2025-01-01",
                    "reason": "Missing from documents",
                    "confidence_impact": "HIGH",
                }
            ],
            "fraud_indicators": [
                {
                    "indicator": "Duplicate claim",
                    "severity": "high",
                    "details": "Similar claim filed last month.",
                }
            ],
            "recommendations": ["Verify VIN manually.", "Contact policyholder."],
        }

    def create_assessment_file(self, claims_dir: Path, claim_id: str, data: dict):
        """Helper to create an assessment file."""
        context_dir = claims_dir / claim_id / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        assessment_path = context_dir / "assessment.json"
        with open(assessment_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_get_assessment_file_not_found(self, service):
        """Test that missing assessment returns None."""
        result = service.get_assessment("nonexistent_claim")
        assert result is None

    def test_get_assessment_transforms_correctly(
        self, service, temp_claims_dir, sample_assessment
    ):
        """Test that assessment is transformed correctly."""
        self.create_assessment_file(temp_claims_dir, "12345", sample_assessment)

        result = service.get_assessment("12345")

        assert result is not None
        assert result["claim_id"] == "12345"
        assert result["recommendation"] == "APPROVE"
        # confidence_score is converted from decimal (0.95) to percentage (95)
        assert result["confidence_score"] == 95.0

        # Check timestamp transformation
        assert result["assessed_at"] == "2026-01-24T22:14:20.485908"
        assert "assessment_timestamp" not in result

        # Check payout transformation (nested -> flat)
        assert result["payout"] == 4500.0

        # Check recommendations
        assert result["recommendations"] == ["Verify VIN manually.", "Contact policyholder."]

    def test_check_number_transformation(
        self, service, temp_claims_dir, sample_assessment
    ):
        """Test that check_number is properly parsed."""
        self.create_assessment_file(temp_claims_dir, "12345", sample_assessment)

        result = service.get_assessment("12345")
        checks = result["checks"]

        # Integer check_number should stay as-is
        assert checks[0]["check_number"] == 1

        # String check_number "1b" should become 1
        assert checks[1]["check_number"] == 1

        # Integer check_number 2
        assert checks[2]["check_number"] == 2

    def test_assumption_impact_transformation(
        self, service, temp_claims_dir, sample_assessment
    ):
        """Test that confidence_impact is transformed to lowercase impact."""
        self.create_assessment_file(temp_claims_dir, "12345", sample_assessment)

        result = service.get_assessment("12345")
        assumptions = result["assumptions"]

        assert len(assumptions) == 1
        # confidence_impact: "HIGH" -> impact: "high"
        assert assumptions[0]["impact"] == "high"
        assert "confidence_impact" not in assumptions[0]

    def test_fraud_indicators_transformation(
        self, service, temp_claims_dir, sample_assessment
    ):
        """Test that fraud indicators are transformed correctly."""
        self.create_assessment_file(temp_claims_dir, "12345", sample_assessment)

        result = service.get_assessment("12345")
        indicators = result["fraud_indicators"]

        assert len(indicators) == 1
        assert indicators[0]["indicator"] == "Duplicate claim"
        assert indicators[0]["severity"] == "high"
        assert indicators[0]["details"] == "Similar claim filed last month."

    def test_get_assessment_handles_json_error(
        self, service, temp_claims_dir
    ):
        """Test that invalid JSON returns None."""
        context_dir = temp_claims_dir / "badclaim" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        assessment_path = context_dir / "assessment.json"
        assessment_path.write_text("not valid json")

        result = service.get_assessment("badclaim")
        assert result is None

    def test_get_assessment_history_returns_list(
        self, service, temp_claims_dir, sample_assessment
    ):
        """Test that assessment history returns a list."""
        self.create_assessment_file(temp_claims_dir, "12345", sample_assessment)

        result = service.get_assessment_history("12345")

        assert isinstance(result, list)
        assert len(result) == 1

    def test_get_assessment_history_entry_structure(
        self, service, temp_claims_dir, sample_assessment
    ):
        """Test that history entry has correct structure."""
        self.create_assessment_file(temp_claims_dir, "12345", sample_assessment)

        result = service.get_assessment_history("12345")
        entry = result[0]

        assert entry["timestamp"] == "2026-01-24T22:14:20.485908"
        assert entry["recommendation"] == "APPROVE"
        # confidence_score is converted from decimal (0.95) to percentage (95)
        assert entry["confidence_score"] == 95.0
        assert entry["payout"] == 4500.0
        # 2 PASS checks out of 3 total
        assert entry["pass_count"] == 2
        assert entry["check_count"] == 3
        assert entry["assumption_count"] == 1

    def test_get_assessment_history_empty_for_missing_claim(self, service):
        """Test that missing claim returns empty history."""
        result = service.get_assessment_history("nonexistent")
        assert result == []

    def test_get_assessment_with_direct_payout_value(
        self, service, temp_claims_dir
    ):
        """Test assessment with payout as a direct number."""
        assessment = {
            "claim_id": "67890",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.8,
            "payout": 0,  # Direct number, not nested
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "67890", assessment)

        result = service.get_assessment("67890")

        assert result["payout"] == 0
        assert result["recommendation"] == "REJECT"
        # confidence_score 0.8 -> 80%
        assert result["confidence_score"] == 80.0

    def test_confidence_score_percentage_conversion(
        self, service, temp_claims_dir
    ):
        """Test that confidence_score is converted from decimal to percentage."""
        assessment = {
            "claim_id": "test123",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 1.0,  # 100%
            "payout": 1000,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "test123", assessment)

        result = service.get_assessment("test123")

        # 1.0 -> 100%
        assert result["confidence_score"] == 100.0

    def test_confidence_score_already_percentage_not_converted(
        self, service, temp_claims_dir
    ):
        """Test that confidence_score > 1.0 is not converted (already a percentage)."""
        assessment = {
            "claim_id": "test456",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 85.5,  # Already a percentage
            "payout": 1000,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "test456", assessment)

        result = service.get_assessment("test456")

        # Should remain as-is since it's > 1.0
        assert result["confidence_score"] == 85.5

    def test_invalid_check_result_mapped_to_inconclusive(
        self, service, temp_claims_dir
    ):
        """Test that invalid check results like N/A are mapped to INCONCLUSIVE."""
        assessment = {
            "claim_id": "test789",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.9,
            "payout": 0,
            "checks": [
                {"check_number": 1, "check_name": "test", "result": "N/A", "details": "Not applicable", "evidence_refs": []},
                {"check_number": 2, "check_name": "test2", "result": "UNKNOWN", "details": "Unknown", "evidence_refs": []},
                {"check_number": 3, "check_name": "test3", "result": "PASS", "details": "OK", "evidence_refs": []},
            ],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "test789", assessment)

        result = service.get_assessment("test789")
        checks = result["checks"]

        # N/A and UNKNOWN should be mapped to INCONCLUSIVE
        assert checks[0]["result"] == "INCONCLUSIVE"
        assert checks[1]["result"] == "INCONCLUSIVE"
        # PASS should remain as-is
        assert checks[2]["result"] == "PASS"

    def test_parse_check_number_edge_cases(self, service):
        """Test edge cases for check number parsing."""
        # Integer
        assert service._parse_check_number(5) == 5

        # Simple string
        assert service._parse_check_number("3") == 3

        # String with letter suffix
        assert service._parse_check_number("2a") == 2
        assert service._parse_check_number("1b") == 1

        # Multi-digit
        assert service._parse_check_number("10c") == 10

        # No digits
        assert service._parse_check_number("abc") == 0

        # Empty string
        assert service._parse_check_number("") == 0

        # None-like
        assert service._parse_check_number(None) == 0

    def test_payout_breakdown_full(self, service, temp_claims_dir):
        """Test that full payout breakdown is preserved."""
        assessment = {
            "claim_id": "breakdown1",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "recommendation_rationale": "All checks passed and policy is valid",
            "payout": {
                "total_claimed": 7315.95,
                "non_covered_deductions": 0,
                "covered_subtotal": 5642.52,
                "coverage_percent": 40,
                "after_coverage": 5000.0,
                "deductible": 500.0,
                "final_payout": 4500.0,
                "currency": "CHF",
            },
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "breakdown1", assessment)

        result = service.get_assessment("breakdown1")

        # Check payout_breakdown is present with all fields
        breakdown = result.get("payout_breakdown")
        assert breakdown is not None
        assert breakdown["total_claimed"] == 7315.95
        assert breakdown["non_covered_deductions"] == 0
        assert breakdown["covered_subtotal"] == 5642.52
        assert breakdown["coverage_percent"] == 40
        assert breakdown["after_coverage"] == 5000.0
        assert breakdown["deductible"] == 500.0
        assert breakdown["final_payout"] == 4500.0
        assert breakdown["currency"] == "CHF"

    def test_payout_breakdown_with_direct_number(self, service, temp_claims_dir):
        """Test payout breakdown when payout is a direct number."""
        assessment = {
            "claim_id": "direct_payout",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.9,
            "payout": 0,  # Direct number
            "currency": "EUR",
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "direct_payout", assessment)

        result = service.get_assessment("direct_payout")

        breakdown = result.get("payout_breakdown")
        assert breakdown is not None
        assert breakdown["final_payout"] == 0
        assert breakdown["currency"] == "EUR"
        # Other fields should be None
        assert breakdown.get("total_claimed") is None

    def test_recommendation_rationale_preserved(self, service, temp_claims_dir):
        """Test that recommendation_rationale is preserved."""
        assessment = {
            "claim_id": "rationale1",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.85,
            "recommendation_rationale": "Policy expired before incident date",
            "payout": 0,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "rationale1", assessment)

        result = service.get_assessment("rationale1")

        assert result["recommendation_rationale"] == "Policy expired before incident date"

    def test_recommendation_rationale_null_when_missing(self, service, temp_claims_dir):
        """Test that missing recommendation_rationale returns None."""
        assessment = {
            "claim_id": "no_rationale",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "payout": 1000,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "no_rationale", assessment)

        result = service.get_assessment("no_rationale")

        assert result.get("recommendation_rationale") is None

    def test_payout_breakdown_currency_fallback(self, service, temp_claims_dir):
        """Test currency fallback from top-level when not in payout structure."""
        assessment = {
            "claim_id": "currency_fallback",
            "assessment_timestamp": "2026-01-25T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "currency": "USD",  # Top-level currency
            "payout": {
                "total_claimed": 1000,
                "final_payout": 800,
                # No currency in payout
            },
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        self.create_assessment_file(temp_claims_dir, "currency_fallback", assessment)

        result = service.get_assessment("currency_fallback")

        breakdown = result.get("payout_breakdown")
        assert breakdown["currency"] == "USD"  # Falls back to top-level


class TestAssessmentServiceVersioning:
    """Tests for AssessmentService versioning and history features."""

    @pytest.fixture
    def temp_claims_dir(self, tmp_path):
        """Create a temporary claims directory."""
        return tmp_path

    @pytest.fixture
    def service(self, temp_claims_dir):
        """Create an AssessmentService instance."""
        return AssessmentService(temp_claims_dir)

    def test_save_assessment_creates_versioned_file(self, service, temp_claims_dir):
        """Test that save_assessment creates a timestamped file."""
        assessment_data = {
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        result = service.save_assessment(
            claim_id="CLM-001",
            assessment_data=assessment_data,
            prompt_version="v1.0",
        )

        # Check result metadata
        assert "id" in result
        assert "filename" in result
        assert result["prompt_version"] == "v1.0"
        assert result["is_current"] is True

        # Check file was created
        assessments_dir = temp_claims_dir / "CLM-001" / "context" / "assessments"
        assert assessments_dir.exists()
        files = list(assessments_dir.glob("*.json"))
        # Should have index.json and the versioned file
        assert len(files) >= 1

    def test_save_assessment_updates_index(self, service, temp_claims_dir):
        """Test that save_assessment updates the index file."""
        assessment_data = {
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        service.save_assessment(
            claim_id="CLM-002",
            assessment_data=assessment_data,
            prompt_version="v1.0",
        )

        # Check index was created
        index_path = temp_claims_dir / "CLM-002" / "context" / "assessments" / "index.json"
        assert index_path.exists()

        with open(index_path) as f:
            index = json.load(f)

        assert "assessments" in index
        assert len(index["assessments"]) == 1
        assert index["assessments"][0]["is_current"] is True

    def test_save_assessment_marks_previous_not_current(self, service, temp_claims_dir):
        """Test that saving a new assessment marks previous as not current."""
        assessment_v1 = {
            "recommendation": "APPROVE",
            "confidence_score": 0.8,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        assessment_v2 = {
            "recommendation": "REJECT",
            "confidence_score": 0.9,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        service.save_assessment("CLM-003", assessment_v1, prompt_version="v1.0")
        service.save_assessment("CLM-003", assessment_v2, prompt_version="v2.0")

        index_path = temp_claims_dir / "CLM-003" / "context" / "assessments" / "index.json"
        with open(index_path) as f:
            index = json.load(f)

        assert len(index["assessments"]) == 2
        # First should no longer be current
        assert index["assessments"][0]["is_current"] is False
        # Second should be current
        assert index["assessments"][1]["is_current"] is True

    def test_save_assessment_copies_to_main_file(self, service, temp_claims_dir):
        """Test that save_assessment also updates the main assessment.json."""
        assessment_data = {
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        service.save_assessment("CLM-004", assessment_data, prompt_version="v1.0")

        main_path = temp_claims_dir / "CLM-004" / "context" / "assessment.json"
        assert main_path.exists()

        with open(main_path) as f:
            data = json.load(f)

        assert data["recommendation"] == "APPROVE"
        assert data["prompt_version"] == "v1.0"

    def test_get_assessment_by_id_found(self, service, temp_claims_dir):
        """Test retrieving a specific assessment by ID."""
        assessment_data = {
            "recommendation": "APPROVE",
            "confidence_score": 0.85,
            "checks": [{"check_number": 1, "check_name": "test", "result": "PASS", "details": "", "evidence_refs": []}],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        result = service.save_assessment("CLM-005", assessment_data, prompt_version="v1.0")
        assessment_id = result["id"]

        loaded = service.get_assessment_by_id("CLM-005", assessment_id)

        assert loaded is not None
        assert loaded["recommendation"] == "APPROVE"
        # Should be transformed (confidence as percentage)
        assert loaded["confidence_score"] == 85.0

    def test_get_assessment_by_id_not_found(self, service, temp_claims_dir):
        """Test that non-existent assessment ID returns None."""
        result = service.get_assessment_by_id("CLM-006", "nonexistent_id")
        assert result is None

    def test_get_assessment_history_with_versioned_entries(self, service, temp_claims_dir):
        """Test get_assessment_history returns versioned entries."""
        assessment_v1 = {
            "recommendation": "REFER_TO_HUMAN",
            "confidence_score": 0.6,
            "checks": [{"check_number": 1, "check_name": "test", "result": "INCONCLUSIVE", "details": "", "evidence_refs": []}],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }
        assessment_v2 = {
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "checks": [{"check_number": 1, "check_name": "test", "result": "PASS", "details": "", "evidence_refs": []}],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
        }

        service.save_assessment("CLM-007", assessment_v1, prompt_version="v1.0")
        service.save_assessment("CLM-007", assessment_v2, prompt_version="v2.0")

        history = service.get_assessment_history("CLM-007")

        assert len(history) == 2
        # Newest first
        assert history[0]["recommendation"] == "APPROVE"
        assert history[0]["is_current"] is True
        assert history[1]["recommendation"] == "REFER_TO_HUMAN"
        assert history[1]["is_current"] is False


class TestAssessmentServiceClaimRuns:
    """Tests for AssessmentService reading from claim_runs directory.

    These tests verify that assessments are correctly read from
    claim_runs/{run_id}/assessment.json, which is where the pipeline
    writes assessments.
    """

    @pytest.fixture
    def temp_claims_dir(self, tmp_path):
        """Create a temporary claims directory."""
        return tmp_path

    @pytest.fixture
    def service(self, temp_claims_dir):
        """Create an AssessmentService instance."""
        return AssessmentService(temp_claims_dir)

    def create_claim_run_assessment(
        self, claims_dir: Path, claim_id: str, run_id: str, data: dict
    ):
        """Helper to create an assessment in a claim_run folder."""
        run_dir = claims_dir / claim_id / "claim_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        assessment_path = run_dir / "assessment.json"
        with open(assessment_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_get_assessment_history_reads_from_claim_runs(
        self, service, temp_claims_dir
    ):
        """Test that get_assessment_history reads from claim_runs directory."""
        # Create two assessments in claim_runs
        assessment1 = {
            "claim_id": "CLM-100",
            "assessment_timestamp": "2026-01-28T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 1000,
        }
        assessment2 = {
            "claim_id": "CLM-100",
            "assessment_timestamp": "2026-01-28T11:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.85,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 0,
        }

        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-100", "run_20260128_100000", assessment1
        )
        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-100", "run_20260128_110000", assessment2
        )

        history = service.get_assessment_history("CLM-100")

        assert len(history) == 2
        # Newest first
        assert history[0]["recommendation"] == "REJECT"
        assert history[0]["run_id"] == "run_20260128_110000"
        assert history[0]["is_current"] is True
        assert history[1]["recommendation"] == "APPROVE"
        assert history[1]["run_id"] == "run_20260128_100000"
        assert history[1]["is_current"] is False

    def test_get_assessment_history_ignores_runs_without_assessment(
        self, service, temp_claims_dir
    ):
        """Test that claim_runs without assessment.json are skipped."""
        # Create one run with assessment
        assessment = {
            "claim_id": "CLM-101",
            "assessment_timestamp": "2026-01-28T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 1000,
        }
        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-101", "run_with_assessment", assessment
        )

        # Create another run without assessment (just manifest)
        run_dir = temp_claims_dir / "CLM-101" / "claim_runs" / "run_without_assessment"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "manifest.json").write_text('{"stages_completed": ["reconciliation"]}')

        history = service.get_assessment_history("CLM-101")

        assert len(history) == 1
        assert history[0]["run_id"] == "run_with_assessment"

    def test_get_assessment_by_id_reads_from_claim_runs(
        self, service, temp_claims_dir
    ):
        """Test that get_assessment_by_id reads from claim_runs directory."""
        assessment = {
            "claim_id": "CLM-102",
            "assessment_timestamp": "2026-01-28T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "checks": [
                {"check_number": 1, "check_name": "test", "result": "PASS", "details": "", "evidence_refs": []}
            ],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": {"final_payout": 1500, "currency": "CHF"},
        }
        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-102", "run_abc123", assessment
        )

        result = service.get_assessment_by_id("CLM-102", "run_abc123")

        assert result is not None
        assert result["recommendation"] == "APPROVE"
        assert result["confidence_score"] == 95.0  # Converted to percentage
        assert result["payout"] == 1500

    def test_get_assessment_by_id_not_found_in_claim_runs(
        self, service, temp_claims_dir
    ):
        """Test that non-existent run_id returns None."""
        # Create claim_runs directory but not the specific run
        runs_dir = temp_claims_dir / "CLM-103" / "claim_runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        result = service.get_assessment_by_id("CLM-103", "nonexistent_run")

        assert result is None

    def test_get_assessment_returns_latest_from_claim_runs(
        self, service, temp_claims_dir
    ):
        """Test that get_assessment returns the most recent assessment from claim_runs."""
        # Create older assessment
        assessment_old = {
            "claim_id": "CLM-104",
            "assessment_timestamp": "2026-01-28T09:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.7,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 0,
        }
        # Create newer assessment
        assessment_new = {
            "claim_id": "CLM-104",
            "assessment_timestamp": "2026-01-28T12:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 2000,
        }

        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-104", "run_old", assessment_old
        )
        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-104", "run_new", assessment_new
        )

        result = service.get_assessment("CLM-104")

        # Should return the newer one (based on timestamp)
        assert result["recommendation"] == "APPROVE"
        assert result["payout"] == 2000

    def test_get_assessment_history_fallback_to_legacy(
        self, service, temp_claims_dir
    ):
        """Test fallback to context/assessments when no claim_runs exist."""
        # Create legacy assessment in context/assessments
        assessments_dir = temp_claims_dir / "CLM-105" / "context" / "assessments"
        assessments_dir.mkdir(parents=True, exist_ok=True)

        # Create index
        index = {
            "assessments": [
                {
                    "id": "2026-01-26T10-00-00_v1.0.0",
                    "filename": "2026-01-26T10-00-00_v1.0.0.json",
                    "timestamp": "2026-01-26T10:00:00",
                    "recommendation": "APPROVE",
                    "confidence_score": 0.9,
                    "is_current": True,
                }
            ]
        }
        with open(assessments_dir / "index.json", "w") as f:
            json.dump(index, f)

        # Create the versioned file
        assessment = {
            "claim_id": "CLM-105",
            "assessment_timestamp": "2026-01-26T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 500,
        }
        with open(assessments_dir / "2026-01-26T10-00-00_v1.0.0.json", "w") as f:
            json.dump(assessment, f)

        history = service.get_assessment_history("CLM-105")

        assert len(history) == 1
        assert history[0]["recommendation"] == "APPROVE"
        assert history[0]["run_id"] == "2026-01-26T10-00-00_v1.0.0"

    def test_get_assessment_by_id_fallback_to_legacy(
        self, service, temp_claims_dir
    ):
        """Test get_assessment_by_id falls back to context/assessments."""
        # Create legacy assessment
        assessments_dir = temp_claims_dir / "CLM-106" / "context" / "assessments"
        assessments_dir.mkdir(parents=True, exist_ok=True)

        index = {
            "assessments": [
                {
                    "id": "legacy_id_123",
                    "filename": "legacy_id_123.json",
                    "timestamp": "2026-01-26T10:00:00",
                    "recommendation": "REJECT",
                    "confidence_score": 0.8,
                    "is_current": True,
                }
            ]
        }
        with open(assessments_dir / "index.json", "w") as f:
            json.dump(index, f)

        assessment = {
            "claim_id": "CLM-106",
            "assessment_timestamp": "2026-01-26T10:00:00",
            "recommendation": "REJECT",
            "confidence_score": 0.8,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 0,
        }
        with open(assessments_dir / "legacy_id_123.json", "w") as f:
            json.dump(assessment, f)

        result = service.get_assessment_by_id("CLM-106", "legacy_id_123")

        assert result is not None
        assert result["recommendation"] == "REJECT"

    def test_get_assessment_fallback_to_context_assessment_json(
        self, service, temp_claims_dir
    ):
        """Test get_assessment falls back to context/assessment.json when no claim_runs."""
        # Create legacy assessment.json
        context_dir = temp_claims_dir / "CLM-107" / "context"
        context_dir.mkdir(parents=True, exist_ok=True)

        assessment = {
            "claim_id": "CLM-107",
            "assessment_timestamp": "2026-01-26T10:00:00",
            "recommendation": "REFER_TO_HUMAN",
            "confidence_score": 0.6,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 0,
        }
        with open(context_dir / "assessment.json", "w") as f:
            json.dump(assessment, f)

        result = service.get_assessment("CLM-107")

        assert result is not None
        assert result["recommendation"] == "REFER_TO_HUMAN"

    def test_get_assessment_history_handles_invalid_json(
        self, service, temp_claims_dir
    ):
        """Test that invalid JSON in claim_runs is skipped gracefully."""
        # Create valid assessment
        assessment = {
            "claim_id": "CLM-108",
            "assessment_timestamp": "2026-01-28T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.9,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 1000,
        }
        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-108", "run_valid", assessment
        )

        # Create invalid assessment
        run_dir = temp_claims_dir / "CLM-108" / "claim_runs" / "run_invalid"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "assessment.json").write_text("not valid json {{{")

        history = service.get_assessment_history("CLM-108")

        # Should only return the valid one
        assert len(history) == 1
        assert history[0]["run_id"] == "run_valid"

    def test_get_assessment_history_correct_check_counts(
        self, service, temp_claims_dir
    ):
        """Test that check counts are computed correctly from claim_runs."""
        assessment = {
            "claim_id": "CLM-109",
            "assessment_timestamp": "2026-01-28T10:00:00",
            "recommendation": "REFER_TO_HUMAN",
            "confidence_score": 0.7,
            "checks": [
                {"check_number": 1, "check_name": "test1", "result": "PASS", "details": "", "evidence_refs": []},
                {"check_number": 2, "check_name": "test2", "result": "PASS", "details": "", "evidence_refs": []},
                {"check_number": 3, "check_name": "test3", "result": "FAIL", "details": "", "evidence_refs": []},
                {"check_number": 4, "check_name": "test4", "result": "INCONCLUSIVE", "details": "", "evidence_refs": []},
            ],
            "assumptions": [
                {"check_number": 3, "field": "test", "assumed_value": "x", "reason": "y", "impact": "high"}
            ],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 0,
        }
        self.create_claim_run_assessment(
            temp_claims_dir, "CLM-109", "run_checks", assessment
        )

        history = service.get_assessment_history("CLM-109")

        assert len(history) == 1
        entry = history[0]
        assert entry["check_count"] == 4
        assert entry["pass_count"] == 2
        assert entry["fail_count"] == 2  # 4 - 2 = 2 (FAIL + INCONCLUSIVE)
        assert entry["assumption_count"] == 1

    def test_claim_runs_takes_precedence_over_legacy(
        self, service, temp_claims_dir
    ):
        """Test that claim_runs data takes precedence over legacy context/assessments."""
        claim_id = "CLM-110"

        # Create legacy assessment in context/assessments
        assessments_dir = temp_claims_dir / claim_id / "context" / "assessments"
        assessments_dir.mkdir(parents=True, exist_ok=True)
        legacy_index = {
            "assessments": [
                {
                    "id": "legacy_old",
                    "filename": "legacy_old.json",
                    "timestamp": "2026-01-25T10:00:00",
                    "recommendation": "REJECT",
                    "confidence_score": 0.5,
                    "is_current": True,
                }
            ]
        }
        with open(assessments_dir / "index.json", "w") as f:
            json.dump(legacy_index, f)
        with open(assessments_dir / "legacy_old.json", "w") as f:
            json.dump({"recommendation": "REJECT", "confidence_score": 0.5, "checks": [], "assumptions": [], "fraud_indicators": [], "recommendations": []}, f)

        # Create newer assessment in claim_runs
        new_assessment = {
            "claim_id": claim_id,
            "assessment_timestamp": "2026-01-28T10:00:00",
            "recommendation": "APPROVE",
            "confidence_score": 0.95,
            "checks": [],
            "assumptions": [],
            "fraud_indicators": [],
            "recommendations": [],
            "payout": 5000,
        }
        self.create_claim_run_assessment(
            temp_claims_dir, claim_id, "run_new", new_assessment
        )

        # claim_runs should take precedence
        history = service.get_assessment_history(claim_id)

        assert len(history) == 1
        assert history[0]["recommendation"] == "APPROVE"
        assert history[0]["run_id"] == "run_new"


class TestAssessmentServiceEvaluation:
    """Tests for AssessmentService evaluation features."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create a temporary workspace with claims dir."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def service(self, temp_workspace):
        """Create an AssessmentService instance."""
        return AssessmentService(temp_workspace / "claims")

    def test_get_latest_evaluation_no_files(self, service, temp_workspace):
        """Test that None is returned when no evaluation files exist."""
        result = service.get_latest_evaluation()
        assert result is None

    def test_get_latest_evaluation_loads_file(self, service, temp_workspace):
        """Test loading and transforming an evaluation file."""
        eval_dir = temp_workspace / "eval"
        eval_dir.mkdir()

        eval_data = {
            "evaluated_at": "2026-01-25T12:00:00",
            "confusion_matrix": {
                "matrix": {
                    "APPROVE": {"APPROVE": 5, "REJECT": 1, "REFER_TO_HUMAN": 0},
                    "REJECT": {"APPROVE": 0, "REJECT": 3, "REFER_TO_HUMAN": 1},
                    "REFER_TO_HUMAN": {"APPROVE": 0, "REJECT": 0, "REFER_TO_HUMAN": 2},
                },
                "total_evaluated": 12,
                "decision_accuracy": 0.833,
            },
            "results": [
                {
                    "claim_id": "CLM-001",
                    "ai_decision": "APPROVE",
                    "expected_decision": "APPROVE",
                    "passed": True,
                    "confidence_score": 0.95,
                },
            ],
            "summary": {
                "total_claims": 12,
                "accuracy": 0.833,
            },
        }

        eval_path = eval_dir / "assessment_eval_20260125_120000.json"
        with open(eval_path, "w") as f:
            json.dump(eval_data, f)

        result = service.get_latest_evaluation()

        assert result is not None
        assert result["eval_id"] == "assessment_eval_20260125_120000"
        assert result["confusion_matrix"]["total_evaluated"] == 12
        # Accuracy should be converted to percentage
        assert result["summary"]["accuracy_rate"] == 83.3

    def test_get_latest_evaluation_picks_newest(self, service, temp_workspace):
        """Test that the newest evaluation file is selected."""
        eval_dir = temp_workspace / "eval"
        eval_dir.mkdir()

        for timestamp in ["20260125_100000", "20260125_120000", "20260125_110000"]:
            eval_path = eval_dir / f"assessment_eval_{timestamp}.json"
            eval_data = {
                "evaluated_at": f"2026-01-25T{timestamp[9:11]}:00:00",
                "confusion_matrix": {"matrix": {}, "total_evaluated": 0, "decision_accuracy": 0},
                "results": [],
                "summary": {"total_claims": 0, "accuracy": 0},
            }
            with open(eval_path, "w") as f:
                json.dump(eval_data, f)

        result = service.get_latest_evaluation()

        # Should pick 120000 (newest by filename sort)
        assert result["eval_id"] == "assessment_eval_20260125_120000"

    def test_compute_precision_approve(self, service):
        """Test precision calculation for APPROVE decision."""
        matrix = {
            "APPROVE": {"APPROVE": 8, "REJECT": 2, "REFER_TO_HUMAN": 0},
            "REJECT": {"APPROVE": 1, "REJECT": 5, "REFER_TO_HUMAN": 1},
            "REFER_TO_HUMAN": {"APPROVE": 1, "REJECT": 0, "REFER_TO_HUMAN": 3},
        }

        precision = service._compute_precision(matrix, "APPROVE")

        # TP = 8, FP = 1 + 1 = 2, Precision = 8 / 10 = 0.8
        assert abs(precision - 0.8) < 0.01

    def test_compute_precision_no_predictions(self, service):
        """Test precision when no predictions of that type exist."""
        matrix = {
            "APPROVE": {"APPROVE": 0, "REJECT": 5, "REFER_TO_HUMAN": 0},
            "REJECT": {"APPROVE": 0, "REJECT": 10, "REFER_TO_HUMAN": 0},
        }

        precision = service._compute_precision(matrix, "APPROVE")

        # No APPROVE predictions at all
        assert precision == 0.0

    def test_compute_refer_rate(self, service):
        """Test refer rate calculation."""
        results = [
            {"predicted": "APPROVE"},
            {"predicted": "REJECT"},
            {"predicted": "REFER_TO_HUMAN"},
            {"predicted": "REFER_TO_HUMAN"},
            {"predicted": "APPROVE"},
        ]

        rate = service._compute_refer_rate(results)

        # 2 out of 5 = 0.4
        assert abs(rate - 0.4) < 0.01

    def test_compute_refer_rate_empty(self, service):
        """Test refer rate with empty results."""
        rate = service._compute_refer_rate([])
        assert rate == 0.0

    def test_transform_evaluation_results(self, service, temp_workspace):
        """Test that evaluation results are transformed correctly."""
        eval_dir = temp_workspace / "eval"
        eval_dir.mkdir()

        eval_data = {
            "evaluated_at": "2026-01-25T12:00:00",
            "confusion_matrix": {"matrix": {}, "total_evaluated": 2, "decision_accuracy": 0.5},
            "results": [
                {
                    "claim_id": "CLM-001",
                    "ai_decision": "APPROVE",
                    "expected_decision": "APPROVE",
                    "passed": True,
                    "confidence_score": 0.9,
                },
                {
                    "claim_id": "CLM-002",
                    "ai_decision": "REJECT",
                    "expected_decision": "APPROVE",
                    "passed": False,
                    "confidence_score": 0.7,
                },
            ],
            "summary": {"total_claims": 2, "accuracy": 0.5},
        }

        eval_path = eval_dir / "assessment_eval_20260125_120000.json"
        with open(eval_path, "w") as f:
            json.dump(eval_data, f)

        result = service.get_latest_evaluation()
        results = result["results"]

        assert len(results) == 2
        # Check field mapping: ai_decision -> predicted, expected_decision -> actual
        assert results[0]["predicted"] == "APPROVE"
        assert results[0]["actual"] == "APPROVE"
        assert results[0]["is_correct"] is True
        assert results[1]["predicted"] == "REJECT"
        assert results[1]["actual"] == "APPROVE"
        assert results[1]["is_correct"] is False
