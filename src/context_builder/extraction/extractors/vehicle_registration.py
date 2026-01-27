"""
Vehicle Registration vision-based extractor for Swiss FZA documents.

Uses OpenAI Vision API to extract fields from vehicle registration documents,
which have complex visual layouts that text-based extraction often misses.
"""

import base64
import json
import logging
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.services.openai_client import get_openai_client, get_default_model

from context_builder.extraction.base import FieldExtractor, ExtractorFactory
from context_builder.extraction.spec_loader import DocTypeSpec, get_spec
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets
from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    QualityGate,
    ExtractionRunMetadata,
    DocumentMetadata,
    PageContent,
)
from context_builder.services.llm_audit import AuditedOpenAIClient, get_llm_audit_service
from context_builder.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class VehicleRegistrationExtractor(FieldExtractor):
    """
    Vision-based extractor for Swiss vehicle registration (FZA) documents.

    Swiss Fahrzeugausweis documents have a specific layout with owner information
    on the left side and vehicle details on the right. Text extraction often fails
    to correctly identify the owner_name field due to the complex layout.

    This extractor uses OpenAI Vision API to directly extract from the image/PDF,
    which provides much better results for these structured documents.
    """

    EXTRACTOR_VERSION = "v1.0.0"
    PROMPT_NAME = "vehicle_registration_extraction"

    def __init__(
        self,
        spec: DocTypeSpec,
        model: Optional[str] = None,
        audit_storage_dir: Optional[Path] = None,
    ):
        """Initialize the vehicle registration extractor.

        Args:
            spec: Document type specification
            model: Optional model override (defaults to gpt-4o)
            audit_storage_dir: Optional directory for audit logs
        """
        # Load prompt config for model defaults
        try:
            prompt_data = load_prompt(self.PROMPT_NAME)
            prompt_config = prompt_data["config"]
            resolved_model = model or prompt_config.get("model", get_default_model())
            self.temperature = prompt_config.get("temperature", 0.1)
            self.max_tokens = prompt_config.get("max_tokens", 1024)
        except Exception:
            # Fallback if prompt not found
            resolved_model = model or get_default_model()
            self.temperature = 0.1
            self.max_tokens = 1024

        super().__init__(spec, resolved_model)

        # Initialize OpenAI client with audit wrapper (uses Azure OpenAI if configured)
        raw_client = get_openai_client()
        audit_service = get_llm_audit_service(audit_storage_dir)
        self.audited_client = AuditedOpenAIClient(raw_client, audit_service)

        # Rendering settings for PDFs
        self.render_scale = 2.0  # Higher quality for OCR

    def extract(
        self,
        pages: List[PageContent],
        doc_meta: DocumentMetadata,
        run_metadata: ExtractionRunMetadata,
    ) -> ExtractionResult:
        """
        Extract fields from vehicle registration document.

        Prefers vision-based extraction when source file is available,
        falls back to text-based extraction otherwise.
        """
        # Set audit context
        self.audited_client.set_context(
            claim_id=doc_meta.claim_id,
            doc_id=doc_meta.doc_id,
            run_id=run_metadata.run_id,
            call_purpose="vision_extraction",
        )

        # Try vision-based extraction if source file available
        if doc_meta.source_file_path and Path(doc_meta.source_file_path).exists():
            logger.info(f"Using vision extraction for {doc_meta.doc_id}")
            fields = self._vision_extract(doc_meta.source_file_path, pages)
        else:
            logger.info(f"No source file, using text fallback for {doc_meta.doc_id}")
            fields = self._text_extract(pages)

        # Build quality gate
        quality_gate = self._build_quality_gate(fields)

        # Build result
        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=run_metadata,
            doc=doc_meta,
            pages=pages,
            fields=fields,
            quality_gate=quality_gate,
        )

        # Resolve evidence offsets
        result = resolve_evidence_offsets(result)

        return result

    def _vision_extract(
        self, source_file_path: str, pages: List[PageContent]
    ) -> List[ExtractedField]:
        """Extract fields using OpenAI Vision API."""
        source_path = Path(source_file_path)
        extension = source_path.suffix.lower()

        # Encode image
        if extension == ".pdf":
            base64_image, mime_type = self._encode_pdf_page(source_path)
        else:
            base64_image, mime_type = self._encode_image(source_path)

        if not base64_image:
            logger.warning("Failed to encode source file, falling back to text")
            return self._text_extract(pages)

        # Build vision messages
        messages = self._build_vision_messages(base64_image, mime_type)

        # Call OpenAI Vision API
        try:
            response = self.audited_client.chat_completions_create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content if response.choices else None
            if not content:
                logger.warning("Empty response from vision API")
                return self._text_extract(pages)

            # Parse response
            return self._parse_vision_response(content, pages)

        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            return self._text_extract(pages)

    def _encode_image(self, image_path: Path) -> tuple[Optional[str], str]:
        """Encode image file to base64."""
        try:
            with open(image_path, "rb") as f:
                base64_data = base64.b64encode(f.read()).decode("utf-8")

            # Determine MIME type
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
                ".tiff": "image/tiff",
                ".tif": "image/tiff",
                ".webp": "image/webp",
            }
            mime_type = mime_types.get(image_path.suffix.lower(), "image/jpeg")

            return base64_data, mime_type
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None, "image/jpeg"

    def _encode_pdf_page(self, pdf_path: Path, page_index: int = 0) -> tuple[Optional[str], str]:
        """Render PDF page to image and encode to base64."""
        try:
            import pypdfium2 as pdfium

            pdf_doc = pdfium.PdfDocument(pdf_path)
            try:
                if page_index >= len(pdf_doc):
                    page_index = 0

                page = pdf_doc[page_index]
                mat = page.render(scale=self.render_scale)
                img = mat.to_pil()

                # Encode to PNG
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                base64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

                return base64_data, "image/png"
            finally:
                pdf_doc.close()

        except ImportError:
            logger.warning("pypdfium2 not installed, cannot process PDF")
            return None, "image/png"
        except Exception as e:
            logger.error(f"Failed to render PDF page: {e}")
            return None, "image/png"

    def _build_vision_messages(self, base64_image: str, mime_type: str) -> List[Dict[str, Any]]:
        """Build OpenAI API messages with image and extraction prompt."""
        # Try to load prompt from file
        try:
            prompt_data = load_prompt(self.PROMPT_NAME)
            system_prompt = prompt_data["messages"][0]["content"]
            user_prompt = prompt_data["messages"][1]["content"] if len(prompt_data["messages"]) > 1 else "Extract all fields from this document."
        except Exception:
            # Fallback to hardcoded prompt
            system_prompt = self._get_system_prompt()
            user_prompt = "Extract all fields from this Swiss vehicle registration document (Fahrzeugausweis)."

        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        },
                    },
                ],
            },
        ]

    def _get_system_prompt(self) -> str:
        """Get the system prompt for Swiss FZA extraction."""
        return """You are an expert at extracting information from Swiss vehicle registration documents (Fahrzeugausweis/FZA).

The document has a specific layout:
- Left side: Owner information (Name, Address)
- Right side: Vehicle details
- Field A: License plate number (Kontrollschild/Plaque)
- Field B: Registration dates
- Field C: Owner name (Name, Vornamen / Nom, prénom)
- Field D: Vehicle make/type (Marke, Typ / Marque, type)
- Field E: VIN, color (Fahrgestell-Nr., Farbe / No de châssis, couleur)

Extract the following fields:
- owner_name: Full name from field C (left side)
- plate_number: License plate from field A
- vin: Vehicle identification number from field E
- make: Vehicle manufacturer from field D
- model: Vehicle model from field D
- color: Vehicle color from field E
- registration_date: First registration date from field B
- expiry_date: Document expiry date

Return JSON with this structure:
{
  "fields": [
    {
      "name": "owner_name",
      "value": "extracted value or null",
      "text_quote": "exact text from the document",
      "confidence": 0.9
    }
  ]
}

Be precise and extract the actual values visible in the document."""

    def _parse_vision_response(
        self, content: str, pages: List[PageContent]
    ) -> List[ExtractedField]:
        """Parse the vision API response into ExtractedField objects."""
        try:
            # Handle markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                if end > start:
                    content = content[start:end].strip()

            data = json.loads(content)
            raw_fields = data.get("fields", [])

            fields = []
            all_field_names = self.spec.all_fields

            for raw_field in raw_fields:
                name = raw_field.get("name", "")
                value = raw_field.get("value")
                text_quote = raw_field.get("text_quote", "")
                confidence = raw_field.get("confidence", 0.8)

                # Build provenance if we have a text quote
                provenance = []
                if text_quote and pages:
                    provenance.append(
                        FieldProvenance(
                            page=1,
                            method="vision_ocr",
                            text_quote=text_quote,
                            char_start=0,
                            char_end=len(text_quote),
                            match_quality="placeholder",  # Will be resolved later
                        )
                    )

                status = "present" if value else "missing"
                fields.append(
                    ExtractedField(
                        name=name,
                        value=value,
                        normalized_value=None,
                        confidence=confidence,
                        status=status,
                        provenance=provenance,
                        value_is_placeholder=False,
                        has_verified_evidence=bool(provenance),
                    )
                )

            # Add missing fields
            extracted_names = {f.name for f in fields}
            for field_name in all_field_names:
                if field_name not in extracted_names:
                    fields.append(self._create_missing_field(field_name))

            return fields

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vision response: {e}")
            return [self._create_missing_field(f) for f in self.spec.all_fields]

    def _text_extract(self, pages: List[PageContent]) -> List[ExtractedField]:
        """Fallback text-based extraction when vision is not available."""
        # Simple keyword-based extraction as fallback
        full_text = "\n".join(p.text for p in pages)

        fields = []
        for field_name in self.spec.all_fields:
            hints = self.spec.get_field_hints(field_name)
            value = None
            text_quote = ""

            # Simple hint-based search
            for hint in hints:
                hint_lower = hint.lower()
                pos = full_text.lower().find(hint_lower)
                if pos >= 0:
                    # Extract value after hint (simple heuristic)
                    start = pos + len(hint)
                    # Find next line or colon
                    end = min(
                        full_text.find("\n", start) if full_text.find("\n", start) > 0 else len(full_text),
                        start + 100
                    )
                    text_quote = full_text[pos:end].strip()
                    # Try to extract value after colon or similar
                    if ":" in text_quote:
                        value = text_quote.split(":", 1)[1].strip()
                    elif "\t" in text_quote:
                        value = text_quote.split("\t", 1)[1].strip()
                    break

            if value:
                provenance = [
                    FieldProvenance(
                        page=1,
                        method="di_text",
                        text_quote=text_quote,
                        char_start=0,
                        char_end=len(text_quote),
                        match_quality="placeholder",
                    )
                ]
                fields.append(
                    ExtractedField(
                        name=field_name,
                        value=value,
                        normalized_value=None,
                        confidence=0.5,  # Lower confidence for text fallback
                        status="present",
                        provenance=provenance,
                        value_is_placeholder=False,
                        has_verified_evidence=False,
                    )
                )
            else:
                fields.append(self._create_missing_field(field_name))

        return fields


# Auto-register with factory
ExtractorFactory.register("vehicle_registration", VehicleRegistrationExtractor)
