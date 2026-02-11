"""Tests for ClaimAssessmentResult property fallback logic.

Verifies that the schema properties prefer authoritative sources
(dossier verdict, CCI score, screener payout) and fall back to
LLM assessment values when the authoritative source is unavailable.
"""

import pytest
from unittest.mock import MagicMock

from context_builder.schemas.claim_assessment import ClaimAssessmentResult


# ── Helpers ─────────────────────────────────────────────────────────


def _make_result(**overrides) -> ClaimAssessmentResult:
    """Create a ClaimAssessmentResult with sensible defaults."""
    defaults = dict(claim_id="CLM-001", success=True)
    defaults.update(overrides)
    return ClaimAssessmentResult(**defaults)


def _fake_assessment(decision="APPROVE", confidence_score=0.85, payout_final=3240.0):
    """Create a mock AssessmentResponse that passes Pydantic validation."""
    payout = MagicMock()
    payout.final_payout = payout_final
    mock = MagicMock()
    mock.decision = decision
    mock.confidence_score = confidence_score
    mock.payout = payout
    return mock


# ── decision property ───────────────────────────────────────────────


class TestDecisionProperty:
    def test_prefers_dossier_verdict(self):
        result = _make_result(
            decision_dossier={"claim_verdict": "DENY"},
        )
        # Pydantic won't accept a MagicMock for assessment, so set it manually
        object.__setattr__(result, "assessment", _fake_assessment(decision="APPROVE"))
        assert result.decision == "DENY"

    def test_falls_back_to_assessment(self):
        result = _make_result()
        object.__setattr__(result, "assessment", _fake_assessment(decision="APPROVE"))
        assert result.decision == "APPROVE"

    def test_none_when_both_missing(self):
        result = _make_result()
        assert result.decision is None

    def test_falls_back_when_dossier_verdict_missing(self):
        result = _make_result(
            decision_dossier={"some_other_field": True},
        )
        object.__setattr__(result, "assessment", _fake_assessment(decision="REFER_TO_HUMAN"))
        assert result.decision == "REFER_TO_HUMAN"


# ── confidence_score property ───────────────────────────────────────


class TestConfidenceScoreProperty:
    def test_prefers_cci_score(self):
        result = _make_result(
            confidence_summary={"composite_score": 0.79, "band": "moderate"},
        )
        object.__setattr__(result, "assessment", _fake_assessment(confidence_score=0.85))
        assert result.confidence_score == pytest.approx(0.79)

    def test_falls_back_to_assessment(self):
        result = _make_result()
        object.__setattr__(result, "assessment", _fake_assessment(confidence_score=0.85))
        assert result.confidence_score == pytest.approx(0.85)

    def test_none_when_both_missing(self):
        result = _make_result()
        assert result.confidence_score is None

    def test_falls_back_when_summary_has_no_score(self):
        result = _make_result(
            confidence_summary={"band": "moderate"},
        )
        object.__setattr__(result, "assessment", _fake_assessment(confidence_score=0.60))
        assert result.confidence_score == pytest.approx(0.60)


# ── confidence_band property ───────────────────────────────────────


class TestConfidenceBandProperty:
    def test_returns_band(self):
        result = _make_result(
            confidence_summary={"composite_score": 0.79, "band": "moderate"},
        )
        assert result.confidence_band == "moderate"

    def test_none_when_no_summary(self):
        result = _make_result()
        assert result.confidence_band is None


# ── final_payout property ──────────────────────────────────────────


class TestFinalPayoutProperty:
    def test_prefers_screening_payout(self):
        result = _make_result(screening_payout=4378.05)
        object.__setattr__(result, "assessment", _fake_assessment(payout_final=3240.0))
        assert result.final_payout == pytest.approx(4378.05)

    def test_falls_back_to_assessment_payout(self):
        result = _make_result()
        object.__setattr__(result, "assessment", _fake_assessment(payout_final=3240.0))
        assert result.final_payout == pytest.approx(3240.0)

    def test_none_when_both_missing(self):
        result = _make_result()
        assert result.final_payout is None

    def test_screening_payout_zero_is_used(self):
        """screening_payout=0 is a valid value (fully denied), not a fallback trigger."""
        result = _make_result(screening_payout=0.0)
        object.__setattr__(result, "assessment", _fake_assessment(payout_final=3240.0))
        assert result.final_payout == pytest.approx(0.0)


# ── gate_status property ──────────────────────────────────────────


class TestGateStatusProperty:
    def test_none_when_no_reconciliation(self):
        result = _make_result()
        assert result.gate_status is None


# ── _extract_screening_payout helper ──────────────────────────────


class TestExtractScreeningPayout:
    def test_extracts_from_payout_dict(self):
        from context_builder.api.services.claim_assessment import _extract_screening_payout

        assert _extract_screening_payout({"payout": {"final_payout": 1234.56}}) == pytest.approx(1234.56)

    def test_returns_none_for_missing_payout(self):
        from context_builder.api.services.claim_assessment import _extract_screening_payout

        assert _extract_screening_payout({"checks": []}) is None

    def test_returns_none_for_none_input(self):
        from context_builder.api.services.claim_assessment import _extract_screening_payout

        assert _extract_screening_payout(None) is None

    def test_returns_none_for_non_dict_payout(self):
        from context_builder.api.services.claim_assessment import _extract_screening_payout

        assert _extract_screening_payout({"payout": 1234.56}) is None
