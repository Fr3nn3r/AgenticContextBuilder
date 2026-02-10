"""Shared assessment runner service.

Extracted from claims.py so both the claims router (manual trigger) and
the pipeline service (auto-trigger) can run assessments with different
broadcast callbacks.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class AssessmentRunnerService:
    """Runs the claim assessment pipeline (reconcile -> enrich -> screen -> process -> decide)."""

    async def run_assessment(
        self,
        claim_id: str,
        run_id: str,
        workspace_path: Path,
        processing_type: str = "assessment",
        on_stage_update: Optional[Callable] = None,
        on_token_update: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run the full assessment pipeline for a single claim.

        Args:
            claim_id: Claim to assess.
            run_id: Assessment run ID for tracking.
            workspace_path: Workspace root directory.
            processing_type: Type of processing (default "assessment").
            on_stage_update: Callback(stage_name, status) for stage progress.
            on_token_update: Callback(input_tokens, output_tokens) for token usage.
            on_complete: Callback(decision, assessment_id, claim_id) on success.
            on_error: Callback(error_message, claim_id) on failure.

        Returns:
            Saved assessment dict on success, None on failure.
        """
        from context_builder.pipeline.claim_stages import (
            ClaimContext,
            ClaimPipelineRunner,
            ClaimStageConfig,
            ConfidenceStage,
            DecisionStage,
            EnrichmentStage,
            ProcessingStage,
            ReconciliationStage,
            ScreeningStage,
            get_processor,
        )
        from context_builder.api.dependencies import get_assessment_service

        loop = asyncio.get_event_loop()

        # Wrap async callbacks for sync pipeline
        def sync_token_callback(input_tokens: int, output_tokens: int) -> None:
            if on_token_update:
                asyncio.run_coroutine_threadsafe(
                    _maybe_await(on_token_update, input_tokens, output_tokens), loop
                )

        def sync_stage_callback(stage_name: str, status: str) -> None:
            if on_stage_update:
                asyncio.run_coroutine_threadsafe(
                    _maybe_await(on_stage_update, stage_name, status), loop
                )

        context = ClaimContext(
            claim_id=claim_id,
            workspace_path=workspace_path,
            run_id=run_id,
            stage_config=ClaimStageConfig(
                run_reconciliation=True,
                run_processing=True,
                processing_type=processing_type,
            ),
            processing_type=processing_type,
            on_token_update=sync_token_callback,
            on_stage_update=sync_stage_callback,
        )

        try:
            processor = get_processor(processing_type)
            if processor is None:
                raise ValueError(f"No processor registered for type: {processing_type}")

            stages = [
                ReconciliationStage(),
                EnrichmentStage(),
                ScreeningStage(),
                ProcessingStage(),
                DecisionStage(),
                ConfidenceStage(),
            ]
            runner = ClaimPipelineRunner(stages)
            context = runner.run(context)

            if context.status == "success" and context.processing_result:
                assessment_service = get_assessment_service()
                saved = assessment_service.save_assessment(
                    claim_id=claim_id,
                    assessment_data=context.processing_result,
                    prompt_version=context.prompt_version,
                    extraction_bundle_id=context.extraction_bundle_id,
                )

                if on_complete:
                    await _maybe_await(
                        on_complete,
                        context.processing_result.get("decision"),
                        saved.get("id"),
                        claim_id,
                    )
                return saved
            else:
                error_msg = context.error or "Unknown error"
                if on_error:
                    await _maybe_await(on_error, error_msg, claim_id)
                return None

        except Exception as e:
            logger.exception(f"Assessment failed for claim {claim_id}")
            if on_error:
                await _maybe_await(on_error, str(e), claim_id)
            return None


async def _maybe_await(fn: Callable, *args: Any) -> Any:
    """Call fn with args, awaiting if the result is a coroutine."""
    result = fn(*args)
    if asyncio.iscoroutine(result):
        return await result
    return result
