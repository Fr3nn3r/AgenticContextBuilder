"""Thread-safe event collector for pipeline progress.

Bridges sync document-processing threads and the async event loop.
Producers call ``emit()`` from any thread; the consumer calls ``drain()``
from the event loop to collect and dispatch events.
"""

from __future__ import annotations

import logging
import queue
from typing import List, Optional, Sequence

from context_builder.pipeline.events import PipelineEvent, PipelineEventHandler

logger = logging.getLogger(__name__)

_SENTINEL = object()  # signals no more events


class EventCollector:
    """Thread-safe pipeline event bus.

    Parameters
    ----------
    handlers:
        Zero or more handlers that receive every drained event.
    fail_on_error:
        If ``True`` (recommended in tests), handler exceptions propagate
        immediately.  If ``False`` (production default), they are logged
        as warnings — still visible, unlike the old ``except: pass``.
    """

    def __init__(
        self,
        handlers: Optional[Sequence[PipelineEventHandler]] = None,
        fail_on_error: bool = False,
    ) -> None:
        self._queue: queue.Queue[PipelineEvent | object] = queue.Queue()
        self._handlers: List[PipelineEventHandler] = list(handlers or [])
        self._fail_on_error = fail_on_error
        self._closed = False
        self._all_events: List[PipelineEvent] = []  # append-only log

    # -- Producer API (called from any thread) --

    def emit(self, event: PipelineEvent) -> None:
        """Enqueue an event.  Safe to call from any thread."""
        if self._closed:
            logger.warning("emit() called after close(); event dropped: %s", event.event_type)
            return
        self._queue.put(event)

    # -- Consumer API (called from the event-loop thread) --

    def drain(self) -> List[PipelineEvent]:
        """Non-blocking drain: pull all pending events and dispatch to handlers.

        Returns the list of events that were drained (useful for tests).
        """
        events: List[PipelineEvent] = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _SENTINEL:
                break
            assert isinstance(item, PipelineEvent)
            events.append(item)
            self._all_events.append(item)
            self._dispatch(item)
        return events

    # -- Lifecycle --

    def close(self) -> None:
        """Signal that no more events will be produced."""
        self._closed = True
        self._queue.put(_SENTINEL)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def all_events(self) -> List[PipelineEvent]:
        """Read-only view of every event drained so far."""
        return list(self._all_events)

    # -- Internal --

    def _dispatch(self, event: PipelineEvent) -> None:
        for handler in self._handlers:
            try:
                handler.handle(event)
            except Exception as exc:
                if self._fail_on_error:
                    raise
                logger.warning(
                    "Event handler %s failed for %s: %s",
                    type(handler).__name__,
                    event.event_type.value,
                    exc,
                    exc_info=True,
                )
