"""Decision stage for claim-level pipeline.

This stage evaluates every claim against denial clauses from the workspace
config, producing a versioned Decision Dossier with full traceability.

The stage:
1. Loads workspace-specific decision engine (if exists)
2. Reads upstream results (screening, coverage, processing)
3. Calls engine.evaluate() with all available evidence
4. Writes decision_dossier_v{N}.json to the claim run directory
5. Stores result in context.decision_result

Pipeline flow:
    Reconciliation -> Enrichment -> Screening -> Processing -> Decision
"""

import importlib.util
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.storage.claim_run import ClaimRunStorage

logger = logging.getLogger(__name__)


# ── Decision Engine Protocol ────────────────────────────────────────


@runtime_checkable
class DecisionEngine(Protocol):
    """Protocol for workspace-specific decision engine implementations.

    Workspace engines implement this protocol to evaluate claims against
    denial clauses and produce a Decision Dossier.

    To create an engine for a workspace:
    1. Create {workspace}/config/decision/engine.py
    2. Define a class implementing this protocol
    3. The class must accept workspace_path in __init__
    """

    engine_id: str
    engine_version: str

    def evaluate(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        screening_result: Optional[Dict[str, Any]] = None,
        coverage_analysis: Optional[Dict[str, Any]] = None,
        processing_result: Optional[Dict[str, Any]] = None,
        assumptions: Optional[Dict[str, bool]] = None,
        coverage_overrides: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """Evaluate a claim against all denial clauses.

        Args:
            claim_id: Claim identifier.
            aggregated_facts: Enriched aggregated facts dict.
            screening_result: Screening result dict (if available).
            coverage_analysis: Coverage analysis dict (if available).
            processing_result: Processing/assessment result dict (if available).
            assumptions: Override assumptions for tier 2/3 clauses
                         {clause_reference: bool}. None = use defaults.
            coverage_overrides: Adjuster coverage overrides
                         {item_id: is_covered}. None = no overrides.

        Returns:
            Decision Dossier as a dict (matching DecisionDossier schema).
        """
        ...

    def get_clause_registry(self) -> List[Dict[str, Any]]:
        """Return the full clause registry as a list of dicts.

        Returns:
            List of denial clause definitions.
        """
        ...


# ── Service Protocols ───────────────────────────────────────────────


@runtime_checkable
class LaborRateService(Protocol):
    """Protocol for labor rate validation services."""

    def validate_labor_rate(
        self,
        operation: str,
        vehicle_make: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        claimed_hours: Optional[float] = None,
        claimed_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Validate labor rate for an operation.

        Returns:
            LaborRateResult as a dict.
        """
        ...


@runtime_checkable
class PartsClassificationService(Protocol):
    """Protocol for parts classification services."""

    def classify_part(
        self,
        description: str,
        item_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Classify a part by description.

        Returns:
            PartsClassification as a dict.
        """
        ...


# ── Default Decision Engine ────────────────────────────────────────


class DefaultDecisionEngine:
    """Default engine that derives a verdict from assessment check results.

    Used when no workspace-specific decision engine is configured.
    Produces no clause evaluations but derives a meaningful verdict
    from the upstream assessment (processing_result) when available.
    """

    engine_id: str = "default"
    engine_version: str = "0.1.0"

    # Check IDs whose FAIL does not block approval (override in subclasses)
    SOFT_CHECK_IDS: set = set()

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def _derive_verdict_from_assessment(
        self, processing_result: Optional[Dict[str, Any]]
    ) -> tuple:
        """Derive verdict and reason from assessment check results.

        Priority order:
        1. No processing_result -> REFER (no data to decide)
        2. Any hard check FAIL -> DENY
        3. Any INCONCLUSIVE check -> REFER
        4. Only soft checks failed -> APPROVE
        5. APPROVE + zero payout -> DENY
        6. Otherwise -> use LLM advisory decision

        Returns:
            (verdict: str, reason: str)
        """
        if not processing_result:
            return "REFER", "No assessment data available to derive verdict"

        checks = processing_result.get("checks", [])
        llm_decision = (processing_result.get("recommendation") or "").upper()

        # Classify check results
        hard_fails = []
        inconclusive_checks = []
        soft_fails = []

        for check in checks:
            if not isinstance(check, dict):
                continue
            result = (check.get("result") or "").upper()
            check_number = check.get("check_number", "")
            check_name = check.get("check_name", "")
            # Skip the final_decision meta-check
            if check_name == "final_decision":
                continue

            if result == "FAIL":
                if check_number in self.SOFT_CHECK_IDS:
                    soft_fails.append(check_name or check_number)
                else:
                    hard_fails.append(check_name or check_number)
            elif result == "INCONCLUSIVE":
                inconclusive_checks.append(check_name or check_number)

        # 1. Hard check FAIL -> DENY
        if hard_fails:
            return "DENY", f"Hard check(s) failed: {', '.join(hard_fails)}"

        # 2. Any INCONCLUSIVE -> REFER
        if inconclusive_checks:
            return (
                "REFER",
                f"Inconclusive check(s) require review: {', '.join(inconclusive_checks)}",
            )

        # 3. Only soft checks failed -> APPROVE (soft checks don't block)
        # (If no hard fails and no inconclusive, approve even with soft fails)

        # 4. Zero payout -> DENY
        final_payout = (processing_result.get("payout") or {}).get("final_payout", 0.0)
        if llm_decision in ("APPROVE", "APPROVED") and final_payout <= 0:
            payout_data = processing_result.get("payout") or {}
            covered = payout_data.get("covered_subtotal", 0.0)
            deductible = payout_data.get("deductible", 0.0)
            currency = payout_data.get("currency", "CHF")
            return (
                "DENY",
                f"Covered amount ({currency} {covered:,.2f}) does not exceed "
                f"the deductible ({currency} {deductible:,.2f}), "
                f"resulting in zero payout",
            )

        # 5. Fall back to LLM advisory decision (normalized)
        if llm_decision in ("APPROVE", "APPROVED"):
            if soft_fails:
                return (
                    "APPROVE",
                    f"Approved despite soft check(s): {', '.join(soft_fails)}",
                )
            return "APPROVE", "All checks passed"
        if llm_decision in ("REJECT", "REJECTED", "DENY", "DENIED"):
            return "DENY", processing_result.get("recommendation_rationale", "Rejected by assessment")
        if llm_decision in ("REFER_TO_HUMAN", "REFER"):
            return "REFER", processing_result.get("recommendation_rationale", "Referred by assessment")

        # No recognizable decision
        return "REFER", "Could not derive verdict from assessment"

    def evaluate(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        screening_result: Optional[Dict[str, Any]] = None,
        coverage_analysis: Optional[Dict[str, Any]] = None,
        processing_result: Optional[Dict[str, Any]] = None,
        assumptions: Optional[Dict[str, bool]] = None,
        coverage_overrides: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """Return dossier with verdict derived from assessment checks."""
        verdict, reason = self._derive_verdict_from_assessment(processing_result)

        return {
            "schema_version": "decision_dossier_v1",
            "claim_id": claim_id,
            "version": 1,
            "claim_verdict": verdict,
            "verdict_reason": reason,
            "clause_evaluations": [],
            "line_item_decisions": [],
            "assumptions_used": [],
            "financial_summary": None,
            "engine_id": self.engine_id,
            "engine_version": self.engine_version,
            "evaluation_timestamp": datetime.utcnow().isoformat(),
            "input_refs": {},
            "failed_clauses": [],
            "unresolved_assumptions": [],
        }

    def get_clause_registry(self) -> List[Dict[str, Any]]:
        """Return empty clause registry."""
        return []


# ── Dynamic loader ──────────────────────────────────────────────────


def load_engine_from_workspace(workspace_path: Path) -> Optional[DecisionEngine]:
    """Discover and load decision engine from workspace config.

    Looks for {workspace}/config/decision/engine.py and loads the
    first class that implements the DecisionEngine protocol
    (has an 'evaluate' method and 'engine_id' attribute).

    Args:
        workspace_path: Path to the workspace root.

    Returns:
        Instantiated engine or None if not found.
    """
    engine_path = workspace_path / "config" / "decision" / "engine.py"

    if not engine_path.exists():
        logger.debug(f"No decision engine found at {engine_path}")
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            "workspace_decision_engine", engine_path
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for {engine_path}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the engine class (first class with an 'evaluate' method)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and attr_name != "DecisionEngine"
                and hasattr(attr, "evaluate")
                and hasattr(attr, "engine_id")
            ):
                engine = attr(workspace_path)
                logger.info(f"Loaded decision engine: {attr_name} from {engine_path}")
                return engine

        logger.warning(f"No DecisionEngine implementation found in {engine_path}")
        return None

    except Exception as e:
        logger.error(f"Failed to load decision engine from {engine_path}: {e}")
        return None


# ── Decision Stage ──────────────────────────────────────────────────


@dataclass
class DecisionStage:
    """Decision stage: loads workspace engine and evaluates claim against denial clauses.

    This stage:
    - Loads workspace-specific decision engine (if exists)
    - Reads upstream results (screening, coverage, processing)
    - Determines next dossier version number
    - Calls engine.evaluate() with all available evidence
    - Writes decision_dossier_v{N}.json to the claim run directory
    - Stores result in context.decision_result

    The stage is non-fatal — exceptions are caught and logged as warnings,
    allowing the pipeline to continue.
    """

    name: str = "decision"
    _engine: Optional[DecisionEngine] = field(default=None, repr=False)
    _workspace_path: Optional[Path] = field(default=None, repr=False)

    def _get_engine(self, workspace_path: Path) -> DecisionEngine:
        """Get or load the decision engine for this workspace (with caching)."""
        if self._engine is not None and self._workspace_path == workspace_path:
            return self._engine

        self._workspace_path = workspace_path
        self._engine = load_engine_from_workspace(workspace_path)

        if self._engine is None:
            self._engine = DefaultDecisionEngine(workspace_path)
            logger.debug("Using default decision engine (no clauses)")

        return self._engine

    def _find_claim_folder(self, workspace_path: Path, claim_id: str) -> Optional[Path]:
        """Find the claim folder for a given claim ID."""
        claims_dir = workspace_path / "claims"

        if (claims_dir / claim_id).exists():
            return claims_dir / claim_id

        for folder in claims_dir.iterdir():
            if folder.is_dir() and claim_id in folder.name:
                return folder

        return None

    def _get_next_version(self, claim_folder: Path, claim_run_id: str) -> int:
        """Determine the next dossier version number.

        Scans for existing decision_dossier_v*.json files in the claim run
        directory and returns the next version number.
        """
        run_dir = claim_folder / "claim_runs" / claim_run_id
        if not run_dir.exists():
            return 1

        existing = list(run_dir.glob("decision_dossier_v*.json"))
        if not existing:
            return 1

        max_version = 0
        for f in existing:
            try:
                # Extract version number from filename: decision_dossier_v3.json -> 3
                version_str = f.stem.split("_v")[-1]
                version = int(version_str)
                max_version = max(max_version, version)
            except (ValueError, IndexError):
                continue

        return max_version + 1

    def _load_coverage_analysis(
        self, claim_folder: Path, claim_run_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load coverage_analysis.json from the claim run directory."""
        run_dir = claim_folder / "claim_runs" / claim_run_id
        coverage_path = run_dir / "coverage_analysis.json"

        if not coverage_path.exists():
            return None

        try:
            with open(coverage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load coverage_analysis.json: {e}")
            return None

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute decision evaluation and return updated context.

        Flow:
        1. Check skip conditions (no facts, run_decision=False)
        2. Load decision engine from workspace
        3. Gather upstream results (screening, coverage, processing)
        4. Determine next version number
        5. Call engine.evaluate()
        6. Write decision_dossier_v{N}.json to claim run
        7. Store result in context.decision_result
        8. Non-fatal on exception (log warning, continue)

        Args:
            context: The claim context with upstream results.

        Returns:
            Updated context with decision_result set.
        """
        context.current_stage = self.name
        context.notify_stage_update(self.name, "running")
        start = time.time()

        # Skip if decision disabled
        if not getattr(context.stage_config, "run_decision", True):
            logger.info(
                f"Decision skipped for claim {context.claim_id}: run_decision=False"
            )
            context.timings.decision_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        # Skip if no facts to evaluate
        if context.aggregated_facts is None:
            logger.info(
                f"Decision skipped for claim {context.claim_id}: no aggregated facts"
            )
            context.timings.decision_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        logger.info(f"Running decision evaluation for claim {context.claim_id}")

        try:
            # Get engine for this workspace
            engine = self._get_engine(context.workspace_path)

            # Gather upstream results
            screening_result = context.screening_result
            processing_result = context.processing_result

            # Load coverage analysis from disk (not stored in context)
            coverage_analysis = None
            claim_folder = self._find_claim_folder(
                context.workspace_path, context.claim_id
            )
            if claim_folder:
                coverage_analysis = self._load_coverage_analysis(
                    claim_folder, context.run_id
                )

            # Apply coverage overrides to coverage data (mirrors
            # DecisionDossierService.evaluate_with_assumptions logic)
            coverage_overrides = getattr(context, "coverage_overrides", None) or {}
            if coverage_overrides and coverage_analysis:
                import copy

                coverage_analysis = copy.deepcopy(coverage_analysis)
                line_items = coverage_analysis.get("line_items", [])
                for key, is_covered in coverage_overrides.items():
                    if key.startswith("item_"):
                        try:
                            idx = int(key[5:])
                            if 0 <= idx < len(line_items):
                                item = line_items[idx]
                                total_price = float(item.get("total_price", 0) or 0)
                                if is_covered:
                                    item["coverage_status"] = "covered"
                                    item["covered_amount"] = total_price
                                    item["not_covered_amount"] = 0
                                else:
                                    item["coverage_status"] = "not_covered"
                                    item["covered_amount"] = 0
                                    item["not_covered_amount"] = total_price
                        except (ValueError, IndexError):
                            pass

            # Determine next version
            next_version = 1
            if claim_folder:
                next_version = self._get_next_version(claim_folder, context.run_id)

            # Run evaluation
            dossier = engine.evaluate(
                claim_id=context.claim_id,
                aggregated_facts=context.aggregated_facts,
                screening_result=screening_result,
                coverage_analysis=coverage_analysis,
                processing_result=processing_result,
                coverage_overrides=coverage_overrides or None,
            )

            # Convert Pydantic model to dict if needed
            # mode="json" ensures enums serialize as strings, not "Enum.VALUE"
            if hasattr(dossier, "model_dump"):
                dossier = dossier.model_dump(mode="json")

            # Set version
            dossier["version"] = next_version

            # Write decision_dossier_v{N}.json
            if claim_folder:
                try:
                    storage = ClaimRunStorage(claim_folder)
                    filename = f"decision_dossier_v{next_version}.json"
                    storage.write_to_claim_run(
                        context.run_id, filename, dossier
                    )
                    logger.info(
                        f"Wrote {filename} for claim {context.claim_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to write decision dossier: {e}")

            # Store in context
            context.decision_result = dossier

            # Log summary
            verdict = dossier.get("claim_verdict", "UNKNOWN")
            n_clauses = len(dossier.get("clause_evaluations", []))
            n_failed = len(dossier.get("failed_clauses", []))
            logger.info(
                f"Decision complete for {context.claim_id}: "
                f"verdict={verdict}, "
                f"{n_clauses} clauses evaluated, "
                f"{n_failed} triggered"
            )

            context.notify_stage_update(self.name, "complete")

        except Exception as e:
            logger.error(f"Decision failed for {context.claim_id}: {e}")
            # Decision failure is non-fatal — continue
            context.notify_stage_update(self.name, "warning")
            logger.warning("Continuing without decision results")

        # Record timing
        elapsed_ms = int((time.time() - start) * 1000)
        context.timings.decision_ms = elapsed_ms

        return context
