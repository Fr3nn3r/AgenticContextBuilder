"""Tests for pipeline events and EventCollector (Phase 1)."""

import threading
import time
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from context_builder.pipeline.events import EventType, PipelineEvent, PipelineEventHandler
from context_builder.pipeline.event_collector import EventCollector


# ---------------------------------------------------------------------------
# PipelineEvent
# ---------------------------------------------------------------------------

class TestPipelineEvent:
    """Tests for the PipelineEvent dataclass."""

    def test_create_event(self):
        """Events can be created with required fields."""
        event = PipelineEvent(
            event_type=EventType.DOC_STAGE_START,
            claim_id="CLM-001",
            doc_id="doc_1",
            filename="report.pdf",
            stage="ingestion",
        )
        assert event.event_type == EventType.DOC_STAGE_START
        assert event.claim_id == "CLM-001"
        assert event.doc_id == "doc_1"
        assert event.filename == "report.pdf"
        assert event.stage == "ingestion"

    def test_frozen_immutability(self):
        """Events are immutable (frozen dataclass)."""
        event = PipelineEvent(
            event_type=EventType.DOC_COMPLETE,
            claim_id="CLM-001",
            doc_id="doc_1",
            filename="report.pdf",
        )
        with pytest.raises(FrozenInstanceError):
            event.claim_id = "CLM-002"

    def test_timestamp_auto_generated(self):
        """Timestamp is auto-populated on creation."""
        event = PipelineEvent(
            event_type=EventType.DOC_COMPLETE,
            claim_id="CLM-001",
            doc_id="doc_1",
            filename="report.pdf",
        )
        assert event.timestamp  # non-empty string
        assert "T" in event.timestamp  # ISO format

    def test_to_dict_serialization(self):
        """to_dict() produces a plain dict for JSON serialization."""
        event = PipelineEvent(
            event_type=EventType.DOC_STAGE_END,
            claim_id="CLM-001",
            doc_id="doc_1",
            filename="report.pdf",
            stage="classification",
            status="success",
            time_ms=1234,
            doc_type="invoice",
        )
        d = event.to_dict()
        assert d["event_type"] == "doc_stage_end"
        assert d["stage"] == "classification"
        assert d["status"] == "success"
        assert d["time_ms"] == 1234
        assert d["doc_type"] == "invoice"

    def test_defaults(self):
        """Optional fields default to empty/None."""
        event = PipelineEvent(
            event_type=EventType.DOC_COMPLETE,
            claim_id="CLM-001",
            doc_id="doc_1",
            filename="report.pdf",
        )
        assert event.stage == ""
        assert event.status == ""
        assert event.error is None
        assert event.time_ms == 0
        assert event.doc_type is None


class TestEventType:
    """Tests for the EventType enum."""

    def test_all_values(self):
        assert EventType.DOC_STAGE_START.value == "doc_stage_start"
        assert EventType.DOC_STAGE_END.value == "doc_stage_end"
        assert EventType.DOC_COMPLETE.value == "doc_complete"
        assert EventType.DOC_FAILED.value == "doc_failed"
        assert EventType.CLAIM_COMPLETE.value == "claim_complete"

    def test_is_str_enum(self):
        """EventType values can be used as strings directly."""
        assert EventType.DOC_COMPLETE == "doc_complete"


# ---------------------------------------------------------------------------
# EventCollector
# ---------------------------------------------------------------------------

class TestEventCollector:
    """Tests for the thread-safe EventCollector."""

    def _make_event(self, event_type=EventType.DOC_STAGE_START, **kwargs):
        defaults = dict(
            claim_id="CLM-001", doc_id="doc_1", filename="test.pdf"
        )
        defaults.update(kwargs)
        return PipelineEvent(event_type=event_type, **defaults)

    def test_emit_and_drain(self):
        """emit() enqueues; drain() collects."""
        collector = EventCollector()
        event = self._make_event()
        collector.emit(event)

        drained = collector.drain()
        assert len(drained) == 1
        assert drained[0] is event

    def test_drain_empty(self):
        """drain() returns [] when nothing is queued."""
        collector = EventCollector()
        assert collector.drain() == []

    def test_multiple_events(self):
        """Multiple emits are drained in order."""
        collector = EventCollector()
        e1 = self._make_event(doc_id="doc_1")
        e2 = self._make_event(doc_id="doc_2")
        e3 = self._make_event(doc_id="doc_3")
        collector.emit(e1)
        collector.emit(e2)
        collector.emit(e3)

        drained = collector.drain()
        assert [e.doc_id for e in drained] == ["doc_1", "doc_2", "doc_3"]

    def test_all_events_property(self):
        """all_events accumulates across multiple drains."""
        collector = EventCollector()
        collector.emit(self._make_event(doc_id="doc_1"))
        collector.drain()
        collector.emit(self._make_event(doc_id="doc_2"))
        collector.drain()

        assert len(collector.all_events) == 2
        assert collector.all_events[0].doc_id == "doc_1"
        assert collector.all_events[1].doc_id == "doc_2"

    def test_close_prevents_further_emits(self):
        """emit() after close() logs a warning and drops the event."""
        collector = EventCollector()
        collector.close()
        assert collector.closed

        collector.emit(self._make_event())
        drained = collector.drain()
        # The sentinel may be consumed but no real events
        assert len([e for e in drained if isinstance(e, PipelineEvent)]) == 0

    def test_handler_called_on_drain(self):
        """Handlers receive events during drain()."""
        handler = MagicMock(spec=PipelineEventHandler)
        collector = EventCollector(handlers=[handler])

        event = self._make_event()
        collector.emit(event)
        collector.drain()

        handler.handle.assert_called_once_with(event)

    def test_multiple_handlers(self):
        """All registered handlers are called."""
        h1 = MagicMock(spec=PipelineEventHandler)
        h2 = MagicMock(spec=PipelineEventHandler)
        collector = EventCollector(handlers=[h1, h2])

        collector.emit(self._make_event())
        collector.drain()

        h1.handle.assert_called_once()
        h2.handle.assert_called_once()

    def test_fail_on_error_propagates(self):
        """With fail_on_error=True, handler exceptions propagate."""
        handler = MagicMock(spec=PipelineEventHandler)
        handler.handle.side_effect = ValueError("boom")
        collector = EventCollector(handlers=[handler], fail_on_error=True)

        collector.emit(self._make_event())
        with pytest.raises(ValueError, match="boom"):
            collector.drain()

    def test_fail_on_error_false_logs_warning(self):
        """With fail_on_error=False (default), handler errors are logged, not raised."""
        handler = MagicMock(spec=PipelineEventHandler)
        handler.handle.side_effect = ValueError("boom")
        collector = EventCollector(handlers=[handler], fail_on_error=False)

        collector.emit(self._make_event())
        # Should not raise
        drained = collector.drain()
        assert len(drained) == 1

    def test_thread_safety_multiple_producers(self):
        """Multiple threads emitting events concurrently is safe."""
        collector = EventCollector()
        errors = []
        n_threads = 4
        events_per_thread = 50

        def producer(thread_id):
            try:
                for i in range(events_per_thread):
                    collector.emit(self._make_event(doc_id=f"t{thread_id}_d{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=producer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

        # Drain all events
        drained = collector.drain()
        assert len(drained) == n_threads * events_per_thread


# ---------------------------------------------------------------------------
# PipelineRunner with fail_on_callback_error
# ---------------------------------------------------------------------------

class TestPipelineRunnerCallbackError:
    """Tests for PipelineRunner's callback error handling."""

    def test_broken_start_callback_logged_not_raised(self):
        """By default, broken start callbacks are logged but don't break the pipeline."""
        from context_builder.pipeline.stages import PipelineRunner

        class FakeStage:
            name = "test_stage"
            def run(self, ctx):
                return ctx

        def broken_start(name, ctx):
            raise RuntimeError("broken start")

        runner = PipelineRunner(
            stages=[FakeStage()],
            on_phase_start=broken_start,
        )
        # Should NOT raise
        result = runner.run({"key": "value"})
        assert result == {"key": "value"}

    def test_broken_end_callback_logged_not_raised(self):
        """By default, broken end callbacks are logged but don't break the pipeline."""
        from context_builder.pipeline.stages import PipelineRunner

        class FakeStage:
            name = "test_stage"
            def run(self, ctx):
                return ctx

        def broken_end(name, ctx, status):
            raise RuntimeError("broken end")

        runner = PipelineRunner(
            stages=[FakeStage()],
            on_phase_end=broken_end,
        )
        result = runner.run({"key": "value"})
        assert result == {"key": "value"}

    def test_fail_on_callback_error_start(self):
        """With fail_on_callback_error=True, broken start callback raises."""
        from context_builder.pipeline.stages import PipelineRunner

        class FakeStage:
            name = "test_stage"
            def run(self, ctx):
                return ctx

        def broken_start(name, ctx):
            raise RuntimeError("broken start")

        runner = PipelineRunner(
            stages=[FakeStage()],
            on_phase_start=broken_start,
            fail_on_callback_error=True,
        )
        with pytest.raises(RuntimeError, match="broken start"):
            runner.run({})

    def test_fail_on_callback_error_end(self):
        """With fail_on_callback_error=True, broken end callback raises."""
        from context_builder.pipeline.stages import PipelineRunner

        class FakeStage:
            name = "test_stage"
            def run(self, ctx):
                return ctx

        def broken_end(name, ctx, status):
            raise RuntimeError("broken end")

        runner = PipelineRunner(
            stages=[FakeStage()],
            on_phase_end=broken_end,
            fail_on_callback_error=True,
        )
        with pytest.raises(RuntimeError, match="broken end"):
            runner.run({})
