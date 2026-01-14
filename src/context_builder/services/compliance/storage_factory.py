"""Factory for creating compliance storage implementations.

This module provides the ComplianceStorageFactory which creates the appropriate
storage backend implementations based on configuration.

Note: Encrypted backend imports are lazy-loaded to avoid importing the
`cryptography` library at module load time. This prevents issues with
uvicorn's --reload on Windows, where the spawn-based reload mechanism
can hang when cryptography's OpenSSL bindings are imported during process spawn.
"""

from typing import TYPE_CHECKING, Tuple

from context_builder.services.compliance.config import (
    ComplianceStorageConfig,
    StorageBackendType,
)
from context_builder.services.compliance.file import (
    FileDecisionStorage,
    FileLLMCallStorage,
)
from context_builder.services.compliance.interfaces import (
    DecisionStorage,
    LLMCallStorage,
)

# Type hints only - not imported at runtime
if TYPE_CHECKING:
    from context_builder.services.compliance.crypto import EnvelopeEncryptor
    from context_builder.services.compliance.encrypted import (
        EncryptedDecisionStorage,
        EncryptedLLMCallStorage,
    )


class ComplianceStorageFactory:
    """Factory for creating storage implementations based on config.

    This factory creates the appropriate DecisionStorage and LLMCallStorage
    implementations based on the provided configuration.

    Example:
        >>> config = ComplianceStorageConfig(
        ...     backend_type=StorageBackendType.FILE,
        ...     storage_dir=Path("output/logs"),
        ... )
        >>> decision_storage = ComplianceStorageFactory.create_decision_storage(config)
        >>> llm_storage = ComplianceStorageFactory.create_llm_storage(config)
    """

    @staticmethod
    def create_decision_storage(config: ComplianceStorageConfig) -> DecisionStorage:
        """Create a DecisionStorage implementation based on config.

        Args:
            config: Storage configuration

        Returns:
            DecisionStorage implementation

        Raises:
            ValueError: If the backend type is not supported
        """
        config.validate_for_backend()

        if config.backend_type == StorageBackendType.FILE:
            return FileDecisionStorage(config.storage_dir)

        if config.backend_type == StorageBackendType.ENCRYPTED_FILE:
            # Lazy import to avoid loading cryptography at module level
            # This prevents uvicorn --reload hang on Windows
            from context_builder.services.compliance.crypto import EnvelopeEncryptor
            from context_builder.services.compliance.encrypted import EncryptedDecisionStorage

            encryptor = EnvelopeEncryptor(config.encryption_key_path)
            return EncryptedDecisionStorage(config.storage_dir, encryptor)

        if config.backend_type == StorageBackendType.S3:
            raise ValueError(
                f"S3 backend not yet implemented. "
                f"Use FILE backend or wait for future implementation."
            )

        if config.backend_type == StorageBackendType.DATABASE:
            raise ValueError(
                f"Database backend not yet implemented. "
                f"Use FILE backend or wait for future implementation."
            )

        raise ValueError(f"Unsupported backend type: {config.backend_type}")

    @staticmethod
    def create_llm_storage(config: ComplianceStorageConfig) -> LLMCallStorage:
        """Create an LLMCallStorage implementation based on config.

        Args:
            config: Storage configuration

        Returns:
            LLMCallStorage implementation

        Raises:
            ValueError: If the backend type is not supported
        """
        config.validate_for_backend()

        if config.backend_type == StorageBackendType.FILE:
            return FileLLMCallStorage(config.storage_dir)

        if config.backend_type == StorageBackendType.ENCRYPTED_FILE:
            # Lazy import to avoid loading cryptography at module level
            # This prevents uvicorn --reload hang on Windows
            from context_builder.services.compliance.crypto import EnvelopeEncryptor
            from context_builder.services.compliance.encrypted import EncryptedLLMCallStorage

            encryptor = EnvelopeEncryptor(config.encryption_key_path)
            return EncryptedLLMCallStorage(config.storage_dir, encryptor)

        if config.backend_type == StorageBackendType.S3:
            raise ValueError(
                f"S3 backend not yet implemented. "
                f"Use FILE backend or wait for future implementation."
            )

        if config.backend_type == StorageBackendType.DATABASE:
            raise ValueError(
                f"Database backend not yet implemented. "
                f"Use FILE backend or wait for future implementation."
            )

        raise ValueError(f"Unsupported backend type: {config.backend_type}")

    @staticmethod
    def create_all(
        config: ComplianceStorageConfig,
    ) -> Tuple[DecisionStorage, LLMCallStorage]:
        """Create both DecisionStorage and LLMCallStorage implementations.

        Args:
            config: Storage configuration

        Returns:
            Tuple of (DecisionStorage, LLMCallStorage) implementations

        Raises:
            ValueError: If the backend type is not supported
        """
        return (
            ComplianceStorageFactory.create_decision_storage(config),
            ComplianceStorageFactory.create_llm_storage(config),
        )
