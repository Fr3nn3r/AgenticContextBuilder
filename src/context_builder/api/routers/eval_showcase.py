"""Eval showcase router - endpoint for metrics history data."""

import json

from fastapi import APIRouter, HTTPException

from context_builder.api.dependencies import get_workspace_path

router = APIRouter(tags=["eval-showcase"])


@router.get("/api/eval-showcase/metrics-history")
def get_metrics_history():
    """Get full metrics history for the eval showcase dashboard.

    Reads metrics_history.json from the active workspace's eval directory
    and returns the raw JSON for client-side computation.
    """
    metrics_path = get_workspace_path() / "eval" / "metrics_history.json"
    if not metrics_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No metrics history found. Run evaluations first.",
        )
    return json.loads(metrics_path.read_text(encoding="utf-8"))
