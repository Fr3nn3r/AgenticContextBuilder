# intake/processors/content_support/handlers/base.py
# Abstract base class for content handlers
# Defines the interface and common functionality for all file type handlers

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

from ..models import FileContentOutput, ProcessingInfo, ContentAnalysis
from ....services import PromptProvider
from ..services import AIAnalysisService, ResponseParser, track_processing_time


class BaseContentHandler(ABC):
    """
    Abstract base class for file type handlers.

    Each handler implements specific logic for processing a particular
    file type using AI models and returning structured context.
    """

    def __init__(
        self,
        ai_service: AIAnalysisService,
        prompt_provider: PromptProvider,
        response_parser: ResponseParser,
        config: Dict[str, Any]
    ):
        """
        Initialize the handler with dependencies.

        Args:
            ai_service: AI analysis service for content processing
            prompt_provider: Prompt provider instance
            response_parser: Response parsing service
            config: Handler-specific configuration
        """
        self.ai_service = ai_service
        self.prompt_provider = prompt_provider
        self.response_parser = response_parser
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """
        Determine if this handler can process the given file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if this handler can process the file, False otherwise
        """
        pass

    @abstractmethod
    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """
        Process the file and extract AI-powered context.

        Args:
            file_path: Path to the file to process
            existing_metadata: Any existing metadata from previous processors

        Returns:
            FileContentOutput containing the processing results

        Raises:
            ContentProcessorError: If processing fails
        """
        pass

    def create_processing_info(
        self,
        status: str,
        ai_model: Optional[str] = None,
        prompt_version: Optional[str] = None,
        error_message: Optional[str] = None,
        processing_time: Optional[float] = None,
        extraction_method: Optional[str] = None,
        extracted_by: Optional[list] = None,
        skipped_methods: Optional[list] = None,
        failed_methods: Optional[list] = None
    ) -> ProcessingInfo:
        """
        Create standardized processing information.

        Args:
            status: Processing status (success, partial_success, error)
            ai_model: AI model used for processing
            prompt_version: Version of prompt used
            error_message: Error message if processing failed
            processing_time: Time taken for processing in seconds
            extraction_method: Method used for content extraction

        Returns:
            ProcessingInfo object
        """
        return ProcessingInfo(
            processor_version="1.0.0",
            processing_status=status,
            error_message=error_message,
            processing_time_seconds=processing_time,
            extracted_by=extracted_by,
            skipped_methods=skipped_methods,
            failed_methods=failed_methods
        )

    def create_content_metadata(
        self,
        content_type: str,
        file_category: str,
        summary: Optional[str] = None,
        detected_language: Optional[str] = None,
        **kwargs  # Accept additional parameters for flexibility
    ) -> ContentAnalysis:
        """
        Create standardized content metadata.

        Args:
            content_type: Type of content (text, image, document, etc.)
            file_category: Category of file
            summary: Content summary
            detected_language: Detected language of content

        Returns:
            ContentAnalysis object
        """
        return ContentAnalysis(
            content_type=content_type,
            file_category=file_category,
            summary=summary,
            detected_language=detected_language
        )