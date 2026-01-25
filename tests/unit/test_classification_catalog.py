"""Unit tests for document type catalog and classification prompt."""

import pytest
import yaml

from context_builder.classification.openai_classifier import (
    load_doc_type_catalog,
    format_doc_type_catalog,
    DOC_TYPE_CATALOG_PATH,
)
from context_builder.schemas.document_classification import (
    DocumentClassification,
    ClaimsDocumentType,
)
from context_builder.utils.prompt_loader import load_prompt


def _load_repo_default_catalog():
    """Load the repo default catalog directly, bypassing workspace overrides."""
    with open(DOC_TYPE_CATALOG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("doc_types", [])


class TestDocTypeCatalog:
    """Test cases for document type catalog loading."""

    def test_catalog_file_exists(self):
        """Test that the catalog YAML file exists."""
        assert DOC_TYPE_CATALOG_PATH.exists(), (
            f"Catalog file not found: {DOC_TYPE_CATALOG_PATH}"
        )

    def test_catalog_loads_successfully(self):
        """Test that catalog loads without errors."""
        doc_types = load_doc_type_catalog()
        assert doc_types is not None
        assert len(doc_types) > 0

    def test_repo_default_catalog_has_required_doc_types(self):
        """Test that repo default catalog contains all required document types."""
        # Load repo default catalog directly (bypasses workspace overrides)
        doc_types = _load_repo_default_catalog()
        doc_type_names = [d["doc_type"] for d in doc_types]

        expected_types = [
            "fnol_form",
            "insurance_policy",
            "police_report",
            "invoice",
            "id_document",
            "vehicle_registration",
            "certificate",
            "medical_report",
            "travel_itinerary",
            "customer_comm",
            "supporting_document",
            "damage_evidence",
        ]

        for expected in expected_types:
            assert expected in doc_type_names, f"Missing doc_type: {expected}"

    def test_catalog_entries_have_required_fields(self):
        """Test that each catalog entry has description and cues."""
        doc_types = load_doc_type_catalog()

        for entry in doc_types:
            assert "doc_type" in entry, f"Missing doc_type in entry: {entry}"
            assert "description" in entry, f"Missing description for {entry.get('doc_type')}"
            assert "cues" in entry, f"Missing cues for {entry.get('doc_type')}"
            assert len(entry["cues"]) >= 3, (
                f"Doc type {entry['doc_type']} should have at least 3 cues"
            )

    def test_format_doc_type_catalog(self):
        """Test that catalog formats correctly for prompt injection."""
        doc_types = load_doc_type_catalog()
        formatted = format_doc_type_catalog(doc_types)

        assert formatted is not None
        assert len(formatted) > 0
        # Check that at least one doc type from the loaded catalog appears
        assert doc_types[0]["doc_type"] in formatted
        assert "Cues:" in formatted


class TestClassificationSchema:
    """Test cases for DocumentClassification schema."""

    def test_valid_classification_response(self):
        """Test that a valid classification response validates."""
        response = {
            "document_type": "fnol_form",
            "language": "en",
            "confidence": 0.95,
            "summary": "This is a first notice of loss form.",
            "signals": ["FNOL header", "claim number field", "incident date"],
            "key_hints": {"claim_reference": "CLM-12345"},
        }

        validated = DocumentClassification.model_validate(response)
        assert validated.document_type == "fnol_form"
        assert validated.confidence == 0.95
        assert len(validated.signals) == 3

    def test_classification_without_key_hints(self):
        """Test that key_hints is optional."""
        response = {
            "document_type": "invoice",
            "language": "es",
            "confidence": 0.85,
            "summary": "Invoice for medical services.",
            "signals": ["FACTURA header", "total amount"],
        }

        validated = DocumentClassification.model_validate(response)
        assert validated.key_hints is None

    def test_classification_confidence_bounds(self):
        """Test that confidence must be between 0 and 1."""
        base_response = {
            "document_type": "invoice",
            "language": "en",
            "summary": "Test",
            "signals": [],
        }

        # Valid confidence
        response = {**base_response, "confidence": 0.5}
        validated = DocumentClassification.model_validate(response)
        assert validated.confidence == 0.5

        # Invalid: > 1.0
        with pytest.raises(Exception):
            response = {**base_response, "confidence": 1.5}
            DocumentClassification.model_validate(response)

        # Invalid: < 0.0
        with pytest.raises(Exception):
            response = {**base_response, "confidence": -0.1}
            DocumentClassification.model_validate(response)

    def test_claims_document_type_enum(self):
        """Test that enum contains all expected values."""
        expected_values = {
            "fnol_form",
            "insurance_policy",
            "police_report",
            "invoice",
            "id_document",
            "vehicle_registration",
            "certificate",
            "medical_report",
            "travel_itinerary",
            "customer_comm",
            "supporting_document",
            "damage_evidence",
        }

        enum_values = {e.value for e in ClaimsDocumentType}
        assert expected_values == enum_values


class TestClassificationPrompt:
    """Test cases for classification prompt rendering."""

    def test_prompt_loads_successfully(self):
        """Test that classification prompt loads without errors."""
        prompt_data = load_prompt(
            "claims_document_classification",
            text_content="Sample document text",
            filename="test.pdf",
            doc_type_catalog="- fnol_form: Test description",
        )

        assert "config" in prompt_data
        assert "messages" in prompt_data
        assert len(prompt_data["messages"]) >= 2

    def test_prompt_injects_catalog(self):
        """Test that doc_type_catalog is injected into prompt."""
        catalog_text = "- fnol_form: First notice of loss\n- invoice: Invoice document"

        prompt_data = load_prompt(
            "claims_document_classification",
            text_content="Sample text",
            filename="doc.pdf",
            doc_type_catalog=catalog_text,
        )

        # Find user message
        user_message = next(
            (m for m in prompt_data["messages"] if m["role"] == "user"),
            None
        )

        assert user_message is not None
        assert "fnol_form" in user_message["content"]
        assert "invoice" in user_message["content"]

    def test_prompt_config_is_valid(self):
        """Test that prompt configuration has required fields."""
        prompt_data = load_prompt(
            "claims_document_classification",
            text_content="Test",
            filename="test.pdf",
            doc_type_catalog="",
        )

        config = prompt_data["config"]
        assert "model" in config
        assert "temperature" in config
        assert config["temperature"] <= 0.3  # Should be low for classification
