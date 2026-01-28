"""Pydantic schemas for aggregated claim facts output."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class FactProvenance(BaseModel):
    """Provenance information for the selected fact value."""

    doc_id: str = Field(..., description="Document ID where this value was extracted")
    doc_type: str = Field(..., description="Document type (e.g., insurance_policy)")
    extraction_run_id: str = Field(..., description="Extraction run ID that produced this value")
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
    extraction_run_id: str = Field(..., description="Extraction run ID that produced this line item")
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


class LineItemsSummary(BaseModel):
    """Summary statistics for line items to reduce token usage."""

    total_items: int = Field(0, description="Total number of line items")
    total_amount: float = Field(0.0, description="Sum of all line item amounts")
    by_type: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Breakdown by item_type: {type: {count, total, items: [descriptions]}}",
    )
    covered_total: float = Field(0.0, description="Total of covered items")
    not_covered_total: float = Field(0.0, description="Total of not-covered items")
    unknown_coverage_total: float = Field(0.0, description="Total of items with unknown coverage")


class PrimaryRepair(BaseModel):
    """High-value repair item for LLM focus."""

    description: str = Field(..., description="Item description")
    item_code: Optional[str] = Field(None, description="Part/labor code")
    total_price: float = Field(..., description="Total price")
    item_type: Optional[str] = Field(None, description="Item type (labor, parts, fee)")
    covered: Optional[bool] = Field(None, description="Whether item is covered")
    coverage_reason: Optional[str] = Field(None, description="Coverage lookup reason")


class StructuredClaimData(BaseModel):
    """Complex data that cannot be represented as simple facts."""

    line_items: Optional[List[AggregatedLineItem]] = Field(
        None, description="Line items from cost estimates"
    )
    service_entries: Optional[List[AggregatedServiceEntry]] = Field(
        None, description="Service history entries from service books"
    )
    # Summary fields for token reduction (prefixed for LLM visibility)
    line_items_summary: Optional[LineItemsSummary] = Field(
        None, description="Summary statistics for line items"
    )
    primary_repairs: Optional[List[PrimaryRepair]] = Field(
        None, description="High-value items (>500 CHF) for LLM focus"
    )


class ClaimFacts(BaseModel):
    """Aggregated facts for a claim, selected from multiple documents."""

    schema_version: str = Field(
        default="claim_facts_v3", description="Schema version identifier"
    )
    claim_id: str = Field(..., description="Claim identifier")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When aggregation was performed"
    )
    claim_run_id: str = Field(..., description="Claim run ID that produced this aggregation")
    extraction_runs_used: List[str] = Field(
        default_factory=list, description="Extraction run IDs that contributed facts"
    )
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


def migrate_claim_facts_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate claim facts data from v2 to v3 schema in-place.

    This function is idempotent - safe to call on already-migrated data.

    Handles:
    - Top-level `run_id` -> `extraction_runs_used` list
    - Adds placeholder `claim_run_id` (caller must set to actual value)
    - Updates `schema_version` to `claim_facts_v3`
    - Provenance `run_id` -> `extraction_run_id` in facts
    - Provenance in structured_data line_items and service_entries

    Args:
        data: Dictionary containing claim facts data (modified in-place)

    Returns:
        The modified dictionary (same reference as input)
    """
    # Already migrated - return early
    if data.get("schema_version") == "claim_facts_v3":
        return data

    # Migrate top-level run_id -> extraction_runs_used
    if "run_id" in data and "extraction_runs_used" not in data:
        old_run_id = data.pop("run_id")
        data["extraction_runs_used"] = [old_run_id] if old_run_id else []

    # Add placeholder claim_run_id if not present (caller should set real value)
    if "claim_run_id" not in data:
        data["claim_run_id"] = "MIGRATION_PLACEHOLDER"

    # Update schema version
    data["schema_version"] = "claim_facts_v3"

    # Migrate provenance in facts
    for fact in data.get("facts", []):
        selected_from = fact.get("selected_from", {})
        if "run_id" in selected_from and "extraction_run_id" not in selected_from:
            selected_from["extraction_run_id"] = selected_from.pop("run_id")

    # Migrate provenance in structured_data
    structured_data = data.get("structured_data")
    if structured_data:
        # Line items
        for item in structured_data.get("line_items") or []:
            source = item.get("source", {})
            if "run_id" in source and "extraction_run_id" not in source:
                source["extraction_run_id"] = source.pop("run_id")

        # Service entries
        for entry in structured_data.get("service_entries") or []:
            source = entry.get("source", {})
            if "run_id" in source and "extraction_run_id" not in source:
                source["extraction_run_id"] = source.pop("run_id")

    return data
