# intake/processors/content.py
# Content enrichment processor for file ingestion
# Extracts semantic content from files using various methods and techniques

import os
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from dotenv import load_dotenv

from .base import BaseProcessor, ProcessingError
from .content_support.models import FileContentOutput, ContentProcessorError, ProcessingInfo, ContentAnalysis
from .content_support.prompt_manager import PromptManager
from .content_support.config import ContentProcessorConfig, AIConfig
from .content_support.factory import create_content_handler, get_all_handlers
from .content_support.services import AIAnalysisService, OpenAIProvider
from .content_support.handlers import BaseContentHandler


class ContentProcessor(BaseProcessor):
    """
    AI-powered context enrichment processor.

    Extracts semantic content from files using AI models, OCR, and Vision APIs.
    Supports text files, images, PDFs, spreadsheets, and office documents.
    Uses versioned prompts and provides structured output with error handling.
    """

    VERSION = "1.0.0"
    DESCRIPTION = "Content enrichment using AI models, OCR, and other extraction methods"
    SUPPORTED_EXTENSIONS = ["*"]  # Supports all file types via handlers

    def __init__(self, config: Optional[Union[Dict[str, Any], ContentProcessorConfig]] = None):
        """
        Initialize the content processor.

        Args:
            config: Configuration dictionary or ContentConfig object
        """
        # Load environment variables from .env file
        load_dotenv()

        # Convert configuration to typed config
        if isinstance(config, dict):
            self.typed_config = ContentProcessorConfig(**config)
        elif isinstance(config, ContentProcessorConfig):
            self.typed_config = config
        else:
            self.typed_config = ContentProcessorConfig()

        # Initialize base class
        super().__init__(self.typed_config.model_dump())

        # Set up logging
        self.logger = logging.getLogger(__name__)

        # Initialize AI service
        self.ai_service = self._initialize_ai_service()

        # Initialize prompt manager with default or configured prompts
        self.prompt_manager = self._initialize_prompt_manager()

        # Initialize file type handlers
        self.handlers: List[BaseContentHandler] = self._initialize_handlers()

        self.logger.info(f"ContentProcessor initialized with {len(self.handlers)} handlers")

    def _initialize_ai_service(self) -> Optional[AIAnalysisService]:
        """
        Initialize AI service with configured provider.

        Returns:
            AI service or None if not available
        """
        try:
            # Create OpenAI provider with AI configuration
            ai_config = self.typed_config.ai
            provider = OpenAIProvider(ai_config)

            if provider.is_available():
                ai_service = AIAnalysisService(provider)
                self.logger.info("AI service initialized successfully")
                return ai_service
            else:
                self.logger.warning(
                    "AI provider not available. AI processing will be disabled. "
                    "Set OPENAI_API_KEY in environment or provide in config."
                )
                return None
        except Exception as e:
            self.logger.error(f"Failed to initialize AI service: {e}")
            return None

    def _initialize_prompt_manager(self) -> PromptManager:
        """
        Initialize prompt manager with configured or default prompts.

        Returns:
            PromptManager instance
        """
        # Get default prompts from ContentConfig in models.py
        from .content_support.models import ContentConfig

        # Create temporary ContentConfig to get default prompts
        temp_config = ContentConfig()
        default_prompts = temp_config.get_default_prompts()

        # Use default prompts for now since config structure changed
        prompt_manager = PromptManager(default_prompts)

        self.logger.info(f"Prompt manager initialized with {len(prompt_manager.prompts)} prompts")
        return prompt_manager

    def _initialize_handlers(self) -> List[BaseContentHandler]:
        """
        Initialize file type handlers based on configuration.

        Returns:
            List of enabled handlers
        """
        if not self.ai_service:
            self.logger.warning("AI service not available, handlers will have limited functionality")
            return []

        # Use factory to create all enabled handlers
        handlers = get_all_handlers(
            ai_service=self.ai_service,
            prompt_manager=self.prompt_manager,
            config=self.typed_config
        )

        self.logger.info(f"Initialized {len(handlers)} handlers")
        return handlers

    def process_file(self, file_path: Path, existing_metadata: Optional[Union[Dict[str, Any], None]] = None) -> Dict[str, Any]:
        """
        Process a file and extract AI-powered context.

        Args:
            file_path: Path to the file to process
            existing_metadata: Any metadata from previous processors

        Returns:
            Dictionary containing file context data

        Raises:
            ProcessingError: If processing fails critically
        """
        self.logger.info(f"Processing file: {file_path}")
        start_time = time.time()

        try:
            # Skip system files that don't need content processing
            if file_path.name in ['.DS_Store', 'Thumbs.db', 'desktop.ini']:
                self.logger.debug(f"Skipping system file: {file_path}")
                # Return minimal metadata for system files
                return {
                    'file_content': self._create_system_file_content(
                        file_path.name,
                        time.time() - start_time
                    )
                }

            # Check file size limits
            if not self._check_file_size(file_path):
                raise ContentProcessorError(
                    f"File size exceeds limit of {self.typed_config.processing.max_file_size_mb}MB",
                    error_type="file_too_large"
                )

            # Find appropriate handler
            handler = self._find_handler(file_path)
            if not handler:
                raise ContentProcessorError(
                    f"No handler available for file type: {file_path.suffix}",
                    error_type="unsupported_file_type"
                )

            # Process file with handler
            result = handler.process(file_path, existing_metadata)

            processing_time = time.time() - start_time
            self.logger.info(
                f"Successfully processed {file_path} in {processing_time:.2f}s "
                f"using {handler.__class__.__name__}"
            )

            # Return as dictionary for pipeline compatibility
            return {'file_content': result.model_dump()}

        except ContentProcessorError as e:
            # Log and re-raise our custom errors
            self.logger.error(f"Content processing failed for {file_path}: {e.message}")

            # Return error context instead of raising if configured for graceful degradation
            if self.typed_config.processing.graceful_degradation:
                error_content = self._create_error_content(str(e), time.time() - start_time)
                return {'file_content': error_content}
            else:
                raise ProcessingError(
                    f"Content processing failed: {e.message}",
                    file_path=file_path,
                    processor_name=self.name
                )

        except Exception as e:
            # Handle unexpected errors
            processing_time = time.time() - start_time
            self.logger.error(f"Unexpected error processing {file_path}: {e}")

            error_content = self._create_error_content(str(e), processing_time)
            return {'file_content': error_content}

    def _check_file_size(self, file_path: Path) -> bool:
        """
        Check if file size is within limits.

        Args:
            file_path: Path to check

        Returns:
            True if file size is acceptable, False otherwise
        """
        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            return file_size_mb <= self.typed_config.processing.max_file_size_mb
        except Exception:
            return False

    def _find_handler(self, file_path: Path) -> Optional[BaseContentHandler]:
        """
        Find the appropriate handler for a file.

        Args:
            file_path: Path to the file

        Returns:
            Handler that can process the file, or None if no handler found
        """
        for handler in self.handlers:
            if handler.can_handle(file_path):
                return handler
        return None

    def _create_system_file_content(self, filename: str, processing_time: float) -> Dict[str, Any]:
        """
        Create content for system files that should be skipped.

        Args:
            filename: Name of the system file
            processing_time: Time spent processing

        Returns:
            Minimal content dictionary for system files
        """

        processing_info = ProcessingInfo(
            processor_version=self.VERSION,
            processing_status="success",
            processing_time_seconds=processing_time
        )

        content_metadata = ContentAnalysis(
            content_type="system",
            file_category="system_file",
            summary=f"System file ({filename}) - skipped"
        )

        system_output = FileContentOutput(
            processing_info=processing_info,
            content_metadata=content_metadata,
            data_text_content=f"System file {filename} was skipped"
        )

        return system_output.model_dump()

    def _create_error_content(self, error_message: str, processing_time: float) -> Dict[str, Any]:
        """
        Create error content output.

        Args:
            error_message: Error description
            processing_time: Time spent processing

        Returns:
            Error content dictionary
        """

        processing_info = ProcessingInfo(
            processor_version=self.VERSION,
            processing_status="error",
            error_message=error_message,
            processing_time_seconds=processing_time
        )

        content_metadata = ContentAnalysis(
            content_type="unknown",
            file_category="processing_failed"
        )

        error_output = FileContentOutput(
            processing_info=processing_info,
            content_metadata=content_metadata  # Fixed field name
        )

        return error_output.model_dump()

    def validate_config(self) -> bool:
        """
        Validate the processor configuration.

        Returns:
            True if configuration is valid
        """
        try:
            # Validate base configuration
            if not isinstance(self.typed_config, ContentProcessorConfig):
                return False

            # Check if at least one handler is enabled
            enabled_handlers = [
                self.typed_config.is_handler_enabled(name)
                for name in ['text', 'image', 'pdf', 'spreadsheet', 'document']
            ]
            if not any(enabled_handlers):
                self.logger.error("No file type handlers are enabled")
                return False

            # Validate prompts
            prompt_validation = self.prompt_manager.validate_all_prompts()
            if not all(prompt_validation.values()):
                invalid_prompts = [name for name, valid in prompt_validation.items() if not valid]
                self.logger.error(f"Invalid prompts found: {invalid_prompts}")
                return False

            # Check AI service if vision API is enabled
            if self.typed_config.ai.enable_vision_api and not self.ai_service:
                self.logger.warning("Vision API enabled but AI service not available")

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def get_processor_info(self) -> Dict[str, Any]:
        """
        Get detailed information about this processor.

        Returns:
            Dictionary with processor information
        """
        base_info = super().get_processor_info()

        # Add AI-specific information
        ai_info = {
            'ai_service_available': self.ai_service is not None,
            'enabled_handlers': [
                handler.__class__.__name__
                for handler in self.handlers
            ],
            'total_prompts': len(self.prompt_manager.prompts),
            'prompt_versions': self.prompt_manager.list_prompts(),
            'configuration': {
                'enable_vision_api': self.typed_config.ai.enable_vision_api,
                'enable_ocr_fallback': self.typed_config.pdf.ocr_as_fallback,
                'max_file_size_mb': self.typed_config.processing.max_file_size_mb,
                'max_retries': self.typed_config.ai.max_retries,
                'timeout_seconds': self.typed_config.ai.timeout_seconds
            }
        }

        base_info.update(ai_info)
        return base_info

    def get_supported_file_types(self) -> List[str]:
        """
        Get list of supported file extensions.

        Returns:
            List of file extensions that can be processed
        """
        supported_extensions = set()
        for handler in self.handlers:
            if hasattr(handler, 'SUPPORTED_EXTENSIONS'):
                supported_extensions.update(handler.SUPPORTED_EXTENSIONS)
        return sorted(list(supported_extensions))

    def test_ai_connectivity(self) -> Dict[str, Any]:
        """
        Test AI service connectivity and capabilities.

        Returns:
            Dictionary with test results
        """
        results = {
            'ai_service_available': self.ai_service is not None,
            'api_key_configured': bool(
                self.typed_config.ai.openai_api_key or
                os.getenv('OPENAI_API_KEY')
            ),
            'vision_api_enabled': self.typed_config.ai.enable_vision_api,
            'test_request_successful': False,
            'error_message': None
        }

        if self.ai_service:
            try:
                # Simple test request
                response = self.ai_service.analyze_content(
                    prompt="Hello",
                    model="gpt-3.5-turbo",
                    max_tokens=5
                )
                results['test_request_successful'] = True
                results['test_response'] = response
            except Exception as e:
                results['error_message'] = str(e)

        return results