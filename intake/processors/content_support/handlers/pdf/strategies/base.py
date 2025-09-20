# intake/processors/content_support/handlers/pdf/strategies/base.py
# Abstract base class for PDF extraction strategies
# Defines interface for different PDF processing methods

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional


class PDFExtractionStrategy(ABC):
    """Abstract base class for PDF extraction strategies."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the extraction strategy.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    @abstractmethod
    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract content from PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary containing extracted content and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    def get_extraction_method(self) -> str:
        """
        Get the name of this extraction method.

        Returns:
            String identifier for the extraction method
        """
        pass

    @abstractmethod
    def can_handle(self, pdf_path: Path) -> bool:
        """
        Check if this strategy can handle the given PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if this strategy can process the file
        """
        pass


class PDFExtractionError(Exception):
    """Exception raised when PDF extraction fails."""

    def __init__(
        self,
        message: str,
        extraction_method: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.extraction_method = extraction_method
        self.original_error = original_error