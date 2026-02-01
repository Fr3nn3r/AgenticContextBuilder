"""Unit tests for document type catalog and classification prompt."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from context_builder.classification.openai_classifier import (
    load_doc_type_catalog,
    format_doc_type_catalog,
    _resolve_catalog_path,
)
from context_builder.schemas.document_classification import (
    DocumentClassification,
    ClaimsDocumentType,
)
from context_builder.utils.prompt_loader import load_prompt

_WORKSPACE_CATALOG = (
    Path(__file__).resolve().parents[2]
    / "workspaces" / "nsa" / "config" / "extraction_specs" / "doc_type_catalog.yaml"
)


def _has_workspace_catalog() -> bool:
    return _WORKSPACE_CATALOG.exists()


def _load_workspace_catalog():
    """Load the workspace catalog directly."""
    with open(_WORKSPACE_CATALOG, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("doc_types", [])


class TestDocTypeCatalog:
    """Test cases for document type catalog loading."""

    def test_resolve_returns_none_without_workspace(self, tmp_path):
        """_resolve_catalog_path returns None when workspace has no catalog."""
        with patch(
            "context_builder.classification.openai_classifier.get_workspace_config_dir",
            return_value=tmp_path,
        ):
            result = _resolve_catalog_path()
            assert result is None

    def test_resolve_returns_path_with_workspace_catalog(self, tmp_path):
        """_resolve_catalog_path returns path when workspace catalog exists."""
        specs_dir = tmp_path / "extraction_specs"
        specs_dir.mkdir()
        catalog_file = specs_dir / "doc_type_catalog.yaml"
        catalog_file.write_text("doc_types: []", encoding="utf-8")

        with patch(
            "context_builder.classification.openai_classifier.get_workspace_config_dir",
            return_value=tmp_path,
        ):
            result = _resolve_catalog_path()
            assert result == catalog_file

    def test_load_raises_without_workspace_catalog(self, tmp_path):
        """load_doc_type_catalog raises ConfigurationError without catalog."""
        with patch(
            "context_builder.classification.openai_classifier.get_workspace_config_dir",
            return_value=tmp_path,
        ):
            from context_builder.classification import ConfigurationError
            with pytest.raises(ConfigurationError, match="not found in workspace"):
                load_doc_type_catalog()

    @pytest.mark.skipif(
        not _has_workspace_catalog(),
        reason="NSA workspace catalog not available",
    )
    def test_workspace_catalog_loads_successfully(self):
        """Test that workspace catalog loads without errors."""
        with patch(
            "context_builder.classification.openai_classifier.get_workspace_config_dir",
            return_value=_WORKSPACE_CATALOG.parents[1],
        ):
            doc_types = load_doc_type_catalog()
            assert doc_types is not None
            assert len(doc_types) > 0

    @pytest.mark.skipif(
        not _has_workspace_catalog(),
        reason="NSA workspace catalog not available",
    )
    def test_workspace_catalog_entries_have_required_fields(self):
        """Test that each catalog entry has description and cues."""
        doc_types = _load_workspace_catalog()

        for entry in doc_types:
            assert "doc_type" in entry, f"Missing doc_type in entry: {entry}"
            assert "description" in entry, f"Missing description for {entry.get('doc_type')}"
            assert "cues" in entry, f"Missing cues for {entry.get('doc_type')}"
            assert len(entry["cues"]) >= 3, (
                f"Doc type {entry['doc_type']} should have at least 3 cues"
            )

    @pytest.mark.skipif(
        not _has_workspace_catalog(),
        reason="NSA workspace catalog not available",
    )
    def test_format_doc_type_catalog(self):
        """Test that catalog formats correctly for prompt injection."""
        doc_types = _load_workspace_catalog()
        formatted = format_doc_type_catalog(doc_types)

        assert formatted is not None
        assert len(formatted) > 0
        # Check that at least one doc type from the loaded catalog appears
        assert doc_types[0]["doc_type"] in formatted
        assert "Cues:" in formatted

    def test_format_empty_catalog(self):
        """Test that formatting empty catalog returns empty string."""
        formatted = format_doc_type_catalog([])
        assert formatted == ""


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
