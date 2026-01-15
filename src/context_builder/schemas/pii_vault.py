"""Schemas for PII Vault storage.

This module defines the data structures for storing and managing PII
(Personally Identifiable Information) in an encrypted vault with
support for tokenization and crypto-shredding.

Key concepts:
- PIIVaultEntry: Individual PII value stored in the vault
- PIIVaultIndex: Lookup index for a claim's vault
- PIIToken: Token format for referencing vault entries
- TokenizationResult: Output of tokenization process
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Token format: [PII:vault_<claim_id>:<entry_id>]
TOKEN_PREFIX = "[PII:"
TOKEN_SUFFIX = "]"


@dataclass
class PIIVaultEntry:
    """A single PII value stored in the encrypted vault.

    Attributes:
        entry_id: Unique identifier for this entry (pii_<12hex>)
        vault_id: Vault identifier (vault_<claim_id>)
        claim_id: Parent claim identifier
        doc_id: Document this PII was extracted from
        run_id: Extraction run that created this entry
        pii_category: Category from pii_config.yaml (e.g., 'names', 'contact')
        field_path: Path to field in extraction result (e.g., 'fields[3].value')
        redaction_strategy: How to display in non-privileged views
        original_value: The actual PII value (stored encrypted)
        normalized_value: Normalized form if applicable
        created_at: ISO timestamp when entry was created
        deleted_at: ISO timestamp if crypto-shredded (for audit trail)
    """

    entry_id: str
    vault_id: str
    claim_id: str
    doc_id: str
    run_id: str
    pii_category: str
    field_path: str
    redaction_strategy: Literal["reference", "mask", "hash"]
    original_value: str
    normalized_value: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    deleted_at: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "entry_id": self.entry_id,
            "vault_id": self.vault_id,
            "claim_id": self.claim_id,
            "doc_id": self.doc_id,
            "run_id": self.run_id,
            "pii_category": self.pii_category,
            "field_path": self.field_path,
            "redaction_strategy": self.redaction_strategy,
            "original_value": self.original_value,
            "normalized_value": self.normalized_value,
            "created_at": self.created_at,
            "deleted_at": self.deleted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PIIVaultEntry":
        """Create from dictionary."""
        return cls(
            entry_id=data["entry_id"],
            vault_id=data["vault_id"],
            claim_id=data["claim_id"],
            doc_id=data["doc_id"],
            run_id=data["run_id"],
            pii_category=data["pii_category"],
            field_path=data["field_path"],
            redaction_strategy=data["redaction_strategy"],
            original_value=data["original_value"],
            normalized_value=data.get("normalized_value"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            deleted_at=data.get("deleted_at"),
        )


@dataclass
class PIIVaultIndexEntry:
    """Lightweight index entry for looking up vault entries.

    Stored unencrypted in index.json for fast lookups without
    decrypting the entire vault.
    """

    entry_id: str
    pii_category: str
    field_path: str
    doc_id: str
    run_id: str


@dataclass
class PIIVaultIndex:
    """Index for a claim's PII vault.

    Provides fast lookups without decrypting vault entries.
    Stored as plaintext JSON alongside encrypted vault data.

    Attributes:
        vault_id: Vault identifier (vault_<claim_id>)
        claim_id: Parent claim identifier
        entries: Map of entry_id -> index entry
        shredded: True if vault has been crypto-shredded
        shredded_at: ISO timestamp when shredded
        shred_reason: Reason for shredding (e.g., "right_to_erasure")
    """

    vault_id: str
    claim_id: str
    entries: Dict[str, PIIVaultIndexEntry] = field(default_factory=dict)
    shredded: bool = False
    shredded_at: Optional[str] = None
    shred_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "vault_id": self.vault_id,
            "claim_id": self.claim_id,
            "entries": {
                k: {
                    "entry_id": v.entry_id,
                    "pii_category": v.pii_category,
                    "field_path": v.field_path,
                    "doc_id": v.doc_id,
                    "run_id": v.run_id,
                }
                for k, v in self.entries.items()
            },
            "shredded": self.shredded,
            "shredded_at": self.shredded_at,
            "shred_reason": self.shred_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PIIVaultIndex":
        """Create from dictionary."""
        entries = {}
        for k, v in data.get("entries", {}).items():
            entries[k] = PIIVaultIndexEntry(
                entry_id=v["entry_id"],
                pii_category=v["pii_category"],
                field_path=v["field_path"],
                doc_id=v["doc_id"],
                run_id=v["run_id"],
            )
        return cls(
            vault_id=data["vault_id"],
            claim_id=data["claim_id"],
            entries=entries,
            shredded=data.get("shredded", False),
            shredded_at=data.get("shredded_at"),
            shred_reason=data.get("shred_reason"),
        )


class PIIToken(BaseModel):
    """Parsed PII token from extraction result.

    Token format: [PII:vault_<claim_id>:<entry_id>]
    """

    vault_id: str = Field(..., description="Vault identifier (vault_<claim_id>)")
    entry_id: str = Field(..., description="Entry identifier (pii_<12hex>)")

    def to_string(self) -> str:
        """Convert to token string format."""
        return f"{TOKEN_PREFIX}{self.vault_id}:{self.entry_id}{TOKEN_SUFFIX}"

    @classmethod
    def parse(cls, token_str: str) -> Optional["PIIToken"]:
        """Parse a token string.

        Args:
            token_str: Token in format [PII:vault_<claim_id>:<entry_id>]

        Returns:
            PIIToken if valid, None if invalid format.
        """
        if not token_str.startswith(TOKEN_PREFIX) or not token_str.endswith(TOKEN_SUFFIX):
            return None

        # Extract content between prefix and suffix
        content = token_str[len(TOKEN_PREFIX) : -len(TOKEN_SUFFIX)]
        parts = content.split(":")

        if len(parts) != 2:
            return None

        vault_id, entry_id = parts
        if not vault_id.startswith("vault_") or not entry_id.startswith("pii_"):
            return None

        return cls(vault_id=vault_id, entry_id=entry_id)


@dataclass
class TokenizationResult:
    """Result of tokenizing an extraction result.

    Contains the redacted result (with tokens replacing PII)
    and the vault entries to store.
    """

    # The extraction result with PII replaced by tokens
    # Note: This is a dict because we mutate the model_dump() output
    redacted_result: Dict

    # Vault entries created during tokenization
    vault_entries: List[PIIVaultEntry]

    # Statistics
    fields_scanned: int = 0
    fields_tokenized: int = 0
    provenance_quotes_tokenized: int = 0


def generate_entry_id() -> str:
    """Generate a unique entry ID for a vault entry."""
    import secrets

    return f"pii_{secrets.token_hex(6)}"


def generate_vault_id(claim_id: str) -> str:
    """Generate a vault ID for a claim."""
    return f"vault_{claim_id}"
