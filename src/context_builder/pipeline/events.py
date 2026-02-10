"""Typed pipeline events — single source of truth for the progress contract.

Every pipeline progress notification flows through PipelineEvent. Frozen
dataclasses are immutable, so a thread producing events can never corrupt
state read by the consumer thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol


class EventType(str, Enum):
    """All event types emitted during document processing."""

    DOC_STAGE_START = "doc_stage_start"
    DOC_STAGE_END = "doc_stage_end"
    DOC_COMPLETE = "doc_complete"
    DOC_FAILED = "doc_failed"
    CLAIM_COMPLETE = "claim_complete"


@dataclass(frozen=True)
class PipelineEvent:
    """Immutable event emitted by the pipeline.

    A single dataclass = a single contract.  Impossible to get a
    signature mismatch between producer and consumer.
    """

    event_type: EventType
    claim_id: str
    doc_id: str
    filename: str
    stage: str = ""              # "ingestion", "classification", "extraction"
    status: str = ""             # "success", "error", "skipped"
    error: Optional[str] = None
    time_ms: int = 0
    doc_type: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Serialize to a plain dict (for JSON/WebSocket)."""
        return {
            "event_type": self.event_type.value,
            "claim_id": self.claim_id,
            "doc_id": self.doc_id,
            "filename": self.filename,
            "stage": self.stage,
            "status": self.status,
            "error": self.error,
            "time_ms": self.time_ms,
            "doc_type": self.doc_type,
            "timestamp": self.timestamp,
        }


class PipelineEventHandler(Protocol):
    """Protocol for anything that consumes pipeline events."""

    def handle(self, event: PipelineEvent) -> None: ...
