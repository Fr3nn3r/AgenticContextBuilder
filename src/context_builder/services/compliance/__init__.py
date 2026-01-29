"""Compliance storage subsystem.

This package provides interfaces and implementations for compliance-related
storage backends including decision ledgers and LLM audit logs.

Storage backends:
- File-based (JSONL with hash chains) - default
- Encrypted file-based (AES-256-GCM envelope encryption) - for sensitive data
- S3 - for cloud storage (future)
- Database - for queryable storage (future)

Note: Crypto and encrypted backend imports are lazy-loaded to avoid importing
the `cryptography` library at module load time. This prevents issues with
uvicorn's --reload on Windows (spawn-based reload hangs with OpenSSL bindings).

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

    # For encrypted storage (imports cryptography when accessed):
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
# Note: crypto and encrypted modules are NOT imported here to avoid
# loading the cryptography library at module level. They are available
# via __getattr__ for lazy loading when actually needed.
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
    NullLLMCallSink,
    NullLLMCallStorage,
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


# Lazy-loaded crypto symbols (to avoid importing cryptography at module level)
_CRYPTO_SYMBOLS = {
    "CryptoError",
    "DecryptionError",
    "EncryptionError",
    "EnvelopeEncryptor",
    "KeyLoadError",
    "generate_key",
    "generate_key_file",
}

# Lazy-loaded encrypted backend symbols
_ENCRYPTED_SYMBOLS = {
    "EncryptedDecisionAppender",
    "EncryptedDecisionReader",
    "EncryptedDecisionStorage",
    "EncryptedDecisionVerifier",
    "EncryptedLLMCallReader",
    "EncryptedLLMCallSink",
    "EncryptedLLMCallStorage",
}


def __getattr__(name: str):
    """Lazy-load crypto and encrypted modules to avoid importing cryptography at startup."""
    if name in _CRYPTO_SYMBOLS:
        from context_builder.services.compliance import crypto
        return getattr(crypto, name)
    if name in _ENCRYPTED_SYMBOLS:
        from context_builder.services.compliance import encrypted
        return getattr(encrypted, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
    # Null backends - LLM (for disabling logging)
    "NullLLMCallSink",
    "NullLLMCallStorage",
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
