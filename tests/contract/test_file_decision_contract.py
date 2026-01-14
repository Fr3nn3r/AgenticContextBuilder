"""Contract tests for FileDecisionStorage.

Applies the DecisionStorageContractTests to the file-based implementation.
"""

from pathlib import Path

import pytest

from context_builder.services.compliance import FileDecisionStorage
from context_builder.services.compliance.interfaces import DecisionStorage
from tests.contract.decision_storage_contract import DecisionStorageContractTests


class TestFileDecisionStorageContract(DecisionStorageContractTests):
    """Apply contract tests to FileDecisionStorage."""

    def create_storage(self, tmp_path: Path) -> DecisionStorage:
        """Create a FileDecisionStorage instance."""
        return FileDecisionStorage(tmp_path)
