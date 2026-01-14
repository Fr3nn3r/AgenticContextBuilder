import json
from pathlib import Path

from context_builder.pipeline.eval import evaluate_run
from context_builder.storage.truth_store import TruthStore


def test_evaluate_run_counts_fields(tmp_path: Path) -> None:
    run_id = "run_20260113_000000_test"
    claim_dir = tmp_path / "claims" / "claim1"
    doc_root = claim_dir / "docs" / "doc1"
    extraction_dir = claim_dir / "runs" / run_id / "extraction"

    (doc_root / "meta").mkdir(parents=True)
    extraction_dir.mkdir(parents=True)

    doc_json = {
        "doc_id": "doc1",
        "claim_id": "claim1",
        "original_filename": "doc1.pdf",
        "file_md5": "abc123def4567890abc123def4567890",
        "content_md5": "def456abc1237890def456abc1237890",
    }
    (doc_root / "meta" / "doc.json").write_text(json.dumps(doc_json), encoding="utf-8")

    extraction = {
        "schema_version": "extraction_result_v1",
        "run": {"run_id": run_id, "input_hashes": {"file_md5": doc_json["file_md5"]}},
        "doc": {"doc_id": "doc1", "claim_id": "claim1", "doc_type": "invoice"},
        "fields": [
            {"name": "field_a", "value": "A", "normalized_value": "A"},
            {"name": "field_b", "value": None, "normalized_value": None},
            {"name": "field_c", "value": "C", "normalized_value": "C"},
        ],
    }
    (extraction_dir / "doc1.json").write_text(json.dumps(extraction), encoding="utf-8")

    truth_payload = {
        "schema_version": "label_v3",
        "doc_id": "doc1",
        "claim_id": "claim1",
        "review": {"reviewed_at": "2026-01-13T00:00:00Z", "reviewer": "", "notes": ""},
        "field_labels": [
            {"field_name": "field_a", "state": "LABELED", "truth_value": "A"},
            {"field_name": "field_b", "state": "LABELED", "truth_value": "B"},
            {"field_name": "field_c", "state": "UNVERIFIABLE", "unverifiable_reason": "cannot_verify"},
        ],
        "doc_labels": {"doc_type_correct": True},
        "input_hashes": {
            "file_md5": doc_json["file_md5"],
            "content_md5": doc_json["content_md5"],
        },
        "source_doc_ref": {
            "claim_id": "claim1",
            "doc_id": "doc1",
            "original_filename": "doc1.pdf",
        },
    }
    TruthStore(tmp_path).save_truth_by_file_md5(doc_json["file_md5"], truth_payload)

    summary = evaluate_run(tmp_path, run_id)

    assert summary["docs_total"] == 1
    assert summary["docs_evaluated"] == 1
    assert summary["fields_total"] == 3
    assert summary["fields_labeled"] == 2
    assert summary["correct"] == 1
    assert summary["missing"] == 1
    assert summary["unverifiable"] == 1

    eval_path = tmp_path / "runs" / run_id / "eval" / "doc1.json"
    assert eval_path.exists()
