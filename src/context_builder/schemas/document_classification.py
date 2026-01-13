"""Pydantic schema for document classification structured output."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List
from enum import Enum


class ClaimsDocumentType(str, Enum):
    """Standard document types for insurance claims processing (LOB-agnostic)."""
    FNOL_FORM = "fnol_form"
    INSURANCE_POLICY = "insurance_policy"
    POLICE_REPORT = "police_report"
    INVOICE = "invoice"
    ID_DOCUMENT = "id_document"
    VEHICLE_REGISTRATION = "vehicle_registration"
    CERTIFICATE = "certificate"
    MEDICAL_REPORT = "medical_report"
    TRAVEL_ITINERARY = "travel_itinerary"
    CUSTOMER_COMM = "customer_comm"
    SUPPORTING_DOCUMENT = "supporting_document"
    DAMAGE_EVIDENCE = "damage_evidence"


class DocumentClassification(BaseModel):
    """
    Structured output schema for document classification router.

    This schema defines the expected structure when classifying documents.
    The classifier acts as a router - identifying doc type with signals,
    not performing deep extraction.
    """

    model_config = ConfigDict(extra="forbid")

    document_type: str = Field(
        ...,
        description="Type of document from the catalog: fnol_form, insurance_policy, "
                    "police_report, invoice, id_document, vehicle_registration, "
                    "certificate, medical_report, travel_itinerary, customer_comm, "
                    "supporting_document, damage_evidence"
    )

    language: str = Field(
        ...,
        description="Primary language code (e.g., 'es', 'en', 'fr')"
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Classification confidence score (0.0-1.0)"
    )

    summary: str = Field(
        ...,
        description="Brief summary of the document content (1-2 sentences)"
    )

    signals: List[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=5,
        description="2-5 short strings explaining strongest evidence for the chosen type "
                    "(e.g., headings, keywords, layout cues)"
    )

    key_hints: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional lightweight hints (max 3) if clearly present. "
                    "Allowed keys: policy_number, claim_reference, incident_date, "
                    "vehicle_plate, invoice_number, total_amount, currency. "
                    "Do NOT guess - only populate if obvious."
    )
