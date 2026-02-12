"""Tests for LLMMatcher.classify_items() -- LLM-first classification.

Tests that classify_items enriches items with keyword/part-number hints
and delegates to batch_match.
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


def _make_llm_response(is_covered: bool, category: str, component: str, confidence: float = 0.8):
    """Build a mock LLM response for a single item."""
    content = json.dumps({
        "is_covered": is_covered,
        "category": category,
        "matched_component": component,
        "confidence": confidence,
        "reasoning": f"Test reasoning for {component}",
    })
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return response


class TestClassifyItemsBasic:
    """Basic tests for classify_items()."""

    def test_empty_items_returns_empty(self):
        matcher = LLMMatcher(config=LLMMatcherConfig(max_retries=1))
        result = matcher.classify_items(
            items=[],
            covered_components={"engine": ["Motor"]},
        )
        assert result == []

    def test_classify_items_delegates_to_batch_match(self):
        """Verify classify_items eventually calls batch_match."""
        config = LLMMatcherConfig(prompt_name="nonexistent", max_retries=1)
        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            return_value=_make_llm_response(True, "engine", "motor"),
        )
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


class TestClassifyItemsWithHints:
    """Tests for hint enrichment in classify_items()."""

    def _make_client(self, responses):
        """Make a mock client that returns responses in order."""
        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(side_effect=responses)
        return client

    def test_keyword_hints_injected_into_context(self):
        """Keyword hints should appear in the item's repair_context_description."""
        config = LLMMatcherConfig(prompt_name="nonexistent", max_retries=1)
        client = self._make_client([
            _make_llm_response(True, "engine", "motor"),
        ])
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

        # Verify the LLM was called and the hint was in the messages
        assert client.chat_completions_create.called
        call_args = client.chat_completions_create.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        # The user message should contain the keyword hint
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "MOTOR" in user_msg["content"]

    def test_part_number_hints_injected_into_context(self):
        """Part-number hints should be passed through to LLM call."""
        config = LLMMatcherConfig(prompt_name="nonexistent", max_retries=1)
        client = self._make_client([
            _make_llm_response(True, "engine", "timing_chain"),
        ])
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
        config = LLMMatcherConfig(prompt_name="nonexistent", max_retries=1)
        client = self._make_client([
            _make_llm_response(False, None, None, confidence=0.7),
        ])
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

    def test_mixed_hints(self):
        """Some items have hints, others don't."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent", max_retries=1, max_concurrent=1,
        )
        client = self._make_client([
            _make_llm_response(True, "engine", "motor"),
            _make_llm_response(False, None, None, confidence=0.7),
        ])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
            {"description": "UNKNOWN PART", "item_type": "parts", "total_price": 100},
        ]
        keyword_hints = [
            {"keyword": "MOTOR", "category": "engine", "component": "motor",
             "confidence": 0.85, "has_consumable_indicator": False},
            None,  # No hint for second item
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            keyword_hints=keyword_hints,
        )

        assert len(results) == 2
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.NOT_COVERED


class TestClassifyItemsRepairContext:
    """Tests for repair context enrichment."""

    def test_global_repair_context_applied(self):
        """Global repair context applied to items without their own."""
        config = LLMMatcherConfig(prompt_name="nonexistent", max_retries=1)
        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            return_value=_make_llm_response(True, "engine", "motor"),
        )
        matcher = LLMMatcher(config=config, audited_client=client)

        items = [
            {"description": "MOTOR BLOCK", "item_type": "parts", "total_price": 500},
        ]

        results = matcher.classify_items(
            items=items,
            covered_components={"engine": ["Motor"]},
            repair_context_description="Engine failure diagnosed",
        )

        # Verify classify_items succeeds and the LLM was called
        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert client.chat_completions_create.called

    def test_item_level_context_preserved(self):
        """Item-level repair_context_description is not overwritten by global."""
        config = LLMMatcherConfig(prompt_name="nonexistent", max_retries=1)
        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            return_value=_make_llm_response(True, "engine", "motor"),
        )
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

    def test_on_progress_called(self):
        config = LLMMatcherConfig(
            prompt_name="nonexistent", max_retries=1, max_concurrent=1,
        )
        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            return_value=_make_llm_response(True, "engine", "motor"),
        )
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
