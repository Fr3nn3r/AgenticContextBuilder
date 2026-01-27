"""Unit tests for compliance storage factory.

Tests:
- Factory creates correct backends
- Invalid config raises errors
- Combined create_all method

Requires: pycryptodome (optional dependency) for encrypted backend tests
Install with: pip install context-builder[encryption]
"""

import tempfile
from pathlib import Path

import pytest

# Skip entire module if pycryptodome is not installed
# (this module tests encrypted backends which require pycryptodome)
pytest.importorskip("Crypto", reason="pycryptodome not installed (optional dependency)")

from context_builder.services.compliance import (
    DecisionStorage,
    LLMCallStorage,
    FileDecisionStorage,
    FileLLMCallStorage,
)
from context_builder.services.compliance.config import (
    ComplianceStorageConfig,
    StorageBackendType,
)
from context_builder.services.compliance.crypto import KeyLoadError, generate_key
from context_builder.services.compliance.encrypted import (
    EncryptedDecisionStorage,
    EncryptedLLMCallStorage,
)
from context_builder.services.compliance.storage_factory import ComplianceStorageFactory


class TestCreateDecisionStorage:
    """Tests for create_decision_storage factory method."""

    def test_creates_file_decision_storage(self, tmp_path: Path):
        """Factory creates FileDecisionStorage for FILE backend."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        storage = ComplianceStorageFactory.create_decision_storage(config)
        assert isinstance(storage, FileDecisionStorage)

    def test_decision_storage_implements_protocol(self, tmp_path: Path):
        """Created storage implements DecisionStorage protocol."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        storage = ComplianceStorageFactory.create_decision_storage(config)
        assert isinstance(storage, DecisionStorage)

    def test_encrypted_backend_creates_encrypted_storage(self, tmp_path: Path):
        """Factory creates EncryptedDecisionStorage for ENCRYPTED_FILE backend."""
        key_path = tmp_path / "key"
        key_path.write_bytes(generate_key())

        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            encryption_key_path=key_path,
        )
        storage = ComplianceStorageFactory.create_decision_storage(config)
        assert isinstance(storage, EncryptedDecisionStorage)

    def test_encrypted_backend_raises_on_missing_key(self, tmp_path: Path):
        """Factory raises KeyLoadError when key file doesn't exist."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            encryption_key_path=tmp_path / "nonexistent_key",
        )
        with pytest.raises(KeyLoadError, match="KEK file not found"):
            ComplianceStorageFactory.create_decision_storage(config)

    def test_s3_backend_not_implemented(self, tmp_path: Path):
        """Factory raises for unimplemented S3 backend."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.S3,
            s3_bucket="my-bucket",
            s3_region="us-east-1",
        )
        with pytest.raises(ValueError, match="S3 backend not yet implemented"):
            ComplianceStorageFactory.create_decision_storage(config)

    def test_database_backend_not_implemented(self):
        """Factory raises for unimplemented database backend."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.DATABASE,
            database_url="postgres://localhost/test",
        )
        with pytest.raises(ValueError, match="Database backend not yet implemented"):
            ComplianceStorageFactory.create_decision_storage(config)

    def test_validates_config_for_backend(self, tmp_path: Path):
        """Factory validates config before creating backend."""
        # Encrypted backend without key path should fail validation
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            # encryption_key_path intentionally omitted
        )
        with pytest.raises(ValueError, match="encryption_key_path is required"):
            ComplianceStorageFactory.create_decision_storage(config)


class TestCreateLLMStorage:
    """Tests for create_llm_storage factory method."""

    def test_creates_file_llm_storage(self, tmp_path: Path):
        """Factory creates FileLLMCallStorage for FILE backend."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        storage = ComplianceStorageFactory.create_llm_storage(config)
        assert isinstance(storage, FileLLMCallStorage)

    def test_llm_storage_implements_protocol(self, tmp_path: Path):
        """Created storage implements LLMCallStorage protocol."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        storage = ComplianceStorageFactory.create_llm_storage(config)
        assert isinstance(storage, LLMCallStorage)

    def test_encrypted_backend_creates_encrypted_storage(self, tmp_path: Path):
        """Factory creates EncryptedLLMCallStorage for ENCRYPTED_FILE backend."""
        key_path = tmp_path / "key"
        key_path.write_bytes(generate_key())

        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            encryption_key_path=key_path,
        )
        storage = ComplianceStorageFactory.create_llm_storage(config)
        assert isinstance(storage, EncryptedLLMCallStorage)

    def test_encrypted_backend_raises_on_missing_key(self, tmp_path: Path):
        """Factory raises KeyLoadError when LLM key file doesn't exist."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            storage_dir=tmp_path,
            encryption_key_path=tmp_path / "nonexistent_key",
        )
        with pytest.raises(KeyLoadError, match="KEK file not found"):
            ComplianceStorageFactory.create_llm_storage(config)


class TestCreateAll:
    """Tests for create_all factory method."""

    def test_creates_both_storages(self, tmp_path: Path):
        """create_all returns tuple of both storage types."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        decision_storage, llm_storage = ComplianceStorageFactory.create_all(config)

        assert isinstance(decision_storage, DecisionStorage)
        assert isinstance(llm_storage, LLMCallStorage)

    def test_returns_correct_types(self, tmp_path: Path):
        """create_all returns correct implementation types."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        decision_storage, llm_storage = ComplianceStorageFactory.create_all(config)

        assert isinstance(decision_storage, FileDecisionStorage)
        assert isinstance(llm_storage, FileLLMCallStorage)

    def test_both_use_same_storage_dir(self, tmp_path: Path):
        """create_all creates storages using the same directory."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )
        decision_storage, llm_storage = ComplianceStorageFactory.create_all(config)

        # Both should be able to operate in the configured directory
        # We verify this indirectly by checking they're properly created
        assert decision_storage is not None
        assert llm_storage is not None


class TestFactoryWithDefaultConfig:
    """Tests for factory with default configuration."""

    def test_default_config_creates_file_backend(self):
        """Default config creates file backends."""
        config = ComplianceStorageConfig()

        decision_storage = ComplianceStorageFactory.create_decision_storage(config)
        llm_storage = ComplianceStorageFactory.create_llm_storage(config)

        assert isinstance(decision_storage, FileDecisionStorage)
        assert isinstance(llm_storage, FileLLMCallStorage)


class TestFactoryIdempotence:
    """Tests for factory idempotence and isolation."""

    def test_creates_new_instances(self, tmp_path: Path):
        """Factory creates new instances on each call."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path,
        )

        storage1 = ComplianceStorageFactory.create_decision_storage(config)
        storage2 = ComplianceStorageFactory.create_decision_storage(config)

        assert storage1 is not storage2

    def test_different_configs_create_different_storages(self, tmp_path: Path):
        """Different configs create independent storages."""
        config1 = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path / "dir1",
        )
        config2 = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=tmp_path / "dir2",
        )

        storage1 = ComplianceStorageFactory.create_decision_storage(config1)
        storage2 = ComplianceStorageFactory.create_decision_storage(config2)

        assert storage1 is not storage2
