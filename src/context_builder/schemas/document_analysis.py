"""Pydantic schema for document analysis structured output."""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any


class DocumentAnalysis(BaseModel):
    """
    Structured output schema for document/page analysis.

    This schema defines the expected structure when analyzing documents
    or individual pages using vision/OCR capabilities.

    NOTE: We use json_object mode (not OpenAI's strict .parse() API) because
    key_information needs to be dynamically structured based on document type.
    Different documents require different fields:
    - Invoices: {invoice_number, date, amount, vendor, ...}
    - Insurance policies: {policy_number, plan_name, cost, coverage, ...}
    - Contracts: {parties, effective_date, terms, ...}

    OpenAI's strict structured output cannot accommodate this flexibility,
    so we parse JSON manually and validate with Pydantic afterward.
    """

    model_config = ConfigDict(extra="forbid")

    document_type: str = Field(
        ...,
        description="Type of document or page (e.g., invoice, report, form, letter, contract, receipt)"
    )

    language: str = Field(
        ...,
        description="Primary language of the document content"
    )

    summary: str = Field(
        ...,
        description="Brief summary of the page or document content"
    )

    key_information: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value pairs extracted from the document. "
                    "Structure should be document-type specific. "
                    "Examples: "
                    "- Invoice: {invoice_number, date, amount, vendor, currency, ...} "
                    "- Policy: {policy_number, plan_name, cost, coverage, traveler_information, ...} "
                    "- Contract: {parties, effective_date, terms, renewal_date, ...}"
    )

    visual_elements: List[str] = Field(
        default_factory=list,
        description="List of notable visual elements present in the document "
                    "(e.g., logos, charts, signatures, stamps, tables, images)"
    )

    text_content: str = Field(
        ...,
        description="All extracted text content from the page or document"
    )
