"""Tests for DecisionSource enum and decision_source tagging on TraceStep."""

import pytest

from context_builder.coverage.schemas import (
    CoverageStatus,
    DecisionSource,
    LineItemCoverage,
    MatchMethod,
    TraceAction,
    TraceStep,
)
from context_builder.coverage.trace import TraceBuilder


class TestDecisionSourceEnum:
    """Tests for DecisionSource enum values."""

    def test_all_values_exist(self):
        values = {ds.value for ds in DecisionSource}
        expected = {
            "rule", "part_number", "keyword", "llm",
            "promotion", "demotion", "validation",
        }
        assert values == expected

    def test_is_string_enum(self):
        assert isinstance(DecisionSource.RULE, str)
        assert DecisionSource.RULE == "rule"
        assert DecisionSource.LLM == "llm"
        assert DecisionSource.PROMOTION == "promotion"


class TestTraceStepDecisionSource:
    """Tests for the decision_source field on TraceStep."""

    def test_default_is_none(self):
        step = TraceStep(
            stage="test",
            action=TraceAction.MATCHED,
            reasoning="test step",
        )
        assert step.decision_source is None

    def test_set_decision_source(self):
        step = TraceStep(
            stage="rule_engine",
            action=TraceAction.EXCLUDED,
            reasoning="Fee item",
            decision_source=DecisionSource.RULE,
        )
        assert step.decision_source == DecisionSource.RULE

    def test_serialization_roundtrip_with_decision_source(self):
        step = TraceStep(
            stage="keyword",
            action=TraceAction.MATCHED,
            verdict=CoverageStatus.COVERED,
            confidence=0.85,
            reasoning="Keyword match",
            detail={"keyword": "ZAHNRIEMEN"},
            decision_source=DecisionSource.KEYWORD,
        )
        data = step.model_dump()
        assert data["decision_source"] == "keyword"

        restored = TraceStep(**data)
        assert restored.decision_source == DecisionSource.KEYWORD
        assert restored == step

    def test_backward_compat_no_decision_source(self):
        """Old trace JSON without decision_source should deserialize correctly."""
        data = {
            "stage": "rule_engine",
            "action": "excluded",
            "reasoning": "Fee item",
            "verdict": "not_covered",
            "confidence": 1.0,
            "detail": {"rule": "fee_item"},
        }
        step = TraceStep(**data)
        assert step.decision_source is None
        assert step.stage == "rule_engine"
        assert step.action == TraceAction.EXCLUDED


class TestTraceBuilderDecisionSource:
    """Tests for decision_source pass-through in TraceBuilder."""

    def test_add_with_decision_source(self):
        tb = TraceBuilder()
        tb.add(
            "rule_engine", TraceAction.EXCLUDED,
            "Fee item excluded",
            verdict=CoverageStatus.NOT_COVERED,
            confidence=1.0,
            decision_source=DecisionSource.RULE,
        )
        steps = tb.build()
        assert len(steps) == 1
        assert steps[0].decision_source == DecisionSource.RULE

    def test_add_without_decision_source(self):
        tb = TraceBuilder()
        tb.add("test", TraceAction.MATCHED, "no source")
        steps = tb.build()
        assert steps[0].decision_source is None

    def test_multiple_steps_different_sources(self):
        tb = TraceBuilder()
        tb.add("keyword", TraceAction.MATCHED, "keyword match",
               decision_source=DecisionSource.KEYWORD)
        tb.add("llm_validation", TraceAction.VALIDATED, "confirmed",
               decision_source=DecisionSource.VALIDATION)
        steps = tb.build()
        assert steps[0].decision_source == DecisionSource.KEYWORD
        assert steps[1].decision_source == DecisionSource.VALIDATION


class TestRuleEngineDecisionSource:
    """Integration: rule engine trace steps have decision_source=RULE."""

    def test_fee_item_has_rule_source(self):
        from context_builder.coverage.rule_engine import RuleConfig, RuleEngine

        engine = RuleEngine(RuleConfig.default())
        result = engine.match(
            description="Entsorgungsgebuehr",
            item_type="fee",
            total_price=50.0,
        )
        assert result is not None
        assert result.decision_trace is not None
        for step in result.decision_trace:
            assert step.decision_source == DecisionSource.RULE

    def test_zero_price_item_has_rule_source(self):
        from context_builder.coverage.rule_engine import RuleConfig, RuleEngine

        engine = RuleEngine(RuleConfig.default())
        result = engine.match(
            description="Complimentary check",
            item_type="labor",
            total_price=0.0,
        )
        assert result is not None
        assert result.decision_trace is not None
        for step in result.decision_trace:
            assert step.decision_source == DecisionSource.RULE


class TestKeywordMatcherDecisionSource:
    """Integration: keyword matcher trace steps have decision_source=KEYWORD."""

    def test_keyword_match_has_keyword_source(self):
        from context_builder.coverage.keyword_matcher import (
            KeywordConfig,
            KeywordMapping,
            KeywordMatcher,
        )

        config = KeywordConfig(
            mappings=[
                KeywordMapping(
                    category="engine",
                    keywords=["ZAHNRIEMEN"],
                    confidence=0.85,
                ),
            ],
        )
        matcher = KeywordMatcher(config)
        result = matcher.match(
            description="ZAHNRIEMEN",
            item_type="parts",
            total_price=200.0,
            covered_categories=["engine"],
        )
        assert result is not None
        assert result.decision_trace is not None
        for step in result.decision_trace:
            assert step.decision_source == DecisionSource.KEYWORD


class TestBackwardCompatibility:
    """Ensure old data without decision_source fields loads correctly."""

    def test_old_line_item_coverage_no_decision_source_in_trace(self):
        """LineItemCoverage with old trace data (no decision_source) loads fine."""
        data = {
            "description": "Test item",
            "item_type": "parts",
            "total_price": 100.0,
            "coverage_status": "covered",
            "match_method": "rule",
            "match_confidence": 1.0,
            "match_reasoning": "Test",
            "decision_trace": [
                {
                    "stage": "rule_engine",
                    "action": "matched",
                    "reasoning": "Zero-price item",
                    "verdict": "covered",
                    "confidence": 1.0,
                },
            ],
        }
        item = LineItemCoverage(**data)
        assert item.decision_trace is not None
        assert len(item.decision_trace) == 1
        assert item.decision_trace[0].decision_source is None
        assert item.decision_trace[0].stage == "rule_engine"

    def test_old_trace_step_no_decision_source(self):
        """TraceStep without decision_source deserializes with None."""
        data = {
            "stage": "llm",
            "action": "matched",
            "reasoning": "LLM coverage",
            "verdict": "covered",
            "confidence": 0.82,
            "detail": {"model": "gpt-4o"},
        }
        step = TraceStep(**data)
        assert step.decision_source is None
        assert step.confidence == 0.82
