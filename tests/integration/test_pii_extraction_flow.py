"""Integration tests for PII vault extraction flow.

Tests the end-to-end flow of PII tokenization during extraction:
1. PII fields in extraction results are tokenized
2. Vault entries are stored encrypted
3. Original values can be retrieved with vault access
4. Crypto-shredding makes data unrecoverable

Requires pycryptodome to be installed for vault storage.
"""

import json
import tempfile
from pathlib import Path

import pytest

# Skip all tests in this module if pycryptodome is not installed
pytest.importorskip("Crypto", reason="pycryptodome not installed")

from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    DocumentMetadata,
    ExtractionRunMetadata,
    PageContent,
    QualityGate,
)
from context_builder.schemas.pii_vault import PIIToken
from context_builder.services.compliance.pii import (
    PIIConfigLoader,
    PIITokenizer,
    EncryptedPIIVaultStorage,
)
from context_builder.services.compliance.pii.tokenizer import detokenize_result
from context_builder.services.compliance.pii.vault_storage import VaultShreddedError


class TestPIIExtractionFlow:
    """Integration tests for PII tokenization in extraction."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def pii_config_path(self, temp_dir: Path) -> Path:
        """Create a PII config file."""
        config_content = """
schema_version: "1.0"

categories:
  names:
    description: "Personal names"
    vault: true
    redaction_strategy: "reference"
    field_patterns:
      - "^full_name$"
      - "_name$"
      - "^insured_"

  contact:
    description: "Contact information"
    vault: true
    redaction_strategy: "mask"
    field_patterns:
      - "phone"
      - "email"
      - "^address$"

  government_id:
    description: "Government IDs"
    vault: true
    redaction_strategy: "reference"
    field_patterns:
      - "^id_number$"
      - "^ssn$"
      - "^vin$"

exclusions:
  - pattern: "^vendor_name$"
    reason: "Business entity"

settings:
  default_vault: false
  log_vault_operations: true
  case_insensitive: true
"""
        config_path = temp_dir / "pii_config.yaml"
        config_path.write_text(config_content)
        return config_path

    @pytest.fixture
    def pii_config(self, pii_config_path: Path):
        """Load PII config."""
        PIIConfigLoader.clear_cache()
        return PIIConfigLoader.load(pii_config_path)

    @pytest.fixture
    def sample_extraction(self) -> ExtractionResult:
        """Create a sample extraction result with various PII types."""
        return ExtractionResult(
            run=ExtractionRunMetadata(
                run_id="2024-01-15T10:30:00",
                extractor_version="v1.0.0",
                model="gpt-4o",
                prompt_version="v1",
                input_hashes={"pdf_md5": "abc123"},
            ),
            doc=DocumentMetadata(
                doc_id="DOC001",
                claim_id="CLM001",
                doc_type="loss_notice",
                doc_type_confidence=0.95,
                language="es",
                page_count=2,
            ),
            pages=[
                PageContent(page=1, text="Page 1 content", text_md5="page1hash"),
                PageContent(page=2, text="Page 2 content", text_md5="page2hash"),
            ],
            fields=[
                ExtractedField(
                    name="full_name",
                    value="Maria Garcia Rodriguez",
                    normalized_value="MARIA GARCIA RODRIGUEZ",
                    confidence=0.92,
                    status="present",
                    provenance=[
                        FieldProvenance(
                            page=1,
                            method="llm_parse",
                            text_quote="Nombre: Maria Garcia Rodriguez",
                            char_start=10,
                            char_end=42,
                        )
                    ],
                ),
                ExtractedField(
                    name="insured_phone",
                    value="+52 555 123 4567",
                    confidence=0.88,
                    status="present",
                    provenance=[],
                ),
                ExtractedField(
                    name="vin",
                    value="1HGBH41JXMN109186",
                    confidence=0.95,
                    status="present",
                    provenance=[],
                ),
                ExtractedField(
                    name="claim_number",
                    value="CLM-2024-00001",
                    confidence=0.99,
                    status="present",
                    provenance=[],
                ),
                ExtractedField(
                    name="event_date",
                    value="2024-01-10",
                    confidence=0.90,
                    status="present",
                    provenance=[],
                ),
            ],
            quality_gate=QualityGate(status="pass"),
        )

    def test_full_tokenization_flow(
        self, temp_dir: Path, pii_config, sample_extraction: ExtractionResult
    ):
        """Test complete tokenization and storage flow."""
        claim_id = "CLM001"
        run_id = "RUN001"

        # Create vault
        vault = EncryptedPIIVaultStorage(
            storage_dir=temp_dir,
            claim_id=claim_id,
            create_if_missing=True,
        )

        # Tokenize extraction
        tokenizer = PIITokenizer(
            claim_id=claim_id,
            config=pii_config,
            vault_id=vault.vault_id,
        )
        result = tokenizer.tokenize(sample_extraction, run_id)

        # Store vault entries
        vault.store_batch(result.vault_entries)

        # Verify PII fields are tokenized
        fields = result.redacted_result["fields"]

        full_name_field = next(f for f in fields if f["name"] == "full_name")
        assert full_name_field["value"].startswith("[PII:")
        assert full_name_field["normalized_value"].startswith("[PII:")

        phone_field = next(f for f in fields if f["name"] == "insured_phone")
        assert phone_field["value"].startswith("[PII:")

        vin_field = next(f for f in fields if f["name"] == "vin")
        assert vin_field["value"].startswith("[PII:")

        # Verify non-PII fields unchanged
        claim_field = next(f for f in fields if f["name"] == "claim_number")
        assert claim_field["value"] == "CLM-2024-00001"

        date_field = next(f for f in fields if f["name"] == "event_date")
        assert date_field["value"] == "2024-01-10"

        # Verify provenance is tokenized
        assert full_name_field["provenance"][0]["text_quote"].startswith("[PII:")

    def test_token_resolution(
        self, temp_dir: Path, pii_config, sample_extraction: ExtractionResult
    ):
        """Test resolving tokens back to original values."""
        claim_id = "CLM001"
        run_id = "RUN001"

        # Create vault and tokenize
        vault = EncryptedPIIVaultStorage(storage_dir=temp_dir, claim_id=claim_id)
        tokenizer = PIITokenizer(claim_id=claim_id, config=pii_config)
        result = tokenizer.tokenize(sample_extraction, run_id)
        vault.store_batch(result.vault_entries)

        # Extract token from result
        fields = result.redacted_result["fields"]
        full_name_field = next(f for f in fields if f["name"] == "full_name")
        token = PIIToken.parse(full_name_field["value"])

        assert token is not None

        # Resolve token
        entry = vault.get(token.entry_id)

        assert entry is not None
        assert entry.original_value == "Maria Garcia Rodriguez"
        assert entry.pii_category == "names"

    def test_detokenization_roundtrip(
        self, temp_dir: Path, pii_config, sample_extraction: ExtractionResult
    ):
        """Test complete tokenize-detokenize roundtrip."""
        claim_id = "CLM001"
        run_id = "RUN001"

        # Tokenize
        vault = EncryptedPIIVaultStorage(storage_dir=temp_dir, claim_id=claim_id)
        tokenizer = PIITokenizer(claim_id=claim_id, config=pii_config)
        result = tokenizer.tokenize(sample_extraction, run_id)
        vault.store_batch(result.vault_entries)

        # Get all tokens from result
        entry_ids = [e.entry_id for e in result.vault_entries]
        entries = vault.get_batch(entry_ids)

        # Detokenize
        restored = detokenize_result(result.redacted_result, entries)

        # Verify original values are restored
        fields = restored["fields"]

        full_name_field = next(f for f in fields if f["name"] == "full_name")
        assert full_name_field["value"] == "Maria Garcia Rodriguez"

        phone_field = next(f for f in fields if f["name"] == "insured_phone")
        assert phone_field["value"] == "+52 555 123 4567"

    def test_crypto_shred_makes_data_unrecoverable(
        self, temp_dir: Path, pii_config, sample_extraction: ExtractionResult
    ):
        """Test that crypto-shredding makes data permanently unrecoverable."""
        claim_id = "CLM001"
        run_id = "RUN001"

        # Tokenize and store
        vault = EncryptedPIIVaultStorage(storage_dir=temp_dir, claim_id=claim_id)
        tokenizer = PIITokenizer(claim_id=claim_id, config=pii_config)
        result = tokenizer.tokenize(sample_extraction, run_id)
        vault.store_batch(result.vault_entries)

        # Verify we can read before shredding
        entry = vault.get(result.vault_entries[0].entry_id)
        assert entry is not None

        # Shred the vault
        shred_result = vault.shred_vault(vault.vault_id, "right_to_erasure")
        assert shred_result is True

        # Verify vault is shredded
        assert vault.is_shredded() is True

        # Attempt to read should fail
        with pytest.raises(VaultShreddedError):
            vault.get(result.vault_entries[0].entry_id)

    def test_persisted_extraction_contains_tokens(
        self, temp_dir: Path, pii_config, sample_extraction: ExtractionResult
    ):
        """Test that saved extraction JSON contains tokens, not PII."""
        claim_id = "CLM001"
        run_id = "RUN001"

        # Tokenize
        vault = EncryptedPIIVaultStorage(storage_dir=temp_dir, claim_id=claim_id)
        tokenizer = PIITokenizer(claim_id=claim_id, config=pii_config)
        result = tokenizer.tokenize(sample_extraction, run_id)
        vault.store_batch(result.vault_entries)

        # Save to file (simulating pipeline write)
        output_path = temp_dir / "extraction.json"
        output_path.write_text(json.dumps(result.redacted_result, indent=2))

        # Read back and verify
        loaded = json.loads(output_path.read_text())

        # Raw JSON should not contain PII
        raw_text = output_path.read_text()
        assert "Maria Garcia Rodriguez" not in raw_text
        assert "+52 555 123 4567" not in raw_text
        assert "1HGBH41JXMN109186" not in raw_text

        # Should contain tokens
        assert "[PII:" in raw_text

    def test_vault_entries_are_encrypted(
        self, temp_dir: Path, pii_config, sample_extraction: ExtractionResult
    ):
        """Test that vault data file is encrypted."""
        claim_id = "CLM001"
        run_id = "RUN001"

        # Tokenize and store
        vault = EncryptedPIIVaultStorage(storage_dir=temp_dir, claim_id=claim_id)
        tokenizer = PIITokenizer(claim_id=claim_id, config=pii_config)
        result = tokenizer.tokenize(sample_extraction, run_id)
        vault.store_batch(result.vault_entries)

        # Read raw vault data file
        vault_data = vault.data_path.read_bytes()

        # PII values should not appear in plaintext
        assert b"Maria Garcia Rodriguez" not in vault_data
        assert b"+52 555 123 4567" not in vault_data
        assert b"1HGBH41JXMN109186" not in vault_data

    def test_multiple_documents_same_vault(
        self, temp_dir: Path, pii_config
    ):
        """Test storing PII from multiple documents in same claim vault."""
        claim_id = "CLM001"

        vault = EncryptedPIIVaultStorage(storage_dir=temp_dir, claim_id=claim_id)
        tokenizer = PIITokenizer(claim_id=claim_id, config=pii_config)

        # Process first document
        doc1 = ExtractionResult(
            run=ExtractionRunMetadata(
                run_id="RUN001", extractor_version="v1", model="gpt-4o",
                prompt_version="v1", input_hashes={},
            ),
            doc=DocumentMetadata(
                doc_id="DOC001", claim_id=claim_id, doc_type="loss_notice",
                doc_type_confidence=0.9, language="es", page_count=1,
            ),
            pages=[PageContent(page=1, text="", text_md5="")],
            fields=[
                ExtractedField(
                    name="full_name", value="Person One", confidence=0.9, status="present",
                ),
            ],
            quality_gate=QualityGate(status="pass"),
        )
        result1 = tokenizer.tokenize(doc1, "RUN001")
        vault.store_batch(result1.vault_entries)

        # Process second document
        doc2 = ExtractionResult(
            run=ExtractionRunMetadata(
                run_id="RUN001", extractor_version="v1", model="gpt-4o",
                prompt_version="v1", input_hashes={},
            ),
            doc=DocumentMetadata(
                doc_id="DOC002", claim_id=claim_id, doc_type="police_report",
                doc_type_confidence=0.85, language="es", page_count=1,
            ),
            pages=[PageContent(page=1, text="", text_md5="")],
            fields=[
                ExtractedField(
                    name="full_name", value="Person Two", confidence=0.9, status="present",
                ),
            ],
            quality_gate=QualityGate(status="pass"),
        )
        result2 = tokenizer.tokenize(doc2, "RUN001")
        vault.store_batch(result2.vault_entries)

        # Verify entries for each document
        doc1_entries = vault.list_by_doc("DOC001")
        doc2_entries = vault.list_by_doc("DOC002")

        assert len(doc1_entries) >= 1
        assert len(doc2_entries) >= 1
        assert doc1_entries[0].original_value == "Person One"
        assert doc2_entries[0].original_value == "Person Two"
