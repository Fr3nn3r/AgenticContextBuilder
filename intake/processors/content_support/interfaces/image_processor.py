# intake/processors/content_support/interfaces/image_processor.py
# Abstract interface for image processing operations
# Defines common interface for image manipulation and conversion

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Any
from io import BytesIO


class ImageProcessorInterface(ABC):
    """Abstract interface for image processing operations."""

    @abstractmethod
    def load_image(self, file_path: Path) -> Any:
        """
        Load an image from file.

        Args:
            file_path: Path to the image file

        Returns:
            Image object (implementation-specific)

        Raises:
            ImageProcessingError: If loading fails
        """
        pass

    @abstractmethod
    def resize_image(self, image: Any, size: Tuple[int, int]) -> Any:
        """
        Resize an image to specified dimensions.

        Args:
            image: Image object
            size: Target size as (width, height)

        Returns:
            Resized image object
        """
        pass

    @abstractmethod
    def convert_to_base64(self, image: Any, format: str = "PNG") -> str:
        """
        Convert image to base64 string.

        Args:
            image: Image object
            format: Output format (PNG, JPEG, etc.)

        Returns:
            Base64-encoded string
        """
        pass

    @abstractmethod
    def render_pdf_page(self, pdf_path: Path, page_number: int, scale: float = 2.0) -> Any:
        """
        Render a PDF page as an image.

        Args:
            pdf_path: Path to PDF file
            page_number: Page number to render (0-based)
            scale: Rendering scale factor

        Returns:
            Rendered page as image object
        """
        pass


class ImageProcessingError(Exception):
    """Exception raised when image processing fails."""

    def __init__(self, message: str, file_path: Optional[Path] = None):
        super().__init__(message)
        self.message = message
        self.file_path = file_path