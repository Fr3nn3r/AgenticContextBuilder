"""Encrypted compliance storage backends.

This package provides encrypted implementations of the compliance storage
interfaces using envelope encryption (AES-256-GCM).

Features:
- Each record encrypted with unique Data Encryption Key (DEK)
- DEK encrypted with Key Encryption Key (KEK)
- Hash chain computed over plaintext (preserves verification capability)
- Authenticated encryption prevents tampering

Usage:
    from context_builder.services.compliance.encrypted import (
        EncryptedDecisionStorage,
        EncryptedLLMCallStorage,
    )
    from context_builder.services.compliance.crypto import EnvelopeEncryptor

    encryptor = EnvelopeEncryptor(Path("keys/master.key"))
    storage = EncryptedDecisionStorage(Path("output/logs"), encryptor)
"""

from context_builder.services.compliance.encrypted.decision_storage import (
    EncryptedDecisionAppender,
    EncryptedDecisionReader,
    EncryptedDecisionStorage,
    EncryptedDecisionVerifier,
)
from context_builder.services.compliance.encrypted.llm_storage import (
    EncryptedLLMCallReader,
    EncryptedLLMCallSink,
    EncryptedLLMCallStorage,
)

__all__ = [
    # Decision storage
    "EncryptedDecisionAppender",
    "EncryptedDecisionReader",
    "EncryptedDecisionVerifier",
    "EncryptedDecisionStorage",
    # LLM storage
    "EncryptedLLMCallSink",
    "EncryptedLLMCallReader",
    "EncryptedLLMCallStorage",
]
