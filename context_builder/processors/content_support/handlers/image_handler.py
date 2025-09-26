# intake/processors/content_support/handlers/image_handler.py
# Handler for image files using extraction registry

import os
from pathlib import Path
from typing import Dict, Any, Optional

from .base import BaseContentHandler
from ..models import FileContentOutput, ContentProcessorError
from ..services import track_processing_time
from ..extractors import get_registry


class ImageContentHandler(BaseContentHandler):
    """Handler for image files using extraction registry."""

    SUPPORTED_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif',
        '.bmp', '.tiff', '.webp'
    }

    def __init__(self, *args, **kwargs):
        """Initialize image handler with extraction registry."""
        super().__init__(*args, **kwargs)
        self.registry = get_registry()

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported image type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """Process image file using configured extraction methods."""
        with track_processing_time("image_processing") as metrics:
            try:
                # Check file size
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self.logger.info(f"Processing image {file_path.name}: {file_size_mb:.2f}MB")

                # Get extraction results from all enabled methods
                extraction_results = self.registry.extract_from_file(file_path)

                # Check if we have any results
                if not extraction_results:
                    raise ContentProcessorError(
                        "No extraction methods available or enabled for images",
                        error_type="no_methods_available"
                    )

                # Determine overall status
                status = self._determine_overall_status(extraction_results)

                # Get list of methods used
                extracted_by = []
                skipped_methods = []
                failed_methods = []

                for result in extraction_results:
                    if result.status in ["success", "partial_success"]:
                        extracted_by.append(result.method)
                    elif result.status == "skipped":
                        skipped_methods.append(result.method)
                    else:  # error
                        failed_methods.append(result.method)

                # Create processing info
                processing_info = self.create_processing_info(
                    status=status,
                    processing_time=metrics.duration_seconds,
                    extracted_by=extracted_by,
                    skipped_methods=skipped_methods,
                    failed_methods=failed_methods
                )

                # Create content metadata
                content_metadata = self.create_content_metadata(
                    content_type="image",
                    file_category="image",
                    total_pages=1  # Images always have single page
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    extraction_results=[self._format_extraction_result(r) for r in extraction_results]
                )

            except Exception as e:
                self.logger.error(f"Image processing failed for {file_path}: {str(e)}")

                processing_info = self.create_processing_info(
                    status="error",
                    error_message=str(e),
                    processing_time=metrics.duration_seconds
                )

                content_metadata = self.create_content_metadata(
                    content_type="image",
                    file_category="image"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    extraction_results=[]
                )

    def _determine_overall_status(self, extraction_results) -> str:
        """
        Determine overall processing status from extraction results.

        Status hierarchy:
        - success: All enabled methods succeeded
        - partial_success: At least one method succeeded
                          OR some methods succeeded while others failed/skipped
        - error: All methods failed or were skipped
        """
        has_success = False
        has_partial = False
        has_error = False
        all_skipped = True

        for result in extraction_results:
            if result.status == "success":
                has_success = True
                all_skipped = False
            elif result.status == "partial_success":
                has_partial = True
                all_skipped = False
            elif result.status == "error":
                has_error = True
                all_skipped = False

        if all_skipped:
            return "error"

        if has_success and not has_error and not has_partial:
            return "success"
        elif has_success or has_partial:
            return "partial_success"
        else:
            return "error"

    def _format_extraction_result(self, result) -> Dict[str, Any]:
        """Format extraction result for output."""
        return {
            "method": result.method,
            "status": result.status,
            "pages": [self._format_page_result(page) for page in result.pages] if result.pages else [],
            "error": result.error
        }

    def _format_page_result(self, page) -> Dict[str, Any]:
        """Format page extraction result for output."""
        formatted = {
            "page_number": page.page_number,
            "status": page.status,
            "content": page.content,
            "quality_score": page.quality_score,
            "processing_time": page.processing_time
        }

        if page.error:
            formatted["error"] = page.error

        return formatted