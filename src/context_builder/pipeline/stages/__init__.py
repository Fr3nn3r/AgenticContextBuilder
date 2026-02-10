"""Pipeline stages package - stage classes, runner, and context dataclasses."""

from __future__ import annotations

import logging
from typing import Callable, Generic, List, Optional, Protocol, TypeVar

logger = logging.getLogger(__name__)

from context_builder.pipeline.stages.context import (
    ClaimResult,
    DocResult,
    DocumentContext,
    IngestionResult,
    PhaseTimings,
    PipelineProviders,
    StageConfig,
)
from context_builder.pipeline.stages.ingestion import IngestionStage
from context_builder.pipeline.stages.classification import ClassificationStage
from context_builder.pipeline.stages.extraction import ExtractionStage

T = TypeVar("T")

# Callback type: (stage_name: str, context: T) -> None
PhaseCallback = Callable[[str, T], None]

# End callback type: (stage_name: str, context: T, status: str) -> None
PhaseEndCallback = Callable[[str, T, str], None]


class Stage(Protocol[T]):
    """Protocol for pipeline stages."""

    name: str

    def run(self, context: T) -> T:
        """Execute stage logic and return updated context."""


class PipelineRunner(Generic[T]):
    """Runs an ordered list of stages with early exit on skip/error."""

    def __init__(
        self,
        stages: List[Stage[T]],
        on_phase_start: Optional[PhaseCallback[T]] = None,
        on_phase_end: Optional[PhaseEndCallback[T]] = None,
        fail_on_callback_error: bool = False,
    ) -> None:
        self.stages = stages
        self.on_phase_start = on_phase_start
        self.on_phase_end = on_phase_end
        self.fail_on_callback_error = fail_on_callback_error

    def run(self, context: T) -> T:
        for stage in self.stages:
            # Notify phase start
            if self.on_phase_start:
                try:
                    self.on_phase_start(stage.name, context)
                except Exception as e:
                    logger.warning("Phase start callback failed for '%s': %s", stage.name, e, exc_info=True)
                    if self.fail_on_callback_error:
                        raise

            context = stage.run(context)
            status = getattr(context, "status", "success")

            # Notify phase end
            if self.on_phase_end:
                try:
                    self.on_phase_end(stage.name, context, status)
                except Exception as e:
                    logger.warning("Phase end callback failed for '%s': %s", stage.name, e, exc_info=True)
                    if self.fail_on_callback_error:
                        raise

            if status in ("skipped", "error"):
                break
        return context


__all__ = [
    # Context dataclasses
    "ClaimResult",
    "DocResult",
    "DocumentContext",
    "IngestionResult",
    "PhaseTimings",
    "PipelineProviders",
    "StageConfig",
    # Stage classes
    "ClassificationStage",
    "ExtractionStage",
    "IngestionStage",
    # Runner
    "PipelineRunner",
    "Stage",
]
