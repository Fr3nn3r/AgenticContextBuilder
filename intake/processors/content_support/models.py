# intake/processors/content_support/models.py
# Pydantic models for content processing configuration and outputs
# Defines type-safe configuration and structured output formats

from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class PromptVersionConfig(BaseModel):
    """
    Configuration for a single version of a prompt.

    Contains the template and parameters for a specific version.
    """
    template: str = Field(..., description="The prompt template text")
    model: str = Field(default="gpt-4o", description="AI model to use for this prompt")
    max_tokens: int = Field(default=2048, description="Maximum tokens for response")
    temperature: float = Field(default=0.1, description="Temperature for response generation")
    description: Optional[str] = Field(None, description="Human-readable description of prompt purpose")
    output_format: Optional[str] = Field(None, description="Expected output format: 'json' or 'text' (default)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional model parameters")


class PromptConfig(BaseModel):
    """
    Configuration for a versioned AI prompt.

    Stores multiple versions of a prompt with an active version indicator.
    """
    active_version: str = Field(..., description="Currently active version to use")
    versions: Dict[str, PromptVersionConfig] = Field(..., description="All available versions of this prompt")

    @field_validator('active_version')
    @classmethod
    def validate_active_version(cls, v, info):
        """Validate that active version follows semantic versioning format."""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Active version must follow semantic versioning format (X.Y.Z)')
        return v

    @field_validator('versions')
    @classmethod
    def validate_versions(cls, v):
        """Validate that all version keys follow semantic versioning."""
        import re
        for version_key in v.keys():
            if not re.match(r'^\d+\.\d+\.\d+$', version_key):
                raise ValueError(f'Version key {version_key} must follow semantic versioning format (X.Y.Z)')
        return v


class ContentConfig(BaseModel):
    """
    Configuration for the Content Processor.

    Controls content extraction models, processing options, file type handlers,
    and prompt management settings.
    """
    # API Configuration
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key (will use dotenv if not provided)")
    enable_vision_api: bool = Field(True, description="Enable OpenAI Vision API for image/document processing")
    enable_ocr_fallback: bool = Field(True, description="Enable OCR fallback when Vision API fails")
    pdf_use_vision_default: bool = Field(True, description="Use Vision API as default for PDFs (otherwise OCR first)")

    # Processing Configuration
    max_retries: int = Field(3, description="Maximum retries for failed API calls")
    timeout_seconds: int = Field(30, description="Timeout for API calls in seconds")
    max_file_size_mb: int = Field(50, description="Maximum file size to process in MB")
    pdf_large_file_threshold_mb: int = Field(50, description="Threshold for splitting large PDFs into pages (MB)")
    pdf_max_pages_vision: int = Field(20, description="Maximum pages to process with Vision API")

    # File Type Handlers
    file_type_handlers: Dict[str, bool] = Field(
        default_factory=lambda: {
            'text': True,
            'image': True,
            'pdf': True,
            'sheet': True,
            'document': True
        },
        description="Enable/disable specific file type handlers"
    )

    # Prompt Management
    prompts: Dict[str, PromptConfig] = Field(
        default_factory=dict,
        description="Versioned prompts for different processing tasks"
    )

    # Performance Configuration
    enable_async_processing: bool = Field(True, description="Enable asynchronous processing where possible")
    connection_pool_size: int = Field(10, description="HTTP connection pool size for API calls")

    # OCR Configuration
    ocr_languages: List[str] = Field(
        default_factory=lambda: ['eng', 'spa'],
        description="Languages for OCR processing (e.g., ['eng', 'spa'] for English and Spanish)"
    )
    ocr_as_fallback: bool = Field(True, description="Use OCR as fallback when Vision API fails")

    def get_default_prompts(self) -> Dict[str, PromptConfig]:
        """
        Get default prompt configurations if none are provided.

        Returns:
            Dictionary of default prompt configurations
        """
        return {
            "universal_document": PromptConfig(
                active_version="2.0.0",
                versions={
                    "1.0.0": PromptVersionConfig(
                        template="""You are an AI assistant for universal document and image processing.
For the image provided:

Describe the content and any visible details as clearly as possible.

Identify the type of image or document, and include this as a field in your output.""",
                        model="gpt-4o",
                        max_tokens=2048,
                        description="Universal prompt for document and image analysis - plain text output"
                    ),
                    "2.0.0": PromptVersionConfig(
                        template="""You are an AI assistant for universal document and image processing.
For the image provided:

If the image is a document (receipt, ticket, invoice, form, etc.), extract all visible information in structured JSON format (include key fields, tables, totals, dates, etc.).

If the image is a photo (e.g., a vehicle, damaged property, or objects), describe the content and any visible details as clearly as possible.

In all cases, identify the type of image or document, and include this as a field in your output.""",
                        model="gpt-4o",
                        max_tokens=2048,
                        description="Universal prompt for document and image analysis - JSON output",
                        output_format="json"
                    )
                }
            ),
            "text_analysis": PromptConfig(
                active_version="2.0.0",
                versions={
                    "1.0.0": PromptVersionConfig(
                        template="""Analyze the following text content and provide:
1. A brief summary (1-2 sentences)
2. Key topics or themes identified
3. Document type (if identifiable)
4. Language detected
5. Any structured data found (dates, numbers, entities)

Text content:
{content}""",
                        model="gpt-4o",
                        max_tokens=1024,
                        description="Analysis prompt for text-based files - plain text output"
                    ),
                    "2.0.0": PromptVersionConfig(
                        template="""Analyze the following text content and return a JSON object with this exact structure:
{{
  "summary": "Brief 1-2 sentence summary",
  "document_type": "Type of document (e.g., email, report, article, code, etc.)",
  "language": "ISO 639-1 language code (e.g., en, es, fr)",
  "key_topics": ["topic1", "topic2", ...],
  "entities": {{
    "people": ["name1", "name2", ...],
    "organizations": ["org1", "org2", ...],
    "locations": ["location1", "location2", ...],
    "dates": ["date1", "date2", ...],
    "numbers": ["significant numbers or amounts", ...]
  }},
  "sentiment": "positive/negative/neutral",
  "technical_level": "low/medium/high",
  "word_count": <number>,
  "has_code": true/false,
  "has_tables": true/false,
  "metadata": {{
    "title": "extracted title if present",
    "author": "extracted author if identifiable",
    "date_created": "extracted creation date if found"
  }}
}}

IMPORTANT: Return ONLY valid JSON, no additional text or explanations.

Text content to analyze:
{content}""",
                        model="gpt-4o",
                        max_tokens=1500,
                        temperature=0.1,
                        description="JSON-structured analysis prompt for text-based files",
                        output_format="json"
                    )
                }
            ),
            "spreadsheet_analysis": PromptConfig(
                active_version="2.0.0",
                versions={
                    "1.0.0": PromptVersionConfig(
                        template="""Analyze this spreadsheet data and provide:
1. Data structure summary
2. Column types and purposes
3. Key patterns or insights
4. Data quality assessment
5. Potential use cases

Data:
{content}""",
                        model="gpt-4o",
                        max_tokens=1024,
                        description="Analysis prompt for spreadsheet files - plain text output"
                    ),
                    "2.0.0": PromptVersionConfig(
                        template="""Analyze the following spreadsheet data and return a JSON object with this exact structure:
{{
  "summary": "Brief description of the spreadsheet content and purpose",
  "dataset_type": "Type of data (e.g., financial, inventory, customer_data, time_series, etc.)",
  "columns": [
    {{
      "name": "column_name",
      "data_type": "string/number/date/boolean/mixed",
      "purpose": "Description of what this column represents",
      "has_nulls": true/false,
      "unique_values_count": <number if applicable>,
      "sample_values": ["val1", "val2", "val3"]
    }}
  ],
  "statistics": {{
    "row_count": <number>,
    "column_count": <number>,
    "empty_cells_percentage": <number>,
    "data_completeness": "complete/mostly_complete/sparse"
  }},
  "insights": {{
    "key_patterns": ["pattern1", "pattern2", ...],
    "anomalies": ["anomaly1", "anomaly2", ...],
    "relationships": ["Column A correlates with Column B", ...],
    "trends": ["trend1", "trend2", ...]
  }},
  "data_quality": {{
    "overall_quality": "high/medium/low",
    "issues": ["issue1", "issue2", ...],
    "recommendations": ["recommendation1", "recommendation2", ...]
  }},
  "use_cases": ["Potential use case 1", "Potential use case 2", ...],
  "metadata": {{
    "has_headers": true/false,
    "delimiter": "comma/tab/semicolon/etc",
    "encoding_issues": true/false,
    "date_format": "detected date format if applicable"
  }}
}}

IMPORTANT: Return ONLY valid JSON, no additional text or explanations.

Spreadsheet data to analyze:
{content}""",
                        model="gpt-4o",
                        max_tokens=2000,
                        temperature=0.1,
                        description="JSON-structured analysis prompt for spreadsheet files",
                        output_format="json"
                    )
                }
            )
        }


class ProcessingInfo(BaseModel):
    """Information about the processing operation."""
    processor_version: str = Field(..., description="Version of the content processor")
    ai_model_used: Optional[str] = Field(None, description="AI model used for processing")
    processing_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="When processing occurred")
    prompt_version: Optional[str] = Field(None, description="Version of prompt used")
    processing_status: str = Field(..., description="Status: success, partial_success, or error")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    processing_time_seconds: Optional[float] = Field(None, description="Time taken for processing")
    extraction_method: Optional[str] = Field(None, description="Method used for content extraction: OCR, Vision API, Direct, etc.")


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

    # Common fields for all file types
    data_content: Optional[Dict[str, Any]] = Field(None, description="Structured JSON analysis from AI")

    # Type-specific raw content fields
    data_text_content: Optional[str] = Field(None, description="Original text content (text files)")
    data_spreadsheet_content: Optional[str] = Field(None, description="Original spreadsheet data as JSON (spreadsheet files)")
    data_image_content: Optional[str] = Field(None, description="Base64 encoded image or description (image files)")
    data_document_content: Optional[str] = Field(None, description="Extracted document content (document files)")

    def model_dump_for_json(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dictionary format.

        Returns:
            Dictionary suitable for JSON serialization
        """
        return self.model_dump(exclude_none=True)


class ContentProcessorError(Exception):
    """Custom exception for content processing errors."""

    def __init__(self, message: str, error_type: str = "processing_error", original_error: Optional[Exception] = None):
        self.message = message
        self.error_type = error_type
        self.original_error = original_error
        super().__init__(self.message)