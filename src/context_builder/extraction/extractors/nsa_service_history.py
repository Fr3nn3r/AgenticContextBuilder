"""
NSA Service History Extractor - Extracts data from VW Group digital service records.

Handles both German (Service-Nachweis) and French (Justificatif d'entretien) documents.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from openai import OpenAI

from context_builder.extraction.base import FieldExtractor, ExtractorFactory
from context_builder.extraction.spec_loader import DocTypeSpec
from context_builder.extraction.page_parser import find_text_position
from context_builder.extraction.normalizers import get_normalizer
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
from context_builder.services.compliance import DecisionStorage, LLMCallSink
from context_builder.storage.workspace_paths import get_workspace_logs_dir
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
)

logger = logging.getLogger(__name__)


class NsaServiceHistoryExtractor(FieldExtractor):
    """
    Extractor for VW Group Digital Service Records.

    Handles:
    - German: Service-Nachweis, Komplettnachweis, Digitaler Serviceplan
    - French: Justificatif d'entretien, Justificatif complet

    Key data extracted:
    - Vehicle identification (VIN, model, delivery date)
    - Warranty information
    - Service entries with dates, mileage, and authorization status
    """

    EXTRACTOR_VERSION = "v1.0.0"
    PROMPT_NAME = "nsa_service_history"

    def __init__(
        self,
        spec: DocTypeSpec,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        audit_storage_dir: Optional[Path] = None,
        decision_storage: Optional[DecisionStorage] = None,
        llm_sink: Optional[LLMCallSink] = None,
    ):
        """Initialize service history extractor."""
        # Load prompt config for defaults
        prompt_data = load_prompt(self.PROMPT_NAME)
        prompt_config = prompt_data["config"]

        resolved_model = model or prompt_config.get("model", "gpt-4o")
        resolved_temperature = (
            temperature if temperature is not None else prompt_config.get("temperature", 0.1)
        )

        super().__init__(spec, resolved_model)
        self.temperature = resolved_temperature
        self.max_tokens = prompt_config.get("max_tokens", 4096)

        # Setup audited client
        raw_client = OpenAI()
        if llm_sink is not None:
            self.audited_client = AuditedOpenAIClient(raw_client, llm_sink)
        else:
            audit_service = get_llm_audit_service(audit_storage_dir)
            self.audited_client = AuditedOpenAIClient(raw_client, audit_service)

        self.client = raw_client
        self._audit_context: Dict[str, Optional[str]] = {
            "claim_id": None,
            "doc_id": None,
            "run_id": None,
        }

        # Decision storage
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
        """Extract service history data from document pages."""
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

        # Build context from all pages
        context = "\n\n".join([f"[Page {p.page}]\n{p.text}" for p in pages])

        # Setup injected context for audit
        sources = [
            InjectedContextSource(
                source_type="page",
                page_number=p.page,
                char_start=0,
                char_end=len(p.text),
                content_preview=p.text[:200] if p.text else "",
                selection_criteria="full_page",
            )
            for p in pages
        ]

        injected = InjectedContext(
            context_tier="service_history_extraction",
            total_source_chars=sum(len(p.text) for p in pages),
            injected_chars=len(context),
            sources=sources,
            field_hints_used=list(self.spec.all_fields),
            template_variables={"doc_type": self.spec.doc_type},
        )
        self.audited_client.set_injected_context(injected)

        # Call LLM for extraction
        raw_extractions = self._llm_extract(context)

        # Build fields from extractions
        fields, structured_data = self._build_extracted_fields(raw_extractions, pages)

        # Build quality gate
        quality_gate = self._build_quality_gate(fields)

        result = ExtractionResult(
            schema_version="extraction_result_v1",
            run=run_metadata,
            doc=doc_meta,
            pages=pages,
            fields=fields,
            quality_gate=quality_gate,
            structured_data=structured_data if structured_data else None,
        )

        self._log_extraction_decision(result)
        return result

    def _llm_extract(self, context: str) -> Dict[str, Any]:
        """Call LLM to extract structured data."""
        claim_id = self._audit_context.get("claim_id", "unknown")
        doc_id = self._audit_context.get("doc_id", "unknown")

        prompt_data = load_prompt(self.PROMPT_NAME, context=context)
        messages = prompt_data["messages"]

        logger.info(
            f"Service history extraction | claim={claim_id} doc={doc_id} | "
            f"context_chars={len(context)}"
        )

        try:
            response = self.audited_client.chat_completions_create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=messages,
            )

            content = response.choices[0].message.content

            if response.usage:
                logger.info(
                    f"Service history extraction complete | claim={claim_id} doc={doc_id} | "
                    f"tokens={response.usage.total_tokens}"
                )

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error | claim={claim_id} doc={doc_id} | {e}")
            return {"fields": [], "service_entries": [], "error": str(e)}
        except Exception as e:
            logger.error(f"Extraction failed | claim={claim_id} doc={doc_id} | {e}")
            return {"fields": [], "service_entries": [], "error": str(e)}

    def _build_extracted_fields(
        self,
        raw_extractions: Dict[str, Any],
        pages: List[PageContent],
    ) -> tuple[List[ExtractedField], Dict[str, Any]]:
        """Convert LLM response to ExtractedField objects.

        Returns:
            Tuple of (fields, structured_data) where structured_data contains
            service_entries for storage in result.structured_data
        """
        fields = []
        raw_fields = raw_extractions.get("fields", [])
        service_entries = raw_extractions.get("service_entries", [])
        structured_data = {}

        # Index raw fields by name
        raw_by_name = {f.get("name"): f for f in raw_fields if f.get("name")}

        # Process standard fields
        for field_name in self.spec.all_fields:
            if field_name == "service_entries":
                # Handle service entries array separately
                if service_entries:
                    summary = f"{len(service_entries)} service entries"
                    fields.append(
                        ExtractedField(
                            name="service_entries",
                            value=summary,
                            normalized_value=summary,  # Human-readable; actual data in structured_data
                            confidence=0.9,
                            status="present",
                            provenance=[],
                            value_is_placeholder=False,
                        )
                    )
                    structured_data["service_entries"] = service_entries
                else:
                    fields.append(self._create_missing_field("service_entries"))
                continue

            raw = raw_by_name.get(field_name)
            if raw and raw.get("value"):
                value = raw.get("value")
                text_quote = raw.get("text_quote", "")
                confidence = raw.get("confidence", 0.5)
                is_placeholder = raw.get("is_placeholder", False)

                # Normalize
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

                fields.append(
                    ExtractedField(
                        name=field_name,
                        value=value,
                        normalized_value=normalized_value,
                        confidence=confidence,
                        status="present",
                        provenance=provenance,
                        value_is_placeholder=is_placeholder,
                    )
                )
            else:
                fields.append(self._create_missing_field(field_name))

        return fields, structured_data

    def _find_provenance(
        self,
        pages: List[PageContent],
        text_quote: str,
    ) -> Optional[FieldProvenance]:
        """Find text location in pages."""
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
        """Log extraction decision for compliance."""
        try:
            fields = result.fields
            present = [f.name for f in fields if f.status == "present"]
            missing = [f.name for f in fields if f.status == "missing"]
            avg_conf = sum(f.confidence for f in fields if f.confidence) / len(fields) if fields else 0.0

            call_id = self.audited_client.get_call_id()
            rationale = DecisionRationale(
                summary=f"Service History: {len(present)} fields, {len(missing)} missing",
                confidence=avg_conf,
                llm_call_ids=[call_id] if call_id else [],
                notes=f"Quality gate: {result.quality_gate.status}",
            )

            outcome = DecisionOutcome(
                fields_extracted=[
                    {"name": f.name, "value": f.value, "confidence": f.confidence, "status": f.status}
                    for f in fields
                ],
                quality_gate_status=result.quality_gate.status,
                missing_required_fields=result.quality_gate.missing_required_fields,
            )

            record = DecisionRecord(
                decision_id="",
                decision_type=DecisionType.EXTRACTION,
                claim_id=result.doc.claim_id,
                doc_id=result.doc.doc_id,
                run_id=result.run.run_id,
                rationale=rationale,
                outcome=outcome,
                actor_type="system",
                actor_id="nsa_service_history_extractor",
                metadata={
                    "doc_type": result.doc.doc_type,
                    "model": self.model,
                    "extractor_version": self.EXTRACTOR_VERSION,
                },
            )

            self._decision_storage.append(record)

        except Exception as e:
            logger.warning(f"Failed to log extraction decision: {e}")
