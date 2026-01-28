"""Unit tests for claim run schemas and migration helpers."""

import pytest
from datetime import datetime

from context_builder.schemas.claim_run import ClaimRunManifest
from context_builder.schemas.claim_facts import (
    ClaimFacts,
    FactProvenance,
    LineItemProvenance,
    migrate_claim_facts_to_v3,
)


class TestClaimRunManifest:
    """Tests for ClaimRunManifest schema."""

    def test_claim_run_manifest_defaults(self):
        """Test that ClaimRunManifest has correct defaults."""
        manifest = ClaimRunManifest(
            claim_run_id="clmrun_001",
            claim_id="CLM-001",
            contextbuilder_version="0.3.0",
        )

        assert manifest.schema_version == "claim_run_v1"
        assert manifest.claim_run_id == "clmrun_001"
        assert manifest.claim_id == "CLM-001"
        assert manifest.contextbuilder_version == "0.3.0"
        assert manifest.extraction_runs_considered == []
        assert manifest.stages_completed == []
        assert manifest.previous_claim_run_id is None
        assert isinstance(manifest.created_at, datetime)

    def test_claim_run_manifest_full(self):
        """Test creating a full manifest with all fields."""
        manifest = ClaimRunManifest(
            claim_run_id="clmrun_002",
            claim_id="CLM-002",
            contextbuilder_version="0.3.0",
            extraction_runs_considered=["run_001", "run_002"],
            stages_completed=["aggregate", "reconcile"],
            previous_claim_run_id="clmrun_001",
        )

        assert manifest.claim_run_id == "clmrun_002"
        assert len(manifest.extraction_runs_considered) == 2
        assert "aggregate" in manifest.stages_completed
        assert manifest.previous_claim_run_id == "clmrun_001"

    def test_claim_run_manifest_serialization(self):
        """Test that manifest serializes to JSON correctly."""
        manifest = ClaimRunManifest(
            claim_run_id="clmrun_001",
            claim_id="CLM-001",
            contextbuilder_version="0.3.0",
            extraction_runs_considered=["run_001"],
            stages_completed=["aggregate"],
        )

        data = manifest.model_dump(mode="json")

        assert data["schema_version"] == "claim_run_v1"
        assert data["claim_run_id"] == "clmrun_001"
        assert data["extraction_runs_considered"] == ["run_001"]


    def test_manifest_with_enriched_fields(self):
        """Test manifest with all new enriched metadata fields populated."""
        manifest = ClaimRunManifest(
            claim_run_id="clmrun_003",
            claim_id="CLM-003",
            contextbuilder_version="0.5.0",
            started_at="2026-01-28T12:00:00Z",
            ended_at="2026-01-28T12:05:00Z",
            hostname="BUILDSERVER",
            python_version="3.11.5",
            git={"commit_sha": "abc123def456", "is_dirty": False},
            workspace_config_hash="deadbeef1234",
            command="python -m context_builder.cli assess --all",
        )

        assert manifest.started_at == "2026-01-28T12:00:00Z"
        assert manifest.ended_at == "2026-01-28T12:05:00Z"
        assert manifest.hostname == "BUILDSERVER"
        assert manifest.python_version == "3.11.5"
        assert manifest.git["commit_sha"] == "abc123def456"
        assert manifest.git["is_dirty"] is False
        assert manifest.workspace_config_hash == "deadbeef1234"
        assert manifest.command == "python -m context_builder.cli assess --all"

    def test_manifest_backward_compat(self):
        """Test that omitting new fields defaults to None (backward compat)."""
        manifest = ClaimRunManifest(
            claim_run_id="clmrun_004",
            claim_id="CLM-004",
            contextbuilder_version="0.3.0",
        )

        assert manifest.started_at is None
        assert manifest.ended_at is None
        assert manifest.hostname is None
        assert manifest.python_version is None
        assert manifest.git is None
        assert manifest.workspace_config_hash is None
        assert manifest.command is None

    def test_manifest_deserialization_old_json(self):
        """Test that old JSON without new fields deserializes cleanly."""
        old_json = {
            "schema_version": "claim_run_v1",
            "claim_run_id": "clmrun_old",
            "claim_id": "CLM-OLD",
            "contextbuilder_version": "0.2.0",
            "extraction_runs_considered": ["run_1"],
            "stages_completed": ["reconciliation"],
            "created_at": "2025-06-01T10:00:00",
        }
        manifest = ClaimRunManifest(**old_json)
        assert manifest.claim_run_id == "clmrun_old"
        assert manifest.started_at is None
        assert manifest.git is None
        assert manifest.hostname is None

    def test_manifest_enriched_serialization_roundtrip(self):
        """Test that enriched fields survive serialization roundtrip."""
        manifest = ClaimRunManifest(
            claim_run_id="clmrun_rt",
            claim_id="CLM-RT",
            contextbuilder_version="0.5.0",
            started_at="2026-01-28T12:00:00Z",
            git={"commit_sha": "abc123", "is_dirty": True},
            hostname="MY-PC",
        )
        data = manifest.model_dump(mode="json")
        restored = ClaimRunManifest(**data)
        assert restored.started_at == "2026-01-28T12:00:00Z"
        assert restored.git == {"commit_sha": "abc123", "is_dirty": True}
        assert restored.hostname == "MY-PC"
        assert restored.ended_at is None


class TestFactProvenanceExtractionRunId:
    """Tests for FactProvenance with extraction_run_id field."""

    def test_fact_provenance_extraction_run_id(self):
        """Test that FactProvenance uses extraction_run_id field."""
        provenance = FactProvenance(
            doc_id="doc_001",
            doc_type="insurance_policy",
            extraction_run_id="run_001",
        )

        assert provenance.extraction_run_id == "run_001"
        assert provenance.doc_id == "doc_001"
        assert provenance.doc_type == "insurance_policy"

    def test_fact_provenance_has_no_run_id(self):
        """Test that FactProvenance no longer has run_id field."""
        provenance = FactProvenance(
            doc_id="doc_001",
            doc_type="insurance_policy",
            extraction_run_id="run_001",
        )

        # The old run_id field should not exist
        assert not hasattr(provenance, "run_id") or "run_id" not in provenance.model_fields


class TestLineItemProvenanceExtractionRunId:
    """Tests for LineItemProvenance with extraction_run_id field."""

    def test_line_item_provenance_extraction_run_id(self):
        """Test that LineItemProvenance uses extraction_run_id field."""
        provenance = LineItemProvenance(
            doc_id="doc_001",
            doc_type="cost_estimate",
            filename="estimate.pdf",
            extraction_run_id="run_001",
        )

        assert provenance.extraction_run_id == "run_001"
        assert provenance.doc_id == "doc_001"
        assert provenance.filename == "estimate.pdf"


class TestClaimFactsV3:
    """Tests for ClaimFacts v3 schema."""

    def test_claim_facts_v3_defaults(self):
        """Test that ClaimFacts has v3 defaults."""
        facts = ClaimFacts(
            claim_id="CLM-001",
            claim_run_id="clmrun_001",
        )

        assert facts.schema_version == "claim_facts_v3"
        assert facts.claim_run_id == "clmrun_001"
        assert facts.extraction_runs_used == []
        assert facts.run_policy == "latest_complete"

    def test_claim_facts_v3_with_extraction_runs(self):
        """Test ClaimFacts with multiple extraction runs."""
        facts = ClaimFacts(
            claim_id="CLM-001",
            claim_run_id="clmrun_001",
            extraction_runs_used=["run_001", "run_002", "run_003"],
        )

        assert len(facts.extraction_runs_used) == 3
        assert "run_002" in facts.extraction_runs_used


class TestMigrateClaimFactsToV3:
    """Tests for migrate_claim_facts_to_v3 function."""

    def test_migrate_claim_facts_v2_to_v3(self):
        """Test migration from v2 to v3 format."""
        v2_data = {
            "schema_version": "claim_facts_v2",
            "claim_id": "CLM-001",
            "run_id": "run_001",
            "run_policy": "latest_complete",
            "facts": [
                {
                    "name": "policy_number",
                    "value": "POL-123",
                    "confidence": 0.95,
                    "selected_from": {
                        "doc_id": "doc_001",
                        "doc_type": "insurance_policy",
                        "run_id": "run_001",
                    },
                }
            ],
            "sources": [],
        }

        result = migrate_claim_facts_to_v3(v2_data)

        # Check top-level changes
        assert result["schema_version"] == "claim_facts_v3"
        assert result["extraction_runs_used"] == ["run_001"]
        assert result["claim_run_id"] == "MIGRATION_PLACEHOLDER"
        assert "run_id" not in result

        # Check fact provenance migration
        fact = result["facts"][0]
        assert fact["selected_from"]["extraction_run_id"] == "run_001"
        assert "run_id" not in fact["selected_from"]

    def test_migrate_claim_facts_idempotent(self):
        """Test that migration is idempotent on v3 data."""
        v3_data = {
            "schema_version": "claim_facts_v3",
            "claim_id": "CLM-001",
            "claim_run_id": "clmrun_001",
            "extraction_runs_used": ["run_001"],
            "run_policy": "latest_complete",
            "facts": [
                {
                    "name": "policy_number",
                    "value": "POL-123",
                    "confidence": 0.95,
                    "selected_from": {
                        "doc_id": "doc_001",
                        "doc_type": "insurance_policy",
                        "extraction_run_id": "run_001",
                    },
                }
            ],
            "sources": [],
        }

        result = migrate_claim_facts_to_v3(v3_data)

        # Should be unchanged
        assert result["schema_version"] == "claim_facts_v3"
        assert result["claim_run_id"] == "clmrun_001"
        assert result["extraction_runs_used"] == ["run_001"]
        assert result["facts"][0]["selected_from"]["extraction_run_id"] == "run_001"

    def test_migrate_with_structured_data_line_items(self):
        """Test migration of line item provenance in structured_data."""
        v2_data = {
            "schema_version": "claim_facts_v2",
            "claim_id": "CLM-001",
            "run_id": "run_001",
            "facts": [],
            "sources": [],
            "structured_data": {
                "line_items": [
                    {
                        "description": "Repair work",
                        "total_price": 100.0,
                        "source": {
                            "doc_id": "doc_002",
                            "doc_type": "cost_estimate",
                            "filename": "estimate.pdf",
                            "run_id": "run_001",
                        },
                    }
                ],
            },
        }

        result = migrate_claim_facts_to_v3(v2_data)

        # Check line item source migration
        line_item = result["structured_data"]["line_items"][0]
        assert line_item["source"]["extraction_run_id"] == "run_001"
        assert "run_id" not in line_item["source"]

    def test_migrate_with_structured_data_service_entries(self):
        """Test migration of service entry provenance in structured_data."""
        v2_data = {
            "schema_version": "claim_facts_v2",
            "claim_id": "CLM-001",
            "run_id": "run_001",
            "facts": [],
            "sources": [],
            "structured_data": {
                "service_entries": [
                    {
                        "service_type": "maintenance",
                        "service_date": "2025-01-01",
                        "source": {
                            "doc_id": "doc_003",
                            "doc_type": "service_book",
                            "filename": "service.pdf",
                            "run_id": "run_001",
                        },
                    }
                ],
            },
        }

        result = migrate_claim_facts_to_v3(v2_data)

        # Check service entry source migration
        entry = result["structured_data"]["service_entries"][0]
        assert entry["source"]["extraction_run_id"] == "run_001"
        assert "run_id" not in entry["source"]

    def test_migrate_handles_empty_run_id(self):
        """Test migration handles empty run_id gracefully."""
        v2_data = {
            "schema_version": "claim_facts_v2",
            "claim_id": "CLM-001",
            "run_id": "",
            "facts": [],
            "sources": [],
        }

        result = migrate_claim_facts_to_v3(v2_data)

        assert result["extraction_runs_used"] == []

    def test_migrate_handles_null_structured_data(self):
        """Test migration handles null structured_data."""
        v2_data = {
            "schema_version": "claim_facts_v2",
            "claim_id": "CLM-001",
            "run_id": "run_001",
            "facts": [],
            "sources": [],
            "structured_data": None,
        }

        result = migrate_claim_facts_to_v3(v2_data)

        assert result["schema_version"] == "claim_facts_v3"
        assert result["structured_data"] is None
