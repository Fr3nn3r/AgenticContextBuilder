"""Claim assessment service - orchestrates reconciliation and assessment.

This service combines reconciliation and assessment into a single operation,
producing a claim decision. It is the backend for the `assess` CLI command.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from context_builder import get_version
from context_builder.api.services.aggregation import AggregationService
from context_builder.api.services.reconciliation import ReconciliationService
from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.pipeline.claim_stages.enrichment import EnrichmentStage
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
            run_context: Optional ClaimRunContext with shared ID and metadata.

        Returns:
            ClaimAssessmentResult with decision, payout, reconciliation report, etc.
        """
        logger.info(f"Starting assessment for claim {claim_id}")

        # Step 1: Run reconciliation
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

        # Step 2b: Run enrichment stage (coverage lookups, shop authorization, etc.)
        enrichment_context = ClaimContext(
            claim_id=claim_id,
            workspace_path=self.storage.output_root,
            run_id=claim_run_id,
            aggregated_facts=claim_facts_data,
        )

        try:
            enrichment_stage = EnrichmentStage()
            enrichment_context = enrichment_stage.run(enrichment_context)
            claim_facts_data = enrichment_context.aggregated_facts
            logger.info(f"Enrichment complete for {claim_id}")

            # Write enriched facts to separate file (preserves raw claim_facts.json)
            claim_run_storage.write_to_claim_run(
                claim_run_id,
                "claim_facts_enriched.json",
                claim_facts_data,
            )
            logger.info(f"Wrote claim_facts_enriched.json to claim_run {claim_run_id}")

        except Exception as e:
            logger.warning(f"Enrichment failed for {claim_id}: {e}, continuing with unenriched facts")
            # Enrichment failure is non-fatal - continue with unenriched facts

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
            on_token_update=on_token_update,
        )

        try:
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

        # Step 6: Update manifest with stages_completed
        try:
            manifest = claim_run_storage.read_manifest(claim_run_id)
            if manifest:
                if "reconciliation" not in manifest.stages_completed:
                    manifest.stages_completed.append("reconciliation")
                if "enrichment" not in manifest.stages_completed:
                    manifest.stages_completed.append("enrichment")
                if "assessment" not in manifest.stages_completed:
                    manifest.stages_completed.append("assessment")
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
            f"decision={assessment_response.decision}, "
            f"confidence={assessment_response.confidence_score}"
        )

        return ClaimAssessmentResult(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            success=True,
            reconciliation=reconcile_result.report,
            assessment=assessment_response,
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
