"""Unit tests for the core screening stage.

Tests the ScreeningStage, DefaultScreener, utility functions,
and screener loading — all using mock screeners (no workspace dependency).
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from context_builder.coverage.schemas import CoverageAnalysisResult
from context_builder.pipeline.claim_stages.context import (
    ClaimContext,
    ClaimStageConfig,
    ClaimStageTimings,
)
from context_builder.pipeline.claim_stages.screening import (
    DefaultScreener,
    ScreeningStage,
    get_fact,
    get_structured_fact,
    load_screener_from_workspace,
    parse_date,
    parse_float,
    parse_int,
)
from context_builder.schemas.screening import (
    CheckVerdict,
    ScreeningCheck,
    ScreeningResult,
)


# ── Utility function tests ───────────────────────────────────────────


class TestGetFact:
    """Tests for the get_fact utility function."""

    def test_exact_match(self):
        facts = [{"name": "start_date", "value": "2025-01-01"}]
        assert get_fact(facts, "start_date") == "2025-01-01"

    def test_suffix_match(self):
        facts = [{"name": "cost_estimate.document_date", "value": "2026-01-16"}]
        assert get_fact(facts, "document_date") == "2026-01-16"

    def test_exact_takes_precedence(self):
        facts = [
            {"name": "document_date", "value": "exact"},
            {"name": "cost_estimate.document_date", "value": "prefixed"},
        ]
        assert get_fact(facts, "document_date") == "exact"

    def test_not_found_returns_none(self):
        facts = [{"name": "start_date", "value": "2025-01-01"}]
        assert get_fact(facts, "nonexistent") is None

    def test_suffix_requires_dot(self):
        facts = [{"name": "my_document_date", "value": "wrong"}]
        assert get_fact(facts, "document_date") is None

    def test_empty_facts(self):
        assert get_fact([], "anything") is None


class TestGetStructuredFact:
    """Tests for the get_structured_fact utility function."""

    def test_exact_match(self):
        facts = [{"name": "covered_components", "structured_value": {"engine": ["block"]}}]
        result = get_structured_fact(facts, "covered_components")
        assert result == {"engine": ["block"]}

    def test_suffix_match(self):
        facts = [{"name": "policy.covered_components", "structured_value": [1, 2, 3]}]
        result = get_structured_fact(facts, "covered_components")
        assert result == [1, 2, 3]

    def test_not_found_returns_none(self):
        facts = [{"name": "other", "structured_value": "x"}]
        assert get_structured_fact(facts, "missing") is None

    def test_returns_none_when_no_structured_value(self):
        facts = [{"name": "start_date", "value": "2025-01-01"}]
        assert get_structured_fact(facts, "start_date") is None


class TestParseDate:
    """Tests for the parse_date utility function."""

    def test_iso_format(self):
        assert parse_date("2025-12-01") == date(2025, 12, 1)

    def test_european_format(self):
        assert parse_date("01.12.2025") == date(2025, 12, 1)

    def test_iso_with_trailing(self):
        assert parse_date("2025-12-01T10:30:00Z") == date(2025, 12, 1)

    def test_european_with_trailing(self):
        assert parse_date("01.12.2025 14:00") == date(2025, 12, 1)

    def test_none_returns_none(self):
        assert parse_date(None) is None

    def test_empty_returns_none(self):
        assert parse_date("") is None

    def test_invalid_returns_none(self):
        assert parse_date("not-a-date") is None

    def test_non_string_returns_none(self):
        assert parse_date(12345) is None


class TestParseInt:
    """Tests for the parse_int utility function."""

    def test_simple_number(self):
        assert parse_int("100000") == 100000

    def test_swiss_format(self):
        assert parse_int("74'359") == 74359

    def test_comma_format(self):
        assert parse_int("74,359") == 74359

    def test_with_suffix(self):
        assert parse_int("74359 km") == 74359

    def test_int_passthrough(self):
        assert parse_int(100000) == 100000

    def test_float_passthrough(self):
        assert parse_int(100000.5) == 100000

    def test_none_returns_none(self):
        assert parse_int(None) is None

    def test_empty_returns_none(self):
        assert parse_int("") is None

    def test_non_numeric_returns_none(self):
        assert parse_int("abc") is None


class TestParseFloat:
    """Tests for the parse_float utility function."""

    def test_simple_number(self):
        assert parse_float("200.00") == 200.0

    def test_percent_format(self):
        assert parse_float("10 %") == 10.0

    def test_currency_format(self):
        assert parse_float("200.00 CHF") == 200.0

    def test_swiss_format(self):
        assert parse_float("74'359.50") == 74359.50

    def test_int_passthrough(self):
        assert parse_float(10) == 10.0

    def test_float_passthrough(self):
        assert parse_float(10.5) == 10.5

    def test_none_returns_none(self):
        assert parse_float(None) is None

    def test_empty_returns_none(self):
        assert parse_float("") is None


# ── DefaultScreener tests ────────────────────────────────────────────


class TestDefaultScreener:
    """Tests for the DefaultScreener class."""

    def test_returns_empty_result(self, tmp_path):
        screener = DefaultScreener(tmp_path)
        result, coverage = screener.screen("CLM-001", {"facts": []})
        assert isinstance(result, ScreeningResult)
        assert result.claim_id == "CLM-001"
        assert result.checks == []
        assert coverage is None

    def test_has_timestamp(self, tmp_path):
        screener = DefaultScreener(tmp_path)
        result, _ = screener.screen("CLM-001", {"facts": []})
        assert result.screening_timestamp is not None
        assert len(result.screening_timestamp) > 0

    def test_no_auto_reject(self, tmp_path):
        screener = DefaultScreener(tmp_path)
        result, _ = screener.screen("CLM-001", {"facts": []})
        assert result.auto_reject is False


# ── load_screener_from_workspace tests ────────────────────────────────


class TestLoadScreener:
    """Tests for the load_screener_from_workspace function."""

    def test_returns_none_when_no_file(self, tmp_path):
        result = load_screener_from_workspace(tmp_path)
        assert result is None

    def test_loads_valid_screener(self, tmp_path):
        screener_dir = tmp_path / "config" / "screening"
        screener_dir.mkdir(parents=True)
        screener_file = screener_dir / "screener.py"
        screener_file.write_text(
            """
from datetime import datetime
from context_builder.schemas.screening import ScreeningResult

class TestScreener:
    def __init__(self, workspace_path):
        self.workspace_path = workspace_path

    def screen(self, claim_id, aggregated_facts, reconciliation_report=None, claim_run_id=None):
        result = ScreeningResult(
            claim_id=claim_id,
            screening_timestamp=datetime.utcnow().isoformat(),
        )
        return result, None
""",
            encoding="utf-8",
        )
        screener = load_screener_from_workspace(tmp_path)
        assert screener is not None
        assert hasattr(screener, "screen")

    def test_returns_none_on_invalid_file(self, tmp_path):
        screener_dir = tmp_path / "config" / "screening"
        screener_dir.mkdir(parents=True)
        screener_file = screener_dir / "screener.py"
        screener_file.write_text("raise RuntimeError('broken')", encoding="utf-8")
        result = load_screener_from_workspace(tmp_path)
        assert result is None


# ── ScreeningStage tests ─────────────────────────────────────────────


def _make_context(
    tmp_path: Path,
    claim_id: str = "CLM-001",
    run_id: str = "clm_20260128_100000_abc123",
    facts: Optional[Dict[str, Any]] = None,
    run_screening: bool = True,
) -> ClaimContext:
    """Create a ClaimContext for testing."""
    # Set up claim folder structure
    claim_folder = tmp_path / "claims" / claim_id
    claim_folder.mkdir(parents=True, exist_ok=True)

    # Create claim run directory
    run_dir = claim_folder / "claim_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    config = ClaimStageConfig(run_screening=run_screening)

    return ClaimContext(
        claim_id=claim_id,
        workspace_path=tmp_path,
        run_id=run_id,
        stage_config=config,
        aggregated_facts=facts,
    )


class _MockScreener:
    """Mock screener for testing the stage."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.screen_called = False

    def screen(
        self,
        claim_id: str,
        aggregated_facts: Dict[str, Any],
        reconciliation_report=None,
        claim_run_id=None,
    ) -> Tuple[ScreeningResult, Optional[CoverageAnalysisResult]]:
        self.screen_called = True
        result = ScreeningResult(
            claim_id=claim_id,
            screening_timestamp=datetime.utcnow().isoformat(),
            checks=[
                ScreeningCheck(
                    check_id="1",
                    check_name="policy_validity",
                    verdict=CheckVerdict.PASS,
                    reason="OK",
                    is_hard_fail=True,
                ),
                ScreeningCheck(
                    check_id="3",
                    check_name="mileage",
                    verdict=CheckVerdict.FAIL,
                    reason="Over limit",
                    is_hard_fail=True,
                ),
            ],
        )
        result.recompute_counts()
        return result, None


class TestScreeningStageRun:
    """Tests for the ScreeningStage.run() method."""

    def test_skips_when_screening_disabled(self, tmp_path):
        context = _make_context(tmp_path, facts={"facts": []}, run_screening=False)
        stage = ScreeningStage()
        result = stage.run(context)
        assert result.screening_result is None
        assert result.timings.screening_ms == 0

    def test_skips_when_no_facts(self, tmp_path):
        context = _make_context(tmp_path, facts=None)
        stage = ScreeningStage()
        result = stage.run(context)
        assert result.screening_result is None
        assert result.timings.screening_ms == 0

    def test_runs_mock_screener(self, tmp_path):
        context = _make_context(tmp_path, facts={"facts": []})
        stage = ScreeningStage()
        mock_screener = _MockScreener(tmp_path)
        stage._screener = mock_screener
        stage._workspace_path = tmp_path

        result = stage.run(context)

        assert mock_screener.screen_called
        assert result.screening_result is not None
        assert result.screening_result["checks_passed"] == 1
        assert result.screening_result["checks_failed"] == 1
        assert result.screening_result["auto_reject"] is True

    def test_writes_screening_json(self, tmp_path):
        context = _make_context(tmp_path, facts={"facts": []})
        stage = ScreeningStage()
        mock_screener = _MockScreener(tmp_path)
        stage._screener = mock_screener
        stage._workspace_path = tmp_path

        stage.run(context)

        screening_path = (
            tmp_path
            / "claims"
            / "CLM-001"
            / "claim_runs"
            / "clm_20260128_100000_abc123"
            / "screening.json"
        )
        assert screening_path.exists()
        data = json.loads(screening_path.read_text(encoding="utf-8"))
        assert data["claim_id"] == "CLM-001"

    def test_records_timing(self, tmp_path):
        context = _make_context(tmp_path, facts={"facts": []})
        stage = ScreeningStage()
        mock_screener = _MockScreener(tmp_path)
        stage._screener = mock_screener
        stage._workspace_path = tmp_path

        result = stage.run(context)
        assert result.timings.screening_ms >= 0

    def test_non_fatal_on_exception(self, tmp_path):
        """Screening failures should not break the pipeline."""
        context = _make_context(tmp_path, facts={"facts": []})
        stage = ScreeningStage()

        # Create a screener that raises
        class _FailingScreener:
            def __init__(self, wp):
                pass

            def screen(self, *args, **kwargs):
                raise RuntimeError("Boom!")

        stage._screener = _FailingScreener(tmp_path)
        stage._workspace_path = tmp_path

        result = stage.run(context)
        # Should not have errored the context
        assert result.status != "error"
        assert result.screening_result is None

    def test_context_screening_result_stored(self, tmp_path):
        context = _make_context(tmp_path, facts={"facts": []})
        stage = ScreeningStage()
        mock_screener = _MockScreener(tmp_path)
        stage._screener = mock_screener
        stage._workspace_path = tmp_path

        result = stage.run(context)

        assert result.screening_result is not None
        assert isinstance(result.screening_result, dict)
        assert result.screening_result["claim_id"] == "CLM-001"

    def test_stage_caches_screener(self, tmp_path):
        stage = ScreeningStage()
        mock_screener = _MockScreener(tmp_path)
        stage._screener = mock_screener
        stage._workspace_path = tmp_path

        # Same workspace → reuses cached screener
        result = stage._get_screener(tmp_path)
        assert result is mock_screener

    def test_stage_name(self):
        stage = ScreeningStage()
        assert stage.name == "screening"


# ── Import tests ─────────────────────────────────────────────────────


class TestImports:
    """Test that screening stage is properly importable from the package."""

    def test_import_from_screening_module(self):
        from context_builder.pipeline.claim_stages.screening import (
            DefaultScreener,
            Screener,
            ScreeningStage,
            load_screener_from_workspace,
        )

        assert ScreeningStage is not None
        assert Screener is not None
        assert DefaultScreener is not None
        assert load_screener_from_workspace is not None

    def test_import_from_package(self):
        from context_builder.pipeline.claim_stages import (
            DefaultScreener,
            Screener,
            ScreeningStage,
            load_screener_from_workspace,
        )

        assert ScreeningStage is not None
        assert Screener is not None
        assert DefaultScreener is not None
        assert load_screener_from_workspace is not None
