"""File-based compliance storage implementations.

This package provides JSONL-based storage backends for compliance records
with SHA-256 hash chain linking for tamper evidence.
"""

from context_builder.services.compliance.file.decision_storage import (
    GENESIS_HASH,
    FileDecisionAppender,
    FileDecisionReader,
    FileDecisionStorage,
    FileDecisionVerifier,
)
from context_builder.services.compliance.file.llm_storage import (
    FileLLMCallReader,
    FileLLMCallSink,
    FileLLMCallStorage,
    NullLLMCallSink,
    NullLLMCallStorage,
)

__all__ = [
    # Decision storage
    "GENESIS_HASH",
    "FileDecisionAppender",
    "FileDecisionReader",
    "FileDecisionVerifier",
    "FileDecisionStorage",
    # LLM call storage
    "FileLLMCallSink",
    "FileLLMCallReader",
    "FileLLMCallStorage",
    # Null storage (for disabling logging)
    "NullLLMCallSink",
    "NullLLMCallStorage",
]
