"""Extraction stage: run extractor and write extraction output."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from context_builder.pipeline.paths import RunPaths
from context_builder.pipeline.stages.context import DocumentContext
from context_builder.pipeline.text import pages_json_to_page_content
from context_builder.pipeline.writer import ResultWriter
from context_builder.schemas.extraction_result import (
    DocumentMetadata,
    ExtractionRunMetadata,
)

logger = logging.getLogger(__name__)

# Placeholder for tests that patch this symbol without importing extraction at module load.
ExtractorFactory = None


def run_extraction(
    doc_id: str,
    file_md5: str,
    content_md5: str,
    claim_id: str,
    pages_data: Dict[str, Any],
    doc_type: str,
    doc_type_confidence: float,
    language: str,
    run_paths: RunPaths,
    run_id: str,
    writer: ResultWriter,
    extractor_factory: Any,
    version_bundle_id: Optional[str] = None,
    audit_storage_dir: Optional[Path] = None,
    pii_vault: Optional[Any] = None,
    source_file_path: Optional[str] = None,
) -> Tuple[Path, Optional[str]]:
    """Run field extraction for supported doc types.

    Args:
        doc_id: Document identifier.
        file_md5: MD5 hash of input file.
        content_md5: MD5 hash of content.
        claim_id: Parent claim identifier.
        pages_data: Page content data.
        doc_type: Document type.
        doc_type_confidence: Classification confidence.
        language: Document language.
        run_paths: Output paths for this run.
        run_id: Extraction run identifier.
        writer: Result writer instance.
        extractor_factory: Factory for creating extractors.
        version_bundle_id: Optional version bundle ID.
        audit_storage_dir: Optional directory for audit logs.
        pii_vault: Optional PII vault for tokenizing PII in extraction results.
        source_file_path: Optional path to original source file (PDF/image) for vision-based extraction.

    Returns:
        Tuple of (extraction_path, quality_gate_status)
    """
    # Import extractors to ensure they're registered
    import context_builder.extraction.extractors  # noqa: F401
    extractor = extractor_factory.create(doc_type, audit_storage_dir=audit_storage_dir)

    # Convert pages to PageContent objects
    pages = pages_json_to_page_content(pages_data)

    # Build metadata
    doc_meta = DocumentMetadata(
        doc_id=doc_id,
        claim_id=claim_id,
        doc_type=doc_type,
        doc_type_confidence=doc_type_confidence,
        language=language,
        page_count=len(pages),
        source_file_path=source_file_path,
    )

    run_meta = ExtractionRunMetadata(
        run_id=run_id,
        extractor_version="v1.0.0",
        model=extractor.model,
        prompt_version="generic_extraction_v1",
        input_hashes={"file_md5": file_md5, "content_md5": content_md5},
        version_bundle_id=version_bundle_id,  # Link to version snapshot
    )

    # Run extraction
    result = extractor.extract(pages, doc_meta, run_meta)

    # PII Tokenization: Replace PII with vault tokens before persisting
    result_data = result.model_dump()
    if pii_vault is not None:
        from context_builder.services.compliance.pii import PIITokenizer

        tokenizer = PIITokenizer(claim_id=claim_id, vault_id=pii_vault.vault_id)
        tokenization = tokenizer.tokenize(result, run_id)

        if tokenization.vault_entries:
            pii_vault.store_batch(tokenization.vault_entries)
            logger.info(
                f"Tokenized {len(tokenization.vault_entries)} PII values for doc {doc_id}"
            )

        result_data = tokenization.redacted_result  # Use redacted for persistence

    # Write extraction result (with tokens if PII vault enabled)
    output_path = run_paths.extraction_dir / f"{doc_id}.json"
    writer.write_json(output_path, result_data)

    # Get quality gate status
    quality_gate_status = result.quality_gate.status if result.quality_gate else None

    return output_path, quality_gate_status


@dataclass
class ExtractionStage:
    """Extraction stage: run extractor and write extraction output."""

    writer: ResultWriter
    name: str = "extraction"

    def run(self, context: DocumentContext) -> DocumentContext:
        context.current_phase = self.name
        start = time.time()

        doc_type = context.doc_type or "unknown"
        extractor_factory = context.extractor_factory or ExtractorFactory
        if context.stage_config.run_extract and extractor_factory is None:
            from context_builder.extraction.base import ExtractorFactory as DefaultExtractorFactory
            extractor_factory = DefaultExtractorFactory

        # Check if extraction should run for this doc type
        should_extract = (
            context.stage_config.run_extract
            and extractor_factory.is_supported(doc_type)
            and context.stage_config.should_extract_doc_type(doc_type)
        )

        if should_extract:
            if context.pages_data is None:
                raise ValueError("Missing pages data for extraction")

            # Compute source file path for vision-based extractors
            source_file_path = None
            if context.doc.source_type in ("pdf", "image") and context.doc_paths:
                # Find the original file in source_dir (copied during ingestion)
                for ext in [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".gif", ".bmp", ".webp"]:
                    candidate = context.doc_paths.source_dir / f"original{ext}"
                    if candidate.exists():
                        source_file_path = str(candidate)
                        break

            context.extraction_path, context.quality_gate_status = run_extraction(
                doc_id=context.doc.doc_id,
                file_md5=context.doc.file_md5,
                content_md5=context.content_md5 or "",
                claim_id=context.claim_id,
                pages_data=context.pages_data,
                doc_type=doc_type,
                doc_type_confidence=context.confidence or 0.0,
                language=context.language or "es",
                run_paths=context.run_paths,
                run_id=context.run_id,
                writer=self.writer,
                extractor_factory=extractor_factory,
                version_bundle_id=context.version_bundle_id,
                audit_storage_dir=context.audit_storage_dir,
                pii_vault=context.pii_vault,
                source_file_path=source_file_path,
            )
            logger.info(f"Extracted {doc_type}: {context.doc.original_filename}")
        elif not context.stage_config.run_extract:
            logger.debug(f"Extraction skipped by --stages: {context.doc.original_filename}")
        elif not context.stage_config.should_extract_doc_type(doc_type):
            logger.debug(f"Extraction skipped by --doc-types filter: {doc_type} ({context.doc.original_filename})")
        else:
            logger.debug(f"No extractor for {doc_type}: {context.doc.original_filename}")

        context.timings.extraction_ms = int((time.time() - start) * 1000)
        return context
