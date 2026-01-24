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
    ClaimFacts,
    FactProvenance,
    SourceDocument,
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
        assert written_data["schema_version"] == "claim_facts_v1"
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
