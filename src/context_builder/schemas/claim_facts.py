"""Pydantic schemas for aggregated claim facts output."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class FactProvenance(BaseModel):
    """Provenance information for the selected fact value."""

    doc_id: str = Field(..., description="Document ID where this value was extracted")
    doc_type: str = Field(..., description="Document type (e.g., insurance_policy)")
    run_id: str = Field(..., description="Run ID that produced this extraction")
    page: Optional[int] = Field(None, description="Page number where value was found")
    text_quote: Optional[str] = Field(
        None, description="Text snippet containing the value"
    )
    char_start: Optional[int] = Field(None, description="Character start offset")
    char_end: Optional[int] = Field(None, description="Character end offset")


class AggregatedFact(BaseModel):
    """A single aggregated fact with its selected value."""

    name: str = Field(..., description="Field name (e.g., policy_number)")
    value: Union[str, List[str], None] = Field(None, description="Selected value (highest confidence)")
    normalized_value: Optional[str] = Field(
        None, description="Normalized form of the selected value"
    )
    confidence: float = Field(..., description="Confidence score of selected value")
    selected_from: FactProvenance = Field(
        ..., description="Provenance of the selected value"
    )
    structured_value: Optional[Union[Dict[str, Any], List[Any]]] = Field(
        None,
        description="Structured data for complex fields (e.g., covered_components with full parts list, or coverage_scale as list)",
    )


class SourceDocument(BaseModel):
    """Reference to a source document used in aggregation."""

    doc_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    doc_type: str = Field(..., description="Classified document type")


class LineItemProvenance(BaseModel):
    """Provenance for a line item."""

    doc_id: str = Field(..., description="Document ID where this line item was extracted")
    doc_type: str = Field(..., description="Document type (e.g., cost_estimate)")
    filename: str = Field(..., description="Original filename")
    run_id: str = Field(..., description="Run ID that produced this extraction")
    # Row-level positioning (P0.1)
    page: Optional[int] = Field(None, description="Page number where item was found")
    char_start: Optional[int] = Field(None, description="Character start offset in page text")
    char_end: Optional[int] = Field(None, description="Character end offset in page text")
    text_quote: Optional[str] = Field(None, description="Text snippet containing the value")
    # Table cell reference (P1.1)
    table_index: Optional[int] = Field(None, description="Index of the table on the page")
    row_index: Optional[int] = Field(None, description="Row index within the table")


class AggregatedLineItem(BaseModel):
    """Line item from cost estimate with provenance."""

    item_code: Optional[str] = Field(None, description="Part/labor code")
    description: str = Field(..., description="Item description")
    quantity: Optional[float] = Field(None, description="Quantity")
    unit: Optional[str] = Field(None, description="Unit of measure")
    unit_price: Optional[float] = Field(None, description="Price per unit")
    total_price: Optional[float] = Field(None, description="Total price for this item")
    item_type: Optional[str] = Field(None, description="Item type (labor, parts, fee)")
    page_number: Optional[int] = Field(None, description="Page number where item was found")
    source: LineItemProvenance = Field(..., description="Provenance of this line item")


class AggregatedServiceEntry(BaseModel):
    """Service entry from service history with provenance."""

    service_type: Optional[str] = Field(None, description="Type of service performed")
    service_date: Optional[str] = Field(None, description="Date of service (ISO format)")
    mileage_km: Optional[int] = Field(None, description="Odometer reading at service")
    order_number: Optional[str] = Field(None, description="Work order number")
    work_performed: Optional[str] = Field(None, description="Main work description")
    additional_work: Optional[List[str]] = Field(None, description="Additional services performed")
    service_provider_name: Optional[str] = Field(None, description="Workshop/dealer name")
    service_provider_address: Optional[str] = Field(None, description="Workshop address")
    is_authorized_partner: Optional[bool] = Field(
        None, description="Whether service was at authorized dealer"
    )
    source: LineItemProvenance = Field(..., description="Provenance of this service entry")


class StructuredClaimData(BaseModel):
    """Complex data that cannot be represented as simple facts."""

    line_items: Optional[List[AggregatedLineItem]] = Field(
        None, description="Line items from cost estimates"
    )
    service_entries: Optional[List[AggregatedServiceEntry]] = Field(
        None, description="Service history entries from service books"
    )


class ClaimFacts(BaseModel):
    """Aggregated facts for a claim, selected from multiple documents."""

    schema_version: str = Field(
        default="claim_facts_v2", description="Schema version identifier"
    )
    claim_id: str = Field(..., description="Claim identifier")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When aggregation was performed"
    )
    run_id: str = Field(..., description="Run ID used for aggregation")
    run_policy: str = Field(
        default="latest_complete",
        description="Policy used to select run (latest_complete)",
    )
    facts: List[AggregatedFact] = Field(
        default_factory=list, description="Aggregated facts from all documents"
    )
    sources: List[SourceDocument] = Field(
        default_factory=list, description="Source documents used in aggregation"
    )
    structured_data: Optional[StructuredClaimData] = Field(
        None, description="Complex structured data (line items, etc.)"
    )
