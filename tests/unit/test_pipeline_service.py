"""Unit tests for PipelineService."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from context_builder.api.services.pipeline import (
    DocPhase,
    DocProgress,
    PipelineRun,
    PipelineService,
    PipelineStatus,
)
from context_builder.api.services.upload import PendingClaim, PendingDocument, UploadService


@pytest.fixture
def mock_upload_service(tmp_path):
    """Create a mock UploadService."""
    staging_dir = tmp_path / ".pending"
    claims_dir = tmp_path / "claims"
    return UploadService(staging_dir, claims_dir)


@pytest.fixture
def pipeline_service(tmp_path, mock_upload_service):
    """Create a PipelineService with mocked dependencies."""
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    return PipelineService(claims_dir, mock_upload_service)


class TestPipelineServiceInit:
    """Tests for PipelineService initialization."""

    def test_init_creates_empty_state(self, pipeline_service):
        """Service initializes with empty run tracking."""
        assert pipeline_service.active_runs == {}
        assert pipeline_service.cancel_events == {}


class TestGenerateRunId:
    """Tests for run ID generation."""

    def test_run_id_format(self, pipeline_service):
        """Run IDs follow expected format."""
        run_id = pipeline_service._generate_run_id()
        assert run_id.startswith("run_")
        # Format: run_YYYYMMDD_HHMMSS_*
        parts = run_id.split("_")
        assert len(parts) >= 3

    def test_run_id_contains_timestamp(self, pipeline_service):
        """Run ID contains a timestamp component."""
        run_id = pipeline_service._generate_run_id()
        # Should have date and time components
        assert len(run_id) > 15  # run_ + 8 digit date + _ + time


class TestStartPipeline:
    """Tests for starting pipeline execution."""

    @pytest.mark.asyncio
    async def test_creates_run_tracking(self, pipeline_service, mock_upload_service):
        """Starting pipeline creates run tracking entry."""
        # Create a pending claim
        from io import BytesIO
        from unittest.mock import MagicMock

        async def mock_read():
            return b"%PDF-1.4 test"

        file = MagicMock()
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = mock_read

        await mock_upload_service.add_document("TEST-001", file)

        # Mock the pipeline execution to prevent actual processing
        with patch.object(pipeline_service, '_run_pipeline', new_callable=AsyncMock):
            run_id = await pipeline_service.start_pipeline(
                claim_ids=["TEST-001"],
                model="gpt-4o",
            )

        assert run_id in pipeline_service.active_runs
        run = pipeline_service.active_runs[run_id]
        assert run.claim_ids == ["TEST-001"]
        assert run.status == PipelineStatus.PENDING

    @pytest.mark.asyncio
    async def test_initializes_doc_progress(self, pipeline_service, mock_upload_service):
        """Starting pipeline initializes doc progress for all documents."""
        # Create pending claim with multiple docs
        async def mock_read():
            return b"%PDF-1.4 test"

        for i in range(3):
            file = MagicMock()
            file.filename = f"doc{i}.pdf"
            file.content_type = "application/pdf"
            file.read = mock_read
            await mock_upload_service.add_document("CLAIM-001", file)

        with patch.object(pipeline_service, '_run_pipeline', new_callable=AsyncMock):
            run_id = await pipeline_service.start_pipeline(
                claim_ids=["CLAIM-001"],
                model="gpt-4o",
            )

        run = pipeline_service.active_runs[run_id]
        assert len(run.docs) == 3
        for doc in run.docs.values():
            assert doc.phase == DocPhase.PENDING


class TestCancelPipeline:
    """Tests for cancelling pipeline execution."""

    @pytest.mark.asyncio
    async def test_sets_cancel_event(self, pipeline_service, mock_upload_service):
        """Cancelling sets the cancel event."""
        # Create a pending claim
        async def mock_read():
            return b"%PDF-1.4 test"

        file = MagicMock()
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = mock_read
        await mock_upload_service.add_document("TEST-001", file)

        with patch.object(pipeline_service, '_run_pipeline', new_callable=AsyncMock):
            run_id = await pipeline_service.start_pipeline(
                claim_ids=["TEST-001"],
                model="gpt-4o",
            )

        result = await pipeline_service.cancel_pipeline(run_id)
        assert result is True
        assert pipeline_service.cancel_events[run_id].is_set()

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_false(self, pipeline_service):
        """Cancelling nonexistent run returns False."""
        result = await pipeline_service.cancel_pipeline("nonexistent")
        assert result is False


class TestGetRunStatus:
    """Tests for getting run status."""

    @pytest.mark.asyncio
    async def test_returns_run_status(self, pipeline_service, mock_upload_service):
        """Get status returns the run object."""
        async def mock_read():
            return b"%PDF-1.4 test"

        file = MagicMock()
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = mock_read
        await mock_upload_service.add_document("TEST-001", file)

        with patch.object(pipeline_service, '_run_pipeline', new_callable=AsyncMock):
            run_id = await pipeline_service.start_pipeline(
                claim_ids=["TEST-001"],
                model="gpt-4o",
            )

        status = pipeline_service.get_run_status(run_id)
        assert status is not None
        assert status.run_id == run_id

    def test_returns_none_for_nonexistent(self, pipeline_service):
        """Get status returns None for nonexistent run."""
        status = pipeline_service.get_run_status("nonexistent")
        assert status is None


class TestIsCancelled:
    """Tests for checking cancellation status."""

    @pytest.mark.asyncio
    async def test_not_cancelled_initially(self, pipeline_service, mock_upload_service):
        """Runs are not cancelled initially."""
        async def mock_read():
            return b"%PDF-1.4 test"

        file = MagicMock()
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = mock_read
        await mock_upload_service.add_document("TEST-001", file)

        with patch.object(pipeline_service, '_run_pipeline', new_callable=AsyncMock):
            run_id = await pipeline_service.start_pipeline(
                claim_ids=["TEST-001"],
                model="gpt-4o",
            )

        assert not pipeline_service._is_cancelled(run_id)

    @pytest.mark.asyncio
    async def test_cancelled_after_cancel(self, pipeline_service, mock_upload_service):
        """Run is cancelled after cancel is called."""
        async def mock_read():
            return b"%PDF-1.4 test"

        file = MagicMock()
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = mock_read
        await mock_upload_service.add_document("TEST-001", file)

        with patch.object(pipeline_service, '_run_pipeline', new_callable=AsyncMock):
            run_id = await pipeline_service.start_pipeline(
                claim_ids=["TEST-001"],
                model="gpt-4o",
            )

        await pipeline_service.cancel_pipeline(run_id)
        assert pipeline_service._is_cancelled(run_id)


class TestDocProgress:
    """Tests for DocProgress dataclass."""

    def test_default_phase(self):
        """Default phase is PENDING."""
        doc = DocProgress(
            doc_id="doc1",
            claim_id="claim1",
            filename="test.pdf",
        )
        assert doc.phase == DocPhase.PENDING
        assert doc.error is None


class TestPipelineRun:
    """Tests for PipelineRun dataclass."""

    def test_default_status(self):
        """Default status is PENDING."""
        run = PipelineRun(
            run_id="run_123",
            claim_ids=["claim1"],
        )
        assert run.status == PipelineStatus.PENDING
        assert run.docs == {}
        assert run.started_at is None
        assert run.completed_at is None


class TestDocPhase:
    """Tests for DocPhase enum."""

    def test_phase_values(self):
        """Phase enum has expected values."""
        assert DocPhase.PENDING.value == "pending"
        assert DocPhase.INGESTING.value == "ingesting"
        assert DocPhase.CLASSIFYING.value == "classifying"
        assert DocPhase.EXTRACTING.value == "extracting"
        assert DocPhase.DONE.value == "done"
        assert DocPhase.FAILED.value == "failed"


class TestPipelineStatus:
    """Tests for PipelineStatus enum."""

    def test_status_values(self):
        """Status enum has expected values."""
        assert PipelineStatus.PENDING.value == "pending"
        assert PipelineStatus.RUNNING.value == "running"
        assert PipelineStatus.COMPLETED.value == "completed"
        assert PipelineStatus.FAILED.value == "failed"
        assert PipelineStatus.CANCELLED.value == "cancelled"


class TestPersistRun:
    """Tests for run persistence to disk."""

    def test_creates_run_directory(self, pipeline_service, tmp_path):
        """_persist_run creates the global run directory structure."""
        run = PipelineRun(
            run_id="run_20260113_120000_abc123",
            claim_ids=["CLAIM-001"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 3, "success": 2, "failed": 1},
        )

        pipeline_service._persist_run(run)

        # Check global run directory was created (output/runs/{run_id}/)
        runs_dir = tmp_path / "runs" / run.run_id
        assert runs_dir.exists()

    def test_creates_manifest_json(self, pipeline_service, tmp_path):
        """_persist_run creates manifest.json with correct content."""
        import json

        run = PipelineRun(
            run_id="run_20260113_120000_abc123",
            claim_ids=["CLAIM-001", "CLAIM-002"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 3, "success": 3, "failed": 0},
            model="gpt-4o",
        )
        run.docs = {
            "CLAIM-001/doc1": DocProgress("doc1", "CLAIM-001", "test1.pdf"),
            "CLAIM-001/doc2": DocProgress("doc2", "CLAIM-001", "test2.pdf"),
        }

        pipeline_service._persist_run(run)

        manifest_path = tmp_path / "runs" / run.run_id / "manifest.json"
        assert manifest_path.exists()

        with open(manifest_path) as f:
            manifest = json.load(f)

        assert manifest["run_id"] == run.run_id
        assert manifest["started_at"] == "2026-01-13T12:00:00Z"
        assert manifest["ended_at"] == "2026-01-13T12:05:00Z"
        assert manifest["model"] == "gpt-4o"
        assert manifest["claims_count"] == 2
        assert len(manifest["claims"]) == 1  # Only CLAIM-001 has docs
        assert manifest["claims"][0]["claim_id"] == "CLAIM-001"
        assert manifest["claims"][0]["docs_count"] == 2

    def test_creates_summary_json(self, pipeline_service, tmp_path):
        """_persist_run creates summary.json with correct content."""
        import json

        run = PipelineRun(
            run_id="run_20260113_120000_abc123",
            claim_ids=["CLAIM-001"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 5, "success": 4, "failed": 1},
        )

        pipeline_service._persist_run(run)

        summary_path = tmp_path / "runs" / run.run_id / "summary.json"
        assert summary_path.exists()

        with open(summary_path) as f:
            summary = json.load(f)

        assert summary["run_id"] == run.run_id
        assert summary["status"] == "completed"
        assert summary["docs_total"] == 5
        assert summary["docs_success"] == 4
        assert summary["claims_discovered"] == 1
        assert summary["claims_processed"] == 1
        assert summary["completed_at"] == "2026-01-13T12:05:00Z"

    def test_creates_complete_marker(self, pipeline_service, tmp_path):
        """_persist_run creates .complete marker file."""
        run = PipelineRun(
            run_id="run_20260113_120000_abc123",
            claim_ids=["CLAIM-001"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 1, "success": 1, "failed": 0},
        )

        pipeline_service._persist_run(run)

        complete_marker = tmp_path / "runs" / run.run_id / ".complete"
        assert complete_marker.exists()

    def test_run_discoverable_by_filesystem(self, pipeline_service, tmp_path):
        """Persisted run can be discovered by FileStorage.list_runs()."""
        from context_builder.storage import FileStorage

        run = PipelineRun(
            run_id="run_20260113_120000_abc123",
            claim_ids=["CLAIM-001"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 1, "success": 1, "failed": 0},
        )

        pipeline_service._persist_run(run)

        # FileStorage should be able to find this run
        storage = FileStorage(tmp_path / "claims")
        runs = storage.list_runs()

        run_ids = [r.run_id for r in runs]
        assert run.run_id in run_ids


class TestAppendToRunIndex:
    """Tests for appending runs to the index."""

    def test_appends_to_existing_index(self, pipeline_service, tmp_path):
        """_append_to_run_index appends to existing run_index.jsonl."""
        import json
        from context_builder.pipeline.paths import create_workspace_run_structure

        # Create registry directory with existing index
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir(parents=True)
        run_index_path = registry_dir / "run_index.jsonl"

        # Write an existing run to the index
        existing_record = {"run_id": "run_existing", "status": "complete"}
        with open(run_index_path, "w") as f:
            f.write(json.dumps(existing_record) + "\n")

        # Create a new run
        run = PipelineRun(
            run_id="run_20260113_120000_new",
            claim_ids=["CLAIM-001"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 2, "success": 2, "failed": 0},
        )

        ws_paths = create_workspace_run_structure(pipeline_service.output_dir, run.run_id)
        pipeline_service._append_to_run_index(run, ws_paths, run.summary)

        # Read back and verify both records exist
        with open(run_index_path) as f:
            lines = f.readlines()

        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        run_ids = [r["run_id"] for r in records]
        assert "run_existing" in run_ids
        assert "run_20260113_120000_new" in run_ids

    def test_skips_when_no_index_exists(self, pipeline_service, tmp_path):
        """_append_to_run_index does nothing if index doesn't exist."""
        from context_builder.pipeline.paths import create_workspace_run_structure

        run = PipelineRun(
            run_id="run_20260113_120000_new",
            claim_ids=["CLAIM-001"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 1, "success": 1, "failed": 0},
        )

        ws_paths = create_workspace_run_structure(pipeline_service.output_dir, run.run_id)

        # Should not raise, just skip
        pipeline_service._append_to_run_index(run, ws_paths, run.summary)

        # Verify no index was created
        run_index_path = tmp_path / "registry" / "run_index.jsonl"
        assert not run_index_path.exists()

    def test_index_record_format(self, pipeline_service, tmp_path):
        """Index record has correct format matching index_builder."""
        import json
        from context_builder.pipeline.paths import create_workspace_run_structure

        # Create registry with empty index
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir(parents=True)
        run_index_path = registry_dir / "run_index.jsonl"
        run_index_path.touch()

        run = PipelineRun(
            run_id="run_20260113_120000_test",
            claim_ids=["CLAIM-001", "CLAIM-002"],
            status=PipelineStatus.COMPLETED,
            started_at="2026-01-13T12:00:00Z",
            completed_at="2026-01-13T12:05:00Z",
            summary={"total": 5, "success": 4, "failed": 1},
        )

        ws_paths = create_workspace_run_structure(pipeline_service.output_dir, run.run_id)
        pipeline_service._append_to_run_index(run, ws_paths, run.summary)

        with open(run_index_path) as f:
            record = json.loads(f.read().strip())

        # Verify all expected fields are present
        assert record["run_id"] == "run_20260113_120000_test"
        assert record["started_at"] == "2026-01-13T12:00:00Z"
        assert record["ended_at"] == "2026-01-13T12:05:00Z"
        assert record["claims_count"] == 2
        assert record["docs_count"] == 5
        assert "run_root" in record


class TestDetectStagesForClaim:
    """Tests for smart stage detection."""

    def test_all_stages_when_no_outputs(self, pipeline_service, tmp_path):
        """Returns all stages when no existing outputs."""
        from context_builder.pipeline.run import PipelineStage

        # No existing outputs
        stage_config = pipeline_service._detect_stages_for_claim("CLAIM-001", ["doc1", "doc2"])

        assert stage_config.run_ingest is True
        assert stage_config.run_classify is True
        assert stage_config.run_extract is True

    def test_skips_ingest_when_pages_exist(self, pipeline_service, tmp_path):
        """Skips ingestion when pages.json exists for all docs."""
        import json

        claim_id = "CLAIM-001"
        doc_ids = ["doc1", "doc2"]

        # Create existing ingestion outputs
        for doc_id in doc_ids:
            doc_dir = tmp_path / "claims" / claim_id / "docs" / doc_id / "text"
            doc_dir.mkdir(parents=True)
            pages_json = doc_dir / "pages.json"
            with open(pages_json, "w") as f:
                json.dump({"pages": [{"text": "test"}]}, f)

        stage_config = pipeline_service._detect_stages_for_claim(claim_id, doc_ids)

        assert stage_config.run_ingest is False
        assert stage_config.run_classify is True  # No doc.json yet
        assert stage_config.run_extract is True

    def test_skips_classify_when_doc_json_exists(self, pipeline_service, tmp_path):
        """Skips classification when doc.json exists for all docs."""
        import json

        claim_id = "CLAIM-001"
        doc_ids = ["doc1", "doc2"]

        # Create existing ingestion AND classification outputs
        for doc_id in doc_ids:
            # pages.json
            text_dir = tmp_path / "claims" / claim_id / "docs" / doc_id / "text"
            text_dir.mkdir(parents=True)
            with open(text_dir / "pages.json", "w") as f:
                json.dump({"pages": [{"text": "test"}]}, f)

            # doc.json
            meta_dir = tmp_path / "claims" / claim_id / "docs" / doc_id / "meta"
            meta_dir.mkdir(parents=True)
            with open(meta_dir / "doc.json", "w") as f:
                json.dump({"doc_type": "invoice", "confidence": 0.95}, f)

        stage_config = pipeline_service._detect_stages_for_claim(claim_id, doc_ids)

        assert stage_config.run_ingest is False
        assert stage_config.run_classify is False
        assert stage_config.run_extract is True  # Always run extraction

    def test_runs_ingest_if_any_doc_missing_pages(self, pipeline_service, tmp_path):
        """Runs ingestion if any doc is missing pages.json."""
        import json

        claim_id = "CLAIM-001"
        doc_ids = ["doc1", "doc2"]

        # Only create pages.json for doc1, not doc2
        doc_dir = tmp_path / "claims" / claim_id / "docs" / "doc1" / "text"
        doc_dir.mkdir(parents=True)
        with open(doc_dir / "pages.json", "w") as f:
            json.dump({"pages": [{"text": "test"}]}, f)

        stage_config = pipeline_service._detect_stages_for_claim(claim_id, doc_ids)

        # Must run ingest because doc2 is missing
        assert stage_config.run_ingest is True
        assert stage_config.run_classify is True
        assert stage_config.run_extract is True

    def test_always_runs_extraction(self, pipeline_service, tmp_path):
        """Extraction always runs regardless of existing outputs."""
        import json

        claim_id = "CLAIM-001"
        doc_ids = ["doc1"]

        # Create all outputs including extraction
        doc_root = tmp_path / "claims" / claim_id / "docs" / "doc1"

        text_dir = doc_root / "text"
        text_dir.mkdir(parents=True)
        with open(text_dir / "pages.json", "w") as f:
            json.dump({"pages": []}, f)

        meta_dir = doc_root / "meta"
        meta_dir.mkdir(parents=True)
        with open(meta_dir / "doc.json", "w") as f:
            json.dump({"doc_type": "invoice"}, f)

        stage_config = pipeline_service._detect_stages_for_claim(claim_id, doc_ids)

        # Extraction should still run (new run = new extraction)
        assert stage_config.run_extract is True
