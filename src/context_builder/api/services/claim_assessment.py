"""Claim assessment service - orchestrates reconciliation and assessment.

This service combines reconciliation and assessment into a single operation,
producing a claim decision. It is the backend for the `assess` CLI command.

Pipeline stages (all non-fatal except reconciliation and assessment):
1. Reconciliation - aggregates facts, detects conflicts, quality gate
2. Screening - deterministic checks (auto-reject, payout calc)
3. Assessment - LLM-based claim assessment
4. Decision - decision dossier (denial clause evaluation)
5. Confidence - Composite Confidence Index (CCI)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from context_builder import get_version
from context_builder.api.services.aggregation import AggregationService
from context_builder.api.services.reconciliation import ReconciliationService
from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.pipeline.claim_stages.screening import ScreeningStage
from context_builder.pipeline.claim_stages.decision import DecisionStage
from context_builder.confidence.stage import ConfidenceStage
from context_builder.pipeline.claim_stages.processing import (
    ProcessingStage,
    ProcessorConfig,
    get_processor,
)
from context_builder.schemas.assessment_response import AssessmentResponse
from context_builder.schemas.claim_assessment import ClaimAssessmentResult
from context_builder.storage.claim_run import ClaimRunStorage
from context_builder.storage.filesystem import FileStorage

logger = logging.getLogger(__name__)


class ClaimAssessmentService:
    """Service for running full claim assessment (reconcile + assess).

    This service orchestrates:
    1. Reconciliation - aggregates facts, detects conflicts, evaluates quality gate
    2. Assessment - runs checks, calculates payout, produces decision

    Output is written to the claim_run directory with both stages tracked
    in the manifest's stages_completed field.
    """

    def __init__(
        self,
        storage: FileStorage,
        reconciliation_service: ReconciliationService,
    ):
        """Initialize the claim assessment service.

        Args:
            storage: FileStorage instance for claim data access.
            reconciliation_service: ReconciliationService for fact aggregation.
        """
        self.storage = storage
        self.reconciliation = reconciliation_service
        self._processing_stage: Optional[ProcessingStage] = None

    def assess(
        self,
        claim_id: str,
        force_reconcile: bool = False,
        on_token_update: Optional[Callable[[int, int], None]] = None,
        on_stage_update: Optional[Callable[[str, str], None]] = None,
        on_llm_start: Optional[Callable[[int], None]] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
        run_context=None,
    ) -> ClaimAssessmentResult:
        """Run full assessment for a claim.

        Steps:
        1. Run reconciliation (creates claim_run, aggregates facts)
        2. Load aggregated facts from claim_run
        3. Load assessment prompt config
        4. Run assessment processor
        5. Save assessment to claim_run
        6. Update manifest with stages_completed

        Args:
            claim_id: Claim to assess.
            force_reconcile: Force re-reconciliation even if recent exists.
            on_token_update: Callback for token usage updates (input, output).
            on_stage_update: Callback for stage status updates (stage_name, status).
            on_llm_start: Callback when LLM batch processing starts (total count).
            on_llm_progress: Callback for LLM progress updates (increment).
            run_context: Optional ClaimRunContext with shared ID and metadata.

        Returns:
            ClaimAssessmentResult with decision, payout, reconciliation report, etc.
        """
        logger.info(f"Starting assessment for claim {claim_id}")

        # Step 1: Run reconciliation
        if on_stage_update:
            try:
                on_stage_update("reconciliation", "running")
            except Exception:
                pass
        reconcile_result = self.reconciliation.reconcile(claim_id, run_context=run_context)
        if not reconcile_result.success:
            logger.error(f"Reconciliation failed for {claim_id}: {reconcile_result.error}")
            return ClaimAssessmentResult(
                claim_id=claim_id,
                success=False,
                error=f"Reconciliation failed: {reconcile_result.error}",
            )

        claim_run_id = reconcile_result.report.claim_run_id
        logger.info(f"Reconciliation complete for {claim_id}, claim_run={claim_run_id}")

        # Step 2: Load claim facts from claim_run
        claim_folder = self.storage._find_claim_folder(claim_id)
        if not claim_folder:
            return ClaimAssessmentResult(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                success=False,
                error=f"Claim folder not found: {claim_id}",
                reconciliation=reconcile_result.report,
            )

        claim_run_storage = ClaimRunStorage(claim_folder)
        claim_facts_data = claim_run_storage.read_claim_facts(claim_run_id)
        if not claim_facts_data:
            return ClaimAssessmentResult(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                success=False,
                error="No claim facts found after reconciliation",
                reconciliation=reconcile_result.report,
            )

        # Step 2b: Run screening stage (deterministic checks before LLM)
        # NOTE: Enrichment stage removed in Phase 6 cleanup.
        # Shop authorization lookup is now handled by the screening stage.
        screening_result = None
        screening_context = ClaimContext(
            claim_id=claim_id,
            workspace_path=self.storage.output_root,
            run_id=claim_run_id,
            aggregated_facts=claim_facts_data,
            reconciliation_report=reconcile_result.report,
            on_stage_update=on_stage_update,
            on_llm_start=on_llm_start,
            on_llm_progress=on_llm_progress,
        )

        try:
            screening_stage = ScreeningStage()
            screening_context = screening_stage.run(screening_context)
            screening_result = screening_context.screening_result
            logger.info(
                f"Screening complete for {claim_id}"
                + (f" (auto_reject={screening_result.get('auto_reject')})"
                   if screening_result else " (no screener configured)")
            )
        except Exception as e:
            logger.warning(
                f"Screening failed for {claim_id}: {e}, continuing without screening"
            )
            screening_result = None

        # Step 3: Load assessment prompt config
        try:
            processor_config = self._load_assessment_config()
        except Exception as e:
            logger.error(f"Failed to load assessment config: {e}")
            return ClaimAssessmentResult(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                success=False,
                error=f"Failed to load assessment config: {e}",
                reconciliation=reconcile_result.report,
            )

        # Step 4: Build context and run assessment
        context = ClaimContext(
            claim_id=claim_id,
            workspace_path=self.storage.output_root,
            run_id=claim_run_id,
            aggregated_facts=claim_facts_data,
            screening_result=screening_result,
            on_token_update=on_token_update,
            on_stage_update=on_stage_update,
            on_llm_start=on_llm_start,
            on_llm_progress=on_llm_progress,
        )

        try:
            if on_stage_update:
                try:
                    on_stage_update("assessment", "running")
                except Exception:
                    pass

            # Get assessment processor
            processor = get_processor("assessment")
            if not processor:
                # Import to trigger auto-registration
                from context_builder.pipeline.claim_stages import assessment_processor  # noqa: F401
                processor = get_processor("assessment")

            if not processor:
                raise ValueError("Assessment processor not found")

            assessment_result = processor.process(
                context=context,
                config=processor_config,
                on_token_update=on_token_update,
            )

            # Parse into AssessmentResponse model
            assessment_response = AssessmentResponse.model_validate(assessment_result)

            if on_stage_update:
                try:
                    on_stage_update("assessment", "complete")
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Assessment failed for {claim_id}: {e}")
            return ClaimAssessmentResult(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                success=False,
                error=f"Assessment failed: {e}",
                reconciliation=reconcile_result.report,
            )

        # Step 5: Save assessment to claim_run
        try:
            claim_run_storage.write_assessment(
                claim_run_id,
                assessment_response.model_dump(mode="json"),
            )
            logger.info(f"Wrote assessment.json to claim_run {claim_run_id}")
        except Exception as e:
            logger.error(f"Failed to write assessment: {e}", exc_info=True)
            return ClaimAssessmentResult(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                success=False,
                error=f"Assessment completed but file write failed: {e}",
                reconciliation=reconcile_result.report,
                assessment=assessment_response,
            )

        # Step 5a: Load coverage overrides from previous run's dossier
        coverage_overrides = self._load_previous_overrides(
            claim_run_storage, claim_run_id
        )

        # Step 5b: Run DecisionStage (non-fatal)
        decision_result = None
        try:
            decision_context = ClaimContext(
                claim_id=claim_id,
                workspace_path=self.storage.output_root,
                run_id=claim_run_id,
                aggregated_facts=claim_facts_data,
                screening_result=screening_result,
                processing_result=assessment_response.model_dump(mode="json"),
                coverage_overrides=coverage_overrides,
                on_stage_update=on_stage_update,
            )
            decision_stage = DecisionStage()
            decision_context = decision_stage.run(decision_context)
            decision_result = decision_context.decision_result
            logger.info(
                f"Decision complete for {claim_id}"
                + (f" (verdict={decision_result.get('claim_verdict')})"
                   if decision_result else " (no result)")
            )
        except Exception as e:
            logger.warning(
                f"Decision stage failed for {claim_id}: {e}, continuing"
            )

        # Step 5c: Run ConfidenceStage (non-fatal)
        confidence_summary_data = None
        try:
            confidence_context = ClaimContext(
                claim_id=claim_id,
                workspace_path=self.storage.output_root,
                run_id=claim_run_id,
                aggregated_facts=claim_facts_data,
                reconciliation_report=(
                    reconcile_result.report.model_dump(mode="json")
                    if reconcile_result.report else None
                ),
                screening_result=screening_result,
                processing_result=assessment_response.model_dump(mode="json"),
                decision_result=decision_result,
                on_stage_update=on_stage_update,
            )
            confidence_stage = ConfidenceStage()
            confidence_context = confidence_stage.run(confidence_context)
            # Read back the persisted summary (stage writes it to disk)
            cs_data = claim_run_storage.read_from_claim_run(
                claim_run_id, "confidence_summary.json"
            )
            if cs_data:
                confidence_summary_data = cs_data
                logger.info(
                    f"Confidence complete for {claim_id}: "
                    f"CCI={cs_data.get('composite_score')}"
                )
        except Exception as e:
            logger.warning(
                f"Confidence stage failed for {claim_id}: {e}, continuing"
            )

        # Step 6: Update manifest with stages_completed
        try:
            manifest = claim_run_storage.read_manifest(claim_run_id)
            if manifest:
                for stage_name in [
                    "reconciliation", "screening", "assessment",
                    "decision", "confidence",
                ]:
                    if stage_name not in manifest.stages_completed:
                        manifest.stages_completed.append(stage_name)
                claim_run_storage.write_manifest(manifest)
                logger.info(
                    f"Updated manifest stages_completed: {manifest.stages_completed}"
                )
        except Exception as e:
            logger.error(f"Failed to update manifest: {e}", exc_info=True)
            return ClaimAssessmentResult(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                success=False,
                error=f"Assessment completed but manifest update failed: {e}",
                reconciliation=reconcile_result.report,
                assessment=assessment_response,
            )

        logger.info(
            f"Assessment complete for {claim_id}: "
            f"recommendation={assessment_response.recommendation}, "
            f"confidence={assessment_response.confidence_score}"
        )

        return ClaimAssessmentResult(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            success=True,
            reconciliation=reconcile_result.report,
            assessment=assessment_response,
            decision_dossier=decision_result,
            confidence_summary=confidence_summary_data,
            screening_payout=_extract_screening_payout(screening_result),
        )

    def _load_assessment_config(self) -> ProcessorConfig:
        """Load assessment processor configuration from workspace.

        Looks for config in {workspace}/config/processing/assessment/

        Returns:
            ProcessorConfig with assessment configuration.

        Raises:
            ValueError: If assessment config not found.
        """
        if self._processing_stage is None:
            self._processing_stage = ProcessingStage()

        # Discover processors from workspace
        self._processing_stage._discover_processors(self.storage.output_root)

        config = self._processing_stage._discovered_configs.get("assessment")
        if not config:
            raise ValueError(
                f"Assessment processor config not found in "
                f"{self.storage.output_root / 'config' / 'processing' / 'assessment'}"
            )

        return config

    def _load_previous_overrides(
        self,
        claim_run_storage: ClaimRunStorage,
        current_run_id: str,
    ) -> Optional[Dict[str, bool]]:
        """Load coverage overrides from the previous run's decision dossier.

        Scans claim runs (newest first) for a run that isn't the current one,
        then reads its latest decision_dossier_v*.json and extracts
        ``coverage_overrides``.

        Returns:
            Dict of overrides, or None if none found.
        """
        try:
            all_runs = claim_run_storage.list_claim_runs()
            for run_id in all_runs:
                if run_id == current_run_id:
                    continue
                # Find latest dossier in this run
                run_dir = claim_run_storage.get_claim_run_path(run_id)
                dossier_files = sorted(run_dir.glob("decision_dossier_v*.json"))
                if not dossier_files:
                    continue
                data = claim_run_storage.read_from_claim_run(
                    run_id, dossier_files[-1].name
                )
                if data and data.get("coverage_overrides"):
                    overrides = data["coverage_overrides"]
                    logger.info(
                        f"Loaded {len(overrides)} coverage override(s) "
                        f"from previous run {run_id}"
                    )
                    return overrides
        except Exception as e:
            logger.debug(f"Could not load previous overrides: {e}")
        return None


def _extract_screening_payout(
    screening_result: Optional[Dict[str, Any]],
) -> Optional[float]:
    """Extract final_payout from screening result.

    Returns 0.0 when the screener auto-rejected the claim, because the
    payout breakdown still contains the hypothetical covered-item total
    even on rejection.
    """
    if not screening_result:
        return None
    if screening_result.get("auto_reject"):
        return 0.0
    payout = screening_result.get("payout")
    if isinstance(payout, dict):
        val = payout.get("final_payout")
        return float(val) if val is not None else None
    return None
