"""Pipeline stage protocol and runner."""

from __future__ import annotations

from typing import Generic, List, Protocol, TypeVar

T = TypeVar("T")


class Stage(Protocol[T]):
    """Protocol for pipeline stages."""

    name: str

    def run(self, context: T) -> T:
        """Execute stage logic and return updated context."""


class PipelineRunner(Generic[T]):
    """Runs an ordered list of stages with early exit on skip/error."""

    def __init__(self, stages: List[Stage[T]]) -> None:
        self.stages = stages

    def run(self, context: T) -> T:
        for stage in self.stages:
            context = stage.run(context)
            if getattr(context, "status", None) in ("skipped", "error"):
                break
        return context
