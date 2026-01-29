"""Progress reporting utilities for CLI operations.

This module provides a unified progress reporting system using tqdm,
designed for long-running pipeline operations like claim assessment.

Usage:
    from context_builder.utils.progress import ProgressReporter, ProgressMode

    # Create reporter (defaults to progress bars)
    reporter = ProgressReporter(mode=ProgressMode.PROGRESS)

    # Or use logs mode for verbose output
    reporter = ProgressReporter(mode=ProgressMode.LOGS)

    # Track claims processing
    reporter.start_claims(claim_ids)
    for claim_id in claim_ids:
        reporter.start_stage(claim_id, "Reconciliation")
        # ... do work ...
        reporter.complete_claim(claim_id, "APPROVE")
    reporter.finish()
"""

import logging
import sys
import threading
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Try to import tqdm, fall back to no-op if not available
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None  # type: ignore


class ProgressMode(Enum):
    """Progress reporting mode."""

    PROGRESS = "progress"  # Show progress bars, suppress INFO logs
    LOGS = "logs"          # Show detailed logs, no progress bars
    QUIET = "quiet"        # Minimal output
    VERBOSE = "verbose"    # Both progress bars and debug logs


class NoOpProgressBar:
    """No-op progress bar for when tqdm is unavailable or disabled."""

    def __init__(self, *args, **kwargs):
        self.n = 0
        self.total = kwargs.get("total", 0)

    def update(self, n: int = 1) -> None:
        self.n += n

    def set_description(self, desc: str) -> None:
        pass

    def set_postfix(self, **kwargs) -> None:
        pass

    def close(self) -> None:
        pass

    def refresh(self) -> None:
        pass

    @staticmethod
    def write(msg: str) -> None:
        print(msg)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ProgressReporter:
    """Unified progress reporting for CLI operations.

    Provides three levels of progress tracking:
    1. Claims level - overall progress through claims
    2. Stage level - current processing stage (reconciliation, screening, etc.)
    3. Detail level - sub-operations like LLM calls

    In PROGRESS mode, INFO logs are suppressed and only WARNING+ are shown.
    In LOGS mode, all logs are shown and progress bars are disabled.

    Thread Safety:
        When parallel > 1, the reporter uses a simplified thread-safe mode
        that only shows claim completions (no nested stage/detail bars).
    """

    def __init__(self, mode: ProgressMode = ProgressMode.PROGRESS, parallel: int = 1):
        """Initialize the progress reporter.

        Args:
            mode: Progress reporting mode (PROGRESS, LOGS, QUIET, VERBOSE)
            parallel: Number of parallel workers (1 = sequential, >1 = parallel mode)
        """
        self.mode = mode
        self.parallel = parallel
        self._claims_bar: Optional[Any] = None
        self._stage_bar: Optional[Any] = None
        self._detail_bar: Optional[Any] = None
        self._current_claim: Optional[str] = None
        self._current_stage: Optional[str] = None
        self._lock = threading.Lock()  # Thread safety for parallel mode

        # Configure logging based on mode
        self._configure_logging()

    def _configure_logging(self) -> None:
        """Configure logging level based on mode."""
        cb_logger = logging.getLogger("context_builder")

        if self.mode == ProgressMode.PROGRESS:
            # Suppress INFO logs, only show WARNING and above
            cb_logger.setLevel(logging.WARNING)
        elif self.mode == ProgressMode.QUIET:
            # Only show errors
            cb_logger.setLevel(logging.ERROR)
        elif self.mode == ProgressMode.VERBOSE:
            # Show everything including debug
            cb_logger.setLevel(logging.DEBUG)
        else:  # LOGS mode
            # Normal logging (INFO and above)
            cb_logger.setLevel(logging.INFO)

    def _create_bar(self, **kwargs) -> Any:
        """Create a progress bar or no-op fallback."""
        if not TQDM_AVAILABLE or self.mode in (ProgressMode.LOGS, ProgressMode.QUIET):
            return NoOpProgressBar(**kwargs)

        # Add common defaults
        kwargs.setdefault("file", sys.stderr)
        kwargs.setdefault("dynamic_ncols", True)
        kwargs.setdefault("miniters", 1)

        return tqdm(**kwargs)

    def write(self, msg: str) -> None:
        """Write a message without breaking progress bars.

        Use this for important status messages, errors, or results.
        Thread-safe when parallel > 1.
        """
        with self._lock:
            if TQDM_AVAILABLE and self.mode == ProgressMode.PROGRESS:
                tqdm.write(msg, file=sys.stderr)
            elif self.mode != ProgressMode.QUIET:
                print(msg, file=sys.stderr)

    def start_claims(self, claim_ids: List[str]) -> None:
        """Initialize the main claims progress bar.

        Args:
            claim_ids: List of claim IDs to process
        """
        if self.mode == ProgressMode.QUIET:
            return

        if self.mode == ProgressMode.LOGS:
            print(f"\n[*] Processing {len(claim_ids)} claims", file=sys.stderr)
            return

        self._claims_bar = self._create_bar(
            total=len(claim_ids),
            desc="Claims",
            unit="claim",
            position=0,
            leave=True,
            bar_format="{desc}: {bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        )

    def start_stage(
        self,
        claim_id: str,
        stage: str,
        total_steps: int = 0,
    ) -> None:
        """Start a new processing stage for a claim.

        Args:
            claim_id: Current claim being processed
            stage: Stage name (e.g., "Reconciliation", "Screening", "Assessment")
            total_steps: Optional total number of steps in this stage
        """
        # In parallel mode, skip nested progress bars (not thread-safe)
        if self.parallel > 1:
            return

        self._current_claim = claim_id
        self._current_stage = stage

        # Close previous stage/detail bars
        self._close_detail_bar()
        self._close_stage_bar()

        if self.mode == ProgressMode.LOGS:
            print(f"  [{claim_id}] {stage}...", file=sys.stderr)
            return

        if self.mode == ProgressMode.QUIET:
            return

        # Determine bar format based on whether we have steps
        if total_steps > 0:
            bar_format = "[{desc}] {bar} {n_fmt}/{total_fmt}"
        else:
            bar_format = "[{desc}]"

        self._stage_bar = self._create_bar(
            total=total_steps or 1,
            desc=f"{claim_id}: {stage}",
            position=1,
            leave=False,
            bar_format=bar_format,
        )

    def start_detail(
        self,
        total: int,
        desc: str = "LLM calls",
        unit: str = "call",
    ) -> None:
        """Start a detail-level progress bar for sub-operations.

        Args:
            total: Total number of operations
            desc: Description of the operation
            unit: Unit name for the progress bar
        """
        # In parallel mode, skip nested progress bars (not thread-safe)
        if self.parallel > 1:
            return

        self._close_detail_bar()

        if self.mode in (ProgressMode.LOGS, ProgressMode.QUIET):
            return

        self._detail_bar = self._create_bar(
            total=total,
            desc=f"  {desc}",
            position=2,
            leave=False,
            unit=unit,
            bar_format="{desc}: {bar} {n_fmt}/{total_fmt} [{rate_fmt}]",
        )

    def update_detail(self, n: int = 1) -> None:
        """Update the detail progress bar.

        Args:
            n: Number of steps to increment
        """
        if self._detail_bar:
            self._detail_bar.update(n)

    def update_stage(self, n: int = 1) -> None:
        """Update the stage progress bar.

        Args:
            n: Number of steps to increment
        """
        if self._stage_bar:
            self._stage_bar.update(n)

    def set_stage_postfix(self, **kwargs) -> None:
        """Set postfix info on the stage bar.

        Args:
            **kwargs: Key-value pairs to display
        """
        if self._stage_bar and hasattr(self._stage_bar, "set_postfix"):
            self._stage_bar.set_postfix(**kwargs)

    def complete_stage(self) -> None:
        """Mark the current stage as complete."""
        self._close_detail_bar()
        if self._stage_bar:
            # Fill remaining progress
            remaining = self._stage_bar.total - self._stage_bar.n
            if remaining > 0:
                self._stage_bar.update(remaining)
        self._close_stage_bar()

    def complete_claim(
        self,
        claim_id: str,
        decision: str,
        confidence: Optional[float] = None,
        payout: Optional[float] = None,
        gate: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Mark a claim as complete and show summary.

        Thread-safe when parallel > 1.

        Args:
            claim_id: Claim that was processed
            decision: Assessment decision (APPROVE, REJECT, etc.)
            confidence: Optional confidence score (0-1)
            payout: Optional payout amount
            gate: Optional quality gate status
            error: Optional error message if failed
        """
        # In parallel mode, skip stage cleanup (handled differently)
        if self.parallel <= 1:
            self.complete_stage()

        # Build result message first (no lock needed)
        if error:
            msg = f"[X] {claim_id}: FAILED - {error}"
        else:
            parts = [f"[OK] {claim_id}: {decision}"]
            if confidence is not None:
                parts.append(f"{int(confidence * 100)}%")
            if payout is not None:
                parts.append(f"CHF {payout:,.2f}")
            if gate:
                parts.append(f"gate={gate}")
            msg = " | ".join(parts)

        # Thread-safe update
        with self._lock:
            if self._claims_bar:
                self._claims_bar.update(1)

        self.write(msg)

    def finish(self) -> None:
        """Close all progress bars and clean up."""
        self._close_detail_bar()
        self._close_stage_bar()
        self._close_claims_bar()

    def _close_detail_bar(self) -> None:
        """Close the detail progress bar if open."""
        if self._detail_bar:
            self._detail_bar.close()
            self._detail_bar = None

    def _close_stage_bar(self) -> None:
        """Close the stage progress bar if open."""
        if self._stage_bar:
            self._stage_bar.close()
            self._stage_bar = None

    def _close_claims_bar(self) -> None:
        """Close the claims progress bar if open."""
        if self._claims_bar:
            self._claims_bar.close()
            self._claims_bar = None

    def create_callback(self) -> Callable[[int], None]:
        """Create a callback function for updating detail progress.

        Returns:
            Callback function that accepts increment value
        """
        def callback(n: int = 1) -> None:
            self.update_detail(n)
        return callback

    def __enter__(self) -> "ProgressReporter":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit - clean up progress bars."""
        self.finish()


# Convenience function for quick access
def create_progress_reporter(
    verbose: bool = False,
    quiet: bool = False,
    logs: bool = False,
    parallel: int = 1,
) -> ProgressReporter:
    """Create a progress reporter from CLI flags.

    Args:
        verbose: Enable verbose mode (progress + debug logs)
        quiet: Enable quiet mode (minimal output)
        logs: Enable logs mode (full logs, no progress bars)
        parallel: Number of parallel workers (1 = sequential)

    Returns:
        Configured ProgressReporter instance
    """
    if quiet:
        mode = ProgressMode.QUIET
    elif verbose:
        mode = ProgressMode.VERBOSE
    elif logs:
        mode = ProgressMode.LOGS
    else:
        mode = ProgressMode.PROGRESS

    return ProgressReporter(mode=mode, parallel=parallel)
