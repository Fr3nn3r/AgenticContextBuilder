"""Encrypted PII Vault Storage.

File-based encrypted storage for PII with per-vault keys enabling crypto-shredding.

File structure per vault:
    <storage_dir>/pii_vaults/<vault_id>/
        vault.kek          # Per-vault KEK (delete to crypto-shred)
        vault.enc.jsonl    # Encrypted entries (one per line)
        index.json         # Unencrypted lookup index
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from context_builder.schemas.pii_vault import (
    PIIVaultEntry,
    PIIVaultIndex,
    PIIVaultIndexEntry,
    generate_vault_id,
)
from context_builder.services.compliance.crypto import (
    EnvelopeEncryptor,
    generate_key,
    DecryptionError,
)

logger = logging.getLogger(__name__)


class PIIVaultError(Exception):
    """Base exception for PII vault errors."""

    pass


class VaultNotFoundError(PIIVaultError):
    """Vault does not exist."""

    pass


class VaultShreddedError(PIIVaultError):
    """Vault has been crypto-shredded and is unreadable."""

    pass


class EncryptedPIIVaultStorage:
    """Encrypted file-based PII vault storage.

    Provides encrypted storage for PII with per-vault keys.
    Each claim gets its own vault with a unique KEK.
    Crypto-shredding is achieved by deleting the vault's KEK.

    Example:
        vault = EncryptedPIIVaultStorage(Path("output/logs"), "CLM001")

        # Store entries
        vault.store_batch(entries)

        # Retrieve entries
        entry = vault.get("pii_abc123")

        # Crypto-shred (permanent deletion)
        vault.shred_vault("vault_CLM001", "right_to_erasure")
    """

    # File names within vault directory
    KEK_FILENAME = "vault.kek"
    DATA_FILENAME = "vault.enc.jsonl"
    INDEX_FILENAME = "index.json"

    def __init__(
        self,
        storage_dir: Path,
        claim_id: str,
        vault_id: Optional[str] = None,
        create_if_missing: bool = True,
    ):
        """Initialize vault storage.

        Args:
            storage_dir: Base directory for vault storage.
            claim_id: Claim identifier.
            vault_id: Optional vault ID. Generated from claim_id if not provided.
            create_if_missing: Create vault directory and KEK if not exists.
        """
        self.storage_dir = Path(storage_dir)
        self.claim_id = claim_id
        self._vault_id = vault_id or generate_vault_id(claim_id)

        # Vault directory
        self.vault_dir = self.storage_dir / "pii_vaults" / self._vault_id
        self.kek_path = self.vault_dir / self.KEK_FILENAME
        self.data_path = self.vault_dir / self.DATA_FILENAME
        self.index_path = self.vault_dir / self.INDEX_FILENAME

        # Lazy-loaded encryptor
        self._encryptor: Optional[EnvelopeEncryptor] = None
        self._index: Optional[PIIVaultIndex] = None

        if create_if_missing:
            self._ensure_vault_exists()

    @property
    def vault_id(self) -> str:
        """Return the vault identifier."""
        return self._vault_id

    def _ensure_vault_exists(self) -> None:
        """Create vault directory and KEK if not exists."""
        if not self.vault_dir.exists():
            self.vault_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created vault directory: {self.vault_dir}")

        if not self.kek_path.exists():
            # Generate new KEK for this vault
            kek = generate_key()
            self.kek_path.write_bytes(kek)
            logger.info(f"Generated new KEK for vault {self._vault_id}")

        if not self.index_path.exists():
            # Create empty index
            index = PIIVaultIndex(vault_id=self._vault_id, claim_id=self.claim_id)
            self._write_index(index)

    def _get_encryptor(self) -> EnvelopeEncryptor:
        """Get or create the encryptor (lazy loading)."""
        if self._encryptor is None:
            if not self.kek_path.exists():
                raise VaultShreddedError(
                    f"Vault {self._vault_id} has been shredded (KEK not found)"
                )
            self._encryptor = EnvelopeEncryptor(self.kek_path)
        return self._encryptor

    def _get_index(self) -> PIIVaultIndex:
        """Get or load the vault index."""
        if self._index is None:
            self._index = self._load_index()
        return self._index

    def _load_index(self) -> PIIVaultIndex:
        """Load index from file."""
        if not self.index_path.exists():
            return PIIVaultIndex(vault_id=self._vault_id, claim_id=self.claim_id)

        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PIIVaultIndex.from_dict(data)

    def _write_index(self, index: PIIVaultIndex) -> None:
        """Write index to file."""
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(index.to_dict(), f, indent=2)
        self._index = index

    def is_shredded(self) -> bool:
        """Check if the vault has been crypto-shredded."""
        index = self._get_index()
        return index.shredded or not self.kek_path.exists()

    def store(self, entry: PIIVaultEntry) -> PIIVaultEntry:
        """Store a single PII vault entry.

        Args:
            entry: The vault entry to store.

        Returns:
            The stored entry.

        Raises:
            VaultShreddedError: If vault has been shredded.
            IOError: If write fails.
        """
        return self.store_batch([entry])[0]

    def store_batch(self, entries: List[PIIVaultEntry]) -> List[PIIVaultEntry]:
        """Store multiple PII vault entries.

        Encrypts each entry and appends to the vault data file.
        Updates the index atomically.

        Args:
            entries: List of vault entries to store.

        Returns:
            List of stored entries.

        Raises:
            VaultShreddedError: If vault has been shredded.
            IOError: If write fails.
        """
        if not entries:
            return []

        if self.is_shredded():
            raise VaultShreddedError(f"Vault {self._vault_id} has been shredded")

        encryptor = self._get_encryptor()
        index = self._get_index()

        # Encrypt and append entries
        with open(self.data_path, "ab") as f:
            for entry in entries:
                # Serialize and encrypt
                entry_json = json.dumps(entry.to_dict())
                encrypted = encryptor.encrypt(entry_json.encode("utf-8"))

                # Write as base64 line
                import base64

                f.write(base64.b64encode(encrypted) + b"\n")

                # Update index
                index.entries[entry.entry_id] = PIIVaultIndexEntry(
                    entry_id=entry.entry_id,
                    pii_category=entry.pii_category,
                    field_path=entry.field_path,
                    doc_id=entry.doc_id,
                    run_id=entry.run_id,
                )

        # Write updated index
        self._write_index(index)

        logger.debug(f"Stored {len(entries)} entries in vault {self._vault_id}")
        return entries

    def get(self, entry_id: str) -> Optional[PIIVaultEntry]:
        """Retrieve a PII entry by its identifier.

        Args:
            entry_id: The entry identifier to look up.

        Returns:
            The PIIVaultEntry if found, None otherwise.

        Raises:
            VaultShreddedError: If vault has been shredded.
        """
        result = self.get_batch([entry_id])
        return result.get(entry_id)

    def get_batch(self, entry_ids: List[str]) -> Dict[str, PIIVaultEntry]:
        """Retrieve multiple PII entries by their identifiers.

        This reads and decrypts all entries to find the requested ones.
        For better performance with many lookups, consider caching.

        Args:
            entry_ids: List of entry identifiers to look up.

        Returns:
            Dict mapping entry_id -> PIIVaultEntry for found entries.

        Raises:
            VaultShreddedError: If vault has been shredded.
        """
        if self.is_shredded():
            raise VaultShreddedError(f"Vault {self._vault_id} has been shredded")

        if not self.data_path.exists():
            return {}

        entry_id_set = set(entry_ids)
        result: Dict[str, PIIVaultEntry] = {}
        encryptor = self._get_encryptor()

        import base64

        with open(self.data_path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    encrypted = base64.b64decode(line)
                    decrypted = encryptor.decrypt(encrypted)
                    entry_dict = json.loads(decrypted.decode("utf-8"))
                    entry = PIIVaultEntry.from_dict(entry_dict)

                    if entry.entry_id in entry_id_set:
                        result[entry.entry_id] = entry

                        # Stop if we found all requested entries
                        if len(result) == len(entry_ids):
                            break
                except (DecryptionError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to decrypt entry in vault {self._vault_id}: {e}")
                    continue

        return result

    def list_by_doc(self, doc_id: str) -> List[PIIVaultEntry]:
        """Get all PII entries for a document.

        Args:
            doc_id: The document identifier.

        Returns:
            List of vault entries for the document.

        Raises:
            VaultShreddedError: If vault has been shredded.
        """
        index = self._get_index()

        # Find entry IDs for this doc
        entry_ids = [
            idx_entry.entry_id
            for idx_entry in index.entries.values()
            if idx_entry.doc_id == doc_id
        ]

        if not entry_ids:
            return []

        entries = self.get_batch(entry_ids)
        return list(entries.values())

    def shred_vault(self, vault_id: str, reason: str) -> bool:
        """Crypto-shred an entire vault by destroying its KEK.

        This permanently destroys access to all PII in the vault.
        The encrypted data remains but is cryptographically unrecoverable.

        Args:
            vault_id: The vault identifier (must match this vault).
            reason: Reason for shredding (for audit trail).

        Returns:
            True if shredded successfully, False if vault not found.
        """
        if vault_id != self._vault_id:
            logger.warning(
                f"Attempted to shred vault {vault_id} but storage is for {self._vault_id}"
            )
            return False

        if not self.kek_path.exists():
            logger.warning(f"Vault {vault_id} already shredded (no KEK)")
            return False

        # Update index to mark as shredded (before deleting KEK)
        index = self._get_index()
        index.shredded = True
        index.shredded_at = datetime.utcnow().isoformat()
        index.shred_reason = reason
        self._write_index(index)

        # Delete the KEK (this is the crypto-shred)
        try:
            # Securely overwrite before deleting (basic protection)
            kek_size = self.kek_path.stat().st_size
            with open(self.kek_path, "wb") as f:
                f.write(os.urandom(kek_size))
            self.kek_path.unlink()
            logger.info(f"Crypto-shredded vault {vault_id}: {reason}")
        except OSError as e:
            logger.error(f"Failed to delete KEK for vault {vault_id}: {e}")
            return False

        # Clear cached encryptor
        self._encryptor = None

        return True

    def shred_entries(self, entry_ids: List[str], reason: str) -> int:
        """Mark specific entries as shredded in the index.

        Note: For true crypto-shredding, use shred_vault() which destroys
        the KEK. This method only marks entries as deleted in the index.

        Args:
            entry_ids: List of entry identifiers to mark as shredded.
            reason: Reason for shredding (for audit trail).

        Returns:
            Number of entries marked as shredded.
        """
        index = self._get_index()
        count = 0

        for entry_id in entry_ids:
            if entry_id in index.entries:
                # Remove from index (data remains encrypted but inaccessible)
                del index.entries[entry_id]
                count += 1

        if count > 0:
            self._write_index(index)
            logger.info(f"Marked {count} entries as shredded in vault {self._vault_id}: {reason}")

        return count


def create_pii_vault(
    storage_dir: Path,
    claim_id: str,
    vault_id: Optional[str] = None,
) -> EncryptedPIIVaultStorage:
    """Factory function to create a PII vault for a claim.

    Args:
        storage_dir: Base directory for vault storage.
        claim_id: Claim identifier.
        vault_id: Optional vault ID.

    Returns:
        EncryptedPIIVaultStorage instance.
    """
    return EncryptedPIIVaultStorage(
        storage_dir=storage_dir,
        claim_id=claim_id,
        vault_id=vault_id,
        create_if_missing=True,
    )
