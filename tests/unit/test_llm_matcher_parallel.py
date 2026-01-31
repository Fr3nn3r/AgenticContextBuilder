"""Tests for parallel LLM matcher batch_match and retry logic."""

import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from context_builder.coverage.llm_matcher import LLMMatcher, LLMMatcherConfig
from context_builder.coverage.schemas import CoverageStatus, MatchMethod


def _make_mock_client(responses=None):
    """Create a mock AuditedOpenAIClient.

    Args:
        responses: Optional list of (is_covered, category, component, confidence) tuples.
                   If None, returns a default covered response.
    """
    client = MagicMock()
    client.client = MagicMock()  # underlying OpenAI client
    client._sink = MagicMock()   # audit log sink

    if responses is None:
        responses = [(True, "engine", "Turbocharger", 0.85)]

    call_index = {"i": 0}

    def fake_create(**kwargs):
        idx = call_index["i"]
        call_index["i"] += 1
        resp_data = responses[idx % len(responses)]
        is_covered, category, component, confidence = resp_data

        content = json.dumps({
            "is_covered": is_covered,
            "category": category,
            "matched_component": component,
            "confidence": confidence,
            "reasoning": f"Test reasoning for item {idx}",
        })

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = content
        return response

    client.chat_completions_create = MagicMock(side_effect=fake_create)
    client.set_context = MagicMock(return_value=client)
    return client


def _make_items(n):
    """Create n test line items."""
    return [
        {
            "item_code": f"P{i:03d}",
            "description": f"Test Part {i}",
            "item_type": "parts",
            "total_price": 100.0 + i,
        }
        for i in range(n)
    ]


def _make_success_thread_client():
    """Create a mock thread client that always succeeds."""
    mock = MagicMock()
    mock.set_context = MagicMock(return_value=mock)

    def fake_create(**kwargs):
        content = json.dumps({
            "is_covered": True,
            "category": "engine",
            "matched_component": "Turbo",
            "confidence": 0.85,
            "reasoning": "test",
        })
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = content
        return response

    mock.chat_completions_create = MagicMock(side_effect=fake_create)
    return mock


class TestLLMMatcherConfig:
    """Tests for config fields."""

    def test_default_max_concurrent(self):
        config = LLMMatcherConfig()
        assert config.max_concurrent == 3

    def test_max_concurrent_from_dict(self):
        config = LLMMatcherConfig.from_dict({"max_concurrent": 5})
        assert config.max_concurrent == 5

    def test_max_concurrent_from_dict_default(self):
        config = LLMMatcherConfig.from_dict({})
        assert config.max_concurrent == 3

    def test_max_concurrent_set_to_one(self):
        config = LLMMatcherConfig.from_dict({"max_concurrent": 1})
        assert config.max_concurrent == 1

    def test_default_retry_config(self):
        config = LLMMatcherConfig()
        assert config.max_retries == 3
        assert config.retry_base_delay == 1.0
        assert config.retry_max_delay == 15.0

    def test_retry_config_from_dict(self):
        config = LLMMatcherConfig.from_dict({
            "max_retries": 5,
            "retry_base_delay": 2.0,
            "retry_max_delay": 30.0,
        })
        assert config.max_retries == 5
        assert config.retry_base_delay == 2.0
        assert config.retry_max_delay == 30.0


class TestBatchMatchSequential:
    """Tests that sequential fallback works correctly."""

    def test_sequential_when_max_concurrent_is_one(self):
        """max_concurrent=1 should use sequential path."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_concurrent=1,
        )
        client = _make_mock_client([
            (True, "engine", "Turbo", 0.85),
            (False, None, None, 0.80),
        ])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = _make_items(2)
        results = matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
            claim_id="CLM-001",
        )

        assert len(results) == 2
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.NOT_COVERED
        assert matcher.get_llm_call_count() == 2

    def test_sequential_with_single_item(self):
        """Single item should always use sequential path regardless of max_concurrent."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_concurrent=5,
        )
        client = _make_mock_client([(True, "engine", "Turbo", 0.85)])
        matcher = LLMMatcher(config=config, audited_client=client)

        items = _make_items(1)
        results = matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert len(results) == 1
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert matcher.get_llm_call_count() == 1

    def test_sequential_progress_callback(self):
        """Progress callback should be called once per item in sequential mode."""
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt", max_concurrent=1)
        client = _make_mock_client([(True, "engine", "Turbo", 0.85)] * 3)
        matcher = LLMMatcher(config=config, audited_client=client)

        progress_calls = []
        results = matcher.batch_match(
            _make_items(3),
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
            on_progress=lambda n: progress_calls.append(n),
        )

        assert len(results) == 3
        assert progress_calls == [1, 1, 1]


class TestBatchMatchParallel:
    """Tests for parallel batch_match execution."""

    def test_parallel_produces_correct_results(self):
        """Parallel mode should produce same results as sequential."""
        responses = [
            (True, "engine", "Turbo", 0.85),
            (False, None, None, 0.80),
            (True, "brakes", "Brake disc", 0.75),
            (False, "chassis", None, 0.30),  # Below threshold -> REVIEW_NEEDED
        ]
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt", max_concurrent=3)

        matcher = LLMMatcher(config=config)

        call_count = {"n": 0}
        call_lock = threading.Lock()

        def make_thread_client():
            mock = MagicMock()
            mock.set_context = MagicMock(return_value=mock)

            def fake_create(**kwargs):
                with call_lock:
                    idx = call_count["n"]
                    call_count["n"] += 1
                resp = responses[idx % len(responses)]
                is_covered, category, component, confidence = resp
                content = json.dumps({
                    "is_covered": is_covered,
                    "category": category,
                    "matched_component": component,
                    "confidence": confidence,
                    "reasoning": f"Test reasoning {idx}",
                })
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message.content = content
                return response

            mock.chat_completions_create = MagicMock(side_effect=fake_create)
            return mock

        matcher._create_thread_client = make_thread_client
        matcher._client = MagicMock()

        items = _make_items(4)
        results = matcher.batch_match(
            items,
            covered_categories=["engine", "brakes", "chassis"],
            covered_components={"engine": ["Turbo"], "brakes": ["Brake disc"]},
            claim_id="CLM-002",
        )

        assert len(results) == 4
        assert matcher.get_llm_call_count() == 4

    def test_parallel_preserves_order(self):
        """Results should be in the same order as input items."""
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt", max_concurrent=4)
        matcher = LLMMatcher(config=config)

        def make_thread_client():
            import re as re_mod
            import time as time_mod
            mock = MagicMock()
            mock.set_context = MagicMock(return_value=mock)

            def fake_create(**kwargs):
                messages = kwargs.get("messages", [])
                user_msg = messages[-1]["content"] if messages else ""
                match = re_mod.search(r"Test Part (\d+)", user_msg)
                item_num = int(match.group(1)) if match else 0

                # Vary sleep to create out-of-order completion
                time_mod.sleep(0.01 * (5 - item_num % 5))

                content = json.dumps({
                    "is_covered": True,
                    "category": "engine",
                    "matched_component": f"Component_{item_num}",
                    "confidence": 0.80,
                    "reasoning": f"Part {item_num}",
                })
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message.content = content
                return response

            mock.chat_completions_create = MagicMock(side_effect=fake_create)
            return mock

        matcher._create_thread_client = make_thread_client
        matcher._client = MagicMock()

        items = _make_items(5)
        results = matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Component_0", "Component_1", "Component_2", "Component_3", "Component_4"]},
        )

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.item_code == f"P{i:03d}", f"Item {i} out of order: {result.item_code}"
            assert result.description == f"Test Part {i}"

    def test_parallel_call_count_thread_safe(self):
        """Call count should be exact even with concurrent increments."""
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt", max_concurrent=5)
        matcher = LLMMatcher(config=config)

        matcher._create_thread_client = _make_success_thread_client
        matcher._client = MagicMock()

        items = _make_items(10)
        results = matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert len(results) == 10
        assert matcher.get_llm_call_count() == 10

    def test_parallel_progress_callback(self):
        """Progress callback should be called exactly once per item."""
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt", max_concurrent=3)
        matcher = LLMMatcher(config=config)

        matcher._create_thread_client = _make_success_thread_client
        matcher._client = MagicMock()

        progress_lock = threading.Lock()
        progress_calls = []

        def on_progress(n):
            with progress_lock:
                progress_calls.append(n)

        results = matcher.batch_match(
            _make_items(5),
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
            on_progress=on_progress,
        )

        assert len(results) == 5
        assert len(progress_calls) == 5
        assert all(c == 1 for c in progress_calls)

    def test_parallel_handles_item_failure_gracefully(self):
        """If one item's LLM call raises on all retries, it should become REVIEW_NEEDED."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_concurrent=3,
            max_retries=1,  # No retries — fail immediately
        )
        matcher = LLMMatcher(config=config)

        def make_thread_client():
            mock = MagicMock()
            mock.set_context = MagicMock(return_value=mock)

            def fake_create(**kwargs):
                messages = kwargs.get("messages", [])
                user_msg = messages[-1]["content"] if messages else ""

                if "FAIL_ME" in user_msg:
                    raise RuntimeError("API timeout")

                content = json.dumps({
                    "is_covered": True,
                    "category": "engine",
                    "matched_component": "Turbo",
                    "confidence": 0.85,
                    "reasoning": "test",
                })
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message.content = content
                return response

            mock.chat_completions_create = MagicMock(side_effect=fake_create)
            return mock

        matcher._create_thread_client = make_thread_client
        matcher._client = MagicMock()

        items = [
            {"item_code": "P000", "description": "Test Part 0", "item_type": "parts", "total_price": 100.0},
            {"item_code": "P001", "description": "FAIL_ME item", "item_type": "parts", "total_price": 101.0},
            {"item_code": "P002", "description": "Test Part 2", "item_type": "parts", "total_price": 102.0},
        ]
        results = matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert len(results) == 3
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.REVIEW_NEEDED
        assert "failed" in results[1].match_reasoning.lower()
        assert results[2].coverage_status == CoverageStatus.COVERED

    def test_parallel_each_thread_gets_own_client(self):
        """Each worker thread should receive a distinct client instance."""
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt", max_concurrent=3)
        matcher = LLMMatcher(config=config)

        clients_seen = []
        clients_lock = threading.Lock()

        def tracking_create_thread_client():
            mock = MagicMock()
            mock.set_context = MagicMock(return_value=mock)

            def fake_create(**kwargs):
                with clients_lock:
                    clients_seen.append(id(mock))
                content = json.dumps({
                    "is_covered": True,
                    "category": "engine",
                    "matched_component": "Turbo",
                    "confidence": 0.85,
                    "reasoning": "test",
                })
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message.content = content
                return response

            mock.chat_completions_create = MagicMock(side_effect=fake_create)
            return mock

        matcher._create_thread_client = tracking_create_thread_client
        matcher._client = MagicMock()

        items = _make_items(4)
        matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert len(clients_seen) == 4
        assert len(set(clients_seen)) == 4, "Each thread should get its own client"


class TestRetryLogic:
    """Tests for retry with exponential backoff + jitter."""

    def test_retry_succeeds_on_second_attempt(self):
        """Should succeed if the second attempt works."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_retries=3,
            retry_base_delay=0.0,  # No actual sleep in tests
        )
        call_count = {"n": 0}

        client = MagicMock()
        client.set_context = MagicMock(return_value=client)

        def fake_create(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Rate limit exceeded")
            content = json.dumps({
                "is_covered": True,
                "category": "engine",
                "matched_component": "Turbo",
                "confidence": 0.85,
                "reasoning": "Matched",
            })
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = content
            return response

        client.chat_completions_create = MagicMock(side_effect=fake_create)
        matcher = LLMMatcher(config=config, audited_client=client)

        result = matcher.match(
            description="TURBOLADER",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert result.coverage_status == CoverageStatus.COVERED
        assert call_count["n"] == 2
        assert "attempt 2" in result.match_reasoning

    def test_retry_exhausted_returns_review_needed(self):
        """Should return REVIEW_NEEDED after all retries are exhausted."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_retries=2,
            retry_base_delay=0.0,
        )

        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            side_effect=RuntimeError("Rate limit exceeded")
        )
        matcher = LLMMatcher(config=config, audited_client=client)

        result = matcher.match(
            description="TURBOLADER",
            item_type="parts",
            total_price=500.0,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED
        assert result.match_confidence == 0.0
        assert "2 attempts" in result.match_reasoning
        assert result.not_covered_amount == 500.0
        assert client.chat_completions_create.call_count == 2

    def test_retry_marks_retry_on_audit_client(self):
        """Should call mark_retry on the client for audit trail linking."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_retries=3,
            retry_base_delay=0.0,
        )
        call_count = {"n": 0}

        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.get_last_call_id = MagicMock(return_value="llm_abc123")
        client.mark_retry = MagicMock()

        def fake_create(**kwargs):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                raise RuntimeError("Rate limit")
            content = json.dumps({
                "is_covered": True,
                "category": "engine",
                "matched_component": "Turbo",
                "confidence": 0.85,
                "reasoning": "Matched",
            })
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = content
            return response

        client.chat_completions_create = MagicMock(side_effect=fake_create)
        matcher = LLMMatcher(config=config, audited_client=client)

        result = matcher.match(
            description="TURBOLADER",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert result.coverage_status == CoverageStatus.COVERED
        # mark_retry should have been called before attempt 2 and attempt 3
        assert client.mark_retry.call_count == 2
        client.mark_retry.assert_called_with("llm_abc123")

    def test_no_retry_when_max_retries_is_one(self):
        """max_retries=1 means single attempt, no retries."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_retries=1,
            retry_base_delay=0.0,
        )

        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            side_effect=RuntimeError("Rate limit")
        )
        matcher = LLMMatcher(config=config, audited_client=client)

        result = matcher.match(
            description="TURBOLADER",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert result.coverage_status == CoverageStatus.REVIEW_NEEDED
        assert client.chat_completions_create.call_count == 1

    @patch("context_builder.coverage.llm_matcher.time.sleep")
    @patch("context_builder.coverage.llm_matcher.random.uniform")
    def test_retry_uses_exponential_backoff_with_jitter(self, mock_uniform, mock_sleep):
        """Verify exponential backoff with jitter is applied between retries."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_retries=3,
            retry_base_delay=1.0,
            retry_max_delay=15.0,
        )

        # random.uniform returns a fixed value for predictability
        mock_uniform.side_effect = [0.5, 1.2]

        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            side_effect=RuntimeError("Rate limit")
        )
        matcher = LLMMatcher(config=config, audited_client=client)

        matcher.match(
            description="TURBOLADER",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        # 3 attempts, 2 sleeps between them
        assert mock_sleep.call_count == 2
        # First sleep: uniform(0, 1.0 * 2^0) = uniform(0, 1.0) -> 0.5
        mock_sleep.assert_any_call(0.5)
        # Second sleep: uniform(0, 1.0 * 2^1) = uniform(0, 2.0) -> 1.2
        mock_sleep.assert_any_call(1.2)
        # Verify uniform was called with correct ranges
        mock_uniform.assert_any_call(0, 1.0)   # base * 2^0
        mock_uniform.assert_any_call(0, 2.0)   # base * 2^1

    @patch("context_builder.coverage.llm_matcher.time.sleep")
    @patch("context_builder.coverage.llm_matcher.random.uniform")
    def test_retry_delay_capped_at_max(self, mock_uniform, mock_sleep):
        """Backoff delay should be capped at retry_max_delay."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_retries=5,
            retry_base_delay=10.0,
            retry_max_delay=15.0,
        )
        mock_uniform.side_effect = [5.0, 10.0, 7.5, 12.0]

        client = MagicMock()
        client.set_context = MagicMock(return_value=client)
        client.chat_completions_create = MagicMock(
            side_effect=RuntimeError("Rate limit")
        )
        matcher = LLMMatcher(config=config, audited_client=client)

        matcher.match(
            description="TURBOLADER",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        # 5 attempts = 4 sleeps
        assert mock_sleep.call_count == 4
        # Verify uniform upper bounds are capped:
        # attempt 0: min(10 * 2^0, 15) = 10
        # attempt 1: min(10 * 2^1, 15) = 15  (capped)
        # attempt 2: min(10 * 2^2, 15) = 15  (capped)
        # attempt 3: min(10 * 2^3, 15) = 15  (capped)
        mock_uniform.assert_any_call(0, 10.0)
        mock_uniform.assert_any_call(0, 15.0)

    def test_retry_in_parallel_mode(self):
        """Retry should work correctly when running in parallel threads."""
        config = LLMMatcherConfig(
            prompt_name="nonexistent_prompt",
            max_concurrent=3,
            max_retries=2,
            retry_base_delay=0.0,
        )
        matcher = LLMMatcher(config=config)

        attempt_counts = {}
        attempt_lock = threading.Lock()

        def make_thread_client():
            mock = MagicMock()
            mock.set_context = MagicMock(return_value=mock)

            def fake_create(**kwargs):
                messages = kwargs.get("messages", [])
                user_msg = messages[-1]["content"] if messages else ""

                with attempt_lock:
                    attempt_counts[user_msg] = attempt_counts.get(user_msg, 0) + 1
                    count = attempt_counts[user_msg]

                # RETRY_ME item fails on first attempt, succeeds on second
                if "RETRY_ME" in user_msg and count == 1:
                    raise RuntimeError("Rate limit")

                content = json.dumps({
                    "is_covered": True,
                    "category": "engine",
                    "matched_component": "Turbo",
                    "confidence": 0.85,
                    "reasoning": "test",
                })
                response = MagicMock()
                response.choices = [MagicMock()]
                response.choices[0].message.content = content
                return response

            mock.chat_completions_create = MagicMock(side_effect=fake_create)
            return mock

        matcher._create_thread_client = make_thread_client
        matcher._client = MagicMock()

        items = [
            {"item_code": "P000", "description": "Test Part 0", "item_type": "parts", "total_price": 100.0},
            {"item_code": "P001", "description": "RETRY_ME item", "item_type": "parts", "total_price": 101.0},
            {"item_code": "P002", "description": "Test Part 2", "item_type": "parts", "total_price": 102.0},
        ]
        results = matcher.batch_match(
            items,
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert len(results) == 3
        # All should succeed (RETRY_ME succeeds on retry)
        assert results[0].coverage_status == CoverageStatus.COVERED
        assert results[1].coverage_status == CoverageStatus.COVERED
        assert "attempt 2" in results[1].match_reasoning
        assert results[2].coverage_status == CoverageStatus.COVERED


class TestMatchSingle:
    """Tests for the extracted _match_single method."""

    def test_match_delegates_to_match_single(self):
        """match() should delegate to _match_single and increment call count."""
        config = LLMMatcherConfig(prompt_name="nonexistent_prompt")
        client = _make_mock_client([(True, "engine", "Turbo", 0.85)])
        matcher = LLMMatcher(config=config, audited_client=client)

        result = matcher.match(
            description="TURBOLADER",
            item_type="parts",
            covered_categories=["engine"],
            covered_components={"engine": ["Turbo"]},
        )

        assert result.coverage_status == CoverageStatus.COVERED
        assert matcher.get_llm_call_count() == 1


class TestAnalyzerConfigConcurrency:
    """Tests for AnalyzerConfig.llm_max_concurrent."""

    def test_default_llm_max_concurrent(self):
        from context_builder.coverage.analyzer import AnalyzerConfig
        config = AnalyzerConfig()
        assert config.llm_max_concurrent == 3

    def test_from_dict_llm_max_concurrent(self):
        from context_builder.coverage.analyzer import AnalyzerConfig
        config = AnalyzerConfig.from_dict({"llm_max_concurrent": 5})
        assert config.llm_max_concurrent == 5

    def test_from_dict_default_llm_max_concurrent(self):
        from context_builder.coverage.analyzer import AnalyzerConfig
        config = AnalyzerConfig.from_dict({})
        assert config.llm_max_concurrent == 3
