"""Tests for the explanation generator."""

import json as _json
from pathlib import Path

import pytest
import yaml

from context_builder.coverage.explanation_generator import (
    ExplanationConfig,
    ExplanationGenerator,
    TemplateEntry,
    infer_exclusion_reason,
)
from context_builder.coverage.schemas import (
    CoverageAnalysisResult,
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
    NonCoveredExplanation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    description: str = "Test item",
    item_type: str = "parts",
    total_price: float = 100.0,
    coverage_status: CoverageStatus = CoverageStatus.NOT_COVERED,
    match_method: MatchMethod = MatchMethod.RULE,
    match_confidence: float = 1.0,
    match_reasoning: str = "test",
    exclusion_reason: str | None = None,
    coverage_category: str | None = None,
    item_code: str | None = None,
) -> LineItemCoverage:
    return LineItemCoverage(
        description=description,
        item_type=item_type,
        total_price=total_price,
        coverage_status=coverage_status,
        match_method=match_method,
        match_confidence=match_confidence,
        match_reasoning=match_reasoning,
        exclusion_reason=exclusion_reason,
        coverage_category=coverage_category,
        item_code=item_code,
        covered_amount=0.0 if coverage_status != CoverageStatus.COVERED else total_price,
        not_covered_amount=total_price if coverage_status != CoverageStatus.COVERED else 0.0,
    )


def _make_result(items: list[LineItemCoverage]) -> CoverageAnalysisResult:
    return CoverageAnalysisResult(
        claim_id="TEST-001",
        line_items=items,
    )


# ---------------------------------------------------------------------------
# infer_exclusion_reason
# ---------------------------------------------------------------------------

class TestInferExclusionReason:
    """Backward-compat parser for legacy results without exclusion_reason."""

    def test_fee_reasoning(self):
        item = _make_item(match_reasoning="Fee items (fee) are not covered by policy")
        assert infer_exclusion_reason(item) == "fee"

    def test_exclusion_pattern_reasoning(self):
        item = _make_item(match_reasoning="Item matches exclusion pattern: ENTSORG")
        assert infer_exclusion_reason(item) == "exclusion_pattern"

    def test_consumable_reasoning(self):
        item = _make_item(match_reasoning="Consumable item not covered: FILTER")
        assert infer_exclusion_reason(item) == "consumable"

    def test_non_covered_labor_reasoning(self):
        item = _make_item(match_reasoning="Labor matches non-covered pattern: DIAGNOS")
        assert infer_exclusion_reason(item) == "non_covered_labor"

    def test_generic_description_reasoning(self):
        item = _make_item(match_reasoning="Generic description - insufficient detail")
        assert infer_exclusion_reason(item) == "generic_description"

    def test_override_excluded_list(self):
        item = _make_item(match_reasoning="LLM matched [OVERRIDE: Component is in excluded list]")
        assert infer_exclusion_reason(item) == "component_excluded"

    def test_demoted_reasoning(self):
        item = _make_item(match_reasoning="engine labor [DEMOTED: no covered parts]")
        assert infer_exclusion_reason(item) == "demoted_no_anchor"

    def test_review_category_not_covered(self):
        item = _make_item(match_reasoning="LLM said covered [REVIEW: category 'turbo' is not covered]")
        assert infer_exclusion_reason(item) == "category_not_covered"

    def test_not_in_exhaustive_list(self):
        item = _make_item(match_reasoning="Part X not in policy's exhaustive parts list")
        assert infer_exclusion_reason(item) == "component_not_in_list"

    def test_explicitly_excluded_by_policy(self):
        item = _make_item(match_reasoning="Part X explicitly excluded by policy")
        assert infer_exclusion_reason(item) == "component_excluded"

    def test_which_is_not_covered(self):
        item = _make_item(match_reasoning="category 'turbo' which is not covered")
        assert infer_exclusion_reason(item) == "category_not_covered"

    def test_unknown_fallback(self):
        item = _make_item(match_reasoning="Something completely different")
        assert infer_exclusion_reason(item) == "other"

    def test_custom_patterns(self):
        custom = [("custom rule", "custom_reason")]
        item = _make_item(match_reasoning="Matches custom rule here")
        assert infer_exclusion_reason(item, custom) == "custom_reason"


# ---------------------------------------------------------------------------
# ExplanationConfig
# ---------------------------------------------------------------------------

class TestExplanationConfig:
    """Tests for config loading and defaults."""

    def test_default_has_all_standard_reasons(self):
        config = ExplanationConfig.default()
        expected_reasons = [
            "fee", "consumable", "exclusion_pattern", "non_covered_labor",
            "generic_description", "component_excluded", "component_not_in_list",
            "category_not_covered", "demoted_no_anchor",
        ]
        for reason in expected_reasons:
            assert reason in config.templates, f"Missing default template for {reason}"

    def test_default_subgroup_reasons(self):
        config = ExplanationConfig.default()
        assert "category_not_covered" in config.category_subgroup_reasons
        assert "component_not_in_list" in config.category_subgroup_reasons

    def test_from_yaml(self, tmp_path):
        yaml_content = {
            "category_subgroup_reasons": ["category_not_covered"],
            "templates": {
                "fee": {
                    "explanation": "Fees not covered.",
                    "policy_reference": "Art. 4.2",
                },
                "other": {
                    "explanation": None,
                    "policy_reference": None,
                },
            },
            "category_templates": {
                "turbo": {
                    "explanation": "Turbo not included.",
                    "policy_reference": "Turbo clause",
                },
            },
            "summary_template": "{count} items not covered.",
            "reason_patterns": [
                {"pattern": "custom", "reason": "custom_reason"},
            ],
        }
        path = tmp_path / "test_templates.yaml"
        with open(path, "w") as f:
            yaml.dump(yaml_content, f)

        config = ExplanationConfig.from_yaml(path)
        assert "fee" in config.templates
        assert config.templates["fee"].explanation_template == "Fees not covered."
        assert config.templates["fee"].policy_reference == "Art. 4.2"
        assert "turbo" in config.category_templates
        assert config.summary_template == "{count} items not covered."
        assert len(config.reason_patterns) == 1
        assert config.reason_patterns[0] == ("custom", "custom_reason")

    def test_from_yaml_empty(self, tmp_path):
        path = tmp_path / "empty.yaml"
        with open(path, "w") as f:
            f.write("")
        config = ExplanationConfig.from_yaml(path)
        assert config.templates == {}

    def test_from_yaml_nsa_config(self):
        """Load the actual NSA config if available."""
        path = (
            Path(__file__).resolve().parents[2]
            / "workspaces" / "nsa" / "config" / "coverage"
            / "nsa_explanation_templates.yaml"
        )
        if not path.exists():
            pytest.skip("NSA explanation templates not available")
        config = ExplanationConfig.from_yaml(path)
        assert "fee" in config.templates
        assert "consumable" in config.templates
        assert "category_not_covered" in config.category_subgroup_reasons


# ---------------------------------------------------------------------------
# ExplanationGenerator
# ---------------------------------------------------------------------------

class TestExplanationGenerator:
    """Tests for grouping and template fill."""

    def test_all_covered_returns_empty(self):
        items = [
            _make_item(coverage_status=CoverageStatus.COVERED),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, summary = gen.generate(result)
        assert explanations == []
        assert summary == ""

    def test_single_not_covered_item(self):
        items = [
            _make_item(
                description="ENTSORGUNG",
                exclusion_reason="exclusion_pattern",
                total_price=50.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, summary = gen.generate(result)
        assert len(explanations) == 1
        assert explanations[0].exclusion_reason == "exclusion_pattern"
        assert explanations[0].total_amount == 50.0
        assert len(explanations[0].items) == 1
        assert "ENTSORGUNG" in explanations[0].items

    def test_grouping_by_reason(self):
        items = [
            _make_item(description="Fee 1", exclusion_reason="fee", total_price=30.0),
            _make_item(description="Fee 2", exclusion_reason="fee", total_price=20.0),
            _make_item(description="Oil filter", exclusion_reason="consumable", total_price=15.0),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, summary = gen.generate(result)
        assert len(explanations) == 2

        fee_group = next(e for e in explanations if e.exclusion_reason == "fee")
        assert len(fee_group.items) == 2
        assert fee_group.total_amount == 50.0

        consumable_group = next(e for e in explanations if e.exclusion_reason == "consumable")
        assert len(consumable_group.items) == 1
        assert consumable_group.total_amount == 15.0

    def test_category_subgrouping(self):
        """Items with category_not_covered should sub-group by category."""
        items = [
            _make_item(
                description="Turbo part",
                exclusion_reason="category_not_covered",
                coverage_category="turbo",
                total_price=500.0,
            ),
            _make_item(
                description="Hybrid part",
                exclusion_reason="category_not_covered",
                coverage_category="hybrid",
                total_price=300.0,
            ),
            _make_item(
                description="Another turbo part",
                exclusion_reason="category_not_covered",
                coverage_category="turbo",
                total_price=200.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, summary = gen.generate(result)

        # Should be 2 groups: turbo and hybrid
        assert len(explanations) == 2
        turbo = next(e for e in explanations if e.category == "turbo")
        assert len(turbo.items) == 2
        assert turbo.total_amount == 700.0

        hybrid = next(e for e in explanations if e.category == "hybrid")
        assert len(hybrid.items) == 1
        assert hybrid.total_amount == 300.0

    def test_non_subgrouped_reasons_merge_categories(self):
        """Fee items from different categories should be in one group."""
        items = [
            _make_item(
                description="Fee A",
                exclusion_reason="fee",
                coverage_category="engine",
                total_price=10.0,
            ),
            _make_item(
                description="Fee B",
                exclusion_reason="fee",
                coverage_category="chassis",
                total_price=20.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, _ = gen.generate(result)
        assert len(explanations) == 1
        assert explanations[0].category is None

    def test_template_fill_with_category(self):
        config = ExplanationConfig.default()
        items = [
            _make_item(
                description="Turbo valve",
                exclusion_reason="category_not_covered",
                coverage_category="turbo",
                total_price=400.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator(config)
        explanations, _ = gen.generate(result)
        assert len(explanations) == 1
        assert "turbo" in explanations[0].explanation.lower()

    def test_category_template_override(self):
        """Category-specific templates should override reason templates."""
        config = ExplanationConfig(
            templates={
                "category_not_covered": TemplateEntry(
                    explanation_template="Generic: '{category}' not covered.",
                    policy_reference="Generic ref",
                ),
            },
            category_templates={
                "turbo": TemplateEntry(
                    explanation_template="Turbo-specific override.",
                    policy_reference="Turbo ref",
                ),
            },
            category_subgroup_reasons=["category_not_covered"],
        )
        items = [
            _make_item(
                description="Turbo part",
                exclusion_reason="category_not_covered",
                coverage_category="turbo",
                total_price=100.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator(config)
        explanations, _ = gen.generate(result)
        assert explanations[0].explanation == "Turbo-specific override."
        assert explanations[0].policy_reference == "Turbo ref"

    def test_fallback_to_match_reasoning(self):
        """When no template matches, use match_reasoning."""
        config = ExplanationConfig(templates={})
        items = [
            _make_item(
                description="Unknown item",
                exclusion_reason="unknown_reason",
                match_reasoning="Some detailed LLM reasoning here",
                total_price=50.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator(config)
        explanations, _ = gen.generate(result)
        assert len(explanations) == 1
        assert explanations[0].explanation == "Some detailed LLM reasoning here"

    def test_other_reason_with_null_template(self):
        """'other' with null template falls back to match_reasoning."""
        config = ExplanationConfig(
            templates={
                "other": TemplateEntry(explanation_template=None),
            },
        )
        items = [
            _make_item(
                description="Mystery item",
                exclusion_reason="other",
                match_reasoning="LLM said not covered because reasons",
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator(config)
        explanations, _ = gen.generate(result)
        assert explanations[0].explanation == "LLM said not covered because reasons"

    def test_min_confidence_in_group(self):
        items = [
            _make_item(exclusion_reason="fee", match_confidence=1.0, total_price=10.0),
            _make_item(exclusion_reason="fee", match_confidence=0.7, total_price=10.0),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, _ = gen.generate(result)
        assert explanations[0].match_confidence == 0.7

    def test_review_needed_included(self):
        """REVIEW_NEEDED items should be included in explanations."""
        items = [
            _make_item(
                coverage_status=CoverageStatus.REVIEW_NEEDED,
                exclusion_reason="category_not_covered",
                coverage_category="turbo",
                total_price=200.0,
                match_confidence=0.45,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, _ = gen.generate(result)
        assert len(explanations) == 1
        assert explanations[0].exclusion_reason == "category_not_covered"

    def test_summary_generation(self):
        items = [
            _make_item(exclusion_reason="fee", total_price=50.0),
            _make_item(exclusion_reason="consumable", total_price=25.0),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        _, summary = gen.generate(result)
        assert "2 item(s)" in summary
        assert "75.00" in summary
        assert "CHF" in summary

    def test_item_codes_preserved(self):
        items = [
            _make_item(
                description="Part A",
                exclusion_reason="fee",
                item_code="P001",
                total_price=10.0,
            ),
            _make_item(
                description="Part B",
                exclusion_reason="fee",
                item_code=None,
                total_price=10.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, _ = gen.generate(result)
        assert explanations[0].item_codes == ["P001", None]

    def test_backward_compat_no_exclusion_reason(self):
        """Items without exclusion_reason should be classified by match_reasoning."""
        items = [
            _make_item(
                description="MIETFAHRZEUG",
                exclusion_reason=None,
                match_reasoning="Item matches exclusion pattern: MIETFAHRZEUG",
                total_price=80.0,
            ),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, _ = gen.generate(result)
        assert len(explanations) == 1
        assert explanations[0].exclusion_reason == "exclusion_pattern"

    def test_sorted_by_total_descending(self):
        items = [
            _make_item(exclusion_reason="fee", total_price=10.0),
            _make_item(exclusion_reason="consumable", total_price=500.0),
            _make_item(exclusion_reason="exclusion_pattern", total_price=100.0),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()
        explanations, _ = gen.generate(result)
        amounts = [e.total_amount for e in explanations]
        assert amounts == sorted(amounts, reverse=True)

    def test_empty_line_items(self):
        result = _make_result([])
        gen = ExplanationGenerator()
        explanations, summary = gen.generate(result)
        assert explanations == []
        assert summary == ""


# ---------------------------------------------------------------------------
# LLM rewrite path
# ---------------------------------------------------------------------------

class _FakeChoice:
    def __init__(self, content: str):
        self.message = type("M", (), {"content": content})()


class _FakeLLMClient:
    """Minimal mock that records calls and returns canned JSON."""

    def __init__(self, response_json: str):
        self._response_json = response_json
        self.calls: list = []

    def chat_completions_create(self, **kwargs):
        self.calls.append(kwargs)
        return type("R", (), {"choices": [_FakeChoice(self._response_json)]})()


class _FailingLLMClient:
    """LLM client that always raises."""

    def chat_completions_create(self, **kwargs):
        raise RuntimeError("LLM unavailable")


class TestExplanationGeneratorLLM:
    """Tests for the LLM rewrite path."""

    _COVERED = {
        "engine": ["timing chain", "cylinder head", "piston"],
        "suspension": ["shock absorber", "spring", "control arm"],
    }

    def test_llm_rewrites_explanations(self):
        """When LLM client returns valid JSON, explanations are rewritten."""
        items = [
            _make_item(
                description="Valve 8W0616887",
                exclusion_reason="component_not_in_list",
                coverage_category="suspension",
                total_price=250.0,
            ),
            _make_item(
                description="ENTSORGUNG",
                exclusion_reason="exclusion_pattern",
                total_price=30.0,
            ),
        ]
        result = _make_result(items)

        llm_response = _json.dumps([
            {"group": 1, "explanation": "Valve is not among covered suspension parts."},
            {"group": 2, "explanation": "Disposal fees are not covered."},
        ])
        client = _FakeLLMClient(llm_response)
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=self._COVERED,
            llm_client=client,
        )

        assert len(explanations) == 2
        # The LLM text should replace template text
        valve_group = next(e for e in explanations if e.exclusion_reason == "component_not_in_list")
        assert valve_group.explanation == "Valve is not among covered suspension parts."
        assert valve_group.policy_reference is None  # cleared by LLM path

        disposal_group = next(e for e in explanations if e.exclusion_reason == "exclusion_pattern")
        assert disposal_group.explanation == "Disposal fees are not covered."

        # Should have made exactly one LLM call
        assert len(client.calls) == 1

    def test_llm_failure_falls_back_to_templates(self):
        """When LLM call fails, template explanations are preserved."""
        items = [
            _make_item(
                description="Oil filter",
                exclusion_reason="consumable",
                total_price=15.0,
            ),
        ]
        result = _make_result(items)
        client = _FailingLLMClient()
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=self._COVERED,
            llm_client=client,
        )

        assert len(explanations) == 1
        # Should have the template text, not LLM text
        assert explanations[0].explanation == "Consumable items are not covered."

    def test_no_llm_client_uses_templates(self):
        """Without llm_client, generator uses pure template mode."""
        items = [
            _make_item(exclusion_reason="fee", total_price=50.0),
        ]
        result = _make_result(items)
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=self._COVERED,
            llm_client=None,
        )

        assert len(explanations) == 1
        assert explanations[0].explanation == "Fee items are not covered by the policy."

    def test_no_covered_components_skips_llm(self):
        """LLM rewrite is skipped when covered_components is empty/None."""
        items = [
            _make_item(exclusion_reason="fee", total_price=50.0),
        ]
        result = _make_result(items)
        client = _FakeLLMClient("[]")
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=None,
            llm_client=client,
        )

        # Should NOT have called LLM
        assert len(client.calls) == 0
        assert explanations[0].explanation == "Fee items are not covered by the policy."

    def test_llm_response_with_code_fences(self):
        """LLM response wrapped in markdown code fences is parsed correctly."""
        items = [
            _make_item(exclusion_reason="fee", total_price=50.0),
        ]
        result = _make_result(items)

        llm_response = '```json\n[{"group": 1, "explanation": "Fees excluded."}]\n```'
        client = _FakeLLMClient(llm_response)
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=self._COVERED,
            llm_client=client,
        )

        assert explanations[0].explanation == "Fees excluded."

    def test_llm_partial_response_preserves_unrewritten_groups(self):
        """If LLM only rewrites some groups, others keep template text."""
        items = [
            _make_item(exclusion_reason="fee", total_price=50.0),
            _make_item(exclusion_reason="consumable", total_price=25.0),
        ]
        result = _make_result(items)

        # Only rewrite group 1 (fee), omit group 2 (consumable)
        llm_response = _json.dumps([
            {"group": 1, "explanation": "Fees not payable."},
        ])
        client = _FakeLLMClient(llm_response)
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=self._COVERED,
            llm_client=client,
        )

        fee_group = next(e for e in explanations if e.exclusion_reason == "fee")
        assert fee_group.explanation == "Fees not payable."

        consumable_group = next(e for e in explanations if e.exclusion_reason == "consumable")
        # Should retain template text
        assert consumable_group.explanation == "Consumable items are not covered."

    def test_prompt_includes_covered_components(self):
        """The LLM prompt should include policy coverage context."""
        items = [
            _make_item(exclusion_reason="fee", total_price=50.0),
        ]
        result = _make_result(items)

        llm_response = _json.dumps([
            {"group": 1, "explanation": "Fee items excluded."},
        ])
        client = _FakeLLMClient(llm_response)
        gen = ExplanationGenerator()

        gen.generate(
            result,
            covered_components=self._COVERED,
            excluded_components={"engine": ["turbocharger"]},
            llm_client=client,
        )

        # Verify the prompt content
        assert len(client.calls) == 1
        messages = client.calls[0]["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")

        # Should contain covered component info
        assert "timing chain" in user_msg["content"]
        assert "shock absorber" in user_msg["content"]
        # Should contain excluded component info
        assert "turbocharger" in user_msg["content"]

    def test_excluded_components_passed_through(self):
        """Excluded components should appear in the LLM prompt."""
        items = [
            _make_item(
                exclusion_reason="component_excluded",
                coverage_category="engine",
                total_price=100.0,
            ),
        ]
        result = _make_result(items)

        llm_response = _json.dumps([
            {"group": 1, "explanation": "Turbocharger explicitly excluded."},
        ])
        client = _FakeLLMClient(llm_response)
        gen = ExplanationGenerator()

        explanations, _ = gen.generate(
            result,
            covered_components=self._COVERED,
            excluded_components={"engine": ["turbocharger"]},
            llm_client=client,
        )

        assert explanations[0].explanation == "Turbocharger explicitly excluded."


# ---------------------------------------------------------------------------
# _parse_llm_response (unit)
# ---------------------------------------------------------------------------

class TestParseLLMResponse:
    """Direct tests for the JSON parser."""

    def test_plain_json(self):
        content = '[{"group": 1, "explanation": "Not covered."}]'
        original = [NonCoveredExplanation(
            exclusion_reason="fee",
            items=["item"],
            explanation="template text",
        )]
        result = ExplanationGenerator._parse_llm_response(content, original)
        assert result[0].explanation == "Not covered."
        assert result[0].policy_reference is None

    def test_code_fenced_json(self):
        content = '```json\n[{"group": 1, "explanation": "Rewritten."}]\n```'
        original = [NonCoveredExplanation(
            exclusion_reason="fee",
            items=["item"],
            explanation="template text",
        )]
        result = ExplanationGenerator._parse_llm_response(content, original)
        assert result[0].explanation == "Rewritten."

    def test_invalid_json_raises(self):
        content = "This is not JSON"
        original = [NonCoveredExplanation(
            exclusion_reason="fee",
            items=["item"],
            explanation="template text",
        )]
        with pytest.raises(_json.JSONDecodeError):
            ExplanationGenerator._parse_llm_response(content, original)

    def test_missing_group_preserves_original(self):
        content = '[{"group": 99, "explanation": "Orphan text."}]'
        original = [NonCoveredExplanation(
            exclusion_reason="fee",
            items=["item"],
            explanation="template text",
            policy_reference="Art. 1",
        )]
        result = ExplanationGenerator._parse_llm_response(content, original)
        # Group 99 doesn't match group 1, so original is preserved
        assert result[0].explanation == "template text"
        assert result[0].policy_reference == "Art. 1"
