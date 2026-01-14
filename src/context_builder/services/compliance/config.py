"""Configuration for compliance storage backends.

This module provides configuration models for selecting and configuring
different compliance storage implementations (file, encrypted, S3, database).
"""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator


class StorageBackendType(str, Enum):
    """Supported storage backend types."""

    FILE = "file"
    ENCRYPTED_FILE = "encrypted_file"
    S3 = "s3"  # Future
    DATABASE = "database"  # Future


class ComplianceStorageConfig(BaseModel):
    """Configuration for compliance storage backends.

    Attributes:
        backend_type: The storage backend to use (file, encrypted_file, etc.)
        storage_dir: Base directory for file-based storage
        encryption_key_path: Path to encryption key (for encrypted backend)
        encryption_algorithm: Encryption algorithm to use
        s3_bucket: S3 bucket name (for S3 backend)
        s3_prefix: Key prefix in S3 bucket
        s3_region: AWS region for S3
        database_url: Database connection URL (for database backend)

    Example:
        >>> config = ComplianceStorageConfig(
        ...     backend_type=StorageBackendType.FILE,
        ...     storage_dir=Path("output/logs"),
        ... )
    """

    backend_type: StorageBackendType = StorageBackendType.FILE
    storage_dir: Path = Path("output/logs")

    # Encrypted backend options (Phase 5)
    encryption_key_path: Optional[Path] = None
    encryption_algorithm: str = "AES-256-GCM"

    # S3 backend options (future)
    s3_bucket: Optional[str] = None
    s3_prefix: Optional[str] = None
    s3_region: Optional[str] = None

    # Database backend options (future)
    database_url: Optional[str] = None

    model_config = {"extra": "forbid"}

    @field_validator("storage_dir", mode="before")
    @classmethod
    def convert_storage_dir(cls, v):
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v

    @field_validator("encryption_key_path", mode="before")
    @classmethod
    def convert_encryption_key_path(cls, v):
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v

    def validate_for_backend(self) -> None:
        """Validate that required options are set for the selected backend.

        Raises:
            ValueError: If required options for the backend are missing.
        """
        if self.backend_type == StorageBackendType.ENCRYPTED_FILE:
            if not self.encryption_key_path:
                raise ValueError(
                    "encryption_key_path is required for encrypted_file backend"
                )

        if self.backend_type == StorageBackendType.S3:
            if not self.s3_bucket:
                raise ValueError("s3_bucket is required for S3 backend")
            if not self.s3_region:
                raise ValueError("s3_region is required for S3 backend")

        if self.backend_type == StorageBackendType.DATABASE:
            if not self.database_url:
                raise ValueError("database_url is required for database backend")

    @classmethod
    def from_env(cls, prefix: str = "COMPLIANCE_") -> "ComplianceStorageConfig":
        """Create config from environment variables.

        Environment variables:
            {prefix}BACKEND_TYPE: Storage backend type
            {prefix}STORAGE_DIR: Base storage directory
            {prefix}ENCRYPTION_KEY_PATH: Path to encryption key
            {prefix}S3_BUCKET: S3 bucket name
            {prefix}S3_PREFIX: S3 key prefix
            {prefix}S3_REGION: AWS region
            {prefix}DATABASE_URL: Database connection URL

        Args:
            prefix: Environment variable prefix (default: COMPLIANCE_)

        Returns:
            ComplianceStorageConfig with values from environment
        """
        import os

        kwargs = {}

        backend_type = os.getenv(f"{prefix}BACKEND_TYPE")
        if backend_type:
            kwargs["backend_type"] = StorageBackendType(backend_type.lower())

        storage_dir = os.getenv(f"{prefix}STORAGE_DIR")
        if storage_dir:
            kwargs["storage_dir"] = Path(storage_dir)

        encryption_key_path = os.getenv(f"{prefix}ENCRYPTION_KEY_PATH")
        if encryption_key_path:
            kwargs["encryption_key_path"] = Path(encryption_key_path)

        s3_bucket = os.getenv(f"{prefix}S3_BUCKET")
        if s3_bucket:
            kwargs["s3_bucket"] = s3_bucket

        s3_prefix = os.getenv(f"{prefix}S3_PREFIX")
        if s3_prefix:
            kwargs["s3_prefix"] = s3_prefix

        s3_region = os.getenv(f"{prefix}S3_REGION")
        if s3_region:
            kwargs["s3_region"] = s3_region

        database_url = os.getenv(f"{prefix}DATABASE_URL")
        if database_url:
            kwargs["database_url"] = database_url

        return cls(**kwargs)
