"""Unit tests for metrics computation.

These tests verify that metrics are computed correctly, especially
the critical doc_type_correct filtering behavior.
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from context_builder.pipeline.metrics import compute_run_metrics, _compute_field_metrics
from context_builder.pipeline.paths import RunPaths, get_claim_paths, get_run_paths


class TestDocTypeCorrectFiltering:
    """Tests verifying metrics filter by doc_type_correct."""

    @pytest.fixture
    def claim_with_labels(self, tmp_path):
        """Create a claim structure with extractions and labels."""
        claim_dir = tmp_path / "test_claim"
        docs_dir = claim_dir / "docs"
        runs_dir = claim_dir / "runs"
        run_dir = runs_dir / "run_001"
        extraction_dir = run_dir / "extraction"
        logs_dir = run_dir / "logs"

        # Create directories
        docs_dir.mkdir(parents=True)
        extraction_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)

        return {
            "claim_dir": claim_dir,
            "docs_dir": docs_dir,
            "runs_dir": runs_dir,
            "run_dir": run_dir,
            "extraction_dir": extraction_dir,
        }

    def _create_doc_with_label(
        self,
        docs_dir: Path,
        doc_id: str,
        doc_type_correct: bool,
        field_judgement: str = "correct",
    ):
        """Helper to create a doc folder with extraction and label."""
        doc_dir = docs_dir / doc_id
        labels_dir = doc_dir / "labels"
        labels_dir.mkdir(parents=True)

        label = {
            "schema_version": "label_v1",
            "doc_id": doc_id,
            "claim_id": "test_claim",
            "review": {
                "reviewed_at": datetime.now().isoformat(),
                "reviewer": "test",
            },
            "field_labels": [
                {"field_name": "incident_date", "judgement": field_judgement}
            ],
            "doc_labels": {
                "doc_type_correct": doc_type_correct,
                "text_readable": "good",
                "needs_vision": False,
            },
        }

        (labels_dir / "latest.json").write_text(json.dumps(label))

    def _create_extraction(
        self,
        extraction_dir: Path,
        doc_id: str,
        doc_type: str = "loss_notice",
    ):
        """Helper to create an extraction file."""
        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {
                "run_id": "run_001",
                "extractor_version": "1.0",
                "model": "gpt-4o",
                "prompt_version": "v1",
            },
            "doc": {
                "doc_id": doc_id,
                "claim_id": "test_claim",
                "doc_type": doc_type,
                "doc_type_confidence": 0.9,
                "language": "es",
                "page_count": 1,
            },
            "pages": [{"page": 1, "text": "Test content", "text_md5": "abc123"}],
            "fields": [
                {
                    "name": "incident_date",
                    "value": "2024-01-15",
                    "normalized_value": "2024-01-15",
                    "confidence": 0.9,
                    "status": "present",
                    "provenance": [
                        {
                            "page": 1,
                            "method": "di_text",
                            "text_quote": "January 15, 2024",
                            "char_start": 0,
                            "char_end": 17,
                        }
                    ],
                }
            ],
            "quality_gate": {"status": "pass", "reasons": []},
        }

        (extraction_dir / f"{doc_id}.json").write_text(json.dumps(extraction))

    def test_excludes_docs_with_wrong_type(self, claim_with_labels):
        """Test that docs with doc_type_correct=False are excluded from metrics."""
        docs_dir = claim_with_labels["docs_dir"]
        extraction_dir = claim_with_labels["extraction_dir"]

        # Create doc1: doc_type_correct=True, should be included
        self._create_doc_with_label(docs_dir, "doc1", doc_type_correct=True)
        self._create_extraction(extraction_dir, "doc1")

        # Create doc2: doc_type_correct=False, should be excluded
        self._create_doc_with_label(docs_dir, "doc2", doc_type_correct=False)
        self._create_extraction(extraction_dir, "doc2")

        # Compute field metrics
        field_metrics = _compute_field_metrics(
            extraction_dir=extraction_dir,
            docs_dir=docs_dir,
            doc_ids={"doc1", "doc2"},
        )

        # Only doc1 should contribute to metrics
        # doc2 should be excluded due to doc_type_correct=False
        assert field_metrics["docs_excluded_wrong_type"] == 1
        assert field_metrics["fields_with_label"] == 1  # Only from doc1

    def test_includes_docs_with_correct_type(self, claim_with_labels):
        """Test that docs with doc_type_correct=True are included."""
        docs_dir = claim_with_labels["docs_dir"]
        extraction_dir = claim_with_labels["extraction_dir"]

        # Create two docs both with correct type
        self._create_doc_with_label(docs_dir, "doc1", doc_type_correct=True)
        self._create_extraction(extraction_dir, "doc1")

        self._create_doc_with_label(docs_dir, "doc2", doc_type_correct=True)
        self._create_extraction(extraction_dir, "doc2")

        # Compute field metrics
        field_metrics = _compute_field_metrics(
            extraction_dir=extraction_dir,
            docs_dir=docs_dir,
            doc_ids={"doc1", "doc2"},
        )

        # Both docs should contribute
        assert field_metrics["docs_excluded_wrong_type"] == 0
        assert field_metrics["fields_with_label"] == 2  # From both docs

    def test_skips_docs_without_labels(self, claim_with_labels):
        """Test that docs without labels are skipped but not counted as wrong type."""
        docs_dir = claim_with_labels["docs_dir"]
        extraction_dir = claim_with_labels["extraction_dir"]

        # Create doc with label
        self._create_doc_with_label(docs_dir, "doc1", doc_type_correct=True)
        self._create_extraction(extraction_dir, "doc1")

        # Create doc without label (just doc folder, no labels)
        (docs_dir / "doc2").mkdir(parents=True)
        self._create_extraction(extraction_dir, "doc2")

        # Compute field metrics
        field_metrics = _compute_field_metrics(
            extraction_dir=extraction_dir,
            docs_dir=docs_dir,
            doc_ids={"doc1", "doc2"},
        )

        # doc2 has no label file, so it's skipped entirely (not in doc_ids & labeled_ids)
        # Only doc1 contributes
        assert field_metrics["docs_excluded_wrong_type"] == 0
        assert field_metrics["fields_with_label"] == 1


class TestAccuracyComputation:
    """Tests for field accuracy computation."""

    @pytest.fixture
    def claim_setup(self, tmp_path):
        """Create basic claim structure."""
        claim_dir = tmp_path / "test_claim"
        docs_dir = claim_dir / "docs"
        run_dir = claim_dir / "runs" / "run_001"
        extraction_dir = run_dir / "extraction"
        logs_dir = run_dir / "logs"

        docs_dir.mkdir(parents=True)
        extraction_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)

        return {
            "claim_dir": claim_dir,
            "docs_dir": docs_dir,
            "extraction_dir": extraction_dir,
        }

    def _create_doc_with_judgement(
        self, docs_dir, extraction_dir, doc_id, judgement
    ):
        """Create a doc with specific field judgement."""
        # Create label
        labels_dir = docs_dir / doc_id / "labels"
        labels_dir.mkdir(parents=True)

        label = {
            "schema_version": "label_v1",
            "doc_id": doc_id,
            "claim_id": "test_claim",
            "review": {
                "reviewed_at": datetime.now().isoformat(),
                "reviewer": "test",
            },
            "field_labels": [
                {"field_name": "incident_date", "judgement": judgement}
            ],
            "doc_labels": {
                "doc_type_correct": True,
                "text_readable": "good",
                "needs_vision": False,
            },
        }
        (labels_dir / "latest.json").write_text(json.dumps(label))

        # Create extraction
        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": "run", "extractor_version": "1", "model": "gpt", "prompt_version": "v1"},
            "doc": {
                "doc_id": doc_id,
                "claim_id": "test_claim",
                "doc_type": "loss_notice",
                "doc_type_confidence": 0.9,
                "language": "es",
                "page_count": 1,
            },
            "pages": [],
            "fields": [
                {
                    "name": "incident_date",
                    "value": "2024-01-15",
                    "confidence": 0.9,
                    "status": "present",
                    "provenance": [],
                }
            ],
            "quality_gate": {"status": "pass"},
        }
        (extraction_dir / f"{doc_id}.json").write_text(json.dumps(extraction))

    def test_accuracy_100_percent(self, claim_setup):
        """Test 100% accuracy when all fields are correct."""
        docs_dir = claim_setup["docs_dir"]
        extraction_dir = claim_setup["extraction_dir"]

        # All docs have correct fields
        self._create_doc_with_judgement(docs_dir, extraction_dir, "doc1", "correct")
        self._create_doc_with_judgement(docs_dir, extraction_dir, "doc2", "correct")

        metrics = _compute_field_metrics(
            extraction_dir=extraction_dir,
            docs_dir=docs_dir,
            doc_ids={"doc1", "doc2"},
        )

        assert metrics["required_field_accuracy_pct"] == 100.0

    def test_accuracy_50_percent(self, claim_setup):
        """Test 50% accuracy when half fields are incorrect."""
        docs_dir = claim_setup["docs_dir"]
        extraction_dir = claim_setup["extraction_dir"]

        # One correct, one incorrect
        self._create_doc_with_judgement(docs_dir, extraction_dir, "doc1", "correct")
        self._create_doc_with_judgement(docs_dir, extraction_dir, "doc2", "incorrect")

        metrics = _compute_field_metrics(
            extraction_dir=extraction_dir,
            docs_dir=docs_dir,
            doc_ids={"doc1", "doc2"},
        )

        assert metrics["required_field_accuracy_pct"] == 50.0


class TestEmptyMetrics:
    """Tests for edge cases with empty data."""

    def test_empty_doc_ids(self, tmp_path):
        """Test metrics with no doc_ids."""
        extraction_dir = tmp_path / "extraction"
        docs_dir = tmp_path / "docs"
        extraction_dir.mkdir()
        docs_dir.mkdir()

        metrics = _compute_field_metrics(
            extraction_dir=extraction_dir,
            docs_dir=docs_dir,
            doc_ids=set(),  # Empty
        )

        assert metrics["total_fields"] == 0
        assert metrics["fields_with_label"] == 0
        assert metrics["required_field_accuracy_pct"] == 0
        assert metrics["docs_excluded_wrong_type"] == 0


class TestComputeRunMetrics:
    """Tests for the full compute_run_metrics function."""

    def test_coverage_metrics(self, tmp_path):
        """Test that coverage metrics are computed correctly."""
        claim_dir = tmp_path / "test_claim"
        docs_dir = claim_dir / "docs"
        run_dir = claim_dir / "runs" / "run_001"
        extraction_dir = run_dir / "extraction"
        logs_dir = run_dir / "logs"

        docs_dir.mkdir(parents=True)
        extraction_dir.mkdir(parents=True)
        logs_dir.mkdir(parents=True)

        # Create 3 docs total, 2 with labels, 1 in run extraction
        for doc_id in ["doc1", "doc2", "doc3"]:
            (docs_dir / doc_id).mkdir()

        # Create labels for doc1 and doc2
        for doc_id in ["doc1", "doc2"]:
            labels_dir = docs_dir / doc_id / "labels"
            labels_dir.mkdir()
            label = {
                "schema_version": "label_v1",
                "doc_id": doc_id,
                "claim_id": "test_claim",
                "review": {"reviewed_at": datetime.now().isoformat(), "reviewer": "test"},
                "field_labels": [],
                "doc_labels": {"doc_type_correct": True, "text_readable": "good", "needs_vision": False},
            }
            (labels_dir / "latest.json").write_text(json.dumps(label))

        # Create extraction for doc1 only
        extraction = {
            "schema_version": "extraction_result_v1",
            "run": {"run_id": "run", "extractor_version": "1", "model": "gpt", "prompt_version": "v1"},
            "doc": {"doc_id": "doc1", "claim_id": "test_claim", "doc_type": "loss_notice", "doc_type_confidence": 0.9, "language": "es", "page_count": 1},
            "pages": [],
            "fields": [],
            "quality_gate": {"status": "pass"},
        }
        (extraction_dir / "doc1.json").write_text(json.dumps(extraction))

        # Create RunPaths
        claim_paths = get_claim_paths(tmp_path, "test_claim")
        run_paths = get_run_paths(claim_paths, "run_001")

        # Compute metrics
        metrics = compute_run_metrics(run_paths, claim_dir)

        assert metrics["coverage"]["docs_total"] == 3
        assert metrics["coverage"]["docs_labeled"] == 2
        assert metrics["coverage"]["docs_in_run"] == 1
        assert metrics["coverage"]["docs_labeled_and_in_run"] == 1
