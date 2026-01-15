"""Integration tests for compliance decision flow.

Tests the end-to-end flow of decision logging:
1. Classification decisions are logged with rationale
2. Extraction decisions include version bundle ID
3. Human review decisions are logged
4. Hash chain integrity is maintained
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
    DecisionQuery,
)
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.storage.version_bundles import VersionBundleStore
from context_builder.storage.truth_store import TruthStore
from context_builder.storage.filesystem import FileStorage


class TestDecisionFlowIntegration:
    """Integration tests for the complete decision flow."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def ledger(self, temp_dir):
        """Create a decision ledger for testing."""
        return DecisionLedger(temp_dir / "logs")

    @pytest.fixture
    def version_bundle_store(self, temp_dir):
        """Create a version bundle store for testing."""
        return VersionBundleStore(temp_dir)

    def test_classification_decision_logged(self, ledger):
        """Test that classification decisions are properly logged."""
        # Simulate classification decision
        record = DecisionRecord(
            decision_id="",
            decision_type=DecisionType.CLASSIFICATION,
            claim_id="CLM-001",
            doc_id="DOC-001",
            rationale=DecisionRationale(
                summary="Document classified as invoice based on header patterns",
                confidence=0.95,
            ),
            outcome=DecisionOutcome(
                doc_type="invoice",
                confidence=0.95,
            ),
            actor_type="system",
            actor_id="gpt-4o-2024-05-13",
        )

        ledger.append(record)

        # Verify record was logged
        records = ledger.query(DecisionQuery(limit=10))
        assert len(records) == 1
        assert records[0].decision_type == DecisionType.CLASSIFICATION
        assert records[0].doc_id == "DOC-001"
        assert records[0].rationale.confidence == 0.95

    def test_extraction_decision_with_version_bundle(self, ledger, version_bundle_store):
        """Test that extraction decisions include version bundle reference."""
        # Create version bundle
        bundle = version_bundle_store.create_version_bundle(
            run_id="run_20260114_120000",
            model_name="gpt-4o",
        )

        # Simulate extraction decision
        record = DecisionRecord(
            decision_id="",
            decision_type=DecisionType.EXTRACTION,
            claim_id="CLM-001",
            doc_id="DOC-001",
            rationale=DecisionRationale(
                summary="Extracted 5 fields from invoice",
                confidence=0.88,
            ),
            outcome=DecisionOutcome(
                fields_extracted=[
                    {"field": "claim_number", "value": "CLM-001"},
                    {"field": "date", "value": "2026-01-14"},
                    {"field": "amount", "value": "1500.00"},
                    {"field": "vendor", "value": "Acme Corp"},
                    {"field": "status", "value": "pending"},
                ],
                quality_gate_status="pass",
            ),
            actor_type="system",
            actor_id="gpt-4o",
            metadata={"version_bundle_id": bundle.bundle_id},
        )

        ledger.append(record)

        # Verify record includes version bundle
        records = ledger.query(DecisionQuery(limit=10))
        assert len(records) == 1
        assert records[0].metadata.get("version_bundle_id") == bundle.bundle_id

    def test_human_review_decision_logged(self, ledger):
        """Test that human review decisions are properly logged."""
        record = DecisionRecord(
            decision_id="",
            decision_type=DecisionType.HUMAN_REVIEW,
            claim_id="CLM-001",
            doc_id="DOC-001",
            rationale=DecisionRationale(
                summary="Human review: 3 fields labeled",
                confidence=1.0,  # Human is authoritative
                notes="Corrected claim_number value",
            ),
            outcome=DecisionOutcome(
                field_corrections=[
                    {"field_name": "claim_number", "state": "LABELED", "truth_value": "CLM-2024-001"},
                ],
            ),
            actor_type="human",
            actor_id="reviewer@example.com",
        )

        ledger.append(record)

        # Verify human review logged
        records = ledger.query(DecisionQuery(limit=10))
        assert len(records) == 1
        assert records[0].decision_type == DecisionType.HUMAN_REVIEW
        assert records[0].actor_type == "human"
        assert records[0].rationale.confidence == 1.0

    def test_override_decision_logged(self, ledger):
        """Test that override decisions capture original and corrected values."""
        record = DecisionRecord(
            decision_id="",
            decision_type=DecisionType.OVERRIDE,
            claim_id="CLM-001",
            doc_id="DOC-001",
            rationale=DecisionRationale(
                summary="Classification override: invoice -> receipt",
                confidence=1.0,
                notes="Document is a receipt, not an invoice",
            ),
            outcome=DecisionOutcome(
                original_value="invoice",
                override_value="receipt",
                override_reason="Document is a receipt, not an invoice",
            ),
            actor_type="human",
            actor_id="reviewer",
        )

        ledger.append(record)

        # Verify override logged
        records = ledger.query(DecisionQuery(limit=10))
        assert len(records) == 1
        assert records[0].decision_type == DecisionType.OVERRIDE
        assert records[0].outcome.original_value == "invoice"
        assert records[0].outcome.override_value == "receipt"

    def test_hash_chain_integrity_maintained(self, ledger):
        """Test that hash chain integrity is maintained across multiple records."""
        # Add multiple records
        for i in range(5):
            record = DecisionRecord(
                decision_id="",
                decision_type=DecisionType.CLASSIFICATION,
                claim_id=f"CLM-{i:03d}",
                doc_id=f"DOC-{i:03d}",
                rationale=DecisionRationale(summary=f"Decision {i}", confidence=0.9),
                outcome=DecisionOutcome(doc_type="invoice"),
                actor_type="system",
                actor_id="gpt-4o",
            )
            ledger.append(record)

        # Verify chain integrity
        report = ledger.verify_integrity()
        assert report.valid is True
        assert report.total_records == 5

    def test_hash_chain_detects_tampering(self, ledger, temp_dir):
        """Test that tampering with the ledger is detected."""
        # Add records
        for i in range(3):
            record = DecisionRecord(
                decision_id="",
                decision_type=DecisionType.CLASSIFICATION,
                claim_id=f"CLM-{i:03d}",
                doc_id=f"DOC-{i:03d}",
                rationale=DecisionRationale(summary=f"Decision {i}", confidence=0.9),
                outcome=DecisionOutcome(doc_type="invoice"),
                actor_type="system",
                actor_id="gpt-4o",
            )
            ledger.append(record)

        # Tamper with the ledger file
        ledger_path = temp_dir / "logs" / "decisions.jsonl"
        with open(ledger_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Modify second record
        record_1 = json.loads(lines[1])
        record_1["doc_id"] = "TAMPERED"
        lines[1] = json.dumps(record_1) + "\n"

        with open(ledger_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Verify tampering is detected
        report = ledger.verify_integrity()
        assert report.valid is False


class TestVersionHistoryIntegration:
    """Integration tests for version history tracking."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with claims folder for proper path resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "claims").mkdir(exist_ok=True)
            yield tmpdir

    def test_truth_store_maintains_history(self, temp_dir):
        """Test that truth store maintains version history."""
        store = TruthStore(temp_dir)

        file_md5 = "test_history_integration"

        # Save multiple versions
        for i in range(3):
            store.save_truth_by_file_md5(file_md5, {
                "doc_type": "invoice",
                "version": i,
                "field_labels": [{"field": f"field_{i}"}],
            })

        # Verify history
        history = store.get_truth_history(file_md5)
        assert len(history) == 3
        assert history[0]["version"] == 0
        assert history[2]["version"] == 2

        # Verify version metadata
        for i, entry in enumerate(history):
            assert "_version_metadata" in entry
            assert entry["_version_metadata"]["version_number"] == i + 1

    def test_truth_store_get_specific_version(self, temp_dir):
        """Test retrieving a specific version of truth."""
        store = TruthStore(temp_dir)

        file_md5 = "test_specific_integration"

        # Save versions
        for i in range(3):
            store.save_truth_by_file_md5(file_md5, {"version": i})

        # Get specific version
        v1 = store.get_truth_version(file_md5, 1)
        v2 = store.get_truth_version(file_md5, 2)
        v3 = store.get_truth_version(file_md5, 3)

        assert v1["version"] == 0
        assert v2["version"] == 1
        assert v3["version"] == 2

        # Invalid version returns None
        assert store.get_truth_version(file_md5, 0) is None
        assert store.get_truth_version(file_md5, 4) is None


class TestVersionBundleIntegration:
    """Integration tests for version bundle creation and retrieval."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_version_bundle_created_with_metadata(self, temp_dir):
        """Test that version bundle captures relevant metadata."""
        store = VersionBundleStore(temp_dir)

        bundle = store.create_version_bundle(
            run_id="run_20260114_120000",
            model_name="gpt-4o",
            model_version="2024-05-13",
            extractor_version="v1.0.0",
        )

        assert bundle.bundle_id.startswith("vb_")
        assert bundle.model_name == "gpt-4o"
        assert bundle.model_version == "2024-05-13"
        assert bundle.extractor_version == "v1.0.0"
        # Version is read from pyproject.toml, just verify it's populated
        assert bundle.contextbuilder_version is not None

    def test_version_bundle_retrievable(self, temp_dir):
        """Test that version bundle can be retrieved after creation."""
        store = VersionBundleStore(temp_dir)

        bundle = store.create_version_bundle(
            run_id="run_20260114_120000",
            model_name="gpt-4o",
        )

        # Retrieve
        retrieved = store.get_version_bundle("run_20260114_120000")
        assert retrieved is not None
        assert retrieved.bundle_id == bundle.bundle_id
        assert retrieved.model_name == "gpt-4o"

    def test_version_bundle_list(self, temp_dir):
        """Test listing all version bundles."""
        store = VersionBundleStore(temp_dir)

        # Create multiple bundles
        store.create_version_bundle(run_id="run_1", model_name="gpt-4o")
        store.create_version_bundle(run_id="run_2", model_name="gpt-4o-mini")
        store.create_version_bundle(run_id="run_3", model_name="gpt-4o")

        # List bundles
        bundle_ids = store.list_bundles()
        assert len(bundle_ids) == 3
        assert "run_1" in bundle_ids
        assert "run_2" in bundle_ids
        assert "run_3" in bundle_ids


class TestLabelHistoryIntegration:
    """Integration tests for label version history."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with document structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create document structure
            doc_dir = tmpdir / "claims" / "CLM-001" / "docs" / "DOC-001"
            (doc_dir / "meta").mkdir(parents=True)
            with open(doc_dir / "meta" / "doc.json", "w") as f:
                json.dump({"doc_id": "DOC-001", "claim_id": "CLM-001"}, f)
            yield tmpdir

    def test_label_history_maintained(self, temp_dir):
        """Test that label save maintains version history."""
        storage = FileStorage(temp_dir / "claims")

        # Save multiple label versions
        for i in range(3):
            storage.save_label("DOC-001", {
                "doc_id": "DOC-001",
                "version": i,
                "field_labels": [{"field": f"field_{i}"}],
            })

        # Get history
        history = storage.get_label_history("DOC-001")
        assert len(history) == 3
        assert history[0]["version"] == 0
        assert history[2]["version"] == 2

        # Verify version metadata
        for i, entry in enumerate(history):
            assert "_version_metadata" in entry
            assert entry["_version_metadata"]["version_number"] == i + 1

    def test_latest_label_includes_version_metadata(self, temp_dir):
        """Test that latest.json includes version metadata."""
        storage = FileStorage(temp_dir / "claims")

        storage.save_label("DOC-001", {"doc_id": "DOC-001", "data": "test"})

        label = storage.get_label("DOC-001")
        assert "_version_metadata" in label
        assert "saved_at" in label["_version_metadata"]
        assert label["_version_metadata"]["version_number"] == 1
