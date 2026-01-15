"""PII Vault package for compliance-grade PII tokenization and storage.

This package provides:
- PIIConfigLoader: Load and match PII field patterns from pii_config.yaml
- PIITokenizer: Tokenize extraction results, replacing PII with vault references
- EncryptedPIIVaultStorage: Encrypted storage for PII with crypto-shred capability

Usage:
    from context_builder.services.compliance.pii import (
        PIIConfigLoader,
        PIITokenizer,
        EncryptedPIIVaultStorage,
    )

    # Load PII configuration
    config = PIIConfigLoader.load()

    # Create vault for a claim
    vault = EncryptedPIIVaultStorage(storage_dir, claim_id)

    # Tokenize extraction result
    tokenizer = PIITokenizer(config, vault)
    result = tokenizer.tokenize(extraction_result, run_id)

Note: EncryptedPIIVaultStorage requires pycryptodome for encryption.
It is imported lazily to avoid import errors when crypto is not needed.
"""

from context_builder.services.compliance.pii.config_loader import PIIConfigLoader
from context_builder.services.compliance.pii.tokenizer import PIITokenizer


def __getattr__(name: str):
    """Lazy load EncryptedPIIVaultStorage to avoid pycryptodome import at module level."""
    if name == "EncryptedPIIVaultStorage":
        from context_builder.services.compliance.pii.vault_storage import EncryptedPIIVaultStorage
        return EncryptedPIIVaultStorage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PIIConfigLoader",
    "PIITokenizer",
    "EncryptedPIIVaultStorage",
]
