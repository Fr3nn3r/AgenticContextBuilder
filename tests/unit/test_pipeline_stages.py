"""Unit tests for pipeline stage-selective execution.

Tests for:
- PipelineStage enum
- StageConfig dataclass and its properties
- parse_stages() CLI helper
- load_existing_ingestion() and load_existing_classification()
- Stage-aware process_document() behavior
"""

import json
from pathlib import Path
import shutil
from uuid import uuid4
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from context_builder.schemas.run_errors import PipelineStage
from context_builder.pipeline.stages import StageConfig, DocResult
from context_builder.pipeline.stages.ingestion import load_existing_ingestion
from context_builder.pipeline.stages.classification import load_existing_classification
from context_builder.cli import parse_stages


@pytest.fixture
def tmp_path() -> Path:
    base = Path.cwd() / "output" / "pytest-tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"tmp-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


class TestPipelineStage:
    """Tests for PipelineStage enum."""

    def test_stage_values(self):
        """Verify all expected stage values exist."""
        assert PipelineStage.INGEST.value == "ingest"
        assert PipelineStage.CLASSIFY.value == "classify"
        assert PipelineStage.EXTRACT.value == "extract"

    def test_stage_count(self):
        """Verify exactly 3 stages exist."""
        assert len(PipelineStage) == 3


class TestStageConfig:
    """Tests for StageConfig dataclass."""

    def test_default_stages(self):
        """Default config should include all stages."""
        config = StageConfig()
        assert PipelineStage.INGEST in config.stages
        assert PipelineStage.CLASSIFY in config.stages
        assert PipelineStage.EXTRACT in config.stages

    def test_default_run_kind(self):
        """Default config should have run_kind='full'."""
        config = StageConfig()
        assert config.run_kind == "full"

    def test_default_run_flags(self):
        """Default config should have all run flags True."""
        config = StageConfig()
        assert config.run_ingest is True
        assert config.run_classify is True
        assert config.run_extract is True

    def test_classify_extract_only(self):
        """Config with classify+extract should skip ingestion."""
        config = StageConfig(stages=[PipelineStage.CLASSIFY, PipelineStage.EXTRACT])
        assert config.run_ingest is False
        assert config.run_classify is True
        assert config.run_extract is True
        assert config.run_kind == "classify_extract"

    def test_extract_only(self):
        """Config with extract only should skip ingestion and classification."""
        config = StageConfig(stages=[PipelineStage.EXTRACT])
        assert config.run_ingest is False
        assert config.run_classify is False
        assert config.run_extract is True
        assert config.run_kind == "extract_only"

    def test_classify_only(self):
        """Config with classify only."""
        config = StageConfig(stages=[PipelineStage.CLASSIFY])
        assert config.run_ingest is False
        assert config.run_classify is True
        assert config.run_extract is False
        assert config.run_kind == "classify_only"

    def test_ingest_only(self):
        """Config with ingest only."""
        config = StageConfig(stages=[PipelineStage.INGEST])
        assert config.run_ingest is True
        assert config.run_classify is False
        assert config.run_extract is False
        assert config.run_kind == "ingest_only"

    def test_ingest_extract_combination(self):
        """Config with ingest+extract (no classify) still reports extract_only.

        Note: This combination doesn't make practical sense (can't extract without
        doc_type from classification), but the run_kind logic matches on extract.
        """
        config = StageConfig(stages=[PipelineStage.INGEST, PipelineStage.EXTRACT])
        assert config.run_ingest is True
        assert config.run_classify is False
        assert config.run_extract is True
        # run_kind prioritizes extract check, so this returns extract_only
        assert config.run_kind == "extract_only"


class TestParseStages:
    """Tests for parse_stages() CLI helper."""

    def test_parse_all_stages(self):
        """Parse full stages string."""
        stages = parse_stages("ingest,classify,extract")
        assert len(stages) == 3
        assert PipelineStage.INGEST in stages
        assert PipelineStage.CLASSIFY in stages
        assert PipelineStage.EXTRACT in stages

    def test_parse_classify_extract(self):
        """Parse classify,extract only."""
        stages = parse_stages("classify,extract")
        assert len(stages) == 2
        assert PipelineStage.INGEST not in stages
        assert PipelineStage.CLASSIFY in stages
        assert PipelineStage.EXTRACT in stages

    def test_parse_single_stage(self):
        """Parse single stage."""
        stages = parse_stages("extract")
        assert len(stages) == 1
        assert stages[0] == PipelineStage.EXTRACT

    def test_parse_with_spaces(self):
        """Parse stages with spaces around commas."""
        stages = parse_stages("ingest , classify , extract")
        assert len(stages) == 3

    def test_parse_case_insensitive(self):
        """Parse stages should be case-insensitive."""
        stages = parse_stages("INGEST,Classify,EXTRACT")
        assert len(stages) == 3
        assert PipelineStage.INGEST in stages

    def test_parse_invalid_stage(self):
        """Invalid stage should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            parse_stages("ingest,invalid,extract")
        assert "Invalid stage 'invalid'" in str(excinfo.value)

    def test_parse_empty_string(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            parse_stages("")


class TestLoadExistingIngestion:
    """Tests for load_existing_ingestion()."""

    @pytest.fixture
    def doc_paths_with_pages(self, tmp_path):
        """Create mock DocPaths with valid pages.json."""
        # Create a mock DocPaths object
        doc_paths = MagicMock()
        pages_json = tmp_path / "pages.json"

        pages_data = {
            "doc_id": "test_doc_123",
            "page_count": 2,
            "pages": [
                {"page": 1, "text": "Page 1 content here."},
                {"page": 2, "text": "Page 2 content here."},
            ],
        }
        pages_json.write_text(json.dumps(pages_data), encoding="utf-8")

        doc_paths.pages_json = pages_json
        return doc_paths, pages_data

    @pytest.fixture
    def doc_paths_without_pages(self, tmp_path):
        """Create mock DocPaths without pages.json."""
        doc_paths = MagicMock()
        doc_paths.pages_json = tmp_path / "nonexistent_pages.json"
        return doc_paths

    def test_load_existing_pages_json(self, doc_paths_with_pages):
        """Successfully load existing pages.json."""
        doc_paths, expected_data = doc_paths_with_pages

        text_content, pages_data = load_existing_ingestion(doc_paths)

        assert pages_data["doc_id"] == "test_doc_123"
        assert pages_data["page_count"] == 2
        assert "Page 1 content" in text_content
        assert "Page 2 content" in text_content

    def test_load_missing_pages_json(self, doc_paths_without_pages):
        """Raise FileNotFoundError when pages.json missing."""
        with pytest.raises(FileNotFoundError) as excinfo:
            load_existing_ingestion(doc_paths_without_pages)
        assert "pages.json not found" in str(excinfo.value)

    def test_reconstructed_text_from_pages(self, doc_paths_with_pages):
        """Text should be reconstructed from all pages."""
        doc_paths, _ = doc_paths_with_pages

        text_content, _ = load_existing_ingestion(doc_paths)

        # Text should contain content from both pages
        assert "Page 1 content" in text_content
        assert "Page 2 content" in text_content


class TestLoadExistingClassification:
    """Tests for load_existing_classification()."""

    @pytest.fixture
    def doc_paths_with_doc_json(self, tmp_path):
        """Create mock DocPaths with valid doc.json."""
        doc_paths = MagicMock()
        doc_json = tmp_path / "doc.json"

        doc_meta = {
            "doc_id": "test_doc_123",
            "doc_type": "fnol_form",
            "doc_type_confidence": 0.95,
            "language": "en",
            "content_md5": "abc123",
        }
        doc_json.write_text(json.dumps(doc_meta), encoding="utf-8")

        doc_paths.doc_json = doc_json
        return doc_paths, doc_meta

    @pytest.fixture
    def doc_paths_without_doc_json(self, tmp_path):
        """Create mock DocPaths without doc.json."""
        doc_paths = MagicMock()
        doc_paths.doc_json = tmp_path / "nonexistent_doc.json"
        return doc_paths

    def test_load_existing_doc_json(self, doc_paths_with_doc_json):
        """Successfully load existing doc.json."""
        doc_paths, expected = doc_paths_with_doc_json

        doc_type, language, confidence = load_existing_classification(doc_paths)

        assert doc_type == "fnol_form"
        assert language == "en"
        assert confidence == 0.95

    def test_load_missing_doc_json(self, doc_paths_without_doc_json):
        """Raise FileNotFoundError when doc.json missing."""
        with pytest.raises(FileNotFoundError) as excinfo:
            load_existing_classification(doc_paths_without_doc_json)
        assert "doc.json not found" in str(excinfo.value)

    def test_default_values_for_missing_fields(self, tmp_path):
        """Use defaults when fields missing from doc.json."""
        doc_paths = MagicMock()
        doc_json = tmp_path / "doc.json"

        # Minimal doc.json
        doc_json.write_text(json.dumps({"doc_id": "test"}), encoding="utf-8")
        doc_paths.doc_json = doc_json

        doc_type, language, confidence = load_existing_classification(doc_paths)

        assert doc_type == "unknown"
        assert language == "es"
        assert confidence == 0.8


class TestDocResultReuseFlags:
    """Tests for DocResult reuse tracking fields."""

    def test_default_reuse_flags(self):
        """DocResult should default to no reuse."""
        result = DocResult(
            doc_id="test",
            original_filename="test.pdf",
            status="success",
        )
        assert result.ingestion_reused is False
        assert result.classification_reused is False

    def test_explicit_reuse_flags(self):
        """DocResult should accept explicit reuse flags."""
        result = DocResult(
            doc_id="test",
            original_filename="test.pdf",
            status="success",
            ingestion_reused=True,
            classification_reused=True,
        )
        assert result.ingestion_reused is True
        assert result.classification_reused is True


class TestStageConfigIntegration:
    """Integration tests for StageConfig with parse_stages."""

    def test_full_pipeline_workflow(self):
        """Verify full pipeline stages parse correctly."""
        stages = parse_stages("ingest,classify,extract")
        config = StageConfig(stages=stages)

        assert config.run_kind == "full"
        assert config.run_ingest
        assert config.run_classify
        assert config.run_extract

    def test_rerun_extraction_workflow(self):
        """Verify extraction-only workflow for re-running."""
        stages = parse_stages("extract")
        config = StageConfig(stages=stages)

        assert config.run_kind == "extract_only"
        assert not config.run_ingest
        assert not config.run_classify
        assert config.run_extract

    def test_skip_ingestion_workflow(self):
        """Verify classify+extract workflow for skipping ingestion."""
        stages = parse_stages("classify,extract")
        config = StageConfig(stages=stages)

        assert config.run_kind == "classify_extract"
        assert not config.run_ingest
        assert config.run_classify
        assert config.run_extract
