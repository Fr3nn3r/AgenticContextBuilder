"""Contract tests for EncryptedDecisionStorage.

Applies the DecisionStorageContractTests to the encrypted implementation.
"""

from pathlib import Path

import pytest

from context_builder.services.compliance import (
    EncryptedDecisionStorage,
    EnvelopeEncryptor,
    generate_key,
)
from context_builder.services.compliance.interfaces import DecisionStorage
from tests.contract.decision_storage_contract import DecisionStorageContractTests


class TestEncryptedDecisionStorageContract(DecisionStorageContractTests):
    """Apply contract tests to EncryptedDecisionStorage."""

    @pytest.fixture
    def encryptor(self) -> EnvelopeEncryptor:
        """Create a test encryptor with a fresh key."""
        return EnvelopeEncryptor(generate_key())

    def create_storage(self, tmp_path: Path) -> DecisionStorage:
        """Create an EncryptedDecisionStorage instance.

        Note: This method needs the encryptor, so we override the fixture.
        """
        # This won't work directly because we need the encryptor
        # Override the storage fixture instead
        raise NotImplementedError("Use storage fixture directly")

    @pytest.fixture
    def storage(self, tmp_path: Path, encryptor: EnvelopeEncryptor) -> DecisionStorage:
        """Create storage with encryptor dependency."""
        return EncryptedDecisionStorage(tmp_path, encryptor)
