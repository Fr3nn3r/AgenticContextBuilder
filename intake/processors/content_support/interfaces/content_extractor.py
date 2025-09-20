# intake/processors/content_support/interfaces/content_extractor.py
# Abstract interface for content extraction strategies
# Defines common interface for different extraction methods (OCR, Vision API, etc.)

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List


class ContentExtractorInterface(ABC):
    """Abstract interface for content extraction strategies."""

    @abstractmethod
    def can_extract(self, file_path: Path) -> bool:
        """
        Check if this extractor can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if this extractor can handle the file
        """
        pass

    @abstractmethod
    def extract_text(self, file_path: Path) -> str:
        """
        Extract text content from a file.

        Args:
            file_path: Path to the file

        Returns:
            Extracted text content

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    def extract_structured_data(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract structured data from a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary containing structured data

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    def get_extraction_method(self) -> str:
        """Get the name of the extraction method."""
        pass


class ExtractionError(Exception):
    """Exception raised when content extraction fails."""

    def __init__(self, message: str, file_path: Optional[Path] = None, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.file_path = file_path
        self.original_error = original_error