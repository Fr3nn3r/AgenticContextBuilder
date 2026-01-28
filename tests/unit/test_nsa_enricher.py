"""Unit tests for the NSA workspace enricher.

These tests verify the enricher correctly handles fact name lookups,
especially for prefixed fact names like 'cost_estimate.document_date'.
"""

import pytest
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch


class TestGetFactLookup:
    """Tests for the get_fact helper function in _compute_check_inputs.

    The get_fact function must support both exact matches and suffix matches
    to handle fact names that are prefixed with document type (e.g.,
    'cost_estimate.document_date' should be found when looking for 'document_date').
    """

    def _create_get_fact(self, facts: list) -> callable:
        """Create a get_fact function matching the enricher's implementation."""
        def get_fact(name: str) -> Optional[Any]:
            # First try exact match
            for f in facts:
                if f.get("name") == name:
                    return f.get("value")
            # Then try suffix match (e.g., "document_date" matches "cost_estimate.document_date")
            for f in facts:
                fact_name = f.get("name", "")
                if fact_name.endswith("." + name):
                    return f.get("value")
            return None
        return get_fact

    def test_exact_match_finds_fact(self):
        """get_fact should find facts by exact name match."""
        facts = [
            {"name": "document_date", "value": "2026-01-15"},
            {"name": "start_date", "value": "2025-12-01"},
        ]
        get_fact = self._create_get_fact(facts)

        assert get_fact("document_date") == "2026-01-15"
        assert get_fact("start_date") == "2025-12-01"

    def test_suffix_match_finds_prefixed_fact(self):
        """get_fact should find 'cost_estimate.document_date' when looking for 'document_date'."""
        facts = [
            {"name": "cost_estimate.document_date", "value": "2026-01-16"},
            {"name": "start_date", "value": "2025-12-01"},
        ]
        get_fact = self._create_get_fact(facts)

        # Should find the prefixed fact via suffix match
        assert get_fact("document_date") == "2026-01-16"

    def test_exact_match_takes_precedence_over_suffix(self):
        """When both exact and suffix matches exist, exact match should win."""
        facts = [
            {"name": "document_date", "value": "exact_value"},
            {"name": "cost_estimate.document_date", "value": "prefixed_value"},
        ]
        get_fact = self._create_get_fact(facts)

        # Exact match should take precedence
        assert get_fact("document_date") == "exact_value"

    def test_suffix_match_with_multiple_prefixed_facts(self):
        """When multiple prefixed facts exist, first one should be returned."""
        facts = [
            {"name": "cost_estimate.document_date", "value": "2026-01-16"},
            {"name": "parts_delivery_note.document_date", "value": "2026-01-08"},
        ]
        get_fact = self._create_get_fact(facts)

        # Should return the first suffix match
        assert get_fact("document_date") == "2026-01-16"

    def test_returns_none_when_not_found(self):
        """get_fact should return None when fact is not found."""
        facts = [
            {"name": "start_date", "value": "2025-12-01"},
        ]
        get_fact = self._create_get_fact(facts)

        assert get_fact("document_date") is None
        assert get_fact("nonexistent_field") is None

    def test_suffix_match_requires_dot_prefix(self):
        """Suffix match should only work with dot-prefixed names, not partial matches."""
        facts = [
            {"name": "my_document_date", "value": "wrong_value"},  # No dot, shouldn't match
        ]
        get_fact = self._create_get_fact(facts)

        # Should NOT match 'my_document_date' when looking for 'document_date'
        # because there's no dot before 'document_date'
        assert get_fact("document_date") is None

    def test_common_prefixed_fact_patterns(self):
        """Test common fact name patterns seen in real claims."""
        facts = [
            {"name": "cost_estimate.document_date", "value": "16.01.2026"},
            {"name": "cost_estimate.document_number", "value": "01418775"},
            {"name": "parts_delivery_note.document_date", "value": "08.01.2025"},
            {"name": "service_history.document_date", "value": "2026-01-08"},
            {"name": "start_date", "value": "22.12.2025"},  # Unprefixed
            {"name": "end_date", "value": "21.12.2026"},    # Unprefixed
        ]
        get_fact = self._create_get_fact(facts)

        # Prefixed facts should be found by suffix
        assert get_fact("document_date") == "16.01.2026"  # First match
        assert get_fact("document_number") == "01418775"

        # Unprefixed facts should be found by exact match
        assert get_fact("start_date") == "22.12.2025"
        assert get_fact("end_date") == "21.12.2026"


class TestComputeCheckInputs:
    """Tests for _compute_check_inputs with prefixed fact names.

    These tests ensure that check inputs are correctly computed even when
    fact names are prefixed with document types.
    """

    @pytest.fixture
    def mock_enricher(self, tmp_path):
        """Create a mock enricher for testing _compute_check_inputs."""
        # Import here to avoid issues if enricher file doesn't exist
        import sys
        import importlib.util

        enricher_path = Path(__file__).parent.parent.parent / "workspaces" / "nsa" / "config" / "enrichment" / "enricher.py"

        if not enricher_path.exists():
            pytest.skip("NSA enricher not found")

        spec = importlib.util.spec_from_file_location("workspace_enricher", enricher_path)
        module = importlib.util.module_from_spec(spec)

        # Mock the assumptions file
        with patch.object(Path, 'exists', return_value=False):
            spec.loader.exec_module(module)

        # Create enricher with empty assumptions
        enricher = module.NSAEnricher(tmp_path)
        enricher.assumptions = {}
        return enricher

    def test_claim_date_from_prefixed_fact(self, mock_enricher):
        """_compute_check_inputs should find claim_date from cost_estimate.document_date."""
        claim_facts = {
            "facts": [
                {"name": "cost_estimate.document_date", "value": "16.01.2026"},
                {"name": "start_date", "value": "22.12.2025"},
                {"name": "end_date", "value": "21.12.2026"},
            ],
            "structured_data": {},
        }

        result = mock_enricher._compute_check_inputs(claim_facts)

        assert result["check_1_policy_validity"]["claim_date"] == "16.01.2026"
        assert result["check_1_policy_validity"]["policy_start"] == "22.12.2025"
        assert result["check_1_policy_validity"]["policy_end"] == "21.12.2026"

    def test_claim_date_from_unprefixed_fact(self, mock_enricher):
        """_compute_check_inputs should still work with unprefixed document_date."""
        claim_facts = {
            "facts": [
                {"name": "document_date", "value": "15.01.2026"},
                {"name": "start_date", "value": "22.12.2025"},
                {"name": "end_date", "value": "21.12.2026"},
            ],
            "structured_data": {},
        }

        result = mock_enricher._compute_check_inputs(claim_facts)

        assert result["check_1_policy_validity"]["claim_date"] == "15.01.2026"

    def test_service_compliance_with_prefixed_claim_date(self, mock_enricher):
        """Service compliance should be computed correctly with prefixed claim_date."""
        claim_facts = {
            "facts": [
                {"name": "cost_estimate.document_date", "value": "16.01.2026"},
            ],
            "structured_data": {
                "service_entries": [
                    {"service_date": "2025-12-22", "is_authorized_partner": True},
                ],
            },
        }

        result = mock_enricher._compute_check_inputs(claim_facts)

        # Should find the claim date and compute days since last service
        assert result["check_4b_service"]["claim_date"] == "16.01.2026"
        assert result["check_4b_service"]["last_service_date"] == "2025-12-22"
        assert result["check_4b_service"]["days_since_last_service"] == 25
        assert result["check_4b_service"]["service_within_12_months"] is True

    def test_missing_claim_date_returns_none(self, mock_enricher):
        """When no document_date exists, claim_date should be None."""
        claim_facts = {
            "facts": [
                {"name": "start_date", "value": "22.12.2025"},
                {"name": "end_date", "value": "21.12.2026"},
            ],
            "structured_data": {},
        }

        result = mock_enricher._compute_check_inputs(claim_facts)

        assert result["check_1_policy_validity"]["claim_date"] is None
        assert result["check_4b_service"]["claim_date"] is None

    def test_odometer_fallback_to_vehicle_current_km(self, mock_enricher):
        """current_odometer should fall back to vehicle_current_km if odometer_km missing."""
        claim_facts = {
            "facts": [
                {"name": "vehicle_current_km", "value": "136000"},
            ],
            "structured_data": {},
        }

        result = mock_enricher._compute_check_inputs(claim_facts)

        assert result["check_1_policy_validity"]["current_odometer"] == "136000"

    def test_odometer_prefers_odometer_km(self, mock_enricher):
        """current_odometer should prefer odometer_km over vehicle_current_km."""
        claim_facts = {
            "facts": [
                {"name": "odometer_km", "value": "140000"},
                {"name": "vehicle_current_km", "value": "136000"},
            ],
            "structured_data": {},
        }

        result = mock_enricher._compute_check_inputs(claim_facts)

        assert result["check_1_policy_validity"]["current_odometer"] == "140000"


class TestRealClaimScenarios:
    """Integration-style tests using real claim data patterns."""

    def _create_get_fact(self, facts: list) -> callable:
        """Create a get_fact function matching the enricher's implementation."""
        def get_fact(name: str) -> Optional[Any]:
            for f in facts:
                if f.get("name") == name:
                    return f.get("value")
            for f in facts:
                fact_name = f.get("name", "")
                if fact_name.endswith("." + name):
                    return f.get("value")
            return None
        return get_fact

    def test_claim_65258_pattern(self):
        """Test the exact pattern seen in claim 65258 that caused the bug."""
        # This is the actual fact structure from claim 65258
        facts = [
            {"name": "start_date", "value": "22.12.2025"},
            {"name": "end_date", "value": "21.12.2026"},
            {"name": "cost_estimate.document_date", "value": "16.01.2026"},
            {"name": "registration_date", "value": "18.09.2019"},
            {"name": "expiry_date", "value": "08.10.2025"},
            {"name": "delivery_date", "value": "2019-09-18"},
            {"name": "parts_delivery_note.document_date", "value": "08.01.2025 13:45:17"},
            {"name": "transaction_date", "value": "08.01.2025"},
            {"name": "service_date", "value": "09.01.2025"},
        ]
        get_fact = self._create_get_fact(facts)

        # The bug: document_date was not found because it's prefixed
        # After fix: should find cost_estimate.document_date
        claim_date = get_fact("document_date")

        assert claim_date is not None, "claim_date should be found from cost_estimate.document_date"
        assert claim_date == "16.01.2026"

    def test_claim_65128_pattern(self):
        """Test another real claim pattern."""
        facts = [
            {"name": "cost_estimate.document_date", "value": "07 janvier 2026"},
            {"name": "service_history.document_date", "value": "2026-01-08"},
        ]
        get_fact = self._create_get_fact(facts)

        # Should find the first prefixed match
        assert get_fact("document_date") == "07 janvier 2026"
