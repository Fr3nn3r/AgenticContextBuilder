"""Pydantic schemas for extraction results with provenance tracking."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


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


class ExtractedField(BaseModel):
    """A single extracted field with value, confidence, and provenance."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Field name (e.g., 'claim_number')")
    value: Optional[str] = Field(None, description="Raw extracted value")
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

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["extraction_result_v1"] = Field(
        default="extraction_result_v1", description="Schema version for compatibility"
    )
    run: ExtractionRunMetadata = Field(..., description="Run metadata")
    doc: DocumentMetadata = Field(..., description="Document metadata")
    pages: List[PageContent] = Field(..., description="Page-level text content")
    fields: List[ExtractedField] = Field(..., description="Extracted fields")
    quality_gate: QualityGate = Field(..., description="Quality assessment")
