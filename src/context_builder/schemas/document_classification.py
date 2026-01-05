"""Pydantic schema for document classification structured output."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
from enum import Enum


class ClaimsDocumentType(str, Enum):
    """Standard document types for insurance claims processing."""
    INSURANCE_POLICY = "insurance_policy"
    LOSS_NOTICE = "loss_notice"
    POLICE_REPORT = "police_report"
    ID_DOCUMENT = "id_document"
    VEHICLE_REGISTRATION = "vehicle_registration"
    INVOICE = "invoice"
    CERTIFICATE = "certificate"
    SUPPORTING_DOCUMENT = "supporting_document"


class DocumentClassification(BaseModel):
    """
    Structured output schema for document classification.

    This schema defines the expected structure when classifying documents
    based on their text content. Uses json_object mode to allow flexible
    key_information structures based on document type.
    """

    model_config = ConfigDict(extra="forbid")

    document_type: str = Field(
        ...,
        description="Type of document. For claims: insurance_policy, loss_notice, "
                    "police_report, id_document, vehicle_registration, invoice, "
                    "certificate, supporting_document"
    )

    language: str = Field(
        ...,
        description="Primary language code (e.g., 'es', 'en')"
    )

    summary: str = Field(
        ...,
        description="Brief summary of the document content (1-2 sentences)"
    )

    key_information: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value pairs extracted from the document. "
                    "Structure varies by document type: "
                    "- insurance_policy: {policy_number, insured_name, vehicle_plate, "
                    "coverage_type, effective_date, expiry_date} "
                    "- police_report: {report_number, incident_date, location, description} "
                    "- id_document: {name, id_number, expiry_date} "
                    "- vehicle_registration: {plate, make, model, year, owner} "
                    "- invoice: {invoice_number, amount, vendor, date}"
    )

    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Classification confidence score (0.0-1.0)"
    )
