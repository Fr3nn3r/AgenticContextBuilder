"""Contract tests for LabelResult schema validation."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from context_builder.schemas.label import (
    LabelResult,
    FieldLabel,
    DocLabels,
    ReviewMetadata,
)


class TestLabelResultSchema:
    """Tests for LabelResult Pydantic model."""

    @pytest.fixture
    def valid_review_metadata(self):
        """Create valid review metadata."""
        return ReviewMetadata(
            reviewed_at=datetime(2024, 1, 15, 10, 30, 0),
            reviewer="test_user",
            notes="Test review",
        )

    @pytest.fixture
    def valid_field_label(self):
        """Create valid field label."""
        return FieldLabel(
            field_name="incident_date",
            judgement="correct",
            notes="Date is correct",
        )

    @pytest.fixture
    def valid_doc_labels(self):
        """Create valid document labels."""
        return DocLabels(
            doc_type_correct=True,
            text_readable="good",
            needs_vision=False,
        )

    def test_valid_label_result(
        self, valid_review_metadata, valid_field_label, valid_doc_labels
    ):
        """Test that a valid LabelResult can be created."""
        label = LabelResult(
            schema_version="label_v1",
            doc_id="doc123",
            claim_id="claim456",
            review=valid_review_metadata,
            field_labels=[valid_field_label],
            doc_labels=valid_doc_labels,
        )
        assert label.schema_version == "label_v1"
        assert label.doc_id == "doc123"
        assert label.doc_labels.doc_type_correct is True

    def test_rejects_extra_fields(
        self, valid_review_metadata, valid_field_label, valid_doc_labels
    ):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LabelResult(
                schema_version="label_v1",
                doc_id="doc123",
                claim_id="claim456",
                review=valid_review_metadata,
                field_labels=[valid_field_label],
                doc_labels=valid_doc_labels,
                extra_field="should_fail",  # Extra field
            )
        assert "extra_field" in str(exc_info.value)

    def test_rejects_invalid_schema_version(
        self, valid_review_metadata, valid_field_label, valid_doc_labels
    ):
        """Test that invalid schema_version is rejected."""
        with pytest.raises(ValidationError):
            LabelResult(
                schema_version="invalid_version",  # Invalid
                doc_id="doc123",
                claim_id="claim456",
                review=valid_review_metadata,
                field_labels=[valid_field_label],
                doc_labels=valid_doc_labels,
            )


class TestLabelResultParsing:
    """Tests for parsing LabelResult from dict/JSON."""

    def test_parse_from_dict(self):
        """Test parsing from dictionary (like JSON file load)."""
        data = {
            "schema_version": "label_v1",
            "doc_id": "abc123",
            "claim_id": "claim1",
            "review": {
                "reviewed_at": "2024-01-01T00:00:00",
                "reviewer": "test",
                "notes": "",
            },
            "field_labels": [
                {"field_name": "date", "judgement": "correct", "notes": ""}
            ],
            "doc_labels": {
                "doc_type_correct": True,
                "text_readable": "good",
                "needs_vision": False,
            },
        }

        label = LabelResult.model_validate(data)

        assert label.doc_id == "abc123"
        assert label.doc_labels.doc_type_correct is True
        assert label.doc_labels.text_readable == "good"
        assert label.doc_labels.needs_vision is False
        assert len(label.field_labels) == 1
        assert label.field_labels[0].judgement == "correct"

    def test_parse_with_iso_datetime(self):
        """Test parsing with ISO datetime string."""
        data = {
            "schema_version": "label_v1",
            "doc_id": "abc123",
            "claim_id": "claim1",
            "review": {
                "reviewed_at": "2024-01-01T12:30:45Z",
                "reviewer": "test",
            },
            "field_labels": [],
            "doc_labels": {
                "doc_type_correct": False,
                "text_readable": "warn",
                "needs_vision": True,
            },
        }

        label = LabelResult.model_validate(data)
        assert label.doc_labels.doc_type_correct is False
        assert label.doc_labels.needs_vision is True


class TestFieldLabelValidation:
    """Tests for FieldLabel validation."""

    def test_valid_judgements(self):
        """Test all valid judgement values."""
        for judgement in ["correct", "incorrect", "unknown"]:
            label = FieldLabel(field_name="test", judgement=judgement)
            assert label.judgement == judgement

    def test_invalid_judgement(self):
        """Test invalid judgement is rejected."""
        with pytest.raises(ValidationError):
            FieldLabel(field_name="test", judgement="invalid")

    def test_correct_value_optional(self):
        """Test correct_value is optional."""
        label = FieldLabel(field_name="test", judgement="correct")
        assert label.correct_value is None

    def test_correct_value_with_incorrect_judgement(self):
        """Test correct_value can be set with incorrect judgement."""
        label = FieldLabel(
            field_name="test",
            judgement="incorrect",
            correct_value="actual_value",
        )
        assert label.correct_value == "actual_value"


class TestDocLabelsValidation:
    """Tests for DocLabels validation."""

    def test_valid_text_readable_values(self):
        """Test all valid text_readable values."""
        for readable in ["good", "warn", "poor"]:
            labels = DocLabels(
                doc_type_correct=True,
                text_readable=readable,
            )
            assert labels.text_readable == readable

    def test_invalid_text_readable(self):
        """Test invalid text_readable is rejected."""
        with pytest.raises(ValidationError):
            DocLabels(
                doc_type_correct=True,
                text_readable="invalid",  # Not in Literal
            )

    def test_needs_vision_default(self):
        """Test needs_vision defaults to False."""
        labels = DocLabels(
            doc_type_correct=True,
            text_readable="good",
        )
        assert labels.needs_vision is False

    def test_doc_type_correct_required(self):
        """Test doc_type_correct is required."""
        with pytest.raises(ValidationError):
            DocLabels(text_readable="good")  # Missing doc_type_correct


class TestReviewMetadataValidation:
    """Tests for ReviewMetadata validation."""

    def test_valid_metadata(self):
        """Test valid metadata creation."""
        meta = ReviewMetadata(
            reviewed_at=datetime(2024, 1, 15),
            reviewer="test_user",
        )
        assert meta.reviewer == "test_user"

    def test_notes_default_empty(self):
        """Test notes defaults to empty string."""
        meta = ReviewMetadata(
            reviewed_at=datetime(2024, 1, 15),
            reviewer="test",
        )
        assert meta.notes == ""

    def test_reviewed_at_required(self):
        """Test reviewed_at is required."""
        with pytest.raises(ValidationError):
            ReviewMetadata(reviewer="test")  # Missing reviewed_at


class TestLabelResultSerialization:
    """Tests for LabelResult serialization."""

    def test_round_trip_serialization(self):
        """Test model can be serialized and deserialized."""
        label = LabelResult(
            schema_version="label_v1",
            doc_id="doc1",
            claim_id="claim1",
            review=ReviewMetadata(
                reviewed_at=datetime(2024, 1, 15),
                reviewer="test",
            ),
            field_labels=[
                FieldLabel(field_name="date", judgement="correct"),
            ],
            doc_labels=DocLabels(
                doc_type_correct=True,
                text_readable="good",
            ),
        )

        # Serialize
        data = label.model_dump()

        # Deserialize
        restored = LabelResult.model_validate(data)

        assert restored.doc_id == label.doc_id
        assert restored.doc_labels.doc_type_correct == label.doc_labels.doc_type_correct
