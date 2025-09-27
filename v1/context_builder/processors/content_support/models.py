# intake/processors/content_support/models.py
# Pydantic models for content processing configuration and outputs
# Defines type-safe configuration and structured output formats

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from ...exceptions import IntakeError


class ProcessingInfo(BaseModel):
    """Information about the processing operation."""
    processor_version: str = Field(..., description="Version of the content processor")
    processing_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="When processing occurred")
    processing_status: str = Field(..., description="Status: success, partial_success, or error")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    processing_time_seconds: Optional[float] = Field(None, description="Time taken for processing")
    extracted_by: Optional[list] = Field(None, description="List of extraction methods that succeeded")
    skipped_methods: Optional[list] = Field(None, description="List of extraction methods that were skipped")
    failed_methods: Optional[list] = Field(None, description="List of extraction methods that failed")


class ContentAnalysis(BaseModel):
    """Standardized content analysis results."""
    content_type: str = Field(..., description="Detected content type: document, image, text, spreadsheet")
    detected_language: Optional[str] = Field(None, description="Detected language code (e.g., 'en', 'es')")
    confidence_score: Optional[float] = Field(None, description="Confidence score for analysis (0.0-1.0)")
    file_category: Optional[str] = Field(None, description="General category of the file")
    summary: Optional[str] = Field(None, description="Brief summary of content")


class FileContentOutput(BaseModel):
    """
    Structured output for content processing.

    Provides both standardized analysis and file-type-specific data
    in a consistent format that can be serialized to JSON.
    """
    processing_info: ProcessingInfo = Field(..., description="Information about the processing operation")
    content_metadata: ContentAnalysis = Field(..., description="Metadata about the content type and analysis")

    # Standardized extraction results structure
    extraction_results: Optional[list] = Field(None, description="Results from each extraction method")

    def model_dump_for_json(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dictionary format.

        Returns:
            Dictionary suitable for JSON serialization
        """
        return self.model_dump(exclude_none=True)


class ContentProcessorError(IntakeError):
    """Exception for content processing errors."""

    def __init__(self, message: str, error_type: str = "content_processing_error", original_error: Optional[Exception] = None):
        super().__init__(message, error_type=error_type, original_error=original_error)