# intake/processors/content_support/handlers/pdf/pdf_handler.py
# Main PDF content handler that coordinates extraction strategies
# Manages strategy selection and fallback mechanisms

import os
from pathlib import Path
from typing import Dict, Any, Optional

from ..base import BaseContentHandler
from ...models import FileContentOutput, ContentProcessorError
from ...services import track_processing_time
from .strategies import VisionAPIStrategy, OCRStrategy


class PDFContentHandler(BaseContentHandler):
    """Handler for PDF files with multiple extraction strategies."""

    SUPPORTED_EXTENSIONS = {'.pdf'}

    def __init__(self, *args, **kwargs):
        """Initialize PDF handler with extraction strategies."""
        super().__init__(*args, **kwargs)

        # Initialize strategies
        self.vision_strategy = VisionAPIStrategy(
            self.config,
            self.ai_service,
            self.prompt_provider,
            self.response_parser
        )
        self.ocr_strategy = OCRStrategy(self.config)

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a PDF."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """Process PDF using configured strategy with fallback."""
        with track_processing_time("pdf_processing") as metrics:
            try:
                # Check file size
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self.logger.info(f"Processing PDF {file_path.name}: {file_size_mb:.2f}MB")

                # Determine primary strategy
                use_vision_default = self.config.get('pdf_use_vision_default', True)

                if use_vision_default:
                    # Try Vision API first
                    result = self._try_vision_with_fallback(file_path, metrics)
                else:
                    # Try OCR first
                    result = self._try_ocr_with_fallback(file_path, metrics)

                return result

            except Exception as e:
                self.logger.error(f"PDF processing failed for {file_path}: {str(e)}")

                processing_info = self.create_processing_info(
                    status="error",
                    error_message=str(e),
                    processing_time=metrics.duration_seconds
                )

                content_metadata = self.create_content_metadata(
                    content_type="document",
                    file_category="pdf"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata
                )

    def _try_vision_with_fallback(self, file_path: Path, metrics) -> FileContentOutput:
        """Try Vision API with OCR fallback."""
        try:
            # Attempt Vision API extraction
            if self.vision_strategy.can_handle(file_path):
                self.logger.info(f"Using Vision API extraction for {file_path}")
                extraction_result = self.vision_strategy.extract(file_path)
                return self._process_extraction_result(
                    file_path,
                    extraction_result,
                    "Vision API",
                    metrics
                )
        except Exception as e:
            self.logger.warning(f"Vision API failed for {file_path}: {e}")

            # Fallback to OCR if enabled
            if self.config.get('ocr_as_fallback', True):
                self.logger.info(f"Falling back to OCR for {file_path}")
                return self._try_ocr_extraction(file_path, metrics, is_fallback=True)
            else:
                raise

    def _try_ocr_with_fallback(self, file_path: Path, metrics) -> FileContentOutput:
        """Try OCR with Vision API fallback."""
        try:
            # Attempt OCR extraction
            if self.ocr_strategy.can_handle(file_path):
                self.logger.info(f"Using OCR extraction for {file_path}")
                extraction_result = self.ocr_strategy.extract(file_path)

                # Check if OCR produced meaningful text
                if extraction_result.get('has_sufficient_quality', False):
                    return self._process_extraction_result(
                        file_path,
                        extraction_result,
                        "OCR",
                        metrics
                    )
                else:
                    self.logger.info(f"OCR text not meaningful for {file_path}, trying Vision API")

        except Exception as e:
            self.logger.warning(f"OCR failed for {file_path}: {e}")

        # Fallback to Vision API
        if self.vision_strategy.can_handle(file_path):
            self.logger.info(f"Using Vision API extraction for {file_path}")
            extraction_result = self.vision_strategy.extract(file_path)
            return self._process_extraction_result(
                file_path,
                extraction_result,
                "Vision API",
                metrics
            )
        else:
            raise ContentProcessorError(
                "No extraction strategy available for PDF",
                error_type="no_strategy_available"
            )

    def _try_ocr_extraction(self, file_path: Path, metrics, is_fallback: bool = False) -> FileContentOutput:
        """Try OCR extraction."""
        try:
            extraction_result = self.ocr_strategy.extract(file_path)
            extraction_method = "OCR (Fallback)" if is_fallback else "OCR"
            return self._process_extraction_result(
                file_path,
                extraction_result,
                extraction_method,
                metrics
            )
        except Exception as e:
            self.logger.error(f"OCR extraction failed: {str(e)}")

            # Return error result
            processing_info = self.create_processing_info(
                status="error",
                error_message=f"Both Vision API and OCR failed: {str(e)}",
                processing_time=metrics.duration_seconds,
                extraction_method="Failed"
            )

            content_metadata = self.create_content_metadata(
                content_type="document",
                file_category="pdf",
                summary="Failed to extract content from PDF"
            )

            return FileContentOutput(
                processing_info=processing_info,
                content_metadata=content_metadata
            )

    def _process_extraction_result(
        self,
        file_path: Path,
        extraction_result: Dict[str, Any],
        extraction_method: str,
        metrics
    ) -> FileContentOutput:
        """Process extraction result and apply AI analysis."""

        # Handle Vision API results (pages)
        if "pages" in extraction_result:
            return self._process_vision_result(
                file_path,
                extraction_result,
                extraction_method,
                metrics
            )

        # Handle OCR results (text)
        elif "text" in extraction_result:
            return self._process_text_result(
                file_path,
                extraction_result["text"],
                extraction_method,
                metrics
            )

        else:
            raise ContentProcessorError(
                "Invalid extraction result format",
                error_type="invalid_result"
            )

    def _process_vision_result(
        self,
        file_path: Path,
        extraction_result: Dict[str, Any],
        extraction_method: str,
        metrics
    ) -> FileContentOutput:
        """Process Vision API extraction results."""

        pages_info = extraction_result.get("pages", [])
        total_pages = extraction_result.get("total_pages", len(pages_info))
        processed_pages = extraction_result.get("processed_pages", len(pages_info))

        # Create summary
        summary = f"PDF processed via {extraction_method} ({processed_pages}/{total_pages} pages)"

        # Get prompt configuration for metadata
        prompt_config = self.prompt_provider.get_prompt("universal-document")
        prompt_version = self.prompt_provider.get_active_version("universal-document") or "1.0.0"

        content_metadata = self.create_content_metadata(
            content_type="document",
            file_category="pdf",
            summary=summary
        )

        processing_info = self.create_processing_info(
            status="success",
            ai_model=prompt_config.model if prompt_config else "gpt-4o",
            prompt_version=prompt_version,
            processing_time=metrics.duration_seconds,
            extraction_method=extraction_method
        )

        return FileContentOutput(
            processing_info=processing_info,
            content_metadata=content_metadata,
            content_data={
                "pages": pages_info,
                "_extraction_method": extraction_method
            }
        )

    def _process_text_result(
        self,
        file_path: Path,
        text_content: str,
        extraction_method: str,
        metrics
    ) -> FileContentOutput:
        """Process OCR text extraction results with AI analysis."""

        # Truncate if necessary
        max_chars = self.config.get('text_truncation_chars', 8000)
        truncated = False
        original_text = text_content

        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n[... content truncated ...]"
            truncated = True

        # Get AI analysis
        prompt_name = "text-analysis"
        prompt_config = self.prompt_provider.get_prompt(prompt_name)
        prompt_version = self.prompt_provider.get_active_version(prompt_name) or "1.0.0"

        prompt_template = self.prompt_provider.get_prompt_template(
            prompt_name,
            content=text_content
        )

        ai_response = self.ai_service.analyze_content(
            prompt_template,
            model=prompt_config.model,
            max_tokens=prompt_config.max_tokens,
            temperature=prompt_config.temperature
        )

        # Parse response
        parsed_data, summary = self.response_parser.parse_ai_response(
            ai_response,
            expected_format=prompt_config.output_format or "text"
        )

        # Create metadata
        content_metadata = self.create_content_metadata(
            content_type="document",
            file_category="pdf",
            summary=summary if parsed_data else f"PDF processed via {extraction_method}",
            detected_language=parsed_data.get('language') if isinstance(parsed_data, dict) else None
        )

        processing_info = self.create_processing_info(
            status="success",
            ai_model=prompt_config.model,
            prompt_version=prompt_version,
            processing_time=metrics.duration_seconds,
            extraction_method=extraction_method
        )

        # Structure content data
        if parsed_data:
            content_data = parsed_data
            content_data['_extraction_method'] = extraction_method
            if truncated:
                content_data['_truncated'] = True
        else:
            content_data = {
                "text": original_text[:max_chars],
                "analysis": ai_response,
                "_extraction_method": extraction_method,
                "_truncated": truncated
            }

        return FileContentOutput(
            processing_info=processing_info,
            content_metadata=content_metadata,
            content_data=content_data
        )