"""Confidence scorer for the Composite Confidence Index.

Takes a list of ``SignalSnapshot`` objects and computes a weighted
composite score with five components.  If a component has zero signals
its weight is redistributed proportionally to the remaining components.
"""

import logging
from typing import Dict, List, Optional

from context_builder.schemas.confidence import (
    ConfidenceBand,
    ConfidenceIndex,
    ConfidenceSummary,
    ComponentScore,
    SignalSnapshot,
)

logger = logging.getLogger(__name__)

# ── Default weights ──────────────────────────────────────────────────

DEFAULT_WEIGHTS: Dict[str, float] = {
    "document_quality": 0.20,
    "data_completeness": 0.15,
    "consistency": 0.15,
    "coverage_reliability": 0.35,
    "decision_clarity": 0.15,
}

# ── Signal-to-component mapping ─────────────────────────────────────

COMPONENT_SIGNALS: Dict[str, List[str]] = {
    "document_quality": [
        "extraction.avg_field_confidence",
        "extraction.avg_doc_type_confidence",
        "extraction.quality_gate_pass_rate",
        "extraction.provenance_match_rate",
        "extraction.verified_evidence_rate",
    ],
    "data_completeness": [
        "reconciliation.provenance_coverage",
        "reconciliation.critical_facts_rate",
        "assessment.data_gap_penalty",
    ],
    "consistency": [
        "reconciliation.conflict_rate",
        "reconciliation.gate_status_score",
    ],
    "coverage_reliability": [
        "coverage.avg_match_confidence",
        "coverage.review_needed_rate",
        "coverage.method_diversity",
        "coverage.primary_repair_confidence",
    ],
    "decision_clarity": [
        "screening.pass_rate",
        "screening.inconclusive_rate",
        "screening.hard_fail_clarity",
        "decision.tier1_ratio",
        "decision.assumption_reliance",
        "assessment.fraud_indicator_penalty",
    ],
}


def score_to_band(score: float) -> ConfidenceBand:
    """Map a 0-1 composite score to a qualitative band."""
    if score >= 0.80:
        return ConfidenceBand.HIGH
    elif score >= 0.55:
        return ConfidenceBand.MODERATE
    else:
        return ConfidenceBand.LOW


class ConfidenceScorer:
    """Computes the Composite Confidence Index from collected signals."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.weights = dict(weights or DEFAULT_WEIGHTS)

    def compute(
        self,
        signals: List[SignalSnapshot],
        claim_id: str = "",
        claim_run_id: str = "",
    ) -> ConfidenceSummary:
        """Compute full CCI summary from signals.

        Args:
            signals: All collected SignalSnapshot objects.
            claim_id: Claim identifier (for the summary).
            claim_run_id: Run ID (for the summary).

        Returns:
            Complete ConfidenceSummary with component breakdown.
        """
        # Index signals by name for fast lookup
        signal_map: Dict[str, SignalSnapshot] = {
            s.signal_name: s for s in signals
        }

        # Build component scores
        component_scores: List[ComponentScore] = []
        active_weights: Dict[str, float] = {}
        stages_available: set = set()
        stages_missing: set = set()

        for comp_name, sig_names in COMPONENT_SIGNALS.items():
            matched = [signal_map[n] for n in sig_names if n in signal_map]

            if matched:
                score = sum(s.normalized_value for s in matched) / len(matched)
                active_weights[comp_name] = self.weights.get(comp_name, 0.0)
                for s in matched:
                    stages_available.add(s.source_stage)
            else:
                score = 0.0
                # Track which stages are missing
                for sn in sig_names:
                    stage = sn.split(".")[0]
                    stages_missing.add(stage)

            component_scores.append(ComponentScore(
                component=comp_name,
                score=round(score, 4),
                weight=self.weights.get(comp_name, 0.0),
                weighted_contribution=0.0,  # filled below
                signals_used=matched,
                notes="" if matched else "no signals available",
            ))

        # Apply line_item_complexity as a multiplier on coverage_reliability
        # (not averaged — it scales the component score directly)
        _complexity = signal_map.get("coverage.line_item_complexity")
        if _complexity is not None:
            for cs in component_scores:
                if cs.component == "coverage_reliability":
                    cs.score = round(cs.score * _complexity.normalized_value, 4)
                    cs.signals_used.append(_complexity)
                    break

        # Redistribute weights (only active components participate)
        total_active_weight = sum(active_weights.values())
        if total_active_weight > 0:
            for cs in component_scores:
                if cs.component in active_weights:
                    effective_weight = active_weights[cs.component] / total_active_weight
                    cs.weighted_contribution = round(cs.score * effective_weight, 4)
                    if total_active_weight < 0.999:  # some weights redistributed
                        cs.notes = f"effective weight {effective_weight:.3f} (redistributed)"
        else:
            total_active_weight = 1.0  # avoid division by zero

        # Composite score
        composite = sum(cs.weighted_contribution for cs in component_scores)
        composite = round(max(0.0, min(1.0, composite)), 4)
        band = score_to_band(composite)

        # Build effective weights dict
        weights_used: Dict[str, float] = {}
        for cs in component_scores:
            if cs.component in active_weights and total_active_weight > 0:
                weights_used[cs.component] = round(
                    active_weights[cs.component] / total_active_weight, 4
                )
            else:
                weights_used[cs.component] = 0.0

        # Flags
        flags: List[str] = []
        stages_missing -= stages_available  # only truly missing
        if "extraction" in stages_missing:
            flags.append("extraction data missing")
        if "reconciliation" in stages_missing:
            flags.append("reconciliation data missing")
        if "coverage" in stages_missing:
            flags.append("coverage data missing")
        if "screening" in stages_missing:
            flags.append("screening data missing")
        if "decision" in stages_missing:
            flags.append("decision data missing")
        if len(active_weights) < len(COMPONENT_SIGNALS):
            flags.append(
                f"only {len(active_weights)}/{len(COMPONENT_SIGNALS)} components active"
            )

        return ConfidenceSummary(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            composite_score=composite,
            band=band,
            component_scores=component_scores,
            weights_used=weights_used,
            signals_collected=signals,
            stages_available=sorted(stages_available),
            stages_missing=sorted(stages_missing),
            flags=flags,
        )

    def to_confidence_index(self, summary: ConfidenceSummary) -> ConfidenceIndex:
        """Extract compact ConfidenceIndex from a full summary."""
        return ConfidenceIndex(
            composite_score=summary.composite_score,
            band=summary.band,
            components={
                cs.component: cs.score for cs in summary.component_scores
            },
        )
