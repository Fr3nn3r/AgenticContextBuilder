"""Tests for storage facade and narrow protocols."""

from pathlib import Path

from context_builder.storage import FileStorage, StorageFacade, DocStore, RunStore, LabelStore


def test_storage_facade_wraps_filestorage(tmp_path: Path) -> None:
    storage = FileStorage(tmp_path)
    facade = StorageFacade.from_storage(storage)

    assert facade.doc_store is storage
    assert facade.run_store is storage
    assert facade.label_store is storage

    assert isinstance(facade.doc_store, DocStore)
    assert isinstance(facade.run_store, RunStore)
    assert isinstance(facade.label_store, LabelStore)
