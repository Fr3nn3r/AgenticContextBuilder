"""Pydantic schemas for extraction results with provenance tracking."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


class CellReference(BaseModel):
    """Reference to a specific table cell."""

    model_config = ConfigDict(extra="forbid")

    table_index: int = Field(..., ge=0, description="Index of the table on the page")
    row_index: int = Field(..., ge=0, description="Row index within the table")
    column_index: int = Field(..., ge=0, description="Column index within the table")


class FieldProvenance(BaseModel):
    """Evidence source for an extracted field value."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., description="Page number (1-indexed)")
    method: Literal["di_text", "vision_ocr", "llm_parse"] = Field(
        ..., description="Extraction method used"
    )
    text_quote: str = Field(..., description="Exact text from source document")
    char_start: int = Field(..., ge=0, description="Character offset start in page text")
    char_end: int = Field(..., ge=0, description="Character offset end in page text")
    match_quality: Optional[str] = Field(
        default=None,
        description="How quote was matched: exact/case_insensitive/normalized/resolved/not_found/placeholder/page_not_found"
    )
    # Table cell reference (P1.1)
    cell_ref: Optional[CellReference] = Field(
        default=None,
        description="Reference to specific table cell when value comes from a table"
    )


class ExtractedField(BaseModel):
    """A single extracted field with value, confidence, and provenance."""

    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)

    name: str = Field(..., description="Field name (e.g., 'claim_number')")
    value: Union[str, List[str], None] = Field(None, description="Raw extracted value (string or list for multi-value fields)")

    @field_validator("value", mode="before")
    @classmethod
    def coerce_numeric_value(cls, v: Any) -> Any:
        """Coerce numeric values to strings. LLMs sometimes return ints/floats for fields like mileage."""
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            return [str(item) if isinstance(item, (int, float)) else item for item in v]
        return v

    normalized_value: Optional[str] = Field(None, description="Value after normalization")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    status: Literal["present", "missing", "uncertain"] = Field(
        ..., description="Extraction status"
    )
    provenance: List[FieldProvenance] = Field(
        default_factory=list, description="Evidence sources for this field"
    )
    value_is_placeholder: bool = Field(
        default=False, description="True if value is a redacted placeholder like [NAME_1]"
    )
    has_verified_evidence: bool = Field(
        default=False, description="True if provenance has verified char offsets"
    )


class QualityGate(BaseModel):
    """Quality assessment of extraction results."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pass", "warn", "fail"] = Field(
        ..., description="Overall quality status"
    )
    reasons: List[str] = Field(
        default_factory=list, description="Reasons for warn/fail status"
    )
    missing_required_fields: List[str] = Field(
        default_factory=list, description="Required fields that were not extracted"
    )
    needs_vision_fallback: bool = Field(
        default=False, description="True if text extraction quality is poor"
    )


class ExtractionRunMetadata(BaseModel):
    """Metadata about the extraction run for reproducibility."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(..., description="Unique run identifier (ISO timestamp)")
    extractor_version: str = Field(..., description="Extractor module version")
    model: str = Field(..., description="LLM model used for extraction")
    prompt_version: str = Field(..., description="Prompt template version")
    input_hashes: Dict[str, str] = Field(
        default_factory=dict,
        description="Input file hashes for reproducibility (pdf_md5, di_text_md5)"
    )
    version_bundle_id: Optional[str] = Field(
        default=None,
        description="Version bundle ID linking to code/config snapshot for compliance"
    )


class DocumentMetadata(BaseModel):
    """Metadata about the document being extracted."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(..., description="Unique document identifier")
    claim_id: str = Field(..., description="Parent claim identifier")
    doc_type: str = Field(..., description="Document type (loss_notice, police_report, etc.)")
    doc_type_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence"
    )
    language: str = Field(..., description="Document language code (es, en)")
    page_count: int = Field(..., ge=1, description="Number of pages")
    source_file_path: Optional[str] = Field(
        default=None,
        description="Path to original source file (PDF/image) for vision-based extraction"
    )


class PageContent(BaseModel):
    """Content of a single page."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    text: str = Field(..., description="Page text content")
    text_md5: str = Field(..., description="MD5 hash of page text for tracking")


class ExtractionResult(BaseModel):
    """
    Complete extraction result for a document.

    This is the primary output schema written to *.extraction.json files.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal["extraction_result_v1"] = Field(
        default="extraction_result_v1", description="Schema version for compatibility"
    )
    run: ExtractionRunMetadata = Field(..., description="Run metadata")
    doc: DocumentMetadata = Field(..., description="Document metadata")
    pages: List[PageContent] = Field(..., description="Page-level text content")
    fields: List[ExtractedField] = Field(..., description="Extracted fields")
    quality_gate: QualityGate = Field(..., description="Quality assessment")
    structured_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Complex structured data (line_items, nested objects) that cannot be represented as simple field values"
    )
    extraction_meta: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="_extraction_meta",
        description="Validation results and diagnostics"
    )
