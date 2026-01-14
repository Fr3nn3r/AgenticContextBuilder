"""Compliance storage subsystem.

This package provides interfaces and implementations for compliance-related
storage backends including decision ledgers and LLM audit logs.

Storage backends:
- File-based (JSONL with hash chains) - default
- Encrypted file-based (AES-256-GCM envelope encryption) - for sensitive data
- S3 - for cloud storage (future)
- Database - for queryable storage (future)

Usage:
    from context_builder.services.compliance import (
        DecisionStorage,
        LLMCallStorage,
        DecisionRecordFactory,
        FileDecisionStorage,
        ComplianceStorageConfig,
        ComplianceStorageFactory,
    )

    # Use interfaces for dependency injection
    def process_document(storage: DecisionStorage):
        ...

    # Use factory to create storage based on config
    config = ComplianceStorageConfig(storage_dir=Path("output/logs"))
    storage = ComplianceStorageFactory.create_decision_storage(config)

    # For encrypted storage:
    from context_builder.services.compliance import (
        EncryptedDecisionStorage,
        EnvelopeEncryptor,
    )
    encryptor = EnvelopeEncryptor(Path("keys/master.key"))
    storage = EncryptedDecisionStorage(Path("output/logs"), encryptor)
"""

from context_builder.services.compliance.config import (
    ComplianceStorageConfig,
    StorageBackendType,
)
from context_builder.services.compliance.crypto import (
    CryptoError,
    DecryptionError,
    EncryptionError,
    EnvelopeEncryptor,
    KeyLoadError,
    generate_key,
    generate_key_file,
)
from context_builder.services.compliance.encrypted import (
    EncryptedDecisionAppender,
    EncryptedDecisionReader,
    EncryptedDecisionStorage,
    EncryptedDecisionVerifier,
    EncryptedLLMCallReader,
    EncryptedLLMCallSink,
    EncryptedLLMCallStorage,
)
from context_builder.services.compliance.factories import DecisionRecordFactory
from context_builder.services.compliance.file import (
    GENESIS_HASH,
    FileDecisionAppender,
    FileDecisionReader,
    FileDecisionStorage,
    FileDecisionVerifier,
    FileLLMCallReader,
    FileLLMCallSink,
    FileLLMCallStorage,
)
from context_builder.services.compliance.interfaces import (
    DecisionAppender,
    DecisionQuery,
    DecisionReader,
    DecisionStorage,
    DecisionVerifier,
    LLMCallReader,
    LLMCallSink,
    LLMCallStorage,
)
from context_builder.services.compliance.storage_factory import ComplianceStorageFactory

__all__ = [
    # Config
    "ComplianceStorageConfig",
    "StorageBackendType",
    # Factory
    "ComplianceStorageFactory",
    # Crypto
    "EnvelopeEncryptor",
    "CryptoError",
    "KeyLoadError",
    "EncryptionError",
    "DecryptionError",
    "generate_key",
    "generate_key_file",
    # Protocols
    "DecisionAppender",
    "DecisionReader",
    "DecisionVerifier",
    "DecisionStorage",
    "DecisionQuery",
    "LLMCallSink",
    "LLMCallReader",
    "LLMCallStorage",
    # Record factory
    "DecisionRecordFactory",
    # File backends - Decision
    "GENESIS_HASH",
    "FileDecisionAppender",
    "FileDecisionReader",
    "FileDecisionVerifier",
    "FileDecisionStorage",
    # File backends - LLM
    "FileLLMCallSink",
    "FileLLMCallReader",
    "FileLLMCallStorage",
    # Encrypted backends - Decision
    "EncryptedDecisionAppender",
    "EncryptedDecisionReader",
    "EncryptedDecisionVerifier",
    "EncryptedDecisionStorage",
    # Encrypted backends - LLM
    "EncryptedLLMCallSink",
    "EncryptedLLMCallReader",
    "EncryptedLLMCallStorage",
]
