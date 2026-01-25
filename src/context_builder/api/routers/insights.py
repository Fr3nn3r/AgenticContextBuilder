"""Insights router - endpoints for analytics, metrics, and token costs."""

from typing import Optional

from fastapi import APIRouter, Query

from context_builder.api.dependencies import (
    get_insights_service,
    get_token_costs_service,
)

router = APIRouter(tags=["insights"])


# =============================================================================
# INSIGHTS OVERVIEW ENDPOINTS
# =============================================================================

@router.get("/api/insights/overview")
def get_insights_overview():
    """
    Get overview KPIs for the Calibration Insights screen.

    Returns:
    - docs_total: Total docs (supported types)
    - docs_reviewed: Docs with labels
    - docs_doc_type_wrong: Docs where doc_type was labeled incorrect
    - docs_needs_vision: Docs flagged as needing vision
    - required_field_presence_rate: Avg presence rate for required fields
    - required_field_accuracy: Avg accuracy for required fields
    - evidence_rate: Avg evidence rate for extracted fields
    """
    return get_insights_service().get_overview()


@router.get("/api/insights/doc-types")
def get_insights_doc_types():
    """
    Get metrics per doc type for the scoreboard.

    Returns list of doc type metrics including:
    - docs_reviewed, docs_doc_type_wrong, docs_needs_vision
    - required_field_presence_pct, required_field_accuracy_pct
    - evidence_rate_pct, top_failing_field
    """
    return get_insights_service().get_doc_type_metrics()


@router.get("/api/insights/priorities")
def get_insights_priorities(limit: int = Query(10, ge=1, le=50)):
    """
    Get prioritized list of (doc_type, field) to improve.

    Returns ranked list with:
    - doc_type, field_name, is_required
    - affected_docs count
    - failure breakdown (extractor_miss, incorrect, etc.)
    - priority_score and fix_bucket recommendation
    """
    return get_insights_service().get_priorities(limit)


@router.get("/api/insights/field-details")
def get_insights_field_details(
    doc_type: str = Query(..., description="Document type"),
    field: str = Query(..., alias="field", description="Field name"),
    run_id: Optional[str] = Query(None, description="Run ID to scope data to"),
):
    """
    Get detailed breakdown for a specific (doc_type, field).

    Returns:
    - total_docs, labeled_docs, with_prediction, with_evidence
    - breakdown: correct, incorrect, extractor_miss, etc.
    - rates: presence_pct, evidence_pct, accuracy_pct
    """
    return get_insights_service().get_field_details(doc_type, field, run_id)


@router.get("/api/insights/examples")
def get_insights_examples(
    doc_type: Optional[str] = Query(None, description="Filter by doc type"),
    field: Optional[str] = Query(None, description="Filter by field name"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    run_id: Optional[str] = Query(None, description="Run ID to scope data to"),
    limit: int = Query(30, ge=1, le=100),
):
    """
    Get example cases for drilldown.

    Filters:
    - doc_type: loss_notice, police_report, insurance_policy
    - field: specific field name
    - outcome: correct, incorrect, extractor_miss, cannot_verify, evidence_missing
    - run_id: scope examples to a specific run

    Returns list with claim_id, doc_id, values, judgement, and review_url.
    """
    return get_insights_service().get_examples(
        doc_type=doc_type,
        field=field,
        outcome=outcome,
        run_id=run_id,
        limit=limit,
    )


# =============================================================================
# TOKEN COST ENDPOINTS
# =============================================================================

@router.get("/api/insights/costs/overview")
def get_costs_overview():
    """
    Get overall token usage and cost summary.

    Returns:
    - total_cost_usd: Total cost across all LLM calls
    - total_tokens: Total tokens (prompt + completion)
    - total_prompt_tokens, total_completion_tokens: Token breakdown
    - total_calls: Number of LLM API calls
    - docs_processed: Unique documents processed
    - avg_cost_per_doc, avg_cost_per_call: Average costs
    - primary_model: Most frequently used model
    """
    return get_token_costs_service().get_overview()


@router.get("/api/insights/costs/by-operation")
def get_costs_by_operation():
    """
    Get token usage and costs broken down by operation type.

    Operations: classification, extraction, vision_ocr

    Returns list with:
    - operation: Operation type name
    - tokens, prompt_tokens, completion_tokens: Token counts
    - cost_usd: Total cost for this operation
    - call_count: Number of calls
    - percentage: Percentage of total cost
    """
    return get_token_costs_service().get_by_operation()


@router.get("/api/insights/costs/by-run")
def get_costs_by_run(limit: int = Query(20, ge=1, le=100)):
    """
    Get token usage and costs per pipeline run.

    Args:
        limit: Maximum number of runs to return (default 20)

    Returns list sorted by timestamp (newest first) with:
    - run_id, timestamp, model
    - claims_count, docs_count: Scope of run
    - tokens, cost_usd: Usage metrics
    - avg_cost_per_doc: Efficiency metric
    """
    return get_token_costs_service().get_by_run(limit)


@router.get("/api/insights/costs/by-claim")
def get_costs_by_claim(run_id: Optional[str] = Query(None)):
    """
    Get token costs per claim.

    Args:
        run_id: Optional filter by run ID

    Returns list sorted by cost (highest first) with:
    - claim_id, docs_count, tokens, cost_usd
    """
    return get_token_costs_service().get_by_claim(run_id)


@router.get("/api/insights/costs/by-doc")
def get_costs_by_doc(
    claim_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    """
    Get token costs per document.

    Args:
        claim_id: Optional filter by claim ID
        run_id: Optional filter by run ID

    Returns list sorted by cost (highest first) with:
    - doc_id, claim_id, tokens, cost_usd, operations
    """
    return get_token_costs_service().get_by_doc(claim_id, run_id)


@router.get("/api/insights/costs/daily-trend")
def get_costs_daily_trend(days: int = Query(30, ge=1, le=90)):
    """
    Get daily token costs for trend chart.

    Args:
        days: Number of days to include (default 30)

    Returns list in chronological order with:
    - date: YYYY-MM-DD
    - tokens, cost_usd, call_count
    """
    return get_token_costs_service().get_daily_trend(days)


@router.get("/api/insights/costs/by-model")
def get_costs_by_model():
    """
    Get token usage and costs broken down by model.

    Returns list sorted by cost (highest first) with:
    - model: Model name/identifier
    - tokens, cost_usd, call_count
    - percentage: Percentage of total cost
    """
    return get_token_costs_service().get_by_model()


# =============================================================================
# RUN MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/api/insights/runs")
def get_insights_runs():
    """
    List all extraction runs with metadata and KPIs.

    Returns list of runs sorted by timestamp (newest first), each with:
    - run_id, timestamp, model, extractor_version, prompt_version
    - claims_count, docs_count, extracted_count, labeled_count
    - presence_rate, accuracy_rate, evidence_rate
    """
    return get_insights_service().list_runs()


@router.get("/api/insights/runs/detailed")
def get_insights_runs_detailed():
    """
    List all extraction runs with detailed metadata including phase metrics.

    Returns list of runs sorted by timestamp (newest first), each with:
    - run_id, timestamp, model, status (complete/partial/failed)
    - duration_seconds, claims_count, docs_total, docs_success, docs_failed
    - phases:
      - ingestion: discovered, ingested, skipped, failed
      - classification: classified, low_confidence, distribution
      - extraction: attempted, succeeded, failed
      - quality_gate: pass, warn, fail
    """
    return get_insights_service().list_runs_detailed()


@router.get("/api/insights/run/{run_id}/overview")
def get_run_overview(run_id: str):
    """Get overview KPIs for a specific run."""
    return get_insights_service().get_run_overview(run_id)


@router.get("/api/insights/run/{run_id}/doc-types")
def get_run_doc_types(run_id: str):
    """Get doc type metrics for a specific run."""
    return get_insights_service().get_run_doc_types(run_id)


@router.get("/api/insights/run/{run_id}/priorities")
def get_run_priorities(run_id: str, limit: int = Query(10, ge=1, le=50)):
    """Get priorities for a specific run."""
    return get_insights_service().get_run_priorities(run_id, limit)


@router.get("/api/insights/compare")
def compare_runs_endpoint(
    baseline: str = Query(..., description="Baseline run ID"),
    current: str = Query(..., description="Current run ID to compare"),
):
    """
    Compare two runs and compute deltas.

    Returns:
    - overview_deltas: delta for each KPI
    - priority_changes: fields that improved/regressed
    - doc_type_deltas: per doc type metric changes
    """
    return get_insights_service().compare_runs(baseline, current)


@router.get("/api/insights/baseline")
def get_baseline_endpoint():
    """Get the current baseline run ID."""
    return get_insights_service().get_baseline()


@router.post("/api/insights/baseline")
def set_baseline_endpoint(run_id: str = Query(..., description="Run ID to set as baseline")):
    """Set a run as the baseline for comparisons."""
    return get_insights_service().set_baseline(run_id)


@router.delete("/api/insights/baseline")
def clear_baseline_endpoint():
    """Clear the baseline setting."""
    return get_insights_service().clear_baseline()
