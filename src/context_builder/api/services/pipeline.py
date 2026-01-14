"""Pipeline service for async pipeline execution with real-time progress."""

import asyncio
import json
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
    PARTIAL = "partial"  # Some docs succeeded, some failed
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
    model: str = "gpt-4o"
    # Extended fields for UI control center
    stages: List[str] = field(default_factory=lambda: ["ingest", "classify", "extract"])
    prompt_config_id: Optional[str] = None
    force_overwrite: bool = False
    compute_metrics: bool = True
    # Tracking fields
    stage_timings: Dict[str, int] = field(default_factory=dict)  # stage -> ms
    reuse_counts: Dict[str, int] = field(default_factory=dict)   # stage -> count reused
    cost_estimate_usd: Optional[float] = None


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
        stages: Optional[List[str]] = None,
        prompt_config_id: Optional[str] = None,
        force_overwrite: bool = False,
        compute_metrics: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Start pipeline execution for pending claims.

        Args:
            claim_ids: List of pending claim IDs to process
            model: Model name for extraction
            stages: Stages to run (ingest, classify, extract). Default: all
            prompt_config_id: Reference to prompt config (for tracking)
            force_overwrite: Reprocess even if outputs exist
            compute_metrics: Compute metrics.json at end
            dry_run: Preview only, no actual processing
            progress_callback: Optional callback for progress updates

        Returns:
            Run ID for tracking
        """
        if stages is None:
            stages = ["ingest", "classify", "extract"]

        run_id = self._generate_run_id()

        # Initialize run tracking
        run = PipelineRun(
            run_id=run_id,
            claim_ids=claim_ids,
            status=PipelineStatus.PENDING,
            started_at=datetime.utcnow().isoformat() + "Z",
            model=model,
            stages=stages,
            prompt_config_id=prompt_config_id,
            force_overwrite=force_overwrite,
            compute_metrics=compute_metrics,
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

        # Handle dry run - return early with estimated work
        if dry_run:
            run.status = PipelineStatus.COMPLETED
            run.completed_at = datetime.utcnow().isoformat() + "Z"
            run.summary = {
                "dry_run": True,
                "total": len(run.docs),
                "stages": stages,
            }
            return run_id

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
            from context_builder.pipeline.run import process_claim

            # Prepare input directories
            input_paths: List[Path] = []
            for claim_id in claim_ids:
                if self._is_cancelled(run_id):
                    break
                input_path = self.upload_service.move_to_input(claim_id)
                input_paths.append(input_path)

            if self._is_cancelled(run_id):
                # Cleanup any claims already moved to input before cancellation
                for input_path in input_paths:
                    claim_id = input_path.name
                    self.upload_service.cleanup_staging(claim_id)
                    self.upload_service.cleanup_input(claim_id)
                run.status = PipelineStatus.CANCELLED
                self._persist_run(run)
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

                # Get event loop for thread-safe callback scheduling
                loop = asyncio.get_running_loop()

                # Create progress callback that reports per-document completion
                def make_doc_callback(claim_id: str):
                    def callback(idx: int, total: int, filename: str):
                        # Find the doc by filename and mark as done
                        for key, doc in run.docs.items():
                            if doc.claim_id == claim_id and doc.filename == filename:
                                doc.phase = DocPhase.DONE
                                if progress_callback:
                                    # Thread-safe scheduling to main event loop
                                    asyncio.run_coroutine_threadsafe(
                                        self._async_callback(
                                            progress_callback, run_id, doc.doc_id, DocPhase.DONE, None
                                        ),
                                        loop
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
                            # Broadcast via WebSocket (thread-safe)
                            if progress_callback:
                                asyncio.run_coroutine_threadsafe(
                                    self._async_callback(
                                        progress_callback, run_id, doc_id, phase, None
                                    ),
                                    loop
                                )
                    return callback

                try:
                    # Build stage config from run settings
                    doc_ids = [doc.doc_id for doc in claim.documents]
                    if run.force_overwrite:
                        # Force overwrite: use exactly the stages specified
                        stage_config = self._build_stage_config(run.stages)
                    else:
                        # Smart detection: skip stages with existing outputs
                        stage_config = self._detect_stages_for_claim(
                            claim_id, doc_ids, requested_stages=run.stages
                        )

                    # Process the claim in a thread pool to allow event loop
                    # to process broadcast tasks while processing runs
                    result = await asyncio.to_thread(
                        process_claim,
                        claim=claim,
                        output_base=self.output_dir,
                        run_id=run_id,
                        model=model,
                        stage_config=stage_config,
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
                run.status = PipelineStatus.PARTIAL
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

            # Persist run to disk for visibility in other screens
            self._persist_run(run)

            # Broadcast run completion via progress callback
            # The callback will be used to send run_complete message
            if progress_callback:
                await self._async_callback(
                    progress_callback, run_id, "__RUN_COMPLETE__",
                    DocPhase.DONE, None, None
                )

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
        """Get all tracked pipeline runs (active + historical from disk)."""
        from context_builder.storage import FileStorage

        # Start with active in-memory runs
        runs_by_id: Dict[str, PipelineRun] = {r.run_id: r for r in self.active_runs.values()}

        # Load historical runs from disk
        try:
            storage = FileStorage(output_root=self.output_dir.parent)
            historical_runs = storage.list_runs()

            for run_ref in historical_runs:
                # Skip if already in active runs
                if run_ref.run_id in runs_by_id:
                    continue

                # Convert RunRef to PipelineRun
                historical_run = self._load_run_from_disk(run_ref.run_id)
                if historical_run:
                    runs_by_id[historical_run.run_id] = historical_run

        except Exception as e:
            logger.warning(f"Failed to load historical runs: {e}")

        return list(runs_by_id.values())

    def _load_run_from_disk(self, run_id: str) -> Optional[PipelineRun]:
        """Load a completed run from disk."""
        import json

        run_dir = self.output_dir.parent / "runs" / run_id
        if not run_dir.exists():
            return None

        manifest_path = run_dir / "manifest.json"
        summary_path = run_dir / "summary.json"

        manifest = {}
        summary = {}

        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        if summary_path.exists():
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Build claim_ids from manifest
        claim_ids = []
        claims_data = manifest.get("claims", [])
        for claim in claims_data:
            claim_id = claim.get("claim_id", claim.get("id"))
            if claim_id:
                claim_ids.append(claim_id)

        # Build docs dict from claims data
        # Each claim in manifest has claim_id and docs_count
        docs: Dict[str, DocProgress] = {}
        total_docs = summary.get("docs_total", 0)

        # Create placeholder docs based on docs_count per claim
        for claim in claims_data:
            claim_id = claim.get("claim_id", claim.get("id", "unknown"))
            docs_count = claim.get("docs_count", 0)
            for i in range(docs_count):
                doc_id = f"doc_{i}"
                key = f"{claim_id}/{doc_id}"
                docs[key] = DocProgress(
                    doc_id=doc_id,
                    claim_id=claim_id,
                    filename="",
                    phase=DocPhase.DONE,
                )

        # If no docs from claims, create placeholders from total count
        if not docs and total_docs > 0:
            for i in range(total_docs):
                doc_id = f"doc_{i}"
                claim_id = claim_ids[0] if claim_ids else "unknown"
                key = f"{claim_id}/{doc_id}"
                docs[key] = DocProgress(
                    doc_id=doc_id,
                    claim_id=claim_id,
                    filename="",
                    phase=DocPhase.DONE,
                )

        # Map status string to enum
        status_str = summary.get("status", "completed")
        status_map = {
            "completed": PipelineStatus.COMPLETED,
            "complete": PipelineStatus.COMPLETED,
            "failed": PipelineStatus.FAILED,
            "cancelled": PipelineStatus.CANCELLED,
            "partial": PipelineStatus.PARTIAL,
            "running": PipelineStatus.COMPLETED,  # If on disk, it's done
        }
        status = status_map.get(status_str, PipelineStatus.COMPLETED)

        # Extract stage timings if available
        stage_timings = {}
        if "timings" in summary:
            stage_timings = summary["timings"]

        return PipelineRun(
            run_id=run_id,
            status=status,
            claim_ids=claim_ids,
            model=manifest.get("model", summary.get("model", "unknown")),
            started_at=manifest.get("started_at"),
            completed_at=manifest.get("ended_at") or summary.get("completed_at"),
            docs=docs,
            prompt_config_id=manifest.get("prompt_config_id", manifest.get("model")),
            summary=summary,
            reuse_counts=summary.get("reuse", {"ingestion": 0, "classification": 0}),
            stage_timings=stage_timings,
        )

    def delete_run(self, run_id: str) -> bool:
        """
        Delete a pipeline run.

        Removes from active tracking and deletes disk outputs.
        Only completed/failed/cancelled runs can be deleted.

        Args:
            run_id: Run ID to delete

        Returns:
            True if deletion was successful
        """
        run = self.active_runs.get(run_id)

        # Check if it's an active run that shouldn't be deleted
        if run is not None:
            if run.status in (PipelineStatus.RUNNING, PipelineStatus.PENDING):
                return False
            # Remove from active tracking
            del self.active_runs[run_id]
            if run_id in self.cancel_events:
                del self.cancel_events[run_id]

        # Delete run directory from disk (works for both active and historical)
        run_dir = self.output_dir.parent / "runs" / run_id
        if not run_dir.exists() and run is None:
            # Neither in memory nor on disk
            return False

        try:
            if run_dir.exists():
                shutil.rmtree(run_dir)
                logger.info(f"Deleted run directory: {run_dir}")
        except Exception as e:
            logger.warning(f"Failed to delete run directory for {run_id}: {e}")
            return False

        # Rebuild run index to remove stale entry
        self._rebuild_run_index()

        logger.info(f"Deleted pipeline run: {run_id}")
        return True

    def _rebuild_run_index(self) -> None:
        """Rebuild the run index after a run is added or deleted."""
        try:
            from context_builder.storage.index_builder import build_run_index
            from context_builder.storage.index_reader import RUN_INDEX_FILE, write_jsonl

            output_dir = self.output_dir.parent  # output/
            registry_dir = output_dir / "registry"

            if not registry_dir.exists():
                logger.debug("Registry directory does not exist, skipping index rebuild")
                return

            run_records = build_run_index(output_dir)
            run_index_path = registry_dir / RUN_INDEX_FILE
            write_jsonl(run_index_path, run_records)
            logger.info(f"Rebuilt run index with {len(run_records)} runs")
        except Exception as e:
            logger.warning(f"Failed to rebuild run index: {e}")

    def _persist_run(self, run: PipelineRun) -> None:
        """Persist run to disk for visibility in other screens.

        Creates the global run directory structure with manifest.json,
        summary.json, and .complete marker so FileStorage.list_runs() can find it.
        Also appends to the run index if it exists for immediate visibility.
        """
        from context_builder.pipeline.paths import create_workspace_run_structure

        try:
            # Create global run directory structure
            ws_paths = create_workspace_run_structure(self.output_dir, run.run_id)

            # Build claims array with per-claim details
            claims_by_id: Dict[str, Dict[str, Any]] = {}
            for doc in run.docs.values():
                if doc.claim_id not in claims_by_id:
                    claims_by_id[doc.claim_id] = {
                        "claim_id": doc.claim_id,
                        "status": "success",
                        "docs_count": 0,
                        "claim_run_path": str(self.output_dir / doc.claim_id / "runs" / run.run_id),
                    }
                claims_by_id[doc.claim_id]["docs_count"] += 1
                # Mark claim as partial/failed if any doc failed
                if doc.phase == DocPhase.FAILED:
                    if claims_by_id[doc.claim_id]["status"] == "success":
                        claims_by_id[doc.claim_id]["status"] = "partial"

            # Write manifest.json (matching CLI format)
            manifest = {
                "run_id": run.run_id,
                "started_at": run.started_at,
                "ended_at": run.completed_at,
                "model": run.model,
                "claims_count": len(run.claim_ids),
                "claims": list(claims_by_id.values()),
            }
            with open(ws_paths.manifest_json, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            # Write summary.json (matching CLI format)
            run_summary = run.summary or {}
            summary_data = {
                "run_id": run.run_id,
                "status": run.status.value,
                "claims_discovered": len(run.claim_ids),
                "claims_processed": len(run.claim_ids),
                "claims_failed": 0,
                "docs_total": run_summary.get("total", len(run.docs)),
                "docs_success": run_summary.get("success", 0),
                "completed_at": run.completed_at,
            }
            with open(ws_paths.summary_json, "w", encoding="utf-8") as f:
                json.dump(summary_data, f, indent=2)

            # Write .complete marker
            ws_paths.complete_marker.touch()

            logger.info(f"Persisted run {run.run_id} to {ws_paths.run_root}")

            # Build or update indexes for fast lookups
            self._update_indexes(run, ws_paths, summary_data)

        except Exception as e:
            logger.error(f"Failed to persist run {run.run_id}: {e}")

    def _update_indexes(
        self,
        run: PipelineRun,
        ws_paths: "WorkspaceRunPaths",
        summary_data: dict,
    ) -> None:
        """Build indexes if missing, or append to existing run index.

        This ensures indexes are available for fast lookups after API-triggered runs.
        Matches CLI behavior which auto-builds indexes after pipeline completion.
        """
        # Registry is at workspace/registry/ (sibling to workspace/claims/)
        registry_dir = self.output_dir.parent / "registry"
        run_index_path = registry_dir / "run_index.jsonl"
        doc_index_path = registry_dir / "doc_index.jsonl"

        # If indexes don't exist, build them from scratch
        if not doc_index_path.exists():
            try:
                from context_builder.storage.index_builder import build_all_indexes
                logger.info("Building indexes for workspace...")
                stats = build_all_indexes(self.output_dir.parent)
                logger.info(f"Indexes built: {stats.get('doc_count', 0)} docs, {stats.get('run_count', 0)} runs")
                return  # build_all_indexes already includes the current run
            except Exception as e:
                logger.warning(f"Index build failed (non-fatal): {e}")
                return

        # If indexes exist, just append the new run
        self._append_to_run_index(run, ws_paths, summary_data)

    def _append_to_run_index(
        self,
        run: PipelineRun,
        ws_paths: "WorkspaceRunPaths",
        summary_data: dict,
    ) -> None:
        """Append run to the existing run index file.

        This allows the run to be immediately visible without rebuilding the full index.
        """
        # Registry is at output/registry/ (sibling to output/claims/ and output/runs/)
        registry_dir = self.output_dir.parent / "registry"
        run_index_path = registry_dir / "run_index.jsonl"

        if not run_index_path.exists():
            logger.debug("No run index exists, skipping index update")
            return

        try:
            # Build index record matching the format from index_builder.build_run_index()
            record = {
                "run_id": run.run_id,
                "status": summary_data.get("status", "complete"),
                "started_at": run.started_at,
                "ended_at": run.completed_at,
                "claims_count": len(run.claim_ids),
                "docs_count": summary_data.get("total", len(run.docs)),
                "run_root": str(ws_paths.run_root.relative_to(self.output_dir.parent.parent)),
            }

            # Append to JSONL file
            with open(run_index_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            logger.info(f"Appended run {run.run_id} to index")
        except Exception as e:
            logger.warning(f"Failed to append to run index: {e}")

    def _build_stage_config(self, stages: List[str]) -> "StageConfig":
        """Build StageConfig from stage name strings.

        Args:
            stages: List of stage names (ingest, classify, extract)

        Returns:
            StageConfig with the requested stages
        """
        from context_builder.pipeline.run import StageConfig, PipelineStage

        stage_map = {
            "ingest": PipelineStage.INGEST,
            "classify": PipelineStage.CLASSIFY,
            "extract": PipelineStage.EXTRACT,
        }
        pipeline_stages = [stage_map[s] for s in stages if s in stage_map]
        return StageConfig(stages=pipeline_stages)

    def _detect_stages_for_claim(
        self,
        claim_id: str,
        doc_ids: List[str],
        requested_stages: Optional[List[str]] = None,
    ) -> "StageConfig":
        """Detect which stages can be skipped based on existing outputs.

        Checks for existing ingestion (pages.json) and classification (doc.json)
        outputs to determine which stages can be skipped.

        Args:
            claim_id: Claim ID to check
            doc_ids: List of document IDs in the claim
            requested_stages: Optional list of requested stages to constrain to

        Returns:
            StageConfig with appropriate stages enabled/disabled
        """
        from context_builder.pipeline.run import StageConfig, PipelineStage
        from context_builder.pipeline.paths import get_claim_paths, get_doc_paths

        # Default to all stages if not specified
        if requested_stages is None:
            requested_stages = ["ingest", "classify", "extract"]

        claim_paths = get_claim_paths(self.output_dir, claim_id)

        can_skip_ingest = True
        can_skip_classify = True

        for doc_id in doc_ids:
            doc_paths = get_doc_paths(claim_paths, doc_id)

            # Check if ingestion output exists
            if not doc_paths.pages_json.exists():
                can_skip_ingest = False

            # Check if classification output exists
            if not doc_paths.doc_json.exists():
                can_skip_classify = False

        # Build stage list based on what can be skipped AND what was requested
        stages = []
        if "ingest" in requested_stages and not can_skip_ingest:
            stages.append(PipelineStage.INGEST)
        if "classify" in requested_stages and not can_skip_classify:
            stages.append(PipelineStage.CLASSIFY)
        if "extract" in requested_stages:
            stages.append(PipelineStage.EXTRACT)  # Always run extraction if requested

        if can_skip_ingest or can_skip_classify:
            logger.info(
                f"Smart stage detection for {claim_id}: "
                f"skip_ingest={can_skip_ingest}, skip_classify={can_skip_classify}"
            )

        return StageConfig(stages=stages)
