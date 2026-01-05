"""
Generic field extractor using two-pass approach:
1. Candidate span finder (regex/keywords)
2. LLM structured extraction on snippets
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib

from openai import OpenAI

from context_builder.extraction.base import (
    FieldExtractor,
    ExtractorFactory,
    CandidateSpan,
)
from context_builder.extraction.spec_loader import DocTypeSpec
from context_builder.extraction.page_parser import find_text_position
from context_builder.extraction.normalizers import get_normalizer, get_validator
from context_builder.utils.prompt_loader import load_prompt
from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    QualityGate,
    ExtractionRunMetadata,
    DocumentMetadata,
    PageContent,
)


class GenericFieldExtractor(FieldExtractor):
    """
    Generic extractor that works for any doc type using its DocTypeSpec.

    Uses two-pass extraction:
    1. Find candidate spans around hint keywords
    2. Extract structured fields using LLM on candidate snippets
    """

    EXTRACTOR_VERSION = "v1.0.0"
    PROMPT_NAME = "generic_extraction"

    def __init__(
        self,
        spec: DocTypeSpec,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        # Load prompt config to get model defaults
        prompt_data = load_prompt(self.PROMPT_NAME)
        prompt_config = prompt_data["config"]

        # Use provided values or fall back to prompt config
        resolved_model = model or prompt_config.get("model", "gpt-4o")
        resolved_temperature = temperature if temperature is not None else prompt_config.get("temperature", 0.1)

        super().__init__(spec, resolved_model)
        self.temperature = resolved_temperature
        self.max_tokens = prompt_config.get("max_tokens", 2048)
        self.client = OpenAI()

    def extract(
        self,
        pages: List[PageContent],
        doc_meta: DocumentMetadata,
        run_metadata: ExtractionRunMetadata,
    ) -> ExtractionResult:
        """
        Extract all fields defined in the spec from document pages.
        """
        # Step 1: Find candidate spans for all fields
        all_candidates = self._collect_all_candidates(pages)

        # Step 2: Build extraction context from candidates
        extraction_context = self._build_extraction_context(all_candidates, pages)

        # Step 3: Call LLM for structured extraction
        raw_extractions = self._llm_extract(extraction_context)

        # Step 4: Build ExtractedField objects with provenance
        fields = self._build_extracted_fields(raw_extractions, pages)

        # Step 5: Evaluate quality gate
        quality_gate = self._build_quality_gate(fields)

        return ExtractionResult(
            schema_version="extraction_result_v1",
            run=run_metadata,
            doc=doc_meta,
            pages=pages,
            fields=fields,
            quality_gate=quality_gate,
        )

    def _collect_all_candidates(
        self, pages: List[PageContent]
    ) -> Dict[str, List[CandidateSpan]]:
        """Collect candidate spans for each field."""
        candidates_by_field = {}

        for field_name in self.spec.all_fields:
            candidates = self._find_field_candidates(pages, field_name)
            candidates_by_field[field_name] = candidates

        return candidates_by_field

    def _build_extraction_context(
        self,
        candidates_by_field: Dict[str, List[CandidateSpan]],
        pages: List[PageContent],
    ) -> str:
        """
        Build context string for LLM extraction.

        Includes:
        - Document text snippets around candidate areas
        - Unique snippets to avoid repetition
        """
        # Collect unique snippets (by page + position)
        seen_snippets = set()
        snippets = []

        for field_name, candidates in candidates_by_field.items():
            for candidate in candidates[:3]:  # Limit candidates per field
                key = (candidate.page, candidate.char_start)
                if key not in seen_snippets:
                    seen_snippets.add(key)
                    snippets.append(
                        f"[Page {candidate.page}, chars {candidate.char_start}-{candidate.char_end}]\n"
                        f"{candidate.text}"
                    )

        # If no candidates found, include first page content
        if not snippets and pages:
            first_page = pages[0]
            preview = first_page.text[:2000]
            snippets.append(f"[Page 1, full preview]\n{preview}")

        return "\n\n---\n\n".join(snippets)

    def _llm_extract(self, context: str) -> Dict[str, Any]:
        """
        Call LLM to extract structured fields from context.

        Returns dict with field extractions including quotes for provenance.
        """
        # Build fields description for prompt
        fields_desc = self._build_fields_desc()

        # Load and render prompt template
        prompt_data = load_prompt(
            self.PROMPT_NAME,
            doc_type=self.spec.doc_type,
            fields_desc=fields_desc,
            context=context,
        )
        messages = prompt_data["messages"]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=messages,
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            # Return empty extractions on error
            return {"fields": [], "error": str(e)}

    def _build_fields_desc(self) -> str:
        """Build formatted field descriptions for prompt template."""
        lines = []
        for field_name in self.spec.all_fields:
            required = "required" if self.spec.is_required(field_name) else "optional"
            lines.append(f"- {field_name} ({required})")
        return "\n".join(lines)

    def _build_extracted_fields(
        self,
        raw_extractions: Dict[str, Any],
        pages: List[PageContent],
    ) -> List[ExtractedField]:
        """
        Convert raw LLM extractions to ExtractedField objects.

        Includes:
        - Normalization
        - Validation
        - Provenance mapping
        """
        fields = []
        raw_fields = raw_extractions.get("fields", [])

        # Process extracted fields
        extracted_names = set()
        for raw in raw_fields:
            field_name = raw.get("name")
            if not field_name or field_name not in self.spec.all_fields:
                continue

            extracted_names.add(field_name)

            value = raw.get("value")
            text_quote = raw.get("text_quote", "")
            confidence = raw.get("confidence", 0.5)
            is_placeholder = raw.get("is_placeholder", False)

            # Normalize value
            if value and field_name in self.spec.field_rules:
                rule = self.spec.field_rules[field_name]
                normalizer = get_normalizer(rule.normalize)
                normalized_value = normalizer(value)
            else:
                normalized_value = value

            # Build provenance if we have a quote
            provenance = []
            if text_quote and value:
                prov = self._find_provenance(pages, text_quote)
                if prov:
                    provenance.append(prov)

            # Determine status
            if value:
                status = "present"
            else:
                status = "missing"

            fields.append(ExtractedField(
                name=field_name,
                value=value,
                normalized_value=normalized_value,
                confidence=confidence,
                status=status,
                provenance=provenance,
                value_is_placeholder=is_placeholder,
            ))

        # Add missing fields
        for field_name in self.spec.all_fields:
            if field_name not in extracted_names:
                fields.append(self._create_missing_field(field_name))

        return fields

    def _find_provenance(
        self, pages: List[PageContent], text_quote: str
    ) -> Optional[FieldProvenance]:
        """Find provenance (page + position) for a text quote."""
        for page in pages:
            position = find_text_position(page.text, text_quote)
            if position:
                return FieldProvenance(
                    page=page.page,
                    method="di_text",
                    text_quote=text_quote,
                    char_start=position[0],
                    char_end=position[1],
                )
        return None


# Auto-register for supported doc types
def _register_extractors():
    """Register GenericFieldExtractor for all supported doc types."""
    supported_types = ["loss_notice", "police_report", "insurance_policy"]
    for doc_type in supported_types:
        ExtractorFactory.register(doc_type, GenericFieldExtractor)


_register_extractors()
