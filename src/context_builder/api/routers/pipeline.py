"""Pipeline router - endpoints for pipeline execution and management."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from context_builder.api.dependencies import (
    CurrentUser,
    get_audit_service,
    get_pipeline_service,
    get_prompt_config_service,
    get_upload_service,
    require_admin,
)
from context_builder.api.services import DocPhase
from context_builder.api.websocket import ws_manager

router = APIRouter(tags=["pipeline"])


# =============================================================================
# REQUEST MODELS
# =============================================================================

class PipelineRunRequest(BaseModel):
    claim_ids: List[str]
    model: str = "gpt-4o"
    stages: List[str] = ["ingest", "classify", "extract"]
    prompt_config_id: Optional[str] = None
    force_overwrite: bool = False
    compute_metrics: bool = True
    dry_run: bool = False
    auto_assess: bool = False
    max_workers: int = 1


class PromptConfigRequest(BaseModel):
    """Request body for creating a prompt config."""
    name: str
    model: str = "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 4096


class PromptConfigUpdateRequest(BaseModel):
    """Request body for updating a prompt config."""
    name: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _generate_friendly_name(run_id: str) -> str:
    """Return the batch ID as the friendly name (enterprise format).

    The batch ID format BATCH-YYYYMMDD-NNN is already professional and sortable.
    """
    return run_id


def _format_duration(ms: int) -> str:
    """Format milliseconds as human-readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds}s"


def _format_relative_time(iso_time: str) -> str:
    """Convert ISO timestamp to relative time string."""
    if not iso_time:
        return "never processed"
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        if delta.days > 30:
            return f"{delta.days // 30}mo ago"
        elif delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60}m ago"
        else:
            return "just now"
    except Exception:
        return "never processed"


# =============================================================================
# PIPELINE EXECUTION ENDPOINTS
# =============================================================================

@router.post("/api/pipeline/run")
async def start_pipeline_run(
    request: PipelineRunRequest,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Start pipeline execution for pending claims.

    Args:
        request: Pipeline run request with claim_ids and model

    Returns:
        run_id for tracking progress

    Requires: Admin role
    """
    pipeline_service = get_pipeline_service()
    upload_service = get_upload_service()

    # Validate claim_ids is not empty
    if not request.claim_ids:
        raise HTTPException(status_code=400, detail="claim_ids cannot be empty")

    # Validate all claims exist in staging
    for claim_id in request.claim_ids:
        if not upload_service.claim_exists_staging(claim_id):
            raise HTTPException(status_code=404, detail=f"Pending claim not found: {claim_id}")

    # Create progress callback that broadcasts to WebSocket
    async def broadcast_progress(run_id: str, doc_id: str, phase: DocPhase, error: Optional[str], failed_at_stage: Optional[DocPhase] = None):
        # Handle run completion signal
        if doc_id == "__RUN_COMPLETE__":
            run = pipeline_service.get_run_status(run_id)
            await ws_manager.broadcast(run_id, {
                "type": "run_complete",
                "run_id": run_id,
                "status": run.status.value if run else "completed",
                "summary": run.summary if run else None,
            })
            return

        await ws_manager.broadcast(run_id, {
            "type": "doc_progress",
            "doc_id": doc_id,
            "phase": phase.value,
            "error": error,
            "failed_at_stage": failed_at_stage.value if failed_at_stage else None,
        })

    # Assessment broadcast callback: sends assessment messages via pipeline WS.
    # Uses a list to hold run_id since the closure is created before start_pipeline returns.
    _run_id_holder = []

    async def assessment_broadcast(message: dict):
        rid = _run_id_holder[0] if _run_id_holder else None
        if rid:
            await ws_manager.broadcast(rid, message)

    run_id = await pipeline_service.start_pipeline(
        claim_ids=request.claim_ids,
        model=request.model,
        stages=request.stages,
        prompt_config_id=request.prompt_config_id,
        force_overwrite=request.force_overwrite,
        compute_metrics=request.compute_metrics,
        dry_run=request.dry_run,
        progress_callback=broadcast_progress,
        auto_assess=request.auto_assess,
        assessment_broadcast=assessment_broadcast if request.auto_assess else None,
        max_workers=max(1, min(request.max_workers, 8)),
    )
    _run_id_holder.append(run_id)

    # Audit log the pipeline start
    audit_service = get_audit_service()
    audit_service.log(
        action=f"pipeline.started (claims: {len(request.claim_ids)}, model: {request.model})",
        user=current_user.username,
        action_type="pipeline.started",
        entity_type="run",
        entity_id=run_id,
    )

    status = "dry_run" if request.dry_run else "running"
    return {"run_id": run_id, "status": status}


@router.get("/api/pipeline/claims")
def list_pipeline_claims():
    """
    List claims available for pipeline processing.

    Returns pending claims from staging area with doc counts and last run info.
    This is the claims selector for the Pipeline Control Center.
    """
    upload_service = get_upload_service()
    pipeline_service = get_pipeline_service()

    pending_claims = upload_service.list_pending_claims()

    # Get all runs to find last run per claim
    all_runs = pipeline_service.get_all_runs()
    claim_last_run: Dict[str, tuple] = {}  # claim_id -> (run_id, started_at)
    for run in all_runs:
        for claim_id in run.claim_ids:
            if claim_id not in claim_last_run or (run.started_at and run.started_at > claim_last_run[claim_id][1]):
                claim_last_run[claim_id] = (run.run_id, run.started_at or "")

    result = []
    for claim in pending_claims:
        last_run_info = claim_last_run.get(claim.claim_id)
        result.append({
            "claim_id": claim.claim_id,
            "doc_count": len(claim.documents),
            "last_run": _format_relative_time(last_run_info[1]) if last_run_info else "never processed",
            "last_run_id": last_run_info[0] if last_run_info else None,
            "is_pending": True,
        })

    return result


@router.post("/api/pipeline/cancel/{run_id}")
async def cancel_pipeline(
    run_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Cancel a running pipeline.

    Args:
        run_id: Run ID to cancel

    Returns:
        Cancellation status

    Requires: Admin role
    """
    pipeline_service = get_pipeline_service()

    if await pipeline_service.cancel_pipeline(run_id):
        # Audit log the cancellation
        audit_service = get_audit_service()
        audit_service.log(
            action="pipeline.cancelled",
            user=current_user.username,
            action_type="pipeline.cancelled",
            entity_type="run",
            entity_id=run_id,
        )
        # Broadcast cancellation
        await ws_manager.broadcast(run_id, {
            "type": "run_cancelled",
            "run_id": run_id,
        })
        return {"status": "cancelled", "run_id": run_id}

    raise HTTPException(status_code=404, detail=f"Run not found or not running: {run_id}")


@router.get("/api/pipeline/status/{run_id}")
def get_pipeline_status(run_id: str):
    """
    Get current status of a pipeline run.

    Args:
        run_id: Run ID to check

    Returns:
        Run status with document progress
    """
    pipeline_service = get_pipeline_service()
    run = pipeline_service.get_run_status(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return {
        "run_id": run.run_id,
        "status": run.status.value,
        "claim_ids": run.claim_ids,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "summary": run.summary,
        "docs": {
            doc.doc_id: {  # Use doc_id as key for consistency with WebSocket messages
                "doc_id": doc.doc_id,
                "claim_id": doc.claim_id,
                "filename": doc.filename,
                "phase": doc.phase.value,
                "error": doc.error,
            }
            for key, doc in run.docs.items()
        },
    }


@router.get("/api/pipeline/runs")
def list_pipeline_runs():
    """
    List all tracked pipeline runs with enhanced metadata.

    Returns:
        List of run summaries with friendly names, progress, timing, and errors
    """
    pipeline_service = get_pipeline_service()
    runs = pipeline_service.get_all_runs()

    result = []
    for run in runs:
        # Calculate stage progress from doc phases
        docs_done = sum(1 for d in run.docs.values() if d.phase == DocPhase.DONE)
        docs_failed = sum(1 for d in run.docs.values() if d.phase == DocPhase.FAILED)
        total_docs = len(run.docs) or 1

        # Calculate overall progress percentage
        progress_pct = int((docs_done + docs_failed) / total_docs * 100)

        # Stage progress (simplified: based on overall completion)
        stage_progress = {
            "ingest": 100 if progress_pct > 0 else 0,
            "classify": 100 if progress_pct > 30 else 0,
            "extract": progress_pct,
        }

        # Calculate duration
        duration_seconds = None
        if run.started_at and run.completed_at:
            try:
                start = datetime.fromisoformat(run.started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(run.completed_at.replace("Z", "+00:00"))
                duration_seconds = int((end - start).total_seconds())
            except Exception:
                pass

        # Collect errors
        errors = []
        for key, doc in run.docs.items():
            if doc.phase == DocPhase.FAILED and doc.error:
                stage = doc.failed_at_stage.value if doc.failed_at_stage else "unknown"
                errors.append({
                    "doc": doc.filename,
                    "stage": stage,
                    "message": doc.error,
                })

        # Format stage timings
        stage_timings = {
            stage: _format_duration(ms)
            for stage, ms in run.stage_timings.items()
        } if run.stage_timings else {}

        result.append({
            "run_id": run.run_id,
            "friendly_name": _generate_friendly_name(run.run_id),
            "status": run.status.value,
            "claim_ids": run.claim_ids,
            "claims_count": len(run.claim_ids),
            "docs_total": len(run.docs),
            "docs_processed": docs_done + docs_failed,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "duration_seconds": duration_seconds,
            "stage_progress": stage_progress,
            "stage_timings": stage_timings,
            "reuse": run.reuse_counts,
            "cost_estimate_usd": run.cost_estimate_usd,
            "prompt_config": run.prompt_config_id,
            "errors": errors,
            "summary": run.summary,
            "model": run.model,
        })

    # Sort by started_at descending (newest first)
    result.sort(key=lambda r: r["started_at"] or "", reverse=True)
    return result


@router.delete("/api/pipeline/runs/{run_id}")
def delete_pipeline_run(
    run_id: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """
    Delete a completed/failed/cancelled pipeline run.

    Args:
        run_id: Run ID to delete

    Returns:
        Deletion status

    Requires: Admin role
    """
    pipeline_service = get_pipeline_service()

    if pipeline_service.delete_run(run_id):
        # Audit log the deletion
        audit_service = get_audit_service()
        audit_service.log(
            action="pipeline.deleted",
            user=current_user.username,
            action_type="pipeline.deleted",
            entity_type="run",
            entity_id=run_id,
        )
        return {"status": "deleted", "run_id": run_id}

    raise HTTPException(
        status_code=400,
        detail=f"Cannot delete run {run_id}: not found or still running"
    )


# =============================================================================
# PROMPT CONFIG ENDPOINTS
# =============================================================================

@router.get("/api/pipeline/configs")
def list_prompt_configs():
    """List all prompt configurations."""
    service = get_prompt_config_service()
    configs = service.list_configs()
    return [
        {
            "id": c.id,
            "name": c.name,
            "model": c.model,
            "temperature": c.temperature,
            "max_tokens": c.max_tokens,
            "is_default": c.is_default,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in configs
    ]


@router.get("/api/pipeline/configs/{config_id}")
def get_prompt_config(config_id: str):
    """Get a single prompt configuration."""
    service = get_prompt_config_service()
    config = service.get_config(config_id)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")

    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.post("/api/pipeline/configs")
def create_prompt_config(request: PromptConfigRequest):
    """Create a new prompt configuration."""
    service = get_prompt_config_service()
    config = service.create_config(
        name=request.name,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.put("/api/pipeline/configs/{config_id}")
def update_prompt_config(config_id: str, request: PromptConfigUpdateRequest):
    """Update an existing prompt configuration."""
    service = get_prompt_config_service()

    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.model is not None:
        updates["model"] = request.model
    if request.temperature is not None:
        updates["temperature"] = request.temperature
    if request.max_tokens is not None:
        updates["max_tokens"] = request.max_tokens

    config = service.update_config(config_id, updates)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")

    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.delete("/api/pipeline/configs/{config_id}")
def delete_prompt_config(config_id: str):
    """Delete a prompt configuration."""
    service = get_prompt_config_service()

    if service.delete_config(config_id):
        return {"status": "deleted", "config_id": config_id}

    raise HTTPException(
        status_code=400,
        detail=f"Cannot delete config {config_id}: not found or is the last config"
    )


@router.post("/api/pipeline/configs/{config_id}/set-default")
def set_default_prompt_config(config_id: str):
    """Set a prompt configuration as the default."""
    service = get_prompt_config_service()
    config = service.set_default(config_id)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Config not found: {config_id}")

    return {
        "id": config.id,
        "name": config.name,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "is_default": config.is_default,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


# =============================================================================
# AUDIT LOG ENDPOINTS
# =============================================================================

@router.get("/api/pipeline/audit")
def list_audit_entries(
    action_type: Optional[str] = Query(None, description="Filter by action type (e.g., run_started)"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (run, config)"),
    since: Optional[str] = Query(None, description="ISO timestamp to filter entries after"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
):
    """
    List audit log entries.

    Returns entries sorted by timestamp descending (newest first).
    """
    service = get_audit_service()
    entries = service.list_entries(
        action_type=action_type,
        entity_type=entity_type,
        since=since,
        limit=limit,
    )
    return [
        {
            "timestamp": e.timestamp,
            "user": e.user,
            "action": e.action,
            "action_type": e.action_type,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
        }
        for e in entries
    ]


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

@router.websocket("/api/pipeline/ws/{run_id}")
async def pipeline_websocket(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for real-time pipeline progress updates.

    Messages sent to client:
    - {"type": "sync", "status": "...", "docs": {...}} - Full state on connect
    - {"type": "doc_progress", "doc_id": "...", "phase": "...", "error": ...}
    - {"type": "run_complete", "run_id": "...", "summary": {...}}
    - {"type": "run_cancelled", "run_id": "..."}
    - {"type": "ping"} - Keepalive

    Messages from client:
    - "pong" - Keepalive response
    """
    print(f"[WS] Connection attempt for run_id={run_id}")
    await ws_manager.connect(websocket, run_id)
    print(f"[WS] Connected for run_id={run_id}")

    try:
        # Send current state on connect (for reconnection sync)
        pipeline_service = get_pipeline_service()
        run = pipeline_service.get_run_status(run_id)
        print(f"[WS] Got run status: {run.status.value if run else 'NOT_FOUND'}")

        if run:
            await websocket.send_json({
                "type": "sync",
                "run_id": run.run_id,
                "status": run.status.value,
                "docs": {
                    doc.doc_id: {  # Use doc_id as key (matches progress messages)
                        "doc_id": doc.doc_id,
                        "claim_id": doc.claim_id,
                        "filename": doc.filename,
                        "phase": doc.phase.value,
                        "error": doc.error,
                        "failed_at_stage": doc.failed_at_stage.value if doc.failed_at_stage else None,
                    }
                    for key, doc in run.docs.items()
                },
            })
            print(f"[WS] Sent sync message for run_id={run_id}")

            # If run already completed, send completion and close
            if run.status.value in ("completed", "failed", "cancelled", "partial"):
                print(f"[WS] Run already {run.status.value}, sending completion")
                await websocket.send_json({
                    "type": "run_complete",
                    "run_id": run_id,
                    "status": run.status.value,
                    "summary": run.summary,
                })
                return  # Close connection - run is done
        else:
            print(f"[WS] Run {run_id} not found in active runs")
            # Run not found - send error and close
            await websocket.send_json({
                "type": "error",
                "message": f"Run {run_id} not found",
            })
            return

        # Keep connection alive while run is in progress
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )
                # Handle ping/pong
                if data == "pong":
                    continue
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    print(f"[WS] Failed to send ping, closing")
                    break

            # Check if run is complete
            run = pipeline_service.get_run_status(run_id)
            if run and run.status.value in ("completed", "failed", "cancelled", "partial"):
                print(f"[WS] Run {run_id} completed with status {run.status.value}")
                await websocket.send_json({
                    "type": "run_complete",
                    "run_id": run_id,
                    "status": run.status.value,
                    "summary": run.summary,
                })
                break  # Exit loop after sending completion

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected for run_id={run_id}")
    except Exception as e:
        print(f"[WS] Error for run_id={run_id}: {e}")
    finally:
        ws_manager.disconnect(websocket, run_id)
        print(f"[WS] Cleaned up connection for run_id={run_id}")
