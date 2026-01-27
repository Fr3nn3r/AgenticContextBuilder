"""Storage abstraction layer for document and run data access.

This module provides a unified interface for accessing documents, runs,
labels, and other data in the output folder structure.

Usage:
    from context_builder.storage import FileStorage

    storage = FileStorage(output_root=Path("output"))

    # List operations (use indexes for O(1) when available)
    claims = storage.list_claims()
    docs = storage.list_docs(claim_id)
    runs = storage.list_runs()

    # Document access
    doc = storage.get_doc(doc_id)
    text = storage.get_doc_text(doc_id)
    source_path = storage.get_doc_source_path(doc_id)

    # Run-scoped access
    extraction = storage.get_extraction(run_id, doc_id)
    run = storage.get_run(run_id)

    # Labels (document-scoped, run-independent)
    label = storage.get_label(doc_id)
    storage.save_label(doc_id, label_data)  # atomic write

    # Index status
    if storage.has_indexes():
        meta = storage.get_index_meta()
"""

from .protocol import Storage, DocStore, RunStore, LabelStore, PendingStore
from .filesystem import FileStorage
from .facade import StorageFacade
from .models import (
    ClaimRef,
    DocRef,
    DocBundle,
    DocText,
    RunRef,
    RunBundle,
    LabelSummary,
    RegistryMeta,
    SourceFileRef,
    ExtractionRef,
)
from .index_reader import IndexReader
from .index_builder import build_all_indexes
from .truth_store import TruthStore
from .claim_run import ClaimRunStorage
from .workspace_paths import (
    get_workspace_logs_dir,
    get_workspace_claims_dir,
    get_workspace_registry_dir,
    get_active_workspace_path,
    reset_workspace_cache,
)

__all__ = [
    # Protocol
    "Storage",
    "DocStore",
    "RunStore",
    "LabelStore",
    "PendingStore",
    # Implementation
    "FileStorage",
    "StorageFacade",
    # Models
    "ClaimRef",
    "DocRef",
    "DocBundle",
    "DocText",
    "RunRef",
    "RunBundle",
    "LabelSummary",
    "RegistryMeta",
    "SourceFileRef",
    "ExtractionRef",
    # Index utilities
    "IndexReader",
    "build_all_indexes",
    "TruthStore",
    # Claim runs
    "ClaimRunStorage",
    # Workspace paths
    "get_workspace_logs_dir",
    "get_workspace_claims_dir",
    "get_workspace_registry_dir",
    "get_active_workspace_path",
    "reset_workspace_cache",
]
