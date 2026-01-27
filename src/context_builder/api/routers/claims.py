"""Claims router - endpoints for listing and reviewing claims."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from context_builder.api.dependencies import (
    get_aggregation_service,
    get_assessment_service,
    get_claims_service,
    get_data_dir,
    get_documents_service,
    get_reconciliation_service,
    get_workspace_path,
)
from context_builder.api.models import (
    ClaimReviewPayload,
    ClaimSummary,
    DocSummary,
    RunSummary,
)
from context_builder.api.websocket import ConnectionManager

router = APIRouter(tags=["claims"])

# WebSocket manager for assessment progress
assessment_ws_manager = ConnectionManager()

# In-memory tracking of running assessment runs
# run_id -> {"claim_id": str, "status": str, "started_at": str, "result": Optional[dict]}
_active_assessment_runs: Dict[str, Dict[str, Any]] = {}


class AssessmentRunRequest(BaseModel):
    """Request body for starting an assessment run."""
    processing_type: str = "assessment"


class AssessmentRunResponse(BaseModel):
    """Response from starting an assessment run."""
    run_id: str
    claim_id: str
    status: str


@router.get("/api/claims", response_model=List[ClaimSummary])
def list_claims(run_id: Optional[str] = Query(None, description="Filter by run ID")):
    """
    List all claims in the data directory.

    Args:
        run_id: Optional run ID to filter extraction metrics. If not provided, uses latest run.

    Uses new folder structure:
      {claim_id}/docs/{doc_id}/meta/doc.json
      {claim_id}/runs/{run_id}/extraction/{doc_id}.json
    """
    return get_claims_service().list_claims(run_id)


@router.get("/api/claims/runs")
def list_claim_runs():
    """
    List all available run IDs for the claims view.

    Returns list of run IDs sorted newest first, with metadata.
    Reads from global runs directory (output/runs/) when available.
    """
    return get_claims_service().list_runs()


@router.get("/api/claims/{claim_id}/docs", response_model=List[DocSummary])
def list_docs(claim_id: str, run_id: Optional[str] = Query(None, description="Filter by run ID")):
    """
    List documents for a specific claim.

    Args:
        claim_id: Can be either the full folder name or extracted claim number.
        run_id: Optional run ID for extraction metrics. If not provided, uses latest run.
    """
    return get_documents_service().list_docs(claim_id, run_id)


@router.get("/api/runs/latest", response_model=RunSummary)
def get_run_summary():
    """Get metrics summary across all claims."""
    return get_claims_service().get_run_summary()


@router.get("/api/claims/{claim_id}/review", response_model=ClaimReviewPayload)
def get_claim_review(claim_id: str):
    """
    Get claim review payload for the claim-level review screen.

    Returns claim metadata, ordered doc list with status, and prev/next claim IDs
    for sequential navigation.
    """
    return get_claims_service().get_claim_review(claim_id)


@router.get("/api/claims/{claim_id}/facts")
def get_claim_facts(claim_id: str) -> Optional[Dict[str, Any]]:
    """
    Get aggregated claim facts for a claim.

    Reads from latest claim run, with fallback to legacy context/ path.
    Returns null if no claim facts found.
    """
    from context_builder.storage.filesystem import FileStorage
    from context_builder.schemas.claim_facts import migrate_claim_facts_to_v3

    data_dir = get_data_dir()
    storage = FileStorage(data_dir)

    try:
        claim_run_storage = storage.get_claim_run_storage(claim_id)
    except ValueError:
        # Claim not found
        return None

    data = claim_run_storage.read_with_fallback("claim_facts.json")
    if data is None:
        return None

    # Migrate v2 -> v3 if needed
    data = migrate_claim_facts_to_v3(data)
    return data


@router.get("/api/claims/{claim_id}/assessment")
def get_claim_assessment(claim_id: str) -> Optional[Dict[str, Any]]:
    """
    Get claim assessment from the context folder.

    Returns the transformed assessment matching the frontend ClaimAssessment type,
    or null if no assessment exists. Transforms backend format to frontend format:
    - assessment_timestamp -> assessed_at
    - payout.final_payout -> payout (number)
    - check_number "1b" -> 1 (parse to int)
    - assumptions[].confidence_impact -> assumptions[].impact
    """
    return get_assessment_service().get_assessment(claim_id)


@router.get("/api/claims/{claim_id}/assessment/history")
def get_claim_assessment_history(claim_id: str) -> List[Dict[str, Any]]:
    """
    Get assessment history for a claim.

    Currently returns the current assessment as a single history entry.
    Future versions may store and return multiple historical assessments.
    """
    return get_assessment_service().get_assessment_history(claim_id)


@router.get("/api/assessment/evals/latest")
def get_latest_assessment_eval() -> Optional[Dict[str, Any]]:
    """
    Get the latest assessment evaluation results.

    Reads the most recent assessment_eval_*.json file from the workspace
    eval directory and transforms it to match the frontend AssessmentEvaluation type.

    Returns:
        Transformed evaluation with confusion matrix, per-claim results, and
        summary metrics (accuracy, precision, refer rate). Returns null if
        no evaluation files exist.
    """
    return get_assessment_service().get_latest_evaluation()


# =============================================================================
# ASSESSMENT RUN ENDPOINTS
# =============================================================================


@router.get("/api/claims/{claim_id}/assessment/{assessment_id}")
def get_historical_assessment(
    claim_id: str, assessment_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific historical assessment by ID.

    Args:
        claim_id: The claim ID
        assessment_id: The assessment ID (timestamp_version format)

    Returns:
        Transformed assessment matching frontend ClaimAssessment type,
        or null if not found.
    """
    return get_assessment_service().get_assessment_by_id(claim_id, assessment_id)


@router.post("/api/claims/{claim_id}/assessment/run", response_model=AssessmentRunResponse)
async def start_assessment_run(
    claim_id: str,
    request: AssessmentRunRequest = AssessmentRunRequest(),
) -> AssessmentRunResponse:
    """
    Start an assessment run for a claim.

    This triggers the claim-level pipeline (reconciliation -> processing)
    and returns a run_id for tracking progress via WebSocket.

    Args:
        claim_id: The claim ID to assess
        request: Optional configuration for the run

    Returns:
        Run ID and status for tracking via WebSocket
    """
    # Check if there's already a running assessment for this claim
    for run_id, run_info in _active_assessment_runs.items():
        if run_info["claim_id"] == claim_id and run_info["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail=f"Assessment already running for claim {claim_id} (run_id: {run_id})"
            )

    # Verify claim has facts to assess (check claim runs with fallback to legacy)
    from context_builder.storage.filesystem import FileStorage

    data_dir = get_data_dir()
    storage = FileStorage(data_dir)

    try:
        claim_run_storage = storage.get_claim_run_storage(claim_id)
        facts_data = claim_run_storage.read_with_fallback("claim_facts.json")
        if facts_data is None:
            raise HTTPException(
                status_code=400,
                detail=f"No claim facts found for {claim_id}. Run reconciliation first."
            )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Claim not found: {claim_id}"
        )

    # Generate run ID and track the run
    run_id = f"ASM-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    _active_assessment_runs[run_id] = {
        "claim_id": claim_id,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "processing_type": request.processing_type,
        "result": None,
        "input_tokens": 0,
        "output_tokens": 0,
    }

    # Start the assessment pipeline in background
    asyncio.create_task(_run_assessment_pipeline(run_id, claim_id, request.processing_type))

    return AssessmentRunResponse(
        run_id=run_id,
        claim_id=claim_id,
        status="running",
    )


async def _run_assessment_pipeline(run_id: str, claim_id: str, processing_type: str) -> None:
    """Background task that runs the assessment pipeline.

    Broadcasts progress via WebSocket and saves results.
    """
    from pathlib import Path
    from context_builder.pipeline.claim_stages import (
        ClaimContext,
        ClaimPipelineRunner,
        ClaimStageConfig,
        ReconciliationStage,
        ProcessingStage,
        get_processor,
    )

    workspace_path = get_workspace_path()

    # Create context with streaming callbacks
    async def token_callback(input_tokens: int, output_tokens: int) -> None:
        await assessment_ws_manager.broadcast(run_id, {
            "type": "tokens",
            "input": input_tokens,
            "output": output_tokens,
        })

    async def stage_callback(stage_name: str, status: str) -> None:
        await assessment_ws_manager.broadcast(run_id, {
            "type": "stage",
            "stage": stage_name,
            "status": status,
        })

    # Wrap async callbacks for sync pipeline
    loop = asyncio.get_event_loop()

    def sync_token_callback(input_tokens: int, output_tokens: int) -> None:
        # Store in run state for late-connecting clients (fixes race condition)
        if run_id in _active_assessment_runs:
            _active_assessment_runs[run_id]["input_tokens"] = input_tokens
            _active_assessment_runs[run_id]["output_tokens"] = output_tokens
        # Broadcast to connected clients
        asyncio.run_coroutine_threadsafe(
            token_callback(input_tokens, output_tokens), loop
        )

    def sync_stage_callback(stage_name: str, status: str) -> None:
        asyncio.run_coroutine_threadsafe(
            stage_callback(stage_name, status), loop
        )

    context = ClaimContext(
        claim_id=claim_id,
        workspace_path=workspace_path,
        run_id=run_id,
        stage_config=ClaimStageConfig(
            run_reconciliation=True,
            run_processing=True,
            processing_type=processing_type,
        ),
        processing_type=processing_type,
        on_token_update=sync_token_callback,
        on_stage_update=sync_stage_callback,
    )

    try:
        # Check if processor is registered
        processor = get_processor(processing_type)
        if processor is None:
            raise ValueError(f"No processor registered for type: {processing_type}")

        # Run pipeline stages: Reconciliation -> Enrichment -> Processing
        from context_builder.pipeline.claim_stages import EnrichmentStage
        stages = [ReconciliationStage(), EnrichmentStage(), ProcessingStage()]
        runner = ClaimPipelineRunner(stages)

        # Run synchronously (blocking)
        # TODO: Consider running in thread pool for true async
        context = runner.run(context)

        # Save result if successful
        if context.status == "success" and context.processing_result:
            assessment_service = get_assessment_service()
            saved = assessment_service.save_assessment(
                claim_id=claim_id,
                assessment_data=context.processing_result,
                prompt_version=context.prompt_version,
                extraction_bundle_id=context.extraction_bundle_id,
            )

            _active_assessment_runs[run_id]["status"] = "completed"
            _active_assessment_runs[run_id]["result"] = saved

            # Broadcast completion
            await assessment_ws_manager.broadcast(run_id, {
                "type": "complete",
                "decision": context.processing_result.get("decision"),
                "assessment_id": saved.get("id"),
                "input_tokens": _active_assessment_runs[run_id].get("input_tokens", 0),
                "output_tokens": _active_assessment_runs[run_id].get("output_tokens", 0),
            })
        else:
            _active_assessment_runs[run_id]["status"] = "error"
            _active_assessment_runs[run_id]["error"] = context.error or "Unknown error"

            await assessment_ws_manager.broadcast(run_id, {
                "type": "error",
                "message": context.error or "Assessment failed",
            })

    except Exception as e:
        _active_assessment_runs[run_id]["status"] = "error"
        _active_assessment_runs[run_id]["error"] = str(e)

        await assessment_ws_manager.broadcast(run_id, {
            "type": "error",
            "message": str(e),
        })


@router.get("/api/claims/{claim_id}/assessment/status/{run_id}")
def get_assessment_run_status(claim_id: str, run_id: str) -> Dict[str, Any]:
    """
    Get the status of an assessment run.

    Args:
        claim_id: The claim ID
        run_id: The run ID from start_assessment_run

    Returns:
        Run status including result if completed
    """
    if run_id not in _active_assessment_runs:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    run_info = _active_assessment_runs[run_id]
    if run_info["claim_id"] != claim_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found for claim {claim_id}")

    return run_info


@router.websocket("/api/claims/{claim_id}/assessment/ws/{run_id}")
async def assessment_websocket(websocket: WebSocket, claim_id: str, run_id: str):
    """
    WebSocket endpoint for real-time assessment progress updates.

    Messages sent to client:
    - {"type": "sync", "status": "...", "claim_id": "..."} - Initial state on connect
    - {"type": "stage", "stage": "...", "status": "running|complete"}
    - {"type": "tokens", "input": N, "output": N}
    - {"type": "complete", "decision": "...", "assessment_id": "..."}
    - {"type": "error", "message": "..."}
    - {"type": "ping"} - Keepalive
    """
    await assessment_ws_manager.connect(websocket, run_id)

    try:
        # Send current state on connect
        if run_id in _active_assessment_runs:
            run_info = _active_assessment_runs[run_id]
            if run_info["claim_id"] != claim_id:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Run {run_id} not found for claim {claim_id}",
                })
                return

            await websocket.send_json({
                "type": "sync",
                "run_id": run_id,
                "claim_id": claim_id,
                "status": run_info["status"],
                "input_tokens": run_info.get("input_tokens", 0),
                "output_tokens": run_info.get("output_tokens", 0),
            })

            # If already completed, send result and close
            if run_info["status"] == "completed":
                await websocket.send_json({
                    "type": "complete",
                    "decision": run_info.get("result", {}).get("decision"),
                    "assessment_id": run_info.get("result", {}).get("id"),
                    "input_tokens": run_info.get("input_tokens", 0),
                    "output_tokens": run_info.get("output_tokens", 0),
                })
                return
            elif run_info["status"] == "error":
                await websocket.send_json({
                    "type": "error",
                    "message": run_info.get("error", "Unknown error"),
                })
                return
        else:
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
                if data == "pong":
                    continue
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

            # Check if run is complete
            if run_id in _active_assessment_runs:
                run_info = _active_assessment_runs[run_id]
                if run_info["status"] in ("completed", "error"):
                    break

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        assessment_ws_manager.disconnect(websocket, run_id)


# =============================================================================
# RECONCILIATION ENDPOINTS
# =============================================================================


class ReconciliationRunRequest(BaseModel):
    """Request body for running reconciliation."""
    run_id: Optional[str] = None


class ReconciliationRunResponse(BaseModel):
    """Response from running reconciliation."""
    claim_id: str
    success: bool
    gate_status: Optional[str] = None
    fact_count: Optional[int] = None
    conflict_count: Optional[int] = None
    error: Optional[str] = None
    report_path: Optional[str] = None


@router.post("/api/claims/{claim_id}/reconcile", response_model=ReconciliationRunResponse)
def run_reconciliation(
    claim_id: str,
    request: ReconciliationRunRequest = ReconciliationRunRequest(),
) -> ReconciliationRunResponse:
    """
    Trigger reconciliation for a claim.

    Creates a new claim run and runs the reconciliation process which:
    1. Creates claim run directory with manifest
    2. Aggregates facts from document extractions
    3. Detects conflicts (same fact with different values)
    4. Evaluates quality gate (pass/warn/fail)
    5. Writes claim_facts.json and reconciliation_report.json to claim run

    Args:
        claim_id: The claim ID to reconcile
        request: Optional run_id to reconcile against specific extraction run

    Returns:
        Reconciliation result with gate status and summary
    """
    service = get_reconciliation_service()

    # reconcile() now handles everything: creates claim run, aggregates, writes outputs
    result = service.reconcile(claim_id, request.run_id)

    if not result.success:
        return ReconciliationRunResponse(
            claim_id=claim_id,
            success=False,
            error=result.error,
        )

    report = result.report
    return ReconciliationRunResponse(
        claim_id=claim_id,
        success=True,
        gate_status=report.gate.status.value,
        fact_count=report.fact_count,
        conflict_count=report.gate.conflict_count,
        report_path=f"claim_runs/{report.claim_run_id}/reconciliation_report.json",
    )


@router.get("/api/claims/{claim_id}/reconciliation-report")
def get_reconciliation_report(claim_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest reconciliation report for a claim.

    Reads from latest claim run, with fallback to legacy context/ path.
    Returns null if no reconciliation has been run.

    The report includes:
    - gate: status (pass/warn/fail), reasons, conflict count
    - conflicts: list of detected conflicts with values and sources
    - fact_count: total aggregated facts
    - critical_facts_spec: list of required facts for this claim's doc types
    - critical_facts_present: which critical facts were found
    """
    from context_builder.storage.filesystem import FileStorage

    data_dir = get_data_dir()
    storage = FileStorage(data_dir)

    try:
        claim_run_storage = storage.get_claim_run_storage(claim_id)
    except ValueError:
        # Claim not found
        return None

    data = claim_run_storage.read_with_fallback("reconciliation_report.json")
    return data


@router.get("/api/claims/{claim_id}/claim-runs")
def list_claim_runs_for_claim(claim_id: str) -> List[Dict[str, Any]]:
    """
    List all claim runs for a claim, newest first.

    Returns manifest information for each claim run including:
    - claim_run_id: Unique identifier for the claim run
    - created_at: When the run was created
    - stages_completed: List of completed stages
    - extraction_runs_considered: Extraction runs used
    """
    from context_builder.storage.filesystem import FileStorage

    data_dir = get_data_dir()
    storage = FileStorage(data_dir)

    try:
        claim_run_storage = storage.get_claim_run_storage(claim_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")

    run_ids = claim_run_storage.list_claim_runs()
    results = []
    for run_id in run_ids:
        manifest = claim_run_storage.read_manifest(run_id)
        if manifest:
            results.append({
                "claim_run_id": run_id,
                "created_at": manifest.created_at.isoformat(),
                "stages_completed": manifest.stages_completed,
                "extraction_runs_considered": manifest.extraction_runs_considered,
                "contextbuilder_version": manifest.contextbuilder_version,
            })
    return results


@router.get("/api/reconciliation/evals/latest")
def get_latest_reconciliation_eval() -> Optional[Dict[str, Any]]:
    """
    Get the latest reconciliation gate evaluation.

    Reads the most recent reconciliation_gate_eval_*.json file from the workspace
    eval directory.

    Returns:
        Evaluation with summary, per-claim results, top missing facts and conflicts.
        Returns null if no evaluation files exist.
    """
    workspace_path = get_workspace_path()
    eval_dir = workspace_path / "eval"

    if not eval_dir.exists():
        return None

    # Find the most recent reconciliation_gate_eval file
    eval_files = sorted(
        eval_dir.glob("reconciliation_gate_eval_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not eval_files:
        return None

    try:
        with open(eval_files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading reconciliation evaluation: {e}"
        )


# =============================================================================
# CUSTOMER COMMUNICATION ENDPOINTS
# =============================================================================


class CustomerDraftRequest(BaseModel):
    """Request body for generating a customer communication draft."""

    language: str = "en"  # "en" or "de"


class CustomerDraftResponse(BaseModel):
    """Response containing the generated customer draft."""

    subject: str
    body: str
    language: str
    claim_id: str
    tokens_used: int = 0


@router.post(
    "/api/claims/{claim_id}/communication/draft",
    response_model=CustomerDraftResponse,
)
def generate_customer_draft(
    claim_id: str,
    request: CustomerDraftRequest = CustomerDraftRequest(),
) -> CustomerDraftResponse:
    """
    Generate a customer communication draft email for a claim assessment.

    This uses the LLM to draft a polite email explaining the assessment
    decision and rationale to the policyholder.

    Args:
        claim_id: The claim ID
        request: Language preference ("en" for English, "de" for German)

    Returns:
        Draft email with subject and body in the requested language
    """
    from context_builder.api.services.customer_communication import (
        get_customer_communication_service,
    )
    from context_builder.storage.filesystem import FileStorage
    from context_builder.schemas.claim_facts import migrate_claim_facts_to_v3

    # First, get the assessment for this claim
    assessment = get_assessment_service().get_assessment(claim_id)
    if not assessment:
        raise HTTPException(
            status_code=400,
            detail=f"No assessment found for claim {claim_id}. Run assessment first.",
        )

    # Get claim facts for policyholder name
    claim_facts = None
    try:
        data_dir = get_data_dir()
        storage = FileStorage(data_dir)
        claim_run_storage = storage.get_claim_run_storage(claim_id)
        claim_facts = claim_run_storage.read_with_fallback("claim_facts.json")
        if claim_facts:
            claim_facts = migrate_claim_facts_to_v3(claim_facts)
    except Exception:
        # Non-fatal: continue without policyholder name
        pass

    try:
        service = get_customer_communication_service()
        result = service.generate_draft(
            claim_id=claim_id,
            assessment=assessment,
            claim_facts=claim_facts,
            language=request.language,
        )

        return CustomerDraftResponse(
            subject=result.subject,
            body=result.body,
            language=result.language,
            claim_id=result.claim_id,
            tokens_used=result.tokens_used,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate draft: {e}"
        )
