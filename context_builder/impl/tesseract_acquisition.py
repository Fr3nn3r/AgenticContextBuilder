"""Tesseract OCR implementation for data acquisition."""

import logging
import os
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from io import BytesIO

from context_builder.acquisition import (
    DataAcquisition,
    ConfigurationError,
    AcquisitionError,
    AcquisitionFactory,
)
from context_builder.utils.file_utils import get_file_metadata

logger = logging.getLogger(__name__)


class TesseractAcquisition(DataAcquisition):
    """Tesseract OCR implementation for document text extraction."""

    def __init__(self):
        """Initialize Tesseract acquisition."""
        super().__init__()

        # Configuration
        self.languages = ['eng']  # Default to English
        self.render_scale = 2.0  # Scale factor for PDF rendering
        self.max_pages = 50  # Maximum pages to process

        # Image preprocessing options
        self.enable_preprocessing = True
        self.deskew = True
        self.remove_noise = False
        self.enhance_contrast = True

        # Initialize libraries
        self.pytesseract = None
        self.Image = None
        self.ImageEnhance = None
        self.ImageOps = None
        self.pdf_renderer = None
        self.cv2 = None
        self.np = None

        # Validate and setup Tesseract
        self._setup_tesseract()

    def _setup_tesseract(self):
        """Setup Tesseract and validate requirements."""
        try:
            import pytesseract
            from PIL import Image, ImageEnhance, ImageOps
            self.pytesseract = pytesseract
            self.Image = Image
            self.ImageEnhance = ImageEnhance
            self.ImageOps = ImageOps

            # Try to import OpenCV for advanced preprocessing
            try:
                import cv2
                import numpy as np
                self.cv2 = cv2
                self.np = np
                logger.debug("OpenCV available for advanced preprocessing")
            except ImportError:
                logger.warning("OpenCV not available, some preprocessing features disabled")

            # On Windows, try to find Tesseract executable
            if platform.system() == 'Windows':
                if not self._find_tesseract_windows():
                    # Try to get from pytesseract-ocr package if available
                    try:
                        import pytesseract_ocr
                        # pytesseract-ocr includes bundled tesseract
                        logger.debug("Using pytesseract-ocr bundled Tesseract")
                    except ImportError:
                        raise ConfigurationError(
                            "Tesseract not found. Install either:\n"
                            "1. Tesseract-OCR: https://github.com/UB-Mannheim/tesseract/wiki\n"
                            "2. Or install pytesseract-ocr: pip install pytesseract-ocr"
                        )

            # Verify Tesseract is working
            try:
                version = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract version: {version}")
            except pytesseract.TesseractNotFoundError:
                raise ConfigurationError(
                    "Tesseract OCR not found. Please install Tesseract:\n"
                    "Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "Mac: brew install tesseract\n"
                    "Linux: apt-get install tesseract-ocr"
                )

            # Setup PDF support
            try:
                import pypdfium2 as pdfium
                self.pdf_renderer = pdfium
                logger.debug("PDF support enabled via pypdfium2")
            except ImportError:
                logger.warning("pypdfium2 not installed, PDF support disabled")

        except ImportError as e:
            raise ConfigurationError(f"Required packages not installed: {e}")

    def _find_tesseract_windows(self) -> bool:
        """
        Find and configure Tesseract path on Windows.

        Returns:
            True if Tesseract found and configured
        """
        # Common Windows installation paths
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\%s\AppData\Local\Tesseract-OCR\tesseract.exe' % os.environ.get('USERNAME', ''),
        ]

        # Check environment variable first
        if os.environ.get('TESSERACT_PATH'):
            tesseract_paths.insert(0, os.environ.get('TESSERACT_PATH'))

        for path in tesseract_paths:
            if os.path.exists(path):
                self.pytesseract.pytesseract.tesseract_cmd = path
                logger.debug(f"Found Tesseract at: {path}")
                return True

        return False


    def _preprocess_image(self, image) -> Any:
        """
        Preprocess image for better OCR accuracy.

        Args:
            image: PIL Image object

        Returns:
            Preprocessed PIL Image
        """
        if not self.enable_preprocessing:
            return image

        try:
            # Convert to grayscale if not already
            if image.mode != 'L':
                image = image.convert('L')

            # Enhance contrast
            if self.enhance_contrast:
                enhancer = self.ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.5)

            # Deskew using OpenCV if available
            if self.deskew and self.cv2 is not None and self.np is not None:
                # Convert PIL to OpenCV format
                img_array = self.np.array(image)

                # Apply deskewing
                coords = self.np.column_stack(self.np.where(img_array > 0))
                if len(coords) > 0:
                    angle = self.cv2.minAreaRect(coords)[-1]
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle

                    # Only deskew if angle is significant
                    if abs(angle) > 0.5:
                        (h, w) = img_array.shape[:2]
                        center = (w // 2, h // 2)
                        M = self.cv2.getRotationMatrix2D(center, angle, 1.0)
                        img_array = self.cv2.warpAffine(
                            img_array, M, (w, h),
                            flags=self.cv2.INTER_CUBIC,
                            borderMode=self.cv2.BORDER_REPLICATE
                        )
                        image = self.Image.fromarray(img_array)

            # Remove noise using OpenCV if available
            if self.remove_noise and self.cv2 is not None and self.np is not None:
                img_array = self.np.array(image)
                img_array = self.cv2.medianBlur(img_array, 3)
                image = self.Image.fromarray(img_array)

            return image

        except Exception as e:
            logger.warning(f"Image preprocessing failed: {e}, using original")
            return image

    def _calculate_confidence(self, data: Dict) -> float:
        """
        Calculate overall confidence score from Tesseract data.

        Args:
            data: Tesseract output data dictionary

        Returns:
            Confidence score between 0 and 1
        """
        try:
            confidences = [
                int(conf) for conf in data.get('conf', [])
                if conf != '-1' and str(conf).isdigit()
            ]

            if not confidences:
                return 0.0

            # Calculate weighted average (higher weight for more confident words)
            total_weight = sum(confidences)
            if total_weight == 0:
                return 0.0

            weighted_sum = sum(c * c for c in confidences)
            avg_confidence = weighted_sum / total_weight

            # Normalize to 0-1 range
            return min(avg_confidence / 100.0, 1.0)

        except Exception as e:
            logger.warning(f"Failed to calculate confidence: {e}")
            return 0.0

    def _extract_text_from_image(self, image, page_num: int = 1) -> Dict[str, Any]:
        """
        Extract text from a PIL Image using Tesseract.

        Args:
            image: PIL Image object
            page_num: Page number for multi-page documents

        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # Preprocess image
            processed_image = self._preprocess_image(image)

            # Configure Tesseract
            lang = '+'.join(self.languages)
            custom_config = r'--oem 3 --psm 6'  # Use LSTM OCR Engine, assume uniform block of text

            # Get text with confidence data
            data = self.pytesseract.image_to_data(
                processed_image,
                lang=lang,
                config=custom_config,
                output_type=self.pytesseract.Output.DICT
            )

            # Extract text
            text = self.pytesseract.image_to_string(
                processed_image,
                lang=lang,
                config=custom_config
            )

            # Calculate confidence
            confidence = self._calculate_confidence(data)

            return {
                "page_number": page_num,
                "text": text.strip(),
                "confidence": confidence,
                "languages": self.languages,
                "preprocessed": self.enable_preprocessing,
                "word_count": len(text.split()) if text else 0
            }

        except Exception as e:
            logger.error(f"OCR failed for page {page_num}: {e}")
            return {
                "page_number": page_num,
                "text": "",
                "confidence": 0.0,
                "error": str(e)
            }

    def _process_pdf_pages(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Process PDF pages one by one.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of extracted content for each page
        """
        if not self.pdf_renderer:
            raise ConfigurationError("PDF support not available (pypdfium2 not installed)")

        logger.info(f"Processing PDF with Tesseract OCR: {pdf_path}")

        pdf_doc = self.pdf_renderer.PdfDocument(pdf_path)
        results = []

        try:
            total_pages = len(pdf_doc)
            pages_to_process = min(total_pages, self.max_pages)

            if total_pages > self.max_pages:
                logger.warning(
                    f"PDF has {total_pages} pages, processing only first {self.max_pages}"
                )

            for page_index in range(pages_to_process):
                logger.debug(f"Processing page {page_index + 1}/{pages_to_process}")

                # Render page to image
                page = pdf_doc[page_index]
                mat = page.render(scale=self.render_scale)
                img = mat.to_pil()

                # Extract text
                page_result = self._extract_text_from_image(img, page_index + 1)
                results.append(page_result)

                # Free memory
                del img
                del mat

                logger.debug(
                    f"Page {page_index + 1} extracted: "
                    f"{page_result.get('word_count', 0)} words, "
                    f"confidence: {page_result.get('confidence', 0):.2f}"
                )

            return results

        finally:
            pdf_doc.close()

    def _process_implementation(self, filepath: Path) -> Dict[str, Any]:
        """
        Process file using Tesseract OCR.

        Args:
            filepath: Path to file to process

        Returns:
            Dictionary containing extracted text and metadata
        """
        logger.info(f"Processing with Tesseract OCR: {filepath}")

        # Get file metadata
        result = get_file_metadata(filepath)

        try:
            if filepath.suffix.lower() == '.pdf':
                # Process PDF pages
                pages = self._process_pdf_pages(filepath)
                result["total_pages"] = len(pages)
                result["pages"] = pages

                # Calculate overall confidence
                if pages:
                    confidences = [p.get('confidence', 0) for p in pages]
                    result["average_confidence"] = sum(confidences) / len(confidences)
                else:
                    result["average_confidence"] = 0.0

            else:
                # Process single image
                img = self.Image.open(filepath)
                page_result = self._extract_text_from_image(img, 1)

                result["total_pages"] = 1
                result["pages"] = [page_result]
                result["average_confidence"] = page_result.get('confidence', 0.0)

            # Add processing metadata
            result["processor"] = "tesseract"
            result["tesseract_languages"] = self.languages
            result["preprocessing_enabled"] = self.enable_preprocessing

            return result

        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            logger.error(error_msg)
            raise AcquisitionError(error_msg)


# Auto-register with factory
AcquisitionFactory.register("tesseract", TesseractAcquisition)