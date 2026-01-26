"""Ingestion stage: copy source, extract text, write pages.json."""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from context_builder.pipeline.discovery import DiscoveredDocument
from context_builder.pipeline.paths import DocPaths
from context_builder.pipeline.stages.context import DocumentContext, IngestionResult
from context_builder.pipeline.text import build_pages_json, build_pages_json_from_azure_di
from context_builder.pipeline.writer import ResultWriter

logger = logging.getLogger(__name__)

# Placeholder for tests that patch this symbol without importing at module load.
IngestionFactory = None


def ingest_document(
    doc: DiscoveredDocument,
    doc_paths: DocPaths,
    writer: ResultWriter,
    ingestion_factory: Optional[Any] = None,
) -> IngestionResult:
    """
    Ingest a PDF or image document to extract text.

    Provider selection follows this priority:
    1. Tenant config ingestion_routes: If a regex pattern matches the filename,
       use the specified provider.
    2. Default extension-based routing: PDF -> Azure DI, images -> OpenAI Vision.

    Args:
        doc: Document to ingest
        doc_paths: Paths for output files
        writer: ResultWriter instance
        ingestion_factory: Optional factory for creating ingestion instances

    Returns:
        IngestionResult with text content and provider-specific data

    Raises:
        Exception: If ingestion fails
    """
    from context_builder.config.tenant import get_tenant_config

    # Check tenant config for provider routing
    tenant_config = get_tenant_config()
    provider_name = None
    if tenant_config:
        provider_name = tenant_config.get_provider_for_filename(doc.original_filename)

    # Get the factory
    factory = ingestion_factory or IngestionFactory
    if factory is None:
        from context_builder.ingestion import IngestionFactory as DefaultIngestionFactory
        factory = DefaultIngestionFactory

    # If tenant config specifies a provider, use it regardless of file type
    if provider_name:
        logger.info(
            f"Using tenant-configured provider '{provider_name}' for: {doc.original_filename}"
        )
        return _ingest_with_provider(
            doc, doc_paths, writer, factory, provider_name
        )

    # Fall back to extension-based routing
    # Azure DI is used for PDFs to get word-level coordinates for evidence highlighting.
    if doc.source_type == "pdf":
        logger.info(f"Ingesting PDF with Azure DI: {doc.original_filename}")
        return _ingest_with_provider(doc, doc_paths, writer, factory, "azure-di")

    elif doc.source_type == "image":
        # Run BOTH Azure DI (coordinates) and Vision (semantic) for images
        # Azure DI provides OCR + word-level coordinates for evidence highlighting
        # Vision provides semantic understanding for better classification of sparse-text images
        logger.info(f"Ingesting image with Azure DI + Vision: {doc.original_filename}")

        azure_result = _ingest_with_provider(doc, doc_paths, writer, factory, "azure-di")
        vision_data = _run_vision_for_image(doc, doc_paths, writer, factory)

        return IngestionResult(
            text_content=azure_result.text_content,
            provider_name="azure-di+vision",
            azure_di_data=azure_result.azure_di_data,
            vision_data=vision_data,
        )

    else:
        raise ValueError(f"Unknown source type: {doc.source_type}")


def _ingest_with_provider(
    doc: DiscoveredDocument,
    doc_paths: DocPaths,
    writer: ResultWriter,
    factory: Any,
    provider_name: str,
) -> IngestionResult:
    """
    Ingest a document using a specific provider.

    Args:
        doc: Document to ingest
        doc_paths: Paths for output files
        writer: ResultWriter instance
        factory: IngestionFactory to use
        provider_name: Name of the provider (azure-di, openai, tesseract)

    Returns:
        IngestionResult with text content and provider-specific data

    Raises:
        ValueError: If provider returns no content
    """
    ingestion = factory.create(provider_name)

    if provider_name == "azure-di":
        ingestion.save_markdown = False  # We'll save ourselves
        result = ingestion.process(doc.source_path, envelope=True)
        data = result.get("data", {})

        # Extract markdown content from Azure DI result
        raw_output = data.get("raw_azure_di_output", {})
        text_content = raw_output.get("content", "")

        if not text_content:
            raise ValueError("Azure DI returned no content")

        # Save raw Azure DI output for debugging
        raw_path = doc_paths.text_raw_dir / "azure_di.json"
        writer.write_json(raw_path, data)

        # Return with Azure DI data for proper page splitting
        return IngestionResult(
            text_content=text_content,
            provider_name=provider_name,
            azure_di_data=data,
        )

    elif provider_name == "openai":
        result = ingestion.process(doc.source_path, envelope=True)
        data = result.get("data", {})

        # Extract text from vision pages
        pages = data.get("pages", [])
        if not pages:
            raise ValueError("OpenAI Vision returned no pages")

        # Combine text from all pages
        text_parts = []
        for page in pages:
            text_content = page.get("text_content", "")
            if text_content:
                text_parts.append(text_content)
            # Also include summary if no raw text
            elif page.get("summary"):
                text_parts.append(page.get("summary", ""))

        text_content = "\n\n".join(text_parts)

        if not text_content:
            # Fallback: serialize key information
            key_info = pages[0].get("key_information", {})
            if key_info:
                text_content = json.dumps(key_info, indent=2, ensure_ascii=False)

        # Save raw vision output for debugging
        raw_path = doc_paths.text_raw_dir / "vision.json"
        writer.write_json(raw_path, data)

        return IngestionResult(
            text_content=text_content,
            provider_name=provider_name,
        )

    elif provider_name == "tesseract":
        result = ingestion.process(doc.source_path, envelope=True)
        data = result.get("data", {})

        # Extract text from tesseract result
        pages = data.get("pages", [])
        if not pages:
            raise ValueError("Tesseract returned no pages")

        # Combine text from all pages
        text_parts = []
        for page in pages:
            text_content = page.get("text", "") or page.get("text_content", "")
            if text_content:
                text_parts.append(text_content)

        text_content = "\n\n".join(text_parts)

        if not text_content:
            raise ValueError("Tesseract returned no content")

        # Save raw tesseract output for debugging
        raw_path = doc_paths.text_raw_dir / "tesseract.json"
        writer.write_json(raw_path, data)

        return IngestionResult(
            text_content=text_content,
            provider_name=provider_name,
        )

    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def _run_vision_for_image(
    doc: DiscoveredDocument,
    doc_paths: DocPaths,
    writer: ResultWriter,
    factory: Any,
) -> Optional[Dict[str, Any]]:
    """
    Run OpenAI Vision on an image for semantic understanding.
    Non-blocking - returns None on failure.
    """
    try:
        ingestion = factory.create("openai")
        result = ingestion.process(doc.source_path, envelope=True)
        data = result.get("data", {})

        if not data:
            logger.warning(f"Vision returned no data for {doc.original_filename}")
            return None

        # Save vision.json
        vision_path = doc_paths.text_raw_dir / "vision.json"
        writer.write_json(vision_path, data)

        return data
    except Exception as e:
        logger.warning(f"Vision enrichment failed for {doc.original_filename}: {e}")
        return None


def load_existing_ingestion(
    doc_paths: DocPaths,
) -> tuple[str, Dict[str, Any]]:
    """
    Load existing ingestion output from pages.json.

    Args:
        doc_paths: Document paths

    Returns:
        Tuple of (text_content, pages_data)

    Raises:
        FileNotFoundError: If pages.json doesn't exist
        ValueError: If pages.json is invalid
    """
    if not doc_paths.pages_json.exists():
        raise FileNotFoundError(f"pages.json not found: {doc_paths.pages_json}")

    with open(doc_paths.pages_json, "r", encoding="utf-8") as f:
        pages_data = json.load(f)

    # Reconstruct text content from pages
    pages = pages_data.get("pages", [])
    text_content = "\n\n".join(p.get("text", "") for p in pages)

    return text_content, pages_data


@dataclass
class IngestionStage:
    """Ingestion stage: copy source, extract text, write pages.json."""

    writer: ResultWriter
    name: str = "ingestion"

    def run(self, context: DocumentContext) -> DocumentContext:
        context.current_phase = self.name
        start = time.time()

        if context.stage_config.run_ingest:
            if context.doc.source_type in ("pdf", "image"):
                dest_path = context.doc_paths.source_dir / f"original{context.doc.source_path.suffix}"
                self.writer.copy_file(context.doc.source_path, dest_path)
            else:
                self.writer.write_text(context.doc_paths.original_txt, context.doc.content)

            azure_di_data = None
            if context.doc.needs_ingestion:
                ingestion_result = ingest_document(
                    context.doc,
                    context.doc_paths,
                    self.writer,
                    ingestion_factory=context.ingestion_factory,
                )
                context.text_content = ingestion_result.text_content
                azure_di_data = ingestion_result.azure_di_data
                context.vision_data = ingestion_result.vision_data  # Store Vision data for images
            else:
                context.text_content = context.doc.content

            self.writer.write_text(context.doc_paths.source_txt, context.text_content)

            # Use Azure DI page spans for reliable multi-page splitting
            if azure_di_data is not None:
                context.pages_data = build_pages_json_from_azure_di(
                    azure_di_data,
                    context.doc.doc_id,
                )
            else:
                # Both PDFs and images use Azure DI, so source_type is azure_di
                # Only preextracted text files use a different source_type
                context.pages_data = build_pages_json(
                    context.text_content,
                    context.doc.doc_id,
                    source_type="azure_di" if context.doc.source_type in ("pdf", "image") else "preextracted_txt",
                )
            self.writer.write_json(context.doc_paths.pages_json, context.pages_data)
        else:
            try:
                context.text_content, context.pages_data = load_existing_ingestion(context.doc_paths)
                context.ingestion_reused = True
                logger.info(f"Reusing existing ingestion for {context.doc.original_filename}")
            except FileNotFoundError:
                context.status = "skipped"
                context.error = "TEXT_MISSING: No pages.json found and --stages excludes ingest"
                context.failed_phase = "ingestion"
                return context

        context.timings.ingestion_ms = int((time.time() - start) * 1000)
        return context
