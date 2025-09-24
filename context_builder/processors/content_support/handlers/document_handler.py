# intake/processors/content_support/handlers/document_handler.py
# Handler for document files (docx, doc) via conversion
# Converts documents to processable format and extracts content

from pathlib import Path
from typing import Dict, Any, Optional, List

from .base import BaseContentHandler
from ..models import FileContentOutput, ContentProcessorError
from ..services import track_processing_time
from ..utilities import DocumentConverter


class DocumentContentHandler(BaseContentHandler):
    """Handler for document files via conversion to images."""

    SUPPORTED_EXTENSIONS = {'.docx', '.doc'}

    def __init__(self, *args, **kwargs):
        """Initialize with document converter."""
        super().__init__(*args, **kwargs)
        self.converter = DocumentConverter()

    def can_handle(self, file_path: Path) -> bool:
        """Check if file is a supported document type."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def process(
        self,
        file_path: Path,
        existing_metadata: Optional[Dict[str, Any]] = None
    ) -> FileContentOutput:
        """Process document by converting to images and using Vision API."""
        with track_processing_time("document_processing") as metrics:
            try:
                # Convert and analyze document
                results = self._convert_and_analyze_document(file_path)

                # Create output
                content_metadata = self.create_content_metadata(
                    content_type="document",
                    file_category="office_document",
                    summary="Document processed via Vision API conversion"
                )

                processing_info = self.create_processing_info(
                    status="success" if results else "error",
                    ai_model="gpt-4o",
                    processing_time=metrics.duration_seconds,
                    error_message="Conversion failed" if not results else None,
                    extraction_method="Document Conversion + Vision API"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata,
                    content_data={"document_analysis": results} if results else None,
                    data_document_content=str(results) if results else None
                )

            except Exception as e:
                self.logger.error(f"Document processing failed for {file_path}: {str(e)}")

                processing_info = self.create_processing_info(
                    status="error",
                    error_message=str(e),
                    processing_time=metrics.duration_seconds
                )

                content_metadata = self.create_content_metadata(
                    content_type="document",
                    file_category="office_document"
                )

                return FileContentOutput(
                    processing_info=processing_info,
                    content_metadata=content_metadata
                )

    def _convert_and_analyze_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """Convert document to images and analyze with Vision API."""
        temp_pdf = None

        try:
            if file_path.suffix.lower() == '.docx':
                # Convert DOCX to PDF
                temp_pdf = self.converter.convert_docx_to_pdf(file_path)

                if temp_pdf and temp_pdf.exists():
                    # Process PDF with Vision API
                    # Import PDF handler to reuse its Vision API logic
                    from .pdf.pdf_handler import PDFContentHandler

                    pdf_handler = PDFContentHandler(
                        self.ai_service,
                        self.prompt_manager,
                        self.response_parser,
                        self.config
                    )

                    # Process the converted PDF
                    result = pdf_handler.process(temp_pdf)

                    # Extract pages data if available
                    if result.content_data and isinstance(result.content_data, dict):
                        return result.content_data.get("pages", [])

            elif file_path.suffix.lower() == '.doc':
                # DOC files need special handling
                self.logger.warning("DOC file conversion not yet implemented")
                return [{"error": "DOC format not yet supported"}]

            return [{"error": "Unsupported document format or conversion failed"}]

        except Exception as e:
            self.logger.error(f"Document conversion failed: {e}")
            return [{"error": f"Document conversion failed: {str(e)}"}]

        finally:
            # Clean up temporary file
            if temp_pdf:
                self.converter.cleanup_temp_file(temp_pdf)