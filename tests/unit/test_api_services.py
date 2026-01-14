import json

from context_builder.api.services import ClaimsService, DocumentsService, InsightsService, LabelsService
from context_builder.storage.models import DocBundle, DocText, RunRef


class FakeStorage:
    def __init__(self, runs=None, doc_bundle=None, doc_text=None, extraction=None, label=None):
        self._runs = runs or []
        self._doc_bundle = doc_bundle
        self._doc_text = doc_text
        self._extraction = extraction
        self._label = label
        self.saved_label = None
        self.doc_store = self
        self.run_store = self
        self.label_store = self

    def list_runs(self):
        return self._runs

    def get_doc(self, doc_id):
        if self._doc_bundle and self._doc_bundle.doc_id == doc_id:
            return self._doc_bundle
        return None

    def get_doc_text(self, doc_id):
        if self._doc_text and self._doc_text.doc_id == doc_id:
            return self._doc_text
        return None

    def get_extraction(self, run_id, doc_id, claim_id=None):
        return self._extraction

    def get_label(self, doc_id):
        return self._label

    def get_doc_source_path(self, doc_id):
        return None

    def save_label(self, doc_id, label_data):
        self.saved_label = label_data


def test_claims_service_list_runs_reads_global_metadata(tmp_path):
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    run_id = "run_2026_01_01"
    run_dir = runs_dir / run_id
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"completed_at": "2026-01-01T01:02:03Z"}),
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps({"model": "gpt-4o", "claims_count": 2}),
        encoding="utf-8",
    )

    fake_storage = FakeStorage(runs=[RunRef(run_id=run_id, status="complete")])
    service = ClaimsService(claims_dir, storage_factory=lambda: fake_storage)

    runs = service.list_runs()

    assert runs == [
        {
            "run_id": run_id,
            "timestamp": "2026-01-01T01:02:03Z",
            "model": "gpt-4o",
            "claims_count": 2,
        }
    ]


def test_documents_service_get_doc_uses_storage(tmp_path):
    doc_root = tmp_path / "claims" / "claim123" / "docs" / "doc1"
    doc_root.mkdir(parents=True)
    source_dir = doc_root / "source"
    source_dir.mkdir()
    (source_dir / "sample.pdf").write_bytes(b"%PDF-1.4")

    doc_bundle = DocBundle(
        doc_id="doc1",
        claim_id="claim123",
        claim_folder="claim123",
        metadata={
            "original_filename": "file.pdf",
            "doc_type": "invoice",
            "language": "en",
        },
        doc_root=doc_root,
    )
    doc_text = DocText(doc_id="doc1", pages=[{"page": 1, "text": "hello"}])

    fake_storage = FakeStorage(
        doc_bundle=doc_bundle,
        doc_text=doc_text,
        extraction={"fields": []},
        label={"doc_labels": {}},
    )
    service = DocumentsService(tmp_path / "claims", storage_factory=lambda: fake_storage)

    payload = service.get_doc("doc1", run_id="run_1")

    assert payload.doc_id == "doc1"
    assert payload.claim_id == "claim123"
    assert payload.doc_type == "invoice"
    assert payload.has_pdf is True
    assert payload.has_image is False
    assert payload.extraction == {"fields": []}
    assert payload.labels == {"doc_labels": {}}


def test_labels_service_save_labels_writes_schema(tmp_path):
    doc_root = tmp_path / "claims" / "claim123" / "docs" / "doc1"
    doc_root.mkdir(parents=True)

    doc_bundle = DocBundle(
        doc_id="doc1",
        claim_id="claim123",
        claim_folder="claim123",
        metadata={
            "original_filename": "file.pdf",
            "file_md5": "abc123def4567890abc123def4567890",
            "content_md5": "def456abc1237890def456abc1237890",
        },
        doc_root=doc_root,
    )
    fake_storage = FakeStorage(doc_bundle=doc_bundle)
    service = LabelsService(storage_factory=lambda: fake_storage)

    result = service.save_labels(
        "doc1",
        reviewer="Ana",
        notes="ok",
        field_labels=[{"name": "amount", "state": "LABELED"}],
        doc_labels={"doc_type_correct": True},
    )

    assert result["status"] == "saved"
    assert fake_storage.saved_label["schema_version"] == "label_v3"
    assert fake_storage.saved_label["review"]["reviewer"] == "Ana"
    assert fake_storage.saved_label["doc_labels"]["doc_type_correct"] is True

    truth_path = (
        tmp_path
        / "registry"
        / "truth"
        / "abc123def4567890abc123def4567890"
        / "latest.json"
    )
    assert truth_path.exists()
    truth_data = json.loads(truth_path.read_text(encoding="utf-8"))
    assert truth_data["input_hashes"]["file_md5"] == "abc123def4567890abc123def4567890"


def test_insights_service_overview_uses_aggregator(monkeypatch, tmp_path):
    from context_builder.api import insights as insights_module

    class FakeAggregator:
        def __init__(self, data_dir, run_id=None):
            self.data_dir = data_dir

        def get_overview(self):
            return {"docs_total": 1}

    monkeypatch.setattr(insights_module, "InsightsAggregator", FakeAggregator)

    service = InsightsService(tmp_path)

    assert service.get_overview() == {"docs_total": 1}
