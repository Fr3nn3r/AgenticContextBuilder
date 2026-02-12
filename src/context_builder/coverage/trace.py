"""Trace builder for coverage decision pipeline.

Accumulates TraceStep records as a line item flows through the
coverage analysis pipeline stages.
"""

from typing import Any, Dict, List, Optional

from context_builder.coverage.schemas import (
    CoverageStatus,
    DecisionSource,
    TraceAction,
    TraceStep,
)


class TraceBuilder:
    """Accumulates trace steps for a single line item."""

    def __init__(self) -> None:
        self._steps: List[TraceStep] = []

    def add(
        self,
        stage: str,
        action: TraceAction,
        reasoning: str,
        verdict: Optional[CoverageStatus] = None,
        confidence: Optional[float] = None,
        detail: Optional[Dict[str, Any]] = None,
        decision_source: Optional[DecisionSource] = None,
    ) -> "TraceBuilder":
        """Append a trace step."""
        self._steps.append(
            TraceStep(
                stage=stage,
                action=action,
                reasoning=reasoning,
                verdict=verdict,
                confidence=confidence,
                detail=detail,
                decision_source=decision_source,
            )
        )
        return self

    def extend(self, steps: Optional[List[TraceStep]]) -> "TraceBuilder":
        """Merge steps from another trace (e.g. combining across stages)."""
        if steps:
            self._steps.extend(steps)
        return self

    def build(self) -> List[TraceStep]:
        """Return the accumulated trace steps."""
        return list(self._steps)
