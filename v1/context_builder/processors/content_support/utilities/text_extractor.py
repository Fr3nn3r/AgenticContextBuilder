# intake/processors/content_support/utilities/text_extractor.py
# Text extraction utilities using unstructured library
# Handles OCR and text quality assessment

import logging
from pathlib import Path
from typing import List, Optional

from ..config import TEXT_QUALITY_MIN_LENGTH, TEXT_QUALITY_MIN_ALPHANUM_RATIO


class UnstructuredTextExtractor:
    """Wrapper for unstructured library text extraction."""

    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initialize text extractor.

        Args:
            languages: List of languages for OCR (e.g., ['eng', 'spa'])
        """
        self.languages = languages or ['eng', 'spa']
        self.logger = logging.getLogger(__name__)

    def extract_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from PDF using unstructured library.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content

        Raises:
            Exception: If PDF processing fails
        """
        try:
            # Lazy import of unstructured
            from unstructured.partition.pdf import partition_pdf

            self.logger.info(f"Extracting text from PDF: {pdf_path}")

            # Partition the PDF into elements
            elements = partition_pdf(
                str(pdf_path),
                languages=self.languages
            )

            # Extract text from all elements
            text_content = []
            for element in elements:
                if hasattr(element, 'text') and element.text:
                    text_content.append(element.text)

            extracted_text = '\n'.join(text_content)
            self.logger.debug(f"Extracted {len(extracted_text)} characters from PDF")

            return extracted_text

        except Exception as e:
            self.logger.error(f"PDF text extraction failed: {str(e)}")
            raise Exception(f"PDF text extraction failed: {str(e)}")

    def extract_from_image(self, image_path: Path) -> str:
        """
        Extract text from image using OCR.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text content

        Raises:
            Exception: If OCR processing fails
        """
        try:
            # Lazy import of unstructured
            from unstructured.partition.image import partition_image

            self.logger.info(f"Extracting text from image: {image_path}")

            # Extract text from image
            elements = partition_image(
                str(image_path),
                languages=self.languages
            )

            text_content = []
            for element in elements:
                if hasattr(element, 'text') and element.text:
                    text_content.append(element.text)

            extracted_text = '\n'.join(text_content)
            self.logger.debug(f"Extracted {len(extracted_text)} characters from image")

            return extracted_text

        except Exception as e:
            self.logger.error(f"Image text extraction failed: {str(e)}")
            raise Exception(f"Image text extraction failed: {str(e)}")


class TextQualityChecker:
    """Assesses quality and meaningfulness of extracted text."""

    def __init__(
        self,
        min_length: int = TEXT_QUALITY_MIN_LENGTH,
        min_alphanum_ratio: float = TEXT_QUALITY_MIN_ALPHANUM_RATIO
    ):
        """
        Initialize text quality checker.

        Args:
            min_length: Minimum text length to be considered meaningful
            min_alphanum_ratio: Minimum ratio of alphanumeric characters
        """
        self.min_length = min_length
        self.min_alphanum_ratio = min_alphanum_ratio
        self.logger = logging.getLogger(__name__)

    def has_sufficient_quality(self, text: str) -> bool:
        """
        Check if text has sufficient quality.

        Args:
            text: Text to check

        Returns:
            True if text meets quality thresholds
        """
        if not text:
            return False

        clean_text = text.strip()

        # Check minimum length
        if len(clean_text) < self.min_length:
            self.logger.debug(f"Text too short: {len(clean_text)} < {self.min_length}")
            return False

        # Check alphanumeric ratio
        alphanum_chars = sum(c.isalnum() for c in clean_text)
        total_chars = len(clean_text)

        if total_chars == 0:
            return False

        ratio = alphanum_chars / total_chars

        if ratio < self.min_alphanum_ratio:
            self.logger.debug(
                f"Low alphanumeric ratio: {ratio:.2f} < {self.min_alphanum_ratio}"
            )
            return False

        return True

    def get_text_statistics(self, text: str) -> dict:
        """
        Get detailed statistics about text quality.

        Args:
            text: Text to analyze

        Returns:
            Dictionary with text statistics
        """
        if not text:
            return {
                "length": 0,
                "alphanum_ratio": 0.0,
                "word_count": 0,
                "line_count": 0,
                "has_sufficient_quality": False
            }

        clean_text = text.strip()
        alphanum_chars = sum(c.isalnum() for c in clean_text)
        total_chars = len(clean_text)

        return {
            "length": total_chars,
            "alphanum_ratio": alphanum_chars / total_chars if total_chars > 0 else 0,
            "word_count": len(clean_text.split()),
            "line_count": len(clean_text.split('\n')),
            "has_sufficient_quality": self.has_sufficient_quality(text)
        }