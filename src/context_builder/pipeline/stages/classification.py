"""Classification stage: classify document and write context/doc.json."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple

from context_builder.pipeline.paths import DocPaths
from context_builder.pipeline.stages.context import DocumentContext
from context_builder.pipeline.writer import ResultWriter

logger = logging.getLogger(__name__)


def load_existing_classification(
    doc_paths: DocPaths,
) -> Tuple[str, str, float]:
    """
    Load existing classification from doc.json.

    Args:
        doc_paths: Document paths

    Returns:
        Tuple of (doc_type, language, confidence)

    Raises:
        FileNotFoundError: If doc.json doesn't exist
    """
    if not doc_paths.doc_json.exists():
        raise FileNotFoundError(f"doc.json not found: {doc_paths.doc_json}")

    with open(doc_paths.doc_json, "r", encoding="utf-8") as f:
        doc_meta = json.load(f)

    return (
        doc_meta.get("doc_type", "unknown"),
        doc_meta.get("language", "es"),
        doc_meta.get("doc_type_confidence", 0.8),
    )


@dataclass
class ClassificationStage:
    """Classification stage: classify and write context/doc.json."""

    writer: ResultWriter
    name: str = "classification"

    def run(self, context: DocumentContext) -> DocumentContext:
        context.current_phase = self.name
        start = time.time()

        if context.text_content is None:
            raise ValueError("Missing text content for classification")

        if context.stage_config.run_classify:
            # Set audit context for compliance logging (links decision to claim/doc/run)
            if hasattr(context.classifier, 'set_audit_context'):
                context.classifier.set_audit_context(
                    claim_id=context.claim_id,
                    doc_id=context.doc.doc_id,
                    run_id=context.run_id,
                )

            # Use page-based classification if pages data is available
            if context.pages_data and "pages" in context.pages_data:
                pages = [p.get("text", "") for p in context.pages_data["pages"]]
                classification = context.classifier.classify_pages(
                    pages,
                    context.doc.original_filename,
                )
                logger.info(
                    f"Classification used {classification.get('context_tier', 'unknown')} context, "
                    f"retried={classification.get('retried', False)}, "
                    f"token_savings={classification.get('token_savings_estimate', 0)}"
                )
            else:
                # Fallback to text-based classification
                classification = context.classifier.classify(
                    context.text_content,
                    context.doc.original_filename,
                )

            context.doc_type = classification.get("document_type", "unknown")
            context.language = classification.get("language", "es")
            confidence = classification.get("confidence")
            context.confidence = confidence if confidence is not None else 0.8

            context_data = {
                "doc_id": context.doc.doc_id,
                "original_filename": context.doc.original_filename,
                "source_type": context.doc.source_type,
                "classification": classification,
                "classified_at": datetime.utcnow().isoformat() + "Z",
            }
            context_path = context.run_paths.context_dir / f"{context.doc.doc_id}.json"
            self.writer.write_json(context_path, context_data)

            context.content_md5 = hashlib.md5(context.text_content.encode("utf-8")).hexdigest()
            doc_meta = {
                "doc_id": context.doc.doc_id,
                "claim_id": context.claim_id,
                "original_filename": context.doc.original_filename,
                "source_type": context.doc.source_type,
                "doc_type": context.doc_type,
                "doc_type_confidence": context.confidence,
                "language": context.language,
                "file_md5": context.doc.file_md5,
                "content_md5": context.content_md5,
                "page_count": context.pages_data["page_count"],
                "created_at": datetime.utcnow().isoformat() + "Z",
            }
            self.writer.write_json(context.doc_paths.doc_json, doc_meta)
        else:
            try:
                context.doc_type, context.language, context.confidence = load_existing_classification(
                    context.doc_paths
                )
                context.classification_reused = True
                logger.info(
                    f"Reusing existing classification for {context.doc.original_filename}: {context.doc_type}"
                )
                with open(context.doc_paths.doc_json, "r", encoding="utf-8") as f:
                    existing_meta = json.load(f)
                context.content_md5 = existing_meta.get("content_md5", "")
            except FileNotFoundError:
                context.status = "skipped"
                context.error = "CLASSIFICATION_MISSING: No doc.json found and --stages excludes classify"
                context.failed_phase = "classification"
                return context

        context.timings.classification_ms = int((time.time() - start) * 1000)
        return context
