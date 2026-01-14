"""
Generic field extractor using two-pass approach:
1. Candidate span finder (regex/keywords)
2. LLM structured extraction on snippets

All LLM calls are logged via the compliance audit service.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

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
from context_builder.services.llm_audit import AuditedOpenAIClient, get_llm_audit_service
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.services.compliance import (
    DecisionStorage,
    LLMCallSink,
)
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
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
        audit_storage_dir: Optional[Path] = None,
        decision_storage: Optional[DecisionStorage] = None,
        llm_sink: Optional[LLMCallSink] = None,
    ):
        """Initialize generic field extractor.

        Args:
            spec: Document type specification defining fields to extract
            model: Optional model override (defaults to prompt config)
            temperature: Optional temperature override (defaults to prompt config)
            audit_storage_dir: Optional directory for audit log storage (used if
                decision_storage/llm_sink not provided)
            decision_storage: Optional DecisionStorage implementation for compliance
                logging. If not provided, creates default DecisionLedger.
            llm_sink: Optional LLMCallSink implementation for LLM call logging.
                If not provided, creates default audit service.
        """
        # Load prompt config to get model defaults
        prompt_data = load_prompt(self.PROMPT_NAME)
        prompt_config = prompt_data["config"]

        # Use provided values or fall back to prompt config
        resolved_model = model or prompt_config.get("model", "gpt-4o")
        resolved_temperature = temperature if temperature is not None else prompt_config.get("temperature", 0.1)

        super().__init__(spec, resolved_model)
        self.temperature = resolved_temperature
        self.max_tokens = prompt_config.get("max_tokens", 2048)

        # Use audited client for compliance logging
        raw_client = OpenAI()
        # Use injected sink or create default audit service
        if llm_sink is not None:
            self.audited_client = AuditedOpenAIClient(raw_client, llm_sink)
        else:
            audit_service = get_llm_audit_service(audit_storage_dir)
            self.audited_client = AuditedOpenAIClient(raw_client, audit_service)

        # Keep raw client for backwards compatibility
        self.client = raw_client

        # Context for audit logging (set before extract())
        self._audit_context: Dict[str, Optional[str]] = {
            "claim_id": None,
            "doc_id": None,
            "run_id": None,
        }

        # Initialize decision storage for compliance logging
        # Use injected storage or create default DecisionLedger
        if decision_storage is not None:
            self._decision_storage = decision_storage
        else:
            ledger_dir = audit_storage_dir or Path("output/logs")
            self._decision_storage = DecisionLedger(ledger_dir)

    def extract(
        self,
        pages: List[PageContent],
        doc_meta: DocumentMetadata,
        run_metadata: ExtractionRunMetadata,
    ) -> ExtractionResult:
        """
        Extract all fields defined in the spec from document pages.
        """
        # Set audit context for LLM call logging
        self._audit_context = {
            "claim_id": doc_meta.claim_id,
            "doc_id": doc_meta.doc_id,
            "run_id": run_metadata.run_id,
        }
        self.audited_client.set_context(
            claim_id=doc_meta.claim_id,
            doc_id=doc_meta.doc_id,
            run_id=run_metadata.run_id,
            call_purpose="extraction",
        )

        # Step 1: Find candidate spans for all fields
        all_candidates = self._collect_all_candidates(pages)

        # Step 2: Build extraction context from candidates
        extraction_context = self._build_extraction_context(all_candidates, pages)

        # Step 3: Call LLM for structured extraction
        raw_extractions = self._llm_extract(extraction_context)

        # Step 4: Build ExtractedField objects with provenance
        fields = self._build_extracted_fields(raw_extractions, pages, all_candidates)

        # Step 5: Evaluate quality gate
        quality_gate = self._build_quality_gate(fields)

        # Step 6: Log extraction decision
        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=run_metadata,
            doc=doc_meta,
            pages=pages,
            fields=fields,
            quality_gate=quality_gate,
        )
        self._log_extraction_decision(result)

        return result

    def _log_extraction_decision(self, result: ExtractionResult) -> None:
        """Log extraction decision to the compliance ledger.

        Args:
            result: The extraction result
        """
        try:
            # Build decision rationale
            fields = result.fields
            present_fields = [f.name for f in fields if f.status == "present"]
            missing_fields = [f.name for f in fields if f.status == "missing"]
            avg_confidence = sum(f.confidence for f in fields if f.confidence) / len(fields) if fields else 0.0

            rationale = DecisionRationale(
                summary=f"Extracted {len(present_fields)} fields, {len(missing_fields)} missing",
                confidence=avg_confidence,
                llm_call_id=self.audited_client.get_last_call_id(),
                notes=f"Quality gate: {result.quality_gate.status}",
            )

            # Build decision outcome
            fields_extracted = [
                {
                    "name": f.name,
                    "value": f.value,
                    "confidence": f.confidence,
                    "status": f.status,
                }
                for f in fields
            ]

            outcome = DecisionOutcome(
                fields_extracted=fields_extracted,
                quality_gate_status=result.quality_gate.status,
                missing_required_fields=result.quality_gate.missing_required_fields,
            )

            # Create and log decision record
            record = DecisionRecord(
                decision_id="",  # Will be generated by ledger
                decision_type=DecisionType.EXTRACTION,
                claim_id=result.doc.claim_id,
                doc_id=result.doc.doc_id,
                run_id=result.run.run_id,
                rationale=rationale,
                outcome=outcome,
                actor_type="system",
                actor_id="generic_extractor",
                metadata={
                    "doc_type": result.doc.doc_type,
                    "model": self.model,
                    "extractor_version": self.EXTRACTOR_VERSION,
                },
            )

            self._decision_storage.append(record)
            logger.debug(f"Logged extraction decision for doc_id={result.doc.doc_id}")

        except Exception as e:
            # Don't fail extraction if logging fails
            logger.warning(f"Failed to log extraction decision: {e}")

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
        All calls are logged via the compliance audit service.
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
            # Use audited client for compliance logging
            response = self.audited_client.chat_completions_create(
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
        candidates_by_field: Optional[Dict[str, List[CandidateSpan]]] = None,
    ) -> List[ExtractedField]:
        """
        Convert raw LLM extractions to ExtractedField objects.

        Includes:
        - Normalization
        - Validation
        - Provenance mapping (using candidate page hints for accuracy)
        """
        fields = []
        raw_fields = raw_extractions.get("fields", [])
        candidates_by_field = candidates_by_field or {}

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
            # Use candidate pages as hints for more accurate page detection
            provenance = []
            if text_quote and value:
                hint_pages = []
                if field_name in candidates_by_field:
                    # Get unique pages from candidates, ordered by occurrence
                    seen_pages = set()
                    for cand in candidates_by_field[field_name]:
                        if cand.page not in seen_pages:
                            hint_pages.append(cand.page)
                            seen_pages.add(cand.page)
                prov = self._find_provenance(pages, text_quote, hint_pages)
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
        self,
        pages: List[PageContent],
        text_quote: str,
        hint_pages: Optional[List[int]] = None,
    ) -> Optional[FieldProvenance]:
        """
        Find provenance (page + position) for a text quote.

        Args:
            pages: List of document pages
            text_quote: The text to find
            hint_pages: Pages to search first (from candidate finder)

        Returns:
            FieldProvenance with correct page number, or None if not found
        """
        # Build page lookup for efficient access
        page_by_num = {p.page: p for p in pages}

        # Search hint pages first (most likely to contain the text)
        if hint_pages:
            for page_num in hint_pages:
                if page_num in page_by_num:
                    page = page_by_num[page_num]
                    position = find_text_position(page.text, text_quote)
                    if position:
                        return FieldProvenance(
                            page=page.page,
                            method="di_text",
                            text_quote=text_quote,
                            char_start=position[0],
                            char_end=position[1],
                        )

        # Fall back to searching all pages if not found in hints
        for page in pages:
            # Skip pages already searched via hints
            if hint_pages and page.page in hint_pages:
                continue
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
    """Register GenericFieldExtractor for all doc types with specs."""
    from context_builder.extraction.spec_loader import list_available_specs

    for doc_type in list_available_specs():
        ExtractorFactory.register(doc_type, GenericFieldExtractor)


_register_extractors()
