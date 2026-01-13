"""Pipeline stage protocol and runner."""

from __future__ import annotations

from typing import Callable, Generic, List, Optional, Protocol, TypeVar

T = TypeVar("T")

# Callback type: (stage_name: str, context: T) -> None
PhaseCallback = Callable[[str, T], None]


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
    ) -> None:
        self.stages = stages
        self.on_phase_start = on_phase_start

    def run(self, context: T) -> T:
        for stage in self.stages:
            # Notify phase start
            if self.on_phase_start:
                try:
                    self.on_phase_start(stage.name, context)
                except Exception:
                    pass  # Don't let callback errors break the pipeline
            context = stage.run(context)
            if getattr(context, "status", None) in ("skipped", "error"):
                break
        return context
