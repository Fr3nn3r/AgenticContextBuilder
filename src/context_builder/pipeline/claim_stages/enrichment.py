"""Enrichment stage for claim-level pipeline.

.. deprecated:: Phase 6 (Two-Phase Assessment)
    This module is DEPRECATED. The enrichment stage functionality has been
    merged into the ScreeningStage:
    - Coverage lookups: Now handled by CoverageAnalyzer in screening
    - Shop authorization: Now handled by screener's _check_4a_shop_auth
    - Compression: No longer needed with reduced token usage

    The enrichment stage is no longer called from ClaimAssessmentService.
    This file is retained for backwards compatibility but may be removed
    in a future release.

This stage applies workspace-specific enrichment to aggregated claim facts.
Enrichment is optional - workspaces can opt-in by providing an enricher module.

The stage:
1. Loads workspace-specific enricher (if exists)
2. Applies enrichment to aggregated facts (coverage lookups, shop auth, etc.)
3. Optionally compresses based on reconciliation gate status
4. Writes enriched facts for audit trail

Pipeline flow:
    ReconciliationStage -> EnrichmentStage -> ProcessingStage
"""

import importlib.util
import json
import logging
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.schemas.reconciliation import ReconciliationReport

logger = logging.getLogger(__name__)


@runtime_checkable
class Enricher(Protocol):
    """Protocol for workspace-specific fact enrichers.

    Workspace enrichers implement this protocol to provide custom
    enrichment logic (coverage lookups, shop authorization, compression, etc.).

    To create an enricher for a workspace:
    1. Create {workspace}/config/enrichment/enricher.py
    2. Define a class implementing this protocol
    3. The class must accept workspace_path in __init__
    """

    def enrich(
        self,
        claim_facts: Dict[str, Any],
        reconciliation_report: Optional[ReconciliationReport] = None,
    ) -> Dict[str, Any]:
        """Enrich claim facts with workspace-specific data.

        Args:
            claim_facts: Aggregated facts from reconciliation (dict form).
            reconciliation_report: Gate status, token estimate, conflicts.

        Returns:
            Enriched claim facts with additional fields (e.g., _coverage_lookup,
            _shop_authorization_lookup, _check_inputs).
        """
        ...

    def should_compress(
        self,
        reconciliation_report: Optional[ReconciliationReport] = None,
        token_threshold: int = 40000,
    ) -> bool:
        """Determine if compression should be applied based on gate status.

        Args:
            reconciliation_report: Report containing token estimate.
            token_threshold: Threshold above which compression is triggered.

        Returns:
            True if compression should be applied.
        """
        ...


class DefaultEnricher:
    """Default enricher that passes through facts unchanged.

    Used when no workspace-specific enricher is configured.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def enrich(
        self,
        claim_facts: Dict[str, Any],
        reconciliation_report: Optional[ReconciliationReport] = None,
    ) -> Dict[str, Any]:
        """Pass through facts unchanged."""
        return claim_facts

    def should_compress(
        self,
        reconciliation_report: Optional[ReconciliationReport] = None,
        token_threshold: int = 40000,
    ) -> bool:
        """Never compress by default."""
        return False


def load_enricher_from_workspace(workspace_path: Path) -> Optional[Enricher]:
    """Discover and load enricher from workspace config.

    Looks for {workspace}/config/enrichment/enricher.py and loads the
    first class that implements the Enricher protocol.

    Args:
        workspace_path: Path to the workspace root.

    Returns:
        Instantiated enricher or None if not found.
    """
    enricher_path = workspace_path / "config" / "enrichment" / "enricher.py"

    if not enricher_path.exists():
        logger.debug(f"No enricher found at {enricher_path}")
        return None

    try:
        # Dynamic import of workspace enricher module
        spec = importlib.util.spec_from_file_location(
            "workspace_enricher", enricher_path
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for {enricher_path}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the enricher class (first class implementing Enricher protocol)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and attr_name != "Enricher"
                and hasattr(attr, "enrich")
                and hasattr(attr, "should_compress")
            ):
                # Instantiate with workspace_path
                enricher = attr(workspace_path)
                logger.info(f"Loaded enricher: {attr_name} from {enricher_path}")
                return enricher

        logger.warning(f"No Enricher implementation found in {enricher_path}")
        return None

    except Exception as e:
        logger.error(f"Failed to load enricher from {enricher_path}: {e}")
        return None


@dataclass
class EnrichmentStage:
    """Enrichment stage: apply workspace-specific enrichment to claim facts.

    This stage:
    - Loads workspace-specific enricher (if exists)
    - Applies coverage lookups, shop authorization, compression
    - Writes enriched facts for audit trail

    The stage is optional - if no enricher is configured, facts pass through unchanged.
    """

    name: str = "enrichment"
    _enricher: Optional[Enricher] = None
    _workspace_path: Optional[Path] = None

    def _get_enricher(self, workspace_path: Path) -> Enricher:
        """Get or load the enricher for this workspace."""
        # Cache enricher if workspace hasn't changed
        if self._enricher is not None and self._workspace_path == workspace_path:
            return self._enricher

        self._workspace_path = workspace_path
        self._enricher = load_enricher_from_workspace(workspace_path)

        if self._enricher is None:
            self._enricher = DefaultEnricher(workspace_path)
            logger.debug("Using default enricher (pass-through)")

        return self._enricher

    def _load_reconciliation_report(
        self, workspace_path: Path, claim_id: str
    ) -> Optional[ReconciliationReport]:
        """Load reconciliation report from claim context directory."""
        # Find claim folder
        claims_dir = workspace_path / "claims"
        claim_folder = None

        # Try exact match first
        if (claims_dir / claim_id).exists():
            claim_folder = claims_dir / claim_id
        else:
            # Try pattern match (e.g., "65258" matches "claim_65258")
            for folder in claims_dir.iterdir():
                if folder.is_dir() and claim_id in folder.name:
                    claim_folder = folder
                    break

        if not claim_folder:
            logger.warning(f"Claim folder not found for {claim_id}")
            return None

        report_path = claim_folder / "context" / "reconciliation_report.json"
        if not report_path.exists():
            logger.debug(f"No reconciliation report at {report_path}")
            return None

        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
            return ReconciliationReport.model_validate(report_data)
        except Exception as e:
            logger.warning(f"Failed to load reconciliation report: {e}")
            return None

    def _find_claim_folder(self, workspace_path: Path, claim_id: str) -> Optional[Path]:
        """Find the claim folder for a given claim ID."""
        claims_dir = workspace_path / "claims"

        # Try exact match first
        if (claims_dir / claim_id).exists():
            return claims_dir / claim_id

        # Try pattern match
        for folder in claims_dir.iterdir():
            if folder.is_dir() and claim_id in folder.name:
                return folder

        return None

    def _write_enriched_facts(
        self, workspace_path: Path, claim_id: str, enriched_facts: Dict[str, Any]
    ) -> Optional[Path]:
        """Write enriched facts to claim context directory."""
        claim_folder = self._find_claim_folder(workspace_path, claim_id)
        if not claim_folder:
            logger.error(f"Cannot write enriched facts: claim folder not found for {claim_id}")
            return None

        context_dir = claim_folder / "context"
        context_dir.mkdir(parents=True, exist_ok=True)

        output_path = context_dir / "claim_facts_enriched.json"
        tmp_path = output_path.with_suffix(".tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(enriched_facts, f, indent=2, ensure_ascii=False, default=str)
            tmp_path.replace(output_path)
            logger.info(f"Wrote claim_facts_enriched.json to {output_path}")
            return output_path
        except IOError as e:
            if tmp_path.exists():
                tmp_path.unlink()
            logger.error(f"Failed to write enriched facts: {e}")
            return None

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute enrichment and return updated context.

        .. deprecated:: Phase 6
            This method is deprecated. Use ScreeningStage instead, which now
            handles coverage analysis and shop authorization lookup internally.

        Args:
            context: The claim context with aggregated_facts loaded.

        Returns:
            Updated context with enriched aggregated_facts.
        """
        warnings.warn(
            "EnrichmentStage.run() is deprecated. Coverage analysis and shop "
            "authorization are now handled by ScreeningStage. This stage will "
            "be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )

        context.current_stage = self.name
        context.notify_stage_update(self.name, "running")
        start = time.time()

        # Skip if no facts to enrich
        if context.aggregated_facts is None:
            logger.info(f"Enrichment skipped for claim {context.claim_id}: no aggregated facts")
            context.timings.enrichment_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        logger.info(f"Running enrichment for claim {context.claim_id}")

        try:
            # Get enricher for this workspace
            enricher = self._get_enricher(context.workspace_path)

            # Use reconciliation report from pipeline context (preferred),
            # falling back to disk for standalone enrichment runs
            report = context.reconciliation_report
            if report is None:
                report = self._load_reconciliation_report(
                    context.workspace_path, context.claim_id
                )

            if report:
                gate_status = report.gate.status.value
                token_estimate = report.gate.estimated_tokens
                logger.info(
                    f"Reconciliation gate: {gate_status}, tokens: {token_estimate}"
                )

            # Apply enrichment
            enriched = enricher.enrich(
                context.aggregated_facts,
                reconciliation_report=report,
            )

            # Update context with enriched facts
            context.aggregated_facts = enriched

            # Write enriched facts for audit trail
            self._write_enriched_facts(
                context.workspace_path, context.claim_id, enriched
            )

            # Log enrichment summary if available
            if "_enrichment_summary" in enriched:
                summary = enriched["_enrichment_summary"]
                logger.info(
                    f"Enrichment complete for {context.claim_id}: "
                    f"{summary.get('total_line_items', 0)} items, "
                    f"{summary.get('covered_count', 0)} covered, "
                    f"{summary.get('unknown_count', 0)} unknown"
                )
            else:
                logger.info(f"Enrichment complete for claim {context.claim_id}")

            context.notify_stage_update(self.name, "complete")

        except Exception as e:
            logger.error(f"Enrichment failed for {context.claim_id}: {e}")
            # Enrichment failure is non-fatal - continue with unenriched facts
            context.notify_stage_update(self.name, "warning")
            logger.warning("Continuing with unenriched facts")

        # Record timing (use attribute if it exists, otherwise track separately)
        elapsed_ms = int((time.time() - start) * 1000)
        if hasattr(context.timings, "enrichment_ms"):
            context.timings.enrichment_ms = elapsed_ms
        else:
            # Store in context for tracking even if not in timings dataclass
            logger.debug(f"Enrichment took {elapsed_ms}ms")

        return context
