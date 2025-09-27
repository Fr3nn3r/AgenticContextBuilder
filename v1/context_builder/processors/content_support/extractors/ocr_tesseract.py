# intake/processors/content_support/extractors/ocr_tesseract.py
# OCR extraction strategy using Tesseract

import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import os

from .base import ExtractionStrategy, PageExtractionResult

logger = logging.getLogger(__name__)


class OCRTesseractStrategy(ExtractionStrategy):
    """OCR extraction using Tesseract."""

    @property
    def name(self) -> str:
        return "ocr_tesseract"

    @property
    def supports_file_types(self) -> list:
        return ["pdf", "image"]

    @property
    def supports_batch_processing(self) -> bool:
        return False

    @property
    def requires_api_key(self) -> bool:
        return False

    @property
    def max_file_size_mb(self) -> float:
        return float(self.config.get('max_file_size_mb', 100.0))

    def _setup(self) -> None:
        """Setup Tesseract configuration."""
        self.languages = self.config.get('languages', ['eng'])
        self.quality_threshold = self.config.get('quality_threshold', 0.6)
        self.pdf_renderer = None
        self.pytesseract = None
        self.Image = None

    def validate_requirements(self) -> Tuple[bool, Optional[str]]:
        """Check if Tesseract and required libraries are available."""
        try:
            import pytesseract
            from PIL import Image
            self.pytesseract = pytesseract
            self.Image = Image

            # On Windows, set the Tesseract path if not in PATH
            import platform
            if platform.system() == 'Windows':
                import os
                if not os.environ.get('TESSERACT_CMD'):
                    # Try common Windows installation paths
                    tesseract_paths = [
                        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                    ]
                    for path in tesseract_paths:
                        if os.path.exists(path):
                            pytesseract.pytesseract.tesseract_cmd = path
                            break

            # Check if Tesseract is installed
            try:
                pytesseract.get_tesseract_version()
            except pytesseract.pytesseract.TesseractNotFoundError:
                return False, "Tesseract OCR is not installed or not in PATH"

            # For PDF support, check pypdfium2
            if "pdf" in self.supports_file_types:
                try:
                    import pypdfium2 as pdfium
                    self.pdf_renderer = pdfium
                except ImportError:
                    logger.warning("pypdfium2 not available, PDF OCR support disabled")
                    # Don't fail completely, just can't handle PDFs
                    pass

            return True, None

        except ImportError as e:
            return False, f"Required libraries not installed: {str(e)}"

    def get_total_pages(self, file_path: Path) -> int:
        """Get total number of pages in the file."""
        if file_path.suffix.lower() == '.pdf':
            if not self.pdf_renderer:
                raise Exception("PDF support not available (pypdfium2 not installed)")

            pdf_doc = self.pdf_renderer.PdfDocument(file_path)
            page_count = len(pdf_doc)
            pdf_doc.close()
            return page_count
        else:
            # Images have single page
            return 1

    def extract_page(self, file_path: Path, page_num: int, total_pages: int) -> PageExtractionResult:
        """Extract text from a single page using OCR."""
        try:
            if file_path.suffix.lower() == '.pdf':
                text = self._extract_pdf_page(file_path, page_num - 1)  # 0-indexed
            else:
                # For images, only process if page_num == 1
                if page_num != 1:
                    return PageExtractionResult(
                        page_number=page_num,
                        status="error",
                        error="Invalid page number for image file"
                    )
                text = self._extract_image(file_path)

            # Check text quality
            quality_score = self._calculate_text_quality(text)

            if quality_score < self.quality_threshold or not text.strip():
                return PageExtractionResult(
                    page_number=page_num,
                    status="unreadable_content",
                    content=None,
                    quality_score=0,
                    error="No readable text found or quality too low"
                )

            return PageExtractionResult(
                page_number=page_num,
                status="success",
                content={
                    "text": text,
                    "confidence": quality_score,
                    "languages": self.languages
                },
                quality_score=quality_score
            )

        except Exception as e:
            logger.error(f"OCR extraction failed for page {page_num}: {str(e)}")
            return PageExtractionResult(
                page_number=page_num,
                status="error",
                error=str(e)
            )

    def _extract_pdf_page(self, file_path: Path, page_index: int) -> str:
        """Extract text from a PDF page."""
        if not self.pdf_renderer:
            raise Exception("PDF support not available")

        pdf_doc = self.pdf_renderer.PdfDocument(file_path)
        try:
            page = pdf_doc[page_index]

            # Render page to image
            scale = 2.0  # 2x scale for better OCR quality
            mat = page.render(scale=scale)
            img = mat.to_pil()

            # Perform OCR
            lang = '+'.join(self.languages)
            text = self.pytesseract.image_to_string(img, lang=lang)

            return text

        finally:
            pdf_doc.close()

    def _extract_image(self, file_path: Path) -> str:
        """Extract text from an image file."""
        img = self.Image.open(file_path)
        lang = '+'.join(self.languages)
        text = self.pytesseract.image_to_string(img, lang=lang)
        return text

    def _calculate_text_quality(self, text: str) -> float:
        """
        Calculate text quality score based on various metrics.

        Returns:
            Quality score between 0 and 1
        """
        if not text or not text.strip():
            return 0.0

        clean_text = text.strip()

        # Check minimum length
        if len(clean_text) < 50:
            return 0.2

        # Calculate alphanumeric ratio
        alphanum_chars = sum(c.isalnum() or c.isspace() for c in clean_text)
        total_chars = len(clean_text)
        alphanum_ratio = alphanum_chars / total_chars if total_chars > 0 else 0

        # Check for word diversity
        words = clean_text.split()
        unique_words = set(words)
        word_diversity = len(unique_words) / len(words) if words else 0

        # Check for average word length (too short might be gibberish)
        avg_word_length = sum(len(w) for w in words) / len(words) if words else 0

        # Calculate quality score
        quality = 0.0

        # Alphanumeric ratio (40% weight)
        quality += alphanum_ratio * 0.4

        # Word diversity (30% weight)
        quality += min(word_diversity * 1.5, 1.0) * 0.3

        # Average word length (30% weight)
        # Ideal average word length is around 4-6 characters
        if avg_word_length >= 2 and avg_word_length <= 10:
            word_length_score = 1.0 - abs(5 - avg_word_length) / 5
            quality += word_length_score * 0.3
        elif avg_word_length > 10:
            quality += 0.1  # Long words might be concatenated gibberish

        return min(quality, 1.0)