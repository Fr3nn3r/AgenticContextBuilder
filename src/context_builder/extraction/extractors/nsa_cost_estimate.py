"""
NSA Cost Estimate Extractor - Page-by-page extraction for repair cost estimates.

Extracts line items from Swiss automotive repair cost estimates (Kostenvoranschlag/Offerte)
using a page-by-page approach for better accuracy on multi-page documents.

Flow:
1. Extract each page independently (header from page 1, items from all, summary from last)
2. Merge page results into unified output
3. Validate totals match
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
from context_builder.extraction.normalizers import get_normalizer, get_validator, safe_float
from context_builder.extraction.evidence_resolver import resolve_evidence_offsets
from context_builder.extraction.validators import validate_extraction, attach_validation_meta
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


class NsaCostEstimateExtractor(FieldExtractor):
    """
    Page-by-page extractor for Swiss automotive repair cost estimates.

    Optimized for:
    - Multi-page documents with many line items (up to 100+)
    - Übertrag (carry-forward) totals between pages
    - German and French language support
    - Dense parts lists (screws, o-rings, etc.)
    """

    EXTRACTOR_VERSION = "v1.0.0"
    PAGE_PROMPT = "nsa_cost_estimate_page"

    # Header fields extracted from page 1
    HEADER_FIELDS = {
        "document_number",
        "document_date",
        "document_type",
        "license_plate",
        "chassis_number",
        "vehicle_description",
        "garage_name",
    }

    # Summary fields extracted from last page
    SUMMARY_FIELDS = {
        "labor_total",
        "parts_total",
        "subtotal_before_vat",
        "vat_rate",
        "vat_amount",
        "total_amount_incl_vat",
        "currency",
    }

    def __init__(
        self,
        spec: DocTypeSpec,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        audit_storage_dir: Optional[Path] = None,
        decision_storage: Optional[DecisionStorage] = None,
        llm_sink: Optional[LLMCallSink] = None,
    ):
        """Initialize NSA Cost Estimate extractor.

        Args:
            spec: Document type specification defining fields to extract
            model: Optional model override (defaults to prompt config)
            temperature: Optional temperature override (defaults to prompt config)
            audit_storage_dir: Optional directory for audit log storage
            decision_storage: Optional DecisionStorage for compliance logging
            llm_sink: Optional LLMCallSink for LLM call logging
        """
        # Load prompt config to get model defaults
        prompt_data = load_prompt(self.PAGE_PROMPT)
        prompt_config = prompt_data["config"]

        # Use provided values or fall back to prompt config
        resolved_model = model or prompt_config.get("model", "gpt-4o")
        resolved_temperature = temperature if temperature is not None else prompt_config.get("temperature", 0.1)

        super().__init__(spec, resolved_model)
        self.temperature = resolved_temperature
        self.max_tokens = prompt_config.get("max_tokens", 4096)

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
        Page-by-page extraction with merge:
        1. Extract each page independently
        2. Merge into unified result
        3. Validate totals

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

        total_pages = len(pages)
        logger.info(
            f"Starting page-by-page extraction | claim={doc_meta.claim_id} "
            f"doc={doc_meta.doc_id} | pages={total_pages}"
        )

        # Extract each page
        page_results = []
        for page in pages:
            page_num = page.page
            is_first = (page_num == 1)
            is_last = (page_num == total_pages)

            page_result = self._extract_page(
                page=page,
                page_number=page_num,
                total_pages=total_pages,
                is_first_page=is_first,
                is_last_page=is_last,
            )
            page_results.append(page_result)

        # Merge results
        merged = self._merge_page_results(page_results, total_pages)

        # Build ExtractedField objects
        all_fields = self._build_fields_from_merged(merged, pages)

        # Add missing fields
        extracted_names = {f.name for f in all_fields}
        for field_name in self.spec.all_fields:
            if field_name not in extracted_names:
                all_fields.append(self._create_missing_field(field_name))

        # Build quality gate
        quality_gate = self._build_quality_gate(all_fields)

        # Build result with structured data for line items
        line_items = merged.get("line_items", [])
        structured_data = {"line_items": line_items} if line_items else None

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

        # Run validation and attach metadata
        validations = validate_extraction(result)
        result = attach_validation_meta(result, validations)

        # Log extraction decision
        self._log_extraction_decision(result, merged)

        return result

    def _extract_page(
        self,
        page: PageContent,
        page_number: int,
        total_pages: int,
        is_first_page: bool,
        is_last_page: bool,
    ) -> Dict[str, Any]:
        """
        Extract data from a single page.

        Args:
            page: Page content
            page_number: Current page number (1-indexed)
            total_pages: Total number of pages
            is_first_page: Whether this is the first page
            is_last_page: Whether this is the last page

        Returns:
            Dict with page extraction results
        """
        claim_id = self._audit_context.get("claim_id", "unknown")
        doc_id = self._audit_context.get("doc_id", "unknown")

        # Set up injected context for audit
        injected = InjectedContext(
            context_tier="page_extraction",
            total_source_chars=len(page.text),
            injected_chars=len(page.text),
            sources=[
                InjectedContextSource(
                    source_type="page",
                    page_number=page_number,
                    char_start=0,
                    char_end=len(page.text),
                    content_preview=page.text[:200] if page.text else "",
                    selection_criteria=f"page_{page_number}_of_{total_pages}",
                )
            ],
            field_hints_used=[],
            template_variables={
                "page_number": page_number,
                "total_pages": total_pages,
                "is_first_page": is_first_page,
                "is_last_page": is_last_page,
            },
        )
        self.audited_client.set_injected_context(injected)

        # Load and render prompt with page context
        prompt_data = load_prompt(
            self.PAGE_PROMPT,
            context=page.text,
            page_number=page_number,
            total_pages=total_pages,
            is_first_page=is_first_page,
            is_last_page=is_last_page,
        )
        messages = prompt_data["messages"]

        logger.info(
            f"Extracting page {page_number}/{total_pages} | "
            f"claim={claim_id} doc={doc_id} | chars={len(page.text)}"
        )

        response = None
        content = None
        try:
            response = self.audited_client.chat_completions_create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=messages,
            )

            content = response.choices[0].message.content

            # Log token usage
            if response.usage:
                logger.info(
                    f"Page {page_number} extraction complete | "
                    f"claim={claim_id} doc={doc_id} | "
                    f"tokens={response.usage.total_tokens}"
                )

            return json.loads(content)

        except json.JSONDecodeError as e:
            call_id = self.audited_client.get_call_id()
            error_pos = e.pos if hasattr(e, 'pos') else 0
            snippet_start = max(0, error_pos - 100)
            snippet_end = min(len(content) if content else 0, error_pos + 100)
            snippet = content[snippet_start:snippet_end] if content else ""
            logger.error(
                f"Page {page_number} JSON parse failed | "
                f"claim={claim_id} doc={doc_id} call_id={call_id} | "
                f"error: {e.msg} at line {e.lineno} col {e.colno} | "
                f"snippet: ...{snippet!r}..."
            )
            return {
                "page_number": page_number,
                "line_items": [],
                "error": str(e),
            }

        except Exception as e:
            call_id = self.audited_client.get_call_id()
            logger.error(
                f"Page {page_number} extraction failed | "
                f"claim={claim_id} doc={doc_id} call_id={call_id} | "
                f"{type(e).__name__}: {e}"
            )
            return {
                "page_number": page_number,
                "line_items": [],
                "error": str(e),
            }

    def _merge_page_results(
        self,
        page_results: List[Dict[str, Any]],
        total_pages: int,
    ) -> Dict[str, Any]:
        """
        Merge page extractions into unified result.

        Args:
            page_results: List of page extraction results
            total_pages: Total number of pages

        Returns:
            Merged result with header, all line items, and summary
        """
        # Header from first page
        header = {}
        if page_results and page_results[0].get("header"):
            header = page_results[0]["header"]

        # Combine all line items with page numbers
        all_items = []
        for page_result in page_results:
            page_num = page_result.get("page_number", 0)
            for item in page_result.get("line_items", []):
                item["page_number"] = page_num
                all_items.append(item)

        # Summary from last page
        summary = {}
        if page_results and page_results[-1].get("summary"):
            summary = page_results[-1]["summary"]

        # Validate totals (use safe_float to handle string values from LLM)
        items_sum = sum(
            safe_float(item.get("total_price"))
            for item in all_items
        )
        subtotal = safe_float(summary.get("subtotal_before_vat"))
        validated = abs(items_sum - subtotal) < 5.0  # Allow CHF 5 tolerance

        if not validated and subtotal > 0:
            logger.warning(
                f"Line items sum ({items_sum:.2f}) does not match "
                f"subtotal ({subtotal:.2f}) - diff={abs(items_sum - subtotal):.2f}"
            )

        return {
            "header": header,
            "line_items": all_items,
            "summary": summary,
            "_meta": {
                "page_count": total_pages,
                "total_line_items": len(all_items),
                "items_sum": items_sum,
                "extraction_validated": validated,
            },
        }

    def _build_fields_from_merged(
        self,
        merged: Dict[str, Any],
        pages: List[PageContent],
    ) -> List[ExtractedField]:
        """
        Build ExtractedField objects from merged result.

        Args:
            merged: Merged extraction result
            pages: All document pages

        Returns:
            List of ExtractedField objects
        """
        fields = []
        header = merged.get("header", {})
        summary = merged.get("summary", {})
        line_items = merged.get("line_items", [])
        meta = merged.get("_meta", {})

        # Header fields
        for field_name in self.HEADER_FIELDS:
            value = header.get(field_name)
            if value:
                # Normalize if rule exists
                normalized = value
                if field_name in self.spec.field_rules:
                    rule = self.spec.field_rules[field_name]
                    normalizer = get_normalizer(rule.normalize)
                    normalized = normalizer(value)

                fields.append(ExtractedField(
                    name=field_name,
                    value=value,
                    normalized_value=normalized,
                    confidence=0.9,
                    status="present",
                    provenance=[FieldProvenance(
                        page=1,
                        method="llm_parse",
                        text_quote=str(value)[:100],
                        char_start=0,
                        char_end=0,
                    )],
                    value_is_placeholder=False,
                ))

        # Summary fields
        for field_name in self.SUMMARY_FIELDS:
            value = summary.get(field_name)
            if value is not None:
                # Normalize if rule exists
                normalized = value
                if field_name in self.spec.field_rules:
                    rule = self.spec.field_rules[field_name]
                    normalizer = get_normalizer(rule.normalize)
                    normalized = normalizer(str(value))

                fields.append(ExtractedField(
                    name=field_name,
                    value=str(value),
                    normalized_value=str(normalized),
                    confidence=0.9,
                    status="present",
                    provenance=[FieldProvenance(
                        page=len(pages),
                        method="llm_parse",
                        text_quote=str(value),
                        char_start=0,
                        char_end=0,
                    )],
                    value_is_placeholder=False,
                ))

        # Line items field (structured data stored separately in result.structured_data)
        if line_items:
            # Human-readable summary for both value and normalized_value
            labor_count = sum(1 for i in line_items if i.get("item_type") == "labor")
            parts_count = sum(1 for i in line_items if i.get("item_type") == "parts")
            fee_count = sum(1 for i in line_items if i.get("item_type") == "fee")
            summary_text = f"{len(line_items)} items: {labor_count} labor, {parts_count} parts, {fee_count} fees"

            fields.append(ExtractedField(
                name="line_items",
                value=summary_text,
                normalized_value=summary_text,  # Human-readable; actual data in structured_data.line_items
                confidence=0.9 if meta.get("extraction_validated", False) else 0.7,
                status="present",
                provenance=[FieldProvenance(
                    page=1,
                    method="llm_parse",
                    text_quote=f"[{len(line_items)} line items across {meta.get('page_count', 1)} pages]",
                    char_start=0,
                    char_end=0,
                )],
                value_is_placeholder=False,
            ))

        # Metadata field
        fields.append(ExtractedField(
            name="_extraction_meta",
            value=f"Pages: {meta.get('page_count', 0)}, Items: {meta.get('total_line_items', 0)}, Validated: {meta.get('extraction_validated', False)}",
            normalized_value=json.dumps(meta, ensure_ascii=False),
            confidence=1.0,
            status="present",
            provenance=[],
            value_is_placeholder=False,
        ))

        return fields

    def _log_extraction_decision(
        self,
        result: ExtractionResult,
        merged: Dict[str, Any],
    ) -> None:
        """Log extraction decision to the compliance ledger.

        Args:
            result: The extraction result
            merged: The merged extraction data
        """
        try:
            fields = result.fields
            present_fields = [f.name for f in fields if f.status == "present"]
            missing_fields = [f.name for f in fields if f.status == "missing"]
            meta = merged.get("_meta", {})

            call_id = self.audited_client.get_call_id()
            rationale = DecisionRationale(
                summary=f"Cost Estimate: {meta.get('total_line_items', 0)} items from {meta.get('page_count', 0)} pages",
                confidence=0.9 if meta.get("extraction_validated", False) else 0.7,
                llm_call_ids=[call_id] if call_id else [],
                notes=f"Quality gate: {result.quality_gate.status}, Validated: {meta.get('extraction_validated', False)}",
            )

            fields_extracted = [
                {
                    "name": f.name,
                    "value": f.value[:100] if f.value and len(f.value) > 100 else f.value,
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
                actor_id="nsa_cost_estimate_extractor",
                metadata={
                    "doc_type": result.doc.doc_type,
                    "model": self.model,
                    "extractor_version": self.EXTRACTOR_VERSION,
                    "page_count": meta.get("page_count", 0),
                    "line_items_count": meta.get("total_line_items", 0),
                    "extraction_validated": meta.get("extraction_validated", False),
                },
            )

            self._decision_storage.append(record)
            logger.debug(f"Logged extraction decision for doc_id={result.doc.doc_id}")

        except Exception as e:
            # Don't fail extraction if logging fails
            logger.warning(f"Failed to log extraction decision: {e}")
