"""Unit tests for NSA Guarantee extractor.

Note: The NSA extractors are loaded dynamically from workspace config/extractors/.
Tests use workspace_extractors module path for patching.
"""

import hashlib
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from context_builder.extraction.spec_loader import get_spec, list_available_specs
from context_builder.extraction.base import ExtractorFactory, FieldExtractor
from context_builder.extraction.extractors.generic import GenericFieldExtractor
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


def get_nsa_guarantee_extractor_class():
    """Get the NsaGuaranteeExtractor class from the registered extractor."""
    with patch("workspace_extractors.nsa_guarantee.get_openai_client"), \
         patch("workspace_extractors.nsa_guarantee.get_llm_audit_service"):
        extractor = ExtractorFactory.create("nsa_guarantee")
    return extractor.__class__


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

    @patch("workspace_extractors.nsa_guarantee.get_openai_client")
    @patch("workspace_extractors.nsa_guarantee.get_llm_audit_service")
    def test_extractor_is_nsa_guarantee_class(self, mock_audit, mock_openai):
        """Test that factory returns NsaGuaranteeExtractor, not GenericFieldExtractor."""
        extractor = ExtractorFactory.create("nsa_guarantee")

        # Should be a NsaGuaranteeExtractor (loaded from workspace)
        assert extractor.__class__.__name__ == "NsaGuaranteeExtractor"
        # Should inherit from FieldExtractor base class
        assert isinstance(extractor, FieldExtractor)
        # Should NOT be the generic extractor
        assert not isinstance(extractor, GenericFieldExtractor)

    @patch("workspace_extractors.nsa_guarantee.get_openai_client")
    @patch("workspace_extractors.nsa_guarantee.get_llm_audit_service")
    def test_extractor_has_correct_doc_type(self, mock_audit, mock_openai):
        """Test that extractor has correct doc_type."""
        extractor = ExtractorFactory.create("nsa_guarantee")
        assert extractor.doc_type == "nsa_guarantee"


class TestNsaGuaranteeExtractorConfig:
    """Tests for extractor configuration."""

    def test_metadata_pages(self):
        """Test that metadata pages are correctly configured."""
        ExtractorClass = get_nsa_guarantee_extractor_class()
        assert ExtractorClass.METADATA_PAGES == [1]

    def test_component_pages(self):
        """Test that component pages are correctly configured."""
        ExtractorClass = get_nsa_guarantee_extractor_class()
        assert ExtractorClass.COMPONENT_PAGES == [2, 3]

    def test_component_fields(self):
        """Test that component fields are correctly identified."""
        ExtractorClass = get_nsa_guarantee_extractor_class()
        expected = {"covered_components", "excluded_components", "coverage_scale"}
        assert ExtractorClass.COMPONENT_FIELDS == expected

    def test_component_categories(self):
        """Test that component categories are defined."""
        ExtractorClass = get_nsa_guarantee_extractor_class()
        categories = ExtractorClass.COMPONENT_CATEGORIES
        assert len(categories) > 0
        # Check some expected categories
        assert "engine" in categories
        assert "brakes" in categories
        assert "steering" in categories


class TestNsaGuaranteeExtractorInit:
    """Tests for extractor initialization."""

    @patch("workspace_extractors.nsa_guarantee.get_openai_client")
    @patch("workspace_extractors.nsa_guarantee.get_llm_audit_service")
    def test_init_with_defaults(self, mock_audit, mock_openai):
        """Test extractor initializes with default values."""
        mock_audit.return_value = Mock()
        mock_openai.return_value = Mock()

        extractor = ExtractorFactory.create("nsa_guarantee")

        assert extractor.model == "gpt-4o"  # From prompt config
        assert extractor.temperature == 0.1

    @patch("workspace_extractors.nsa_guarantee.get_openai_client")
    @patch("workspace_extractors.nsa_guarantee.get_llm_audit_service")
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
        with patch("workspace_extractors.nsa_guarantee.get_openai_client") as mock_openai, \
             patch("workspace_extractors.nsa_guarantee.get_llm_audit_service") as mock_audit:
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

    @patch('workspace_extractors.nsa_guarantee.get_openai_client')
    def test_extract_filters_pages_for_metadata(self, mock_openai_class, mock_extractor, sample_pages, sample_doc_meta, sample_run_meta):
        """Test that extract filters pages correctly for metadata extraction.

        With chunked extraction, metadata uses 4 parallel OpenAI clients (one per group),
        while components still uses the audited_client.
        """
        # Configure mock for parallel metadata group extraction (4 groups)
        mock_openai_instance = Mock()
        mock_openai_class.return_value = mock_openai_instance

        def create_metadata_response(*args, **kwargs):
            response = Mock()
            response.choices = [Mock()]
            response.choices[0].message.content = json.dumps({
                "fields": [
                    {"name": "policy_number", "value": "625928", "confidence": 0.9}
                ]
            })
            response.usage = Mock(prompt_tokens=100, completion_tokens=50)
            return response

        mock_openai_instance.chat.completions.create.side_effect = create_metadata_response

        # Configure component extraction response (uses audited_client)
        component_response = Mock()
        component_response.choices = [Mock()]
        component_response.choices[0].message.content = json.dumps({
            "covered": {"engine": ["Pistons"]},
            "excluded": {},
            "coverage_scale": [],
        })
        component_response.usage = Mock(prompt_tokens=200, completion_tokens=100)

        mock_extractor.audited_client.chat_completions_create.return_value = component_response

        result = mock_extractor.extract(sample_pages, sample_doc_meta, sample_run_meta)

        # Should have made 4 metadata group calls via OpenAI()
        assert mock_openai_instance.chat.completions.create.call_count == 4

        # Should have made 1 component call via audited_client
        assert mock_extractor.audited_client.chat_completions_create.call_count == 1

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
        with patch("workspace_extractors.nsa_guarantee.get_openai_client"), \
             patch("workspace_extractors.nsa_guarantee.get_llm_audit_service"):
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
        # Normalizers now preserve raw values (type coercion only)
        assert fields[0].normalized_value == "31.12.2025"

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
        with patch("workspace_extractors.nsa_guarantee.get_openai_client") as mock_openai, \
             patch("workspace_extractors.nsa_guarantee.get_llm_audit_service") as mock_audit:
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
        fields, structured_data = mock_extractor._extract_components(pages)

        covered_field = next(f for f in fields if f.name == "covered_components")
        assert covered_field.status == "present"
        # Actual data is now in structured_data, not normalized_value
        assert "covered_components" in structured_data
        assert "engine" in structured_data["covered_components"]
        assert "Pistons" in structured_data["covered_components"]["engine"]

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
        fields, structured_data = mock_extractor._extract_components(pages)

        excluded_field = next(f for f in fields if f.name == "excluded_components")
        assert excluded_field.status == "present"
        # Actual data is now in structured_data, not normalized_value
        assert "excluded_components" in structured_data
        assert "engine" in structured_data["excluded_components"]

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
        fields, structured_data = mock_extractor._extract_components(pages)

        scale_field = next(f for f in fields if f.name == "coverage_scale")
        assert scale_field.status == "present"
        # Actual data is now in structured_data, not normalized_value
        assert "coverage_scale" in structured_data
        assert len(structured_data["coverage_scale"]) == 2

    def test_extract_components_handles_empty_pages(self, mock_extractor):
        """Test that empty pages are handled gracefully."""
        fields, structured_data = mock_extractor._extract_components([])

        assert len(fields) == 0
        assert structured_data == {}

    def test_extract_components_includes_value_summary(self, mock_extractor):
        """Test that extracted components include human-readable value summary."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = json.dumps({
            "covered": {
                "engine": ["Pistons", "Crankshaft", "Valves"],
                "brakes": ["Master cylinder"],
            },
            "excluded": {},
            "coverage_scale": [
                {"km_threshold": 50000, "coverage_percent": 80},
                {"km_threshold": 80000, "coverage_percent": 60},
            ],
        })
        mock_extractor.audited_client.chat_completions_create.return_value = response

        pages = [make_page_content(page=2, text="Component list")]
        fields, structured_data = mock_extractor._extract_components(pages)

        # Check covered components has summary in value
        covered_field = next(f for f in fields if f.name == "covered_components")
        assert covered_field.value is not None
        assert "Engine: 3 parts" in covered_field.value
        assert "Brakes: 1 parts" in covered_field.value

        # Check coverage scale has summary in value
        scale_field = next(f for f in fields if f.name == "coverage_scale")
        assert scale_field.value is not None
        assert "100% below 50'000 km" in scale_field.value
        assert "80% from 50'000 km" in scale_field.value
        assert "60% from 80'000 km" in scale_field.value


class TestNsaGuaranteeExtractorSummaryFunctions:
    """Tests for human-readable summary functions."""

    @pytest.fixture
    def extractor(self):
        """Create extractor with mocked dependencies."""
        with patch("workspace_extractors.nsa_guarantee.get_openai_client"), \
             patch("workspace_extractors.nsa_guarantee.get_llm_audit_service"):
            return ExtractorFactory.create("nsa_guarantee")

    def test_summarize_components_empty(self, extractor):
        """Test summarize_components with empty dict."""
        result = extractor._summarize_components({})
        assert result == ""

    def test_summarize_components_single_category(self, extractor):
        """Test summarize_components with single category."""
        components = {"engine": ["Pistons", "Crankshaft", "Valves"]}
        result = extractor._summarize_components(components)
        assert result == "Engine: 3 parts"

    def test_summarize_components_multiple_categories(self, extractor):
        """Test summarize_components with multiple categories."""
        components = {
            "engine": ["Pistons", "Crankshaft"],
            "brakes": ["Master cylinder"],
            "steering": ["Rack", "Pinion", "Tie rods"],
        }
        result = extractor._summarize_components(components)
        assert "Engine: 2 parts" in result
        assert "Brakes: 1 parts" in result
        assert "Steering: 3 parts" in result

    def test_summarize_components_underscore_to_title(self, extractor):
        """Test that underscores in category names are converted to title case."""
        components = {
            "automatic_transmission": ["Torque converter"],
            "four_wd": ["Transfer case", "Diff lock"],
        }
        result = extractor._summarize_components(components)
        assert "Automatic Transmission: 1 parts" in result
        assert "Four Wd: 2 parts" in result

    def test_summarize_components_skips_empty_categories(self, extractor):
        """Test that empty categories are skipped."""
        components = {
            "engine": ["Pistons"],
            "brakes": [],
        }
        result = extractor._summarize_components(components)
        assert "Engine: 1 parts" in result
        assert "Brakes" not in result

    def test_summarize_coverage_scale_empty(self, extractor):
        """Test summarize_coverage_scale with empty list."""
        result = extractor._summarize_coverage_scale([])
        assert result == ""

    def test_summarize_coverage_scale_single_tier(self, extractor):
        """Test summarize_coverage_scale with single tier.

        Uses "a partir de" (from X km onwards) semantics with implicit 100% below first threshold.
        """
        scale = [{"km_threshold": 50000, "coverage_percent": 80}]
        result = extractor._summarize_coverage_scale(scale)
        assert "100% below 50'000 km" in result
        assert "80% from 50'000 km" in result

    def test_summarize_coverage_scale_multiple_tiers(self, extractor):
        """Test summarize_coverage_scale with multiple tiers.

        Uses "a partir de" (from X km onwards) semantics with implicit 100% below first threshold.
        """
        scale = [
            {"km_threshold": 50000, "coverage_percent": 80},
            {"km_threshold": 80000, "coverage_percent": 60},
            {"km_threshold": 110000, "coverage_percent": 40},
        ]
        result = extractor._summarize_coverage_scale(scale)
        assert "100% below 50'000 km" in result
        assert "80% from 50'000 km" in result
        assert "60% from 80'000 km" in result
        assert "40% from 110'000 km" in result

    def test_summarize_coverage_scale_swiss_format(self, extractor):
        """Test that km values use Swiss thousands separator (apostrophe)."""
        scale = [{"km_threshold": 150000, "coverage_percent": 30}]
        result = extractor._summarize_coverage_scale(scale)
        # Swiss format uses apostrophe: 150'000
        assert "150'000" in result
