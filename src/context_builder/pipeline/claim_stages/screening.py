"""Screening stage for claim-level pipeline.

This stage runs deterministic checks on aggregated claim facts before
(or instead of) a full LLM assessment.  Screening is optional — workspaces
can opt-in by providing a screener module.

The stage:
1. Loads workspace-specific screener (if exists)
2. Runs deterministic checks (policy validity, mileage, coverage, etc.)
3. Produces ScreeningResult + optional CoverageAnalysisResult
4. Writes screening.json and coverage_analysis.json to claim run
5. Stores result in context for downstream stages

Pipeline flow:
    ReconciliationStage -> EnrichmentStage -> ScreeningStage -> ProcessingStage
"""

import importlib.util
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from context_builder.coverage.schemas import CoverageAnalysisResult
from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.schemas.reconciliation import ReconciliationReport
from context_builder.schemas.screening import ScreeningResult
from context_builder.storage.claim_run import ClaimRunStorage

logger = logging.getLogger(__name__)


# ── Utility functions ────────────────────────────────────────────────


def get_fact(facts: List[Dict], name: str) -> Optional[str]:
    """Get a fact value by name, with suffix match fallback.

    Tries exact match first, then suffix match for prefixed fact names
    (e.g., 'document_date' matches 'cost_estimate.document_date').

    Args:
        facts: List of fact dicts with 'name' and 'value' keys.
        name: Fact name to search for.

    Returns:
        Fact value string, or None if not found.
    """
    # Exact match first
    for f in facts:
        if f.get("name") == name:
            return f.get("value")
    # Suffix match (e.g., "document_date" matches "cost_estimate.document_date")
    for f in facts:
        fact_name = f.get("name", "")
        if fact_name.endswith("." + name):
            return f.get("value")
    return None


def get_structured_fact(facts: List[Dict], name: str) -> Optional[Any]:
    """Get a fact's structured_value by name, with suffix match fallback.

    Same lookup logic as get_fact but returns structured_value instead of value.

    Args:
        facts: List of fact dicts with 'name' and optional 'structured_value' keys.
        name: Fact name to search for.

    Returns:
        structured_value, or None if not found.
    """
    # Exact match first
    for f in facts:
        if f.get("name") == name:
            return f.get("structured_value")
    # Suffix match
    for f in facts:
        fact_name = f.get("name", "")
        if fact_name.endswith("." + name):
            return f.get("structured_value")
    return None


def parse_date(value: Optional[str]) -> Optional[date]:
    """Parse ISO (YYYY-MM-DD) and European (DD.MM.YYYY) date strings.

    Args:
        value: Date string or None.

    Returns:
        date object, or None if parsing fails.
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    # ISO format: YYYY-MM-DD
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, IndexError):
        pass
    # European format: DD.MM.YYYY
    try:
        return datetime.strptime(value[:10], "%d.%m.%Y").date()
    except (ValueError, IndexError):
        pass
    return None


def parse_int(value: Optional[str]) -> Optional[int]:
    """Parse numeric string to int (handles Swiss formatting like 74'359).

    Strips apostrophes, commas, and non-numeric suffixes.

    Args:
        value: Numeric string or None.

    Returns:
        Integer, or None if parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    # Remove common separators and whitespace
    cleaned = value.replace("'", "").replace(",", "").replace("\u2019", "").strip()
    # Extract leading number
    match = re.match(r"^[\d]+", cleaned)
    if match:
        return int(match.group())
    return None


def parse_float(value: Optional[str]) -> Optional[float]:
    """Parse numeric/percent string to float.

    Handles European formats where comma is decimal separator and
    space/apostrophe is thousands separator:
    - "300,00 CHF" → 300.0
    - "8 000,00 CHF" → 8000.0
    - "74'359.50" → 74359.5
    - "10 %" → 10.0

    Args:
        value: Numeric string or None.

    Returns:
        Float, or None if parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    # Remove currency/unit suffixes and whitespace
    cleaned = value.strip()

    # Remove thousands separators (space, apostrophe, right single quote)
    cleaned = cleaned.replace(" ", "").replace("'", "").replace("\u2019", "")

    # Handle European decimal comma: replace comma with period
    # But only if there's no period already (to avoid breaking "74359.50")
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")

    # Extract number (including decimal)
    match = re.search(r"([\d]+(?:\.[\d]+)?)", cleaned)
    if match:
        return float(match.group(1))
    return None


# ── Screener Protocol ────────────────────────────────────────────────


@runtime_checkable
class Screener(Protocol):
    """Protocol for workspace-specific screening implementations.

    Workspace screeners implement this protocol to provide custom
    deterministic checks, coverage analysis, and payout calculation.

    To create a screener for a workspace:
    1. Create {workspace}/config/screening/screener.py
    2. Define a class implementing this protocol
    3. The class must accept workspace_path in __init__
    """

    def screen(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        reconciliation_report: Optional[ReconciliationReport] = None,
        claim_run_id: Optional[str] = None,
        on_llm_start: Optional[Callable[[int], None]] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
    ) -> Tuple[ScreeningResult, Optional[CoverageAnalysisResult]]:
        """Run all screening checks and return results.

        Args:
            claim_id: Claim identifier.
            aggregated_facts: Enriched aggregated facts dict.
            reconciliation_report: Reconciliation report (for VIN conflicts etc.).
            claim_run_id: Claim run ID for coverage analysis storage.
            on_llm_start: Optional callback when LLM calls start (total count).
            on_llm_progress: Optional callback for LLM progress (increment).

        Returns:
            Tuple of (ScreeningResult, CoverageAnalysisResult or None).
        """
        ...


# ── Default Screener ─────────────────────────────────────────────────


class DefaultScreener:
    """Default screener that produces an empty result (no checks).

    Used when no workspace-specific screener is configured.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def screen(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        reconciliation_report: Optional[ReconciliationReport] = None,
        claim_run_id: Optional[str] = None,
        on_llm_start: Optional[Callable[[int], None]] = None,
        on_llm_progress: Optional[Callable[[int], None]] = None,
    ) -> Tuple[ScreeningResult, Optional[CoverageAnalysisResult]]:
        """Return empty screening result with no checks."""
        result = ScreeningResult(
            claim_id=claim_id,
            screening_timestamp=datetime.utcnow().isoformat(),
        )
        return result, None


# ── Dynamic loader ───────────────────────────────────────────────────


def load_screener_from_workspace(workspace_path: Path) -> Optional[Screener]:
    """Discover and load screener from workspace config.

    Looks for {workspace}/config/screening/screener.py and loads the
    first class that implements the Screener protocol (has a 'screen' method).

    Args:
        workspace_path: Path to the workspace root.

    Returns:
        Instantiated screener or None if not found.
    """
    screener_path = workspace_path / "config" / "screening" / "screener.py"

    if not screener_path.exists():
        logger.debug(f"No screener found at {screener_path}")
        return None

    try:
        # Dynamic import of workspace screener module
        spec = importlib.util.spec_from_file_location(
            "workspace_screener", screener_path
        )
        if spec is None or spec.loader is None:
            logger.warning(f"Could not load spec for {screener_path}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find the screener class (first class with a 'screen' method)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and attr_name != "Screener"
                and hasattr(attr, "screen")
            ):
                # Instantiate with workspace_path
                screener = attr(workspace_path)
                logger.info(f"Loaded screener: {attr_name} from {screener_path}")
                return screener

        logger.warning(f"No Screener implementation found in {screener_path}")
        return None

    except Exception as e:
        logger.error(f"Failed to load screener from {screener_path}: {e}")
        return None


# ── Screening Stage ──────────────────────────────────────────────────


@dataclass
class ScreeningStage:
    """Screening stage: loads workspace screener and runs deterministic checks.

    This stage:
    - Loads workspace-specific screener (if exists)
    - Runs deterministic checks on aggregated facts
    - Writes screening.json and coverage_analysis.json to claim run
    - Stores result in context for downstream stages

    The stage is non-fatal — exceptions are caught and logged as warnings,
    allowing the pipeline to continue with assessment.
    """

    name: str = "screening"
    _screener: Optional[Screener] = field(default=None, repr=False)
    _workspace_path: Optional[Path] = field(default=None, repr=False)

    def _get_screener(self, workspace_path: Path) -> Screener:
        """Get or load the screener for this workspace (with caching)."""
        if self._screener is not None and self._workspace_path == workspace_path:
            return self._screener

        self._workspace_path = workspace_path
        self._screener = load_screener_from_workspace(workspace_path)

        if self._screener is None:
            self._screener = DefaultScreener(workspace_path)
            logger.debug("Using default screener (no checks)")

        return self._screener

    def _load_reconciliation_report(
        self, workspace_path: Path, claim_id: str
    ) -> Optional[ReconciliationReport]:
        """Load reconciliation report from claim context directory."""
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

        if (claims_dir / claim_id).exists():
            return claims_dir / claim_id

        for folder in claims_dir.iterdir():
            if folder.is_dir() and claim_id in folder.name:
                return folder

        return None

    def _write_screening_result(
        self,
        workspace_path: Path,
        claim_id: str,
        claim_run_id: str,
        screening_result: ScreeningResult,
    ) -> Optional[Path]:
        """Write screening.json to the claim run directory."""
        claim_folder = self._find_claim_folder(workspace_path, claim_id)
        if not claim_folder:
            logger.error(f"Cannot write screening result: claim folder not found for {claim_id}")
            return None

        try:
            storage = ClaimRunStorage(claim_folder)
            return storage.write_to_claim_run(
                claim_run_id,
                "screening.json",
                screening_result.model_dump(mode="json"),
            )
        except Exception as e:
            logger.error(f"Failed to write screening.json: {e}")
            return None

    def _write_coverage_analysis(
        self,
        workspace_path: Path,
        claim_id: str,
        claim_run_id: str,
        coverage_result: CoverageAnalysisResult,
    ) -> Optional[Path]:
        """Write coverage_analysis.json to the claim run directory."""
        claim_folder = self._find_claim_folder(workspace_path, claim_id)
        if not claim_folder:
            logger.error(f"Cannot write coverage analysis: claim folder not found for {claim_id}")
            return None

        try:
            storage = ClaimRunStorage(claim_folder)
            return storage.write_to_claim_run(
                claim_run_id,
                "coverage_analysis.json",
                coverage_result.model_dump(mode="json"),
            )
        except Exception as e:
            logger.error(f"Failed to write coverage_analysis.json: {e}")
            return None

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute screening and return updated context.

        Flow:
        1. Check skip conditions (no facts, run_screening=False)
        2. Load screener from workspace
        3. Load reconciliation report (for VIN conflicts)
        4. Call screener.screen() -> (ScreeningResult, CoverageAnalysisResult)
        5. Write screening.json to claim run
        6. Write coverage_analysis.json to claim run (if present)
        7. Store result in context.screening_result
        8. Non-fatal on exception (log warning, continue)

        Args:
            context: The claim context with aggregated_facts loaded.

        Returns:
            Updated context with screening_result set.
        """
        context.current_stage = self.name
        context.notify_stage_update(self.name, "running")
        start = time.time()

        # Skip if screening disabled
        if not context.stage_config.run_screening:
            logger.info(f"Screening skipped for claim {context.claim_id}: run_screening=False")
            context.timings.screening_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        # Skip if no facts to screen
        if context.aggregated_facts is None:
            logger.info(f"Screening skipped for claim {context.claim_id}: no aggregated facts")
            context.timings.screening_ms = 0
            context.notify_stage_update(self.name, "skipped")
            return context

        logger.info(f"Running screening for claim {context.claim_id}")

        try:
            # Get screener for this workspace
            screener = self._get_screener(context.workspace_path)

            # Use reconciliation report from pipeline context (preferred),
            # falling back to disk for standalone screening runs
            report = context.reconciliation_report
            if report is None:
                report = self._load_reconciliation_report(
                    context.workspace_path, context.claim_id
                )

            # Run screening
            screening_result, coverage_result = screener.screen(
                claim_id=context.claim_id,
                aggregated_facts=context.aggregated_facts,
                reconciliation_report=report,
                claim_run_id=context.run_id,
                on_llm_start=context.on_llm_start,
                on_llm_progress=context.on_llm_progress,
            )

            # Write screening.json
            self._write_screening_result(
                context.workspace_path,
                context.claim_id,
                context.run_id,
                screening_result,
            )

            # Write coverage_analysis.json if present
            if coverage_result is not None:
                self._write_coverage_analysis(
                    context.workspace_path,
                    context.claim_id,
                    context.run_id,
                    coverage_result,
                )

            # Store result in context
            context.screening_result = screening_result.model_dump(mode="json")

            # Log summary
            logger.info(
                f"Screening complete for {context.claim_id}: "
                f"{screening_result.checks_passed} passed, "
                f"{screening_result.checks_failed} failed, "
                f"{screening_result.checks_inconclusive} inconclusive, "
                f"auto_reject={screening_result.auto_reject}"
            )

            context.notify_stage_update(self.name, "complete")

        except Exception as e:
            logger.error(f"Screening failed for {context.claim_id}: {e}")
            # Screening failure is non-fatal — continue with assessment
            context.notify_stage_update(self.name, "warning")
            logger.warning("Continuing without screening results")

        # Record timing
        elapsed_ms = int((time.time() - start) * 1000)
        context.timings.screening_ms = elapsed_ms

        return context
