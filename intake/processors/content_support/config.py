# intake/processors/content_support/config.py
# Centralized configuration management for content processing
# Handles all configuration settings, thresholds, and feature flags

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class HandlerConfig(BaseModel):
    """Configuration for individual content handlers."""

    enabled: bool = Field(True, description="Whether this handler is enabled")
    supported_extensions: List[str] = Field(
        default_factory=list,
        description="File extensions this handler supports"
    )
    max_file_size_mb: Optional[int] = Field(
        None,
        description="Maximum file size for this handler (overrides global)"
    )


class PDFConfig(BaseModel):
    """PDF-specific processing configuration."""

    use_vision_default: bool = Field(
        True,
        description="Use Vision API as default for PDFs (otherwise OCR first)"
    )
    large_file_threshold_mb: int = Field(
        50,
        description="Threshold for splitting large PDFs into pages (MB)"
    )
    max_pages_vision: int = Field(
        20,
        description="Maximum pages to process with Vision API"
    )
    ocr_as_fallback: bool = Field(
        True,
        description="Use OCR as fallback when Vision API fails"
    )
    ocr_languages: List[str] = Field(
        default_factory=lambda: ['eng', 'spa'],
        description="Languages for OCR processing"
    )


class AIConfig(BaseModel):
    """AI service configuration."""

    openai_api_key: Optional[str] = Field(
        None,
        description="OpenAI API key (will use env if not provided)"
    )
    default_model: str = Field(
        "gpt-4o",
        description="Default AI model to use"
    )
    max_tokens: int = Field(
        2048,
        description="Default maximum tokens for responses"
    )
    temperature: float = Field(
        0.1,
        description="Default temperature for generation"
    )
    max_retries: int = Field(
        3,
        description="Maximum retries for failed API calls"
    )
    timeout_seconds: int = Field(
        30,
        description="Timeout for API calls in seconds"
    )
    enable_vision_api: bool = Field(
        True,
        description="Enable OpenAI Vision API for image/document processing"
    )


class ProcessingConfig(BaseModel):
    """General processing configuration."""

    max_file_size_mb: int = Field(
        50,
        description="Global maximum file size to process in MB"
    )
    enable_async_processing: bool = Field(
        True,
        description="Enable asynchronous processing where possible"
    )
    connection_pool_size: int = Field(
        10,
        description="HTTP connection pool size for API calls"
    )
    graceful_degradation: bool = Field(
        True,
        description="Continue processing on errors with degraded output"
    )
    text_truncation_chars: int = Field(
        8000,
        description="Maximum characters before truncating text content"
    )
    json_truncation_chars: int = Field(
        6000,
        description="Maximum characters for JSON data before truncation"
    )


class HandlerRegistry(BaseModel):
    """Registry of available handlers and their configurations."""

    text: HandlerConfig = Field(
        default_factory=lambda: HandlerConfig(
            supported_extensions=['.txt', '.json', '.md', '.xml', '.html',
                                 '.py', '.js', '.css', '.yaml', '.yml']
        )
    )
    image: HandlerConfig = Field(
        default_factory=lambda: HandlerConfig(
            supported_extensions=['.jpg', '.jpeg', '.png', '.gif',
                                '.bmp', '.tiff', '.webp']
        )
    )
    pdf: HandlerConfig = Field(
        default_factory=lambda: HandlerConfig(
            supported_extensions=['.pdf']
        )
    )
    spreadsheet: HandlerConfig = Field(
        default_factory=lambda: HandlerConfig(
            supported_extensions=['.csv', '.xls', '.xlsx']
        )
    )
    document: HandlerConfig = Field(
        default_factory=lambda: HandlerConfig(
            supported_extensions=['.docx', '.doc']
        )
    )


class ContentProcessorConfig(BaseModel):
    """Main configuration for the content processor."""

    ai: AIConfig = Field(
        default_factory=AIConfig,
        description="AI service configuration"
    )
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig,
        description="General processing settings"
    )
    pdf: PDFConfig = Field(
        default_factory=PDFConfig,
        description="PDF-specific settings"
    )
    handlers: HandlerRegistry = Field(
        default_factory=HandlerRegistry,
        description="Handler registry and configurations"
    )

    def is_handler_enabled(self, handler_name: str) -> bool:
        """Check if a specific handler is enabled."""
        handler = getattr(self.handlers, handler_name, None)
        return handler.enabled if handler else False

    def get_supported_extensions(self) -> List[str]:
        """Get all supported file extensions from enabled handlers."""
        extensions = []
        for handler_name in ['text', 'image', 'pdf', 'spreadsheet', 'document']:
            handler = getattr(self.handlers, handler_name, None)
            if handler and handler.enabled:
                extensions.extend(handler.supported_extensions)
        return list(set(extensions))

    def get_handler_for_extension(self, extension: str) -> Optional[str]:
        """Find which handler supports a given file extension."""
        ext_lower = extension.lower()
        for handler_name in ['text', 'image', 'pdf', 'spreadsheet', 'document']:
            handler = getattr(self.handlers, handler_name, None)
            if handler and handler.enabled and ext_lower in handler.supported_extensions:
                return handler_name
        return None


# System file patterns that should be skipped
SYSTEM_FILES = {
    '.DS_Store',
    'Thumbs.db',
    'desktop.ini',
    '.gitignore',
    '.gitkeep'
}

# Text quality thresholds
TEXT_QUALITY_MIN_LENGTH = 50
TEXT_QUALITY_MIN_ALPHANUM_RATIO = 0.6