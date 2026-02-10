"""Tests for coverage decision trace schemas and builder."""

import pytest

from context_builder.coverage.schemas import (
    CoverageAnalysisResult,
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
    PrimaryRepairResult,
    TraceAction,
    TraceStep,
)
from context_builder.coverage.trace import TraceBuilder


class TestTraceAction:
    """Tests for TraceAction enum."""

    def test_all_values_exist(self):
        values = {a.value for a in TraceAction}
        expected = {
            "matched", "skipped", "deferred", "overridden",
            "promoted", "demoted", "excluded", "validated",
        }
        assert values == expected

    def test_is_string_enum(self):
        assert isinstance(TraceAction.MATCHED, str)
        assert TraceAction.MATCHED == "matched"


class TestTraceStep:
    """Tests for TraceStep model."""

    def test_minimal_construction(self):
        step = TraceStep(
            stage="rule_engine",
            action=TraceAction.EXCLUDED,
            reasoning="Fee item",
        )
        assert step.stage == "rule_engine"
        assert step.action == TraceAction.EXCLUDED
        assert step.reasoning == "Fee item"
        assert step.verdict is None
        assert step.confidence is None
        assert step.detail is None

    def test_full_construction(self):
        step = TraceStep(
            stage="llm",
            action=TraceAction.MATCHED,
            verdict=CoverageStatus.COVERED,
            confidence=0.82,
            reasoning="LLM determined coverage",
            detail={"model": "gpt-4o", "prompt_tokens": 847},
        )
        assert step.verdict == CoverageStatus.COVERED
        assert step.confidence == 0.82
        assert step.detail["model"] == "gpt-4o"
        assert step.detail["prompt_tokens"] == 847

    def test_serialization_roundtrip(self):
        step = TraceStep(
            stage="keyword",
            action=TraceAction.MATCHED,
            verdict=CoverageStatus.COVERED,
            confidence=0.85,
            reasoning="Keyword match",
            detail={"keyword": "ZAHNRIEMEN", "category": "engine"},
        )
        data = step.model_dump()
        restored = TraceStep(**data)
        assert restored == step

    def test_confidence_validation(self):
        with pytest.raises(Exception):
            TraceStep(
                stage="test",
                action=TraceAction.MATCHED,
                reasoning="bad",
                confidence=1.5,
            )


class TestTraceBuilder:
    """Tests for TraceBuilder helper."""

    def test_empty_build(self):
        tb = TraceBuilder()
        assert tb.build() == []

    def test_add_returns_self(self):
        tb = TraceBuilder()
        result = tb.add("rule_engine", TraceAction.EXCLUDED, "fee item")
        assert result is tb

    def test_add_single_step(self):
        tb = TraceBuilder()
        tb.add("rule_engine", TraceAction.EXCLUDED, "Fee item excluded",
               verdict=CoverageStatus.NOT_COVERED, confidence=1.0,
               detail={"rule": "fee_item"})
        steps = tb.build()
        assert len(steps) == 1
        assert steps[0].stage == "rule_engine"
        assert steps[0].action == TraceAction.EXCLUDED
        assert steps[0].detail == {"rule": "fee_item"}

    def test_add_multiple_steps(self):
        tb = TraceBuilder()
        tb.add("keyword", TraceAction.MATCHED, "matched")
        tb.add("policy_list_check", TraceAction.VALIDATED, "confirmed")
        steps = tb.build()
        assert len(steps) == 2
        assert steps[0].stage == "keyword"
        assert steps[1].stage == "policy_list_check"

    def test_extend_with_none(self):
        tb = TraceBuilder()
        tb.add("rule_engine", TraceAction.EXCLUDED, "fee")
        tb.extend(None)
        assert len(tb.build()) == 1

    def test_extend_with_steps(self):
        tb1 = TraceBuilder()
        tb1.add("keyword", TraceAction.MATCHED, "matched")
        prior_steps = tb1.build()

        tb2 = TraceBuilder()
        tb2.extend(prior_steps)
        tb2.add("policy_list_check", TraceAction.VALIDATED, "confirmed")
        steps = tb2.build()
        assert len(steps) == 2
        assert steps[0].stage == "keyword"
        assert steps[1].stage == "policy_list_check"

    def test_build_returns_copy(self):
        tb = TraceBuilder()
        tb.add("test", TraceAction.MATCHED, "test")
        steps1 = tb.build()
        steps2 = tb.build()
        assert steps1 == steps2
        assert steps1 is not steps2


class TestLineItemCoverageDecisionTrace:
    """Tests for decision_trace field on LineItemCoverage."""

    def test_default_is_none(self):
        item = LineItemCoverage(
            description="Test",
            item_type="parts",
            total_price=100.0,
            coverage_status=CoverageStatus.COVERED,
            match_method=MatchMethod.RULE,
            match_confidence=1.0,
            match_reasoning="Test",
        )
        assert item.decision_trace is None

    def test_with_trace_steps(self):
        steps = [
            TraceStep(stage="rule_engine", action=TraceAction.EXCLUDED,
                      reasoning="Fee item",
                      verdict=CoverageStatus.NOT_COVERED, confidence=1.0),
        ]
        item = LineItemCoverage(
            description="Test",
            item_type="fee",
            total_price=50.0,
            coverage_status=CoverageStatus.NOT_COVERED,
            match_method=MatchMethod.RULE,
            match_confidence=1.0,
            match_reasoning="Fee not covered",
            decision_trace=steps,
        )
        assert item.decision_trace is not None
        assert len(item.decision_trace) == 1
        assert item.decision_trace[0].stage == "rule_engine"

    def test_serialization_with_trace(self):
        steps = [
            TraceStep(stage="keyword", action=TraceAction.MATCHED,
                      reasoning="Keyword match", confidence=0.85,
                      detail={"keyword": "ZAHNRIEMEN"}),
            TraceStep(stage="policy_list_check", action=TraceAction.VALIDATED,
                      reasoning="Confirmed in policy"),
        ]
        item = LineItemCoverage(
            description="Zahnriemen",
            item_type="parts",
            total_price=200.0,
            coverage_status=CoverageStatus.COVERED,
            match_method=MatchMethod.KEYWORD,
            match_confidence=0.85,
            match_reasoning="Keyword match",
            decision_trace=steps,
        )
        data = item.model_dump()
        assert data["decision_trace"] is not None
        assert len(data["decision_trace"]) == 2
        assert data["decision_trace"][0]["stage"] == "keyword"

        # Roundtrip
        restored = LineItemCoverage(**data)
        assert restored.decision_trace is not None
        assert len(restored.decision_trace) == 2


class TestCoverageAnalysisResultSchema:
    """Tests for schema version and repair_context field."""

    def test_default_schema_version_v2(self):
        result = CoverageAnalysisResult(claim_id="CLM-001")
        assert result.schema_version == "coverage_analysis_v2"

    def test_v1_schema_version_accepted(self):
        result = CoverageAnalysisResult(
            claim_id="CLM-001",
            schema_version="coverage_analysis_v1",
        )
        assert result.schema_version == "coverage_analysis_v1"

    def test_repair_context_default_none(self):
        result = CoverageAnalysisResult(claim_id="CLM-001")
        assert result.repair_context is None

    def test_repair_context_populated(self):
        rc = PrimaryRepairResult(
            component="oil_cooler",
            category="engine",
            is_covered=True,
            description="Olkuhler defekt",
            determination_method="repair_context",
        )
        result = CoverageAnalysisResult(
            claim_id="CLM-001",
            repair_context=rc,
        )
        assert result.repair_context is not None
        assert result.repair_context.component == "oil_cooler"
        assert result.repair_context.determination_method == "repair_context"

    def test_backward_compat_no_trace(self):
        """Old JSON without decision_trace should load fine."""
        data = {
            "schema_version": "coverage_analysis_v1",
            "claim_id": "CLM-001",
            "line_items": [{
                "description": "Test",
                "item_type": "parts",
                "total_price": 100.0,
                "coverage_status": "covered",
                "match_method": "rule",
                "match_confidence": 1.0,
                "match_reasoning": "Test",
            }],
        }
        result = CoverageAnalysisResult(**data)
        assert result.schema_version == "coverage_analysis_v1"
        assert result.line_items[0].decision_trace is None
        assert result.repair_context is None
