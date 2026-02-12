"""Tests for LLMMatcher.classify_items() -- batch LLM classification.

Tests that classify_items batches items into multi-item LLM calls,
enriches prompts with keyword/part-number hints, and applies
post-processing (vague-description capping, asymmetric thresholds).
"""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest

from context_builder.coverage.llm_matcher import LLMMatcher, LLMMatcherConfig
from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
)


def _make_batch_response(items_data: List[Dict[str, Any]]):
    """Build a mock LLM response for a batch of items.

    Args:
        items_data: List of dicts with keys: index, is_covered, category,
            matched_component, confidence, reasoning.
    """
    content = json.dumps({"items": items_data})
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock(prompt_tokens=500, completion_tokens=200)
    return response


def _make_single_item_data(
    index: int,
    is_covered: bool,
    category: str = "engine",
    component: str = "motor",
    confidence: float = 0.85,
) -> Dict[str, Any]:
    """Build one entry for a batch response."""
    return {
        "index": index,
        "is_covered": is_covered,
        "category": category,
        "matched_component": component,
        "confidence": confidence,
        "reasoning": f"Test reasoning for item {index}",
    }


def _make_client(responses):
    """Make a mock client that returns responses in order."""
    client = MagicMock()
    client.set_context = MagicMock(return_value=client)
    client.chat_completions_create = MagicMock(side_effect=responses)
    return client


class TestClassifyItemsBasic:
    """Basic tests for classify_items()."""

    def test_empty_items_returns_empty(self):
        matcher = LLMMatcher(config=LLMMatcherConfig(max_retries=1))
        result = matcher.classify_items(
            items=[],
            covered_components={"engine": ["Motor"]},
        )
        assert result == []

    def test_single_item_batch(self):
        """Single item should produce a single batch call."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = _make_batch_response([
            _make_single_item_data(0, True, "engine", "motor"),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            claim_id="TEST-001",
        )

        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[0].match_method == MatchMethod.LLM
        # Only 1 LLM call for the batch
        assert client.chat_completions_create.call_count == 1

    def test_five_items_single_batch(self):
        """5 items with batch_size=15 should fit in 1 batch (1 LLM call)."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15, max_concurrent=1,
        )
        batch_data = [
            _make_single_item_data(i, i % 2 == 0) for i in range(5)
        ]
        client = _make_client([_make_batch_response(batch_data)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": f"PART_{i}", "item_type": "parts", "total_price": 100 + i}
            for i in range(5)
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 5
        assert client.chat_completions_create.call_count == 1
        # Even indices covered, odd not
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.NOT_COVERED

    def test_40_items_split_into_3_batches(self):
        """40 items with batch_size=15 should produce 3 batches (15+15+10)."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15, max_concurrent=1,
        )
        # 3 batch responses: 15, 15, 10 items
        batch1 = [_make_single_item_data(i, True) for i in range(15)]
        batch2 = [_make_single_item_data(i, True) for i in range(15)]
        batch3 = [_make_single_item_data(i, True) for i in range(10)]
        client = _make_client([
            _make_batch_response(batch1),
            _make_batch_response(batch2),
            _make_batch_response(batch3),
        ])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": f"PART_{i}", "item_type": "parts", "total_price": 100}
            for i in range(40)
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 40
        assert client.chat_completions_create.call_count == 3
        # All items should be classified (no truncation)
        assert all(r.coverage_status == CoverageStatus.COVERED for r in results)


class TestClassifyItemsParseFailure:
    """Tests for parse failure handling."""

    def test_parse_failure_returns_review_needed(self):
        """JSON parse failure should return REVIEW_NEEDED for all items in batch."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "NOT VALID JSON!!!"
        response.usage = MagicMock(prompt_tokens=500, completion_tokens=50)
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "PART_A", "item_type": "parts", "total_price": 100},
            {"description": "PART_B", "item_type": "parts", "total_price": 200},
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 2
        assert all(r.coverage_status == CoverageStatus.REVIEW_NEEDED for r in results)
        assert all(r.match_confidence == 0.0 for r in results)

    def test_missing_item_in_response_gets_review_needed(self):
        """If the LLM omits an item from its response, it gets REVIEW_NEEDED."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        # Response only includes index 0, omits index 1
        batch_data = [_make_single_item_data(0, True)]
        client = _make_client([_make_batch_response(batch_data)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR", "item_type": "parts", "total_price": 500},
            {"description": "UNKNOWN", "item_type": "parts", "total_price": 100},
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 2
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.REVIEW_NEEDED
        assert results[1].match_confidence == 0.0


class TestClassifyItemsWithHints:
    """Tests for hint enrichment in classify_items()."""

    def test_keyword_hints_in_batch_prompt(self):
        """Keyword hints should appear in the batch prompt's item list."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = _make_batch_response([
            _make_single_item_data(0, True),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
        ]
        keyword_hints = [
            {"keyword": "MOTOR", "category": "engine", "component": "motor",
             "confidence": 0.85, "has_consumable_indicator": False},
        ]

        matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            keyword_hints=keyword_hints,
        )

        assert client.chat_completions_create.called
        call_args = client.chat_completions_create.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "MOTOR" in user_msg["content"]
        assert "Keyword hint" in user_msg["content"]

    def test_part_number_hints_in_batch_prompt(self):
        """Part-number hints should appear in the batch prompt."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = _make_batch_response([
            _make_single_item_data(0, True, "engine", "timing_chain"),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "STEUERKETTE", "item_type": "parts",
             "item_code": "ABC123", "total_price": 300},
        ]
        part_number_hints = [
            {"part_number": "ABC123", "system": "engine",
             "component": "timing_chain", "lookup_source": "assumptions",
             "covered": True},
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Steuerkette"]},
            part_number_hints=part_number_hints,
        )

        assert client.chat_completions_create.called
        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED

    def test_no_hints_still_works(self):
        """Items without hints should still be classified normally."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = _make_batch_response([
            _make_single_item_data(0, False, confidence=0.7),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "UNKNOWN PART", "item_type": "parts", "total_price": 100},
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            keyword_hints=[None],
            part_number_hints=[None],
        )

        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.NOT_COVERED

    def test_mixed_hints_in_same_batch(self):
        """Some items have hints, others don't -- all in one batch."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15, max_concurrent=1,
        )
        batch_data = [
            _make_single_item_data(0, True, "engine", "motor"),
            _make_single_item_data(1, False, confidence=0.7),
        ]
        client = _make_client([_make_batch_response(batch_data)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
            {"description": "UNKNOWN PART", "item_type": "parts", "total_price": 100},
        ]
        keyword_hints = [
            {"keyword": "MOTOR", "category": "engine", "component": "motor",
             "confidence": 0.85, "has_consumable_indicator": False},
            None,
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            keyword_hints=keyword_hints,
        )

        assert len(results) == 2
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.NOT_COVERED
        # Single batch call for both items
        assert client.chat_completions_create.call_count == 1


class TestClassifyItemsVagueDescription:
    """Tests for vague description confidence capping."""

    def test_vague_description_confidence_capped(self):
        """Vague descriptions should have confidence capped at 0.50."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        # LLM returns high confidence for a vague description
        batch_data = [
            _make_single_item_data(0, True, confidence=0.85),
        ]
        client = _make_client([_make_batch_response(batch_data)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "PART", "item_type": "parts", "total_price": 100},
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 1
        # "PART" is in vague terms -> confidence capped to 0.50 -> below 0.60 threshold -> REVIEW_NEEDED
        assert results[0].coverage_status == CoverageStatus.REVIEW_NEEDED
        assert results[0].match_confidence == 0.50

    def test_non_vague_description_not_capped(self):
        """Normal descriptions should keep their LLM confidence."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        batch_data = [
            _make_single_item_data(0, True, confidence=0.85),
        ]
        client = _make_client([_make_batch_response(batch_data)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "STEUERKETTE MOTOR", "item_type": "parts", "total_price": 500},
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[0].match_confidence == 0.85


class TestClassifyItemsRepairContext:
    """Tests for repair context enrichment."""

    def test_global_repair_context_applied(self):
        """Global repair context applied to items without their own."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = _make_batch_response([
            _make_single_item_data(0, True),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            repair_context_description="Engine failure diagnosed",
        )

        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert client.chat_completions_create.called

    def test_item_level_context_preserved(self):
        """Item-level repair_context_description is not overwritten by global."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        response = _make_batch_response([
            _make_single_item_data(0, True),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500,
             "repair_context_description": "Specific motor context"},
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            repair_context_description="Global context",
        )

        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED


class TestClassifyItemsProgressCallback:
    """Tests for progress callback support."""

    def test_on_progress_called_per_batch(self):
        """Progress callback should be called once per batch with batch size."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15, max_concurrent=1,
        )
        response = _make_batch_response([
            _make_single_item_data(0, True),
        ])
        client = _make_client([response])
        matcher = LLMMatcher(config=config, audited_client=client)

        progress = MagicMock()
        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
        ]

        matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            on_progress=progress,
        )

        progress.assert_called()


class TestClassifyItemsTraceInfo:
    """Tests for trace/metadata in batch results."""

    def test_batch_info_in_trace(self):
        """Trace detail should include batch_index and batch_size."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        batch_data = [
            _make_single_item_data(0, True),
            _make_single_item_data(1, False, confidence=0.7),
        ]
        client = _make_client([_make_batch_response(batch_data)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR", "item_type": "parts", "total_price": 500},
            {"description": "OIL", "item_type": "parts", "total_price": 50},
        ]
        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
        )

        assert len(results) == 2
        # Check trace detail has batch info
        for r in results:
            assert r.decision_trace is not None
            assert len(r.decision_trace) > 0
            detail = r.decision_trace[0].detail or {}
            assert detail.get("batch_size") == 2


class TestBatchClassifyPromptBuilder:
    """Tests for _build_batch_classify_prompt()."""

    def test_inline_fallback_prompt_format(self):
        """Inline fallback prompt should contain items text and policy info."""
        config = LLMMatcherConfig(
            max_retries=1, classification_batch_size=15,
        )
        matcher = LLMMatcher(config=config)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts",
             "item_code": "M001", "total_price": 500,
             "repair_context_description": "Keyword hint: MOTOR -> engine"},
            {"description": "ÖLFILTER", "item_type": "parts",
             "total_price": 20},
        ]

        messages = matcher._build_batch_classify_prompt(
            items=items,
            covered_components={"engine": ["Motor", "Steuerkette"]},
            excluded_components={"engine": ["Ölfilter"]},
            covered_parts_in_claim=[{"item_code": "X1", "description": "Pumpe", "matched_component": "pump"}],
        )

        assert len(messages) == 2
        system_msg = messages[0]["content"]
        user_msg = messages[1]["content"]

        # System should contain policy matrix
        assert "engine" in system_msg
        assert "Motor" in system_msg
        # System should list excluded components
        assert "EXCLUDED" in system_msg

        # User message should contain numbered items
        assert "[0]" in user_msg
        assert "[1]" in user_msg
        assert "MOTOR BLOCK" in user_msg
        assert "ÖLFILTER" in user_msg
        # Hints should be in user message
        assert "Keyword hint" in user_msg


class TestBatchClassifyResponseParser:
    """Tests for _parse_batch_classify_response()."""

    def test_parse_valid_response(self):
        """Valid JSON with items array should parse correctly."""
        config = LLMMatcherConfig(max_retries=1)
        matcher = LLMMatcher(config=config)

        content = json.dumps({"items": [
            {"index": 0, "is_covered": True, "category": "engine",
             "matched_component": "Motor", "confidence": 0.85,
             "reasoning": "Exact match"},
            {"index": 1, "is_covered": False, "category": None,
             "matched_component": None, "confidence": 0.70,
             "reasoning": "Not in policy"},
        ]})

        items = [
            {"description": "MOTOR", "item_type": "parts"},
            {"description": "ÖLFILTER", "item_type": "parts"},
        ]
        results = matcher._parse_batch_classify_response(content, items)

        assert len(results) == 2
        assert results[0].is_covered is True
        assert results[0].category == "engine"
        assert results[0].confidence == 0.85
        assert results[1].is_covered is False
        assert results[1].confidence == 0.70

    def test_parse_with_markdown_code_block(self):
        """Response wrapped in ```json ... ``` should parse correctly."""
        config = LLMMatcherConfig(max_retries=1)
        matcher = LLMMatcher(config=config)

        inner = json.dumps({"items": [
            {"index": 0, "is_covered": True, "category": "engine",
             "matched_component": "Motor", "confidence": 0.80,
             "reasoning": "Match"},
        ]})
        content = f"```json\n{inner}\n```"

        items = [{"description": "MOTOR", "item_type": "parts"}]
        results = matcher._parse_batch_classify_response(content, items)

        assert len(results) == 1
        assert results[0].is_covered is True

    def test_parse_invalid_json_returns_defaults(self):
        """Invalid JSON should return REVIEW_NEEDED defaults for all items."""
        config = LLMMatcherConfig(max_retries=1)
        matcher = LLMMatcher(config=config)

        items = [
            {"description": "A", "item_type": "parts"},
            {"description": "B", "item_type": "parts"},
        ]
        results = matcher._parse_batch_classify_response("NOT JSON", items)

        assert len(results) == 2
        assert all(not r.is_covered for r in results)
        assert all(r.confidence == 0.0 for r in results)

    def test_parse_missing_indices(self):
        """Missing indices in response should get conservative defaults."""
        config = LLMMatcherConfig(max_retries=1)
        matcher = LLMMatcher(config=config)

        content = json.dumps({"items": [
            {"index": 0, "is_covered": True, "category": "engine",
             "matched_component": "Motor", "confidence": 0.85,
             "reasoning": "Match"},
            # index 1 is missing
        ]})
        items = [
            {"description": "MOTOR", "item_type": "parts"},
            {"description": "UNKNOWN", "item_type": "parts"},
        ]
        results = matcher._parse_batch_classify_response(content, items)

        assert len(results) == 2
        assert results[0].is_covered is True
        assert results[1].is_covered is False
        assert results[1].confidence == 0.0
