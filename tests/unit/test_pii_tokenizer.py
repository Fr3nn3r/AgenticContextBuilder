"""Unit tests for PII tokenizer.

Tests:
- Tokenization of extraction results
- Field value tokenization
- Provenance quote tokenization
- Token format validation
- Detokenization roundtrip
"""

from pathlib import Path
from typing import Dict, Any

import pytest

from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    DocumentMetadata,
    ExtractionRunMetadata,
    PageContent,
    QualityGate,
)
from context_builder.schemas.pii_vault import (
    PIIToken,
    PIIVaultEntry,
    TokenizationResult,
    generate_entry_id,
    generate_vault_id,
)
from context_builder.services.compliance.pii.tokenizer import PIITokenizer, detokenize_result
from context_builder.services.compliance.pii.config_loader import PIIConfigLoader


@pytest.fixture
def sample_config_yaml(tmp_path: Path) -> Path:
    """Create a sample pii_config.yaml for testing."""
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

  contact:
    description: "Contact information"
    vault: true
    redaction_strategy: "mask"
    field_patterns:
      - "phone"
      - "email"

exclusions:
  - pattern: "^vendor_name$"
    reason: "Business entity"

settings:
  default_vault: false
  case_insensitive: true
"""
    config_path = tmp_path / "pii_config.yaml"
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def pii_config(sample_config_yaml: Path):
    """Load PII config for testing."""
    PIIConfigLoader.clear_cache()
    return PIIConfigLoader.load(sample_config_yaml)


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """Create a sample extraction result with PII fields."""
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
            page_count=1,
        ),
        pages=[
            PageContent(
                page=1,
                text="Sample document text",
                text_md5="textmd5",
            )
        ],
        fields=[
            ExtractedField(
                name="full_name",
                value="John Smith",
                confidence=0.9,
                status="present",
                provenance=[
                    FieldProvenance(
                        page=1,
                        method="llm_parse",
                        text_quote="Name: John Smith",
                        char_start=0,
                        char_end=16,
                    )
                ],
            ),
            ExtractedField(
                name="phone",
                value="555-123-4567",
                confidence=0.85,
                status="present",
                provenance=[],
            ),
            ExtractedField(
                name="claim_number",
                value="CLM-2024-001",
                confidence=0.99,
                status="present",
                provenance=[],
            ),
            ExtractedField(
                name="vendor_name",
                value="Acme Corp",
                confidence=0.9,
                status="present",
                provenance=[],
            ),
        ],
        quality_gate=QualityGate(status="pass"),
    )


class TestPIITokenFormat:
    """Tests for PII token format and parsing."""

    def test_token_to_string(self):
        """Token converts to correct string format."""
        token = PIIToken(vault_id="vault_CLM001", entry_id="pii_abc123def456")
        assert token.to_string() == "[PII:vault_CLM001:pii_abc123def456]"

    def test_parse_valid_token(self):
        """Valid token string parses correctly."""
        token = PIIToken.parse("[PII:vault_CLM001:pii_abc123def456]")
        assert token is not None
        assert token.vault_id == "vault_CLM001"
        assert token.entry_id == "pii_abc123def456"

    def test_parse_invalid_token_returns_none(self):
        """Invalid token strings return None."""
        assert PIIToken.parse("not a token") is None
        assert PIIToken.parse("[PII:invalid]") is None
        assert PIIToken.parse("[PII:vault_X]") is None  # Missing entry_id
        assert PIIToken.parse("vault_X:pii_Y") is None  # Missing brackets

    def test_generate_entry_id_format(self):
        """Generated entry IDs have correct format."""
        entry_id = generate_entry_id()
        assert entry_id.startswith("pii_")
        assert len(entry_id) == 16  # pii_ + 12 hex chars

    def test_generate_vault_id_format(self):
        """Generated vault IDs have correct format."""
        vault_id = generate_vault_id("CLM001")
        assert vault_id == "vault_CLM001"


class TestPIITokenization:
    """Tests for tokenizing extraction results."""

    def test_tokenizes_pii_fields(
        self, pii_config, sample_extraction_result: ExtractionResult
    ):
        """PII fields are tokenized in extraction result."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        # Check that PII fields are tokenized
        fields = result.redacted_result["fields"]

        # full_name should be tokenized
        full_name_field = next(f for f in fields if f["name"] == "full_name")
        assert full_name_field["value"].startswith("[PII:")

        # phone should be tokenized
        phone_field = next(f for f in fields if f["name"] == "phone")
        assert phone_field["value"].startswith("[PII:")

        # claim_number should NOT be tokenized (not PII)
        claim_field = next(f for f in fields if f["name"] == "claim_number")
        assert claim_field["value"] == "CLM-2024-001"

        # vendor_name should NOT be tokenized (excluded)
        vendor_field = next(f for f in fields if f["name"] == "vendor_name")
        assert vendor_field["value"] == "Acme Corp"

    def test_creates_vault_entries(
        self, pii_config, sample_extraction_result: ExtractionResult
    ):
        """Vault entries are created for tokenized fields."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        # Should have vault entries for: full_name value, full_name provenance, phone
        assert len(result.vault_entries) >= 2

        # Check entry properties
        for entry in result.vault_entries:
            assert entry.claim_id == "CLM001"
            assert entry.doc_id == "DOC001"
            assert entry.run_id == "RUN001"
            assert entry.vault_id == "vault_CLM001"
            assert entry.entry_id.startswith("pii_")

    def test_tokenizes_provenance_quotes(
        self, pii_config, sample_extraction_result: ExtractionResult
    ):
        """Provenance text_quote is also tokenized for PII fields."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        # full_name has provenance with PII
        fields = result.redacted_result["fields"]
        full_name_field = next(f for f in fields if f["name"] == "full_name")

        if full_name_field["provenance"]:
            text_quote = full_name_field["provenance"][0]["text_quote"]
            assert text_quote.startswith("[PII:")

    def test_preserves_non_pii_fields(
        self, pii_config, sample_extraction_result: ExtractionResult
    ):
        """Non-PII fields are preserved unchanged."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        fields = result.redacted_result["fields"]
        claim_field = next(f for f in fields if f["name"] == "claim_number")

        assert claim_field["value"] == "CLM-2024-001"
        assert claim_field["confidence"] == 0.99
        assert claim_field["status"] == "present"

    def test_statistics_reported(
        self, pii_config, sample_extraction_result: ExtractionResult
    ):
        """Tokenization statistics are accurate."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        assert result.fields_scanned == 4
        assert result.fields_tokenized >= 2  # full_name and phone


class TestPIIDetokenization:
    """Tests for restoring PII from tokens."""

    def test_detokenize_roundtrip(
        self, pii_config, sample_extraction_result: ExtractionResult
    ):
        """Detokenization restores original values."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        # Build entry lookup
        entries = {e.entry_id: e for e in result.vault_entries}

        # Detokenize
        restored = detokenize_result(result.redacted_result, entries)

        # Check values are restored
        fields = restored["fields"]
        full_name_field = next(f for f in fields if f["name"] == "full_name")
        assert full_name_field["value"] == "John Smith"

        phone_field = next(f for f in fields if f["name"] == "phone")
        assert phone_field["value"] == "555-123-4567"

    def test_detokenize_missing_entry(self, pii_config, sample_extraction_result):
        """Detokenization with missing entries keeps tokens."""
        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        result = tokenizer.tokenize(sample_extraction_result, run_id="RUN001")

        # Empty entry lookup
        restored = detokenize_result(result.redacted_result, {})

        # Tokens should remain (no entries to restore from)
        fields = restored["fields"]
        full_name_field = next(f for f in fields if f["name"] == "full_name")
        assert full_name_field["value"].startswith("[PII:")


class TestTokenizerEdgeCases:
    """Tests for edge cases in tokenization."""

    def test_empty_fields_list(self, pii_config):
        """Handles extraction result with no fields."""
        result = ExtractionResult(
            run=ExtractionRunMetadata(
                run_id="RUN001",
                extractor_version="v1",
                model="gpt-4o",
                prompt_version="v1",
                input_hashes={},
            ),
            doc=DocumentMetadata(
                doc_id="DOC001",
                claim_id="CLM001",
                doc_type="unknown",
                doc_type_confidence=0.5,
                language="en",
                page_count=1,
            ),
            pages=[PageContent(page=1, text="", text_md5="empty")],
            fields=[],
            quality_gate=QualityGate(status="pass"),
        )

        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        tokenization = tokenizer.tokenize(result, run_id="RUN001")

        assert len(tokenization.vault_entries) == 0
        assert tokenization.fields_scanned == 0

    def test_null_field_value(self, pii_config):
        """Handles fields with null values."""
        result = ExtractionResult(
            run=ExtractionRunMetadata(
                run_id="RUN001",
                extractor_version="v1",
                model="gpt-4o",
                prompt_version="v1",
                input_hashes={},
            ),
            doc=DocumentMetadata(
                doc_id="DOC001",
                claim_id="CLM001",
                doc_type="loss_notice",
                doc_type_confidence=0.9,
                language="es",
                page_count=1,
            ),
            pages=[PageContent(page=1, text="", text_md5="empty")],
            fields=[
                ExtractedField(
                    name="full_name",
                    value=None,
                    confidence=0.0,
                    status="missing",
                    provenance=[],
                ),
            ],
            quality_gate=QualityGate(status="warn", reasons=["Missing full_name"]),
        )

        tokenizer = PIITokenizer(claim_id="CLM001", config=pii_config)
        tokenization = tokenizer.tokenize(result, run_id="RUN001")

        # No entries created for null value
        assert len(tokenization.vault_entries) == 0
