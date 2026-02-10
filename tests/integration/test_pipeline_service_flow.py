"""Integration tests for PipelineService -> process_claim() call chain.

Tests the full async pipeline execution through PipelineService, exercising:
- UploadService staging -> move_to_input
- discover_claims document discovery
- process_claim -> process_document -> stage execution
- Progress callbacks and status logic
- Run persistence to disk

Mocks ONLY at LLM boundaries (classifier, extractor) and git/version metadata.
Uses text documents (source_type="text") to avoid Azure DI / Vision dependencies.

This test layer would have caught the `model=model` kwargs bug where
_run_pipeline passed an unsupported keyword argument to process_claim.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from context_builder.api.services.pipeline import (
    DocPhase,
    PipelineService,
    PipelineStatus,
)
from context_builder.api.services.upload import UploadService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_classifier(doc_type="loss_notice", language="en", confidence=0.92):
    """Return a mock classifier that returns fixed classification results."""
    result = {
        "document_type": doc_type,
        "language": language,
        "confidence": confidence,
    }
    classifier = MagicMock()
    classifier.classify.return_value = result
    classifier.classify_pages.return_value = result
    return classifier


def make_extractor_factory(
    supported_types=None,
    fields=None,
    quality_gate_status="pass",
):
    """Return a mock extractor factory."""
    if fields is None:
        fields = [
            {"name": "claim_number", "value": "CLM-001", "confidence": 0.95},
        ]

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "schema_version": "extraction_result_v1",
        "fields": fields,
        "quality_gate": {"status": quality_gate_status},
    }
    mock_result.quality_gate.status = quality_gate_status

    mock_extractor = MagicMock()
    mock_extractor.model = "gpt-4o-test"
    mock_extractor.extract.return_value = mock_result

    factory = MagicMock()
    if supported_types is not None:
        factory.is_supported.side_effect = lambda dt: dt in supported_types
    else:
        factory.is_supported.return_value = True
    factory.create.return_value = mock_extractor
    return factory


async def stage_text_document(
    upload_service: UploadService,
    claim_id: str,
    filename: str,
    content: str,
) -> None:
    """Stage a text document via UploadService (simulates user upload)."""
    content_bytes = content.encode("utf-8")
    file_mock = MagicMock()
    file_mock.filename = filename
    file_mock.content_type = "text/plain"
    file_mock.read = AsyncMock(return_value=content_bytes)
    await upload_service.add_document(claim_id, file_mock)


async def wait_for_pipeline(
    service: PipelineService,
    run_id: str,
    timeout: float = 30.0,
):
    """Poll until pipeline reaches a terminal status."""
    import time
    start = time.time()
    terminal = {"completed", "partial", "failed", "cancelled"}

    while time.time() - start < timeout:
        run = service.get_run_status(run_id)
        if run and run.status.value in terminal:
            return run
        await asyncio.sleep(0.1)

    raise TimeoutError(f"Pipeline {run_id} did not complete within {timeout}s")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    """Create a workspace-like directory structure."""
    ws = tmp_path / "workspace"
    (ws / "claims").mkdir(parents=True)
    (ws / "runs").mkdir(parents=True)
    (ws / "registry").mkdir(parents=True)
    (ws / "logs").mkdir(parents=True)
    (ws / ".pending").mkdir(parents=True)
    return ws


@pytest.fixture
def upload_service(workspace):
    """Create UploadService with real file I/O."""
    return UploadService(
        staging_dir=workspace / ".pending",
        claims_dir=workspace / "claims",
    )


@pytest.fixture
def pipeline_service(workspace, upload_service):
    """Create PipelineService with real dependencies."""
    return PipelineService(
        output_dir=workspace / "claims",
        upload_service=upload_service,
    )


@pytest.fixture(autouse=True)
def mock_version_bundle_store():
    """Patch get_version_bundle_store so no real git/version logic runs."""
    mock_bundle = MagicMock()
    mock_bundle.bundle_id = "vb_test_integration_01"

    mock_store = MagicMock()
    mock_store.create_version_bundle.return_value = mock_bundle

    with patch(
        "context_builder.pipeline.run.get_version_bundle_store",
        return_value=mock_store,
    ):
        yield mock_store


@pytest.fixture(autouse=True)
def mock_metadata_helpers():
    """Patch git/config helpers for deterministic manifests."""
    with (
        patch(
            "context_builder.pipeline.helpers.metadata.get_git_info",
            return_value={"commit_sha": "abc123integ", "is_dirty": False},
        ),
        patch(
            "context_builder.pipeline.helpers.metadata.compute_workspace_config_hash",
            return_value=None,
        ),
        patch(
            "context_builder.pipeline.helpers.metadata.snapshot_workspace_config",
            return_value=None,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_classifier():
    """Patch ClassifierFactory so process_claim uses a mock classifier."""
    classifier = make_classifier()
    mock_factory = MagicMock()
    mock_factory.create.return_value = classifier

    with patch("context_builder.classification.ClassifierFactory", mock_factory):
        yield classifier


@pytest.fixture(autouse=True)
def mock_extractor():
    """Patch ExtractorFactory at the extraction stage level."""
    factory = make_extractor_factory()

    with patch(
        "context_builder.pipeline.stages.extraction.ExtractorFactory",
        factory,
    ):
        yield factory


# ---------------------------------------------------------------------------
# TestPipelineServiceHappyPath
# ---------------------------------------------------------------------------

class TestPipelineServiceHappyPath:
    """Full chain: start_pipeline -> _run_pipeline -> process_claim."""

    @pytest.mark.asyncio
    async def test_single_claim_completes(
        self, pipeline_service, upload_service, workspace
    ):
        """Single claim with one text doc completes successfully."""
        await stage_text_document(
            upload_service, "CLM-INTEG-001", "notice.txt",
            "Loss notice: vehicle collision on Jan 15, 2026.",
        )

        # Verify staging worked
        claim = upload_service.get_pending_claim("CLM-INTEG-001")
        assert claim is not None
        assert len(claim.documents) == 1

        # Start pipeline
        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-001"],
            model="gpt-4o",
        )

        # Wait for completion
        run = await wait_for_pipeline(pipeline_service, run_id)

        assert run.status == PipelineStatus.COMPLETED
        assert run.summary["total"] == 1
        assert run.summary["success"] == 1
        assert run.summary["failed"] == 0

        # Verify claim artifacts on disk
        claim_dir = workspace / "claims" / "CLM-INTEG-001"
        assert claim_dir.exists()

        # Verify global run artifacts
        run_dir = workspace / "runs" / run_id
        assert run_dir.exists()
        assert (run_dir / "manifest.json").exists()
        assert (run_dir / "summary.json").exists()

        # Verify summary content
        summary = json.loads((run_dir / "summary.json").read_text())
        assert summary["status"] == "completed"
        assert summary["docs_success"] == 1

    @pytest.mark.asyncio
    async def test_multi_doc_claim_completes(
        self, pipeline_service, upload_service, workspace
    ):
        """Claim with 2 text docs both succeed -> COMPLETED."""
        await stage_text_document(
            upload_service, "CLM-INTEG-002", "doc_a.txt",
            "First document content for testing.",
        )
        await stage_text_document(
            upload_service, "CLM-INTEG-002", "doc_b.txt",
            "Second document content for testing.",
        )

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-002"],
            model="gpt-4o",
        )
        run = await wait_for_pipeline(pipeline_service, run_id)

        assert run.status == PipelineStatus.COMPLETED
        assert run.summary["total"] == 2
        assert run.summary["success"] == 2

        # Both docs should be tracked as DONE
        done_docs = [d for d in run.docs.values() if d.phase == DocPhase.DONE]
        assert len(done_docs) == 2

    @pytest.mark.asyncio
    async def test_staging_cleaned_up_after_success(
        self, pipeline_service, upload_service, workspace
    ):
        """Staging and input directories are cleaned up after pipeline."""
        await stage_text_document(
            upload_service, "CLM-INTEG-003", "cleanup.txt",
            "Document to verify cleanup happens.",
        )

        # Verify staging exists before
        staging_dir = workspace / ".pending" / "CLM-INTEG-003"
        assert staging_dir.exists()

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-003"],
            model="gpt-4o",
        )
        await wait_for_pipeline(pipeline_service, run_id)

        # Staging and input should be cleaned up
        assert not staging_dir.exists()
        input_dir = workspace / ".input" / "CLM-INTEG-003"
        assert not input_dir.exists()


# ---------------------------------------------------------------------------
# TestProgressCallbacks
# ---------------------------------------------------------------------------

class TestProgressCallbacks:
    """Verify progress callbacks are wired correctly through the chain."""

    @pytest.mark.asyncio
    async def test_phase_callbacks_received(
        self, pipeline_service, upload_service
    ):
        """Progress callback receives phase updates during execution."""
        await stage_text_document(
            upload_service, "CLM-INTEG-CB", "progress.txt",
            "Document to test progress callbacks.",
        )

        progress_events = []

        async def progress_callback(run_id, doc_id, phase, error, failed_at_stage=None):
            progress_events.append({
                "doc_id": doc_id,
                "phase": phase,
                "error": error,
            })

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-CB"],
            model="gpt-4o",
            progress_callback=progress_callback,
        )
        run = await wait_for_pipeline(pipeline_service, run_id)

        assert run.status == PipelineStatus.COMPLETED

        # Should have received phase updates for the document
        phases_seen = {e["phase"] for e in progress_events}

        # CRITICAL: Intermediate phases must be delivered (not just DONE).
        # This catches the make_phase_callback arity bug where TypeError
        # was silently swallowed by PipelineRunner, resulting in "stuck at
        # Waiting" in the UI until all docs completed at once.
        assert DocPhase.CLASSIFYING in phases_seen, (
            "CLASSIFYING phase never received — phase callback is likely broken"
        )
        assert DocPhase.DONE in phases_seen

        # __RUN_COMPLETE__ signal should be sent
        doc_ids = [e["doc_id"] for e in progress_events]
        assert "__RUN_COMPLETE__" in doc_ids

    @pytest.mark.asyncio
    async def test_stage_phases_in_order(
        self, pipeline_service, upload_service
    ):
        """Phase callbacks arrive in pipeline order: ingest -> classify -> extract."""
        await stage_text_document(
            upload_service, "CLM-INTEG-ORDER", "order.txt",
            "Document to test phase ordering.",
        )

        progress_events = []

        async def progress_callback(run_id, doc_id, phase, error, failed_at_stage=None):
            if doc_id != "__RUN_COMPLETE__":
                progress_events.append(phase)

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-ORDER"],
            model="gpt-4o",
            progress_callback=progress_callback,
        )
        await wait_for_pipeline(pipeline_service, run_id)

        # Filter out PENDING updates (doc_id resolution)
        non_pending = [p for p in progress_events if p != DocPhase.PENDING]

        # Must have at least 2 phases: at least one stage + DONE
        assert len(non_pending) >= 2, (
            f"Expected stage phases + DONE, got only: {non_pending}"
        )

        # Last phase should be DONE
        assert non_pending[-1] == DocPhase.DONE

        # Earlier phases should be pipeline stages in correct order
        stage_phases = non_pending[:-1]
        for phase in stage_phases:
            assert phase in (
                DocPhase.INGESTING,
                DocPhase.CLASSIFYING,
                DocPhase.EXTRACTING,
            )

        # If classifying and extracting both appear, classifying must come first
        if DocPhase.CLASSIFYING in stage_phases and DocPhase.EXTRACTING in stage_phases:
            assert stage_phases.index(DocPhase.CLASSIFYING) < stage_phases.index(
                DocPhase.EXTRACTING
            )


# ---------------------------------------------------------------------------
# TestPipelineServiceFailures
# ---------------------------------------------------------------------------

class TestPipelineServiceFailures:
    """Test failure paths through the full chain."""

    @pytest.mark.asyncio
    async def test_classifier_error_marks_failed(
        self, pipeline_service, upload_service, mock_classifier
    ):
        """Classifier error -> all docs fail -> FAILED status."""
        mock_classifier.classify.side_effect = RuntimeError("LLM API timeout")
        mock_classifier.classify_pages.side_effect = RuntimeError("LLM API timeout")

        await stage_text_document(
            upload_service, "CLM-INTEG-FAIL", "bad.txt",
            "Document that will fail classification.",
        )

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-FAIL"],
            model="gpt-4o",
        )
        run = await wait_for_pipeline(pipeline_service, run_id)

        assert run.status == PipelineStatus.FAILED
        assert run.summary["failed"] > 0

        # Doc should be marked FAILED
        failed_docs = [d for d in run.docs.values() if d.phase == DocPhase.FAILED]
        assert len(failed_docs) > 0

    @pytest.mark.asyncio
    async def test_extractor_error_marks_failed(
        self, pipeline_service, upload_service, mock_extractor
    ):
        """Extractor error -> doc fails -> FAILED status."""
        mock_extractor.create.return_value.extract.side_effect = RuntimeError(
            "Extraction API error"
        )

        await stage_text_document(
            upload_service, "CLM-INTEG-EXFAIL", "extractfail.txt",
            "Document that will fail extraction.",
        )

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-EXFAIL"],
            model="gpt-4o",
        )
        run = await wait_for_pipeline(pipeline_service, run_id)

        assert run.status == PipelineStatus.FAILED
        assert run.summary["failed"] > 0


# ---------------------------------------------------------------------------
# TestPipelineServicePartialStatus
# ---------------------------------------------------------------------------

class TestPipelineServicePartialStatus:
    """Test PARTIAL status when some docs succeed and others fail."""

    @pytest.mark.asyncio
    async def test_mixed_results_partial_status(
        self, pipeline_service, upload_service, mock_extractor
    ):
        """One doc succeeds, one fails extraction -> PARTIAL status."""
        await stage_text_document(
            upload_service, "CLM-INTEG-MIX", "good.txt",
            "Good document that will succeed.",
        )
        await stage_text_document(
            upload_service, "CLM-INTEG-MIX", "bad.txt",
            "Bad document that will fail extraction.",
        )

        # Make extractor fail on second invocation
        original_result = mock_extractor.create.return_value.extract.return_value
        call_count = {"n": 0}

        def extract_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("Extraction failed for second doc")
            return original_result

        mock_extractor.create.return_value.extract.side_effect = extract_side_effect

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-MIX"],
            model="gpt-4o",
        )
        run = await wait_for_pipeline(pipeline_service, run_id)

        assert run.status == PipelineStatus.PARTIAL
        assert run.summary["success"] >= 1
        assert run.summary["failed"] >= 1


# ---------------------------------------------------------------------------
# TestPipelineServiceCancellation
# ---------------------------------------------------------------------------

class TestPipelineServiceCancellation:
    """Test cancellation flow through PipelineService."""

    @pytest.mark.asyncio
    async def test_cancel_sets_cancelled_status(
        self, pipeline_service, upload_service
    ):
        """Cancel after starting -> CANCELLED status."""
        await stage_text_document(
            upload_service, "CLM-INTEG-CANCEL", "cancel.txt",
            "Document that will be cancelled.",
        )

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-CANCEL"],
            model="gpt-4o",
        )

        # Cancel immediately
        cancelled = await pipeline_service.cancel_pipeline(run_id)
        assert cancelled

        run = await wait_for_pipeline(pipeline_service, run_id, timeout=10)

        assert run.status == PipelineStatus.CANCELLED


# ---------------------------------------------------------------------------
# TestPipelineServiceDryRun
# ---------------------------------------------------------------------------

class TestPipelineServiceDryRun:
    """Test dry run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_without_processing(
        self, pipeline_service, upload_service
    ):
        """Dry run returns estimated work without processing."""
        await stage_text_document(
            upload_service, "CLM-INTEG-DRY", "dry.txt",
            "Document for dry run test.",
        )

        run_id = await pipeline_service.start_pipeline(
            claim_ids=["CLM-INTEG-DRY"],
            model="gpt-4o",
            dry_run=True,
        )

        run = pipeline_service.get_run_status(run_id)
        assert run is not None
        assert run.status == PipelineStatus.COMPLETED
        assert run.summary["dry_run"] is True
        assert run.summary["total"] == 1

        # Staging should still exist (dry run doesn't process)
        staging_dir = upload_service._get_claim_staging_dir("CLM-INTEG-DRY")
        assert staging_dir.exists()


# ---------------------------------------------------------------------------
# TestKwargsContract
# ---------------------------------------------------------------------------

class TestKwargsContract:
    """Contract tests: verify _run_pipeline passes valid kwargs to process_claim.

    These tests would have caught the `model=model` bug that caused:
    process_claim() got an unexpected keyword argument 'model'
    """

    def test_process_claim_has_no_model_param(self):
        """process_claim must not accept a 'model' keyword argument."""
        import inspect
        from context_builder.pipeline.run import process_claim

        sig = inspect.signature(process_claim)
        assert "model" not in sig.parameters, (
            "process_claim should not have a 'model' parameter. "
            "Model is metadata for PipelineRun, not a process_claim arg."
        )

    def test_run_pipeline_kwargs_match_process_claim_signature(self):
        """All kwargs passed by _run_pipeline must be accepted by process_claim."""
        import inspect
        from context_builder.pipeline.run import process_claim

        sig = inspect.signature(process_claim)
        valid_params = set(sig.parameters.keys())

        # These are the kwargs _run_pipeline passes (pipeline.py:322-330)
        passed_kwargs = {
            "claim",
            "output_base",
            "run_id",
            "stage_config",
            "progress_callback",
            "phase_callback",
        }

        invalid = passed_kwargs - valid_params
        assert invalid == set(), (
            f"_run_pipeline passes kwargs not accepted by process_claim: {invalid}"
        )
