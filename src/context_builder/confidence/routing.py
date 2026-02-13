"""Claim routing engine with deterministic trigger checks.

Evaluates 5 structural triggers to route claims into GREEN / YELLOW / RED
tiers.  RED triggers override the verdict to REFER_TO_HUMAN.

Trigger summary:
    RT-1  reconciliation_gate_fail       gate.status == "fail"           -> RED
    RT-2  high_impact_data_gap           >= 1 HIGH-severity data gap     -> YELLOW (1) / RED (2+)
    RT-3  coverage_complexity_extreme    > 25 line items                 -> YELLOW (26-35) / RED (36+)
    RT-4  coverage_missing_on_approve    no coverage AND verdict APPROVE -> RED
    RT-5  low_structural_cci             CCI < 0.55 AND verdict APPROVE -> RED

Thresholds are constants with optional workspace-level override via
``config/confidence/routing_thresholds.yaml``.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from context_builder.schemas.routing import (
    RoutingDecision,
    RoutingTier,
    RoutingTriggerResult,
)

logger = logging.getLogger(__name__)

# ── Default thresholds ───────────────────────────────────────────────

DEFAULT_THRESHOLDS: Dict[str, Any] = {
    # RT-2: high-impact data gaps
    "high_impact_data_gap_yellow": 1,   # >= 1 HIGH gap -> YELLOW
    "high_impact_data_gap_red": 2,      # >= 2 HIGH gaps -> RED

    # RT-3: coverage complexity (line item count)
    "complexity_yellow": 26,   # >= 26 items -> YELLOW
    "complexity_red": 36,      # >= 36 items -> RED

    # RT-5: low structural CCI
    "low_cci_threshold": 0.55,
}


def load_thresholds(workspace_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load routing thresholds, with optional workspace override.

    Looks for ``config/confidence/routing_thresholds.yaml`` in the
    workspace.  Missing keys fall back to DEFAULT_THRESHOLDS.
    """
    thresholds = dict(DEFAULT_THRESHOLDS)
    if workspace_path is None:
        return thresholds

    yaml_path = workspace_path / "config" / "confidence" / "routing_thresholds.yaml"
    if not yaml_path.exists():
        return thresholds

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            for key in DEFAULT_THRESHOLDS:
                if key in data:
                    thresholds[key] = data[key]
            logger.info(f"Loaded routing thresholds override from {yaml_path}")
    except Exception:
        logger.warning(f"Could not load routing thresholds from {yaml_path}", exc_info=True)

    return thresholds


class ClaimRouter:
    """Evaluates structural triggers to route claims into processing tiers."""

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None) -> None:
        self.thresholds = thresholds or dict(DEFAULT_THRESHOLDS)

    def evaluate(
        self,
        *,
        claim_id: str = "",
        claim_run_id: str = "",
        verdict: str = "",
        reconciliation_report: Optional[Dict[str, Any]] = None,
        coverage_analysis: Optional[Dict[str, Any]] = None,
        processing_result: Optional[Dict[str, Any]] = None,
        confidence_summary: Optional[Dict[str, Any]] = None,
    ) -> RoutingDecision:
        """Evaluate all routing triggers and produce a RoutingDecision.

        Args:
            claim_id: Claim identifier.
            claim_run_id: Run identifier.
            verdict: Original verdict (APPROVE, DENY, REFER).
            reconciliation_report: Reconciliation report dict.
            coverage_analysis: Coverage analysis dict.
            processing_result: Assessment/processing result dict.
            confidence_summary: CCI summary dict with composite_score.

        Returns:
            RoutingDecision with tier, all trigger results, and reason.
        """
        verdict_upper = verdict.upper().strip()
        all_triggers: List[RoutingTriggerResult] = []

        # RT-1: Reconciliation gate fail
        all_triggers.append(self._check_reconciliation_gate(reconciliation_report))

        # RT-2: High-impact data gaps
        all_triggers.append(self._check_high_impact_data_gaps(processing_result))

        # RT-3: Coverage complexity (extreme line item count)
        all_triggers.append(self._check_coverage_complexity(coverage_analysis))

        # RT-4: Coverage missing on APPROVE
        all_triggers.append(
            self._check_coverage_missing_on_approve(coverage_analysis, verdict_upper)
        )

        # RT-5: Low structural CCI on APPROVE
        all_triggers.append(
            self._check_low_structural_cci(confidence_summary, verdict_upper)
        )

        # Determine tier: worst of all fired triggers
        fired = [t for t in all_triggers if t.fired]
        if verdict_upper == "REFER":
            # REFER verdicts always route to RED
            tier = RoutingTier.RED
            tier_reason = "Original verdict is REFER"
        elif any(t.severity == RoutingTier.RED for t in fired):
            tier = RoutingTier.RED
            red_names = [t.name for t in fired if t.severity == RoutingTier.RED]
            tier_reason = f"RED triggers: {', '.join(red_names)}"
        elif any(t.severity == RoutingTier.YELLOW for t in fired):
            tier = RoutingTier.YELLOW
            yellow_names = [t.name for t in fired if t.severity == RoutingTier.YELLOW]
            tier_reason = f"YELLOW triggers: {', '.join(yellow_names)}"
        else:
            tier = RoutingTier.GREEN
            tier_reason = "No triggers fired"

        # Determine routed verdict
        routed_verdict = None
        if tier == RoutingTier.RED and verdict_upper == "APPROVE":
            routed_verdict = "REFER"

        # Extract structural CCI
        structural_cci = None
        if confidence_summary:
            structural_cci = confidence_summary.get("composite_score")

        return RoutingDecision(
            claim_id=claim_id,
            claim_run_id=claim_run_id,
            original_verdict=verdict_upper,
            routed_verdict=routed_verdict,
            routing_tier=tier,
            triggers_evaluated=len(all_triggers),
            triggers_fired=fired,
            all_triggers=all_triggers,
            tier_reason=tier_reason,
            structural_cci=structural_cci,
        )

    # ── Individual trigger checks ────────────────────────────────────

    def _check_reconciliation_gate(
        self, reconciliation_report: Optional[Dict[str, Any]]
    ) -> RoutingTriggerResult:
        """RT-1: Reconciliation gate fail -> RED."""
        gate_status = None
        if reconciliation_report:
            gate = reconciliation_report.get("gate") or {}
            gate_status = str(gate.get("status", "")).lower()

        fired = gate_status == "fail"
        return RoutingTriggerResult(
            trigger_id="RT-1",
            name="reconciliation_gate_fail",
            fired=fired,
            severity=RoutingTier.RED,
            signal_value=gate_status,
            threshold="fail",
            explanation=(
                "Reconciliation gate FAIL: critical data inconsistencies detected"
                if fired
                else "Reconciliation gate passed or not available"
            ),
        )

    def _check_high_impact_data_gaps(
        self, processing_result: Optional[Dict[str, Any]]
    ) -> RoutingTriggerResult:
        """RT-2: HIGH-severity data gaps -> YELLOW (1) / RED (2+)."""
        high_gaps = 0
        if processing_result:
            data_gaps = processing_result.get("data_gaps") or []
            high_gaps = sum(
                1 for g in data_gaps
                if str(g.get("severity", "")).upper() == "HIGH"
            )

        yellow_threshold = self.thresholds["high_impact_data_gap_yellow"]
        red_threshold = self.thresholds["high_impact_data_gap_red"]

        if high_gaps >= red_threshold:
            fired = True
            severity = RoutingTier.RED
            explanation = f"{high_gaps} HIGH-severity data gaps (>= {red_threshold} -> RED)"
        elif high_gaps >= yellow_threshold:
            fired = True
            severity = RoutingTier.YELLOW
            explanation = f"{high_gaps} HIGH-severity data gap(s) (>= {yellow_threshold} -> YELLOW)"
        else:
            fired = False
            severity = RoutingTier.YELLOW  # default if it were to fire
            explanation = f"{high_gaps} HIGH-severity data gaps (below threshold)"

        return RoutingTriggerResult(
            trigger_id="RT-2",
            name="high_impact_data_gap",
            fired=fired,
            severity=severity,
            signal_value=high_gaps,
            threshold=f"YELLOW>={yellow_threshold}, RED>={red_threshold}",
            explanation=explanation,
        )

    def _check_coverage_complexity(
        self, coverage_analysis: Optional[Dict[str, Any]]
    ) -> RoutingTriggerResult:
        """RT-3: Extreme line item count -> YELLOW / RED."""
        n_items = 0
        if coverage_analysis:
            line_items = coverage_analysis.get("line_items") or []
            n_items = len(line_items)

        yellow_threshold = self.thresholds["complexity_yellow"]
        red_threshold = self.thresholds["complexity_red"]

        if n_items >= red_threshold:
            fired = True
            severity = RoutingTier.RED
            explanation = f"{n_items} line items (>= {red_threshold} -> RED)"
        elif n_items >= yellow_threshold:
            fired = True
            severity = RoutingTier.YELLOW
            explanation = f"{n_items} line items (>= {yellow_threshold} -> YELLOW)"
        else:
            fired = False
            severity = RoutingTier.YELLOW
            explanation = f"{n_items} line items (below complexity threshold)"

        return RoutingTriggerResult(
            trigger_id="RT-3",
            name="coverage_complexity_extreme",
            fired=fired,
            severity=severity,
            signal_value=n_items,
            threshold=f"YELLOW>={yellow_threshold}, RED>={red_threshold}",
            explanation=explanation,
        )

    def _check_coverage_missing_on_approve(
        self,
        coverage_analysis: Optional[Dict[str, Any]],
        verdict: str,
    ) -> RoutingTriggerResult:
        """RT-4: No coverage analysis AND verdict is APPROVE -> RED."""
        has_coverage = coverage_analysis is not None and bool(
            coverage_analysis.get("line_items")
        )
        fired = not has_coverage and verdict == "APPROVE"

        return RoutingTriggerResult(
            trigger_id="RT-4",
            name="coverage_missing_on_approve",
            fired=fired,
            severity=RoutingTier.RED,
            signal_value=has_coverage,
            threshold="coverage required for APPROVE",
            explanation=(
                "APPROVE verdict without coverage analysis -> RED"
                if fired
                else (
                    "Coverage analysis present"
                    if has_coverage
                    else "Not applicable (verdict is not APPROVE)"
                )
            ),
        )

    def _check_low_structural_cci(
        self,
        confidence_summary: Optional[Dict[str, Any]],
        verdict: str,
    ) -> RoutingTriggerResult:
        """RT-5: Low structural CCI on APPROVE -> RED."""
        cci = None
        if confidence_summary:
            cci = confidence_summary.get("composite_score")

        threshold = self.thresholds["low_cci_threshold"]
        fired = (
            cci is not None
            and cci < threshold
            and verdict == "APPROVE"
        )

        return RoutingTriggerResult(
            trigger_id="RT-5",
            name="low_structural_cci",
            fired=fired,
            severity=RoutingTier.RED,
            signal_value=cci,
            threshold=threshold,
            explanation=(
                f"Structural CCI {cci:.3f} < {threshold} on APPROVE -> RED"
                if fired
                else (
                    f"CCI {cci:.3f} >= {threshold}"
                    if cci is not None
                    else "CCI not available"
                )
            ),
        )
