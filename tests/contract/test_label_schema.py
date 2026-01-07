"""Contract tests for LabelResult schema validation (label_v3)."""

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
        """Create valid field label with LABELED state."""
        return FieldLabel(
            field_name="incident_date",
            state="LABELED",
            truth_value="2024-01-15",
            notes="Date is correct",
        )

    @pytest.fixture
    def valid_doc_labels(self):
        """Create valid document labels."""
        return DocLabels(doc_type_correct=True)

    def test_valid_label_result(
        self, valid_review_metadata, valid_field_label, valid_doc_labels
    ):
        """Test that a valid LabelResult can be created."""
        label = LabelResult(
            schema_version="label_v3",
            doc_id="doc123",
            claim_id="claim456",
            review=valid_review_metadata,
            field_labels=[valid_field_label],
            doc_labels=valid_doc_labels,
        )
        assert label.schema_version == "label_v3"
        assert label.doc_id == "doc123"
        assert label.doc_labels.doc_type_correct is True

    def test_rejects_extra_fields(
        self, valid_review_metadata, valid_field_label, valid_doc_labels
    ):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LabelResult(
                schema_version="label_v3",
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
            "schema_version": "label_v3",
            "doc_id": "abc123",
            "claim_id": "claim1",
            "review": {
                "reviewed_at": "2024-01-01T00:00:00",
                "reviewer": "test",
                "notes": "",
            },
            "field_labels": [
                {
                    "field_name": "date",
                    "state": "LABELED",
                    "truth_value": "2024-01-01",
                    "notes": "",
                }
            ],
            "doc_labels": {
                "doc_type_correct": True,
            },
        }

        label = LabelResult.model_validate(data)

        assert label.doc_id == "abc123"
        assert label.doc_labels.doc_type_correct is True
        assert len(label.field_labels) == 1
        assert label.field_labels[0].state == "LABELED"
        assert label.field_labels[0].truth_value == "2024-01-01"

    def test_parse_with_iso_datetime(self):
        """Test parsing with ISO datetime string."""
        data = {
            "schema_version": "label_v3",
            "doc_id": "abc123",
            "claim_id": "claim1",
            "review": {
                "reviewed_at": "2024-01-01T12:30:45Z",
                "reviewer": "test",
            },
            "field_labels": [],
            "doc_labels": {
                "doc_type_correct": False,
            },
        }

        label = LabelResult.model_validate(data)
        assert label.doc_labels.doc_type_correct is False


class TestFieldLabelValidation:
    """Tests for FieldLabel validation."""

    def test_valid_states(self):
        """Test all valid state values."""
        # LABELED requires truth_value
        label_labeled = FieldLabel(field_name="test", state="LABELED", truth_value="value")
        assert label_labeled.state == "LABELED"

        # UNVERIFIABLE requires unverifiable_reason
        label_unverifiable = FieldLabel(
            field_name="test", state="UNVERIFIABLE", unverifiable_reason="cannot_verify"
        )
        assert label_unverifiable.state == "UNVERIFIABLE"

        # UNLABELED is default, no requirements
        label_unlabeled = FieldLabel(field_name="test", state="UNLABELED")
        assert label_unlabeled.state == "UNLABELED"

    def test_invalid_state(self):
        """Test invalid state is rejected."""
        with pytest.raises(ValidationError):
            FieldLabel(field_name="test", state="invalid")

    def test_truth_value_optional_for_unlabeled(self):
        """Test truth_value is optional for UNLABELED state."""
        label = FieldLabel(field_name="test", state="UNLABELED")
        assert label.truth_value is None

    def test_truth_value_required_for_labeled(self):
        """Test truth_value is required when state=LABELED."""
        with pytest.raises(ValidationError):
            FieldLabel(field_name="test", state="LABELED")  # Missing truth_value

    def test_truth_value_with_labeled_state(self):
        """Test truth_value can be set with LABELED state."""
        label = FieldLabel(
            field_name="test",
            state="LABELED",
            truth_value="actual_value",
        )
        assert label.truth_value == "actual_value"

    def test_unverifiable_reason_required_for_unverifiable(self):
        """Test unverifiable_reason is required when state=UNVERIFIABLE."""
        with pytest.raises(ValidationError):
            FieldLabel(field_name="test", state="UNVERIFIABLE")  # Missing reason

    def test_unverifiable_reason_with_state(self):
        """Test unverifiable_reason can be set with UNVERIFIABLE state."""
        label = FieldLabel(
            field_name="test",
            state="UNVERIFIABLE",
            unverifiable_reason="not_present_in_doc",
        )
        assert label.unverifiable_reason == "not_present_in_doc"

    def test_all_unverifiable_reasons(self):
        """Test all valid unverifiable reason values."""
        reasons = ["not_present_in_doc", "unreadable_text", "wrong_doc_type", "cannot_verify", "other"]
        for reason in reasons:
            label = FieldLabel(
                field_name="test",
                state="UNVERIFIABLE",
                unverifiable_reason=reason,
            )
            assert label.unverifiable_reason == reason

    def test_updated_at_optional(self):
        """Test updated_at is optional."""
        label = FieldLabel(field_name="test", state="UNLABELED")
        assert label.updated_at is None


class TestDocLabelsValidation:
    """Tests for DocLabels validation."""

    def test_doc_type_correct_true(self):
        """Test doc_type_correct can be True."""
        labels = DocLabels(doc_type_correct=True)
        assert labels.doc_type_correct is True

    def test_doc_type_correct_false(self):
        """Test doc_type_correct can be False."""
        labels = DocLabels(doc_type_correct=False)
        assert labels.doc_type_correct is False

    def test_doc_type_correct_default(self):
        """Test doc_type_correct defaults to True."""
        labels = DocLabels()
        assert labels.doc_type_correct is True


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
            schema_version="label_v3",
            doc_id="doc1",
            claim_id="claim1",
            review=ReviewMetadata(
                reviewed_at=datetime(2024, 1, 15),
                reviewer="test",
            ),
            field_labels=[
                FieldLabel(
                    field_name="date",
                    state="LABELED",
                    truth_value="2024-01-15",
                ),
            ],
            doc_labels=DocLabels(doc_type_correct=True),
        )

        # Serialize
        data = label.model_dump()

        # Deserialize
        restored = LabelResult.model_validate(data)

        assert restored.doc_id == label.doc_id
        assert restored.doc_labels.doc_type_correct == label.doc_labels.doc_type_correct
        assert restored.field_labels[0].state == label.field_labels[0].state
        assert restored.field_labels[0].truth_value == label.field_labels[0].truth_value
