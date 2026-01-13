"""Pipeline service for async pipeline execution with real-time progress."""

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from context_builder.api.services.upload import UploadService

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocPhase(str, Enum):
    """Document processing phase."""

    PENDING = "pending"
    INGESTING = "ingesting"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    DONE = "done"
    FAILED = "failed"


@dataclass
class DocProgress:
    """Progress status for a single document."""

    doc_id: str
    claim_id: str
    filename: str
    phase: DocPhase = DocPhase.PENDING
    failed_at_stage: Optional[DocPhase] = None  # Which stage failed
    error: Optional[str] = None


@dataclass
class PipelineRun:
    """State of a pipeline run."""

    run_id: str
    claim_ids: List[str]
    status: PipelineStatus = PipelineStatus.PENDING
    docs: Dict[str, DocProgress] = field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


# Progress callback type: (run_id, doc_id, phase, error, failed_at_stage)
ProgressCallback = Callable[[str, str, DocPhase, Optional[str], Optional[DocPhase]], None]


class PipelineService:
    """Service for executing pipelines with real-time progress reporting."""

    def __init__(
        self,
        output_dir: Path,
        upload_service: UploadService,
    ):
        """
        Initialize the pipeline service.

        Args:
            output_dir: Base output directory for claims (output/claims/)
            upload_service: Service for managing pending claims
        """
        self.output_dir = output_dir
        self.upload_service = upload_service
        self.active_runs: Dict[str, PipelineRun] = {}
        self.cancel_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def _generate_run_id(self) -> str:
        """Generate a unique run ID."""
        from context_builder.extraction.base import generate_run_id
        return generate_run_id()

    async def start_pipeline(
        self,
        claim_ids: List[str],
        model: str = "gpt-4o",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Start pipeline execution for pending claims.

        Args:
            claim_ids: List of pending claim IDs to process
            model: Model name for extraction
            progress_callback: Optional callback for progress updates

        Returns:
            Run ID for tracking
        """
        run_id = self._generate_run_id()

        # Initialize run tracking
        run = PipelineRun(
            run_id=run_id,
            claim_ids=claim_ids,
            status=PipelineStatus.PENDING,
            started_at=datetime.utcnow().isoformat() + "Z",
        )

        # Build initial doc list from pending claims
        for claim_id in claim_ids:
            claim = self.upload_service.get_pending_claim(claim_id)
            if claim:
                for doc in claim.documents:
                    key = f"{claim_id}/{doc.doc_id}"
                    run.docs[key] = DocProgress(
                        doc_id=doc.doc_id,
                        claim_id=claim_id,
                        filename=doc.original_filename,
                        phase=DocPhase.PENDING,
                    )

        async with self._lock:
            self.active_runs[run_id] = run
            self.cancel_events[run_id] = asyncio.Event()

        # Start background task
        asyncio.create_task(
            self._run_pipeline(run_id, claim_ids, model, progress_callback)
        )

        return run_id

    async def _run_pipeline(
        self,
        run_id: str,
        claim_ids: List[str],
        model: str,
        progress_callback: Optional[ProgressCallback],
    ) -> None:
        """Execute pipeline in background."""
        run = self.active_runs.get(run_id)
        if not run:
            return

        run.status = PipelineStatus.RUNNING

        try:
            # Import pipeline components
            from context_builder.pipeline.discovery import discover_claims
            from context_builder.pipeline.run import process_claim, StageConfig

            # Prepare input directories
            input_paths: List[Path] = []
            for claim_id in claim_ids:
                if self._is_cancelled(run_id):
                    break
                input_path = self.upload_service.move_to_input(claim_id)
                input_paths.append(input_path)

            if self._is_cancelled(run_id):
                run.status = PipelineStatus.CANCELLED
                return

            # Process each claim
            total_success = 0
            total_failed = 0

            for input_path in input_paths:
                if self._is_cancelled(run_id):
                    break

                claim_id = input_path.name

                # Discover documents in this claim
                claims = discover_claims(input_path)
                if not claims:
                    logger.warning(f"No documents found in {input_path}")
                    continue

                claim = claims[0]  # Should be one claim per input_path

                # Update doc IDs to match discovered documents
                # The original doc_ids from upload may differ from discovered doc_ids
                await self._update_doc_ids(run_id, claim_id, claim.documents, progress_callback)

                # Create progress callback that reports per-document completion
                def make_doc_callback(claim_id: str):
                    def callback(idx: int, total: int, filename: str):
                        # Find the doc by filename and mark as done
                        for key, doc in run.docs.items():
                            if doc.claim_id == claim_id and doc.filename == filename:
                                doc.phase = DocPhase.DONE
                                if progress_callback:
                                    asyncio.create_task(
                                        self._async_callback(
                                            progress_callback, run_id, doc.doc_id, DocPhase.DONE, None
                                        )
                                    )
                                break
                    return callback

                # Create phase callback for real-time stage updates
                def make_phase_callback(claim_id: str):
                    # Map stage names to DocPhase
                    stage_to_phase = {
                        "ingestion": DocPhase.INGESTING,
                        "classification": DocPhase.CLASSIFYING,
                        "extraction": DocPhase.EXTRACTING,
                    }

                    def callback(stage_name: str, doc_id: str):
                        phase = stage_to_phase.get(stage_name)
                        if phase:
                            # Update local state
                            for key, doc in run.docs.items():
                                if doc.doc_id == doc_id:
                                    doc.phase = phase
                                    break
                            # Broadcast via WebSocket
                            if progress_callback:
                                asyncio.create_task(
                                    self._async_callback(
                                        progress_callback, run_id, doc_id, phase, None
                                    )
                                )
                    return callback

                try:
                    # Process the claim
                    result = process_claim(
                        claim=claim,
                        output_base=self.output_dir,
                        run_id=run_id,
                        model=model,
                        stage_config=StageConfig(),
                        progress_callback=make_doc_callback(claim_id),
                        phase_callback=make_phase_callback(claim_id),
                    )

                    # Count results
                    for doc_result in result.documents:
                        if doc_result.status == "success":
                            total_success += 1
                        else:
                            total_failed += 1
                            # Mark failed doc and track which stage failed
                            for key, doc in run.docs.items():
                                if doc.claim_id == claim_id and doc.filename == doc_result.original_filename:
                                    # Save the stage where it failed before marking as failed
                                    doc.failed_at_stage = doc.phase if doc.phase != DocPhase.PENDING else DocPhase.INGESTING
                                    doc.phase = DocPhase.FAILED
                                    doc.error = doc_result.error
                                    if progress_callback:
                                        asyncio.create_task(
                                            self._async_callback(
                                                progress_callback, run_id, doc.doc_id, DocPhase.FAILED, doc_result.error, doc.failed_at_stage
                                            )
                                        )
                                    break

                except Exception as e:
                    logger.exception(f"Failed to process claim {claim_id}")
                    # Mark all docs in this claim as failed, tracking which stage they were in
                    for key, doc in run.docs.items():
                        if doc.claim_id == claim_id and doc.phase != DocPhase.DONE:
                            doc.failed_at_stage = doc.phase if doc.phase != DocPhase.PENDING else DocPhase.INGESTING
                            doc.phase = DocPhase.FAILED
                            doc.error = str(e)
                            total_failed += 1
                            if progress_callback:
                                asyncio.create_task(
                                    self._async_callback(
                                        progress_callback, run_id, doc.doc_id, DocPhase.FAILED, str(e), doc.failed_at_stage
                                    )
                                )

                # Cleanup staging for this claim
                self.upload_service.cleanup_staging(claim_id)
                self.upload_service.cleanup_input(claim_id)

            # Set final status
            if self._is_cancelled(run_id):
                run.status = PipelineStatus.CANCELLED
            elif total_failed > 0 and total_success > 0:
                run.status = PipelineStatus.COMPLETED  # Partial success
            elif total_failed > 0:
                run.status = PipelineStatus.FAILED
            else:
                run.status = PipelineStatus.COMPLETED

            run.completed_at = datetime.utcnow().isoformat() + "Z"
            run.summary = {
                "total": total_success + total_failed,
                "success": total_success,
                "failed": total_failed,
            }

        except Exception as e:
            logger.exception(f"Pipeline run {run_id} failed")
            run.status = PipelineStatus.FAILED
            run.completed_at = datetime.utcnow().isoformat() + "Z"

    async def _update_doc_ids(
        self,
        run_id: str,
        claim_id: str,
        discovered_docs: List,
        progress_callback: Optional[ProgressCallback],
    ) -> None:
        """Update doc IDs after discovery and notify of phase start."""
        run = self.active_runs.get(run_id)
        if not run:
            return

        # Map discovered docs by filename to update our tracking
        for discovered in discovered_docs:
            for key, doc in list(run.docs.items()):
                if doc.claim_id == claim_id and doc.filename == discovered.original_filename:
                    # Update doc_id to match discovered
                    doc.doc_id = discovered.doc_id
                    # Mark as ingesting (first phase)
                    doc.phase = DocPhase.INGESTING
                    if progress_callback:
                        await self._async_callback(
                            progress_callback, run_id, doc.doc_id, DocPhase.INGESTING, None
                        )
                    break

    async def _async_callback(
        self,
        callback: ProgressCallback,
        run_id: str,
        doc_id: str,
        phase: DocPhase,
        error: Optional[str],
        failed_at_stage: Optional[DocPhase] = None,
    ) -> None:
        """Execute callback, handling both sync and async callbacks."""
        try:
            result = callback(run_id, doc_id, phase, error, failed_at_stage)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")

    def _is_cancelled(self, run_id: str) -> bool:
        """Check if run is cancelled."""
        event = self.cancel_events.get(run_id)
        return event is not None and event.is_set()

    async def cancel_pipeline(self, run_id: str) -> bool:
        """
        Cancel a running pipeline.

        Args:
            run_id: Run ID to cancel

        Returns:
            True if cancellation was triggered
        """
        async with self._lock:
            event = self.cancel_events.get(run_id)
            if event is None:
                return False

            event.set()
            run = self.active_runs.get(run_id)
            if run:
                run.status = PipelineStatus.CANCELLED

            return True

    def get_run_status(self, run_id: str) -> Optional[PipelineRun]:
        """Get current status of a pipeline run."""
        return self.active_runs.get(run_id)

    def get_all_runs(self) -> List[PipelineRun]:
        """Get all tracked pipeline runs."""
        return list(self.active_runs.values())
