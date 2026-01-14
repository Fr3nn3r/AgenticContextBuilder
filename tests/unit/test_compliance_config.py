"""Unit tests for compliance storage configuration.

Tests:
- Config validation
- Default values
- Backend validation
- Environment variable loading
- Path conversion
"""

import os
from pathlib import Path
from unittest import mock

import pytest
from pydantic import ValidationError

from context_builder.services.compliance.config import (
    ComplianceStorageConfig,
    StorageBackendType,
)


class TestStorageBackendType:
    """Tests for StorageBackendType enum."""

    def test_file_backend_value(self):
        """FILE backend has correct string value."""
        assert StorageBackendType.FILE.value == "file"

    def test_encrypted_backend_value(self):
        """ENCRYPTED_FILE backend has correct string value."""
        assert StorageBackendType.ENCRYPTED_FILE.value == "encrypted_file"

    def test_s3_backend_value(self):
        """S3 backend has correct string value."""
        assert StorageBackendType.S3.value == "s3"

    def test_database_backend_value(self):
        """DATABASE backend has correct string value."""
        assert StorageBackendType.DATABASE.value == "database"

    def test_backend_from_string(self):
        """Backend type can be created from string value."""
        assert StorageBackendType("file") == StorageBackendType.FILE
        assert StorageBackendType("encrypted_file") == StorageBackendType.ENCRYPTED_FILE


class TestComplianceStorageConfigDefaults:
    """Tests for config default values."""

    def test_default_backend_type(self):
        """Default backend type is FILE."""
        config = ComplianceStorageConfig()
        assert config.backend_type == StorageBackendType.FILE

    def test_default_storage_dir(self):
        """Default storage dir is output/logs."""
        config = ComplianceStorageConfig()
        assert config.storage_dir == Path("output/logs")

    def test_default_encryption_key_path(self):
        """Default encryption key path is None."""
        config = ComplianceStorageConfig()
        assert config.encryption_key_path is None

    def test_default_encryption_algorithm(self):
        """Default encryption algorithm is AES-256-GCM."""
        config = ComplianceStorageConfig()
        assert config.encryption_algorithm == "AES-256-GCM"

    def test_default_s3_options(self):
        """Default S3 options are None."""
        config = ComplianceStorageConfig()
        assert config.s3_bucket is None
        assert config.s3_prefix is None
        assert config.s3_region is None

    def test_default_database_url(self):
        """Default database URL is None."""
        config = ComplianceStorageConfig()
        assert config.database_url is None


class TestComplianceStorageConfigValidation:
    """Tests for config validation."""

    def test_accepts_file_backend(self):
        """Config accepts FILE backend type."""
        config = ComplianceStorageConfig(backend_type=StorageBackendType.FILE)
        assert config.backend_type == StorageBackendType.FILE

    def test_accepts_string_backend_type(self):
        """Config accepts string value for backend type."""
        config = ComplianceStorageConfig(backend_type="file")
        assert config.backend_type == StorageBackendType.FILE

    def test_rejects_invalid_backend_type(self):
        """Config rejects invalid backend type."""
        with pytest.raises(ValidationError):
            ComplianceStorageConfig(backend_type="invalid")

    def test_converts_string_storage_dir(self):
        """Config converts string storage_dir to Path."""
        config = ComplianceStorageConfig(storage_dir="custom/path")
        assert config.storage_dir == Path("custom/path")
        assert isinstance(config.storage_dir, Path)

    def test_converts_string_encryption_key_path(self):
        """Config converts string encryption_key_path to Path."""
        config = ComplianceStorageConfig(encryption_key_path="keys/master.key")
        assert config.encryption_key_path == Path("keys/master.key")
        assert isinstance(config.encryption_key_path, Path)

    def test_accepts_path_storage_dir(self):
        """Config accepts Path for storage_dir."""
        config = ComplianceStorageConfig(storage_dir=Path("custom/path"))
        assert config.storage_dir == Path("custom/path")

    def test_forbids_extra_fields(self):
        """Config rejects unknown fields."""
        with pytest.raises(ValidationError):
            ComplianceStorageConfig(unknown_field="value")


class TestBackendValidation:
    """Tests for backend-specific validation."""

    def test_file_backend_no_extra_requirements(self):
        """FILE backend requires no extra options."""
        config = ComplianceStorageConfig(backend_type=StorageBackendType.FILE)
        config.validate_for_backend()  # Should not raise

    def test_encrypted_requires_key_path(self):
        """ENCRYPTED_FILE backend requires encryption_key_path."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE
        )
        with pytest.raises(ValueError, match="encryption_key_path is required"):
            config.validate_for_backend()

    def test_encrypted_valid_with_key_path(self):
        """ENCRYPTED_FILE backend validates with encryption_key_path."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.ENCRYPTED_FILE,
            encryption_key_path=Path("keys/master.key"),
        )
        config.validate_for_backend()  # Should not raise

    def test_s3_requires_bucket(self):
        """S3 backend requires s3_bucket."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.S3,
            s3_region="us-east-1",
        )
        with pytest.raises(ValueError, match="s3_bucket is required"):
            config.validate_for_backend()

    def test_s3_requires_region(self):
        """S3 backend requires s3_region."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.S3,
            s3_bucket="my-bucket",
        )
        with pytest.raises(ValueError, match="s3_region is required"):
            config.validate_for_backend()

    def test_s3_valid_with_all_required(self):
        """S3 backend validates with all required options."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.S3,
            s3_bucket="my-bucket",
            s3_region="us-east-1",
        )
        config.validate_for_backend()  # Should not raise

    def test_database_requires_url(self):
        """DATABASE backend requires database_url."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.DATABASE
        )
        with pytest.raises(ValueError, match="database_url is required"):
            config.validate_for_backend()

    def test_database_valid_with_url(self):
        """DATABASE backend validates with database_url."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.DATABASE,
            database_url="postgresql://localhost/compliance",
        )
        config.validate_for_backend()  # Should not raise


class TestEnvironmentLoading:
    """Tests for loading config from environment variables."""

    def test_from_env_defaults_when_empty(self):
        """from_env returns defaults when no env vars set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = ComplianceStorageConfig.from_env()
            assert config.backend_type == StorageBackendType.FILE
            assert config.storage_dir == Path("output/logs")

    def test_from_env_reads_backend_type(self):
        """from_env reads COMPLIANCE_BACKEND_TYPE."""
        with mock.patch.dict(os.environ, {"COMPLIANCE_BACKEND_TYPE": "file"}):
            config = ComplianceStorageConfig.from_env()
            assert config.backend_type == StorageBackendType.FILE

    def test_from_env_reads_storage_dir(self):
        """from_env reads COMPLIANCE_STORAGE_DIR."""
        with mock.patch.dict(os.environ, {"COMPLIANCE_STORAGE_DIR": "custom/logs"}):
            config = ComplianceStorageConfig.from_env()
            assert config.storage_dir == Path("custom/logs")

    def test_from_env_reads_encryption_key_path(self):
        """from_env reads COMPLIANCE_ENCRYPTION_KEY_PATH."""
        with mock.patch.dict(os.environ, {"COMPLIANCE_ENCRYPTION_KEY_PATH": "keys/key"}):
            config = ComplianceStorageConfig.from_env()
            assert config.encryption_key_path == Path("keys/key")

    def test_from_env_reads_s3_options(self):
        """from_env reads S3 configuration."""
        env_vars = {
            "COMPLIANCE_S3_BUCKET": "compliance-bucket",
            "COMPLIANCE_S3_PREFIX": "logs/",
            "COMPLIANCE_S3_REGION": "eu-west-1",
        }
        with mock.patch.dict(os.environ, env_vars):
            config = ComplianceStorageConfig.from_env()
            assert config.s3_bucket == "compliance-bucket"
            assert config.s3_prefix == "logs/"
            assert config.s3_region == "eu-west-1"

    def test_from_env_reads_database_url(self):
        """from_env reads COMPLIANCE_DATABASE_URL."""
        with mock.patch.dict(os.environ, {"COMPLIANCE_DATABASE_URL": "postgres://localhost"}):
            config = ComplianceStorageConfig.from_env()
            assert config.database_url == "postgres://localhost"

    def test_from_env_custom_prefix(self):
        """from_env supports custom prefix."""
        with mock.patch.dict(os.environ, {"CUSTOM_BACKEND_TYPE": "file"}):
            config = ComplianceStorageConfig.from_env(prefix="CUSTOM_")
            assert config.backend_type == StorageBackendType.FILE

    def test_from_env_case_insensitive_backend(self):
        """from_env handles uppercase backend type."""
        with mock.patch.dict(os.environ, {"COMPLIANCE_BACKEND_TYPE": "FILE"}):
            config = ComplianceStorageConfig.from_env()
            assert config.backend_type == StorageBackendType.FILE


class TestConfigSerialization:
    """Tests for config serialization."""

    def test_model_dump_includes_all_fields(self):
        """model_dump includes all fields."""
        config = ComplianceStorageConfig(
            backend_type=StorageBackendType.FILE,
            storage_dir=Path("custom/path"),
        )
        dumped = config.model_dump()
        assert "backend_type" in dumped
        assert "storage_dir" in dumped
        assert "encryption_key_path" in dumped

    def test_model_dump_json_compatible(self):
        """model_dump produces JSON-compatible output with mode='json'."""
        config = ComplianceStorageConfig(
            storage_dir=Path("custom/path"),
            encryption_key_path=Path("keys/key"),
        )
        dumped = config.model_dump(mode="json")
        # Path should be converted to string
        assert isinstance(dumped["storage_dir"], str)
