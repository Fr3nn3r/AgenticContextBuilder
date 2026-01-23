"""Unit tests for NSA Guarantee extractor."""

import hashlib
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from context_builder.extraction.spec_loader import get_spec, list_available_specs
from context_builder.extraction.base import ExtractorFactory
from context_builder.extraction.extractors.nsa_guarantee import NsaGuaranteeExtractor
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


class TestNsaGuaranteeSpecExists:
    """Tests that NSA Guarantee spec is properly configured."""

    def test_spec_in_available_specs(self):
        """Test that nsa_guarantee appears in available specs."""
        specs = list_available_specs()
        assert "nsa_guarantee" in specs

    def test_spec_loads_successfully(self):
        """Test that nsa_guarantee spec loads without errors."""
        spec = get_spec("nsa_guarantee")
        assert spec is not None
        assert spec.doc_type == "nsa_guarantee"

    def test_spec_has_required_fields(self):
        """Test that spec defines required fields."""
        spec = get_spec("nsa_guarantee")
        expected_required = [
            "policy_number",
            "guarantee_type",
            "start_date",
            "end_date",
            "policyholder_name",
            "vehicle_make",
            "vehicle_model",
            "vehicle_vin",
        ]
        for field in expected_required:
            assert field in spec.required_fields, f"Missing required field: {field}"

    def test_spec_has_optional_fields(self):
        """Test that spec defines optional fields."""
        spec = get_spec("nsa_guarantee")
        assert len(spec.optional_fields) > 0
        # Check some key optional fields
        assert "covered_components" in spec.optional_fields
        assert "excluded_components" in spec.optional_fields
        assert "coverage_scale" in spec.optional_fields

    def test_spec_field_rules_defined(self):
        """Test that field rules are defined for key fields."""
        spec = get_spec("nsa_guarantee")
        # Check some key field rules
        assert "policy_number" in spec.field_rules
        assert "start_date" in spec.field_rules
        assert "vehicle_vin" in spec.field_rules

    def test_spec_field_rule_normalizers(self):
        """Test that field rules have appropriate normalizers."""
        spec = get_spec("nsa_guarantee")
        # Swiss date normalizer for date fields
        assert spec.field_rules["start_date"].normalize == "swiss_date_to_iso"
        assert spec.field_rules["end_date"].normalize == "swiss_date_to_iso"
        # VIN validator
        assert spec.field_rules["vehicle_vin"].validate == "vin_format"


class TestNsaGuaranteeExtractorRegistration:
    """Tests for extractor factory registration."""

    def test_extractor_registered(self):
        """Test that NsaGuaranteeExtractor is registered for nsa_guarantee."""
        assert ExtractorFactory.is_supported("nsa_guarantee")

    def test_extractor_is_nsa_guarantee_class(self):
        """Test that factory returns NsaGuaranteeExtractor, not GenericFieldExtractor."""
        # Create extractor via factory
        extractor = ExtractorFactory.create("nsa_guarantee")
        assert isinstance(extractor, NsaGuaranteeExtractor)

    def test_extractor_has_correct_doc_type(self):
        """Test that extractor has correct doc_type."""
        extractor = ExtractorFactory.create("nsa_guarantee")
        assert extractor.doc_type == "nsa_guarantee"


class TestNsaGuaranteeExtractorConfig:
    """Tests for extractor configuration."""

    def test_metadata_pages(self):
        """Test that metadata pages are correctly configured."""
        assert NsaGuaranteeExtractor.METADATA_PAGES == [1]

    def test_component_pages(self):
        """Test that component pages are correctly configured."""
        assert NsaGuaranteeExtractor.COMPONENT_PAGES == [2, 3]

    def test_component_fields(self):
        """Test that component fields are correctly identified."""
        expected = {"covered_components", "excluded_components", "coverage_scale"}
        assert NsaGuaranteeExtractor.COMPONENT_FIELDS == expected

    def test_component_categories(self):
        """Test that component categories are defined."""
        categories = NsaGuaranteeExtractor.COMPONENT_CATEGORIES
        assert len(categories) > 0
        # Check some expected categories
        assert "engine" in categories
        assert "brakes" in categories
        assert "steering" in categories


class TestNsaGuaranteeExtractorInit:
    """Tests for extractor initialization."""

    @patch("context_builder.extraction.extractors.nsa_guarantee.OpenAI")
    @patch("context_builder.extraction.extractors.nsa_guarantee.get_llm_audit_service")
    def test_init_with_defaults(self, mock_audit, mock_openai):
        """Test extractor initializes with default values."""
        mock_audit.return_value = Mock()
        mock_openai.return_value = Mock()

        extractor = ExtractorFactory.create("nsa_guarantee")

        assert extractor.model == "gpt-4o"  # From prompt config
        assert extractor.temperature == 0.1

    @patch("context_builder.extraction.extractors.nsa_guarantee.OpenAI")
    @patch("context_builder.extraction.extractors.nsa_guarantee.get_llm_audit_service")
    def test_init_with_model_override(self, mock_audit, mock_openai):
        """Test extractor accepts model override."""
        mock_audit.return_value = Mock()
        mock_openai.return_value = Mock()

        extractor = ExtractorFactory.create("nsa_guarantee", model="gpt-4o-mini")

        assert extractor.model == "gpt-4o-mini"


class TestNsaGuaranteeExtractorExtraction:
    """Tests for extraction logic."""

    @pytest.fixture
    def mock_extractor(self):
        """Create extractor with mocked LLM client."""
        with patch("context_builder.extraction.extractors.nsa_guarantee.OpenAI") as mock_openai, \
             patch("context_builder.extraction.extractors.nsa_guarantee.get_llm_audit_service") as mock_audit:
            mock_audit.return_value = Mock()
            mock_client = Mock()
            mock_openai.return_value = mock_client

            extractor = ExtractorFactory.create("nsa_guarantee")

            # Mock the audited client
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "fields": [
                    {
                        "name": "policy_number",
                        "value": "625928",
                        "text_quote": "Policy Number: 625928",
                        "confidence": 0.95,
                        "is_placeholder": False,
                    },
                    {
                        "name": "vehicle_vin",
                        "value": "WVWZZZ3CZWE123456",
                        "text_quote": "VIN: WVWZZZ3CZWE123456",
                        "confidence": 0.90,
                        "is_placeholder": False,
                    },
                ]
            })
            extractor.audited_client.chat_completions_create = Mock(return_value=mock_response)
            extractor.audited_client.set_context = Mock()
            extractor.audited_client.set_injected_context = Mock()
            extractor.audited_client.get_call_id = Mock(return_value="test-call-id")

            # Mock decision storage
            extractor._decision_storage = Mock()
            extractor._decision_storage.append = Mock()

            yield extractor

    @pytest.fixture
    def sample_pages(self):
        """Create sample page content."""
        page1 = make_page_content(
            page=1,
            text="Policy Number: 625928\nVIN: WVWZZZ3CZWE123456\nStart: 31.12.2025",
        )
        page2 = make_page_content(
            page=2,
            text="Covered components:\n- Engine: Pistons, Crankshaft\n- Brakes: Master cylinder",
        )
        page3 = make_page_content(
            page=3,
            text="Not covered:\n- Engine: Timing belt\nCoverage scale: 50000 km = 80%",
        )
        return [page1, page2, page3]

    @pytest.fixture
    def sample_doc_meta(self):
        """Create sample document metadata."""
        return DocumentMetadata(
            doc_id="test-doc-123",
            claim_id="claim-456",
            doc_type="nsa_guarantee",
            doc_type_confidence=0.95,
            language="de",
            page_count=3,
        )

    @pytest.fixture
    def sample_run_meta(self):
        """Create sample run metadata."""
        return ExtractionRunMetadata(
            run_id="run-789",
            model="gpt-4o",
            extractor_version="v1.0.0",
            prompt_version="v1.0",
        )

    def test_extract_filters_pages_for_metadata(self, mock_extractor, sample_pages, sample_doc_meta, sample_run_meta):
        """Test that extract filters pages correctly for metadata extraction."""
        # Configure component extraction response too
        component_response = Mock()
        component_response.choices = [Mock()]
        component_response.choices[0].message.content = json.dumps({
            "covered": {"engine": ["Pistons"]},
            "excluded": {},
            "coverage_scale": [],
        })

        # Return different responses for metadata and components
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Metadata extraction
                response = Mock()
                response.choices = [Mock()]
                response.choices[0].message.content = json.dumps({
                    "fields": [
                        {"name": "policy_number", "value": "625928", "confidence": 0.9}
                    ]
                })
                return response
            else:
                # Component extraction
                return component_response

        mock_extractor.audited_client.chat_completions_create.side_effect = side_effect

        result = mock_extractor.extract(sample_pages, sample_doc_meta, sample_run_meta)

        # Should have made 2 LLM calls (metadata + components)
        assert mock_extractor.audited_client.chat_completions_create.call_count == 2

    def test_extract_returns_extraction_result(self, mock_extractor, sample_pages, sample_doc_meta, sample_run_meta):
        """Test that extract returns ExtractionResult."""
        # Configure component extraction response
        component_response = Mock()
        component_response.choices = [Mock()]
        component_response.choices[0].message.content = json.dumps({
            "covered": {},
            "excluded": {},
            "coverage_scale": [],
        })

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                response = Mock()
                response.choices = [Mock()]
                response.choices[0].message.content = json.dumps({"fields": []})
                return response
            return component_response

        mock_extractor.audited_client.chat_completions_create.side_effect = side_effect

        result = mock_extractor.extract(sample_pages, sample_doc_meta, sample_run_meta)

        assert result is not None
        assert result.schema_version == "extraction_result_v1"
        assert result.doc.doc_type == "nsa_guarantee"

    def test_extract_logs_decision(self, mock_extractor, sample_pages, sample_doc_meta, sample_run_meta):
        """Test that extract logs decision to compliance ledger."""
        component_response = Mock()
        component_response.choices = [Mock()]
        component_response.choices[0].message.content = json.dumps({
            "covered": {},
            "excluded": {},
            "coverage_scale": [],
        })

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                response = Mock()
                response.choices = [Mock()]
                response.choices[0].message.content = json.dumps({"fields": []})
                return response
            return component_response

        mock_extractor.audited_client.chat_completions_create.side_effect = side_effect

        mock_extractor.extract(sample_pages, sample_doc_meta, sample_run_meta)

        # Should have logged decision
        mock_extractor._decision_storage.append.assert_called_once()


class TestNsaGuaranteeExtractorBuildExtractedFields:
    """Tests for _build_extracted_fields method."""

    @pytest.fixture
    def mock_extractor(self):
        """Create extractor with mocked dependencies."""
        with patch("context_builder.extraction.extractors.nsa_guarantee.OpenAI"), \
             patch("context_builder.extraction.extractors.nsa_guarantee.get_llm_audit_service"):
            return ExtractorFactory.create("nsa_guarantee")

    def test_normalizes_values(self, mock_extractor):
        """Test that values are normalized according to field rules."""
        raw = {
            "fields": [
                {
                    "name": "start_date",
                    "value": "31.12.2025",
                    "confidence": 0.9,
                }
            ]
        }
        pages = [make_page_content(page=1, text="Start: 31.12.2025")]

        fields = mock_extractor._build_extracted_fields(raw, pages, ["start_date"])

        assert len(fields) == 1
        assert fields[0].normalized_value == "2025-12-31"

    def test_handles_missing_fields(self, mock_extractor):
        """Test that missing fields are handled gracefully."""
        raw = {"fields": []}
        pages = [make_page_content(page=1, text="test")]

        fields = mock_extractor._build_extracted_fields(raw, pages, ["policy_number"])

        # Should return empty list (missing fields are added later in extract())
        assert len(fields) == 0


class TestNsaGuaranteeExtractorComponentExtraction:
    """Tests for component extraction logic."""

    @pytest.fixture
    def mock_extractor(self):
        """Create extractor with mocked dependencies."""
        with patch("context_builder.extraction.extractors.nsa_guarantee.OpenAI") as mock_openai, \
             patch("context_builder.extraction.extractors.nsa_guarantee.get_llm_audit_service") as mock_audit:
            mock_audit.return_value = Mock()
            mock_openai.return_value = Mock()

            extractor = ExtractorFactory.create("nsa_guarantee")
            extractor.audited_client.chat_completions_create = Mock()
            extractor.audited_client.set_injected_context = Mock()

            yield extractor

    def test_extract_components_parses_covered(self, mock_extractor):
        """Test that covered components are parsed correctly."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = json.dumps({
            "covered": {
                "engine": ["Pistons", "Crankshaft"],
                "brakes": ["Master cylinder"],
            },
            "excluded": {},
            "coverage_scale": [],
        })
        mock_extractor.audited_client.chat_completions_create.return_value = response

        pages = [make_page_content(page=2, text="Component list")]
        fields = mock_extractor._extract_components(pages)

        covered_field = next(f for f in fields if f.name == "covered_components")
        assert covered_field.status == "present"
        # normalized_value is a JSON string, parse it to check
        covered_data = json.loads(covered_field.normalized_value)
        assert "engine" in covered_data
        assert "Pistons" in covered_data["engine"]

    def test_extract_components_parses_excluded(self, mock_extractor):
        """Test that excluded components are parsed correctly."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = json.dumps({
            "covered": {},
            "excluded": {
                "engine": ["Timing belt"],
            },
            "coverage_scale": [],
        })
        mock_extractor.audited_client.chat_completions_create.return_value = response

        pages = [make_page_content(page=2, text="Component list")]
        fields = mock_extractor._extract_components(pages)

        excluded_field = next(f for f in fields if f.name == "excluded_components")
        assert excluded_field.status == "present"
        # normalized_value is a JSON string, parse it to check
        excluded_data = json.loads(excluded_field.normalized_value)
        assert "engine" in excluded_data

    def test_extract_components_parses_coverage_scale(self, mock_extractor):
        """Test that coverage scale is parsed correctly."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = json.dumps({
            "covered": {},
            "excluded": {},
            "coverage_scale": [
                {"km_threshold": 50000, "coverage_percent": 80},
                {"km_threshold": 80000, "coverage_percent": 60},
            ],
        })
        mock_extractor.audited_client.chat_completions_create.return_value = response

        pages = [make_page_content(page=2, text="Coverage scale")]
        fields = mock_extractor._extract_components(pages)

        scale_field = next(f for f in fields if f.name == "coverage_scale")
        assert scale_field.status == "present"
        # normalized_value is a JSON string, parse it to check
        scale_data = json.loads(scale_field.normalized_value)
        assert len(scale_data) == 2

    def test_extract_components_handles_empty_pages(self, mock_extractor):
        """Test that empty pages are handled gracefully."""
        fields = mock_extractor._extract_components([])

        assert len(fields) == 0
