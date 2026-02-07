"""Integration tests for claims pipeline (ingest → classify → extract).

Tests multi-stage data flow with real file I/O and mocked LLM providers.
Uses text documents (source_type="text", needs_ingestion=False) to avoid
external ingestion dependencies (Azure DI / Vision).
"""

import hashlib
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from context_builder.pipeline.run import process_claim
from context_builder.pipeline.discovery import DiscoveredClaim, DiscoveredDocument
from context_builder.pipeline.stages import PipelineProviders, StageConfig
from context_builder.schemas.run_errors import PipelineStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_text_doc(tmp_path: Path, filename: str, content: str) -> DiscoveredDocument:
    """Create a text file on disk and return a DiscoveredDocument for it."""
    input_dir = tmp_path / "input"
    input_dir.mkdir(exist_ok=True)
    doc_file = input_dir / filename
    doc_file.write_text(content, encoding="utf-8")
    file_md5 = hashlib.md5(content.encode("utf-8")).hexdigest()
    doc_id = file_md5[:12]
    return DiscoveredDocument(
        source_path=doc_file,
        original_filename=filename,
        source_type="text",
        file_md5=file_md5,
        doc_id=doc_id,
        content=content,
        needs_ingestion=False,
    )


def make_claim(claim_id: str, documents: list, source_path: Path) -> DiscoveredClaim:
    """Wrap documents into a DiscoveredClaim."""
    return DiscoveredClaim(
        claim_id=claim_id,
        source_path=source_path,
        documents=documents,
    )


def make_classifier(doc_type: str = "loss_notice", language: str = "es", confidence: float = 0.92):
    """Return a mock classifier that returns fixed classification results.

    Handles both classify() and classify_pages() calls used by the
    ClassificationStage depending on whether pages_data is available.
    """
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
    supported_types: list | None = None,
    fields: list | None = None,
    quality_gate_status: str = "pass",
):
    """Return a mock extractor factory.

    The factory's ``is_supported()`` returns True for types in *supported_types*
    (defaults to all types). The extractor returned by ``create()`` produces a
    result with the given *fields* and *quality_gate_status*.
    """
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Create a workspace-like output directory: <tmp>/workspace/claims."""
    claims_dir = tmp_path / "workspace" / "claims"
    claims_dir.mkdir(parents=True)
    return claims_dir


@pytest.fixture(autouse=True)
def mock_version_bundle_store():
    """Patch get_version_bundle_store so no real git/version logic runs."""
    mock_bundle = MagicMock()
    mock_bundle.bundle_id = "vb_test_bundle_01"

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
            return_value={"commit_sha": "abc123test", "is_dirty": False},
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


# ---------------------------------------------------------------------------
# TestPipelineHappyPath
# ---------------------------------------------------------------------------

class TestPipelineHappyPath:
    """Verify successful end-to-end pipeline runs produce all expected artifacts."""

    def test_single_doc_full_pipeline(self, tmp_path, output_dir):
        """Single text doc through full pipeline → all artifacts created."""
        doc = make_text_doc(tmp_path, "notice.txt", "Loss notice: vehicle collision on Jan 15.")
        claim = make_claim("CLM-001", [doc], tmp_path / "input")
        classifier = make_classifier("loss_notice", "en", 0.95)
        ext_factory = make_extractor_factory()

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_001",
            force=True,
            compute_metrics=False,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "success"
        assert result.run_id == "run_integ_001"
        assert len(result.documents) == 1

        doc_result = result.documents[0]
        assert doc_result.status == "success"
        assert doc_result.doc_type == "loss_notice"
        assert doc_result.extraction_path is not None

        # Check file artifacts on disk
        run_dir = output_dir / "CLM-001" / "runs" / "run_integ_001"
        doc_dir = output_dir / "CLM-001" / "docs" / doc.doc_id

        assert (doc_dir / "text" / "pages.json").exists()
        assert (doc_dir / "meta" / "doc.json").exists()
        assert (run_dir / "extraction" / f"{doc.doc_id}.json").exists()
        assert (run_dir / "manifest.json").exists()
        assert (run_dir / "logs" / "summary.json").exists()
        assert (run_dir / ".complete").exists()

        # Validate JSON content
        doc_meta = json.loads((doc_dir / "meta" / "doc.json").read_text())
        assert doc_meta["doc_type"] == "loss_notice"

        extraction = json.loads(
            (run_dir / "extraction" / f"{doc.doc_id}.json").read_text()
        )
        assert extraction["fields"] is not None

        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["run_id"] == "run_integ_001"

    def test_multi_document_claim(self, tmp_path, output_dir):
        """3 text docs with different types all succeed."""
        docs = [
            make_text_doc(tmp_path, "notice.txt", "Loss notice content here."),
            make_text_doc(tmp_path, "police.txt", "Police report content here."),
            make_text_doc(tmp_path, "estimate.txt", "Repair estimate content here."),
        ]
        claim = make_claim("CLM-002", docs, tmp_path / "input")

        # Classifier returns different types based on filename
        type_map = {
            "notice.txt": "loss_notice",
            "police.txt": "police_report",
            "estimate.txt": "repair_estimate",
        }

        def classify_by_filename(*args, **kwargs):
            # classify_pages(pages, filename) or classify(text, filename)
            filename = args[1] if len(args) > 1 else "unknown"
            doc_type = type_map.get(filename, "unknown")
            return {"document_type": doc_type, "language": "en", "confidence": 0.90}

        classifier = MagicMock()
        classifier.classify.side_effect = classify_by_filename
        classifier.classify_pages.side_effect = classify_by_filename

        ext_factory = make_extractor_factory()

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_002",
            force=True,
            compute_metrics=False,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "success"
        assert result.stats["total"] == 3
        assert result.stats["success"] == 3
        assert len(result.documents) == 3

        # Each doc should have extraction output
        run_dir = output_dir / "CLM-002" / "runs" / "run_integ_002"
        for doc in docs:
            assert (run_dir / "extraction" / f"{doc.doc_id}.json").exists()

        # Summary should list 3 documents
        summary = json.loads((run_dir / "logs" / "summary.json").read_text())
        assert len(summary["documents"]) == 3

    def test_run_artifacts_content(self, tmp_path, output_dir):
        """Deep validation of manifest.json and summary.json content."""
        doc = make_text_doc(tmp_path, "claim_form.txt", "Insurance claim form content.")
        claim = make_claim("CLM-003", [doc], tmp_path / "input")
        classifier = make_classifier("claim_form", "en", 0.88)
        ext_factory = make_extractor_factory(quality_gate_status="warn")

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_003",
            force=True,
            compute_metrics=False,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "success"

        run_dir = output_dir / "CLM-003" / "runs" / "run_integ_003"

        # --- Manifest validation ---
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["run_id"] == "run_integ_003"
        assert manifest["started_at"] is not None
        assert manifest["ended_at"] is not None
        assert manifest["input"]["claim_id"] == "CLM-003"
        assert manifest["input"]["docs_discovered"] == 1
        assert manifest["stages_executed"] == ["ingest", "classify", "extract"]
        assert manifest["run_kind"] == "full"

        # --- Summary validation ---
        summary = json.loads((run_dir / "logs" / "summary.json").read_text())
        assert summary["status"] == "success"
        assert summary["claim_id"] == "CLM-003"
        assert summary["run_id"] == "run_integ_003"
        assert summary["stats"]["total"] == 1
        assert summary["stats"]["success"] == 1
        assert len(summary["documents"]) == 1
        assert "phases" in summary

        # --- .complete marker ---
        assert (run_dir / ".complete").exists()

        # --- run.log exists (may be empty if root logger level > DEBUG) ---
        run_log = run_dir / "logs" / "run.log"
        assert run_log.exists()


# ---------------------------------------------------------------------------
# TestStageFiltering
# ---------------------------------------------------------------------------

class TestStageFiltering:
    """Verify stage-selective execution and doc-type filtering."""

    def test_ingest_classify_only(self, tmp_path, output_dir):
        """stages=[INGEST, CLASSIFY] → no extraction output."""
        doc = make_text_doc(tmp_path, "report.txt", "Some report content.")
        claim = make_claim("CLM-010", [doc], tmp_path / "input")
        classifier = make_classifier("police_report")
        ext_factory = make_extractor_factory()

        stage_config = StageConfig(
            stages=[PipelineStage.INGEST, PipelineStage.CLASSIFY],
        )

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_010",
            force=True,
            compute_metrics=False,
            stage_config=stage_config,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "success"

        doc_dir = output_dir / "CLM-010" / "docs" / doc.doc_id
        run_dir = output_dir / "CLM-010" / "runs" / "run_integ_010"

        assert (doc_dir / "text" / "pages.json").exists()
        assert (doc_dir / "meta" / "doc.json").exists()
        assert not (run_dir / "extraction" / f"{doc.doc_id}.json").exists()

        doc_result = result.documents[0]
        assert doc_result.extraction_path is None

    def test_doc_type_filter_skips_unmatched(self, tmp_path, output_dir):
        """doc_type_filter=["fnol_form"] → only fnol_form gets extraction."""
        docs = [
            make_text_doc(tmp_path, "fnol.txt", "First notice of loss form."),
            make_text_doc(tmp_path, "police.txt", "Police report text."),
        ]
        claim = make_claim("CLM-011", docs, tmp_path / "input")

        type_map = {
            "fnol.txt": "fnol_form",
            "police.txt": "police_report",
        }

        def classify_by_filename(*args, **kwargs):
            filename = args[1] if len(args) > 1 else "unknown"
            doc_type = type_map.get(filename, "unknown")
            return {"document_type": doc_type, "language": "en", "confidence": 0.90}

        classifier = MagicMock()
        classifier.classify.side_effect = classify_by_filename
        classifier.classify_pages.side_effect = classify_by_filename

        ext_factory = make_extractor_factory()

        stage_config = StageConfig(
            stages=[PipelineStage.INGEST, PipelineStage.CLASSIFY, PipelineStage.EXTRACT],
            doc_type_filter=["fnol_form"],
        )

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_011",
            force=True,
            compute_metrics=False,
            stage_config=stage_config,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "success"

        run_dir = output_dir / "CLM-011" / "runs" / "run_integ_011"

        # Both should be classified
        for doc in docs:
            doc_json = output_dir / "CLM-011" / "docs" / doc.doc_id / "meta" / "doc.json"
            assert doc_json.exists()

        # Only fnol should have extraction
        fnol_doc = docs[0]
        police_doc = docs[1]
        assert (run_dir / "extraction" / f"{fnol_doc.doc_id}.json").exists()
        assert not (run_dir / "extraction" / f"{police_doc.doc_id}.json").exists()

    def test_unsupported_doc_type_skips_extraction(self, tmp_path, output_dir):
        """Unsupported doc type → success with no extraction file."""
        doc = make_text_doc(tmp_path, "unknown.txt", "Unknown document content.")
        claim = make_claim("CLM-012", [doc], tmp_path / "input")
        classifier = make_classifier("unknown_type")
        ext_factory = make_extractor_factory(supported_types=["loss_notice", "police_report"])

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_012",
            force=True,
            compute_metrics=False,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "success"
        doc_result = result.documents[0]
        assert doc_result.doc_type == "unknown_type"
        assert doc_result.extraction_path is None

        run_dir = output_dir / "CLM-012" / "runs" / "run_integ_012"
        assert not (run_dir / "extraction" / f"{doc.doc_id}.json").exists()


# ---------------------------------------------------------------------------
# TestStageReuse
# ---------------------------------------------------------------------------

class TestStageReuse:
    """Verify reuse of prior-stage artifacts on subsequent runs."""

    def test_reuse_ingestion_on_second_run(self, tmp_path, output_dir):
        """Run 1: ingest+classify → Run 2: classify+extract reuses pages.json."""
        doc = make_text_doc(tmp_path, "reuse.txt", "Reuse test document content.")
        claim = make_claim("CLM-020", [doc], tmp_path / "input")
        classifier = make_classifier("loss_notice")
        ext_factory = make_extractor_factory()

        # --- Run 1: Ingest + Classify (no extraction) ---
        # We include CLASSIFY so the doc isn't marked "skipped" (the
        # ClassificationStage sets status="skipped" when run_classify=False
        # and no prior doc.json exists).
        stage_config_1 = StageConfig(
            stages=[PipelineStage.INGEST, PipelineStage.CLASSIFY],
        )

        result_1 = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_020a",
            force=True,
            compute_metrics=False,
            stage_config=stage_config_1,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result_1.status == "success"
        doc_dir = output_dir / "CLM-020" / "docs" / doc.doc_id
        assert (doc_dir / "text" / "pages.json").exists()

        # --- Run 2: Classify + Extract (reuse ingestion) ---
        stage_config_2 = StageConfig(
            stages=[PipelineStage.CLASSIFY, PipelineStage.EXTRACT],
        )

        result_2 = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_020b",
            force=True,
            compute_metrics=False,
            stage_config=stage_config_2,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result_2.status == "success"
        doc_result = result_2.documents[0]
        assert doc_result.ingestion_reused is True

        run_dir_2 = output_dir / "CLM-020" / "runs" / "run_integ_020b"
        assert (run_dir_2 / "extraction" / f"{doc.doc_id}.json").exists()


# ---------------------------------------------------------------------------
# TestErrorHandling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Verify error propagation and status reporting."""

    def test_classification_error_propagates(self, tmp_path, output_dir):
        """Classifier raises → result.status == 'failed', error details captured."""
        doc = make_text_doc(tmp_path, "bad.txt", "Document that will fail classification.")
        claim = make_claim("CLM-030", [doc], tmp_path / "input")

        classifier = MagicMock()
        classifier.classify.side_effect = RuntimeError("LLM API timeout")
        classifier.classify_pages.side_effect = RuntimeError("LLM API timeout")

        ext_factory = make_extractor_factory()

        result = process_claim(
            claim=claim,
            output_base=output_dir,
            classifier=classifier,
            run_id="run_integ_030",
            force=True,
            compute_metrics=False,
            providers=PipelineProviders(extractor_factory=ext_factory),
        )

        assert result.status == "failed"

        doc_result = result.documents[0]
        assert doc_result.status == "error"
        assert doc_result.failed_phase == "classification"
        assert "LLM API timeout" in (doc_result.error or "")

        # No extraction file
        run_dir = output_dir / "CLM-030" / "runs" / "run_integ_030"
        assert not (run_dir / "extraction" / f"{doc.doc_id}.json").exists()

        # Summary should record the error
        summary = json.loads((run_dir / "logs" / "summary.json").read_text())
        failed_docs = [d for d in summary["documents"] if d["status"] == "failed"]
        assert len(failed_docs) == 1
        assert "LLM API timeout" in (failed_docs[0].get("error_message") or "")
