"""Unit tests for Vehicle Registration extractor.

Tests the VehicleRegistrationExtractor which uses OpenAI Vision API
to extract fields from Swiss vehicle registration documents (Fahrzeugausweis).
"""

import hashlib
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path
import tempfile
from PIL import Image

from context_builder.extraction.spec_loader import get_spec, list_available_specs
from context_builder.extraction.base import ExtractorFactory, FieldExtractor
from context_builder.extraction.extractors.generic import GenericFieldExtractor
from context_builder.extraction.extractors.vehicle_registration import VehicleRegistrationExtractor
from context_builder.schemas.extraction_result import (
    PageContent,
    DocumentMetadata,
    ExtractionRunMetadata,
)


def make_page_content(page: int, text: str) -> PageContent:
    """Helper to create PageContent with computed text_md5."""
    return PageContent(
        page=page,
        text=text,
        text_md5=hashlib.md5(text.encode()).hexdigest(),
    )


def make_doc_meta(doc_id: str = "doc_abc", source_file_path: str = None) -> DocumentMetadata:
    """Helper to create DocumentMetadata."""
    return DocumentMetadata(
        doc_id=doc_id,
        claim_id="CLM001",
        doc_type="vehicle_registration",
        doc_type_confidence=0.95,
        language="de",
        page_count=1,
        source_file_path=source_file_path,
    )


def make_run_meta(run_id: str = "run_20260115_120000") -> ExtractionRunMetadata:
    """Helper to create ExtractionRunMetadata."""
    return ExtractionRunMetadata(
        run_id=run_id,
        extractor_version="v1.0.0",
        model="gpt-4o",
        prompt_version="vehicle_registration_extraction_v1",
        input_hashes={"file_md5": "abc123", "content_md5": "def456"},
    )


class TestVehicleRegistrationSpecExists:
    """Tests that vehicle_registration spec is properly configured."""

    def test_spec_in_available_specs(self):
        """Test that vehicle_registration appears in available specs."""
        specs = list_available_specs()
        assert "vehicle_registration" in specs

    def test_spec_loads_successfully(self):
        """Test that vehicle_registration spec loads without errors."""
        spec = get_spec("vehicle_registration")
        assert spec is not None
        assert spec.doc_type == "vehicle_registration"

    def test_spec_has_required_fields(self):
        """Test that spec defines required fields."""
        spec = get_spec("vehicle_registration")
        expected_required = ["plate_number", "owner_name"]
        for field in expected_required:
            assert field in spec.required_fields, f"Missing required field: {field}"

    def test_spec_has_optional_fields(self):
        """Test that spec defines optional fields."""
        spec = get_spec("vehicle_registration")
        expected_optional = ["vin", "make", "model", "year", "color", "registration_date", "expiry_date"]
        for field in expected_optional:
            assert field in spec.optional_fields, f"Missing optional field: {field}"


class TestVehicleRegistrationExtractorRegistration:
    """Tests for extractor factory registration."""

    def test_extractor_registered(self):
        """Test that VehicleRegistrationExtractor is registered."""
        assert ExtractorFactory.is_supported("vehicle_registration")

    def test_extractor_is_vehicle_registration_class(self):
        """Test that factory returns VehicleRegistrationExtractor."""
        extractor = ExtractorFactory.create("vehicle_registration")

        assert extractor.__class__.__name__ == "VehicleRegistrationExtractor"
        assert isinstance(extractor, FieldExtractor)
        assert isinstance(extractor, VehicleRegistrationExtractor)
        # Should NOT be the generic extractor
        assert not isinstance(extractor, GenericFieldExtractor)

    def test_extractor_has_correct_doc_type(self):
        """Test that extractor has correct doc_type."""
        extractor = ExtractorFactory.create("vehicle_registration")
        assert extractor.doc_type == "vehicle_registration"


class TestVehicleRegistrationExtractorConfig:
    """Tests for extractor configuration."""

    def test_extractor_version(self):
        """Test that extractor has version defined."""
        assert VehicleRegistrationExtractor.EXTRACTOR_VERSION == "v1.0.0"

    def test_prompt_name(self):
        """Test that extractor has prompt name defined."""
        assert VehicleRegistrationExtractor.PROMPT_NAME == "vehicle_registration_extraction"

    def test_default_model(self):
        """Test that extractor uses gpt-4o by default."""
        extractor = ExtractorFactory.create("vehicle_registration")
        assert extractor.model == "gpt-4o"


class TestVehicleRegistrationVisionExtraction:
    """Tests for vision-based extraction."""

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_vision_extract_with_image(self, mock_audit_service, mock_openai):
        """Test vision extraction when source image file exists."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "fields": [
                            {"name": "owner_name", "value": "Ramadani Dzevahir", "text_quote": "Ramadani Dzevahir", "confidence": 0.95},
                            {"name": "plate_number", "value": "ZH 123456", "text_quote": "ZH 123456", "confidence": 0.98},
                            {"name": "vin", "value": "WVWZZZ3CZWE123456", "text_quote": "WVWZZZ3CZWE123456", "confidence": 0.9},
                        ]
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        # Create a temporary valid image file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = f.name
        Image.new("RGB", (200, 200), color="white").save(temp_path, format="JPEG")

        try:
            extractor = ExtractorFactory.create("vehicle_registration")
            pages = [make_page_content(1, "Some OCR text")]
            doc_meta = make_doc_meta(source_file_path=temp_path)
            run_meta = make_run_meta()

            result = extractor.extract(pages, doc_meta, run_meta)

            # Verify fields were extracted
            field_names = {f.name for f in result.fields}
            assert "owner_name" in field_names
            assert "plate_number" in field_names

            # Check owner_name value
            owner_field = next(f for f in result.fields if f.name == "owner_name")
            assert owner_field.value == "Ramadani Dzevahir"
            assert owner_field.status == "present"

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_text_fallback_when_no_source_file(self, mock_audit_service, mock_openai):
        """Test text fallback when no source file is available."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        extractor = ExtractorFactory.create("vehicle_registration")

        # Text with some vehicle registration info
        text = """
        Fahrzeugausweis
        Kontrollschild: ZH 123456
        Name, Vornamen: Mueller Hans
        Marke: TOYOTA
        """
        pages = [make_page_content(1, text)]
        doc_meta = make_doc_meta(source_file_path=None)
        run_meta = make_run_meta()

        result = extractor.extract(pages, doc_meta, run_meta)

        # Should have attempted text extraction
        assert result is not None
        assert len(result.fields) > 0

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_quality_gate_pass_with_required_fields(self, mock_audit_service, mock_openai):
        """Test quality gate passes when required fields are extracted."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "fields": [
                            {"name": "owner_name", "value": "Test Owner", "text_quote": "Test Owner", "confidence": 0.9},
                            {"name": "plate_number", "value": "ZH 999888", "text_quote": "ZH 999888", "confidence": 0.95},
                        ]
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
        Image.new("RGB", (200, 200), color="white").save(temp_path, format="PNG")

        try:
            extractor = ExtractorFactory.create("vehicle_registration")
            pages = [make_page_content(1, "")]
            doc_meta = make_doc_meta(source_file_path=temp_path)
            run_meta = make_run_meta()

            result = extractor.extract(pages, doc_meta, run_meta)

            # Quality gate should pass with both required fields present
            assert result.quality_gate.status == "pass"
            assert len(result.quality_gate.missing_required_fields) == 0

        finally:
            Path(temp_path).unlink(missing_ok=True)

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_quality_gate_fail_missing_required(self, mock_audit_service, mock_openai):
        """Test quality gate fails when required field is missing."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps({
                        "fields": [
                            # Missing owner_name
                            {"name": "plate_number", "value": "ZH 999888", "text_quote": "ZH 999888", "confidence": 0.95},
                        ]
                    })
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
        Image.new("RGB", (200, 200), color="white").save(temp_path, format="PNG")

        try:
            extractor = ExtractorFactory.create("vehicle_registration")
            pages = [make_page_content(1, "")]
            doc_meta = make_doc_meta(source_file_path=temp_path)
            run_meta = make_run_meta()

            result = extractor.extract(pages, doc_meta, run_meta)

            # Quality gate should fail with missing required field
            assert result.quality_gate.status == "fail"
            assert "owner_name" in result.quality_gate.missing_required_fields

        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestVehicleRegistrationParseResponse:
    """Tests for vision response parsing."""

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_parse_json_with_code_block(self, mock_audit_service, mock_openai):
        """Test parsing JSON response wrapped in markdown code block."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        extractor = ExtractorFactory.create("vehicle_registration")
        pages = [make_page_content(1, "test")]

        # JSON wrapped in code block
        content = '''```json
{
  "fields": [
    {"name": "owner_name", "value": "Test User", "text_quote": "Test User", "confidence": 0.9}
  ]
}
```'''

        fields = extractor._parse_vision_response(content, pages)

        owner_field = next((f for f in fields if f.name == "owner_name"), None)
        assert owner_field is not None
        assert owner_field.value == "Test User"

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_parse_invalid_json_returns_missing_fields(self, mock_audit_service, mock_openai):
        """Test that invalid JSON returns missing fields for all spec fields."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        extractor = ExtractorFactory.create("vehicle_registration")
        pages = [make_page_content(1, "test")]

        content = "This is not valid JSON"

        fields = extractor._parse_vision_response(content, pages)

        # Should have all fields from spec, all marked missing
        assert len(fields) > 0
        assert all(f.status == "missing" for f in fields)


class TestVehicleRegistrationImageEncoding:
    """Tests for image encoding methods."""

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_encode_image_jpg(self, mock_audit_service, mock_openai):
        """Test encoding JPEG image."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        extractor = ExtractorFactory.create("vehicle_registration")

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_path = Path(f.name)
        Image.new("RGB", (100, 100), color="red").save(temp_path, format="JPEG")

        try:
            base64_data, mime_type = extractor._encode_image(temp_path)

            assert base64_data is not None
            assert mime_type == "image/jpeg"
        finally:
            temp_path.unlink(missing_ok=True)

    @patch("context_builder.extraction.extractors.vehicle_registration.get_openai_client")
    @patch("context_builder.extraction.extractors.vehicle_registration.get_llm_audit_service")
    def test_encode_image_png(self, mock_audit_service, mock_openai):
        """Test encoding PNG image returns JPEG after preprocessing."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        extractor = ExtractorFactory.create("vehicle_registration")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = Path(f.name)
        Image.new("RGB", (100, 100), color="blue").save(temp_path, format="PNG")

        try:
            base64_data, mime_type = extractor._encode_image(temp_path)

            assert base64_data is not None
            # After preprocessing, all images are JPEG
            assert mime_type == "image/jpeg"
        finally:
            temp_path.unlink(missing_ok=True)


class TestDocumentMetadataSourcePath:
    """Tests for DocumentMetadata with source_file_path."""

    def test_source_file_path_optional(self):
        """Test that source_file_path is optional."""
        meta = DocumentMetadata(
            doc_id="doc_abc",
            claim_id="CLM001",
            doc_type="vehicle_registration",
            doc_type_confidence=0.95,
            language="de",
            page_count=1,
        )
        assert meta.source_file_path is None

    def test_source_file_path_can_be_set(self):
        """Test that source_file_path can be set."""
        meta = DocumentMetadata(
            doc_id="doc_abc",
            claim_id="CLM001",
            doc_type="vehicle_registration",
            doc_type_confidence=0.95,
            language="de",
            page_count=1,
            source_file_path="/path/to/file.pdf",
        )
        assert meta.source_file_path == "/path/to/file.pdf"
