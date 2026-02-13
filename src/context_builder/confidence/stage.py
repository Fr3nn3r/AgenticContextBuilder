"""Confidence stage for claim-level pipeline.

Runs after DecisionStage.  Collects data-quality signals from all
upstream results, computes the Composite Confidence Index, and:
1. Writes ``confidence_summary.json`` to the claim run directory
2. Patches the latest ``decision_dossier_v{N}.json`` with a
   ``confidence_index`` field

The stage is **non-fatal**: any exception is logged and the pipeline
continues without a confidence score.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from context_builder.confidence.scorer import ConfidenceScorer
from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.storage.claim_run import ClaimRunStorage

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceStage:
    """Confidence stage: collects signals and computes Composite Confidence Index.

    Pipeline position:
        Reconciliation -> Enrichment -> Screening -> Processing -> Decision -> **Confidence**
    """

    name: str = "confidence"

    def _find_claim_folder(self, workspace_path: Path, claim_id: str) -> Optional[Path]:
        """Find the claim folder for a given claim ID."""
        claims_dir = workspace_path / "claims"
        if not claims_dir.exists():
            return None

        if (claims_dir / claim_id).exists():
            return claims_dir / claim_id

        for folder in claims_dir.iterdir():
            if folder.is_dir() and claim_id in folder.name:
                return folder

        return None

    def _load_extraction_results(
        self, claim_folder: Path
    ) -> List[Dict[str, Any]]:
        """Load extraction JSON files from all docs in the claim."""
        results: List[Dict[str, Any]] = []
        docs_dir = claim_folder / "docs"
        if not docs_dir.exists():
            return results

        for doc_dir in docs_dir.iterdir():
            if not doc_dir.is_dir():
                continue
            extraction_dir = doc_dir / "extraction"
            if not extraction_dir.exists():
                continue
            for ext_file in sorted(extraction_dir.glob("*.json")):
                try:
                    with open(ext_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        results.append(data)
                except Exception:
                    logger.debug(f"Could not load extraction file {ext_file}", exc_info=True)

        return results

    def _derive_extraction_from_facts(
        self, claim_folder: Path, claim_run_id: str
    ) -> List[Dict[str, Any]]:
        """Derive extraction quality signals from claim_facts.json when per-doc extraction files are missing.

        Falls back to claim_facts (aggregated fields with confidence) and
        meta/doc.json (doc-type confidence) to produce synthetic extraction
        results that the collector can score.
        """
        storage = ClaimRunStorage(claim_folder)
        claim_facts = storage.read_from_claim_run(claim_run_id, "claim_facts.json")
        if not claim_facts:
            return []

        facts = claim_facts.get("facts") or []
        if not facts:
            return []

        # Group facts by source doc
        doc_facts: Dict[str, List[Dict[str, Any]]] = {}
        for fact in facts:
            selected = fact.get("selected_from") or {}
            doc_id = selected.get("doc_id", "unknown")
            doc_facts.setdefault(doc_id, []).append(fact)

        results: List[Dict[str, Any]] = []
        docs_dir = claim_folder / "docs"
        for doc_id, fields_data in doc_facts.items():
            result: Dict[str, Any] = {"fields": []}

            # Read doc_type_confidence from meta/doc.json
            meta_path = docs_dir / doc_id / "meta" / "doc.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    dtc = meta.get("doc_type_confidence")
                    if dtc is not None:
                        result["doc_type_confidence"] = dtc
                except Exception:
                    pass

            # Convert facts to field-like dicts
            for fact in fields_data:
                fld: Dict[str, Any] = {
                    "confidence": fact.get("confidence"),
                }
                selected = fact.get("selected_from") or {}
                if selected.get("text_quote"):
                    fld["has_verified_evidence"] = True

                result["fields"].append(fld)

            results.append(result)

        logger.debug(
            f"Derived extraction data from claim_facts: {len(results)} docs, "
            f"{sum(len(r['fields']) for r in results)} fields"
        )
        return results

    def _load_coverage_analysis(
        self, claim_folder: Path, claim_run_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load coverage_analysis.json from the claim run directory."""
        run_dir = claim_folder / "claim_runs" / claim_run_id
        path = run_dir / "coverage_analysis.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.debug(f"Could not load {path}", exc_info=True)
            return None

    def _load_reconciliation_report(
        self, context: ClaimContext, claim_folder: Path
    ) -> Optional[Dict[str, Any]]:
        """Get reconciliation report from context or disk."""
        # Prefer context (already a dict or Pydantic model)
        rr = context.reconciliation_report
        if rr is not None:
            if hasattr(rr, "model_dump"):
                return rr.model_dump(mode="json")
            if isinstance(rr, dict):
                return rr

        # Fallback: disk
        path = claim_folder / "context" / "reconciliation_report.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _load_custom_weights(self, workspace_path: Path) -> Optional[Dict[str, float]]:
        """Load custom CCI weights from workspace config (if exists)."""
        weights_path = workspace_path / "config" / "confidence" / "weights.yaml"
        if not weights_path.exists():
            return None

        try:
            with open(weights_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "weights" in data:
                return {str(k): float(v) for k, v in data["weights"].items()}
        except Exception:
            logger.warning(f"Could not load custom weights from {weights_path}", exc_info=True)

        return None

    def _find_latest_dossier(
        self, claim_folder: Path, claim_run_id: str
    ) -> Optional[Path]:
        """Find the latest decision_dossier_v{N}.json in the claim run."""
        run_dir = claim_folder / "claim_runs" / claim_run_id
        if not run_dir.exists():
            return None

        dossiers = sorted(run_dir.glob("decision_dossier_v*.json"))
        return dossiers[-1] if dossiers else None

    def _patch_dossier(
        self, dossier_path: Path, confidence_index: Dict[str, Any]
    ) -> None:
        """Patch an existing decision dossier JSON with the confidence_index field."""
        try:
            with open(dossier_path, "r", encoding="utf-8") as f:
                dossier = json.load(f)
            dossier["confidence_index"] = confidence_index
            with open(dossier_path, "w", encoding="utf-8") as f:
                json.dump(dossier, f, indent=2, ensure_ascii=False)
            logger.info(f"Patched {dossier_path.name} with confidence_index")
        except Exception:
            logger.warning(f"Failed to patch dossier {dossier_path}", exc_info=True)

    def _evaluate_routing(
        self,
        *,
        claim_id: str,
        claim_run_id: str,
        verdict: str,
        reconciliation_report: Optional[Dict[str, Any]],
        coverage_analysis: Optional[Dict[str, Any]],
        processing_result: Optional[Dict[str, Any]],
        confidence_summary: Optional[Dict[str, Any]],
        workspace_path: Optional[Path] = None,
    ) -> Optional["RoutingDecision"]:
        """Run routing evaluation. Returns None on error."""
        try:
            from context_builder.confidence.routing import ClaimRouter, load_thresholds

            thresholds = load_thresholds(workspace_path)
            router = ClaimRouter(thresholds=thresholds)
            return router.evaluate(
                claim_id=claim_id,
                claim_run_id=claim_run_id,
                verdict=verdict,
                reconciliation_report=reconciliation_report,
                coverage_analysis=coverage_analysis,
                processing_result=processing_result,
                confidence_summary=confidence_summary,
            )
        except Exception:
            logger.warning("Routing evaluation failed", exc_info=True)
            return None

    def _patch_dossier_routing(
        self, dossier_path: Path, routing_decision: "RoutingDecision"
    ) -> None:
        """Patch dossier with routing info and override verdict if RED."""
        try:
            with open(dossier_path, "r", encoding="utf-8") as f:
                dossier = json.load(f)

            routing_data = {
                "routing_tier": routing_decision.routing_tier.value,
                "triggers_fired": [
                    {"trigger_id": t.trigger_id, "name": t.name, "explanation": t.explanation}
                    for t in routing_decision.triggers_fired
                ],
                "tier_reason": routing_decision.tier_reason,
                "original_verdict": routing_decision.original_verdict,
                "structural_cci": routing_decision.structural_cci,
                "cci_threshold_green": routing_decision.cci_threshold_green,
                "cci_threshold_yellow": routing_decision.cci_threshold_yellow,
            }
            dossier["routing"] = routing_data

            # Override verdict to REFER if RED + originally APPROVE
            if routing_decision.routed_verdict:
                dossier["claim_verdict"] = routing_decision.routed_verdict
                cci_str = (
                    f"CCI {routing_decision.structural_cci:.3f}"
                    if routing_decision.structural_cci is not None
                    else "CCI not available"
                )
                dossier["verdict_reason"] = (
                    f"Routed to REFER: {cci_str}. "
                    f"{routing_decision.tier_reason}. "
                    f"Original verdict: {routing_decision.original_verdict}"
                )
                logger.info(
                    f"Verdict overridden to REFER for {routing_decision.claim_id} "
                    f"(was {routing_decision.original_verdict})"
                )

            with open(dossier_path, "w", encoding="utf-8") as f:
                json.dump(dossier, f, indent=2, ensure_ascii=False)
        except Exception:
            logger.warning(f"Failed to patch dossier routing {dossier_path}", exc_info=True)

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute confidence computation and return updated context.

        Non-fatal: exceptions are caught and logged as warnings.
        """
        context.current_stage = self.name
        context.notify_stage_update(self.name, "running")
        start = time.time()

        # Skip if disabled
        if not getattr(context.stage_config, "run_confidence", True):
            logger.info(f"Confidence skipped for {context.claim_id}: run_confidence=False")
            context.timings.confidence_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        try:
            claim_folder = self._find_claim_folder(
                context.workspace_path, context.claim_id
            )

            # ── Load data ────────────────────────────────────────
            extraction_results = (
                self._load_extraction_results(claim_folder) if claim_folder else []
            )
            if not extraction_results and claim_folder:
                extraction_results = self._derive_extraction_from_facts(
                    claim_folder, context.run_id
                )
            coverage_analysis = (
                self._load_coverage_analysis(claim_folder, context.run_id)
                if claim_folder
                else None
            )
            reconciliation_report = (
                self._load_reconciliation_report(context, claim_folder)
                if claim_folder
                else None
            )
            custom_weights = self._load_custom_weights(context.workspace_path)

            # ── Compute CCI (centralised) ────────────────────────
            from context_builder.confidence import compute_confidence

            summary = compute_confidence(
                claim_id=context.claim_id,
                claim_run_id=context.run_id,
                extraction_results=extraction_results,
                reconciliation_report=reconciliation_report,
                coverage_analysis=coverage_analysis,
                screening_result=context.screening_result,
                processing_result=context.processing_result,
                decision_result=context.decision_result,
                weights=custom_weights,
            )

            if summary is None:
                logger.info(f"No signals collected for {context.claim_id}, skipping CCI")
                context.notify_stage_update(self.name, "skipped")
                elapsed_ms = int((time.time() - start) * 1000)
                context.timings.confidence_ms = elapsed_ms
                return context

            # ── Persist ──────────────────────────────────────────
            if claim_folder:
                try:
                    storage = ClaimRunStorage(claim_folder)
                    storage.write_to_claim_run(
                        context.run_id,
                        "confidence_summary.json",
                        summary.model_dump(mode="json"),
                    )
                    logger.info(f"Wrote confidence_summary.json for {context.claim_id}")
                except Exception:
                    logger.warning("Failed to write confidence_summary.json", exc_info=True)

                # Patch latest dossier
                scorer = ConfidenceScorer(weights=custom_weights)
                ci = scorer.to_confidence_index(summary)
                dossier_path = self._find_latest_dossier(claim_folder, context.run_id)
                if dossier_path:
                    self._patch_dossier(dossier_path, ci.model_dump(mode="json"))

            # ── Routing evaluation ────────────────────────────────
            verdict = ""
            if context.decision_result:
                verdict = (context.decision_result.get("claim_verdict") or "")

            routing_decision = self._evaluate_routing(
                claim_id=context.claim_id,
                claim_run_id=context.run_id,
                verdict=verdict,
                reconciliation_report=reconciliation_report,
                coverage_analysis=coverage_analysis,
                processing_result=context.processing_result,
                confidence_summary=summary.model_dump(mode="json") if summary else None,
                workspace_path=context.workspace_path,
            )

            if routing_decision and claim_folder:
                try:
                    storage = ClaimRunStorage(claim_folder)
                    storage.write_to_claim_run(
                        context.run_id,
                        "routing_decision.json",
                        routing_decision.model_dump(mode="json"),
                    )
                    logger.info(
                        f"Routing for {context.claim_id}: "
                        f"tier={routing_decision.routing_tier.value}, "
                        f"triggers_fired={len(routing_decision.triggers_fired)}"
                    )
                except Exception:
                    logger.warning("Failed to write routing_decision.json", exc_info=True)

                # Patch dossier with routing info
                dossier_path_for_routing = self._find_latest_dossier(
                    claim_folder, context.run_id
                )
                if dossier_path_for_routing:
                    self._patch_dossier_routing(
                        dossier_path_for_routing, routing_decision
                    )

            logger.info(
                f"Confidence complete for {context.claim_id}: "
                f"CCI={summary.composite_score:.3f} ({summary.band.value}), "
                f"{len(summary.signals_collected)} signals, "
                f"{len(summary.stages_available)} stages"
            )
            context.notify_stage_update(self.name, "complete")

        except Exception:
            logger.error(
                f"Confidence failed for {context.claim_id}", exc_info=True
            )
            context.notify_stage_update(self.name, "warning")
            logger.warning("Continuing without confidence results")

        elapsed_ms = int((time.time() - start) * 1000)
        context.timings.confidence_ms = elapsed_ms
        return context
