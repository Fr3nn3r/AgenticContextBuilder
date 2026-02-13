"""Unit tests for ConfidenceScorer.

Uses importlib to load the scorer module directly from its file path,
bypassing the confidence package __init__.py which triggers a circular
import (confidence.stage -> pipeline.claim_stages -> confidence.stage).
"""

import importlib.util
import pathlib

import pytest

from context_builder.schemas.confidence import (
    ConfidenceBand,
    SignalSnapshot,
)

# ── Load scorer module directly (avoids circular import) ─────────────

_SCORER_FILE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "context_builder"
    / "confidence"
    / "scorer.py"
)
_spec = importlib.util.spec_from_file_location("confidence_scorer", _SCORER_FILE)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ConfidenceScorer = _mod.ConfidenceScorer
score_to_band = _mod.score_to_band
COMPONENT_SIGNALS = _mod.COMPONENT_SIGNALS
DEFAULT_WEIGHTS = _mod.DEFAULT_WEIGHTS
DENY_WEIGHTS = _mod.DENY_WEIGHTS
DENY_POLARITY_FLIPS = _mod.DENY_POLARITY_FLIPS


# ── Helpers ──────────────────────────────────────────────────────────


def _make_signal(name: str, value: float) -> SignalSnapshot:
    """Create a SignalSnapshot with the given name and normalised value."""
    stage = name.split(".")[0]
    return SignalSnapshot(
        signal_name=name,
        raw_value=value,
        normalized_value=value,
        source_stage=stage,
        description=f"test signal {name}",
    )


def _all_signal_names() -> list[str]:
    """Return a flat list of every signal name across all components."""
    names: list[str] = []
    for sigs in COMPONENT_SIGNALS.values():
        names.extend(sigs)
    return names


def _make_all_signals(value: float) -> list[SignalSnapshot]:
    """Create one SignalSnapshot per known signal, all set to *value*."""
    return [_make_signal(name, value) for name in _all_signal_names()]


# ── Tests ────────────────────────────────────────────────────────────


class TestAllSignalsActive:
    """Test 1: All 5 components active, all signals = 1.0."""

    def test_composite_near_one(self):
        scorer = ConfidenceScorer()
        summary = scorer.compute(_make_all_signals(1.0), claim_id="CLM-001")

        assert summary.composite_score == pytest.approx(1.0, abs=0.01)
        assert summary.band == ConfidenceBand.HIGH

    def test_all_component_scores_are_one(self):
        scorer = ConfidenceScorer()
        summary = scorer.compute(_make_all_signals(1.0))

        for cs in summary.component_scores:
            assert cs.score == pytest.approx(1.0, abs=0.001)


class TestAllSignalsZero:
    """Test 2: All signals = 0.0 -> composite = 0.0, band = LOW."""

    def test_composite_zero(self):
        scorer = ConfidenceScorer()
        summary = scorer.compute(_make_all_signals(0.0))

        assert summary.composite_score == pytest.approx(0.0, abs=0.001)
        assert summary.band == ConfidenceBand.LOW


class TestMixedSignals:
    """Test 3: Mixed signals produce a MODERATE band."""

    def test_mixed_gives_moderate_band(self):
        signals = []
        for name in COMPONENT_SIGNALS["document_quality"]:
            signals.append(_make_signal(name, 0.9))
        for name in COMPONENT_SIGNALS["data_completeness"]:
            signals.append(_make_signal(name, 0.8))
        for name in COMPONENT_SIGNALS["consistency"]:
            signals.append(_make_signal(name, 0.7))
        for name in COMPONENT_SIGNALS["coverage_reliability"]:
            signals.append(_make_signal(name, 0.6))
        for name in COMPONENT_SIGNALS["decision_clarity"]:
            signals.append(_make_signal(name, 0.5))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        # Weighted average should fall in the moderate range
        assert summary.band == ConfidenceBand.MODERATE
        assert 0.65 <= summary.composite_score < 0.80


class TestWeightRedistribution:
    """Test 4: If a component has 0 signals, its weight redistributes."""

    def test_document_quality_weight_redistributed(self):
        # Provide signals for everything EXCEPT document_quality
        signals = []
        for comp, sig_names in COMPONENT_SIGNALS.items():
            if comp == "document_quality":
                continue  # skip -> 0 signals for this component
            for name in sig_names:
                signals.append(_make_signal(name, 1.0))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        # document_quality should have effective weight 0
        assert summary.weights_used["document_quality"] == pytest.approx(0.0)

        # Remaining weights should sum to 1.0 (redistributed)
        remaining_weight = sum(
            w for comp, w in summary.weights_used.items()
            if comp != "document_quality"
        )
        assert remaining_weight == pytest.approx(1.0, abs=0.01)

        # Composite should still be high because all active components score 1.0
        assert summary.composite_score == pytest.approx(1.0, abs=0.01)


class TestCustomWeights:
    """Test 5: Custom weights override defaults."""

    def test_custom_weights_applied(self):
        custom = {
            "document_quality": 0.50,
            "data_completeness": 0.10,
            "consistency": 0.10,
            "coverage_reliability": 0.10,
            "decision_clarity": 0.20,
        }
        scorer = ConfidenceScorer(weights=custom)

        # Give document_quality signals 1.0, everything else 0.0
        signals = []
        for comp, sig_names in COMPONENT_SIGNALS.items():
            val = 1.0 if comp == "document_quality" else 0.0
            for name in sig_names:
                signals.append(_make_signal(name, val))

        summary = scorer.compute(signals)

        # document_quality has weight 0.50/1.0 = 0.50, score 1.0
        # All others score 0.0 -> composite = 0.50
        assert summary.composite_score == pytest.approx(0.50, abs=0.01)


class TestSingleComponentActive:
    """Test 6: Only extraction signals -> that component gets weight 1.0."""

    def test_single_component_gets_full_weight(self):
        # Only document_quality signals (source_stage = extraction)
        signals = [
            _make_signal(name, 0.9)
            for name in COMPONENT_SIGNALS["document_quality"]
        ]

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        # document_quality should have effective weight of 1.0
        assert summary.weights_used["document_quality"] == pytest.approx(1.0, abs=0.01)

        # Composite should equal the single component score
        assert summary.composite_score == pytest.approx(0.9, abs=0.01)


class TestScoreToBandBoundaries:
    """Test 7: score_to_band boundary values."""

    def test_080_is_high(self):
        assert score_to_band(0.80) == ConfidenceBand.HIGH

    def test_079_is_moderate(self):
        assert score_to_band(0.79) == ConfidenceBand.MODERATE

    def test_065_is_moderate(self):
        assert score_to_band(0.65) == ConfidenceBand.MODERATE

    def test_064_is_low(self):
        assert score_to_band(0.64) == ConfidenceBand.LOW

    def test_100_is_high(self):
        assert score_to_band(1.0) == ConfidenceBand.HIGH

    def test_000_is_low(self):
        assert score_to_band(0.0) == ConfidenceBand.LOW


class TestToConfidenceIndex:
    """Test 8: to_confidence_index produces correct compact model."""

    def test_compact_model_fields(self):
        scorer = ConfidenceScorer()
        signals = _make_all_signals(0.75)
        summary = scorer.compute(signals, claim_id="CLM-042", claim_run_id="RUN-7")

        index = scorer.to_confidence_index(summary)

        assert index.composite_score == summary.composite_score
        assert index.band == summary.band
        assert len(index.components) == len(COMPONENT_SIGNALS)

        for cs in summary.component_scores:
            assert index.components[cs.component] == pytest.approx(cs.score, abs=0.001)


class TestEmptySignals:
    """Test 9: Empty signals -> composite = 0.0, band = LOW, all missing."""

    def test_no_signals_gives_zero(self):
        scorer = ConfidenceScorer()
        summary = scorer.compute([], claim_id="CLM-EMPTY")

        assert summary.composite_score == pytest.approx(0.0, abs=0.001)
        assert summary.band == ConfidenceBand.LOW

    def test_no_signals_all_stages_missing(self):
        scorer = ConfidenceScorer()
        summary = scorer.compute([])

        # All unique stages from signal names should appear as missing
        expected_missing = set()
        for sig_names in COMPONENT_SIGNALS.values():
            for sn in sig_names:
                expected_missing.add(sn.split(".")[0])

        assert set(summary.stages_missing) == expected_missing
        assert summary.stages_available == []


class TestStagesTracking:
    """Test 10: stages_available and stages_missing tracked correctly."""

    def test_stages_tracked(self):
        # Provide only extraction and reconciliation signals
        signals = []
        for name in COMPONENT_SIGNALS["document_quality"]:
            signals.append(_make_signal(name, 0.8))
        for name in COMPONENT_SIGNALS["data_completeness"]:
            signals.append(_make_signal(name, 0.7))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        assert "extraction" in summary.stages_available
        assert "reconciliation" in summary.stages_available

        # Coverage and screening are missing (no signals provided)
        assert "coverage" in summary.stages_missing
        assert "screening" in summary.stages_missing

        # assessment contributes to data_completeness, so it should be available
        assert "assessment" in summary.stages_available


class TestComponentCountFlag:
    """Test 11: Flags include component count when < 5 active."""

    def test_partial_components_flagged(self):
        # Only provide signals for 2 components
        signals = []
        for name in COMPONENT_SIGNALS["document_quality"]:
            signals.append(_make_signal(name, 0.9))
        for name in COMPONENT_SIGNALS["consistency"]:
            signals.append(_make_signal(name, 0.9))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        component_flag = [f for f in summary.flags if "components active" in f]
        assert len(component_flag) == 1
        # 2 of 5 components have signals
        assert "2/5" in component_flag[0]


class TestSignalNames:
    """Verify signal names match the structural replacements."""

    def test_document_quality_has_4_signals(self):
        """document_quality has 4 signals (avg_doc_type_confidence removed)."""
        assert len(COMPONENT_SIGNALS["document_quality"]) == 4
        assert "extraction.avg_doc_type_confidence" not in COMPONENT_SIGNALS["document_quality"]

    def test_coverage_reliability_uses_structural_signals(self):
        """coverage_reliability uses structural_match_quality, primary_repair_method_reliability, parts_coverage_check."""
        cr_signals = COMPONENT_SIGNALS["coverage_reliability"]
        assert "coverage.structural_match_quality" in cr_signals
        assert "coverage.primary_repair_method_reliability" in cr_signals
        assert "coverage.policy_confirmation_rate" in cr_signals
        assert "coverage.parts_coverage_check" in cr_signals
        # Old signal names should NOT be present
        assert "coverage.avg_match_confidence" not in cr_signals
        assert "coverage.primary_repair_confidence" not in cr_signals

    def test_decision_clarity_has_assumption_density(self):
        """decision_clarity includes assumption_density signal."""
        dc_signals = COMPONENT_SIGNALS["decision_clarity"]
        assert "decision.assumption_density" in dc_signals


class TestSignalsUsedPerComponent:
    """Test 12: signals_used in each ComponentScore match expected signals."""

    def test_signals_used_match(self):
        signals = _make_all_signals(0.6)
        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        for cs in summary.component_scores:
            expected_names = set(COMPONENT_SIGNALS[cs.component])
            actual_names = {s.signal_name for s in cs.signals_used}
            assert actual_names == expected_names, (
                f"Component {cs.component}: expected {expected_names}, "
                f"got {actual_names}"
            )


# ── Verdict-aware scoring tests ─────────────────────────────────────


class TestDenyPolarityFlip:
    """Test 13: DENY verdict inverts polarity of specific signals."""

    def test_pass_rate_flipped_for_deny(self):
        """screening.pass_rate is flipped (1 - value) for DENY."""
        signals = _make_all_signals(0.8)
        # Set pass_rate to 0.3 (low = many fails)
        for s in signals:
            if s.signal_name == "screening.pass_rate":
                s.normalized_value = 0.3

        scorer = ConfidenceScorer()

        # APPROVE: pass_rate = 0.3 (as-is)
        approve_summary = scorer.compute(signals, verdict="APPROVE")
        approve_dc = next(
            c for c in approve_summary.component_scores
            if c.component == "decision_clarity"
        )
        approve_pass_rate = next(
            s for s in approve_dc.signals_used
            if s.signal_name == "screening.pass_rate"
        )
        assert approve_pass_rate.normalized_value == pytest.approx(0.3)

        # DENY: pass_rate flipped to 0.7
        deny_summary = scorer.compute(signals, verdict="DENY")
        deny_dc = next(
            c for c in deny_summary.component_scores
            if c.component == "decision_clarity"
        )
        deny_pass_rate = next(
            s for s in deny_dc.signals_used
            if s.signal_name == "screening.pass_rate"
        )
        assert deny_pass_rate.normalized_value == pytest.approx(0.7, abs=0.001)

    def test_hard_fail_clarity_flipped_for_deny(self):
        """screening.hard_fail_clarity is flipped for DENY."""
        signals = _make_all_signals(0.8)
        for s in signals:
            if s.signal_name == "screening.hard_fail_clarity":
                s.normalized_value = 0.0  # hard fail present

        scorer = ConfidenceScorer()

        # DENY: flipped to 1.0 (hard fail supports denial)
        deny_summary = scorer.compute(signals, verdict="DENY")
        deny_dc = next(
            c for c in deny_summary.component_scores
            if c.component == "decision_clarity"
        )
        deny_hf = next(
            s for s in deny_dc.signals_used
            if s.signal_name == "screening.hard_fail_clarity"
        )
        assert deny_hf.normalized_value == pytest.approx(1.0)

    def test_approve_no_polarity_flip(self):
        """APPROVE verdict does not flip any signals."""
        signals = _make_all_signals(0.5)
        scorer = ConfidenceScorer()

        approve = scorer.compute(signals, verdict="APPROVE")
        no_verdict = scorer.compute(signals, verdict="")

        # Should produce identical scores
        assert approve.composite_score == pytest.approx(
            no_verdict.composite_score, abs=0.001
        )


class TestDenyWeightSelection:
    """Test 14: DENY verdict selects DENY_WEIGHTS."""

    def test_deny_uses_deny_weights(self):
        """DENY verdict gives decision_clarity higher weight (0.30 vs 0.20)."""
        signals = _make_all_signals(0.8)
        scorer = ConfidenceScorer()

        summary = scorer.compute(signals, verdict="DENY")

        # decision_clarity should have weight 0.30 in DENY_WEIGHTS
        dc = next(
            c for c in summary.component_scores
            if c.component == "decision_clarity"
        )
        assert dc.weight == pytest.approx(DENY_WEIGHTS["decision_clarity"])

        # coverage_reliability should have weight 0.25 in DENY_WEIGHTS
        cr = next(
            c for c in summary.component_scores
            if c.component == "coverage_reliability"
        )
        assert cr.weight == pytest.approx(DENY_WEIGHTS["coverage_reliability"])

    def test_approve_uses_default_weights(self):
        """APPROVE verdict uses DEFAULT_WEIGHTS."""
        signals = _make_all_signals(0.8)
        scorer = ConfidenceScorer()

        summary = scorer.compute(signals, verdict="APPROVE")

        dc = next(
            c for c in summary.component_scores
            if c.component == "decision_clarity"
        )
        assert dc.weight == pytest.approx(DEFAULT_WEIGHTS["decision_clarity"])

    def test_custom_weights_override_deny_weights(self):
        """Custom weights take priority over DENY_WEIGHTS."""
        custom = {
            "document_quality": 0.10,
            "data_completeness": 0.10,
            "consistency": 0.10,
            "coverage_reliability": 0.30,
            "decision_clarity": 0.40,
        }
        scorer = ConfidenceScorer(weights=custom)

        signals = _make_all_signals(0.8)
        summary = scorer.compute(signals, verdict="DENY")

        dc = next(
            c for c in summary.component_scores
            if c.component == "decision_clarity"
        )
        # Custom weight should be used, not DENY_WEIGHTS
        assert dc.weight == pytest.approx(0.40)


class TestDenyVsApproveComposite:
    """Test 15: Deny-style signals produce higher CCI under DENY verdict."""

    def test_deny_higher_than_approve_for_denial_evidence(self):
        """A claim with hard fails + low pass rate should score
        higher when verdict=DENY than verdict=APPROVE."""
        signals = []
        # Good data quality
        for name in COMPONENT_SIGNALS["document_quality"]:
            signals.append(_make_signal(name, 0.85))
        for name in COMPONENT_SIGNALS["data_completeness"]:
            signals.append(_make_signal(name, 0.80))
        for name in COMPONENT_SIGNALS["consistency"]:
            signals.append(_make_signal(name, 0.75))
        for name in COMPONENT_SIGNALS["coverage_reliability"]:
            signals.append(_make_signal(name, 0.70))
        # Decision clarity with denial-supporting signals
        signals.append(_make_signal("screening.pass_rate", 0.25))
        signals.append(_make_signal("screening.inconclusive_rate", 0.10))
        signals.append(_make_signal("screening.hard_fail_clarity", 0.0))
        signals.append(_make_signal("assessment.fraud_indicator_penalty", 0.15))

        scorer = ConfidenceScorer()

        approve = scorer.compute(signals, verdict="APPROVE")
        deny = scorer.compute(signals, verdict="DENY")

        # DENY should score higher because polarity flips + weight shift
        assert deny.composite_score > approve.composite_score


class TestMultiplierChain:
    """Test 16: Multiplier signals scale coverage_reliability down."""

    def test_zero_coverage_penalty_zeros_component(self):
        """zero_coverage_penalty = 0.0 zeros out coverage_reliability."""
        signals = _make_all_signals(0.8)
        # Add the multiplier signal with value 0.0
        signals.append(_make_signal("coverage.zero_coverage_penalty", 0.0))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        cr = next(
            c for c in summary.component_scores
            if c.component == "coverage_reliability"
        )
        # Component score should be 0.0 (multiplied by 0.0)
        assert cr.score == pytest.approx(0.0, abs=0.001)

        # Composite should be significantly lower than 0.8
        # (coverage_reliability weight 0.30 contribution gone)
        assert summary.composite_score < 0.65

    def test_payout_materiality_scales_component(self):
        """payout_materiality = 0.13 drastically reduces coverage_reliability."""
        signals = _make_all_signals(0.8)
        signals.append(_make_signal("coverage.payout_materiality", 0.13))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        cr = next(
            c for c in summary.component_scores
            if c.component == "coverage_reliability"
        )
        # 0.8 * 0.13 = 0.104
        assert cr.score < 0.15

    def test_multipliers_chain_together(self):
        """Multiple multipliers compound: 0.8 * 0.5 * 0.5 = 0.2."""
        signals = _make_all_signals(0.8)
        signals.append(_make_signal("coverage.line_item_complexity", 0.5))
        signals.append(_make_signal("coverage.zero_coverage_penalty", 0.5))
        # No payout_materiality signal (not emitted)

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        cr = next(
            c for c in summary.component_scores
            if c.component == "coverage_reliability"
        )
        # 0.8 * 0.5 * 0.5 = 0.2
        assert cr.score == pytest.approx(0.2, abs=0.01)

    def test_all_multipliers_one_no_effect(self):
        """Multipliers at 1.0 don't change the score."""
        signals = _make_all_signals(0.8)
        signals.append(_make_signal("coverage.line_item_complexity", 1.0))
        signals.append(_make_signal("coverage.zero_coverage_penalty", 1.0))
        signals.append(_make_signal("coverage.payout_materiality", 1.0))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        cr = next(
            c for c in summary.component_scores
            if c.component == "coverage_reliability"
        )
        assert cr.score == pytest.approx(0.8, abs=0.01)
