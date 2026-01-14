"""Unit tests for compliance API endpoints.

Tests the REST API endpoints for compliance verification and audit queries.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestLedgerVerifyEndpoint:
    """Tests for ledger verification."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_verify_empty_ledger(self, temp_dir):
        """Test verification with empty ledger."""
        from context_builder.services.decision_ledger import DecisionLedger

        ledger = DecisionLedger(temp_dir / "logs")
        report = ledger.verify_integrity()

        assert report.valid is True
        assert report.total_records == 0

    def test_verify_valid_chain(self, temp_dir):
        """Test verification with valid hash chain."""
        from context_builder.services.decision_ledger import DecisionLedger
        from context_builder.schemas.decision_record import (
            DecisionRecord,
            DecisionType,
            DecisionRationale,
            DecisionOutcome,
        )

        ledger = DecisionLedger(temp_dir / "logs")

        # Add records
        for i in range(5):
            record = DecisionRecord(
                decision_id="",
                decision_type=DecisionType.CLASSIFICATION,
                claim_id=f"CLM-{i:03d}",
                doc_id=f"DOC-{i:03d}",
                rationale=DecisionRationale(summary=f"Test {i}", confidence=0.95),
                outcome=DecisionOutcome(doc_type="invoice"),
                actor_type="system",
                actor_id="test",
            )
            ledger.append(record)

        report = ledger.verify_integrity()
        assert report.valid is True
        assert report.total_records == 5

    def test_verify_detects_tampering(self, temp_dir):
        """Test that tampering is detected."""
        from context_builder.services.decision_ledger import DecisionLedger
        from context_builder.schemas.decision_record import (
            DecisionRecord,
            DecisionType,
            DecisionRationale,
            DecisionOutcome,
        )

        ledger = DecisionLedger(temp_dir / "logs")

        # Add records
        for i in range(3):
            record = DecisionRecord(
                decision_id="",
                decision_type=DecisionType.CLASSIFICATION,
                claim_id=f"CLM-{i:03d}",
                doc_id=f"DOC-{i:03d}",
                rationale=DecisionRationale(summary=f"Test {i}", confidence=0.95),
                outcome=DecisionOutcome(doc_type="invoice"),
                actor_type="system",
                actor_id="test",
            )
            ledger.append(record)

        # Tamper with ledger
        ledger_path = temp_dir / "logs" / "decisions.jsonl"
        with open(ledger_path, "r") as f:
            lines = f.readlines()

        # Modify middle record
        record = json.loads(lines[1])
        record["doc_id"] = "TAMPERED"
        lines[1] = json.dumps(record) + "\n"

        with open(ledger_path, "w") as f:
            f.writelines(lines)

        # Verify should fail
        report = ledger.verify_integrity()
        assert report.valid is False


class TestDecisionQueryEndpoint:
    """Tests for decision query functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def ledger_with_records(self, temp_dir):
        """Create a ledger with test records."""
        from context_builder.services.decision_ledger import DecisionLedger
        from context_builder.schemas.decision_record import (
            DecisionRecord,
            DecisionType,
            DecisionRationale,
            DecisionOutcome,
        )

        ledger = DecisionLedger(temp_dir / "logs")

        # Add various records
        records = [
            ("CLM-001", "DOC-001", DecisionType.CLASSIFICATION),
            ("CLM-001", "DOC-002", DecisionType.EXTRACTION),
            ("CLM-002", "DOC-003", DecisionType.CLASSIFICATION),
            ("CLM-002", "DOC-003", DecisionType.HUMAN_REVIEW),
        ]

        for claim_id, doc_id, dtype in records:
            record = DecisionRecord(
                decision_id="",
                decision_type=dtype,
                claim_id=claim_id,
                doc_id=doc_id,
                rationale=DecisionRationale(summary=f"Test {dtype.value}", confidence=0.9),
                outcome=DecisionOutcome(doc_type="invoice"),
                actor_type="system" if dtype != DecisionType.HUMAN_REVIEW else "human",
                actor_id="test",
            )
            ledger.append(record)

        return ledger

    def test_query_all_records(self, ledger_with_records):
        """Test querying all records."""
        from context_builder.schemas.decision_record import DecisionQuery

        records = ledger_with_records.query(DecisionQuery(limit=100))
        assert len(records) == 4

    def test_query_by_decision_type(self, ledger_with_records):
        """Test filtering by decision type."""
        from context_builder.schemas.decision_record import DecisionType, DecisionQuery

        records = ledger_with_records.query(
            DecisionQuery(decision_type=DecisionType.CLASSIFICATION, limit=100)
        )
        assert len(records) == 2
        assert all(r.decision_type == DecisionType.CLASSIFICATION for r in records)

    def test_query_by_doc_id(self, ledger_with_records):
        """Test filtering by doc_id."""
        from context_builder.schemas.decision_record import DecisionQuery

        records = ledger_with_records.query(DecisionQuery(doc_id="DOC-003", limit=100))
        assert len(records) == 2
        assert all(r.doc_id == "DOC-003" for r in records)

    def test_query_by_claim_id(self, ledger_with_records):
        """Test filtering by claim_id."""
        from context_builder.schemas.decision_record import DecisionQuery

        records = ledger_with_records.query(DecisionQuery(claim_id="CLM-001", limit=100))
        assert len(records) == 2
        assert all(r.claim_id == "CLM-001" for r in records)

    def test_query_with_limit(self, ledger_with_records):
        """Test limiting results."""
        from context_builder.schemas.decision_record import DecisionQuery

        records = ledger_with_records.query(DecisionQuery(limit=2))
        assert len(records) == 2


class TestVersionBundleEndpoints:
    """Tests for version bundle functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def bundle_store(self, temp_dir):
        """Create a VersionBundleStore with test data."""
        from context_builder.storage.version_bundles import VersionBundleStore

        store = VersionBundleStore(temp_dir)

        # Create test bundles
        store.create_version_bundle(run_id="run_1", model_name="gpt-4o")
        store.create_version_bundle(run_id="run_2", model_name="gpt-4o-mini")
        store.create_version_bundle(run_id="run_3", model_name="gpt-4o")

        return store

    def test_list_bundles(self, bundle_store):
        """Test listing version bundles."""
        run_ids = bundle_store.list_bundles()
        assert len(run_ids) == 3
        assert "run_1" in run_ids
        assert "run_2" in run_ids
        assert "run_3" in run_ids

    def test_get_bundle_details(self, bundle_store):
        """Test getting bundle details."""
        bundle = bundle_store.get_version_bundle("run_1")
        assert bundle is not None
        assert bundle.model_name == "gpt-4o"
        assert bundle.bundle_id.startswith("vb_")

    def test_get_nonexistent_bundle(self, bundle_store):
        """Test getting nonexistent bundle."""
        bundle = bundle_store.get_version_bundle("nonexistent")
        assert bundle is None


class TestConfigHistoryEndpoint:
    """Tests for config history functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config_service(self, temp_dir):
        """Create a config service with test data."""
        from context_builder.api.services.prompt_config import PromptConfigService

        service = PromptConfigService(temp_dir / "config")

        # Make some changes
        service.create_config(name="config1", model="gpt-4o")
        service.create_config(name="config2", model="gpt-4o")
        service.update_config("config1", {"temperature": 0.5})

        return service

    def test_get_config_history(self, config_service):
        """Test getting config change history."""
        history = config_service.get_config_history()
        assert len(history) >= 3  # May have more from defaults

        actions = [h["action"] for h in history]
        assert "create" in actions

    def test_history_has_timestamps(self, config_service):
        """Test that history entries have timestamps."""
        history = config_service.get_config_history()
        for entry in history:
            assert "timestamp" in entry
            # Should parse as ISO datetime
            datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

    def test_history_has_config_id(self, config_service):
        """Test that history entries have config_id."""
        history = config_service.get_config_history()
        for entry in history:
            if entry["action"] in ("create", "update", "delete"):
                assert "config_id" in entry


class TestTruthHistoryEndpoint:
    """Tests for truth history functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with claims folder for proper path resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            (tmpdir / "claims").mkdir(exist_ok=True)
            yield tmpdir

    @pytest.fixture
    def truth_store(self, temp_dir):
        """Create a truth store instance."""
        from context_builder.storage.truth_store import TruthStore
        return TruthStore(temp_dir)

    def test_get_truth_history(self, truth_store):
        """Test getting truth history."""
        file_md5 = "test_history_abc123"
        # Save multiple versions
        for i in range(3):
            truth_store.save_truth_by_file_md5(file_md5, {
                "version": i,
                "field_labels": [{"field": f"field_{i}"}],
                "review": {"reviewer": f"user{i}"},
            })

        history = truth_store.get_truth_history(file_md5)
        assert len(history) == 3

    def test_history_has_version_numbers(self, truth_store):
        """Test that history has version numbers."""
        file_md5 = "test_version_abc123"
        for i in range(3):
            truth_store.save_truth_by_file_md5(file_md5, {
                "version": i,
            })

        history = truth_store.get_truth_history(file_md5)
        for i, entry in enumerate(history):
            assert entry["_version_metadata"]["version_number"] == i + 1

    def test_nonexistent_file_returns_empty(self, truth_store):
        """Test that nonexistent file returns empty history."""
        history = truth_store.get_truth_history("nonexistent")
        assert history == []


class TestLabelHistoryEndpoint:
    """Tests for label history functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with document structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            # Create document structure
            doc_dir = tmpdir / "claims" / "CLM-001" / "docs" / "DOC-001"
            (doc_dir / "meta").mkdir(parents=True)
            (doc_dir / "labels").mkdir(parents=True)
            with open(doc_dir / "meta" / "doc.json", "w") as f:
                json.dump({"doc_id": "DOC-001", "claim_id": "CLM-001"}, f)
            yield tmpdir

    @pytest.fixture
    def storage_with_labels(self, temp_dir):
        """Create storage with label history."""
        from context_builder.storage.filesystem import FileStorage

        storage = FileStorage(temp_dir / "claims")

        # Save multiple label versions
        for i in range(3):
            storage.save_label("DOC-001", {
                "doc_id": "DOC-001",
                "version": i,
                "field_labels": [{"field": f"field_{i}"}],
                "review": {"reviewer": f"user{i}"},
            })

        return storage

    def test_get_label_history(self, storage_with_labels):
        """Test getting label history."""
        history = storage_with_labels.get_label_history("DOC-001")
        assert len(history) == 3

    def test_history_has_version_metadata(self, storage_with_labels):
        """Test that history has version metadata."""
        history = storage_with_labels.get_label_history("DOC-001")
        for i, entry in enumerate(history):
            assert "_version_metadata" in entry
            assert entry["_version_metadata"]["version_number"] == i + 1

    def test_nonexistent_doc_returns_empty(self, storage_with_labels):
        """Test that nonexistent doc returns empty history."""
        history = storage_with_labels.get_label_history("NONEXISTENT")
        assert history == []


class TestComplianceApiResponses:
    """Tests for API response format compliance."""

    def test_decision_record_serializable(self):
        """Test that decision records are JSON serializable."""
        from context_builder.schemas.decision_record import (
            DecisionRecord,
            DecisionType,
            DecisionRationale,
            DecisionOutcome,
        )

        record = DecisionRecord(
            decision_id="test_123",
            decision_type=DecisionType.CLASSIFICATION,
            claim_id="CLM-001",
            doc_id="DOC-001",
            rationale=DecisionRationale(
                summary="Test rationale",
                confidence=0.95,
            ),
            outcome=DecisionOutcome(
                doc_type="invoice",
                confidence=0.95,
            ),
            actor_type="system",
            actor_id="gpt-4o",
        )

        # Should serialize without error
        serialized = record.model_dump()
        json_str = json.dumps(serialized, default=str)
        assert json_str is not None

    def test_version_bundle_serializable(self):
        """Test that version bundles are JSON serializable."""
        from context_builder.storage.version_bundles import VersionBundle

        bundle = VersionBundle(
            bundle_id="vb_test",
            created_at="2026-01-14T12:00:00Z",
            git_commit="abc123",
            git_dirty=False,
            contextbuilder_version="1.0.0",
            extractor_version="v1.0.0",
            model_name="gpt-4o",
            model_version="2024-05-13",
        )

        # Should serialize without error
        json_str = json.dumps(bundle.__dict__, default=str)
        assert json_str is not None

    def test_integrity_report_has_expected_fields(self):
        """Test that IntegrityReport has expected fields."""
        from context_builder.schemas.decision_record import IntegrityReport

        report = IntegrityReport(
            valid=True,
            total_records=10,
            verified_at="2026-01-14T12:00:00Z",
        )

        assert report.valid is True
        assert report.total_records == 10
        assert report.break_at_index is None
        assert report.error_type is None
