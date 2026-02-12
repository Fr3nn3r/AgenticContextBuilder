"""Composite Confidence Index (CCI) package.

Collects data-quality signals from every pipeline stage and computes
a single composite confidence score with full traceability.

Primary entry point::

    from context_builder.confidence import compute_confidence

    summary = compute_confidence(
        claim_id="64166",
        claim_run_id="clm_...",
        extraction_results=[...],
        reconciliation_report={...},
        coverage_analysis={...},
        screening_result={...},
        processing_result={...},
        decision_result={...},
    )
"""

from typing import Any, Dict, List, Optional

from context_builder.confidence.collector import ConfidenceCollector
from context_builder.confidence.scorer import ConfidenceScorer
from context_builder.confidence.stage import ConfidenceStage
from context_builder.schemas.confidence import ConfidenceSummary


def compute_confidence(
    *,
    claim_id: str = "",
    claim_run_id: str = "",
    extraction_results: Optional[List[Dict[str, Any]]] = None,
    reconciliation_report: Optional[Dict[str, Any]] = None,
    coverage_analysis: Optional[Dict[str, Any]] = None,
    screening_result: Optional[Dict[str, Any]] = None,
    processing_result: Optional[Dict[str, Any]] = None,
    decision_result: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
    verdict: str = "",
) -> Optional[ConfidenceSummary]:
    """Compute the Composite Confidence Index from upstream stage data.

    Pure computation function with no disk I/O or side effects.
    All inputs are plain dicts; returns a ConfidenceSummary or None
    if no signals could be collected.

    Args:
        claim_id: Claim identifier (for the summary record).
        claim_run_id: Run identifier (for the summary record).
        extraction_results: Per-doc extraction dicts with ``fields``,
            ``doc_type_confidence``, etc.  May be synthesised from
            claim_facts when raw extraction files are unavailable.
        reconciliation_report: Reconciliation report dict with ``gate``,
            ``conflicts``, ``fact_count``, etc.
        coverage_analysis: Coverage analysis dict with ``line_items``,
            ``primary_repair``, etc.
        screening_result: Screening result dict with ``checks_passed``,
            ``checks_failed``, ``checks``, etc.
        processing_result: Assessment/processing result dict with
            ``confidence_score``, ``data_gaps``, ``fraud_indicators``.
        decision_result: Decision dossier dict with
            ``clause_evaluations``, ``assumptions_used``, etc.
        weights: Optional custom component weights.  If None, uses
            DEFAULT_WEIGHTS for APPROVE/REFER or DENY_WEIGHTS for DENY.
        verdict: Claim verdict (``"APPROVE"``, ``"DENY"``, ``"REFER"``).
            Controls signal polarity, weight selection, and whether
            the coverage concordance signal is emitted.  If empty,
            auto-detected from ``decision_result["claim_verdict"]``.

    Returns:
        A ConfidenceSummary with composite score, band, component
        breakdown, and collected signals.  Returns None if no signals
        could be collected from any stage.
    """
    # Auto-detect verdict from decision dossier if not provided
    if not verdict and decision_result:
        verdict = (decision_result.get("claim_verdict") or "").upper()

    collector = ConfidenceCollector()
    signals = collector.collect_all(
        extraction_results=extraction_results or [],
        reconciliation_report=reconciliation_report,
        coverage_analysis=coverage_analysis,
        screening_result=screening_result,
        processing_result=processing_result,
        decision_result=decision_result,
        verdict=verdict,
    )

    if not signals:
        return None

    scorer = ConfidenceScorer(weights=weights)
    summary = scorer.compute(
        signals=signals,
        claim_id=claim_id,
        claim_run_id=claim_run_id,
        verdict=verdict,
    )
    _enrich_data_completeness_detail(summary, reconciliation_report, processing_result)
    return summary


def _enrich_data_completeness_detail(
    summary: ConfidenceSummary,
    reconciliation_report: Optional[Dict[str, Any]],
    processing_result: Optional[Dict[str, Any]],
) -> None:
    """Attach structured detail to the data_completeness component."""
    comp = next(
        (c for c in summary.component_scores if c.component == "data_completeness"),
        None,
    )
    if comp is None:
        return

    detail: Dict[str, Any] = {}

    if reconciliation_report:
        gate = reconciliation_report.get("gate") or {}
        missing = gate.get("missing_critical_facts") or []
        spec = reconciliation_report.get("critical_facts_spec") or []
        present = reconciliation_report.get("critical_facts_present") or []
        detail["critical_facts_total"] = len(spec)
        detail["critical_facts_present"] = len(present)
        if missing:
            detail["missing_critical_facts"] = list(missing)

    if processing_result:
        gaps = processing_result.get("data_gaps") or []
        if gaps:
            detail["data_gaps"] = [
                {"field": g.get("field", ""), "impact": g.get("impact", "")}
                for g in gaps
                if isinstance(g, dict)
            ]

    if detail:
        comp.detail = detail


__all__ = [
    "ConfidenceCollector",
    "ConfidenceScorer",
    "ConfidenceStage",
    "compute_confidence",
]
