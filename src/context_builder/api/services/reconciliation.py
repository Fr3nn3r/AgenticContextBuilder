"""Reconciliation service for claim-level fact reconciliation and quality gates.

This service orchestrates:
1. Fact aggregation (via AggregationService)
2. Conflict detection (same fact with different values)
3. Quality gate evaluation (pass/warn/fail)
4. Report generation
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from context_builder.api.services.aggregation import AggregationError, AggregationService
from context_builder.schemas.claim_facts import ClaimFacts
from context_builder.schemas.reconciliation import (
    ConflictSource,
    FactConflict,
    FactFrequency,
    GateStatus,
    GateThresholds,
    ReconciliationClaimResult,
    ReconciliationEvalSummary,
    ReconciliationGate,
    ReconciliationReport,
    ReconciliationResult,
    ReconciliationRunEval,
)
from context_builder.storage.filesystem import FileStorage

logger = logging.getLogger(__name__)


class ReconciliationError(Exception):
    """Error during reconciliation."""

    pass


class ReconciliationService:
    """Service for claim-level fact reconciliation and quality gates.

    This service:
    - Aggregates facts from document extractions (via AggregationService)
    - Detects conflicts (same fact with different values across documents)
    - Evaluates a quality gate (pass/warn/fail)
    - Writes a reconciliation report

    Critical facts are derived from extraction specs (required_fields).
    Gate thresholds can be overridden via workspace config.
    """

    def __init__(self, storage: FileStorage, aggregation_service: AggregationService):
        """Initialize reconciliation service.

        Args:
            storage: FileStorage instance for accessing claims and config.
            aggregation_service: AggregationService for fact aggregation.
        """
        self.storage = storage
        self.aggregation = aggregation_service

    def reconcile(self, claim_id: str, run_context=None) -> ReconciliationResult:
        """Run full reconciliation for a claim using cross-run extraction collection.

        For each document, uses the latest available extraction regardless of
        which run produced it. This allows partial re-extractions to improve
        claim data without re-processing all documents.

        Steps:
        1. Aggregate facts from latest extraction per document (cross-run)
        2. Create claim run with actual runs used
        3. Load critical facts spec from extraction specs
        4. Detect conflicts
        5. Evaluate quality gate
        6. Build report with extractions_used
        7. Write outputs to claim run
        8. Update manifest

        Args:
            claim_id: Claim identifier.
            run_context: Optional ClaimRunContext with shared ID and metadata.

        Returns:
            ReconciliationResult with report (if successful) or error.
        """
        try:
            from context_builder.storage.claim_run import ClaimRunStorage
            from context_builder import get_version

            logger.info(f"Starting reconciliation for claim {claim_id} (cross-run)")

            claim_folder = self.storage._find_claim_folder(claim_id)
            if not claim_folder:
                return ReconciliationResult(
                    claim_id=claim_id,
                    success=False,
                    error=f"Claim not found: {claim_id}",
                )

            claim_run_storage = ClaimRunStorage(claim_folder)

            # Step 1: Aggregate facts using cross-run collection
            # This creates a temporary claim_run_id that we'll update
            claim_facts = self.aggregation.aggregate_claim_facts(
                claim_id, claim_run_id="pending"
            )

            # Step 2: Create claim run with actual runs used
            manifest = claim_run_storage.create_claim_run(
                extraction_runs=claim_facts.extraction_runs_used,
                contextbuilder_version=get_version(),
                run_context=run_context,
            )
            claim_run_id = manifest.claim_run_id

            # Update claim_facts with actual claim_run_id
            claim_facts.claim_run_id = claim_run_id
            logger.info(
                f"Created claim run {claim_run_id} using "
                f"{len(claim_facts.extraction_runs_used)} extraction run(s)"
            )

            # Step 3: Load critical facts spec and thresholds
            critical_facts_by_doctype = self.load_critical_facts_spec()
            thresholds = self.load_gate_thresholds()

            doc_types_present = {src.doc_type for src in claim_facts.sources}
            critical_facts = self._build_critical_facts_set(
                critical_facts_by_doctype, doc_types_present
            )
            logger.info(
                f"Critical facts for claim {claim_id}: {len(critical_facts)} "
                f"(from {len(doc_types_present)} doc types)"
            )

            # Step 4: Detect conflicts
            # Re-collect extractions for conflict detection
            extractions = self.aggregation.collect_latest_extractions(claim_id)
            candidates = self.aggregation.build_candidates(extractions)
            conflicts = self.detect_conflicts(candidates)
            logger.info(f"Detected {len(conflicts)} conflicts for claim {claim_id}")

            # Step 5: Evaluate gate
            gate = self.evaluate_gate(
                claim_facts, conflicts, list(critical_facts), thresholds
            )
            logger.info(f"Gate status for claim {claim_id}: {gate.status.value}")

            # Step 6: Build report with extractions_used
            present_facts = {f.name for f in claim_facts.facts}
            critical_present = [f for f in critical_facts if f in present_facts]

            # Build extractions_used list showing which extraction was used per document
            extractions_used = [
                {"doc_id": doc_id, "run_id": run_id, "filename": filename}
                for doc_id, run_id, _, filename, _ in extractions
            ]

            # Backward compatibility: set run_id if only one run was used
            single_run_id = (
                claim_facts.extraction_runs_used[0]
                if len(claim_facts.extraction_runs_used) == 1
                else None
            )

            report = ReconciliationReport(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                run_id=single_run_id,
                generated_at=datetime.utcnow(),
                gate=gate,
                conflicts=conflicts,
                fact_count=len(claim_facts.facts),
                critical_facts_spec=list(critical_facts),
                critical_facts_present=critical_present,
                thresholds_used=thresholds,
                extractions_used=extractions_used,
            )

            # Step 7: Write outputs to claim run
            self.aggregation.write_claim_facts(claim_id, claim_facts)
            self.write_reconciliation_report(claim_id, report)

            # Step 8: Update manifest with stages_completed
            manifest.stages_completed = ["reconciliation"]
            claim_run_storage.write_manifest(manifest)
            logger.info(
                f"Reconciliation complete for claim {claim_id}, claim run {claim_run_id}"
            )

            return ReconciliationResult(
                claim_id=claim_id,
                success=True,
                report=report,
            )

        except AggregationError as e:
            logger.error(f"Aggregation failed for claim {claim_id}: {e}")
            return ReconciliationResult(
                claim_id=claim_id,
                success=False,
                error=f"Aggregation failed: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Reconciliation failed for claim {claim_id}: {e}")
            return ReconciliationResult(
                claim_id=claim_id,
                success=False,
                error=f"Reconciliation failed: {str(e)}",
            )

    def load_critical_facts_spec(self) -> Dict[str, List[str]]:
        """Load critical facts from extraction specs (required_fields per doc_type).

        Reads all *.yaml files in the workspace config/extraction_specs directory
        and extracts required_fields from each.

        Returns:
            Dict mapping doc_type to list of required field names.
        """
        specs_dir = self.storage.output_root / "config" / "extraction_specs"
        critical_by_doctype: Dict[str, List[str]] = {}

        if not specs_dir.exists():
            logger.warning(f"Extraction specs directory not found: {specs_dir}")
            return critical_by_doctype

        for spec_file in specs_dir.glob("*.yaml"):
            try:
                with open(spec_file, "r", encoding="utf-8") as f:
                    spec = yaml.safe_load(f)

                if not spec:
                    continue

                doc_type = spec.get("doc_type")
                required_fields = spec.get("required_fields", [])

                if doc_type and required_fields:
                    critical_by_doctype[doc_type] = required_fields
                    logger.debug(
                        f"Loaded {len(required_fields)} critical facts for {doc_type}"
                    )

            except Exception as e:
                logger.warning(f"Failed to load extraction spec {spec_file}: {e}")
                continue

        logger.info(
            f"Loaded critical facts for {len(critical_by_doctype)} doc types"
        )
        return critical_by_doctype

    def load_gate_thresholds(self) -> GateThresholds:
        """Load gate thresholds from workspace config (optional override).

        Looks for config/reconciliation_gate.yaml in workspace.
        If not found, returns defaults.

        Returns:
            GateThresholds with values (defaults or overrides).
        """
        config_path = (
            self.storage.output_root / "config" / "reconciliation_gate.yaml"
        )

        if not config_path.exists():
            logger.debug("No reconciliation_gate.yaml found, using defaults")
            return GateThresholds()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if not config:
                return GateThresholds()

            thresholds_data = config.get("thresholds", {})
            return GateThresholds(
                missing_critical_warn=thresholds_data.get("missing_critical_warn", 2),
                missing_critical_fail=thresholds_data.get("missing_critical_fail", 2),
                conflict_warn=thresholds_data.get("conflict_warn", 2),
                conflict_fail=thresholds_data.get("conflict_fail", 2),
                token_warn=thresholds_data.get("token_warn", 40000),
                token_fail=thresholds_data.get("token_fail", 60000),
            )

        except Exception as e:
            logger.warning(f"Failed to load gate thresholds: {e}, using defaults")
            return GateThresholds()

    def _build_critical_facts_set(
        self,
        critical_by_doctype: Dict[str, List[str]],
        doc_types_present: Set[str],
    ) -> Set[str]:
        """Build union of critical facts for doc types present in the claim.

        Args:
            critical_by_doctype: Dict mapping doc_type to required fields.
            doc_types_present: Set of doc types present in the claim.

        Returns:
            Set of critical fact names.
        """
        critical_facts: Set[str] = set()
        for doc_type in doc_types_present:
            if doc_type in critical_by_doctype:
                critical_facts.update(critical_by_doctype[doc_type])
        return critical_facts

    def detect_conflicts(
        self, candidates: Dict[str, List[dict]]
    ) -> List[FactConflict]:
        """Detect facts with conflicting values across documents.

        A conflict exists when the same fact has different normalized values
        from different documents.

        Args:
            candidates: Dict mapping field names to candidate values
                       (from AggregationService.build_candidates).

        Returns:
            List of FactConflict objects.
        """
        conflicts = []

        for fact_name, candidate_list in candidates.items():
            if len(candidate_list) < 2:
                continue  # Need at least 2 candidates to have a conflict

            # Group by normalized value (or raw value if no normalized)
            values_to_sources: Dict[str, List[ConflictSource]] = defaultdict(list)
            value_to_confidence: Dict[str, float] = {}

            for candidate in candidate_list:
                val = candidate.get("normalized_value") or candidate.get("value")
                if val is None:
                    continue

                # Convert to string for comparison
                val_str = str(val)
                doc_id = candidate.get("doc_id", "unknown")
                doc_type = candidate.get("doc_type", "unknown")
                filename = candidate.get("filename", f"{doc_id}.pdf")
                confidence = candidate.get("confidence", 0.0)

                # Create ConflictSource with full provenance
                source = ConflictSource(
                    doc_id=doc_id,
                    doc_type=doc_type,
                    filename=filename,
                )
                values_to_sources[val_str].append(source)

                # Track highest confidence per value
                if val_str not in value_to_confidence:
                    value_to_confidence[val_str] = confidence
                else:
                    value_to_confidence[val_str] = max(
                        value_to_confidence[val_str], confidence
                    )

            # If more than one distinct value, it's a conflict
            if len(values_to_sources) > 1:
                # Find selected value (highest confidence)
                selected_value = max(
                    value_to_confidence.keys(),
                    key=lambda v: value_to_confidence[v],
                )

                conflicts.append(
                    FactConflict(
                        fact_name=fact_name,
                        values=list(values_to_sources.keys()),
                        sources=list(values_to_sources.values()),
                        selected_value=selected_value,
                        selected_confidence=value_to_confidence[selected_value],
                        selection_reason="highest_confidence",
                    )
                )

        return conflicts

    def evaluate_gate(
        self,
        claim_facts: ClaimFacts,
        conflicts: List[FactConflict],
        critical_facts: List[str],
        thresholds: GateThresholds,
    ) -> ReconciliationGate:
        """Evaluate quality gate for reconciliation.

        Gate rules:
        - FAIL: >N missing critical facts OR >N conflicts OR tokens > fail_threshold
        - WARN: <=N missing critical facts OR <=N conflicts OR tokens > warn_threshold
        - PASS: No missing critical facts AND no conflicts AND tokens <= warn_threshold

        Args:
            claim_facts: Aggregated claim facts.
            conflicts: List of detected conflicts.
            critical_facts: List of critical fact names to check.
            thresholds: Gate thresholds.

        Returns:
            ReconciliationGate with status and reasons.
        """
        # Check missing critical facts
        # Handle namespaced facts: if checking for "document_date", consider it present
        # if any namespaced version exists (e.g., "service_history.document_date")
        present_facts = {f.name for f in claim_facts.facts}

        def is_fact_present(fact_name: str) -> bool:
            """Check if a critical fact is present, considering namespaced versions."""
            if fact_name in present_facts:
                return True
            # Check for namespaced versions (e.g., "doc_type.fact_name")
            suffix = f".{fact_name}"
            return any(pf.endswith(suffix) for pf in present_facts)

        missing = [f for f in critical_facts if not is_fact_present(f)]

        # Count conflicts
        conflict_count = len(conflicts)

        # Estimate tokens (rough: ~4 chars per token)
        total_chars = sum(
            len(str(f.value) or "") + len(f.name) for f in claim_facts.facts
        )
        token_estimate = total_chars // 4

        # Calculate provenance coverage
        with_provenance = sum(
            1 for f in claim_facts.facts if f.selected_from.text_quote
        )
        coverage = (
            with_provenance / len(claim_facts.facts) if claim_facts.facts else 0.0
        )

        # Determine status
        reasons: List[str] = []
        status = GateStatus.PASS

        # Check for FAIL conditions
        if len(missing) > thresholds.missing_critical_fail:
            status = GateStatus.FAIL
            reasons.append(
                f"{len(missing)} critical facts missing (threshold: {thresholds.missing_critical_fail})"
            )

        if conflict_count > thresholds.conflict_fail:
            status = GateStatus.FAIL
            reasons.append(
                f"{conflict_count} conflicts detected (threshold: {thresholds.conflict_fail})"
            )

        if token_estimate > thresholds.token_fail:
            status = GateStatus.FAIL
            reasons.append(
                f"Token estimate ({token_estimate}) exceeds {thresholds.token_fail}"
            )

        # Check for WARN conditions (only if not already FAIL)
        if status != GateStatus.FAIL:
            if missing and len(missing) <= thresholds.missing_critical_warn:
                status = GateStatus.WARN
                reasons.append(f"{len(missing)} critical facts missing")

            if conflicts and conflict_count <= thresholds.conflict_warn:
                status = GateStatus.WARN
                reasons.append(f"{conflict_count} conflicts detected")

            if token_estimate > thresholds.token_warn:
                status = GateStatus.WARN
                reasons.append(
                    f"Token estimate ({token_estimate}) exceeds {thresholds.token_warn}"
                )

        # PASS message
        if status == GateStatus.PASS:
            reasons.append("All critical facts present, no conflicts")

        return ReconciliationGate(
            status=status,
            missing_critical_facts=missing,
            conflict_count=conflict_count,
            provenance_coverage=round(coverage, 3),
            estimated_tokens=token_estimate,
            reasons=reasons,
        )

    def write_reconciliation_report(
        self, claim_id: str, report: ReconciliationReport
    ) -> Path:
        """Write reconciliation report to claim run directory.

        Args:
            claim_id: Claim identifier.
            report: ReconciliationReport to write.

        Returns:
            Path to written file.

        Raises:
            ReconciliationError: If claim folder not found or write fails.
        """
        claim_folder = self.storage._find_claim_folder(claim_id)
        if not claim_folder:
            raise ReconciliationError(f"Claim not found: {claim_id}")

        from context_builder.storage.claim_run import ClaimRunStorage

        claim_run_storage = ClaimRunStorage(claim_folder)
        try:
            output_path = claim_run_storage.write_to_claim_run(
                report.claim_run_id,
                "reconciliation_report.json",
                report.model_dump(mode="json"),
            )
            logger.info(f"Wrote reconciliation_report.json to {output_path}")
            return output_path
        except Exception as e:
            raise ReconciliationError(f"Failed to write reconciliation report: {e}")

    def write_claim_facts(self, claim_id: str, claim_facts: ClaimFacts) -> Path:
        """Write aggregated claim facts to claim context directory.

        Delegates to AggregationService.

        Args:
            claim_id: Claim identifier.
            claim_facts: ClaimFacts to write.

        Returns:
            Path to written file.
        """
        return self.aggregation.write_claim_facts(claim_id, claim_facts)

    # =========================================================================
    # RUN-LEVEL AGGREGATION
    # =========================================================================

    def aggregate_run_evaluation(self, top_n: int = 10) -> ReconciliationRunEval:
        """Aggregate reconciliation reports from all claims into a run-level evaluation.

        Scans all claims in the workspace for reconciliation_report.json files
        and produces a summary evaluation.

        Args:
            top_n: Number of top missing facts and conflicts to include (default 10).

        Returns:
            ReconciliationRunEval with summary and per-claim results.
        """
        claims_dir = self.storage.claims_dir
        results: List[ReconciliationClaimResult] = []
        missing_facts_counter: Dict[str, List[str]] = defaultdict(list)
        conflicts_counter: Dict[str, List[str]] = defaultdict(list)
        run_ids: Set[str] = set()

        # Scan all claim directories for reconciliation reports
        for claim_folder in claims_dir.iterdir():
            if not claim_folder.is_dir():
                continue

            report_path = claim_folder / "context" / "reconciliation_report.json"
            if not report_path.exists():
                continue

            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    report_data = json.load(f)

                claim_id = report_data.get("claim_id", claim_folder.name)
                gate_data = report_data.get("gate", {})
                gate_status = GateStatus(gate_data.get("status", "fail"))
                missing_critical = gate_data.get("missing_critical_facts", [])

                # Track run_id
                if "run_id" in report_data:
                    run_ids.add(report_data["run_id"])

                # Build per-claim result
                result = ReconciliationClaimResult(
                    claim_id=claim_id,
                    gate_status=gate_status,
                    fact_count=report_data.get("fact_count", 0),
                    conflict_count=gate_data.get("conflict_count", 0),
                    missing_critical_count=len(missing_critical),
                    missing_critical_facts=missing_critical,
                    provenance_coverage=gate_data.get("provenance_coverage", 0.0),
                    reasons=gate_data.get("reasons", []),
                )
                results.append(result)

                # Count missing facts
                for fact in missing_critical:
                    missing_facts_counter[fact].append(claim_id)

                # Count conflicts
                for conflict in report_data.get("conflicts", []):
                    fact_name = conflict.get("fact_name", "unknown")
                    conflicts_counter[fact_name].append(claim_id)

            except (json.JSONDecodeError, IOError, KeyError) as e:
                logger.warning(f"Failed to read reconciliation report {report_path}: {e}")
                continue

        # Build summary
        total = len(results)
        passed = sum(1 for r in results if r.gate_status == GateStatus.PASS)
        warned = sum(1 for r in results if r.gate_status == GateStatus.WARN)
        failed = sum(1 for r in results if r.gate_status == GateStatus.FAIL)
        total_conflicts = sum(r.conflict_count for r in results)

        summary = ReconciliationEvalSummary(
            total_claims=total,
            passed=passed,
            warned=warned,
            failed=failed,
            pass_rate=passed / total if total > 0 else 0.0,
            pass_rate_percent=f"{(passed / total * 100) if total > 0 else 0:.1f}%",
            avg_fact_count=sum(r.fact_count for r in results) / total if total > 0 else 0.0,
            avg_conflicts=total_conflicts / total if total > 0 else 0.0,
            avg_missing_critical=(
                sum(r.missing_critical_count for r in results) / total if total > 0 else 0.0
            ),
            total_conflicts=total_conflicts,
        )

        # Build top missing facts
        top_missing = sorted(
            missing_facts_counter.items(), key=lambda x: len(x[1]), reverse=True
        )[:top_n]
        top_missing_facts = [
            FactFrequency(fact_name=fact, count=len(claims), claim_ids=claims)
            for fact, claims in top_missing
        ]

        # Build top conflicts
        top_conflict_items = sorted(
            conflicts_counter.items(), key=lambda x: len(x[1]), reverse=True
        )[:top_n]
        top_conflicts = [
            FactFrequency(fact_name=fact, count=len(claims), claim_ids=claims)
            for fact, claims in top_conflict_items
        ]

        # Determine run_id (use single if consistent, None if multiple)
        run_id = run_ids.pop() if len(run_ids) == 1 else None

        return ReconciliationRunEval(
            run_id=run_id,
            summary=summary,
            top_missing_facts=top_missing_facts,
            top_conflicts=top_conflicts,
            results=sorted(results, key=lambda r: r.claim_id),
        )

    def write_run_evaluation(self, evaluation: ReconciliationRunEval) -> Path:
        """Write run-level evaluation to workspace eval directory.

        Args:
            evaluation: ReconciliationRunEval to write.

        Returns:
            Path to written file.
        """
        # claims_dir is {workspace}/claims, so parent is the workspace root
        eval_dir = self.storage.claims_dir.parent / "eval"
        eval_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = eval_dir / f"reconciliation_gate_eval_{timestamp}.json"
        tmp_path = output_path.with_suffix(".tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(
                    evaluation.model_dump(mode="json"),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            tmp_path.replace(output_path)
            logger.info(f"Wrote reconciliation_gate_eval to {output_path}")
            return output_path

        except IOError as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise ReconciliationError(f"Failed to write run evaluation: {e}")
