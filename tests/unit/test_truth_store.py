from pathlib import Path

from context_builder.storage.truth_store import TruthStore


def test_truth_store_save_and_get(tmp_path: Path) -> None:
    output_root = tmp_path
    (output_root / "claims").mkdir()
    store = TruthStore(output_root)

    payload = {"schema_version": "label_v3", "doc_id": "doc1"}
    file_md5 = "abc123def4567890abc123def4567890"

    store.save_truth_by_file_md5(file_md5, payload)
    loaded = store.get_truth_by_file_md5(file_md5)

    assert loaded == payload
