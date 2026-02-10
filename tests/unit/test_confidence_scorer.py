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
            signals.append(_make_signal(name, 0.5))
        for name in COMPONENT_SIGNALS["coverage_reliability"]:
            signals.append(_make_signal(name, 0.4))
        for name in COMPONENT_SIGNALS["decision_clarity"]:
            signals.append(_make_signal(name, 0.3))

        scorer = ConfidenceScorer()
        summary = scorer.compute(signals)

        # Weighted average should fall in the moderate range
        assert summary.band == ConfidenceBand.MODERATE
        assert 0.55 <= summary.composite_score < 0.80


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

    def test_055_is_moderate(self):
        assert score_to_band(0.55) == ConfidenceBand.MODERATE

    def test_054_is_low(self):
        assert score_to_band(0.54) == ConfidenceBand.LOW

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

        # Coverage and screening/decision are missing (no signals provided)
        assert "coverage" in summary.stages_missing
        assert "screening" in summary.stages_missing
        assert "decision" in summary.stages_missing

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
        assert "2/5" in component_flag[0]


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
