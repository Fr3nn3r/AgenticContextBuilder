# intake/processors/content_support/services/processing_tracker.py
# Processing time tracking and metrics collection
# Provides context managers and utilities for performance monitoring

import time
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ProcessingMetrics:
    """Container for processing metrics."""

    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
    status: str = "in_progress"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "success", error_message: Optional[str] = None):
        """Mark processing as complete and calculate duration."""
        self.end_time = time.time()
        self.duration_seconds = self.end_time - self.start_time
        self.status = status
        self.error_message = error_message


class ProcessingTracker:
    """Tracks processing time and collects metrics."""

    def __init__(self):
        """Initialize the processing tracker."""
        self.logger = logging.getLogger(__name__)
        self.metrics_history = []

    def start_tracking(self, operation_name: str) -> ProcessingMetrics:
        """
        Start tracking a new operation.

        Args:
            operation_name: Name of the operation being tracked

        Returns:
            ProcessingMetrics instance
        """
        metrics = ProcessingMetrics(metadata={"operation": operation_name})
        self.logger.debug(f"Started tracking: {operation_name}")
        return metrics

    def record_metrics(self, metrics: ProcessingMetrics):
        """
        Record completed metrics.

        Args:
            metrics: Completed metrics to record
        """
        self.metrics_history.append(metrics)
        operation = metrics.metadata.get("operation", "unknown")
        self.logger.info(
            f"Operation '{operation}' completed in {metrics.duration_seconds:.2f}s "
            f"with status: {metrics.status}"
        )

    def get_average_duration(self, operation_name: Optional[str] = None) -> float:
        """
        Get average duration for operations.

        Args:
            operation_name: Optional specific operation to filter by

        Returns:
            Average duration in seconds
        """
        relevant_metrics = [
            m for m in self.metrics_history
            if m.duration_seconds is not None and
            (operation_name is None or m.metadata.get("operation") == operation_name)
        ]

        if not relevant_metrics:
            return 0.0

        total_duration = sum(m.duration_seconds for m in relevant_metrics)
        return total_duration / len(relevant_metrics)

    def get_success_rate(self, operation_name: Optional[str] = None) -> float:
        """
        Get success rate for operations.

        Args:
            operation_name: Optional specific operation to filter by

        Returns:
            Success rate as percentage (0-100)
        """
        relevant_metrics = [
            m for m in self.metrics_history
            if operation_name is None or m.metadata.get("operation") == operation_name
        ]

        if not relevant_metrics:
            return 0.0

        successful = sum(1 for m in relevant_metrics if m.status == "success")
        return (successful / len(relevant_metrics)) * 100


@contextmanager
def track_processing_time(operation_name: Optional[str] = None):
    """
    Context manager for tracking processing time.

    Args:
        operation_name: Optional name for the operation

    Yields:
        ProcessingMetrics instance

    Example:
        with track_processing_time("pdf_extraction") as metrics:
            # Do some processing
            metrics.metadata["pages"] = 10
        print(f"Took {metrics.duration_seconds}s")
    """
    metrics = ProcessingMetrics(
        metadata={"operation": operation_name} if operation_name else {}
    )

    try:
        yield metrics
        metrics.complete(status="success")
    except Exception as e:
        metrics.complete(status="error", error_message=str(e))
        raise
    finally:
        if operation_name:
            logger = logging.getLogger(__name__)
            logger.debug(
                f"Operation '{operation_name}' took {metrics.duration_seconds:.3f}s "
                f"(status: {metrics.status})"
            )