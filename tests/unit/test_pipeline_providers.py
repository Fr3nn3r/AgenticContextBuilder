"""Tests for pipeline dependency injection hooks."""

from pathlib import Path

from context_builder.pipeline.discovery import DiscoveredClaim, DiscoveredDocument
from context_builder.pipeline.paths import create_doc_structure, get_claim_paths, get_run_paths
from context_builder.pipeline.run import PipelineProviders, StageConfig, process_claim, process_document
from context_builder.schemas.run_errors import PipelineStage


class FakeClassifier:
    def classify(self, text, filename):
        return {
            "document_type": "invoice",
            "language": "en",
            "confidence": 0.9,
        }


class FakeClassifierFactory:
    def __init__(self, classifier):
        self.classifier = classifier
        self.called = 0

    def create(self, name):
        self.called += 1
        return self.classifier


class FakeExtractor:
    model = "fake-model"

    def extract(self, pages, doc_meta, run_meta):
        class Result:
            def __init__(self):
                class Gate:
                    status = "pass"

                self.quality_gate = Gate()

            def model_dump(self):
                return {
                    "schema_version": "extraction_result_v1",
                    "fields": [],
                    "quality_gate": {"status": "pass"},
                }

        return Result()


class FakeExtractorFactory:
    def __init__(self, supported=True):
        self.supported = supported
        self.called = 0

    def is_supported(self, doc_type):
        return self.supported

    def create(self, doc_type):
        self.called += 1
        return FakeExtractor()


def _make_text_doc(tmp_path: Path) -> DiscoveredDocument:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    doc_path = input_dir / "doc.txt"
    doc_path.write_text("sample content", encoding="utf-8")
    return DiscoveredDocument(
        doc_id="doc_001",
        original_filename="doc.txt",
        source_type="text",
        source_path=doc_path,
        file_md5="deadbeefdeadbeef",
        content="sample content",
        needs_ingestion=False,
    )


def test_process_claim_uses_classifier_factory(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    doc = _make_text_doc(tmp_path)
    claim = DiscoveredClaim(
        claim_id="claim_001",
        source_path=tmp_path,
        documents=[doc],
    )

    classifier = FakeClassifier()
    classifier_factory = FakeClassifierFactory(classifier)
    extractor_factory = FakeExtractorFactory(supported=False)
    providers = PipelineProviders(
        classifier_factory=classifier_factory,
        extractor_factory=extractor_factory,
    )

    result = process_claim(
        claim=claim,
        output_base=output_dir,
        classifier=None,
        run_id="run_test_001",
        force=True,
        stage_config=StageConfig(stages=[PipelineStage.INGEST, PipelineStage.CLASSIFY]),
        providers=providers,
    )

    assert classifier_factory.called == 1
    assert result.status == "success"


def test_process_document_uses_extractor_factory(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    doc = _make_text_doc(tmp_path)
    claim_id = "claim_002"
    run_id = "run_test_002"

    doc_paths, _, _ = create_doc_structure(output_dir, claim_id, doc.doc_id, run_id)
    run_paths = get_run_paths(get_claim_paths(output_dir, claim_id), run_id)

    classifier = FakeClassifier()
    extractor_factory = FakeExtractorFactory(supported=True)
    providers = PipelineProviders(extractor_factory=extractor_factory)

    result = process_document(
        doc=doc,
        claim_id=claim_id,
        doc_paths=doc_paths,
        run_paths=run_paths,
        classifier=classifier,
        run_id=run_id,
        providers=providers,
    )

    assert extractor_factory.called == 1
    assert result.extraction_path is not None
