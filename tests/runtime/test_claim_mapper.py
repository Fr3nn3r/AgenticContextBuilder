"""
Unit tests for ClaimMapper - the inflation pattern implementation.

Tests the core responsibility: transforming flat key-value pairs from UI
into nested JSON structure for the logic engine.
"""

import pytest
from context_builder.runtime.claim_mapper import SchemaBasedClaimMapper


class TestClaimMapperInflation:
    """Test the inflation pattern - flat to nested transformation."""

    def test_simple_nested_path(self):
        """Test simple dot-notation inflation."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "liability"
        }

        schema = {}  # Schema not needed for inflation

        result = mapper.inflate(flat_data, schema)

        assert result == {
            "claim": {
                "header": {
                    "claim_type": "liability"
                }
            }
        }

    def test_multiple_fields_same_path(self):
        """Test multiple fields in the same nested object."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "liability",
            "claim.header.claim_id": "CLM-12345",
            "claim.header.claim_date": "2025-11-29"
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        assert result == {
            "claim": {
                "header": {
                    "claim_type": "liability",
                    "claim_id": "CLM-12345",
                    "claim_date": "2025-11-29"
                }
            }
        }

    def test_deep_nesting(self):
        """Test deeply nested paths."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.incident.attributes.watercraft_length": 10
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        assert result == {
            "claim": {
                "incident": {
                    "attributes": {
                        "watercraft_length": 10
                    }
                }
            }
        }

    def test_array_notation_single_item(self):
        """Test array notation with single item."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.parties.claimants[0].role": "insured"
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        assert result == {
            "claim": {
                "parties": {
                    "claimants": [
                        {"role": "insured"}
                    ]
                }
            }
        }

    def test_array_notation_multiple_items(self):
        """Test array notation with multiple items."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.parties.claimants[0].role": "insured",
            "claim.parties.claimants[0].name": "John Doe",
            "claim.parties.claimants[1].role": "driver",
            "claim.parties.claimants[1].name": "Jane Smith"
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        expected = {
            "claim": {
                "parties": {
                    "claimants": [
                        {"role": "insured", "name": "John Doe"},
                        {"role": "driver", "name": "Jane Smith"}
                    ]
                }
            }
        }

        assert result == expected

    def test_mixed_types(self):
        """Test inflation with mixed data types."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "liability",
            "claim.incident.attributes.watercraft_length": 10,
            "claim.incident.attributes.is_collision": True,
            "claim.financials.amount": 25000.50
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        assert result["claim"]["header"]["claim_type"] == "liability"
        assert result["claim"]["incident"]["attributes"]["watercraft_length"] == 10
        assert result["claim"]["incident"]["attributes"]["is_collision"] is True
        assert result["claim"]["financials"]["amount"] == 25000.50

    def test_none_values_skipped(self):
        """Test that None values are skipped during inflation."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "liability",
            "claim.header.claim_id": None,  # Should be skipped
            "claim.incident.location": "Toronto"
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        assert "claim_id" not in result["claim"]["header"]
        assert result["claim"]["header"]["claim_type"] == "liability"
        assert result["claim"]["incident"]["location"] == "Toronto"

    def test_complex_scenario(self):
        """Test a complex real-world scenario."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "first_party",
            "claim.header.policy_number": "POL-123",
            "claim.incident.date": "2025-11-29",
            "claim.incident.attributes.is_watercraft": True,
            "claim.incident.attributes.watercraft_length": 12,
            "claim.parties.claimants[0].role": "insured",
            "claim.parties.claimants[0].attributes.is_partner": True,
            "claim.parties.claimants[1].role": "spouse",
            "claim.financials.claim_amount": 50000
        }

        schema = {}

        result = mapper.inflate(flat_data, schema)

        # Verify structure
        assert result["claim"]["header"]["claim_type"] == "first_party"
        assert result["claim"]["incident"]["attributes"]["watercraft_length"] == 12
        assert len(result["claim"]["parties"]["claimants"]) == 2
        assert result["claim"]["parties"]["claimants"][0]["role"] == "insured"
        assert result["claim"]["parties"]["claimants"][1]["role"] == "spouse"
        assert result["claim"]["financials"]["claim_amount"] == 50000


class TestClaimMapperValidation:
    """Test validation functionality."""

    def test_valid_data_no_errors(self):
        """Test that valid data passes validation."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "liability",
            "claim.incident.attributes.watercraft_length": 10
        }

        schema = {
            "sections": {
                "header": {
                    "fields": [
                        {"key": "claim.header.claim_type", "type": "string"}
                    ]
                },
                "incident": {
                    "fields": [
                        {"key": "claim.incident.attributes.watercraft_length", "type": "integer"}
                    ]
                }
            }
        }

        errors = mapper.validate(flat_data, schema)
        assert len(errors) == 0

    def test_type_mismatch_error(self):
        """Test that type mismatches are caught."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.incident.attributes.watercraft_length": "ten"  # Should be integer
        }

        schema = {
            "sections": {
                "incident": {
                    "fields": [
                        {"key": "claim.incident.attributes.watercraft_length", "type": "integer"}
                    ]
                }
            }
        }

        errors = mapper.validate(flat_data, schema)
        assert len(errors) == 1
        assert "watercraft_length" in errors[0].field_key

    def test_enum_validation(self):
        """Test enum value validation."""
        mapper = SchemaBasedClaimMapper()

        flat_data = {
            "claim.header.claim_type": "invalid_type"
        }

        schema = {
            "sections": {
                "header": {
                    "fields": [
                        {
                            "key": "claim.header.claim_type",
                            "type": "enum",
                            "options": ["first_party", "liability"]
                        }
                    ]
                }
            }
        }

        errors = mapper.validate(flat_data, schema)
        assert len(errors) == 1
        assert "claim_type" in errors[0].field_key


class TestKeyParsing:
    """Test the internal key parsing logic."""

    def test_parse_simple_key(self):
        """Test parsing simple dot-notation key."""
        mapper = SchemaBasedClaimMapper()

        segments = mapper._parse_key("claim.header.claim_type")

        assert segments == ["claim", "header", "claim_type"]

    def test_parse_array_key(self):
        """Test parsing key with array notation."""
        mapper = SchemaBasedClaimMapper()

        segments = mapper._parse_key("claim.parties.claimants[0].role")

        assert segments == ["claim", "parties", "claimants", 0, "role"]

    def test_parse_complex_array_key(self):
        """Test parsing complex array key."""
        mapper = SchemaBasedClaimMapper()

        segments = mapper._parse_key("claim.parties.claimants[2].attributes.is_driver")

        assert segments == ["claim", "parties", "claimants", 2, "attributes", "is_driver"]
