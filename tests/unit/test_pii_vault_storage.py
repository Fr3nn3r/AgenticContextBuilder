"""Unit tests for PII vault storage.

Tests:
- Vault creation and initialization
- Storing and retrieving entries
- Batch operations
- Crypto-shredding
- Index management

Requires pycryptodome to be installed.
"""

from datetime import datetime
from pathlib import Path

import pytest

# Skip all tests in this module if pycryptodome is not installed
pytest.importorskip("Crypto", reason="pycryptodome not installed")

from context_builder.schemas.pii_vault import (
    PIIVaultEntry,
    PIIVaultIndex,
    generate_entry_id,
    generate_vault_id,
)
from context_builder.services.compliance.pii.vault_storage import (
    EncryptedPIIVaultStorage,
    VaultNotFoundError,
    VaultShreddedError,
    create_pii_vault,
)


@pytest.fixture
def storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    return tmp_path / "pii_vaults"


@pytest.fixture
def sample_entry() -> PIIVaultEntry:
    """Create a sample vault entry."""
    return PIIVaultEntry(
        entry_id=generate_entry_id(),
        vault_id="vault_CLM001",
        claim_id="CLM001",
        doc_id="DOC001",
        run_id="RUN001",
        pii_category="names",
        field_path="fields[0].value",
        redaction_strategy="reference",
        original_value="John Smith",
    )


class TestVaultCreation:
    """Tests for vault initialization."""

    def test_creates_vault_directory(self, storage_dir: Path):
        """Vault creates directory structure on init."""
        vault = EncryptedPIIVaultStorage(
            storage_dir=storage_dir,
            claim_id="CLM001",
            create_if_missing=True,
        )

        assert vault.vault_dir.exists()
        assert vault.kek_path.exists()
        assert vault.index_path.exists()

    def test_vault_id_generated(self, storage_dir: Path):
        """Vault ID is generated from claim ID."""
        vault = EncryptedPIIVaultStorage(
            storage_dir=storage_dir,
            claim_id="CLM001",
        )

        assert vault.vault_id == "vault_CLM001"

    def test_custom_vault_id(self, storage_dir: Path):
        """Custom vault ID can be specified."""
        vault = EncryptedPIIVaultStorage(
            storage_dir=storage_dir,
            claim_id="CLM001",
            vault_id="custom_vault_123",
        )

        assert vault.vault_id == "custom_vault_123"

    def test_kek_is_32_bytes(self, storage_dir: Path):
        """Generated KEK is 32 bytes (256 bits)."""
        vault = EncryptedPIIVaultStorage(
            storage_dir=storage_dir,
            claim_id="CLM001",
        )

        kek = vault.kek_path.read_bytes()
        assert len(kek) == 32


class TestVaultStorage:
    """Tests for storing entries."""

    def test_store_single_entry(self, storage_dir: Path, sample_entry: PIIVaultEntry):
        """Single entry stores successfully."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        stored = vault.store(sample_entry)

        assert stored.entry_id == sample_entry.entry_id
        assert vault.data_path.exists()

    def test_store_batch(self, storage_dir: Path):
        """Multiple entries store in batch."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")

        entries = [
            PIIVaultEntry(
                entry_id=generate_entry_id(),
                vault_id="vault_CLM001",
                claim_id="CLM001",
                doc_id="DOC001",
                run_id="RUN001",
                pii_category="names",
                field_path=f"fields[{i}].value",
                redaction_strategy="reference",
                original_value=f"Value {i}",
            )
            for i in range(5)
        ]

        stored = vault.store_batch(entries)
        assert len(stored) == 5

    def test_index_updated_on_store(self, storage_dir: Path, sample_entry: PIIVaultEntry):
        """Index is updated when entries are stored."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        # Re-load index from file
        vault._index = None
        index = vault._get_index()

        assert sample_entry.entry_id in index.entries


class TestVaultRetrieval:
    """Tests for retrieving entries."""

    def test_get_existing_entry(self, storage_dir: Path, sample_entry: PIIVaultEntry):
        """Retrieve entry by ID."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        retrieved = vault.get(sample_entry.entry_id)

        assert retrieved is not None
        assert retrieved.entry_id == sample_entry.entry_id
        assert retrieved.original_value == sample_entry.original_value

    def test_get_nonexistent_entry(self, storage_dir: Path):
        """Getting non-existent entry returns None."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        retrieved = vault.get("pii_nonexistent")

        assert retrieved is None

    def test_get_batch(self, storage_dir: Path):
        """Retrieve multiple entries at once."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")

        entries = [
            PIIVaultEntry(
                entry_id=generate_entry_id(),
                vault_id="vault_CLM001",
                claim_id="CLM001",
                doc_id="DOC001",
                run_id="RUN001",
                pii_category="names",
                field_path=f"fields[{i}].value",
                redaction_strategy="reference",
                original_value=f"Value {i}",
            )
            for i in range(3)
        ]
        vault.store_batch(entries)

        entry_ids = [e.entry_id for e in entries]
        retrieved = vault.get_batch(entry_ids)

        assert len(retrieved) == 3
        for entry_id in entry_ids:
            assert entry_id in retrieved

    def test_list_by_doc(self, storage_dir: Path):
        """List entries for a specific document."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")

        # Store entries for different docs
        entries = [
            PIIVaultEntry(
                entry_id=generate_entry_id(),
                vault_id="vault_CLM001",
                claim_id="CLM001",
                doc_id=f"DOC00{i % 2}",  # DOC000 and DOC001
                run_id="RUN001",
                pii_category="names",
                field_path=f"fields[{i}].value",
                redaction_strategy="reference",
                original_value=f"Value {i}",
            )
            for i in range(4)
        ]
        vault.store_batch(entries)

        doc0_entries = vault.list_by_doc("DOC000")
        doc1_entries = vault.list_by_doc("DOC001")

        assert len(doc0_entries) == 2
        assert len(doc1_entries) == 2


class TestVaultEncryption:
    """Tests for encryption functionality."""

    def test_data_is_encrypted(self, storage_dir: Path, sample_entry: PIIVaultEntry):
        """Stored data is encrypted (not readable as plaintext)."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        # Read raw file content
        raw_data = vault.data_path.read_bytes()

        # Original value should not appear in plaintext
        assert b"John Smith" not in raw_data

    def test_decryption_roundtrip(self, storage_dir: Path, sample_entry: PIIVaultEntry):
        """Data survives encrypt/decrypt roundtrip."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        # Clear cache and reload
        vault._encryptor = None
        retrieved = vault.get(sample_entry.entry_id)

        assert retrieved is not None
        assert retrieved.original_value == "John Smith"


class TestCryptoShredding:
    """Tests for crypto-shredding functionality."""

    def test_shred_vault_deletes_kek(self, storage_dir: Path, sample_entry: PIIVaultEntry):
        """Shredding vault deletes KEK file."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        assert vault.kek_path.exists()

        result = vault.shred_vault("vault_CLM001", "right_to_erasure")

        assert result is True
        assert not vault.kek_path.exists()

    def test_shredded_vault_is_unreadable(
        self, storage_dir: Path, sample_entry: PIIVaultEntry
    ):
        """After shredding, entries cannot be retrieved."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)
        vault.shred_vault("vault_CLM001", "test_deletion")

        with pytest.raises(VaultShreddedError):
            vault.get(sample_entry.entry_id)

    def test_is_shredded_returns_true(
        self, storage_dir: Path, sample_entry: PIIVaultEntry
    ):
        """is_shredded returns True after shredding."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        assert not vault.is_shredded()

        vault.shred_vault("vault_CLM001", "test")

        assert vault.is_shredded()

    def test_index_marked_shredded(
        self, storage_dir: Path, sample_entry: PIIVaultEntry
    ):
        """Index is marked as shredded with reason."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)
        vault.shred_vault("vault_CLM001", "right_to_erasure")

        # Reload index
        vault._index = None
        index = vault._get_index()

        assert index.shredded is True
        assert index.shred_reason == "right_to_erasure"
        assert index.shredded_at is not None

    def test_shred_wrong_vault_id_fails(
        self, storage_dir: Path, sample_entry: PIIVaultEntry
    ):
        """Shredding with wrong vault ID returns False."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        result = vault.shred_vault("vault_OTHER", "test")

        assert result is False
        assert vault.kek_path.exists()  # KEK not deleted

    def test_shred_entries_updates_index(
        self, storage_dir: Path, sample_entry: PIIVaultEntry
    ):
        """Shredding entries removes them from index."""
        vault = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault.store(sample_entry)

        count = vault.shred_entries([sample_entry.entry_id], "individual_deletion")

        assert count == 1

        index = vault._get_index()
        assert sample_entry.entry_id not in index.entries


class TestVaultPersistence:
    """Tests for vault persistence across instances."""

    def test_new_instance_reads_existing_vault(
        self, storage_dir: Path, sample_entry: PIIVaultEntry
    ):
        """New vault instance can read entries from existing vault."""
        # Create and store
        vault1 = EncryptedPIIVaultStorage(storage_dir=storage_dir, claim_id="CLM001")
        vault1.store(sample_entry)

        # Create new instance
        vault2 = EncryptedPIIVaultStorage(
            storage_dir=storage_dir,
            claim_id="CLM001",
            create_if_missing=False,
        )

        retrieved = vault2.get(sample_entry.entry_id)
        assert retrieved is not None
        assert retrieved.original_value == sample_entry.original_value


class TestFactoryFunction:
    """Tests for create_pii_vault factory."""

    def test_create_pii_vault(self, storage_dir: Path):
        """Factory creates vault successfully."""
        vault = create_pii_vault(storage_dir, "CLM001")

        assert vault is not None
        assert vault.vault_id == "vault_CLM001"
        assert vault.vault_dir.exists()
