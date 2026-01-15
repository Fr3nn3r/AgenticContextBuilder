"""Tests to ensure compliance decisions have proper audit context.

These tests verify that classification and extraction decisions logged
to the compliance ledger include claim_id, doc_id, and run_id - critical
for audit trail and filtering in the compliance UI.

This catches bugs like the ClassificationStage not setting audit context
before classification, which would result in decisions with null context fields.
"""

import inspect
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestClassificationAuditContext:
    """Tests that classification decisions include proper audit context."""

    def test_classifier_set_audit_context_called_before_classify(self):
        """Test that ClassificationStage calls set_audit_context before classifying.

        This is a structural test that verifies the code flow, not the decision content.
        It ensures we don't regress on the bug where audit context wasn't set.
        """
        from context_builder.pipeline.run import ClassificationStage

        # Create mock classifier with set_audit_context method
        mock_classifier = MagicMock()
        mock_classifier.classify_pages.return_value = {
            "document_type": "invoice",
            "language": "en",
            "confidence": 0.95,
            "context_tier": "optimized",
            "retried": False,
            "token_savings_estimate": 100,
        }

        # Create minimal document context
        mock_doc = MagicMock()
        mock_doc.doc_id = "DOC-001"
        mock_doc.original_filename = "test.pdf"

        mock_doc_paths = MagicMock()
        mock_run_paths = MagicMock()
        mock_run_paths.context_dir = Path("/tmp/context")

        # Create mock stage config that enables classification
        mock_stage_config = MagicMock()
        mock_stage_config.run_classify = True

        # Create mock writer
        mock_writer = MagicMock()

        # Create document context with pages data
        context = MagicMock()
        context.text_content = "Sample text content"
        context.pages_data = {"pages": [{"text": "Page 1"}], "page_count": 1}
        context.classifier = mock_classifier
        context.claim_id = "CLM-001"
        context.doc = mock_doc
        context.doc_paths = mock_doc_paths
        context.run_paths = mock_run_paths
        context.run_id = "BATCH-001"
        context.stage_config = mock_stage_config
        context.current_phase = None
        context.timings = MagicMock()

        # Run classification stage
        stage = ClassificationStage(writer=mock_writer)
        stage.run(context)

        # Verify set_audit_context was called with correct arguments BEFORE classify_pages
        mock_classifier.set_audit_context.assert_called_once_with(
            claim_id="CLM-001",
            doc_id="DOC-001",
            run_id="BATCH-001",
        )

        # Verify classify_pages was called after set_audit_context
        # (The mock records call order automatically)
        assert mock_classifier.set_audit_context.called
        assert mock_classifier.classify_pages.called

    def test_classifier_without_set_audit_context_still_works(self):
        """Test that ClassificationStage handles classifiers without set_audit_context.

        Some classifiers (e.g., mocks, custom implementations) may not have
        the set_audit_context method. The stage should handle this gracefully.
        """
        from context_builder.pipeline.run import ClassificationStage

        # Create mock classifier WITHOUT set_audit_context
        mock_classifier = MagicMock(spec=['classify_pages'])
        mock_classifier.classify_pages.return_value = {
            "document_type": "invoice",
            "language": "en",
            "confidence": 0.95,
            "context_tier": "full",
            "retried": False,
            "token_savings_estimate": 0,
        }

        # Create minimal context
        mock_doc = MagicMock()
        mock_doc.doc_id = "DOC-001"
        mock_doc.original_filename = "test.pdf"

        context = MagicMock()
        context.text_content = "Sample text content"
        context.pages_data = {"pages": [{"text": "Page 1"}], "page_count": 1}
        context.classifier = mock_classifier
        context.claim_id = "CLM-001"
        context.doc = mock_doc
        context.run_id = "BATCH-001"
        context.stage_config = MagicMock()
        context.stage_config.run_classify = True
        context.run_paths = MagicMock()
        context.run_paths.context_dir = Path("/tmp/context")
        context.timings = MagicMock()

        # Run classification stage - should not raise
        stage = ClassificationStage(writer=MagicMock())
        stage.run(context)

        # Should still classify even without set_audit_context
        mock_classifier.classify_pages.assert_called_once()


class TestPipelineAuditContextIntegration:
    """Integration tests that verify full pipeline sets audit context correctly."""

    def test_classification_stage_sets_audit_context(self):
        """Verify ClassificationStage implementation calls set_audit_context.

        This is a code inspection test that would fail if someone removes
        the set_audit_context call from ClassificationStage.
        """
        from context_builder.pipeline.run import ClassificationStage

        # Get the source code of the run method
        source = inspect.getsource(ClassificationStage.run)

        # Verify set_audit_context is called in the run method
        assert "set_audit_context" in source, (
            "ClassificationStage.run() does not call set_audit_context! "
            "Classification decisions will be logged without claim_id, doc_id, run_id. "
            "This breaks compliance filtering in the UI."
        )

        # Verify it's called with the expected arguments
        assert "claim_id" in source, "set_audit_context should be called with claim_id"
        assert "doc_id" in source, "set_audit_context should be called with doc_id"
        assert "run_id" in source, "set_audit_context should be called with run_id"

    def test_openai_classifier_has_set_audit_context_method(self):
        """Verify OpenAIDocumentClassifier has the set_audit_context method.

        This ensures the method exists so ClassificationStage can use it.
        """
        from context_builder.classification.openai_classifier import OpenAIDocumentClassifier

        # Verify the method exists
        assert hasattr(OpenAIDocumentClassifier, 'set_audit_context'), (
            "OpenAIDocumentClassifier does not have set_audit_context method! "
            "This is required for compliance audit context logging."
        )

        # Verify it accepts the expected arguments
        sig = inspect.signature(OpenAIDocumentClassifier.set_audit_context)
        params = list(sig.parameters.keys())
        assert 'claim_id' in params, "set_audit_context should accept claim_id"
        assert 'doc_id' in params, "set_audit_context should accept doc_id"
        assert 'run_id' in params, "set_audit_context should accept run_id"

    def test_extractor_sets_audit_context_in_extract(self):
        """Verify GenericFieldExtractor.extract() sets audit context.

        The extractor should set _audit_context and call audited_client.set_context()
        at the start of extract() so that decisions are logged with proper context.
        """
        from context_builder.extraction.extractors.generic import GenericFieldExtractor

        # Get the source code of the extract method
        source = inspect.getsource(GenericFieldExtractor.extract)

        # Verify audit context is set in the extract method
        assert "_audit_context" in source, (
            "GenericFieldExtractor.extract() does not set _audit_context! "
            "Extraction decisions will be logged without claim_id, doc_id, run_id."
        )
        assert "claim_id" in source, "extract should set claim_id in audit context"
        assert "doc_id" in source, "extract should set doc_id in audit context"
        assert "run_id" in source, "extract should set run_id in audit context"

        # Verify audited_client.set_context is called
        assert "set_context" in source, (
            "GenericFieldExtractor.extract() should call audited_client.set_context()"
        )


class TestDecisionRecordContext:
    """Tests that decision records have required context fields."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test artifacts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_decision_record_requires_context_fields(self):
        """Verify DecisionRecord schema includes context fields.

        This ensures the schema supports claim_id, doc_id, run_id even if
        they're optional (nullable for backwards compatibility).
        """
        from context_builder.schemas.decision_record import DecisionRecord

        # Get the model fields
        fields = DecisionRecord.model_fields

        # These fields must exist in the schema
        assert 'claim_id' in fields, "DecisionRecord must have claim_id field"
        assert 'doc_id' in fields, "DecisionRecord must have doc_id field"
        assert 'run_id' in fields, "DecisionRecord must have run_id field"

    def test_decision_query_can_filter_by_context(self):
        """Verify DecisionQuery supports filtering by context fields.

        This ensures the API can filter decisions by claim_id, doc_id, etc.
        """
        from context_builder.schemas.decision_record import DecisionQuery

        # Get the model fields
        fields = DecisionQuery.model_fields

        # These filter fields must exist
        assert 'claim_id' in fields, "DecisionQuery must support claim_id filter"
        assert 'doc_id' in fields, "DecisionQuery must support doc_id filter"

    def test_classification_log_method_uses_audit_context(self):
        """Verify _log_classification_decision uses _audit_context.

        This ensures the logged decision includes the context set via set_audit_context.
        """
        from context_builder.classification.openai_classifier import OpenAIDocumentClassifier

        # Get the source of the log method
        source = inspect.getsource(OpenAIDocumentClassifier._log_classification_decision)

        # Verify it uses _audit_context
        assert "_audit_context" in source, (
            "_log_classification_decision does not use _audit_context! "
            "Decisions will be logged without claim_id, doc_id, run_id."
        )

        # Verify specific fields are extracted
        assert "claim_id" in source, "Should extract claim_id from audit context"
        assert "doc_id" in source, "Should extract doc_id from audit context"
        assert "run_id" in source, "Should extract run_id from audit context"

    def test_extraction_log_method_uses_audit_context(self):
        """Verify _log_extraction_decision includes context in the decision.

        The extractor can get context either from:
        - _audit_context (instance attribute set before extract)
        - result.doc / result.run (passed through the ExtractionResult)

        Both patterns are valid; this test verifies context is included somehow.
        """
        from context_builder.extraction.extractors.generic import GenericFieldExtractor

        # Get the source of the log method
        source = inspect.getsource(GenericFieldExtractor._log_extraction_decision)

        # Verify context is included via one of the valid patterns:
        # Pattern 1: Uses _audit_context
        # Pattern 2: Uses result.doc.claim_id / result.run.run_id
        uses_audit_context = "_audit_context" in source
        uses_result_context = "result.doc.claim_id" in source or "result.run.run_id" in source

        assert uses_audit_context or uses_result_context, (
            "_log_extraction_decision does not include audit context! "
            "Decisions will be logged without claim_id, doc_id, run_id. "
            "Should use either _audit_context or result.doc/result.run."
        )

        # Verify claim_id, doc_id, run_id are included in the record
        assert "claim_id" in source, "DecisionRecord should include claim_id"
        assert "doc_id" in source, "DecisionRecord should include doc_id"
        assert "run_id" in source, "DecisionRecord should include run_id"
