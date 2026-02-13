"""CCI-driven claim routing engine (v2).

Uses the Composite Confidence Index as the **sole driver** of tier
assignment.  Structural triggers are kept as informational annotations
for the audit trail but do NOT affect the tier.

Tier logic:
    If verdict == REFER            -> RED  (always)
    If CCI is None                 -> RED  (safety fallback)
    If CCI >= cci_green_threshold  -> GREEN
    If CCI >= cci_yellow_threshold -> YELLOW
    If CCI < cci_yellow_threshold  -> RED

Informational triggers (annotations only):
    RT-1  reconciliation_gate_fail       gate.status == "fail"
    RT-2  high_impact_data_gap           >= 1 HIGH-severity data gap
    RT-3  coverage_complexity_extreme    > 25 line items
    RT-5  low_structural_cci             CCI < 0.55 AND verdict APPROVE
    RT-6  excluded_part_with_covered_labor  excluded parts + covered labor

RT-4 (coverage_missing_on_approve) has been removed -- it was a
pipeline-data concern, not a routing concern.

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

# -- Default thresholds -------------------------------------------------------

DEFAULT_THRESHOLDS: Dict[str, Any] = {
    # CCI-driven tier thresholds (v2)
    "cci_green_threshold": 0.70,
    "cci_yellow_threshold": 0.55,

    # RT-2: high-impact data gaps (informational)
    "high_impact_data_gap_yellow": 1,   # >= 1 HIGH gap
    "high_impact_data_gap_red": 2,      # >= 2 HIGH gaps

    # RT-3: coverage complexity (informational)
    "complexity_yellow": 26,   # >= 26 items
    "complexity_red": 36,      # >= 36 items

    # RT-5: low structural CCI (informational)
    "low_cci_threshold": 0.55,

    # RT-6: excluded parts with covered labor (informational)
    "excluded_part_labor_severity": "YELLOW",
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
    """CCI-driven router: assigns tier from CCI score, keeps triggers as annotations."""

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
        """Evaluate CCI-driven routing and produce a RoutingDecision.

        The tier is determined solely by the CCI score and the verdict.
        Structural triggers are evaluated as informational annotations.
        """
        verdict_upper = verdict.upper().strip()

        # -- Extract CCI --
        cci: Optional[float] = None
        if confidence_summary:
            cci = confidence_summary.get("composite_score")

        # -- CCI thresholds --
        green_threshold = self.thresholds.get(
            "cci_green_threshold", DEFAULT_THRESHOLDS["cci_green_threshold"]
        )
        yellow_threshold = self.thresholds.get(
            "cci_yellow_threshold", DEFAULT_THRESHOLDS["cci_yellow_threshold"]
        )

        # -- Determine tier from CCI --
        if verdict_upper == "REFER":
            tier = RoutingTier.RED
            tier_reason = "Original verdict is REFER"
        elif cci is None:
            tier = RoutingTier.RED
            tier_reason = "CCI not available (safety fallback)"
        elif cci >= green_threshold:
            tier = RoutingTier.GREEN
            tier_reason = f"CCI {cci:.3f} >= {green_threshold} (GREEN threshold)"
        elif cci >= yellow_threshold:
            tier = RoutingTier.YELLOW
            tier_reason = f"CCI {cci:.3f} >= {yellow_threshold} (YELLOW threshold)"
        else:
            tier = RoutingTier.RED
            tier_reason = f"CCI {cci:.3f} < {yellow_threshold} (below YELLOW threshold)"

        # -- Run informational triggers (annotations only) --
        all_triggers: List[RoutingTriggerResult] = []
        all_triggers.append(self._check_reconciliation_gate(reconciliation_report))
        all_triggers.append(self._check_high_impact_data_gaps(processing_result))
        all_triggers.append(self._check_coverage_complexity(coverage_analysis))
        all_triggers.append(
            self._check_low_structural_cci(confidence_summary, verdict_upper)
        )
        all_triggers.append(
            self._check_excluded_part_with_covered_labor(
                coverage_analysis, verdict_upper,
            )
        )

        fired = [t for t in all_triggers if t.fired]

        # -- Verdict override: RED + APPROVE -> REFER --
        routed_verdict = None
        if tier == RoutingTier.RED and verdict_upper == "APPROVE":
            routed_verdict = "REFER"

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
            structural_cci=cci,
            cci_threshold_green=green_threshold,
            cci_threshold_yellow=yellow_threshold,
        )

    # -- Individual trigger checks (informational) -------------------------

    def _check_reconciliation_gate(
        self, reconciliation_report: Optional[Dict[str, Any]]
    ) -> RoutingTriggerResult:
        """RT-1: Reconciliation gate fail (informational)."""
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
        """RT-2: HIGH-severity data gaps (informational)."""
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
            explanation = f"{high_gaps} HIGH-severity data gaps (>= {red_threshold})"
        elif high_gaps >= yellow_threshold:
            fired = True
            severity = RoutingTier.YELLOW
            explanation = f"{high_gaps} HIGH-severity data gap(s) (>= {yellow_threshold})"
        else:
            fired = False
            severity = RoutingTier.YELLOW
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
        """RT-3: Extreme line item count (informational)."""
        n_items = 0
        if coverage_analysis:
            line_items = coverage_analysis.get("line_items") or []
            n_items = len(line_items)

        yellow_threshold = self.thresholds["complexity_yellow"]
        red_threshold = self.thresholds["complexity_red"]

        if n_items >= red_threshold:
            fired = True
            severity = RoutingTier.RED
            explanation = f"{n_items} line items (>= {red_threshold})"
        elif n_items >= yellow_threshold:
            fired = True
            severity = RoutingTier.YELLOW
            explanation = f"{n_items} line items (>= {yellow_threshold})"
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

    def _check_low_structural_cci(
        self,
        confidence_summary: Optional[Dict[str, Any]],
        verdict: str,
    ) -> RoutingTriggerResult:
        """RT-5: Low structural CCI on APPROVE (informational)."""
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
                f"Structural CCI {cci:.3f} < {threshold} on APPROVE"
                if fired
                else (
                    f"CCI {cci:.3f} >= {threshold}"
                    if cci is not None
                    else "CCI not available"
                )
            ),
        )

    def _check_excluded_part_with_covered_labor(
        self,
        coverage_analysis: Optional[Dict[str, Any]],
        verdict: str,
    ) -> RoutingTriggerResult:
        """RT-6: Excluded parts with covered labor but no covered parts (informational).

        Safety net for cases where labor is marked COVERED but the only parts
        on the invoice are excluded by policy.
        Only fires on APPROVE verdicts (DENY claims are already denied).
        """
        severity_str = self.thresholds.get("excluded_part_labor_severity", "YELLOW")
        severity = (
            RoutingTier.RED if severity_str == "RED" else RoutingTier.YELLOW
        )

        if verdict != "APPROVE" or not coverage_analysis:
            return RoutingTriggerResult(
                trigger_id="RT-6",
                name="excluded_part_with_covered_labor",
                fired=False,
                severity=severity,
                signal_value=None,
                threshold="excluded parts + covered labor + no covered parts",
                explanation=(
                    "Not applicable (verdict is not APPROVE)"
                    if verdict != "APPROVE"
                    else "No coverage analysis available"
                ),
            )

        line_items = coverage_analysis.get("line_items") or []

        has_excluded_parts = False
        has_covered_labor = False
        has_covered_parts = False

        for li in line_items:
            item_type = li.get("item_type", "")
            status = str(li.get("coverage_status", "")).upper()

            if item_type in ("parts", "part", "piece"):
                if status == "COVERED":
                    has_covered_parts = True
                elif status == "NOT_COVERED" and li.get("exclusion_reason"):
                    has_excluded_parts = True
            elif item_type in ("labor", "labour", "main d'oeuvre", "arbeit"):
                if status == "COVERED":
                    has_covered_labor = True

        fired = (
            has_excluded_parts
            and has_covered_labor
            and not has_covered_parts
        )

        return RoutingTriggerResult(
            trigger_id="RT-6",
            name="excluded_part_with_covered_labor",
            fired=fired,
            severity=severity,
            signal_value={
                "excluded_parts": has_excluded_parts,
                "covered_labor": has_covered_labor,
                "covered_parts": has_covered_parts,
            },
            threshold="excluded parts + covered labor + no covered parts",
            explanation=(
                "Excluded parts with covered labor but no covered parts "
                "-> inconsistency detected"
                if fired
                else "No excluded-part/labor inconsistency"
            ),
        )
