"""
Progress callback interface for extraction processes.

Follows the Dependency Inversion Principle:
- High-level extraction code depends on this abstraction (ProgressCallback)
- Low-level UI code (tqdm, CLI) implements concrete callbacks
- Zero coupling between extraction logic and UI library

Single Responsibility: Define the contract for progress reporting.
"""

from abc import ABC, abstractmethod
from typing import Optional


class ProgressCallback(ABC):
    """
    Abstract base class for progress reporting during extraction.

    Allows extraction code to report progress without depending on
    specific UI implementations (tqdm, logging, GUI, etc.).
    """

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def on_processing_start(self, total_chunks: int, policy_name: str) -> None:
        """
        Called when chunked processing starts for a policy.

        Args:
            total_chunks: Total number of chunks
            policy_name: Name of policy being processed
        """
        pass

    @abstractmethod
    def on_processing_complete(self, policy_name: str) -> None:
        """
        Called when all chunks have been processed for a policy.

        Args:
            policy_name: Name of policy being processed
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass


class NoOpProgressCallback(ProgressCallback):
    """
    No-operation progress callback for testing or when progress reporting is disabled.

    Follows the Null Object Pattern: Provides safe default behavior.
    """

    def on_chunk_start(
        self,
        chunk_index: int,
        total_chunks: int,
        policy_name: str,
        step: Optional[str] = None
    ) -> None:
        """Do nothing."""
        pass

    def on_chunk_complete(
        self,
        chunk_index: int,
        total_chunks: int,
        policy_name: str
    ) -> None:
        """Do nothing."""
        pass

    def on_chunk_error(
        self,
        chunk_index: int,
        total_chunks: int,
        policy_name: str,
        error: Exception
    ) -> None:
        """Do nothing."""
        pass

    def on_processing_start(self, total_chunks: int, policy_name: str) -> None:
        """Do nothing."""
        pass

    def on_processing_complete(self, policy_name: str) -> None:
        """Do nothing."""
        pass

    def on_stage_start(
        self,
        stage_index: int,
        total_stages: int,
        stage_name: str
    ) -> None:
        """Do nothing."""
        pass

    def on_stage_complete(
        self,
        stage_index: int,
        total_stages: int,
        stage_name: str
    ) -> None:
        """Do nothing."""
        pass
