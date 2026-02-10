"""Tests for parallel document processing in process_claim (Phase 2)."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from context_builder.pipeline.events import EventType, PipelineEvent
from context_builder.pipeline.event_collector import EventCollector
from context_builder.pipeline.stages.context import (
    ClaimResult,
    DocResult,
    PhaseTimings,
    StageConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_discovered_doc(doc_id: str, filename: str):
    """Create a minimal DiscoveredDocument-like mock."""
    doc = MagicMock()
    doc.doc_id = doc_id
    doc.original_filename = filename
    doc.source_type = "pdf"
    doc.source_path = Path(f"/tmp/{filename}")
    return doc


def _make_discovered_claim(claim_id: str, doc_count: int):
    """Create a minimal DiscoveredClaim-like mock."""
    claim = MagicMock()
    claim.claim_id = claim_id
    claim.documents = [
        _make_discovered_doc(f"doc_{i}", f"file_{i}.pdf")
        for i in range(doc_count)
    ]
    return claim


def _fake_process_document(**kwargs):
    """Simulate a successful process_document call."""
    doc = kwargs.get("doc")
    return DocResult(
        doc_id=doc.doc_id,
        original_filename=doc.original_filename,
        status="success",
        source_type="pdf",
        doc_type="invoice",
        time_ms=100,
        timings=PhaseTimings(ingestion_ms=30, classification_ms=30, extraction_ms=40, total_ms=100),
    )


def _slow_process_document(**kwargs):
    """Simulate a process_document call with a small delay."""
    time.sleep(0.05)  # 50ms per doc
    return _fake_process_document(**kwargs)


def _failing_process_document(**kwargs):
    """Simulate a process_document that raises."""
    doc = kwargs.get("doc")
    if doc.doc_id == "doc_1":
        raise RuntimeError("extraction failed for doc_1")
    return _fake_process_document(**kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParallelDocProcessing:
    """Tests for max_workers > 1 parallel execution."""

    @patch("context_builder.pipeline.run.process_document")
    @patch("context_builder.pipeline.run.create_doc_structure")
    @patch("context_builder.pipeline.run.get_workspace_logs_dir")
    @patch("context_builder.pipeline.run.get_version_bundle_store")
    @patch("context_builder.pipeline.run.write_manifest")
    @patch("context_builder.pipeline.run.write_json_atomic")
    @patch("context_builder.pipeline.run.mark_run_complete")
    @patch("context_builder.pipeline.run.is_claim_processed", return_value=False)
    def test_parallel_all_succeed(
        self, mock_processed, mock_complete, mock_write, mock_manifest,
        mock_vbs, mock_logs_dir, mock_create_doc, mock_proc_doc, tmp_path,
    ):
        """4 docs with max_workers=3 -- all succeed, all events emitted."""
        from context_builder.pipeline.run import process_claim

        claim = _make_discovered_claim("CLM-001", 4)
        collector = EventCollector(fail_on_error=True)

        # Mock setup
        mock_create_doc.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_logs_dir.return_value = tmp_path / "logs"
        mock_manifest.return_value = {}
        mock_vbs.return_value.create_version_bundle.return_value = MagicMock(bundle_id="VB-001")
        mock_proc_doc.side_effect = _fake_process_document

        # Create necessary directories
        run_dir = tmp_path / "claims" / "CLM-001" / "runs" / "RUN-001" / "logs"
        run_dir.mkdir(parents=True)

        # Create a mock classifier factory so parallel path uses it
        mock_clf_factory = MagicMock()
        mock_clf_factory.create.return_value = MagicMock()

        from context_builder.pipeline.stages.context import PipelineProviders
        providers = PipelineProviders(classifier_factory=mock_clf_factory)

        result = process_claim(
            claim=claim,
            output_base=tmp_path / "claims",
            run_id="RUN-001",
            force=True,
            event_collector=collector,
            max_workers=3,
            providers=providers,
        )

        assert result.status in ("success", "partial")
        assert len(result.documents) == 4
        assert all(d.status == "success" for d in result.documents)

        # Drain remaining events
        collector.close()
        collector.drain()

        # process_document is fully mocked, so DOC_* events don't fire.
        # Only CLAIM_COMPLETE (emitted by process_claim itself) is expected.
        all_events = collector.all_events
        claim_events = [e for e in all_events if e.event_type == EventType.CLAIM_COMPLETE]
        assert len(claim_events) == 1
        assert claim_events[0].claim_id == "CLM-001"

    @patch("context_builder.pipeline.run.process_document")
    @patch("context_builder.pipeline.run.create_doc_structure")
    @patch("context_builder.pipeline.run.get_workspace_logs_dir")
    @patch("context_builder.pipeline.run.get_version_bundle_store")
    @patch("context_builder.pipeline.run.write_manifest")
    @patch("context_builder.pipeline.run.write_json_atomic")
    @patch("context_builder.pipeline.run.mark_run_complete")
    @patch("context_builder.pipeline.run.is_claim_processed", return_value=False)
    def test_error_in_one_doc_doesnt_kill_others(
        self, mock_processed, mock_complete, mock_write, mock_manifest,
        mock_vbs, mock_logs_dir, mock_create_doc, mock_proc_doc, tmp_path,
    ):
        """One doc failing doesn't prevent others from completing."""
        from context_builder.pipeline.run import process_claim

        claim = _make_discovered_claim("CLM-001", 3)
        collector = EventCollector(fail_on_error=False)

        mock_create_doc.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_logs_dir.return_value = tmp_path / "logs"
        mock_manifest.return_value = {}
        mock_vbs.return_value.create_version_bundle.return_value = MagicMock(bundle_id="VB-001")
        mock_proc_doc.side_effect = _failing_process_document

        run_dir = tmp_path / "claims" / "CLM-001" / "runs" / "RUN-001" / "logs"
        run_dir.mkdir(parents=True)

        mock_clf_factory = MagicMock()
        mock_clf_factory.create.return_value = MagicMock()

        from context_builder.pipeline.stages.context import PipelineProviders
        providers = PipelineProviders(classifier_factory=mock_clf_factory)

        result = process_claim(
            claim=claim,
            output_base=tmp_path / "claims",
            run_id="RUN-001",
            force=True,
            event_collector=collector,
            max_workers=3,
            providers=providers,
        )

        # 2 success + 1 error
        success = [d for d in result.documents if d.status == "success"]
        errors = [d for d in result.documents if d.status == "error"]
        assert len(success) == 2
        assert len(errors) == 1
        assert result.status == "partial"

    @patch("context_builder.pipeline.run.process_document")
    @patch("context_builder.pipeline.run.create_doc_structure")
    @patch("context_builder.pipeline.run.get_workspace_logs_dir")
    @patch("context_builder.pipeline.run.get_version_bundle_store")
    @patch("context_builder.pipeline.run.write_manifest")
    @patch("context_builder.pipeline.run.write_json_atomic")
    @patch("context_builder.pipeline.run.mark_run_complete")
    @patch("context_builder.pipeline.run.is_claim_processed", return_value=False)
    def test_cancellation_propagates(
        self, mock_processed, mock_complete, mock_write, mock_manifest,
        mock_vbs, mock_logs_dir, mock_create_doc, mock_proc_doc, tmp_path,
    ):
        """cancel_event stops processing of pending documents."""
        from context_builder.pipeline.run import process_claim

        claim = _make_discovered_claim("CLM-001", 4)
        cancel = threading.Event()

        mock_create_doc.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_logs_dir.return_value = tmp_path / "logs"
        mock_manifest.return_value = {}
        mock_vbs.return_value.create_version_bundle.return_value = MagicMock(bundle_id="VB-001")

        call_count = 0

        def _cancelling_process(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                cancel.set()  # Cancel after 2nd doc
            return _fake_process_document(**kwargs)

        mock_proc_doc.side_effect = _cancelling_process

        run_dir = tmp_path / "claims" / "CLM-001" / "runs" / "RUN-001" / "logs"
        run_dir.mkdir(parents=True)

        result = process_claim(
            claim=claim,
            output_base=tmp_path / "claims",
            run_id="RUN-001",
            force=True,
            cancel_event=cancel,
            max_workers=1,  # sequential for deterministic cancellation
        )

        # Should have processed at most 2-3 docs before cancellation kicked in
        assert len(result.documents) < 4


class TestSequentialBackwardCompat:
    """Verify max_workers=1 (default) preserves sequential behavior."""

    @patch("context_builder.pipeline.run.process_document")
    @patch("context_builder.pipeline.run.create_doc_structure")
    @patch("context_builder.pipeline.run.get_workspace_logs_dir")
    @patch("context_builder.pipeline.run.get_version_bundle_store")
    @patch("context_builder.pipeline.run.write_manifest")
    @patch("context_builder.pipeline.run.write_json_atomic")
    @patch("context_builder.pipeline.run.mark_run_complete")
    @patch("context_builder.pipeline.run.is_claim_processed", return_value=False)
    def test_sequential_default(
        self, mock_processed, mock_complete, mock_write, mock_manifest,
        mock_vbs, mock_logs_dir, mock_create_doc, mock_proc_doc, tmp_path,
    ):
        """max_workers=1 processes docs sequentially."""
        from context_builder.pipeline.run import process_claim

        claim = _make_discovered_claim("CLM-001", 3)
        order = []

        def _ordering_process(**kwargs):
            doc = kwargs.get("doc")
            order.append(doc.doc_id)
            return _fake_process_document(**kwargs)

        mock_create_doc.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_logs_dir.return_value = tmp_path / "logs"
        mock_manifest.return_value = {}
        mock_vbs.return_value.create_version_bundle.return_value = MagicMock(bundle_id="VB-001")
        mock_proc_doc.side_effect = _ordering_process

        run_dir = tmp_path / "claims" / "CLM-001" / "runs" / "RUN-001" / "logs"
        run_dir.mkdir(parents=True)

        result = process_claim(
            claim=claim,
            output_base=tmp_path / "claims",
            run_id="RUN-001",
            force=True,
            max_workers=1,
        )

        # Sequential: order matches input order
        assert order == ["doc_0", "doc_1", "doc_2"]
        assert len(result.documents) == 3


class TestEventCollectorIntegration:
    """Verify events are emitted during document processing."""

    @patch("context_builder.pipeline.run.process_document")
    @patch("context_builder.pipeline.run.create_doc_structure")
    @patch("context_builder.pipeline.run.get_workspace_logs_dir")
    @patch("context_builder.pipeline.run.get_version_bundle_store")
    @patch("context_builder.pipeline.run.write_manifest")
    @patch("context_builder.pipeline.run.write_json_atomic")
    @patch("context_builder.pipeline.run.mark_run_complete")
    @patch("context_builder.pipeline.run.is_claim_processed", return_value=False)
    def test_events_emitted_sequential(
        self, mock_processed, mock_complete, mock_write, mock_manifest,
        mock_vbs, mock_logs_dir, mock_create_doc, mock_proc_doc, tmp_path,
    ):
        """EventCollector receives events in sequential mode."""
        from context_builder.pipeline.run import process_claim

        claim = _make_discovered_claim("CLM-001", 2)
        collector = EventCollector(fail_on_error=True)

        mock_create_doc.return_value = (MagicMock(), MagicMock(), MagicMock())
        mock_logs_dir.return_value = tmp_path / "logs"
        mock_manifest.return_value = {}
        mock_vbs.return_value.create_version_bundle.return_value = MagicMock(bundle_id="VB-001")
        mock_proc_doc.side_effect = _fake_process_document

        run_dir = tmp_path / "claims" / "CLM-001" / "runs" / "RUN-001" / "logs"
        run_dir.mkdir(parents=True)

        result = process_claim(
            claim=claim,
            output_base=tmp_path / "claims",
            run_id="RUN-001",
            force=True,
            event_collector=collector,
            max_workers=1,
        )

        collector.close()
        collector.drain()

        all_events = collector.all_events
        # process_document is mocked so DOC_* events don't fire.
        # Only CLAIM_COMPLETE from process_claim is expected.
        claim_events = [e for e in all_events if e.event_type == EventType.CLAIM_COMPLETE]
        assert len(claim_events) == 1
        assert claim_events[0].claim_id == "CLM-001"
