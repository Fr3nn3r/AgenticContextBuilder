"""Contract tests for FileLLMCallStorage.

Applies the LLMCallStorageContractTests to the file-based implementation.
"""

from pathlib import Path

import pytest

from context_builder.services.compliance import FileLLMCallStorage
from context_builder.services.compliance.interfaces import LLMCallStorage
from tests.contract.llm_storage_contract import LLMCallStorageContractTests


class TestFileLLMCallStorageContract(LLMCallStorageContractTests):
    """Apply contract tests to FileLLMCallStorage."""

    def create_storage(self, tmp_path: Path) -> LLMCallStorage:
        """Create a FileLLMCallStorage instance."""
        return FileLLMCallStorage(tmp_path)
