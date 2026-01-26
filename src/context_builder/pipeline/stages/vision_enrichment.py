"""Vision enrichment stage: optional semantic understanding for images.

This stage runs OpenAI Vision on image documents to provide semantic
understanding that goes beyond OCR. It's triggered after classification
for doc types that are configured to require vision analysis.

Use cases:
- Dashboard images (odometer readings, instrument clusters)
- Damage photos (visual damage assessment)
- Handwritten notes (better interpretation than OCR alone)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from context_builder.pipeline.stages.context import DocumentContext
from context_builder.pipeline.writer import ResultWriter

logger = logging.getLogger(__name__)

# Default doc types that benefit from Vision enrichment
DEFAULT_VISION_DOC_TYPES: Set[str] = {
    "dashboard_image",
    "odometer_photo",
    "damage_photo",
    "handwritten_note",
}


@dataclass
class VisionEnrichmentStage:
    """Optional Vision enrichment stage for semantic image understanding.

    Runs OpenAI Vision on image documents after classification to provide
    semantic context that complements Azure DI's OCR output.

    Configuration:
    - vision_doc_types: Set of doc types that trigger Vision enrichment
    - Can be configured via workspace config or passed directly

    Output:
    - Saves vision.json alongside azure_di.json in text/raw/
    - Does NOT replace Azure DI text - Vision data is supplemental
    """

    writer: ResultWriter
    name: str = "vision_enrichment"
    vision_doc_types: Set[str] = field(default_factory=lambda: DEFAULT_VISION_DOC_TYPES.copy())
    ingestion_factory: Optional[Any] = None

    def should_run(self, context: DocumentContext) -> bool:
        """Determine if Vision enrichment should run for this document.

        Conditions:
        1. Vision data not already present (from ingestion dual-provider)
        2. Document is an image (not PDF or text)
        3. Classification has run and doc_type is known
        4. doc_type is in the vision_doc_types set
        """
        # Skip if Vision already ran during ingestion (Option C dual-provider)
        if context.vision_data is not None:
            logger.debug(f"Skipping Vision - already enriched during ingestion")
            return False

        # Only run for images
        if context.doc.source_type != "image":
            return False

        # Need doc_type from classification
        if not context.doc_type:
            return False

        # Check if this doc type requires vision
        return context.doc_type in self.vision_doc_types

    def run(self, context: DocumentContext) -> DocumentContext:
        """Run Vision enrichment if applicable.

        This stage is designed to be non-blocking - if Vision fails,
        we log a warning but don't fail the pipeline. Azure DI output
        is sufficient for extraction.
        """
        context.current_phase = self.name
        start = time.time()

        if not self.should_run(context):
            logger.debug(f"Skipping Vision enrichment for {context.doc.original_filename}")
            return context

        logger.info(
            f"Running Vision enrichment for {context.doc_type}: {context.doc.original_filename}"
        )

        try:
            vision_result = self._run_vision(context)

            if vision_result:
                # Save vision.json
                vision_path = context.doc_paths.text_raw_dir / "vision.json"
                self.writer.write_json(vision_path, vision_result)

                # Store in context for potential use by extractors
                context.vision_data = vision_result

                logger.info(
                    f"Vision enrichment complete for {context.doc.original_filename}"
                )
        except Exception as e:
            # Non-blocking - log warning but continue
            logger.warning(
                f"Vision enrichment failed for {context.doc.original_filename}: {e}"
            )

        context.timings.vision_enrichment_ms = int((time.time() - start) * 1000)
        return context

    def _run_vision(self, context: DocumentContext) -> Optional[Dict[str, Any]]:
        """Execute OpenAI Vision on the document.

        Returns:
            Vision result dict or None if failed
        """
        # Get ingestion factory
        factory = self.ingestion_factory or context.ingestion_factory
        if factory is None:
            from context_builder.ingestion import IngestionFactory
            factory = IngestionFactory

        # Create OpenAI Vision ingestion
        try:
            ingestion = factory.create("openai")
        except Exception as e:
            logger.warning(f"Could not create OpenAI Vision provider: {e}")
            return None

        # Process the image
        result = ingestion.process(context.doc.source_path, envelope=True)
        data = result.get("data", {})

        if not data:
            logger.warning("OpenAI Vision returned no data")
            return None

        return data


def get_vision_doc_types_from_config(workspace_config_dir: Optional[Path] = None) -> Set[str]:
    """Load vision doc types from workspace config if available.

    Looks for vision_config.yaml or similar in workspace config.
    Falls back to DEFAULT_VISION_DOC_TYPES if not configured.

    Args:
        workspace_config_dir: Path to workspace config directory

    Returns:
        Set of doc types that should trigger Vision enrichment
    """
    if not workspace_config_dir:
        return DEFAULT_VISION_DOC_TYPES.copy()

    # Check for vision config
    vision_config_path = workspace_config_dir / "vision_config.yaml"
    if not vision_config_path.exists():
        # Also check pipeline_config.yaml
        pipeline_config_path = workspace_config_dir / "pipeline_config.yaml"
        if pipeline_config_path.exists():
            try:
                import yaml
                with open(pipeline_config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                vision_types = config.get("vision_enrichment", {}).get("doc_types", [])
                if vision_types:
                    return set(vision_types)
            except Exception as e:
                logger.debug(f"Could not load pipeline config: {e}")

        return DEFAULT_VISION_DOC_TYPES.copy()

    try:
        import yaml
        with open(vision_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        doc_types = config.get("doc_types", [])
        return set(doc_types) if doc_types else DEFAULT_VISION_DOC_TYPES.copy()
    except Exception as e:
        logger.warning(f"Could not load vision config: {e}")
        return DEFAULT_VISION_DOC_TYPES.copy()
