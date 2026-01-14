"""Contract tests for EncryptedLLMCallStorage.

Applies the LLMCallStorageContractTests to the encrypted implementation.
"""

from pathlib import Path

import pytest

from context_builder.services.compliance import (
    EncryptedLLMCallStorage,
    EnvelopeEncryptor,
    generate_key,
)
from context_builder.services.compliance.interfaces import LLMCallStorage
from tests.contract.llm_storage_contract import LLMCallStorageContractTests


class TestEncryptedLLMCallStorageContract(LLMCallStorageContractTests):
    """Apply contract tests to EncryptedLLMCallStorage."""

    @pytest.fixture
    def encryptor(self) -> EnvelopeEncryptor:
        """Create a test encryptor with a fresh key."""
        return EnvelopeEncryptor(generate_key())

    def create_storage(self, tmp_path: Path) -> LLMCallStorage:
        """Create an EncryptedLLMCallStorage instance.

        Note: This method needs the encryptor, so we override the fixture.
        """
        # This won't work directly because we need the encryptor
        # Override the storage fixture instead
        raise NotImplementedError("Use storage fixture directly")

    @pytest.fixture
    def storage(self, tmp_path: Path, encryptor: EnvelopeEncryptor) -> LLMCallStorage:
        """Create storage with encryptor dependency."""
        return EncryptedLLMCallStorage(tmp_path, encryptor)
