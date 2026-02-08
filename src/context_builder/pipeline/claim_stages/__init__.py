"""Claim-level pipeline stages package.

This package contains stages that operate at the claim level (across all documents),
as opposed to the document-level stages in pipeline/stages/.

Pipeline flow:
    Document Pipeline (per doc):  Ingestion -> Classification -> Extraction
    Claim Pipeline (per claim):   Reconciliation -> Enrichment -> Screening -> Processing -> Decision

The claim pipeline runs after all documents have been processed by the document pipeline.

Enrichment stage is optional - workspaces can opt-in by providing an enricher module
at {workspace}/config/enrichment/enricher.py implementing the Enricher protocol.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Protocol

from context_builder.pipeline.claim_stages.context import (
    ClaimContext,
    ClaimProcessingResult,
    ClaimStageConfig,
    ClaimStageTimings,
)
from context_builder.pipeline.claim_stages.reconciliation import ReconciliationStage
from context_builder.pipeline.claim_stages.enrichment import (
    EnrichmentStage,
    Enricher,
    DefaultEnricher,
    load_enricher_from_workspace,
)
from context_builder.pipeline.claim_stages.screening import (
    ScreeningStage,
    Screener,
    DefaultScreener,
    load_screener_from_workspace,
)
from context_builder.pipeline.claim_stages.processing import (
    ProcessingStage,
    ProcessorConfig,
    Processor,
    register_processor,
    get_processor,
)
from context_builder.pipeline.claim_stages.decision import (
    DecisionStage,
    DecisionEngine,
    DefaultDecisionEngine,
    load_engine_from_workspace,
)

# Import assessment processor to auto-register it
import context_builder.pipeline.claim_stages.assessment_processor  # noqa: F401

# Callback type: (stage_name: str, context: ClaimContext) -> None
ClaimPhaseCallback = Callable[[str, ClaimContext], None]

# End callback type: (stage_name: str, context: ClaimContext, status: str) -> None
ClaimPhaseEndCallback = Callable[[str, ClaimContext, str], None]


class ClaimStage(Protocol):
    """Protocol for claim-level pipeline stages.

    Each stage must have a name and implement a run method that takes
    a ClaimContext and returns the updated context.
    """

    name: str

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute stage logic and return updated context."""
        ...


class ClaimPipelineRunner:
    """Runs an ordered list of claim-level stages with early exit on error.

    Similar to PipelineRunner for document stages, but specialized for
    claim-level processing with streaming support.
    """

    def __init__(
        self,
        stages: List[ClaimStage],
        on_phase_start: Optional[ClaimPhaseCallback] = None,
        on_phase_end: Optional[ClaimPhaseEndCallback] = None,
    ) -> None:
        """Initialize the claim pipeline runner.

        Args:
            stages: Ordered list of claim stages to run.
            on_phase_start: Optional callback called when each stage starts.
            on_phase_end: Optional callback called when each stage ends.
        """
        self.stages = stages
        self.on_phase_start = on_phase_start
        self.on_phase_end = on_phase_end

    def run(self, context: ClaimContext) -> ClaimContext:
        """Run all stages in order.

        Args:
            context: The claim context to process.

        Returns:
            Updated claim context after all stages have run.
        """
        context.status = "running"

        for stage in self.stages:
            # Notify phase start
            context.notify_stage_update(stage.name, "running")
            if self.on_phase_start:
                try:
                    self.on_phase_start(stage.name, context)
                except Exception:
                    pass  # Don't let callback errors break the pipeline

            # Run the stage
            context = stage.run(context)
            status = context.status

            # Notify phase end
            if self.on_phase_end:
                try:
                    self.on_phase_end(stage.name, context, status)
                except Exception:
                    pass  # Don't let callback errors break the pipeline

            context.notify_stage_update(stage.name, status)

            # Early exit on error
            if status == "error":
                break

        # Set final status if not already error
        if context.status != "error":
            context.status = "success"

        return context


__all__ = [
    # Context dataclasses
    "ClaimContext",
    "ClaimProcessingResult",
    "ClaimStageConfig",
    "ClaimStageTimings",
    # Protocol and runner
    "ClaimStage",
    "ClaimPipelineRunner",
    # Callback types
    "ClaimPhaseCallback",
    "ClaimPhaseEndCallback",
    # Stage implementations
    "ReconciliationStage",
    "EnrichmentStage",
    "ScreeningStage",
    "ProcessingStage",
    "DecisionStage",
    # Enrichment utilities
    "Enricher",
    "DefaultEnricher",
    "load_enricher_from_workspace",
    # Screening utilities
    "Screener",
    "DefaultScreener",
    "load_screener_from_workspace",
    # Processing utilities
    "ProcessorConfig",
    "Processor",
    "register_processor",
    "get_processor",
    # Decision utilities
    "DecisionEngine",
    "DefaultDecisionEngine",
    "load_engine_from_workspace",
]
