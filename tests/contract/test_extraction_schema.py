"""Contract tests for ExtractionResult schema validation."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractionRunMetadata,
    DocumentMetadata,
    PageContent,
    ExtractedField,
    FieldProvenance,
    QualityGate,
)


class TestExtractionResultSchema:
    """Tests for ExtractionResult Pydantic model."""

    @pytest.fixture
    def valid_run_metadata(self):
        """Create valid run metadata."""
        return ExtractionRunMetadata(
            run_id="run_20240101_120000_abc1234",
            extractor_version="1.0.0",
            model="gpt-4o",
            prompt_version="v1",
            input_hashes={"pdf_md5": "abc123", "di_text_md5": "def456"},
        )

    @pytest.fixture
    def valid_doc_metadata(self):
        """Create valid document metadata."""
        return DocumentMetadata(
            doc_id="doc123",
            claim_id="claim456",
            doc_type="loss_notice",
            doc_type_confidence=0.95,
            language="es",
            page_count=3,
        )

    @pytest.fixture
    def valid_page_content(self):
        """Create valid page content."""
        return PageContent(
            page=1,
            text="This is page 1 content.",
            text_md5="abc123def456",
        )

    @pytest.fixture
    def valid_provenance(self):
        """Create valid field provenance."""
        return FieldProvenance(
            page=1,
            method="di_text",
            text_quote="January 15, 2024",
            char_start=100,
            char_end=117,
        )

    @pytest.fixture
    def valid_field(self, valid_provenance):
        """Create valid extracted field."""
        return ExtractedField(
            name="incident_date",
            value="January 15, 2024",
            normalized_value="2024-01-15",
            confidence=0.9,
            status="present",
            provenance=[valid_provenance],
        )

    @pytest.fixture
    def valid_quality_gate(self):
        """Create valid quality gate."""
        return QualityGate(
            status="pass",
            reasons=[],
            missing_required_fields=[],
            needs_vision_fallback=False,
        )

    def test_valid_extraction_result(
        self,
        valid_run_metadata,
        valid_doc_metadata,
        valid_page_content,
        valid_field,
        valid_quality_gate,
    ):
        """Test that a valid ExtractionResult can be created."""
        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=valid_run_metadata,
            doc=valid_doc_metadata,
            pages=[valid_page_content],
            fields=[valid_field],
            quality_gate=valid_quality_gate,
        )
        assert result.schema_version == "extraction_result_v1"
        assert result.doc.doc_id == "doc123"
        assert len(result.fields) == 1
        assert result.fields[0].name == "incident_date"

    def test_rejects_extra_fields(
        self,
        valid_run_metadata,
        valid_doc_metadata,
        valid_page_content,
        valid_field,
        valid_quality_gate,
    ):
        """Test that extra fields are rejected (ConfigDict extra='forbid')."""
        with pytest.raises(ValidationError) as exc_info:
            ExtractionResult(
                schema_version="extraction_result_v1",
                run=valid_run_metadata,
                doc=valid_doc_metadata,
                pages=[valid_page_content],
                fields=[valid_field],
                quality_gate=valid_quality_gate,
                extra_field="should_fail",  # Extra field
            )
        assert "extra_field" in str(exc_info.value)

    def test_rejects_invalid_schema_version(
        self,
        valid_run_metadata,
        valid_doc_metadata,
        valid_page_content,
        valid_field,
        valid_quality_gate,
    ):
        """Test that invalid schema_version is rejected."""
        with pytest.raises(ValidationError):
            ExtractionResult(
                schema_version="invalid_version",  # Invalid
                run=valid_run_metadata,
                doc=valid_doc_metadata,
                pages=[valid_page_content],
                fields=[valid_field],
                quality_gate=valid_quality_gate,
            )

    def test_confidence_range_validation(self, valid_doc_metadata):
        """Test confidence must be between 0 and 1."""
        # Above 1 should fail
        with pytest.raises(ValidationError):
            ExtractedField(
                name="test",
                confidence=1.5,  # Invalid: > 1
                status="present",
            )

        # Below 0 should fail
        with pytest.raises(ValidationError):
            ExtractedField(
                name="test",
                confidence=-0.1,  # Invalid: < 0
                status="present",
            )

    def test_page_count_validation(self):
        """Test page_count must be >= 1."""
        with pytest.raises(ValidationError):
            DocumentMetadata(
                doc_id="doc123",
                claim_id="claim456",
                doc_type="loss_notice",
                doc_type_confidence=0.95,
                language="es",
                page_count=0,  # Invalid: must be >= 1
            )


class TestExtractionResultSerialization:
    """Tests for ExtractionResult serialization."""

    def test_round_trip_serialization(self):
        """Test that model can be serialized and deserialized."""
        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=ExtractionRunMetadata(
                run_id="run_20240101",
                extractor_version="1.0",
                model="gpt-4o",
                prompt_version="v1",
            ),
            doc=DocumentMetadata(
                doc_id="doc1",
                claim_id="claim1",
                doc_type="loss_notice",
                doc_type_confidence=0.9,
                language="es",
                page_count=1,
            ),
            pages=[PageContent(page=1, text="Hello", text_md5="abc")],
            fields=[
                ExtractedField(
                    name="date",
                    value="2024-01-15",
                    confidence=0.9,
                    status="present",
                )
            ],
            quality_gate=QualityGate(status="pass"),
        )

        # Serialize to dict
        data = result.model_dump()

        # Deserialize back
        restored = ExtractionResult.model_validate(data)

        assert restored.schema_version == result.schema_version
        assert restored.doc.doc_id == result.doc.doc_id
        assert restored.fields[0].name == result.fields[0].name

    def test_json_serialization(self):
        """Test JSON serialization works."""
        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=ExtractionRunMetadata(
                run_id="run_20240101",
                extractor_version="1.0",
                model="gpt-4o",
                prompt_version="v1",
            ),
            doc=DocumentMetadata(
                doc_id="doc1",
                claim_id="claim1",
                doc_type="loss_notice",
                doc_type_confidence=0.9,
                language="es",
                page_count=1,
            ),
            pages=[],
            fields=[],
            quality_gate=QualityGate(status="pass"),
        )

        json_str = result.model_dump_json()
        assert '"schema_version":"extraction_result_v1"' in json_str


class TestFieldProvenanceValidation:
    """Tests for FieldProvenance validation."""

    def test_valid_provenance(self):
        """Test valid provenance creation."""
        prov = FieldProvenance(
            page=1,
            method="di_text",
            text_quote="sample text",
            char_start=0,
            char_end=11,
        )
        assert prov.page == 1
        assert prov.method == "di_text"

    def test_invalid_method(self):
        """Test invalid method is rejected."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                page=1,
                method="invalid_method",  # Not in Literal
                text_quote="sample text",
                char_start=0,
                char_end=11,
            )

    def test_negative_char_start(self):
        """Test negative char_start is rejected."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                page=1,
                method="di_text",
                text_quote="sample text",
                char_start=-1,  # Invalid
                char_end=11,
            )


class TestQualityGateValidation:
    """Tests for QualityGate validation."""

    def test_valid_status_values(self):
        """Test all valid status values."""
        for status in ["pass", "warn", "fail"]:
            gate = QualityGate(status=status)
            assert gate.status == status

    def test_invalid_status(self):
        """Test invalid status is rejected."""
        with pytest.raises(ValidationError):
            QualityGate(status="invalid")
