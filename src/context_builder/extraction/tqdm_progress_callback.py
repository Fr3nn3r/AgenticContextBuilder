"""
Tqdm-based progress callback implementation.

Provides progress reporting using tqdm progress bars for batch extraction.

Single Responsibility: Update tqdm progress display based on extraction events.
"""

from typing import Optional
from context_builder.extraction.progress_callback import ProgressCallback

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class TqdmProgressCallback(ProgressCallback):
    """
    Progress callback that updates tqdm progress bar descriptions.

    Updates the file-level progress bar description to show:
    - Current policy name
    - Current chunk being processed (if chunked)
    - Current step (Extract/Lint/Refine, if provided)

    Example: "Policy: my_policy - Chunk 5/24 - Linting"
    """

    def __init__(
        self,
        file_progress_bar: Optional[any] = None,
        stage_progress_bar: Optional[any] = None
    ):
        """
        Initialize tqdm progress callback.

        Args:
            file_progress_bar: tqdm progress bar instance for file-level progress.
                              If None, callback becomes no-op.
            stage_progress_bar: tqdm progress bar instance for stage-level progress.
                               If None, stage progress is not displayed.
        """
        self.file_pbar = file_progress_bar
        self.stage_pbar = stage_progress_bar
        self.chunk_pbar = None  # Created dynamically when chunked processing starts
        self.current_policy = ""
        self.is_chunked = False

    def _update_description(
        self,
        policy_name: str,
        chunk_info: Optional[str] = None,
        step: Optional[str] = None
    ) -> None:
        """
        Update progress bar description with current status.

        Args:
            policy_name: Name of policy being processed
            chunk_info: Optional chunk info (e.g., "5/24")
            step: Optional step description (e.g., "Linting")
        """
        if not self.file_pbar or not HAS_TQDM:
            return

        # Build description parts
        parts = [f"Policy: {policy_name[:30]:<30}"]

        if chunk_info:
            parts.append(f"Chunk {chunk_info}")

        if step:
            parts.append(step)

        description = " - ".join(parts)

        # Update tqdm description
        self.file_pbar.set_description(description)

    def on_processing_start(self, total_chunks: int, policy_name: str) -> None:
        """
        Called when chunked processing starts for a policy.

        Args:
            total_chunks: Total number of chunks
            policy_name: Name of policy being processed
        """
        self.current_policy = policy_name
        self.is_chunked = True

        # Create chunk progress bar dynamically
        if HAS_TQDM:
            self.chunk_pbar = tqdm(
                total=total_chunks,
                desc="Chunks",
                ncols=100,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}',
                leave=False  # Don't leave the bar after completion
            )

        # Update description to show we're starting
        self._update_description(policy_name, chunk_info=f"0/{total_chunks}")

    def on_chunk_start(
        self,
        chunk_index: int,
        total_chunks: int,
        policy_name: str,
        step: Optional[str] = None
    ) -> None:
        """
        Called when chunk processing starts.

        Args:
            chunk_index: Current chunk number (1-based)
            total_chunks: Total number of chunks
            policy_name: Name of policy being processed
            step: Optional step description (e.g., "Extracting", "Linting", "Refining")
        """
        self.current_policy = policy_name

        # Update chunk progress bar
        if self.chunk_pbar and HAS_TQDM:
            self.chunk_pbar.n = chunk_index - 1
            step_desc = f" - {step}" if step else ""
            self.chunk_pbar.set_description(f"Chunk {chunk_index}/{total_chunks}{step_desc}")
            self.chunk_pbar.refresh()

        # Update description with current chunk and step
        chunk_info = f"{chunk_index}/{total_chunks}"
        self._update_description(policy_name, chunk_info=chunk_info, step=step)

    def on_chunk_complete(
        self,
        chunk_index: int,
        total_chunks: int,
        policy_name: str
    ) -> None:
        """
        Called when chunk processing completes successfully.

        Args:
            chunk_index: Current chunk number (1-based)
            total_chunks: Total number of chunks
            policy_name: Name of policy being processed
        """
        # Update chunk progress bar
        if self.chunk_pbar and HAS_TQDM:
            self.chunk_pbar.n = chunk_index
            self.chunk_pbar.set_description(f"Chunk {chunk_index}/{total_chunks} - Done")
            self.chunk_pbar.refresh()

        # Update description to show chunk completed
        chunk_info = f"{chunk_index}/{total_chunks}"
        self._update_description(policy_name, chunk_info=chunk_info, step="Done")

    def on_chunk_error(
        self,
        chunk_index: int,
        total_chunks: int,
        policy_name: str,
        error: Exception
    ) -> None:
        """
        Called when chunk processing fails.

        Args:
            chunk_index: Current chunk number (1-based)
            total_chunks: Total number of chunks
            policy_name: Name of policy being processed
            error: Exception that occurred
        """
        # Update chunk progress bar
        if self.chunk_pbar and HAS_TQDM:
            self.chunk_pbar.set_description(f"Chunk {chunk_index}/{total_chunks} - ERROR")
            self.chunk_pbar.refresh()

        # Update description to show error
        chunk_info = f"{chunk_index}/{total_chunks}"
        self._update_description(policy_name, chunk_info=chunk_info, step="ERROR")

    def on_processing_complete(self, policy_name: str) -> None:
        """
        Called when all chunks have been processed for a policy.

        Args:
            policy_name: Name of policy being processed
        """
        # Close and cleanup chunk progress bar
        if self.chunk_pbar and HAS_TQDM:
            self.chunk_pbar.close()
            self.chunk_pbar = None

        # Clear chunk-specific info when policy completes
        self._update_description(policy_name)
        self.is_chunked = False

    def on_stage_start(
        self,
        stage_index: int,
        total_stages: int,
        stage_name: str
    ) -> None:
        """
        Called when a pipeline stage starts.

        Args:
            stage_index: Current stage number (1-based)
            total_stages: Total number of stages
            stage_name: Name of the stage (e.g., "Copying PDF", "Azure DI Acquisition")
        """
        if not self.stage_pbar or not HAS_TQDM:
            return

        # Update stage bar
        self.stage_pbar.n = stage_index - 1
        self.stage_pbar.set_description(f"Stage {stage_index}/{total_stages}: {stage_name}")
        self.stage_pbar.refresh()

    def on_stage_complete(
        self,
        stage_index: int,
        total_stages: int,
        stage_name: str
    ) -> None:
        """
        Called when a pipeline stage completes.

        Args:
            stage_index: Current stage number (1-based)
            total_stages: Total number of stages
            stage_name: Name of the stage
        """
        if not self.stage_pbar or not HAS_TQDM:
            return

        # Update stage bar to show completion
        self.stage_pbar.n = stage_index
        self.stage_pbar.set_description(f"Stage {stage_index}/{total_stages}: {stage_name}")
        self.stage_pbar.refresh()
