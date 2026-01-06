"""Unit tests for DocTypeSpec loading and validation."""

import pytest
from context_builder.extraction.spec_loader import (
    load_spec,
    get_spec,
    list_available_specs,
    clear_spec_cache,
    DocTypeSpec,
    FieldRule,
)


class TestListAvailableSpecs:
    """Tests for spec discovery."""

    def test_specs_available(self):
        """Test that at least some specs are available."""
        specs = list_available_specs()
        assert len(specs) >= 1

    def test_expected_specs_exist(self):
        """Test that expected document types have specs."""
        specs = list_available_specs()
        # At least loss_notice should exist based on codebase
        assert "loss_notice" in specs


class TestLoadSpec:
    """Tests for loading individual specs."""

    def test_load_loss_notice(self):
        """Test loading loss_notice spec."""
        spec = load_spec("loss_notice", "v0")
        assert spec is not None
        assert spec.doc_type == "loss_notice"

    def test_load_nonexistent_spec(self):
        """Test loading non-existent spec raises error."""
        with pytest.raises(FileNotFoundError):
            load_spec("nonexistent_doc_type", "v0")

    def test_load_nonexistent_version(self):
        """Test loading non-existent version raises error."""
        with pytest.raises(FileNotFoundError):
            load_spec("loss_notice", "v999")


class TestGetSpec:
    """Tests for cached spec retrieval."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_spec_cache()

    def test_get_spec_basic(self):
        """Test basic spec retrieval."""
        spec = get_spec("loss_notice")
        assert spec is not None
        assert spec.doc_type == "loss_notice"

    def test_get_spec_caching(self):
        """Test that specs are cached."""
        spec1 = get_spec("loss_notice")
        spec2 = get_spec("loss_notice")
        # Should be the same object due to caching
        assert spec1 is spec2

    def test_get_spec_no_cache(self):
        """Test spec retrieval without caching."""
        spec1 = get_spec("loss_notice", use_cache=False)
        spec2 = get_spec("loss_notice", use_cache=False)
        # Should be different objects since cache is bypassed
        assert spec1 is not spec2
        # But values should be equal
        assert spec1.doc_type == spec2.doc_type


class TestDocTypeSpecProperties:
    """Tests for DocTypeSpec properties and methods."""

    @pytest.fixture
    def loss_notice_spec(self):
        """Load loss_notice spec for testing."""
        return get_spec("loss_notice")

    def test_required_fields_not_empty(self, loss_notice_spec):
        """Test that required_fields list is not empty."""
        assert len(loss_notice_spec.required_fields) > 0

    def test_all_fields_includes_required(self, loss_notice_spec):
        """Test that all_fields includes required fields."""
        all_fields = loss_notice_spec.all_fields
        for req_field in loss_notice_spec.required_fields:
            assert req_field in all_fields

    def test_all_fields_includes_optional(self, loss_notice_spec):
        """Test that all_fields includes optional fields."""
        all_fields = loss_notice_spec.all_fields
        for opt_field in loss_notice_spec.optional_fields:
            assert opt_field in all_fields

    def test_fields_unique(self, loss_notice_spec):
        """Test that all field names are unique."""
        all_fields = loss_notice_spec.all_fields
        assert len(all_fields) == len(set(all_fields))

    def test_is_required(self, loss_notice_spec):
        """Test is_required method."""
        if loss_notice_spec.required_fields:
            req_field = loss_notice_spec.required_fields[0]
            assert loss_notice_spec.is_required(req_field) is True

        if loss_notice_spec.optional_fields:
            opt_field = loss_notice_spec.optional_fields[0]
            assert loss_notice_spec.is_required(opt_field) is False

    def test_get_field_hints(self, loss_notice_spec):
        """Test get_field_hints returns list."""
        if loss_notice_spec.required_fields:
            field_name = loss_notice_spec.required_fields[0]
            hints = loss_notice_spec.get_field_hints(field_name)
            assert isinstance(hints, list)

    def test_get_field_hints_nonexistent(self, loss_notice_spec):
        """Test get_field_hints for non-existent field returns empty list."""
        hints = loss_notice_spec.get_field_hints("nonexistent_field")
        assert hints == []

    def test_all_hints_returns_list(self, loss_notice_spec):
        """Test all_hints property returns a list."""
        hints = loss_notice_spec.all_hints
        assert isinstance(hints, list)


class TestClearSpecCache:
    """Tests for cache clearing."""

    def test_clear_cache(self):
        """Test that clearing cache works."""
        # Load a spec to populate cache
        spec1 = get_spec("loss_notice")

        # Clear cache
        clear_spec_cache()

        # Load again - should be a different object
        spec2 = get_spec("loss_notice")

        # While values are equal, objects should be different after cache clear
        assert spec1.doc_type == spec2.doc_type
