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

    def __init__(self, file_progress_bar: Optional[any] = None):
        """
        Initialize tqdm progress callback.

        Args:
            file_progress_bar: tqdm progress bar instance for file-level progress.
                              If None, callback becomes no-op.
        """
        self.file_pbar = file_progress_bar
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
        # Update description to show error
        chunk_info = f"{chunk_index}/{total_chunks}"
        self._update_description(policy_name, chunk_info=chunk_info, step="ERROR")

    def on_processing_complete(self, policy_name: str) -> None:
        """
        Called when all chunks have been processed for a policy.

        Args:
            policy_name: Name of policy being processed
        """
        # Clear chunk-specific info when policy completes
        self._update_description(policy_name)
        self.is_chunked = False
