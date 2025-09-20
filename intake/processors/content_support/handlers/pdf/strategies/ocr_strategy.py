# intake/processors/content_support/handlers/pdf/strategies/ocr_strategy.py
# OCR-based PDF extraction strategy
# Uses unstructured library for text extraction with OCR

import logging
from pathlib import Path
from typing import Dict, Any

from .base import PDFExtractionStrategy, PDFExtractionError
from ....utilities import UnstructuredTextExtractor, TextQualityChecker


class OCRStrategy(PDFExtractionStrategy):
    """PDF extraction using OCR technology."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize OCR strategy.

        Args:
            config: Configuration with OCR settings
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)

        # Initialize text extractor with configured languages
        ocr_languages = config.get('ocr_languages', ['eng', 'spa'])
        self.text_extractor = UnstructuredTextExtractor(languages=ocr_languages)

        # Initialize quality checker
        self.quality_checker = TextQualityChecker()

    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract text from PDF using OCR.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            self.logger.info(f"Extracting text from {pdf_path} using OCR")

            # Extract text using unstructured
            extracted_text = self.text_extractor.extract_from_pdf(pdf_path)

            # Check text quality
            quality_stats = self.quality_checker.get_text_statistics(extracted_text)

            if not quality_stats['has_sufficient_quality']:
                self.logger.warning(
                    f"OCR text quality below threshold for {pdf_path}: "
                    f"length={quality_stats['length']}, "
                    f"alphanum_ratio={quality_stats['alphanum_ratio']:.2f}"
                )

            return {
                "text": extracted_text,
                "extraction_method": self.get_extraction_method(),
                "quality_stats": quality_stats,
                "has_sufficient_quality": quality_stats['has_sufficient_quality']
            }

        except Exception as e:
            raise PDFExtractionError(
                f"OCR extraction failed: {str(e)}",
                extraction_method=self.get_extraction_method(),
                original_error=e
            )

    def get_extraction_method(self) -> str:
        """Return the extraction method name."""
        return "OCR"

    def can_handle(self, pdf_path: Path) -> bool:
        """
        Check if OCR can handle this PDF.

        OCR can theoretically handle any PDF, but may not produce
        meaningful results for all types.
        """
        # Check if OCR is enabled in config
        if not self.config.get('enable_ocr_fallback', True):
            return False

        # OCR can attempt to handle any PDF
        return True