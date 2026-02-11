"""Rich-based progress reporting — replaces tqdm-based utils/progress.py.

Provides:
- RichProgressReporter: For assess command (claims-level tracking with stages).
- RichClaimProgress: For pipeline command (per-document per-stage tracking).

Both use Rich Progress + Live for clean output that doesn't corrupt logs.
"""

import logging
import sys
import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    MofNCompleteColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class ProgressMode(Enum):
    """Progress reporting mode."""
    PROGRESS = "progress"
    LOGS = "logs"
    QUIET = "quiet"
    VERBOSE = "verbose"


class RichProgressReporter:
    """Unified progress reporting for assess command using Rich.

    Drop-in replacement for utils.progress.ProgressReporter with the same API.
    Thread-safe for parallel assess.
    """

    def __init__(self, mode: ProgressMode = ProgressMode.PROGRESS, parallel: int = 1):
        self.mode = mode
        self.parallel = parallel
        self._console = Console(stderr=True)
        self._progress: Optional[Progress] = None
        self._claims_task = None
        self._stage_task = None
        self._detail_task = None
        self._current_claim: Optional[str] = None
        self._lock = threading.Lock()

        self._configure_logging()

    def _configure_logging(self) -> None:
        """Configure logging level based on mode."""
        loggers = [
            logging.getLogger("context_builder"),
            logging.getLogger("workspace_screener"),
            # Dynamically-loaded workspace engines use this module name
            logging.getLogger("workspace_decision_engine"),
        ]

        level_map = {
            ProgressMode.PROGRESS: logging.WARNING,
            ProgressMode.QUIET: logging.ERROR,
            ProgressMode.VERBOSE: logging.DEBUG,
            ProgressMode.LOGS: logging.INFO,
        }
        level = level_map.get(self.mode, logging.INFO)
        for lg in loggers:
            lg.setLevel(level)

    def write(self, msg: str) -> None:
        """Write a message without breaking progress bars."""
        with self._lock:
            if self._progress and self._progress.live.is_started:
                self._progress.console.print(msg)
            elif self.mode != ProgressMode.QUIET:
                self._console.print(msg)

    def start_claims(self, claim_ids: List[str]) -> None:
        """Initialize the main claims progress bar."""
        if self.mode == ProgressMode.QUIET:
            return

        if self.mode == ProgressMode.LOGS:
            self._console.print(f"\n[bold]Processing {len(claim_ids)} claims[/bold]")
            return

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            transient=True,
        )
        self._progress.start()
        self._claims_task = self._progress.add_task("Claims", total=len(claim_ids))

    def start_stage(self, claim_id: str, stage: str, total_steps: int = 0) -> None:
        """Start a new processing stage for a claim."""
        if self.parallel > 1:
            return

        self._current_claim = claim_id

        if self.mode == ProgressMode.LOGS:
            self._console.print(f"  [{claim_id}] {stage}...")
            return

        if not self._progress or self.mode == ProgressMode.QUIET:
            return

        # Remove old stage/detail tasks
        self._close_detail_task()
        self._close_stage_task()

        self._stage_task = self._progress.add_task(
            f"{claim_id}: {stage}",
            total=total_steps or 1,
        )

    def start_detail(self, total: int, desc: str = "LLM calls", unit: str = "call") -> None:
        """Start a detail-level progress bar for sub-operations."""
        if self.parallel > 1:
            return

        self._close_detail_task()

        if not self._progress or self.mode in (ProgressMode.LOGS, ProgressMode.QUIET):
            return

        self._detail_task = self._progress.add_task(f"  {desc}", total=total)

    def update_detail(self, n: int = 1) -> None:
        """Update the detail progress bar."""
        if self._progress and self._detail_task is not None:
            self._progress.advance(self._detail_task, n)

    def update_stage(self, n: int = 1) -> None:
        """Update the stage progress bar."""
        if self._progress and self._stage_task is not None:
            self._progress.advance(self._stage_task, n)

    def complete_stage(self) -> None:
        """Mark the current stage as complete."""
        self._close_detail_task()
        self._close_stage_task()

    def complete_claim(
        self,
        claim_id: str,
        decision: str,
        confidence: Optional[float] = None,
        payout: Optional[float] = None,
        gate: Optional[str] = None,
        error: Optional[str] = None,
        confidence_band: Optional[str] = None,
    ) -> None:
        """Mark a claim as complete and show summary. Thread-safe.

        Operations are done atomically under a single lock to prevent
        Rich's refresh timer from rendering intermediate states (e.g.
        progress bars without the stage task but before the result line).
        The result is buffered FIRST so that the next Live refresh
        renders it alongside the updated bars.
        """
        if error:
            msg = f"[red]✗[/red] {claim_id}: FAILED -- {error}"
        else:
            parts = [f"[green]✓[/green] {claim_id}: {decision}"]
            if confidence is not None:
                pct = f"{int(confidence * 100)}%"
                if confidence_band:
                    pct += f" ({confidence_band})"
                parts.append(pct)
            if payout is not None:
                parts.append(f"CHF {payout:,.2f}")
            if gate:
                parts.append(f"gate={gate}")
            msg = " | ".join(parts)

        with self._lock:
            # 1. Buffer the result line FIRST — Rich queues it for the
            #    next Live refresh, so it appears above the progress bars.
            if self._progress and self._progress.live.is_started:
                self._progress.console.print(msg)
            elif self.mode != ProgressMode.QUIET:
                self._console.print(msg)

            # 2. NOW clean up stage/detail tasks and advance the counter.
            #    Any refresh that fires after this shows updated bars
            #    with the result line already rendered above.
            if self.parallel <= 1 and self._progress:
                if self._detail_task is not None:
                    self._progress.remove_task(self._detail_task)
                    self._detail_task = None
                if self._stage_task is not None:
                    self._progress.remove_task(self._stage_task)
                    self._stage_task = None

            if self._progress and self._claims_task is not None:
                self._progress.advance(self._claims_task, 1)

    def finish(self) -> None:
        """Close all progress bars and clean up."""
        self._close_detail_task()
        self._close_stage_task()
        if self._progress:
            self._progress.stop()
            self._progress = None

    def _close_detail_task(self) -> None:
        if self._progress and self._detail_task is not None:
            self._progress.remove_task(self._detail_task)
            self._detail_task = None

    def _close_stage_task(self) -> None:
        if self._progress and self._stage_task is not None:
            self._progress.remove_task(self._stage_task)
            self._stage_task = None

    def create_callback(self) -> Callable[[int], None]:
        """Create a callback function for updating detail progress."""
        def callback(n: int = 1) -> None:
            self.update_detail(n)
        return callback

    def __enter__(self) -> "RichProgressReporter":
        return self

    def __exit__(self, *args) -> None:
        self.finish()


class RichClaimProgress:
    """Per-claim progress display for pipeline command using Rich.

    Replaces tqdm-based ClaimProgressDisplay.
    Tracks progress per stage completion (4 docs x 3 stages = 12 steps).
    """

    STAGE_NAME_MAP = {
        "ingestion": "ingest",
        "classification": "classify",
        "extraction": "extract",
    }

    def __init__(self, claim_id: str, doc_count: int, stages: List[str],
                 quiet: bool = False, verbose: bool = False):
        self.claim_id = claim_id
        self.doc_count = doc_count
        self.stages = set(stages)
        self.stage_count = len(stages)
        self.total_steps = doc_count * self.stage_count
        self.quiet = quiet
        self.verbose = verbose
        self._console = Console(stderr=True)
        self._progress: Optional[Progress] = None
        self._task = None
        self.current_filename: Optional[str] = None
        self._configure_logging()

    def _configure_logging(self) -> None:
        """Suppress INFO logs during progress display."""
        if self.verbose:
            return
        level = logging.ERROR if self.quiet else logging.WARNING
        for name in (
            "context_builder",
            "workspace_screener",
            "workspace_decision_engine",
        ):
            logging.getLogger(name).setLevel(level)

    def _restore_logging(self) -> None:
        """Restore logger levels after progress display ends."""
        if self.verbose:
            return
        for name in (
            "context_builder",
            "workspace_screener",
            "workspace_decision_engine",
        ):
            logging.getLogger(name).setLevel(logging.INFO)

    def start(self) -> None:
        """Print claim header and initialize progress bar."""
        self._console.print(f"\n[bold]Processing claim: {self.claim_id}[/bold]")
        self._progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            transient=False,
        )
        self._progress.start()
        self._task = self._progress.add_task("starting...", total=self.total_steps)

    def start_document(self, filename: str, doc_id: str) -> None:
        """Called when starting to process a new document."""
        self.current_filename = filename
        if len(filename) > 35:
            filename = filename[:32] + "..."
        if self._progress and self._task is not None:
            self._progress.update(self._task, description=filename)

    def on_phase_start(self, phase: str) -> None:
        """Called when a phase starts."""
        cli_phase = self.STAGE_NAME_MAP.get(phase, phase)
        if cli_phase not in self.stages:
            return

        if self._progress and self._task is not None and self.current_filename:
            filename = self.current_filename
            if len(filename) > 30:
                filename = filename[:27] + "..."
            self._progress.update(self._task, description=f"{filename}: {phase}")

    def on_phase_end(self, phase: str, status: str = "success") -> None:
        """Called when a phase ends — advance the progress bar."""
        if self._progress and self._task is not None:
            cli_phase = self.STAGE_NAME_MAP.get(phase, phase)
            if cli_phase in self.stages:
                self._progress.advance(self._task, 1)

    def complete_document(self, timings=None, status="success", doc_type=None, error=None) -> None:
        """Called when a document finishes all stages."""
        pass

    def finish(self) -> None:
        """Close progress bar for this claim."""
        if self._progress:
            self._progress.stop()
            self._progress = None
        self._restore_logging()


def create_progress_reporter(
    verbose: bool = False,
    quiet: bool = False,
    logs: bool = False,
    parallel: int = 1,
) -> RichProgressReporter:
    """Create a progress reporter from CLI flags."""
    if quiet:
        mode = ProgressMode.QUIET
    elif verbose:
        mode = ProgressMode.VERBOSE
    elif logs:
        mode = ProgressMode.LOGS
    else:
        mode = ProgressMode.PROGRESS

    return RichProgressReporter(mode=mode, parallel=parallel)
