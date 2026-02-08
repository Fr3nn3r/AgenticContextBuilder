"""Tests for decision dossier Pydantic schemas."""

import pytest

from context_builder.schemas.decision_dossier import (
    AssumptionRecord,
    ClaimVerdict,
    ClauseEvaluation,
    ClauseEvaluationLevel,
    ClauseEvidence,
    DecisionDossier,
    DenialClauseDefinition,
    EvaluabilityTier,
    FinancialSummary,
    LineItemDecision,
    LineItemVerdict,
)
from context_builder.schemas.decision_services import (
    LaborRateResult,
    PartsClassification,
)


# ── Enum tests ──────────────────────────────────────────────────────


class TestClaimVerdict:
    def test_values(self):
        assert ClaimVerdict.APPROVE == "APPROVE"
        assert ClaimVerdict.DENY == "DENY"
        assert ClaimVerdict.REFER == "REFER"

    def test_all_values(self):
        assert set(ClaimVerdict) == {
            ClaimVerdict.APPROVE,
            ClaimVerdict.DENY,
            ClaimVerdict.REFER,
        }


class TestLineItemVerdict:
    def test_values(self):
        assert LineItemVerdict.COVERED == "COVERED"
        assert LineItemVerdict.DENIED == "DENIED"
        assert LineItemVerdict.PARTIAL == "PARTIAL"
        assert LineItemVerdict.REFER == "REFER"


class TestEvaluabilityTier:
    def test_values(self):
        assert EvaluabilityTier.DETERMINISTIC == 1
        assert EvaluabilityTier.INFERRABLE == 2
        assert EvaluabilityTier.NOT_AUTOMATABLE == 3

    def test_is_int(self):
        assert isinstance(EvaluabilityTier.DETERMINISTIC, int)


class TestClauseEvaluationLevel:
    def test_values(self):
        assert ClauseEvaluationLevel.CLAIM == "claim"
        assert ClauseEvaluationLevel.LINE_ITEM == "line_item"
        assert ClauseEvaluationLevel.CLAIM_WITH_ITEM_CONSEQUENCE == "claim_with_item_consequence"


# ── Model tests ─────────────────────────────────────────────────────


class TestDenialClauseDefinition:
    def test_minimal(self):
        clause = DenialClauseDefinition(
            reference="2.2.A",
            text="No coverage if part is uninsured",
            short_name="Uninsured part",
            category="coverage",
            evaluation_level=ClauseEvaluationLevel.CLAIM,
            evaluability_tier=EvaluabilityTier.DETERMINISTIC,
        )
        assert clause.reference == "2.2.A"
        assert clause.default_assumption is True
        assert clause.assumption_question is None

    def test_with_assumption(self):
        clause = DenialClauseDefinition(
            reference="2.3.A.q",
            text="Was the vehicle properly maintained?",
            short_name="Maintenance compliance",
            category="procedural",
            evaluation_level=ClauseEvaluationLevel.CLAIM,
            evaluability_tier=EvaluabilityTier.NOT_AUTOMATABLE,
            default_assumption=True,
            assumption_question="Has the vehicle been serviced according to manufacturer schedule?",
        )
        assert clause.evaluability_tier == EvaluabilityTier.NOT_AUTOMATABLE
        assert clause.assumption_question is not None

    def test_serialization(self):
        clause = DenialClauseDefinition(
            reference="2.2.A",
            text="Test",
            short_name="Test",
            category="coverage",
            evaluation_level=ClauseEvaluationLevel.CLAIM,
            evaluability_tier=EvaluabilityTier.DETERMINISTIC,
        )
        data = clause.model_dump()
        assert data["evaluation_level"] == "claim"
        assert data["evaluability_tier"] == 1
        restored = DenialClauseDefinition.model_validate(data)
        assert restored.reference == clause.reference


class TestClauseEvidence:
    def test_minimal(self):
        evidence = ClauseEvidence(fact_name="policy_start_date")
        assert evidence.fact_name == "policy_start_date"
        assert evidence.fact_value is None

    def test_full(self):
        evidence = ClauseEvidence(
            fact_name="policy_start_date",
            fact_value="2025-01-01",
            source_doc_id="DOC-001",
            screening_check_id="1",
            description="Policy start date from policy document",
        )
        assert evidence.source_doc_id == "DOC-001"


class TestClauseEvaluation:
    def test_pass_verdict(self):
        evaluation = ClauseEvaluation(
            clause_reference="2.2.A",
            clause_short_name="Uninsured part",
            category="coverage",
            evaluation_level=ClauseEvaluationLevel.CLAIM,
            evaluability_tier=EvaluabilityTier.DETERMINISTIC,
            verdict="PASS",
            reason="Component is covered by policy",
        )
        assert evaluation.verdict == "PASS"
        assert evaluation.assumption_used is None
        assert evaluation.affected_line_items == []

    def test_fail_verdict_with_evidence(self):
        evaluation = ClauseEvaluation(
            clause_reference="2.3.A.a",
            clause_short_name="Policy expired",
            category="exclusion",
            evaluation_level=ClauseEvaluationLevel.CLAIM,
            evaluability_tier=EvaluabilityTier.DETERMINISTIC,
            verdict="FAIL",
            reason="Claim date is outside policy period",
            evidence=[
                ClauseEvidence(
                    fact_name="claim_date",
                    fact_value="2026-03-01",
                    screening_check_id="1",
                ),
                ClauseEvidence(
                    fact_name="policy_end_date",
                    fact_value="2026-01-31",
                    screening_check_id="1",
                ),
            ],
        )
        assert evaluation.verdict == "FAIL"
        assert len(evaluation.evidence) == 2

    def test_with_assumption(self):
        evaluation = ClauseEvaluation(
            clause_reference="2.3.A.q",
            clause_short_name="Maintenance compliance",
            category="procedural",
            evaluation_level=ClauseEvaluationLevel.CLAIM,
            evaluability_tier=EvaluabilityTier.NOT_AUTOMATABLE,
            verdict="PASS",
            assumption_used=True,
            reason="Assumed: vehicle was properly maintained",
        )
        assert evaluation.assumption_used is True


class TestLineItemDecision:
    def test_covered(self):
        decision = LineItemDecision(
            item_id="LI-001",
            description="Timing chain replacement",
            item_type="parts",
            verdict=LineItemVerdict.COVERED,
            claimed_amount=1200.0,
            approved_amount=1200.0,
        )
        assert decision.verdict == LineItemVerdict.COVERED
        assert decision.denied_amount == 0.0

    def test_denied(self):
        decision = LineItemDecision(
            item_id="LI-002",
            description="Oil change",
            item_type="parts",
            verdict=LineItemVerdict.DENIED,
            applicable_clauses=["2.4.A.e"],
            denial_reasons=["Consumable item excluded"],
            claimed_amount=80.0,
            denied_amount=80.0,
        )
        assert decision.verdict == LineItemVerdict.DENIED
        assert len(decision.applicable_clauses) == 1

    def test_partial(self):
        decision = LineItemDecision(
            item_id="LI-003",
            description="Engine repair labor",
            item_type="labor",
            verdict=LineItemVerdict.PARTIAL,
            claimed_amount=500.0,
            approved_amount=400.0,
            denied_amount=0.0,
            adjusted_amount=100.0,
            adjustment_reason="Exceeds flat-rate hours",
        )
        assert decision.adjusted_amount == 100.0


class TestAssumptionRecord:
    def test_default_unconfirmed(self):
        record = AssumptionRecord(
            clause_reference="2.3.A.q",
            question="Has the vehicle been serviced per schedule?",
            assumed_value=True,
            tier=EvaluabilityTier.NOT_AUTOMATABLE,
        )
        assert record.adjuster_confirmed is False

    def test_confirmed(self):
        record = AssumptionRecord(
            clause_reference="2.3.A.q",
            question="Has the vehicle been serviced per schedule?",
            assumed_value=False,
            adjuster_confirmed=True,
            tier=EvaluabilityTier.NOT_AUTOMATABLE,
        )
        assert record.adjuster_confirmed is True
        assert record.assumed_value is False


class TestFinancialSummary:
    def test_defaults(self):
        summary = FinancialSummary()
        assert summary.total_claimed == 0.0
        assert summary.currency == "CHF"

    def test_with_values(self):
        summary = FinancialSummary(
            total_claimed=5000.0,
            total_covered=4000.0,
            total_denied=800.0,
            total_adjusted=200.0,
            net_payout=4000.0,
            parts_total=3000.0,
            labor_total=1500.0,
            fees_total=300.0,
            other_total=200.0,
        )
        assert summary.total_claimed == 5000.0
        assert summary.net_payout == 4000.0


class TestDecisionDossier:
    def test_minimal_deny(self):
        dossier = DecisionDossier(
            claim_id="CLM-001",
            claim_verdict=ClaimVerdict.DENY,
            verdict_reason="Policy expired",
            clause_evaluations=[
                ClauseEvaluation(
                    clause_reference="2.3.A.a",
                    clause_short_name="Policy expired",
                    category="exclusion",
                    evaluation_level=ClauseEvaluationLevel.CLAIM,
                    evaluability_tier=EvaluabilityTier.DETERMINISTIC,
                    verdict="FAIL",
                    reason="Claim date outside policy period",
                ),
            ],
            failed_clauses=["2.3.A.a"],
        )
        assert dossier.schema_version == "decision_dossier_v1"
        assert dossier.version == 1
        assert dossier.claim_verdict == ClaimVerdict.DENY
        assert len(dossier.clause_evaluations) == 1
        assert dossier.financial_summary is None

    def test_approve_with_line_items(self):
        dossier = DecisionDossier(
            claim_id="CLM-002",
            claim_verdict=ClaimVerdict.APPROVE,
            verdict_reason="All clauses passed",
            line_item_decisions=[
                LineItemDecision(
                    item_id="LI-001",
                    description="Timing chain",
                    item_type="parts",
                    verdict=LineItemVerdict.COVERED,
                    claimed_amount=1200.0,
                    approved_amount=1200.0,
                ),
            ],
            financial_summary=FinancialSummary(
                total_claimed=1200.0,
                total_covered=1200.0,
                net_payout=1200.0,
            ),
        )
        assert dossier.claim_verdict == ClaimVerdict.APPROVE
        assert len(dossier.line_item_decisions) == 1
        assert dossier.financial_summary.net_payout == 1200.0

    def test_refer_with_assumptions(self):
        dossier = DecisionDossier(
            claim_id="CLM-003",
            claim_verdict=ClaimVerdict.REFER,
            verdict_reason="Unconfirmed assumptions remain",
            assumptions_used=[
                AssumptionRecord(
                    clause_reference="2.3.A.q",
                    question="Maintenance compliance?",
                    assumed_value=True,
                    tier=EvaluabilityTier.NOT_AUTOMATABLE,
                ),
            ],
            unresolved_assumptions=["2.3.A.q"],
        )
        assert dossier.claim_verdict == ClaimVerdict.REFER
        assert len(dossier.assumptions_used) == 1
        assert "2.3.A.q" in dossier.unresolved_assumptions

    def test_serialization_roundtrip(self):
        dossier = DecisionDossier(
            claim_id="CLM-004",
            claim_verdict=ClaimVerdict.APPROVE,
            verdict_reason="All clear",
            engine_id="nsa_v1",
            engine_version="1.0.0",
            evaluation_timestamp="2026-02-08T10:00:00",
            input_refs={"screening_run": "run-123", "coverage_run": "run-123"},
        )
        data = dossier.model_dump(mode="json")
        restored = DecisionDossier.model_validate(data)
        assert restored.claim_id == dossier.claim_id
        assert restored.engine_id == "nsa_v1"
        assert restored.input_refs["screening_run"] == "run-123"


# ── Service schema tests ───────────────────────────────────────────


class TestLaborRateResult:
    def test_within_guideline(self):
        result = LaborRateResult(
            operation="Timing chain replacement",
            flat_rate_hours=8.0,
            max_hourly_rate=180.0,
            is_within_guideline=True,
        )
        assert result.excess_amount == 0.0

    def test_exceeds_guideline(self):
        result = LaborRateResult(
            operation="Timing chain replacement",
            flat_rate_hours=8.0,
            max_hourly_rate=180.0,
            is_within_guideline=False,
            excess_amount=360.0,
        )
        assert result.excess_amount == 360.0


class TestPartsClassification:
    def test_wear_part(self):
        result = PartsClassification(
            description="Bremsbelag vorne",
            is_wear_part=True,
        )
        assert result.is_wear_part is True
        assert result.is_body_component is False

    def test_body_component(self):
        result = PartsClassification(
            description="Kotflügel links",
            is_body_component=True,
        )
        assert result.is_body_component is True
