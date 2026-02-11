"""Unit tests for ConfidenceStage (src/context_builder/confidence/stage.py).

Tests cover:
1. run() with run_confidence=False -> skipped, timing=0
2. run() with no claim folder found -> no crash, stage completes
3. run() with screening_result + processing_result + decision_result -> signals collected, confidence_summary.json written
4. run() patches decision_dossier_v1.json with confidence_index
5. run() handles exception gracefully (non-fatal)
6. _load_extraction_results reads JSON from docs/*/extraction/*.json
7. _load_custom_weights from YAML
8. run() with no signals collected -> skipped
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from context_builder.confidence.stage import ConfidenceStage
from context_builder.pipeline.claim_stages.context import (
    ClaimContext,
    ClaimStageConfig,
    ClaimStageTimings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLAIM_ID = "CLM-001"
RUN_ID = "run-001"


def _make_context(tmp_path: Path, **overrides) -> ClaimContext:
    """Create a minimal ClaimContext rooted at tmp_path."""
    defaults = dict(
        claim_id=CLAIM_ID,
        workspace_path=tmp_path,
        run_id=RUN_ID,
    )
    defaults.update(overrides)
    return ClaimContext(**defaults)


def _setup_claim_folder(tmp_path: Path, claim_id: str = CLAIM_ID) -> Path:
    """Create the claims/{claim_id} directory tree and return claim_folder."""
    claim_folder = tmp_path / "claims" / claim_id
    claim_folder.mkdir(parents=True, exist_ok=True)
    return claim_folder


def _setup_run_dir(claim_folder: Path, run_id: str = RUN_ID) -> Path:
    """Create claim_runs/{run_id}/ under claim_folder and return run_dir."""
    run_dir = claim_folder / "claim_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, data: dict) -> None:
    """Write a dict as JSON to path (parent dirs created automatically)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# Realistic upstream results that produce at least one signal each.
SCREENING_RESULT = {
    "checks_passed": 5,
    "checks_failed": 1,
    "checks_inconclusive": 0,
    "checks": [
        {"name": "completeness", "verdict": "PASS", "is_hard_fail": False},
        {"name": "fraud_screen", "verdict": "FAIL", "is_hard_fail": False},
    ],
}

PROCESSING_RESULT = {
    "confidence_score": 0.85,
    "data_gaps": [{"severity": "LOW", "description": "Missing witness statement"}],
    "fraud_indicators": [],
}

DECISION_RESULT = {
    "clause_evaluations": [
        {"clause": "A", "evaluability_tier": 1, "verdict": "covered"},
        {"clause": "B", "evaluability_tier": 2, "verdict": "excluded"},
    ],
    "assumptions_used": [{"id": "A1", "text": "assumed standard policy"}],
    "unresolved_assumptions": [],
}

EXTRACTION_RESULT = {
    "doc_type_confidence": 0.92,
    "fields": [
        {
            "name": "loss_date",
            "confidence": 0.95,
            "has_verified_evidence": True,
            "provenance": {"match_quality": "exact"},
        },
        {
            "name": "amount",
            "confidence": 0.80,
            "has_verified_evidence": False,
            "provenance": {"match_quality": "normalized"},
        },
    ],
    "quality_gate": {"status": "pass"},
}


# ---------------------------------------------------------------------------
# 1. run() with run_confidence=False -> skipped, timing=0
# ---------------------------------------------------------------------------
class TestRunConfidenceDisabled:
    def test_skipped_when_disabled(self, tmp_path: Path) -> None:
        config = ClaimStageConfig(run_confidence=False)
        ctx = _make_context(tmp_path, stage_config=config)
        stage = ConfidenceStage()

        result = stage.run(ctx)

        assert result.timings.confidence_ms == 0
        assert result.current_stage == "confidence"

    def test_returns_same_context(self, tmp_path: Path) -> None:
        config = ClaimStageConfig(run_confidence=False)
        ctx = _make_context(tmp_path, stage_config=config)
        stage = ConfidenceStage()

        result = stage.run(ctx)

        assert result is ctx


# ---------------------------------------------------------------------------
# 2. run() with no claim folder found -> no crash, stage completes
# ---------------------------------------------------------------------------
class TestNoCLaimFolder:
    def test_no_crash_when_claims_dir_missing(self, tmp_path: Path) -> None:
        """No claims/ directory at all -- stage should still return context."""
        ctx = _make_context(tmp_path)
        stage = ConfidenceStage()

        result = stage.run(ctx)

        # Should complete without error; timing is set
        assert result is ctx
        assert result.timings.confidence_ms >= 0

    def test_no_crash_when_claim_id_not_found(self, tmp_path: Path) -> None:
        """claims/ exists but the specific claim_id folder does not."""
        (tmp_path / "claims").mkdir()
        ctx = _make_context(tmp_path)
        stage = ConfidenceStage()

        result = stage.run(ctx)

        assert result is ctx
        assert result.timings.confidence_ms >= 0


# ---------------------------------------------------------------------------
# 3. run() with upstream results on context -> signals collected,
#    confidence_summary.json written
# ---------------------------------------------------------------------------
class TestSignalsCollectedAndSummaryWritten:
    def test_confidence_summary_written(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        run_dir = _setup_run_dir(claim_folder)

        # Put an extraction result on disk
        ext_dir = claim_folder / "docs" / "doc1" / "extraction"
        ext_dir.mkdir(parents=True)
        _write_json(ext_dir / "result.json", EXTRACTION_RESULT)

        ctx = _make_context(
            tmp_path,
            screening_result=SCREENING_RESULT,
            processing_result=PROCESSING_RESULT,
            decision_result=DECISION_RESULT,
        )
        stage = ConfidenceStage()

        result = stage.run(ctx)

        # confidence_summary.json should exist
        summary_path = run_dir / "confidence_summary.json"
        assert summary_path.exists(), f"Expected {summary_path} to be written"

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert "composite_score" in summary
        assert "band" in summary
        assert summary["claim_id"] == CLAIM_ID
        assert summary["claim_run_id"] == RUN_ID

    def test_timing_recorded(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        _setup_run_dir(claim_folder)

        ctx = _make_context(
            tmp_path,
            screening_result=SCREENING_RESULT,
            processing_result=PROCESSING_RESULT,
            decision_result=DECISION_RESULT,
        )
        stage = ConfidenceStage()
        stage.run(ctx)

        assert ctx.timings.confidence_ms >= 0


# ---------------------------------------------------------------------------
# 4. run() patches decision_dossier_v1.json with confidence_index
# ---------------------------------------------------------------------------
class TestDossierPatching:
    def test_dossier_patched_with_confidence_index(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        run_dir = _setup_run_dir(claim_folder)

        # Create a decision dossier that the stage should patch
        dossier = {"verdict": "APPROVE", "reasons": ["all good"]}
        _write_json(run_dir / "decision_dossier_v1.json", dossier)

        # Need at least some signals so the stage reaches the patching code.
        ctx = _make_context(
            tmp_path,
            screening_result=SCREENING_RESULT,
            processing_result=PROCESSING_RESULT,
            decision_result=DECISION_RESULT,
        )
        stage = ConfidenceStage()
        stage.run(ctx)

        # Re-read the dossier and verify the patch
        patched = json.loads(
            (run_dir / "decision_dossier_v1.json").read_text(encoding="utf-8")
        )
        assert "confidence_index" in patched
        ci = patched["confidence_index"]
        assert "composite_score" in ci
        assert "band" in ci
        assert "components" in ci
        # Original fields should still be there
        assert patched["verdict"] == "APPROVE"

    def test_dossier_not_patched_when_absent(self, tmp_path: Path) -> None:
        """If there is no dossier file, patching is silently skipped."""
        claim_folder = _setup_claim_folder(tmp_path)
        _setup_run_dir(claim_folder)

        ctx = _make_context(
            tmp_path,
            screening_result=SCREENING_RESULT,
        )
        stage = ConfidenceStage()

        # Should not raise
        result = stage.run(ctx)
        assert result is ctx


# ---------------------------------------------------------------------------
# 5. run() handles exception gracefully (non-fatal)
# ---------------------------------------------------------------------------
class TestExceptionHandling:
    def test_exception_in_compute_is_non_fatal(self, tmp_path: Path) -> None:
        """If compute_confidence blows up, the stage catches and continues."""
        _setup_claim_folder(tmp_path)
        ctx = _make_context(
            tmp_path,
            screening_result=SCREENING_RESULT,
        )
        stage = ConfidenceStage()

        with patch(
            "context_builder.confidence.compute_confidence",
            side_effect=RuntimeError("boom"),
        ):
            result = stage.run(ctx)

        # Stage should return context without crashing
        assert result is ctx
        assert result.timings.confidence_ms >= 0


# ---------------------------------------------------------------------------
# 6. _load_extraction_results reads JSON from docs/*/extraction/*.json
# ---------------------------------------------------------------------------
class TestLoadExtractionResults:
    def test_loads_single_doc(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        ext_dir = claim_folder / "docs" / "doc1" / "extraction"
        ext_dir.mkdir(parents=True)
        _write_json(ext_dir / "result.json", EXTRACTION_RESULT)

        stage = ConfidenceStage()
        results = stage._load_extraction_results(claim_folder)

        assert len(results) == 1
        assert results[0]["doc_type_confidence"] == 0.92

    def test_loads_multiple_docs(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        for doc_name in ["doc1", "doc2", "doc3"]:
            ext_dir = claim_folder / "docs" / doc_name / "extraction"
            ext_dir.mkdir(parents=True)
            data = {"doc_type_confidence": 0.8, "fields": []}
            _write_json(ext_dir / "result.json", data)

        stage = ConfidenceStage()
        results = stage._load_extraction_results(claim_folder)

        assert len(results) == 3

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        ext_dir = claim_folder / "docs" / "doc1" / "extraction"
        ext_dir.mkdir(parents=True)

        # Write invalid JSON
        (ext_dir / "bad.json").write_text("NOT JSON", encoding="utf-8")
        # Also write valid JSON
        _write_json(ext_dir / "good.json", {"fields": []})

        stage = ConfidenceStage()
        results = stage._load_extraction_results(claim_folder)

        # Should load only the valid one
        assert len(results) == 1

    def test_returns_empty_when_no_docs_dir(self, tmp_path: Path) -> None:
        claim_folder = _setup_claim_folder(tmp_path)
        # No docs/ directory

        stage = ConfidenceStage()
        results = stage._load_extraction_results(claim_folder)

        assert results == []


# ---------------------------------------------------------------------------
# 7. _load_custom_weights from YAML
# ---------------------------------------------------------------------------
class TestLoadCustomWeights:
    def test_loads_yaml_weights(self, tmp_path: Path) -> None:
        weights_dir = tmp_path / "config" / "confidence"
        weights_dir.mkdir(parents=True)
        weights_yaml = weights_dir / "weights.yaml"
        weights_yaml.write_text(
            "weights:\n"
            "  document_quality: 0.30\n"
            "  data_completeness: 0.25\n"
            "  consistency: 0.15\n"
            "  coverage_reliability: 0.15\n"
            "  decision_clarity: 0.15\n",
            encoding="utf-8",
        )

        stage = ConfidenceStage()
        weights = stage._load_custom_weights(tmp_path)

        assert weights is not None
        assert weights["document_quality"] == 0.30
        assert weights["data_completeness"] == 0.25
        assert weights["consistency"] == 0.15

    def test_returns_none_when_no_file(self, tmp_path: Path) -> None:
        stage = ConfidenceStage()
        weights = stage._load_custom_weights(tmp_path)

        assert weights is None

    def test_returns_none_for_invalid_yaml(self, tmp_path: Path) -> None:
        weights_dir = tmp_path / "config" / "confidence"
        weights_dir.mkdir(parents=True)
        # YAML without a "weights" key
        (weights_dir / "weights.yaml").write_text(
            "something_else: true\n", encoding="utf-8"
        )

        stage = ConfidenceStage()
        weights = stage._load_custom_weights(tmp_path)

        assert weights is None


# ---------------------------------------------------------------------------
# 8. run() with no signals collected -> skipped
# ---------------------------------------------------------------------------
class TestNoSignalsCollected:
    def test_skipped_when_zero_signals(self, tmp_path: Path) -> None:
        """If the collector returns an empty list, stage logs skip and returns."""
        _setup_claim_folder(tmp_path)
        ctx = _make_context(tmp_path)
        # No upstream results and no extraction data on disk -> 0 signals
        stage = ConfidenceStage()

        result = stage.run(ctx)

        assert result is ctx
        assert result.timings.confidence_ms >= 0

    def test_no_confidence_summary_written_when_zero_signals(
        self, tmp_path: Path
    ) -> None:
        """Verify confidence_summary.json is NOT created when there are no signals."""
        claim_folder = _setup_claim_folder(tmp_path)
        run_dir = _setup_run_dir(claim_folder)
        ctx = _make_context(tmp_path)
        stage = ConfidenceStage()

        stage.run(ctx)

        summary_path = run_dir / "confidence_summary.json"
        assert not summary_path.exists(), (
            "confidence_summary.json should NOT be written when there are no signals"
        )
