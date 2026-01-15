"""PII Tokenizer for extraction results.

Scans extraction results for PII fields, creates vault entries,
and replaces PII values with tokens referencing the vault.
"""

import logging
from copy import deepcopy
from typing import Dict, List, Optional, Any

from context_builder.schemas.extraction_result import ExtractionResult
from context_builder.schemas.pii_vault import (
    PIIToken,
    PIIVaultEntry,
    TokenizationResult,
    generate_entry_id,
    generate_vault_id,
)
from context_builder.services.compliance.pii.config_loader import PIIConfig, PIIConfigLoader

logger = logging.getLogger(__name__)


class PIITokenizer:
    """Tokenize PII in extraction results.

    Scans extraction result fields and provenance quotes for PII,
    creates vault entries, and returns a redacted result with tokens.

    Example:
        tokenizer = PIITokenizer(claim_id="CLM001")
        result = tokenizer.tokenize(extraction_result, run_id="2024-01-15T10:30:00")

        # result.redacted_result has PII replaced with tokens
        # result.vault_entries contains PIIVaultEntry objects to store
    """

    def __init__(
        self,
        claim_id: str,
        config: Optional[PIIConfig] = None,
        vault_id: Optional[str] = None,
    ):
        """Initialize the tokenizer.

        Args:
            claim_id: Claim identifier for vault association.
            config: Optional PIIConfig. Loaded from default if not provided.
            vault_id: Optional vault ID. Generated from claim_id if not provided.
        """
        self.claim_id = claim_id
        self.vault_id = vault_id or generate_vault_id(claim_id)
        self.config = config or PIIConfigLoader.load()

    def tokenize(
        self,
        result: ExtractionResult,
        run_id: str,
    ) -> TokenizationResult:
        """Tokenize PII in an extraction result.

        Scans the following locations for PII:
        1. fields[].value
        2. fields[].normalized_value
        3. fields[].provenance[].text_quote

        Args:
            result: The extraction result to tokenize.
            run_id: The extraction run ID.

        Returns:
            TokenizationResult with redacted result and vault entries.
        """
        # Work with a dict copy to avoid mutating the original
        result_dict = result.model_dump()
        doc_id = result.doc.doc_id
        doc_type = result.doc.doc_type

        vault_entries: List[PIIVaultEntry] = []
        fields_scanned = 0
        fields_tokenized = 0
        provenance_quotes_tokenized = 0

        # Process each field
        for field_idx, field_data in enumerate(result_dict.get("fields", [])):
            fields_scanned += 1
            field_name = field_data.get("name", "")

            # Check if this field should be vaulted
            should_vault, pii_category, redaction_strategy = self.config.should_vault_field(
                field_name, doc_type
            )

            if not should_vault:
                continue

            # Tokenize field value
            value = field_data.get("value")
            if value and isinstance(value, str) and value.strip():
                entry = self._create_vault_entry(
                    value=value,
                    field_path=f"fields[{field_idx}].value",
                    pii_category=pii_category or "unknown",
                    redaction_strategy=redaction_strategy or "reference",
                    doc_id=doc_id,
                    run_id=run_id,
                )
                vault_entries.append(entry)

                # Replace value with token
                token = PIIToken(vault_id=self.vault_id, entry_id=entry.entry_id)
                field_data["value"] = token.to_string()
                fields_tokenized += 1

            # Tokenize normalized_value if different from value
            normalized_value = field_data.get("normalized_value")
            if (
                normalized_value
                and isinstance(normalized_value, str)
                and normalized_value.strip()
                and normalized_value != value  # Don't double-tokenize same value
            ):
                entry = self._create_vault_entry(
                    value=normalized_value,
                    field_path=f"fields[{field_idx}].normalized_value",
                    pii_category=pii_category or "unknown",
                    redaction_strategy=redaction_strategy or "reference",
                    doc_id=doc_id,
                    run_id=run_id,
                )
                vault_entries.append(entry)

                # Replace with token
                token = PIIToken(vault_id=self.vault_id, entry_id=entry.entry_id)
                field_data["normalized_value"] = token.to_string()

            # Tokenize provenance quotes
            for prov_idx, prov_data in enumerate(field_data.get("provenance", [])):
                text_quote = prov_data.get("text_quote")
                if text_quote and isinstance(text_quote, str) and text_quote.strip():
                    entry = self._create_vault_entry(
                        value=text_quote,
                        field_path=f"fields[{field_idx}].provenance[{prov_idx}].text_quote",
                        pii_category=pii_category or "unknown",
                        redaction_strategy=redaction_strategy or "reference",
                        doc_id=doc_id,
                        run_id=run_id,
                    )
                    vault_entries.append(entry)

                    # Replace with token
                    token = PIIToken(vault_id=self.vault_id, entry_id=entry.entry_id)
                    prov_data["text_quote"] = token.to_string()
                    provenance_quotes_tokenized += 1

        if vault_entries:
            logger.info(
                f"Tokenized {len(vault_entries)} PII values from doc {doc_id}: "
                f"{fields_tokenized} fields, {provenance_quotes_tokenized} provenance quotes"
            )

        return TokenizationResult(
            redacted_result=result_dict,
            vault_entries=vault_entries,
            fields_scanned=fields_scanned,
            fields_tokenized=fields_tokenized,
            provenance_quotes_tokenized=provenance_quotes_tokenized,
        )

    def _create_vault_entry(
        self,
        value: str,
        field_path: str,
        pii_category: str,
        redaction_strategy: str,
        doc_id: str,
        run_id: str,
    ) -> PIIVaultEntry:
        """Create a vault entry for a PII value.

        Args:
            value: The PII value to store.
            field_path: Path to field in extraction result.
            pii_category: Category from pii_config.yaml.
            redaction_strategy: How to display in non-privileged views.
            doc_id: Document identifier.
            run_id: Extraction run identifier.

        Returns:
            PIIVaultEntry ready to store.
        """
        return PIIVaultEntry(
            entry_id=generate_entry_id(),
            vault_id=self.vault_id,
            claim_id=self.claim_id,
            doc_id=doc_id,
            run_id=run_id,
            pii_category=pii_category,
            field_path=field_path,
            redaction_strategy=redaction_strategy,
            original_value=value,
        )


def detokenize_result(
    result_dict: Dict[str, Any],
    vault_entries: Dict[str, PIIVaultEntry],
) -> Dict[str, Any]:
    """Restore PII values from tokens in an extraction result.

    This is the inverse of tokenization - replaces tokens with original values.

    Args:
        result_dict: Extraction result dict with tokens.
        vault_entries: Map of entry_id -> PIIVaultEntry.

    Returns:
        Result dict with tokens replaced by original values.
    """
    result = deepcopy(result_dict)

    for field_data in result.get("fields", []):
        # Detokenize value
        value = field_data.get("value")
        if value and isinstance(value, str):
            token = PIIToken.parse(value)
            if token and token.entry_id in vault_entries:
                field_data["value"] = vault_entries[token.entry_id].original_value

        # Detokenize normalized_value
        normalized_value = field_data.get("normalized_value")
        if normalized_value and isinstance(normalized_value, str):
            token = PIIToken.parse(normalized_value)
            if token and token.entry_id in vault_entries:
                field_data["normalized_value"] = vault_entries[token.entry_id].original_value

        # Detokenize provenance quotes
        for prov_data in field_data.get("provenance", []):
            text_quote = prov_data.get("text_quote")
            if text_quote and isinstance(text_quote, str):
                token = PIIToken.parse(text_quote)
                if token and token.entry_id in vault_entries:
                    prov_data["text_quote"] = vault_entries[token.entry_id].original_value

    return result
