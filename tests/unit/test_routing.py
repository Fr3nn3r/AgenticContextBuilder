"""Unit tests for the CCI-driven claim routing engine (v2).

Tests CCI-driven tier assignment, REFER handling, verdict override,
informational triggers, threshold overrides, and edge cases.
"""

import importlib.util
from pathlib import Path

import pytest

# Load routing.py directly, bypassing confidence/__init__.py
_routing_path = (
    Path(__file__).resolve().parents[2]
    / "src" / "context_builder" / "confidence" / "routing.py"
)
_spec = importlib.util.spec_from_file_location(
    "context_builder.confidence.routing", _routing_path,
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ClaimRouter = _mod.ClaimRouter
DEFAULT_THRESHOLDS = _mod.DEFAULT_THRESHOLDS

from context_builder.schemas.routing import RoutingTier


@pytest.fixture
def router():
    return ClaimRouter()


# -- CCI-driven tier assignment ------------------------------------------------


class TestCCIDrivenTierAssignment:
    """Tier is determined solely by CCI score."""

    def test_high_cci_green(self, router):
        """CCI 0.85 -> GREEN."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.GREEN

    def test_cci_at_green_boundary(self, router):
        """CCI exactly at 0.70 -> GREEN (>= threshold)."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.70},
        )
        assert result.routing_tier == RoutingTier.GREEN

    def test_cci_just_below_green(self, router):
        """CCI 0.699 -> YELLOW."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.699},
        )
        assert result.routing_tier == RoutingTier.YELLOW

    def test_cci_at_yellow_boundary(self, router):
        """CCI exactly at 0.55 -> YELLOW (>= threshold)."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.55},
        )
        assert result.routing_tier == RoutingTier.YELLOW

    def test_cci_just_below_yellow(self, router):
        """CCI 0.549 -> RED."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.549},
        )
        assert result.routing_tier == RoutingTier.RED

    def test_cci_none_is_red(self, router):
        """CCI None -> RED (safety fallback)."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary=None,
        )
        assert result.routing_tier == RoutingTier.RED
        assert "not available" in result.tier_reason.lower()

    def test_cci_missing_from_summary_is_red(self, router):
        """confidence_summary dict without composite_score -> RED."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"some_other_field": 0.9},
        )
        assert result.routing_tier == RoutingTier.RED


# -- REFER always RED ----------------------------------------------------------


class TestReferAlwaysRed:
    """REFER verdicts always route to RED regardless of CCI."""

    def test_refer_high_cci_still_red(self, router):
        """REFER + CCI 0.95 -> RED."""
        result = router.evaluate(
            verdict="REFER",
            confidence_summary={"composite_score": 0.95},
        )
        assert result.routing_tier == RoutingTier.RED
        assert "REFER" in result.tier_reason

    def test_refer_no_cci_still_red(self, router):
        result = router.evaluate(verdict="REFER")
        assert result.routing_tier == RoutingTier.RED

    def test_refer_original_verdict_preserved(self, router):
        result = router.evaluate(verdict="REFER")
        assert result.original_verdict == "REFER"
        assert result.routed_verdict is None  # no override needed


# -- Verdict override -----------------------------------------------------------


class TestVerdictOverride:
    """RED + APPROVE -> routed_verdict = REFER."""

    def test_red_approve_overrides_to_refer(self, router):
        """Low CCI + APPROVE -> routed to REFER."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.40},
        )
        assert result.routing_tier == RoutingTier.RED
        assert result.routed_verdict == "REFER"
        assert result.original_verdict == "APPROVE"

    def test_red_deny_no_override(self, router):
        """RED + DENY -> no override."""
        result = router.evaluate(
            verdict="DENY",
            confidence_summary={"composite_score": 0.40},
        )
        assert result.routing_tier == RoutingTier.RED
        assert result.routed_verdict is None

    def test_green_approve_no_override(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.GREEN
        assert result.routed_verdict is None

    def test_yellow_approve_no_override(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.60},
        )
        assert result.routing_tier == RoutingTier.YELLOW
        assert result.routed_verdict is None

    def test_red_none_cci_approve_overrides(self, router):
        """No CCI + APPROVE -> RED -> REFER."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary=None,
        )
        assert result.routing_tier == RoutingTier.RED
        assert result.routed_verdict == "REFER"


# -- Informational triggers (the key fix!) -------------------------------------


class TestInformationalTriggers:
    """Triggers fire as annotations but do NOT affect the tier."""

    def test_reconciliation_fail_does_not_override_green(self, router):
        """RT-1 fires but CCI 0.75 still GREEN -- the key fix!"""
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "fail"}},
            confidence_summary={"composite_score": 0.75},
        )
        # Tier is GREEN (driven by CCI), not RED
        assert result.routing_tier == RoutingTier.GREEN
        # But RT-1 still fires as annotation
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert rt1.fired
        assert rt1.severity == RoutingTier.RED

    def test_data_gaps_do_not_override_green(self, router):
        """RT-2 fires but CCI 0.80 still GREEN."""
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={
                "data_gaps": [{"severity": "HIGH"}, {"severity": "HIGH"}],
            },
            confidence_summary={"composite_score": 0.80},
        )
        assert result.routing_tier == RoutingTier.GREEN
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert rt2.fired

    def test_complexity_does_not_override_green(self, router):
        """RT-3 fires but CCI 0.85 still GREEN."""
        items = [{"match_method": "keyword"} for _ in range(40)]
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": items},
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.GREEN
        rt3 = next(t for t in result.all_triggers if t.trigger_id == "RT-3")
        assert rt3.fired

    def test_all_triggers_fire_but_cci_determines_tier(self, router):
        """Multiple triggers fire but tier is based on CCI alone."""
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "fail"}},
            processing_result={
                "data_gaps": [{"severity": "HIGH"}, {"severity": "HIGH"}],
            },
            coverage_analysis={
                "line_items": [{"match_method": "keyword"} for _ in range(40)],
            },
            confidence_summary={"composite_score": 0.72},
        )
        assert result.routing_tier == RoutingTier.GREEN
        assert len(result.triggers_fired) >= 2  # RT-1, RT-2, RT-3 all fire


# -- Tier reason ---------------------------------------------------------------


class TestTierReason:
    """Reason includes CCI score and threshold."""

    def test_green_reason_includes_cci(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.82},
        )
        assert "0.82" in result.tier_reason
        assert "0.7" in result.tier_reason
        assert "GREEN" in result.tier_reason

    def test_yellow_reason_includes_cci(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.63},
        )
        assert "0.63" in result.tier_reason
        assert "0.55" in result.tier_reason
        assert "YELLOW" in result.tier_reason

    def test_red_reason_includes_cci(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.42},
        )
        assert "0.42" in result.tier_reason
        assert "0.55" in result.tier_reason

    def test_refer_reason(self, router):
        result = router.evaluate(verdict="REFER")
        assert "REFER" in result.tier_reason

    def test_none_cci_reason(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary=None,
        )
        assert "not available" in result.tier_reason.lower()


# -- Threshold override from config --------------------------------------------


class TestThresholdOverride:
    """Custom thresholds change CCI tier boundaries."""

    def test_custom_green_threshold(self):
        """Raising green threshold to 0.80: CCI 0.75 -> YELLOW instead of GREEN."""
        custom = dict(DEFAULT_THRESHOLDS)
        custom["cci_green_threshold"] = 0.80
        router = ClaimRouter(thresholds=custom)

        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.75},
        )
        assert result.routing_tier == RoutingTier.YELLOW

    def test_custom_yellow_threshold(self):
        """Lowering yellow threshold to 0.40: CCI 0.45 -> YELLOW instead of RED."""
        custom = dict(DEFAULT_THRESHOLDS)
        custom["cci_yellow_threshold"] = 0.40
        router = ClaimRouter(thresholds=custom)

        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.45},
        )
        assert result.routing_tier == RoutingTier.YELLOW

    def test_custom_thresholds_stored_in_decision(self):
        """Custom thresholds are recorded in the decision for auditability."""
        custom = dict(DEFAULT_THRESHOLDS)
        custom["cci_green_threshold"] = 0.80
        custom["cci_yellow_threshold"] = 0.40
        router = ClaimRouter(thresholds=custom)

        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.60},
        )
        assert result.cci_threshold_green == 0.80
        assert result.cci_threshold_yellow == 0.40


# -- RT-4 removed ---------------------------------------------------------------


class TestRT4Removed:
    """RT-4 (coverage_missing_on_approve) is no longer in the trigger set."""

    def test_no_rt4_in_all_triggers(self, router):
        result = router.evaluate(verdict="APPROVE")
        ids = {t.trigger_id for t in result.all_triggers}
        assert "RT-4" not in ids

    def test_trigger_count_is_five(self, router):
        result = router.evaluate(verdict="APPROVE")
        assert result.triggers_evaluated == 5
        assert len(result.all_triggers) == 5


# -- All triggers evaluated -----------------------------------------------------


class TestAllTriggersEvaluated:
    """All 5 informational triggers are always evaluated."""

    def test_trigger_ids_complete(self, router):
        result = router.evaluate(verdict="APPROVE")
        ids = {t.trigger_id for t in result.all_triggers}
        assert ids == {"RT-1", "RT-2", "RT-3", "RT-5", "RT-6"}


# -- Structural CCI passthrough -------------------------------------------------


class TestStructuralCCI:
    """Structural CCI is passed through to routing decision."""

    def test_cci_included(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.782},
        )
        assert result.structural_cci == pytest.approx(0.782)

    def test_no_cci_is_none(self, router):
        result = router.evaluate(verdict="APPROVE")
        assert result.structural_cci is None


# -- Schema version -------------------------------------------------------------


class TestSchemaVersion:
    """Routing decision uses v2 schema."""

    def test_schema_version_v2(self, router):
        result = router.evaluate(verdict="APPROVE")
        assert result.schema_version == "routing_decision_v2"


# -- Individual trigger behavior (informational, no tier impact) ----------------


class TestRT1ReconciliationGateFail:
    """RT-1: Reconciliation gate fail fires as annotation."""

    def test_gate_fail_fires(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "fail"}},
            confidence_summary={"composite_score": 0.80},
        )
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert rt1.fired
        assert rt1.severity == RoutingTier.RED

    def test_gate_pass_does_not_fire(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "pass"}},
            confidence_summary={"composite_score": 0.80},
        )
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert not rt1.fired

    def test_no_reconciliation_report(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report=None,
            confidence_summary={"composite_score": 0.80},
        )
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert not rt1.fired


class TestRT2HighImpactDataGaps:
    """RT-2: HIGH-severity data gaps fire as annotation."""

    def test_one_high_gap_fires_yellow(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={"data_gaps": [{"severity": "HIGH"}]},
            confidence_summary={"composite_score": 0.80},
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert rt2.fired
        assert rt2.severity == RoutingTier.YELLOW

    def test_two_high_gaps_fires_red(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={
                "data_gaps": [{"severity": "HIGH"}, {"severity": "HIGH"}],
            },
            confidence_summary={"composite_score": 0.80},
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert rt2.fired
        assert rt2.severity == RoutingTier.RED

    def test_medium_gaps_do_not_fire(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={
                "data_gaps": [{"severity": "MEDIUM"}, {"severity": "LOW"}],
            },
            confidence_summary={"composite_score": 0.80},
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert not rt2.fired


class TestRT5LowStructuralCCI:
    """RT-5: Low CCI on APPROVE fires as annotation."""

    def test_low_cci_approve_fires(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.40},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert rt5.fired

    def test_high_cci_approve_does_not_fire(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.80},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert not rt5.fired

    def test_low_cci_deny_does_not_fire(self, router):
        result = router.evaluate(
            verdict="DENY",
            confidence_summary={"composite_score": 0.40},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert not rt5.fired


class TestRT6ExcludedPartWithCoveredLabor:
    """RT-6: Excluded parts with covered labor fires as annotation."""

    def test_fires_when_excluded_parts_and_covered_labor(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={
                "line_items": [
                    {
                        "item_type": "parts",
                        "coverage_status": "NOT_COVERED",
                        "exclusion_reason": "component_excluded",
                    },
                    {
                        "item_type": "labor",
                        "coverage_status": "COVERED",
                    },
                ],
            },
            confidence_summary={"composite_score": 0.85},
        )
        rt6 = next(t for t in result.all_triggers if t.trigger_id == "RT-6")
        assert rt6.fired
        assert rt6.severity == RoutingTier.YELLOW

    def test_does_not_fire_when_covered_parts_exist(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={
                "line_items": [
                    {
                        "item_type": "parts",
                        "coverage_status": "NOT_COVERED",
                        "exclusion_reason": "component_excluded",
                    },
                    {
                        "item_type": "parts",
                        "coverage_status": "COVERED",
                    },
                    {
                        "item_type": "labor",
                        "coverage_status": "COVERED",
                    },
                ],
            },
            confidence_summary={"composite_score": 0.85},
        )
        rt6 = next(t for t in result.all_triggers if t.trigger_id == "RT-6")
        assert not rt6.fired

    def test_does_not_fire_for_deny_verdicts(self, router):
        result = router.evaluate(
            verdict="DENY",
            coverage_analysis={
                "line_items": [
                    {
                        "item_type": "parts",
                        "coverage_status": "NOT_COVERED",
                        "exclusion_reason": "component_excluded",
                    },
                    {
                        "item_type": "labor",
                        "coverage_status": "COVERED",
                    },
                ],
            },
            confidence_summary={"composite_score": 0.85},
        )
        rt6 = next(t for t in result.all_triggers if t.trigger_id == "RT-6")
        assert not rt6.fired
