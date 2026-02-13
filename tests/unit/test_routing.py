"""Unit tests for the claim routing engine (ClaimRouter).

Tests all 5 deterministic triggers, tier computation, REFER handling,
threshold overrides, and edge cases.
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


# ── RT-1: Reconciliation gate fail ──────────────────────────────────


class TestRT1ReconciliationGateFail:
    """RT-1: Reconciliation gate fail -> RED."""

    def test_gate_fail_fires_red(self, router):
        result = router.evaluate(
            claim_id="CLM-001",
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "fail"}},
        )
        fired = [t for t in result.triggers_fired if t.trigger_id == "RT-1"]
        assert len(fired) == 1
        assert fired[0].severity == RoutingTier.RED
        assert result.routing_tier == RoutingTier.RED

    def test_gate_pass_does_not_fire(self, router):
        result = router.evaluate(
            claim_id="CLM-002",
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "pass"}},
        )
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert not rt1.fired

    def test_gate_warn_does_not_fire(self, router):
        result = router.evaluate(
            claim_id="CLM-003",
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "warn"}},
        )
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert not rt1.fired

    def test_no_reconciliation_report(self, router):
        result = router.evaluate(
            claim_id="CLM-004",
            verdict="APPROVE",
            reconciliation_report=None,
        )
        rt1 = next(t for t in result.all_triggers if t.trigger_id == "RT-1")
        assert not rt1.fired


# ── RT-2: High-impact data gaps ─────────────────────────────────────


class TestRT2HighImpactDataGaps:
    """RT-2: HIGH-severity data gaps -> YELLOW (1) / RED (2+)."""

    def test_one_high_gap_fires_yellow(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={
                "data_gaps": [{"severity": "HIGH"}],
            },
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert rt2.fired
        assert rt2.severity == RoutingTier.YELLOW

    def test_two_high_gaps_fires_red(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={
                "data_gaps": [
                    {"severity": "HIGH"},
                    {"severity": "HIGH"},
                ],
            },
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert rt2.fired
        assert rt2.severity == RoutingTier.RED

    def test_medium_gaps_do_not_fire(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={
                "data_gaps": [
                    {"severity": "MEDIUM"},
                    {"severity": "LOW"},
                ],
            },
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert not rt2.fired

    def test_no_gaps(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            processing_result={"data_gaps": []},
        )
        rt2 = next(t for t in result.all_triggers if t.trigger_id == "RT-2")
        assert not rt2.fired


# ── RT-3: Coverage complexity extreme ───────────────────────────────


class TestRT3CoverageComplexity:
    """RT-3: Extreme line item count -> YELLOW / RED."""

    def test_25_items_green(self, router):
        items = [{"match_method": "keyword"} for _ in range(25)]
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": items},
        )
        rt3 = next(t for t in result.all_triggers if t.trigger_id == "RT-3")
        assert not rt3.fired

    def test_26_items_yellow(self, router):
        items = [{"match_method": "keyword"} for _ in range(26)]
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": items},
        )
        rt3 = next(t for t in result.all_triggers if t.trigger_id == "RT-3")
        assert rt3.fired
        assert rt3.severity == RoutingTier.YELLOW

    def test_35_items_yellow(self, router):
        items = [{"match_method": "keyword"} for _ in range(35)]
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": items},
        )
        rt3 = next(t for t in result.all_triggers if t.trigger_id == "RT-3")
        assert rt3.fired
        assert rt3.severity == RoutingTier.YELLOW

    def test_36_items_red(self, router):
        items = [{"match_method": "keyword"} for _ in range(36)]
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": items},
        )
        rt3 = next(t for t in result.all_triggers if t.trigger_id == "RT-3")
        assert rt3.fired
        assert rt3.severity == RoutingTier.RED


# ── RT-4: Coverage missing on APPROVE ───────────────────────────────


class TestRT4CoverageMissingOnApprove:
    """RT-4: No coverage AND verdict APPROVE -> RED."""

    def test_no_coverage_approve_fires(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis=None,
        )
        rt4 = next(t for t in result.all_triggers if t.trigger_id == "RT-4")
        assert rt4.fired
        assert rt4.severity == RoutingTier.RED

    def test_empty_line_items_approve_fires(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": []},
        )
        rt4 = next(t for t in result.all_triggers if t.trigger_id == "RT-4")
        assert rt4.fired

    def test_no_coverage_deny_does_not_fire(self, router):
        result = router.evaluate(
            verdict="DENY",
            coverage_analysis=None,
        )
        rt4 = next(t for t in result.all_triggers if t.trigger_id == "RT-4")
        assert not rt4.fired

    def test_with_coverage_approve_does_not_fire(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": [{"match_method": "keyword"}]},
        )
        rt4 = next(t for t in result.all_triggers if t.trigger_id == "RT-4")
        assert not rt4.fired


# ── RT-5: Low structural CCI on APPROVE ─────────────────────────────


class TestRT5LowStructuralCCI:
    """RT-5: Low CCI + APPROVE -> RED."""

    def test_low_cci_approve_fires(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.40},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert rt5.fired
        assert rt5.severity == RoutingTier.RED

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

    def test_no_cci_does_not_fire(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary=None,
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert not rt5.fired

    def test_boundary_cci_at_threshold(self, router):
        """CCI exactly at 0.55 should NOT fire (not strictly less than)."""
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.55},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert not rt5.fired

    def test_boundary_cci_just_below(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.549},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert rt5.fired


# ── Tier computation ────────────────────────────────────────────────


class TestTierComputation:
    """Tier = worst of all fired triggers. RED > YELLOW > GREEN."""

    def test_no_triggers_green(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "pass"}},
            coverage_analysis={"line_items": [{"match_method": "rule"}]},
            processing_result={"data_gaps": []},
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.GREEN
        assert len(result.triggers_fired) == 0
        assert result.tier_reason == "No triggers fired"

    def test_yellow_only(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "pass"}},
            coverage_analysis={"line_items": [{"match_method": "rule"}]},
            processing_result={
                "data_gaps": [{"severity": "HIGH"}],
            },
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.YELLOW

    def test_red_overrides_yellow(self, router):
        """If both RED and YELLOW triggers fire, tier is RED."""
        items = [{"match_method": "keyword"} for _ in range(30)]
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "fail"}},  # RED
            coverage_analysis={"line_items": items},  # YELLOW (30 items)
            processing_result={"data_gaps": [{"severity": "HIGH"}]},  # YELLOW
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.RED


# ── REFER verdict always RED ────────────────────────────────────────


class TestReferAlwaysRed:
    """REFER verdicts always route to RED regardless of triggers."""

    def test_refer_is_red_no_triggers(self, router):
        result = router.evaluate(
            verdict="REFER",
            reconciliation_report={"gate": {"status": "pass"}},
            coverage_analysis={"line_items": [{"match_method": "rule"}]},
            processing_result={"data_gaps": []},
            confidence_summary={"composite_score": 0.90},
        )
        assert result.routing_tier == RoutingTier.RED
        assert "REFER" in result.tier_reason

    def test_refer_original_verdict_preserved(self, router):
        result = router.evaluate(
            verdict="REFER",
        )
        assert result.original_verdict == "REFER"
        assert result.routed_verdict is None  # no override needed


# ── Verdict override ────────────────────────────────────────────────


class TestVerdictOverride:
    """RED + APPROVE -> routed_verdict = REFER."""

    def test_red_approve_overrides_to_refer(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "fail"}},
        )
        assert result.routing_tier == RoutingTier.RED
        assert result.routed_verdict == "REFER"
        assert result.original_verdict == "APPROVE"

    def test_red_deny_no_override(self, router):
        result = router.evaluate(
            verdict="DENY",
            reconciliation_report={"gate": {"status": "fail"}},
        )
        assert result.routing_tier == RoutingTier.RED
        assert result.routed_verdict is None

    def test_green_approve_no_override(self, router):
        result = router.evaluate(
            verdict="APPROVE",
            reconciliation_report={"gate": {"status": "pass"}},
            coverage_analysis={"line_items": [{"match_method": "rule"}]},
            processing_result={"data_gaps": []},
            confidence_summary={"composite_score": 0.85},
        )
        assert result.routing_tier == RoutingTier.GREEN
        assert result.routed_verdict is None


# ── Threshold override from config ──────────────────────────────────


class TestThresholdOverride:
    """Custom thresholds change trigger behavior."""

    def test_custom_complexity_threshold(self):
        custom = dict(DEFAULT_THRESHOLDS)
        custom["complexity_yellow"] = 10
        custom["complexity_red"] = 20
        router = ClaimRouter(thresholds=custom)

        items = [{"match_method": "rule"} for _ in range(12)]
        result = router.evaluate(
            verdict="APPROVE",
            coverage_analysis={"line_items": items},
            reconciliation_report={"gate": {"status": "pass"}},
            processing_result={"data_gaps": []},
            confidence_summary={"composite_score": 0.85},
        )
        rt3 = next(t for t in result.all_triggers if t.trigger_id == "RT-3")
        assert rt3.fired
        assert rt3.severity == RoutingTier.YELLOW

    def test_custom_cci_threshold(self):
        custom = dict(DEFAULT_THRESHOLDS)
        custom["low_cci_threshold"] = 0.70
        router = ClaimRouter(thresholds=custom)

        result = router.evaluate(
            verdict="APPROVE",
            confidence_summary={"composite_score": 0.60},
            reconciliation_report={"gate": {"status": "pass"}},
            coverage_analysis={"line_items": [{"match_method": "rule"}]},
        )
        rt5 = next(t for t in result.all_triggers if t.trigger_id == "RT-5")
        assert rt5.fired


# ── All triggers evaluated ──────────────────────────────────────────


class TestAllTriggersEvaluated:
    """All 5 triggers are always evaluated."""

    def test_all_triggers_count(self, router):
        result = router.evaluate(verdict="APPROVE")
        assert result.triggers_evaluated == 5
        assert len(result.all_triggers) == 5

    def test_trigger_ids_complete(self, router):
        result = router.evaluate(verdict="APPROVE")
        ids = {t.trigger_id for t in result.all_triggers}
        assert ids == {"RT-1", "RT-2", "RT-3", "RT-4", "RT-5"}


# ── Structural CCI passthrough ──────────────────────────────────────


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
