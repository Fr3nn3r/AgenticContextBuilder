# intake/processors/content_support/handlers/pdf/strategies/vision_strategy.py
# Vision API-based PDF extraction strategy
# Renders PDF pages as images and uses Vision API for analysis

import io
import base64
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import PDFExtractionStrategy, PDFExtractionError
from .page_processor import PageProcessor


class VisionAPIStrategy(PDFExtractionStrategy):
    """PDF extraction using Vision API on rendered pages."""

    def __init__(self, config: Dict[str, Any], ai_service, prompt_manager, response_parser):
        """
        Initialize Vision API strategy.

        Args:
            config: Configuration with Vision API settings
            ai_service: AI service for Vision API calls
            prompt_manager: Prompt manager for templates
            response_parser: Response parser for JSON extraction
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.ai_service = ai_service
        self.prompt_manager = prompt_manager
        self.response_parser = response_parser
        self.page_processor = PageProcessor()

    def extract(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract content from PDF using Vision API.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary with extracted content from all pages
        """
        try:
            # Check file size to determine processing method
            file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
            large_threshold = self.config.get('pdf_large_file_threshold_mb', 50)

            if file_size_mb > large_threshold:
                self.logger.info(f"Large PDF ({file_size_mb:.2f}MB), using page-by-page processing")
                return self._process_large_pdf(pdf_path)
            else:
                return self._process_standard_pdf(pdf_path)

        except Exception as e:
            raise PDFExtractionError(
                f"Vision API extraction failed: {str(e)}",
                extraction_method=self.get_extraction_method(),
                original_error=e
            )

    def _process_standard_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Process standard-sized PDF."""
        results = []

        # Lazy import pdfium
        import pypdfium2 as pdfium

        pdf_doc = pdfium.PdfDocument(pdf_path)
        prompt_config = self.prompt_manager.get_prompt("universal_document")
        prompt_version = self.prompt_manager.get_active_version("universal_document") or "1.0.0"

        # Process pages up to limit
        max_pages = min(
            self.config.get('pdf_max_pages_vision', 20),
            len(pdf_doc)
        )

        for i in range(max_pages):
            page_result = self._process_single_page(
                pdf_doc[i],
                i + 1,
                prompt_config
            )
            if page_result:
                results.append(page_result)

        return {
            "pages": results,
            "extraction_method": self.get_extraction_method(),
            "total_pages": len(pdf_doc),
            "processed_pages": len(results)
        }

    def _process_large_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """Process large PDF with error recovery."""
        results = []
        all_pages_processed = True

        # Lazy import pdfium
        import pypdfium2 as pdfium

        pdf_doc = pdfium.PdfDocument(pdf_path)
        prompt_config = self.prompt_manager.get_prompt("universal_document")

        max_pages = min(
            self.config.get('pdf_max_pages_vision', 20),
            len(pdf_doc)
        )

        self.logger.info(f"Processing {max_pages} pages from {len(pdf_doc)} total")

        for i in range(max_pages):
            try:
                page_result = self._process_single_page(
                    pdf_doc[i],
                    i + 1,
                    prompt_config
                )
                if page_result:
                    results.append(page_result)
                    self.logger.debug(f"Processed page {i+1}/{max_pages}")

            except Exception as e:
                self.logger.error(f"Failed to process page {i+1}: {str(e)}")
                all_pages_processed = False
                # Continue processing other pages instead of failing completely
                results.append({
                    "page": i + 1,
                    "error": str(e),
                    "analysis": None
                })

        return {
            "pages": results,
            "extraction_method": f"{self.get_extraction_method()} (Page-by-Page)",
            "total_pages": len(pdf_doc),
            "processed_pages": len(results),
            "all_pages_successful": all_pages_processed
        }

    def _process_single_page(self, page, page_number: int, prompt_config) -> Optional[Dict[str, Any]]:
        """Process a single PDF page."""
        try:
            # Render page to image
            image_base64 = self.page_processor.render_page_to_base64(page)

            # Get prompt template
            prompt_template = self.prompt_manager.get_prompt_template("universal_document")

            # Analyze with Vision API
            ai_response = self.ai_service.analyze_content(
                prompt_template,
                image_base64=image_base64,
                model=prompt_config.model,
                max_tokens=prompt_config.max_tokens,
                temperature=prompt_config.temperature
            )

            # Parse response if JSON expected
            if prompt_config.output_format == "json":
                parsed_data, _ = self.response_parser.parse_ai_response(
                    ai_response,
                    expected_format="json"
                )
                return {
                    "page": page_number,
                    "analysis": parsed_data if parsed_data else ai_response
                }
            else:
                return {
                    "page": page_number,
                    "analysis": ai_response
                }

        except Exception as e:
            self.logger.error(f"Failed to process page {page_number}: {str(e)}")
            raise

    def get_extraction_method(self) -> str:
        """Return the extraction method name."""
        return "Vision API"

    def can_handle(self, pdf_path: Path) -> bool:
        """Check if Vision API can handle this PDF."""
        # Check if Vision API is enabled
        if not self.config.get('enable_vision_api', True):
            return False

        # Check if AI service is available
        if not self.ai_service or not self.ai_service.provider.is_available():
            return False

        # Vision API can handle any PDF that exists
        return pdf_path.exists()