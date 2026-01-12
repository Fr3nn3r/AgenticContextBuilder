"""Facade for accessing narrow storage interfaces."""

from __future__ import annotations

from dataclasses import dataclass

from .protocol import DocStore, LabelStore, RunStore
from .filesystem import FileStorage


@dataclass(frozen=True)
class StorageFacade:
    """Bundle of narrow store interfaces for API services."""

    doc_store: DocStore
    label_store: LabelStore
    run_store: RunStore

    @classmethod
    def from_storage(cls, storage: FileStorage) -> "StorageFacade":
        return cls(doc_store=storage, label_store=storage, run_store=storage)
