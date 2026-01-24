"""
NSA Guarantee Extractor - Two-stage extraction for warranty policies.

Stage 1: Extract metadata from page 1 (policy, vehicle, coverage)
Stage 2: Extract component lists from pages 2-3 (covered/excluded)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from openai import OpenAI

from context_builder.extraction.base import (
    FieldExtractor,
    ExtractorFactory,
    CandidateSpan,
)
from context_builder.extraction.spec_loader import DocTypeSpec
from context_builder.extraction.page_parser import find_text_position
from context_builder.extraction.normalizers import get_normalizer, get_validator
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets
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
from context_builder.schemas.llm_call_record import InjectedContext, InjectedContextSource
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.services.compliance import (
    DecisionStorage,
    LLMCallSink,
)
from context_builder.storage.workspace_paths import get_workspace_logs_dir
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
)

logger = logging.getLogger(__name__)


class NsaGuaranteeExtractor(FieldExtractor):
    """
    Two-stage extractor for NSA Guarantee insurance policies.

    Optimized for:
    - Page 1: Structured key-value metadata (~30 fields)
    - Pages 2-3: Two-column component lists (covered vs excluded)
    - Bilingual support (German/English)
    """

    EXTRACTOR_VERSION = "v1.0.0"
    METADATA_PROMPT = "nsa_guarantee_metadata"
    COMPONENTS_PROMPT = "nsa_guarantee_components"

    # Pages for each stage
    METADATA_PAGES = [1]
    COMPONENT_PAGES = [2, 3]

    # Fields that are extracted from components (not metadata)
    COMPONENT_FIELDS = {"covered_components", "excluded_components", "coverage_scale"}

    # Component categories to extract
    COMPONENT_CATEGORIES = [
        "engine",
        "turbo_supercharger",
        "four_wd",
        "electric",
        "mechanical_transmission",
        "automatic_transmission",
        "limited_slip_differential",
        "fuel_system",
        "axle_drive",
        "steering",
        "brakes",
        "suspension",
        "electrical_system",
        "air_conditioning",
        "cooling_system",
        "chassis",
        "electronics",
        "comfort_options",
        "exhaust",
    ]

    def __init__(
        self,
        spec: DocTypeSpec,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        audit_storage_dir: Optional[Path] = None,
        decision_storage: Optional[DecisionStorage] = None,
        llm_sink: Optional[LLMCallSink] = None,
    ):
        """Initialize NSA Guarantee extractor.

        Args:
            spec: Document type specification defining fields to extract
            model: Optional model override (defaults to prompt config)
            temperature: Optional temperature override (defaults to prompt config)
            audit_storage_dir: Optional directory for audit log storage
            decision_storage: Optional DecisionStorage for compliance logging
            llm_sink: Optional LLMCallSink for LLM call logging
        """
        # Load prompt config to get model defaults
        prompt_data = load_prompt(self.METADATA_PROMPT)
        prompt_config = prompt_data["config"]

        # Use provided values or fall back to prompt config
        resolved_model = model or prompt_config.get("model", "gpt-4o")
        resolved_temperature = temperature if temperature is not None else prompt_config.get("temperature", 0.1)

        super().__init__(spec, resolved_model)
        self.temperature = resolved_temperature
        self.max_tokens_metadata = prompt_config.get("max_tokens", 2048)

        # Load components prompt config
        components_prompt_data = load_prompt(self.COMPONENTS_PROMPT)
        components_config = components_prompt_data["config"]
        self.max_tokens_components = components_config.get("max_tokens", 4096)

        # Use audited client for compliance logging
        raw_client = OpenAI()
        if llm_sink is not None:
            self.audited_client = AuditedOpenAIClient(raw_client, llm_sink)
        else:
            audit_service = get_llm_audit_service(audit_storage_dir)
            self.audited_client = AuditedOpenAIClient(raw_client, audit_service)

        # Keep raw client for backwards compatibility
        self.client = raw_client

        # Context for audit logging
        self._audit_context: Dict[str, Optional[str]] = {
            "claim_id": None,
            "doc_id": None,
            "run_id": None,
        }

        # Initialize decision storage
        if decision_storage is not None:
            self._decision_storage = decision_storage
        else:
            ledger_dir = audit_storage_dir or get_workspace_logs_dir()
            self._decision_storage = DecisionLedger(ledger_dir)

    def extract(
        self,
        pages: List[PageContent],
        doc_meta: DocumentMetadata,
        run_metadata: ExtractionRunMetadata,
    ) -> ExtractionResult:
        """
        Two-stage extraction:
        1. Metadata from page 1
        2. Components from pages 2-3

        Args:
            pages: List of parsed page content
            doc_meta: Document metadata
            run_metadata: Run metadata for tracking

        Returns:
            ExtractionResult with all extracted fields and quality gate
        """
        # Set audit context
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

        # Filter pages for each stage
        metadata_pages = [p for p in pages if p.page in self.METADATA_PAGES]
        component_pages = [p for p in pages if p.page in self.COMPONENT_PAGES]

        # Stage 1: Extract metadata from page 1
        metadata_fields = self._extract_metadata(metadata_pages, pages)

        # Stage 2: Extract components from pages 2-3
        component_fields, component_structured_data = self._extract_components(component_pages)

        # Merge results
        all_fields = metadata_fields + component_fields

        # Add missing fields
        extracted_names = {f.name for f in all_fields}
        for field_name in self.spec.all_fields:
            if field_name not in extracted_names:
                all_fields.append(self._create_missing_field(field_name))

        # Build quality gate
        quality_gate = self._build_quality_gate(all_fields)

        # Build structured_data from components (covered_components, excluded_components, coverage_scale)
        structured_data = component_structured_data if component_structured_data else None

        # Build result
        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=run_metadata,
            doc=doc_meta,
            pages=pages,
            fields=all_fields,
            quality_gate=quality_gate,
            structured_data=structured_data,
        )

        # Resolve evidence offsets
        result = resolve_evidence_offsets(result)

        # Log extraction decision
        self._log_extraction_decision(result)

        return result

    def _extract_metadata(
        self,
        metadata_pages: List[PageContent],
        all_pages: List[PageContent],
    ) -> List[ExtractedField]:
        """
        Extract structured metadata from page 1.
        Uses focused prompt for key-value pairs.

        Args:
            metadata_pages: Pages containing metadata (page 1)
            all_pages: All document pages (for provenance lookup)

        Returns:
            List of extracted metadata fields
        """
        claim_id = self._audit_context.get("claim_id", "unknown")
        doc_id = self._audit_context.get("doc_id", "unknown")

        if not metadata_pages:
            logger.warning(f"No metadata pages found | claim={claim_id} doc={doc_id}")
            return []

        # Build context from page 1
        context = "\n".join([
            f"[Page {p.page}]\n{p.text}"
            for p in metadata_pages
        ])

        # Get metadata field names (exclude component fields)
        metadata_field_names = [
            f for f in self.spec.all_fields
            if f not in self.COMPONENT_FIELDS
        ]

        # Set up injected context for audit logging
        sources = [
            InjectedContextSource(
                source_type="page",
                page_number=p.page,
                char_start=0,
                char_end=len(p.text),
                content_preview=p.text[:200] if p.text else "",
                selection_criteria="metadata_page",
            )
            for p in metadata_pages
        ]

        injected = InjectedContext(
            context_tier="metadata_extraction",
            total_source_chars=sum(len(p.text) for p in all_pages),
            injected_chars=len(context),
            sources=sources,
            field_hints_used=metadata_field_names,
            template_variables={
                "doc_type": self.spec.doc_type,
                "stage": "metadata",
            },
        )
        self.audited_client.set_injected_context(injected)

        # Load and render prompt
        prompt_data = load_prompt(
            self.METADATA_PROMPT,
            context=context,
        )
        messages = prompt_data["messages"]

        # Log pre-call info for debugging
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        logger.info(
            f"Metadata extraction starting | claim={claim_id} doc={doc_id} | "
            f"context_chars={len(context)} prompt_chars={prompt_chars} "
            f"max_tokens={self.max_tokens_metadata}"
        )

        response = None
        content = None
        try:
            response = self.audited_client.chat_completions_create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens_metadata,
                response_format={"type": "json_object"},
                messages=messages,
            )

            content = response.choices[0].message.content

            # Log token usage for successful calls
            if response.usage:
                logger.info(
                    f"Metadata extraction complete | claim={claim_id} doc={doc_id} | "
                    f"prompt_tokens={response.usage.prompt_tokens} "
                    f"completion_tokens={response.usage.completion_tokens} "
                    f"total_tokens={response.usage.total_tokens} "
                    f"finish_reason={response.choices[0].finish_reason}"
                )

            raw_extractions = json.loads(content)

        except json.JSONDecodeError as e:
            # Log detailed context for JSON parse failures
            call_id = self.audited_client.get_call_id()
            # Get token info from response if available
            token_info = ""
            if response and response.usage:
                token_info = (
                    f"prompt_tokens={response.usage.prompt_tokens} "
                    f"completion_tokens={response.usage.completion_tokens} "
                    f"finish_reason={response.choices[0].finish_reason} "
                )
            # Show snippet around the error position
            error_pos = e.pos if hasattr(e, 'pos') else 0
            snippet_start = max(0, error_pos - 100)
            snippet_end = min(len(content) if content else 0, error_pos + 100)
            snippet = content[snippet_start:snippet_end] if content else ""
            logger.error(
                f"Metadata extraction JSON parse failed | "
                f"claim={claim_id} doc={doc_id} call_id={call_id} | "
                f"{token_info}"
                f"error: {e.msg} at line {e.lineno} col {e.colno} (char {e.pos}) | "
                f"snippet: ...{snippet!r}..."
            )
            raw_extractions = {"fields": [], "error": str(e)}

        except Exception as e:
            call_id = self.audited_client.get_call_id()
            logger.error(
                f"Metadata extraction failed | claim={claim_id} doc={doc_id} call_id={call_id} | "
                f"{type(e).__name__}: {e}"
            )
            raw_extractions = {"fields": [], "error": str(e)}

        # Build ExtractedField objects
        return self._build_extracted_fields(
            raw_extractions,
            all_pages,
            metadata_field_names,
        )

    def _extract_components(
        self,
        component_pages: List[PageContent],
    ) -> tuple[List[ExtractedField], Dict[str, Any]]:
        """
        Extract component lists from pages 2-3.
        Returns structured data for covered/excluded components.

        Args:
            component_pages: Pages containing component lists (pages 2-3)

        Returns:
            Tuple of (fields, structured_data) where structured_data contains
            the raw component data for storage in result.structured_data
        """
        claim_id = self._audit_context.get("claim_id", "unknown")
        doc_id = self._audit_context.get("doc_id", "unknown")

        if not component_pages:
            logger.warning(f"No component pages found | claim={claim_id} doc={doc_id}")
            return [], {}

        # Build context from pages 2-3
        context = "\n\n".join([
            f"[Page {p.page}]\n{p.text}"
            for p in component_pages
        ])

        # Set up injected context
        sources = [
            InjectedContextSource(
                source_type="page",
                page_number=p.page,
                char_start=0,
                char_end=len(p.text),
                content_preview=p.text[:200] if p.text else "",
                selection_criteria="component_page",
            )
            for p in component_pages
        ]

        injected = InjectedContext(
            context_tier="component_extraction",
            total_source_chars=sum(len(p.text) for p in component_pages),
            injected_chars=len(context),
            sources=sources,
            field_hints_used=list(self.COMPONENT_FIELDS),
            template_variables={
                "doc_type": self.spec.doc_type,
                "stage": "components",
            },
        )
        self.audited_client.set_injected_context(injected)

        # Load and render prompt
        prompt_data = load_prompt(
            self.COMPONENTS_PROMPT,
            context=context,
        )
        messages = prompt_data["messages"]

        # Log pre-call info for debugging
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        logger.info(
            f"Component extraction starting | claim={claim_id} doc={doc_id} | "
            f"pages={[p.page for p in component_pages]} context_chars={len(context)} "
            f"prompt_chars={prompt_chars} max_tokens={self.max_tokens_components}"
        )

        response = None
        content = None
        try:
            response = self.audited_client.chat_completions_create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens_components,
                response_format={"type": "json_object"},
                messages=messages,
            )

            content = response.choices[0].message.content

            # Log token usage for successful calls
            if response.usage:
                logger.info(
                    f"Component extraction complete | claim={claim_id} doc={doc_id} | "
                    f"prompt_tokens={response.usage.prompt_tokens} "
                    f"completion_tokens={response.usage.completion_tokens} "
                    f"total_tokens={response.usage.total_tokens} "
                    f"finish_reason={response.choices[0].finish_reason}"
                )

            component_data = json.loads(content)

        except json.JSONDecodeError as e:
            # Log detailed context for JSON parse failures
            call_id = self.audited_client.get_call_id()
            # Get token info from response if available
            token_info = ""
            if response and response.usage:
                token_info = (
                    f"prompt_tokens={response.usage.prompt_tokens} "
                    f"completion_tokens={response.usage.completion_tokens} "
                    f"finish_reason={response.choices[0].finish_reason} "
                )
            # Show snippet around the error position
            error_pos = e.pos if hasattr(e, 'pos') else 0
            snippet_start = max(0, error_pos - 100)
            snippet_end = min(len(content) if content else 0, error_pos + 100)
            snippet = content[snippet_start:snippet_end] if content else ""
            logger.error(
                f"Component extraction JSON parse failed | "
                f"claim={claim_id} doc={doc_id} call_id={call_id} | "
                f"{token_info}"
                f"error: {e.msg} at line {e.lineno} col {e.colno} (char {e.pos}) | "
                f"snippet: ...{snippet!r}..."
            )
            component_data = {"covered": {}, "excluded": {}, "coverage_scale": []}

        except Exception as e:
            call_id = self.audited_client.get_call_id()
            logger.error(
                f"Component extraction failed | claim={claim_id} doc={doc_id} call_id={call_id} | "
                f"{type(e).__name__}: {e}"
            )
            component_data = {"covered": {}, "excluded": {}, "coverage_scale": []}

        # Build ExtractedField objects for component data
        # value and normalized_value = human-readable summary
        # Actual structured data returned separately for result.structured_data
        fields = []

        # Covered components
        covered = component_data.get("covered", {})
        covered_summary = self._summarize_components(covered) if covered else None
        fields.append(ExtractedField(
            name="covered_components",
            value=covered_summary,
            normalized_value=covered_summary,  # Human-readable; actual data in structured_data
            confidence=0.9 if covered else 0.0,
            status="present" if covered else "missing",
            provenance=[FieldProvenance(
                page=component_pages[0].page if component_pages else 1,
                method="llm_parse",
                text_quote="[Component list extraction]",
                char_start=0,
                char_end=0,
            )] if covered else [],
            value_is_placeholder=False,
        ))

        # Excluded components
        excluded = component_data.get("excluded", {})
        excluded_summary = self._summarize_components(excluded) if excluded else None
        fields.append(ExtractedField(
            name="excluded_components",
            value=excluded_summary,
            normalized_value=excluded_summary,  # Human-readable; actual data in structured_data
            confidence=0.9 if excluded else 0.0,
            status="present" if excluded else "missing",
            provenance=[FieldProvenance(
                page=component_pages[0].page if component_pages else 1,
                method="llm_parse",
                text_quote="[Component list extraction]",
                char_start=0,
                char_end=0,
            )] if excluded else [],
            value_is_placeholder=False,
        ))

        # Coverage scale
        coverage_scale = component_data.get("coverage_scale", [])
        coverage_summary = self._summarize_coverage_scale(coverage_scale) if coverage_scale else None
        fields.append(ExtractedField(
            name="coverage_scale",
            value=coverage_summary,
            normalized_value=coverage_summary,  # Human-readable; actual data in structured_data
            confidence=0.9 if coverage_scale else 0.0,
            status="present" if coverage_scale else "missing",
            provenance=[FieldProvenance(
                page=component_pages[-1].page if component_pages else 1,
                method="llm_parse",
                text_quote="[Coverage scale extraction]",
                char_start=0,
                char_end=0,
            )] if coverage_scale else [],
            value_is_placeholder=False,
        ))

        # Build structured data for complex fields
        structured_data = {}
        if covered:
            structured_data["covered_components"] = covered
        if excluded:
            structured_data["excluded_components"] = excluded
        if coverage_scale:
            structured_data["coverage_scale"] = coverage_scale

        return fields, structured_data

    def _summarize_components(self, components: Dict[str, List[str]]) -> str:
        """
        Create a human-readable summary of component categories.

        Args:
            components: Dict mapping category names to lists of parts

        Returns:
            Summary string like "Engine: 30 parts, Turbo: 3 parts, ..."
        """
        if not components:
            return ""

        parts = []
        for category, items in components.items():
            if items:
                # Convert category name to readable format
                readable_category = category.replace("_", " ").title()
                parts.append(f"{readable_category}: {len(items)} parts")

        return ", ".join(parts)

    def _summarize_coverage_scale(self, coverage_scale: List[Dict[str, Any]]) -> str:
        """
        Create a human-readable summary of coverage scale.

        Args:
            coverage_scale: List of {km_threshold, coverage_percent} dicts

        Returns:
            Summary string like "80% up to 50'000 km, 60% up to 80'000 km, ..."
        """
        if not coverage_scale:
            return ""

        parts = []
        for tier in coverage_scale:
            km = tier.get("km_threshold", 0)
            pct = tier.get("coverage_percent", 0)
            # Format km with Swiss thousands separator
            km_formatted = f"{km:,}".replace(",", "'")
            parts.append(f"{pct}% up to {km_formatted} km")

        return ", ".join(parts)

    def _build_extracted_fields(
        self,
        raw_extractions: Dict[str, Any],
        pages: List[PageContent],
        field_names: List[str],
    ) -> List[ExtractedField]:
        """
        Convert raw LLM extractions to ExtractedField objects.

        Args:
            raw_extractions: Raw LLM response with fields
            pages: All document pages (for provenance lookup)
            field_names: List of expected field names

        Returns:
            List of ExtractedField objects
        """
        fields = []
        raw_fields = raw_extractions.get("fields", [])

        # Index raw fields by name
        raw_by_name = {f.get("name"): f for f in raw_fields if f.get("name")}

        for field_name in field_names:
            raw = raw_by_name.get(field_name)

            if raw and raw.get("value"):
                value = raw.get("value")
                text_quote = raw.get("text_quote", "")
                confidence = raw.get("confidence", 0.5)
                is_placeholder = raw.get("is_placeholder", False)

                # Normalize value
                if field_name in self.spec.field_rules:
                    rule = self.spec.field_rules[field_name]
                    normalizer = get_normalizer(rule.normalize)
                    normalized_value = normalizer(value)
                else:
                    normalized_value = value

                # Find provenance
                provenance = []
                if text_quote:
                    prov = self._find_provenance(pages, text_quote)
                    if prov:
                        provenance.append(prov)

                fields.append(ExtractedField(
                    name=field_name,
                    value=value,
                    normalized_value=normalized_value,
                    confidence=confidence,
                    status="present",
                    provenance=provenance,
                    value_is_placeholder=is_placeholder,
                ))
            else:
                # Field not found - will be added as missing later
                pass

        return fields

    def _find_provenance(
        self,
        pages: List[PageContent],
        text_quote: str,
    ) -> Optional[FieldProvenance]:
        """
        Find provenance (page + position) for a text quote.

        Args:
            pages: List of document pages
            text_quote: The text to find

        Returns:
            FieldProvenance if found, None otherwise
        """
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

    def _log_extraction_decision(self, result: ExtractionResult) -> None:
        """Log extraction decision to the compliance ledger.

        Args:
            result: The extraction result
        """
        try:
            fields = result.fields
            present_fields = [f.name for f in fields if f.status == "present"]
            missing_fields = [f.name for f in fields if f.status == "missing"]
            avg_confidence = sum(f.confidence for f in fields if f.confidence) / len(fields) if fields else 0.0

            call_id = self.audited_client.get_call_id()
            rationale = DecisionRationale(
                summary=f"NSA Guarantee: Extracted {len(present_fields)} fields, {len(missing_fields)} missing",
                confidence=avg_confidence,
                llm_call_ids=[call_id] if call_id else [],
                notes=f"Quality gate: {result.quality_gate.status}",
            )

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

            record = DecisionRecord(
                decision_id="",  # Will be generated by ledger
                decision_type=DecisionType.EXTRACTION,
                claim_id=result.doc.claim_id,
                doc_id=result.doc.doc_id,
                run_id=result.run.run_id,
                rationale=rationale,
                outcome=outcome,
                actor_type="system",
                actor_id="nsa_guarantee_extractor",
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
