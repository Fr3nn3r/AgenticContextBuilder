"""Reconciliation stage for claim-level pipeline.

This stage aggregates facts from document extractions across multiple documents,
detects conflicts, evaluates a quality gate, and produces:
- claim_facts.json: Aggregated facts for downstream processing
- reconciliation_report.json: Gate status and conflict details

The stage uses ReconciliationService which:
1. Loads extractions from the latest complete run
2. Aggregates facts with confidence-based selection
3. Detects conflicts (same fact with different values)
4. Evaluates a quality gate (advisory, does not block)
5. Tracks provenance for audit purposes
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from context_builder.api.services.aggregation import AggregationService
from context_builder.api.services.reconciliation import ReconciliationService
from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.storage.filesystem import FileStorage

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationStage:
    """Reconciliation stage: aggregate facts, detect conflicts, evaluate gate.

    This stage produces:
    - claim_facts.json: Aggregated facts for assessment/processing
    - reconciliation_report.json: Gate status, conflicts, critical facts check

    The gate is advisory - even if it fails, downstream processing can continue.
    """

    name: str = "reconciliation"

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute reconciliation and return updated context.

        Args:
            context: The claim context with claim_id and workspace_path.

        Returns:
            Updated context with aggregated_facts and reconciliation_report.
        """
        context.current_stage = self.name
        context.notify_stage_update(self.name, "running")
        start = time.time()

        if not context.stage_config.run_reconciliation:
            logger.info(f"Reconciliation skipped for claim {context.claim_id}")
            context.timings.reconciliation_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        logger.info(f"Running reconciliation for claim {context.claim_id}")

        try:
            # Create services
            storage = FileStorage(context.workspace_path)
            aggregation = AggregationService(storage)
            reconciliation = ReconciliationService(storage, aggregation)

            # Run reconciliation (aggregates facts, detects conflicts, evaluates gate)
            result = reconciliation.reconcile(
                claim_id=context.claim_id,
                run_id=context.run_id if context.run_id else None,
            )

            if not result.success:
                logger.error(
                    f"Reconciliation failed for {context.claim_id}: {result.error}"
                )
                context.status = "error"
                context.error = result.error
                context.notify_stage_update(self.name, "error")
                return context

            # Get the aggregated facts for downstream processing
            claim_facts = aggregation.aggregate_claim_facts(
                context.claim_id,
                result.report.run_id if result.report else None,
            )

            # Write outputs
            aggregation.write_claim_facts(context.claim_id, claim_facts)
            if result.report:
                reconciliation.write_reconciliation_report(
                    context.claim_id, result.report
                )

            # Store in context for downstream stages
            context.aggregated_facts = claim_facts.model_dump(mode="json")
            context.facts_run_id = claim_facts.run_id
            context.reconciliation_report = result.report

            # Log summary
            gate_status = result.report.gate.status.value if result.report else "unknown"
            conflict_count = result.report.gate.conflict_count if result.report else 0
            missing_count = (
                len(result.report.gate.missing_critical_facts) if result.report else 0
            )

            logger.info(
                f"Reconciliation complete for {context.claim_id}: "
                f"gate={gate_status}, facts={len(claim_facts.facts)}, "
                f"conflicts={conflict_count}, missing_critical={missing_count}"
            )

            context.notify_stage_update(self.name, "complete")

        except Exception as e:
            logger.error(f"Reconciliation failed for {context.claim_id}: {e}")
            context.status = "error"
            context.error = f"Reconciliation failed: {str(e)}"
            context.notify_stage_update(self.name, "error")
            return context

        context.timings.reconciliation_ms = int((time.time() - start) * 1000)
        return context
