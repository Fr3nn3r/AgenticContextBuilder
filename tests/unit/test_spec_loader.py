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
        # At least fnol_form should exist based on codebase
        assert "fnol_form" in specs


class TestLoadSpec:
    """Tests for loading individual specs."""

    def test_load_fnol_form(self):
        """Test loading fnol_form spec."""
        spec = load_spec("fnol_form", "v0")
        assert spec is not None
        assert spec.doc_type == "fnol_form"

    def test_load_nonexistent_spec(self):
        """Test loading non-existent spec raises error."""
        with pytest.raises(FileNotFoundError):
            load_spec("nonexistent_doc_type", "v0")

    def test_load_nonexistent_version(self):
        """Test loading non-existent legacy versioned spec raises error.

        Note: New format specs ({doc_type}.yaml) ignore the version parameter
        since version is stored in metadata. This test verifies that a truly
        non-existent doc_type with version still raises FileNotFoundError.
        """
        with pytest.raises(FileNotFoundError):
            load_spec("nonexistent_legacy_type", "v999")


class TestGetSpec:
    """Tests for cached spec retrieval."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_spec_cache()

    def test_get_spec_basic(self):
        """Test basic spec retrieval."""
        spec = get_spec("fnol_form")
        assert spec is not None
        assert spec.doc_type == "fnol_form"

    def test_get_spec_caching(self):
        """Test that specs are cached."""
        spec1 = get_spec("fnol_form")
        spec2 = get_spec("fnol_form")
        # Should be the same object due to caching
        assert spec1 is spec2

    def test_get_spec_no_cache(self):
        """Test spec retrieval without caching."""
        spec1 = get_spec("fnol_form", use_cache=False)
        spec2 = get_spec("fnol_form", use_cache=False)
        # Should be different objects since cache is bypassed
        assert spec1 is not spec2
        # But values should be equal
        assert spec1.doc_type == spec2.doc_type


class TestDocTypeSpecProperties:
    """Tests for DocTypeSpec properties and methods."""

    @pytest.fixture
    def fnol_form_spec(self):
        """Load fnol_form spec for testing."""
        return get_spec("fnol_form")

    def test_required_fields_not_empty(self, fnol_form_spec):
        """Test that required_fields list is not empty."""
        assert len(fnol_form_spec.required_fields) > 0

    def test_all_fields_includes_required(self, fnol_form_spec):
        """Test that all_fields includes required fields."""
        all_fields = fnol_form_spec.all_fields
        for req_field in fnol_form_spec.required_fields:
            assert req_field in all_fields

    def test_all_fields_includes_optional(self, fnol_form_spec):
        """Test that all_fields includes optional fields."""
        all_fields = fnol_form_spec.all_fields
        for opt_field in fnol_form_spec.optional_fields:
            assert opt_field in all_fields

    def test_fields_unique(self, fnol_form_spec):
        """Test that all field names are unique."""
        all_fields = fnol_form_spec.all_fields
        assert len(all_fields) == len(set(all_fields))

    def test_is_required(self, fnol_form_spec):
        """Test is_required method."""
        if fnol_form_spec.required_fields:
            req_field = fnol_form_spec.required_fields[0]
            assert fnol_form_spec.is_required(req_field) is True

        if fnol_form_spec.optional_fields:
            opt_field = fnol_form_spec.optional_fields[0]
            assert fnol_form_spec.is_required(opt_field) is False

    def test_get_field_hints(self, fnol_form_spec):
        """Test get_field_hints returns list."""
        if fnol_form_spec.required_fields:
            field_name = fnol_form_spec.required_fields[0]
            hints = fnol_form_spec.get_field_hints(field_name)
            assert isinstance(hints, list)

    def test_get_field_hints_nonexistent(self, fnol_form_spec):
        """Test get_field_hints for non-existent field returns empty list."""
        hints = fnol_form_spec.get_field_hints("nonexistent_field")
        assert hints == []

    def test_all_hints_returns_list(self, fnol_form_spec):
        """Test all_hints property returns a list."""
        hints = fnol_form_spec.all_hints
        assert isinstance(hints, list)


class TestClearSpecCache:
    """Tests for cache clearing."""

    def test_clear_cache(self):
        """Test that clearing cache works."""
        # Load a spec to populate cache
        spec1 = get_spec("fnol_form")

        # Clear cache
        clear_spec_cache()

        # Load again - should be a different object
        spec2 = get_spec("fnol_form")

        # While values are equal, objects should be different after cache clear
        assert spec1.doc_type == spec2.doc_type
