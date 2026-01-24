"""Unit tests for the AggregationService."""

import json
import pytest
from datetime import datetime
from pathlib import Path

from context_builder.api.services.aggregation import (
    AggregationError,
    AggregationService,
)
from context_builder.schemas.claim_facts import (
    AggregatedFact,
    AggregatedLineItem,
    AggregatedServiceEntry,
    ClaimFacts,
    FactProvenance,
    LineItemProvenance,
    SourceDocument,
    StructuredClaimData,
)
from context_builder.storage.filesystem import FileStorage


@pytest.fixture
def claim_with_extractions(tmp_path):
    """Create a claim structure with multiple documents and extractions."""
    # Create claims directory
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()

    # Create claim folder
    claim_id = "CLM-TEST-001"
    claim_folder = claims_dir / claim_id
    docs_dir = claim_folder / "docs"
    docs_dir.mkdir(parents=True)

    # Create doc 1 (insurance_policy)
    doc1_id = "doc_policy_001"
    doc1_dir = docs_dir / doc1_id
    (doc1_dir / "meta").mkdir(parents=True)
    doc1_meta = {
        "doc_id": doc1_id,
        "claim_id": claim_id,
        "original_filename": "policy.pdf",
        "source_type": "pdf",
        "doc_type": "insurance_policy",
        "page_count": 2,
    }
    with open(doc1_dir / "meta" / "doc.json", "w") as f:
        json.dump(doc1_meta, f)

    # Create doc 2 (loss_notice)
    doc2_id = "doc_notice_002"
    doc2_dir = docs_dir / doc2_id
    (doc2_dir / "meta").mkdir(parents=True)
    doc2_meta = {
        "doc_id": doc2_id,
        "claim_id": claim_id,
        "original_filename": "loss_notice.pdf",
        "source_type": "pdf",
        "doc_type": "loss_notice",
        "page_count": 1,
    }
    with open(doc2_dir / "meta" / "doc.json", "w") as f:
        json.dump(doc2_meta, f)

    # Create run directory with extractions
    run_id = "run_20260124_100000_test123"
    run_dir = claim_folder / "runs" / run_id
    extraction_dir = run_dir / "extraction"
    extraction_dir.mkdir(parents=True)
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)

    # Write extraction for doc 1 (higher confidence for policy_number)
    extraction1 = {
        "schema_version": "extraction_result_v1",
        "run": {"run_id": run_id},
        "doc": {
            "doc_id": doc1_id,
            "claim_id": claim_id,
            "doc_type": "insurance_policy",
        },
        "fields": [
            {
                "name": "policy_number",
                "value": "POL-123456",
                "normalized_value": "POL-123456",
                "confidence": 0.95,
                "status": "present",
                "provenance": [
                    {
                        "page": 1,
                        "method": "di_text",
                        "text_quote": "Policy No: POL-123456",
                        "char_start": 100,
                        "char_end": 125,
                    }
                ],
            },
            {
                "name": "insured_name",
                "value": "John Smith",
                "normalized_value": "John Smith",
                "confidence": 0.88,
                "status": "present",
                "provenance": [{"page": 1, "method": "di_text"}],
            },
            {
                "name": "coverage_start",
                "value": None,
                "normalized_value": None,
                "confidence": 0.0,
                "status": "missing",
                "provenance": [],
            },
        ],
    }
    with open(extraction_dir / f"{doc1_id}.json", "w") as f:
        json.dump(extraction1, f)

    # Write extraction for doc 2 (lower confidence for policy_number, different insured_name)
    extraction2 = {
        "schema_version": "extraction_result_v1",
        "run": {"run_id": run_id},
        "doc": {
            "doc_id": doc2_id,
            "claim_id": claim_id,
            "doc_type": "loss_notice",
        },
        "fields": [
            {
                "name": "policy_number",
                "value": "POL-123456",
                "normalized_value": "POL-123456",
                "confidence": 0.85,
                "status": "present",
                "provenance": [{"page": 1, "method": "di_text"}],
            },
            {
                "name": "insured_name",
                "value": "J. Smith",
                "normalized_value": "J. Smith",
                "confidence": 0.92,
                "status": "present",
                "provenance": [{"page": 1, "method": "di_text"}],
            },
            {
                "name": "loss_date",
                "value": "2026-01-15",
                "normalized_value": "2026-01-15",
                "confidence": 0.90,
                "status": "present",
                "provenance": [{"page": 1, "method": "di_text"}],
            },
        ],
    }
    with open(extraction_dir / f"{doc2_id}.json", "w") as f:
        json.dump(extraction2, f)

    # Write summary.json
    summary = {"completed_at": "2026-01-24T10:00:05Z", "status": "success"}
    with open(logs_dir / "summary.json", "w") as f:
        json.dump(summary, f)

    # Mark run as complete
    (run_dir / ".complete").touch()

    return {
        "tmp_path": tmp_path,
        "claim_id": claim_id,
        "run_id": run_id,
        "doc1_id": doc1_id,
        "doc2_id": doc2_id,
    }


@pytest.fixture
def claim_no_complete_run(tmp_path):
    """Create a claim with no complete runs."""
    claims_dir = tmp_path / "claims"
    claims_dir.mkdir()

    claim_id = "CLM-NO-RUN"
    claim_folder = claims_dir / claim_id
    docs_dir = claim_folder / "docs"
    docs_dir.mkdir(parents=True)

    # Create a doc
    doc_dir = docs_dir / "doc_001"
    (doc_dir / "meta").mkdir(parents=True)
    doc_meta = {
        "doc_id": "doc_001",
        "claim_id": claim_id,
        "original_filename": "doc.pdf",
    }
    with open(doc_dir / "meta" / "doc.json", "w") as f:
        json.dump(doc_meta, f)

    # Create run directory WITHOUT .complete marker
    run_dir = claim_folder / "runs" / "run_20260124_000000_incomplete"
    run_dir.mkdir(parents=True)

    return {"tmp_path": tmp_path, "claim_id": claim_id}


class TestFindLatestCompleteRun:
    """Tests for find_latest_complete_run method."""

    def test_finds_latest_complete_run(self, claim_with_extractions):
        """Should find the latest complete run for a claim."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        run_id = service.find_latest_complete_run(claim_with_extractions["claim_id"])

        assert run_id == claim_with_extractions["run_id"]

    def test_returns_none_for_no_complete_runs(self, claim_no_complete_run):
        """Should return None if no complete runs exist."""
        storage = FileStorage(claim_no_complete_run["tmp_path"])
        service = AggregationService(storage)

        run_id = service.find_latest_complete_run(claim_no_complete_run["claim_id"])

        assert run_id is None

    def test_returns_none_for_nonexistent_claim(self, tmp_path):
        """Should return None for a nonexistent claim."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        run_id = service.find_latest_complete_run("NONEXISTENT-CLAIM")

        assert run_id is None


class TestAggregateSingleDoc:
    """Tests for aggregating facts from a single document."""

    def test_aggregate_single_doc(self, tmp_path):
        """Single document should produce correct facts."""
        # Create minimal structure with one doc
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-SINGLE"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"
        doc_id = "doc_single"
        doc_dir = docs_dir / doc_id
        (doc_dir / "meta").mkdir(parents=True)

        doc_meta = {
            "doc_id": doc_id,
            "claim_id": claim_id,
            "original_filename": "single.pdf",
            "doc_type": "invoice",
        }
        with open(doc_dir / "meta" / "doc.json", "w") as f:
            json.dump(doc_meta, f)

        # Create run with extraction
        run_id = "run_20260124_single"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc_id, "claim_id": claim_id, "doc_type": "invoice"},
            "fields": [
                {
                    "name": "invoice_number",
                    "value": "INV-001",
                    "normalized_value": "INV-001",
                    "confidence": 0.95,
                    "status": "present",
                    "provenance": [{"page": 1}],
                }
            ],
        }
        with open(extraction_dir / f"{doc_id}.json", "w") as f:
            json.dump(extraction, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        assert facts.claim_id == claim_id
        assert facts.run_id == run_id
        assert len(facts.facts) == 1
        assert facts.facts[0].name == "invoice_number"
        assert facts.facts[0].value == "INV-001"
        assert facts.facts[0].confidence == 0.95
        assert len(facts.sources) == 1
        assert facts.sources[0].doc_id == doc_id


class TestAggregateMultipleDocs:
    """Tests for aggregating facts from multiple documents."""

    def test_highest_confidence_wins(self, claim_with_extractions):
        """Highest confidence value should be selected as primary."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        # Find policy_number fact
        policy_fact = next(f for f in facts.facts if f.name == "policy_number")

        # Doc 1 has 0.95 confidence, doc 2 has 0.85 - doc 1 should win
        assert policy_fact.confidence == 0.95
        assert policy_fact.selected_from.doc_id == claim_with_extractions["doc1_id"]
        assert policy_fact.selected_from.doc_type == "insurance_policy"

    def test_insured_name_higher_confidence_from_doc2(self, claim_with_extractions):
        """insured_name should come from doc2 which has higher confidence (0.92 vs 0.88)."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        # Find insured_name fact
        name_fact = next(f for f in facts.facts if f.name == "insured_name")

        # Doc 2 has 0.92 confidence, doc 1 has 0.88 - doc 2 should win
        assert name_fact.confidence == 0.92
        assert name_fact.value == "J. Smith"
        assert name_fact.selected_from.doc_id == claim_with_extractions["doc2_id"]

    def test_unique_field_from_single_doc(self, claim_with_extractions):
        """Field only in one doc should be included."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        # loss_date only in doc2
        loss_fact = next(f for f in facts.facts if f.name == "loss_date")

        assert loss_fact.value == "2026-01-15"
        assert loss_fact.selected_from.doc_id == claim_with_extractions["doc2_id"]


class TestMissingRunRaises:
    """Tests for error handling when no runs exist."""

    def test_no_complete_run_raises(self, claim_no_complete_run):
        """Should raise AggregationError if no complete runs exist."""
        storage = FileStorage(claim_no_complete_run["tmp_path"])
        service = AggregationService(storage)

        with pytest.raises(AggregationError) as exc_info:
            service.aggregate_claim_facts(claim_no_complete_run["claim_id"])

        assert "No complete runs found" in str(exc_info.value)

    def test_nonexistent_claim_raises(self, tmp_path):
        """Should raise AggregationError for nonexistent claim."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        with pytest.raises(AggregationError) as exc_info:
            service.aggregate_claim_facts("NONEXISTENT")

        assert "No complete runs found" in str(exc_info.value)


class TestDryRunNoWrite:
    """Tests for dry-run mode (no file writes)."""

    def test_aggregate_returns_facts_without_writing(self, claim_with_extractions):
        """aggregate_claim_facts should return facts without writing to disk."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        # This should not write any files
        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        # Verify facts were returned
        assert isinstance(facts, ClaimFacts)
        assert len(facts.facts) > 0

        # Verify no file was written (context dir should not exist)
        claim_folder = (
            claim_with_extractions["tmp_path"]
            / "claims"
            / claim_with_extractions["claim_id"]
        )
        context_dir = claim_folder / "context"
        assert not context_dir.exists()


class TestWriteClaimFacts:
    """Tests for writing claim facts to disk."""

    def test_write_creates_file(self, claim_with_extractions):
        """write_claim_facts should create claim_facts.json."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])
        output_path = service.write_claim_facts(claim_with_extractions["claim_id"], facts)

        assert output_path.exists()
        assert output_path.name == "claim_facts.json"

        # Verify content
        with open(output_path) as f:
            written_data = json.load(f)

        assert written_data["claim_id"] == claim_with_extractions["claim_id"]
        assert written_data["schema_version"] == "claim_facts_v2"
        assert len(written_data["facts"]) > 0

    def test_write_nonexistent_claim_raises(self, tmp_path):
        """write_claim_facts should raise for nonexistent claim."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        # Create a mock ClaimFacts object
        facts = ClaimFacts(
            claim_id="NONEXISTENT",
            run_id="test_run",
            facts=[],
            sources=[],
        )

        with pytest.raises(AggregationError) as exc_info:
            service.write_claim_facts("NONEXISTENT", facts)

        assert "Claim not found" in str(exc_info.value)


class TestSourceDocuments:
    """Tests for source document tracking."""

    def test_sources_list_all_docs(self, claim_with_extractions):
        """sources should list all documents used in aggregation."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        # Should have 2 source documents
        assert len(facts.sources) == 2

        doc_ids = {s.doc_id for s in facts.sources}
        assert claim_with_extractions["doc1_id"] in doc_ids
        assert claim_with_extractions["doc2_id"] in doc_ids

        # Check doc types
        doc_types = {s.doc_type for s in facts.sources}
        assert "insurance_policy" in doc_types
        assert "loss_notice" in doc_types


class TestStructuredDataAggregation:
    """Tests for structured data (line items) aggregation."""

    def test_line_items_from_cost_estimate(self, tmp_path):
        """Line items from cost_estimate should be aggregated with provenance."""
        # Create minimal structure with cost estimate
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-COST-001"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"
        doc_id = "doc_cost_001"
        doc_dir = docs_dir / doc_id
        (doc_dir / "meta").mkdir(parents=True)

        doc_meta = {
            "doc_id": doc_id,
            "claim_id": claim_id,
            "original_filename": "cost_estimate.pdf",
            "doc_type": "cost_estimate",
        }
        with open(doc_dir / "meta" / "doc.json", "w") as f:
            json.dump(doc_meta, f)

        # Create run with extraction including structured_data
        run_id = "run_20260124_cost"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc_id, "claim_id": claim_id, "doc_type": "cost_estimate"},
            "fields": [
                {
                    "name": "total_cost",
                    "value": "1500.00",
                    "confidence": 0.95,
                    "status": "present",
                    "provenance": [{"page": 1}],
                }
            ],
            "structured_data": {
                "line_items": [
                    {
                        "item_code": "LAB-001",
                        "description": "Labor - windshield removal",
                        "quantity": 1.0,
                        "unit": "hour",
                        "unit_price": 75.00,
                        "total_price": 75.00,
                        "item_type": "labor",
                        "page_number": 1,
                    },
                    {
                        "item_code": "PRT-WS01",
                        "description": "Windshield OEM replacement",
                        "quantity": 1.0,
                        "unit": "each",
                        "unit_price": 350.00,
                        "total_price": 350.00,
                        "item_type": "parts",
                        "page_number": 1,
                    },
                ]
            },
        }
        with open(extraction_dir / f"{doc_id}.json", "w") as f:
            json.dump(extraction, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Verify structured_data is populated
        assert facts.structured_data is not None
        assert facts.structured_data.line_items is not None
        assert len(facts.structured_data.line_items) == 2

        # Verify line item details
        labor_item = next(
            i for i in facts.structured_data.line_items if i.item_type == "labor"
        )
        assert labor_item.item_code == "LAB-001"
        assert labor_item.description == "Labor - windshield removal"
        assert labor_item.quantity == 1.0
        assert labor_item.total_price == 75.00
        assert labor_item.source.doc_id == doc_id
        assert labor_item.source.doc_type == "cost_estimate"
        assert labor_item.source.run_id == run_id

        parts_item = next(
            i for i in facts.structured_data.line_items if i.item_type == "parts"
        )
        assert parts_item.item_code == "PRT-WS01"
        assert parts_item.total_price == 350.00

    def test_multiple_cost_estimates_merged(self, tmp_path):
        """Line items from multiple cost estimates should be merged."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-MULTI-COST"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"

        # Create two cost estimate documents
        for i, doc_id in enumerate(["doc_cost_1", "doc_cost_2"]):
            doc_dir = docs_dir / doc_id
            (doc_dir / "meta").mkdir(parents=True)
            doc_meta = {
                "doc_id": doc_id,
                "claim_id": claim_id,
                "original_filename": f"estimate_{i+1}.pdf",
                "doc_type": "cost_estimate",
            }
            with open(doc_dir / "meta" / "doc.json", "w") as f:
                json.dump(doc_meta, f)

        run_id = "run_20260124_multi"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        # First cost estimate
        extraction1 = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": "doc_cost_1", "claim_id": claim_id, "doc_type": "cost_estimate"},
            "fields": [],
            "structured_data": {
                "line_items": [
                    {"description": "Item from estimate 1", "total_price": 100.00, "item_type": "parts"}
                ]
            },
        }
        with open(extraction_dir / "doc_cost_1.json", "w") as f:
            json.dump(extraction1, f)

        # Second cost estimate
        extraction2 = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": "doc_cost_2", "claim_id": claim_id, "doc_type": "cost_estimate"},
            "fields": [],
            "structured_data": {
                "line_items": [
                    {"description": "Item from estimate 2", "total_price": 200.00, "item_type": "labor"}
                ]
            },
        }
        with open(extraction_dir / "doc_cost_2.json", "w") as f:
            json.dump(extraction2, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Should have merged line items from both documents
        assert facts.structured_data is not None
        assert len(facts.structured_data.line_items) == 2

        # Verify items come from different sources
        sources = {item.source.doc_id for item in facts.structured_data.line_items}
        assert "doc_cost_1" in sources
        assert "doc_cost_2" in sources

    def test_no_structured_data_returns_none(self, claim_with_extractions):
        """structured_data should be None if no cost estimates with line items."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        # Existing fixture has insurance_policy and loss_notice, not cost_estimate
        assert facts.structured_data is None

    def test_empty_line_items_returns_none(self, tmp_path):
        """structured_data should be None if cost estimate has empty line_items."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-EMPTY-ITEMS"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"
        doc_id = "doc_empty"
        doc_dir = docs_dir / doc_id
        (doc_dir / "meta").mkdir(parents=True)

        doc_meta = {
            "doc_id": doc_id,
            "claim_id": claim_id,
            "original_filename": "empty_estimate.pdf",
            "doc_type": "cost_estimate",
        }
        with open(doc_dir / "meta" / "doc.json", "w") as f:
            json.dump(doc_meta, f)

        run_id = "run_20260124_empty"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc_id, "claim_id": claim_id, "doc_type": "cost_estimate"},
            "fields": [
                {
                    "name": "total_cost",
                    "value": "0.00",
                    "confidence": 0.90,
                    "status": "present",
                    "provenance": [{"page": 1}],
                }
            ],
            "structured_data": {
                "line_items": []  # Empty array
            },
        }
        with open(extraction_dir / f"{doc_id}.json", "w") as f:
            json.dump(extraction, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Empty line_items should result in None structured_data
        assert facts.structured_data is None

    def test_schema_version_is_v2(self, claim_with_extractions):
        """ClaimFacts should use schema_version claim_facts_v2."""
        storage = FileStorage(claim_with_extractions["tmp_path"])
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_with_extractions["claim_id"])

        assert facts.schema_version == "claim_facts_v2"

    def test_service_entries_from_service_history(self, tmp_path):
        """Service entries from service_history should be aggregated with provenance."""
        # Create minimal structure with service history
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-SERVICE-001"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"
        doc_id = "doc_service_001"
        doc_dir = docs_dir / doc_id
        (doc_dir / "meta").mkdir(parents=True)

        doc_meta = {
            "doc_id": doc_id,
            "claim_id": claim_id,
            "original_filename": "service_book.pdf",
            "doc_type": "service_history",
        }
        with open(doc_dir / "meta" / "doc.json", "w") as f:
            json.dump(doc_meta, f)

        # Create run with extraction including structured_data.service_entries
        run_id = "run_20260124_service"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc_id, "claim_id": claim_id, "doc_type": "service_history"},
            "fields": [
                {
                    "name": "service_entries",
                    "value": "2 service entries",
                    "confidence": 0.95,
                    "status": "present",
                    "provenance": [{"page": 1}],
                }
            ],
            "structured_data": {
                "service_entries": [
                    {
                        "service_type": "Inspektion mit Ölwechsel",
                        "service_date": "2024-07-26",
                        "mileage_km": 25451,
                        "order_number": "MDDE523064401",
                        "work_performed": "Full inspection",
                        "additional_work": ["Oil change", "Filter replacement"],
                        "service_provider_name": "VW Service Center",
                        "service_provider_address": "Main Street 123",
                        "is_authorized_partner": True,
                    },
                    {
                        "service_type": "Brake Service",
                        "service_date": "2025-01-15",
                        "mileage_km": 45000,
                        "order_number": "MDDE523064402",
                        "work_performed": None,
                        "additional_work": [],
                        "service_provider_name": None,
                        "service_provider_address": None,
                        "is_authorized_partner": False,
                    },
                ]
            },
        }
        with open(extraction_dir / f"{doc_id}.json", "w") as f:
            json.dump(extraction, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Verify structured_data is populated with service_entries
        assert facts.structured_data is not None
        assert facts.structured_data.service_entries is not None
        assert len(facts.structured_data.service_entries) == 2

        # Verify first service entry details
        first_entry = facts.structured_data.service_entries[0]
        assert first_entry.service_type == "Inspektion mit Ölwechsel"
        assert first_entry.service_date == "2024-07-26"
        assert first_entry.mileage_km == 25451
        assert first_entry.order_number == "MDDE523064401"
        assert first_entry.work_performed == "Full inspection"
        assert first_entry.additional_work == ["Oil change", "Filter replacement"]
        assert first_entry.service_provider_name == "VW Service Center"
        assert first_entry.is_authorized_partner is True
        assert first_entry.source.doc_id == doc_id
        assert first_entry.source.doc_type == "service_history"
        assert first_entry.source.run_id == run_id

        # Verify second entry captures unauthorized partner
        second_entry = facts.structured_data.service_entries[1]
        assert second_entry.is_authorized_partner is False
        assert second_entry.mileage_km == 45000

    def test_multiple_service_histories_merged(self, tmp_path):
        """Service entries from multiple service_history docs should be merged."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-MULTI-SERVICE"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"

        # Create two service_history documents
        for i, doc_id in enumerate(["doc_service_1", "doc_service_2"]):
            doc_dir = docs_dir / doc_id
            (doc_dir / "meta").mkdir(parents=True)
            doc_meta = {
                "doc_id": doc_id,
                "claim_id": claim_id,
                "original_filename": f"service_book_{i+1}.pdf",
                "doc_type": "service_history",
            }
            with open(doc_dir / "meta" / "doc.json", "w") as f:
                json.dump(doc_meta, f)

        run_id = "run_20260124_multi_service"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        # First service history
        extraction1 = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": "doc_service_1", "claim_id": claim_id, "doc_type": "service_history"},
            "fields": [],
            "structured_data": {
                "service_entries": [
                    {
                        "service_type": "Oil Change",
                        "service_date": "2024-01-01",
                        "mileage_km": 10000,
                        "is_authorized_partner": True,
                    }
                ]
            },
        }
        with open(extraction_dir / "doc_service_1.json", "w") as f:
            json.dump(extraction1, f)

        # Second service history
        extraction2 = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": "doc_service_2", "claim_id": claim_id, "doc_type": "service_history"},
            "fields": [],
            "structured_data": {
                "service_entries": [
                    {
                        "service_type": "Brake Check",
                        "service_date": "2024-06-01",
                        "mileage_km": 20000,
                        "is_authorized_partner": False,
                    }
                ]
            },
        }
        with open(extraction_dir / "doc_service_2.json", "w") as f:
            json.dump(extraction2, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Should have merged service entries from both documents
        assert facts.structured_data is not None
        assert len(facts.structured_data.service_entries) == 2

        # Verify entries come from different sources
        sources = {entry.source.doc_id for entry in facts.structured_data.service_entries}
        assert "doc_service_1" in sources
        assert "doc_service_2" in sources

    def test_both_line_items_and_service_entries(self, tmp_path):
        """Both line_items and service_entries can coexist in structured_data."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-BOTH"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"

        # Create cost_estimate document
        doc1_id = "doc_cost"
        doc1_dir = docs_dir / doc1_id
        (doc1_dir / "meta").mkdir(parents=True)
        with open(doc1_dir / "meta" / "doc.json", "w") as f:
            json.dump({
                "doc_id": doc1_id,
                "claim_id": claim_id,
                "original_filename": "estimate.pdf",
                "doc_type": "cost_estimate",
            }, f)

        # Create service_history document
        doc2_id = "doc_service"
        doc2_dir = docs_dir / doc2_id
        (doc2_dir / "meta").mkdir(parents=True)
        with open(doc2_dir / "meta" / "doc.json", "w") as f:
            json.dump({
                "doc_id": doc2_id,
                "claim_id": claim_id,
                "original_filename": "service.pdf",
                "doc_type": "service_history",
            }, f)

        run_id = "run_20260124_both"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        # Cost estimate extraction
        extraction1 = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc1_id, "claim_id": claim_id, "doc_type": "cost_estimate"},
            "fields": [],
            "structured_data": {
                "line_items": [
                    {"description": "Repair work", "total_price": 500.00, "item_type": "labor"}
                ]
            },
        }
        with open(extraction_dir / f"{doc1_id}.json", "w") as f:
            json.dump(extraction1, f)

        # Service history extraction
        extraction2 = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc2_id, "claim_id": claim_id, "doc_type": "service_history"},
            "fields": [],
            "structured_data": {
                "service_entries": [
                    {"service_type": "Inspection", "mileage_km": 30000, "is_authorized_partner": True}
                ]
            },
        }
        with open(extraction_dir / f"{doc2_id}.json", "w") as f:
            json.dump(extraction2, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Both should be present
        assert facts.structured_data is not None
        assert facts.structured_data.line_items is not None
        assert len(facts.structured_data.line_items) == 1
        assert facts.structured_data.service_entries is not None
        assert len(facts.structured_data.service_entries) == 1

        # Verify content
        assert facts.structured_data.line_items[0].description == "Repair work"
        assert facts.structured_data.service_entries[0].service_type == "Inspection"
        assert facts.structured_data.service_entries[0].is_authorized_partner is True

    def test_empty_service_entries_returns_none(self, tmp_path):
        """structured_data.service_entries should be None if service_history has empty array."""
        claims_dir = tmp_path / "claims"
        claims_dir.mkdir()
        claim_id = "CLM-EMPTY-SERVICE"
        claim_folder = claims_dir / claim_id
        docs_dir = claim_folder / "docs"
        doc_id = "doc_empty_service"
        doc_dir = docs_dir / doc_id
        (doc_dir / "meta").mkdir(parents=True)

        with open(doc_dir / "meta" / "doc.json", "w") as f:
            json.dump({
                "doc_id": doc_id,
                "claim_id": claim_id,
                "original_filename": "empty_service.pdf",
                "doc_type": "service_history",
            }, f)

        run_id = "run_20260124_empty_service"
        run_dir = claim_folder / "runs" / run_id
        extraction_dir = run_dir / "extraction"
        extraction_dir.mkdir(parents=True)

        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": run_id},
            "doc": {"doc_id": doc_id, "claim_id": claim_id, "doc_type": "service_history"},
            "fields": [
                {
                    "name": "service_entries",
                    "value": "0 entries",
                    "confidence": 0.90,
                    "status": "present",
                    "provenance": [{"page": 1}],
                }
            ],
            "structured_data": {
                "service_entries": []  # Empty array
            },
        }
        with open(extraction_dir / f"{doc_id}.json", "w") as f:
            json.dump(extraction, f)

        (run_dir / ".complete").touch()

        storage = FileStorage(tmp_path)
        service = AggregationService(storage)

        facts = service.aggregate_claim_facts(claim_id)

        # Empty service_entries should result in None structured_data
        assert facts.structured_data is None
