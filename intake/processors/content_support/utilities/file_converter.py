# intake/processors/content_support/utilities/file_converter.py
# File conversion utilities for document processing
# Handles conversion between different file formats

import os
import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple


class DocumentConverter:
    """Converts documents between different formats."""

    def __init__(self):
        """Initialize the document converter."""
        self.logger = logging.getLogger(__name__)

    def convert_docx_to_pdf(self, docx_path: Path) -> Optional[Path]:
        """
        Convert a DOCX file to PDF.

        Args:
            docx_path: Path to the DOCX file

        Returns:
            Path to the converted PDF file, or None if conversion failed
        """
        try:
            # Lazy import of docx2pdf
            from docx2pdf import convert as docx_to_pdf

            # Create temporary PDF file
            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False
            ) as temp_file:
                temp_pdf_path = Path(temp_file.name)

            self.logger.info(f"Converting {docx_path} to PDF")

            # Convert DOCX to PDF
            docx_to_pdf(str(docx_path), str(temp_pdf_path))

            # Verify the conversion succeeded
            if temp_pdf_path.exists() and temp_pdf_path.stat().st_size > 0:
                self.logger.info(f"Successfully converted to {temp_pdf_path}")
                return temp_pdf_path
            else:
                self.logger.error("Conversion produced empty or missing file")
                if temp_pdf_path.exists():
                    temp_pdf_path.unlink()
                return None

        except Exception as e:
            self.logger.error(f"DOCX to PDF conversion failed: {str(e)}")
            return None

    def convert_doc_to_docx(self, doc_path: Path) -> Optional[Path]:
        """
        Convert a DOC file to DOCX.

        Args:
            doc_path: Path to the DOC file

        Returns:
            Path to the converted DOCX file, or None if conversion failed
        """
        try:
            # This would require a library like python-docx or LibreOffice
            # For now, returning None as DOC conversion is complex
            self.logger.warning("DOC to DOCX conversion not yet implemented")
            return None

        except Exception as e:
            self.logger.error(f"DOC to DOCX conversion failed: {str(e)}")
            return None

    def cleanup_temp_file(self, file_path: Path) -> bool:
        """
        Safely cleanup a temporary file.

        Args:
            file_path: Path to the file to delete

        Returns:
            True if cleanup succeeded
        """
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                self.logger.debug(f"Cleaned up temporary file: {file_path}")
                return True
            return False
        except Exception as e:
            self.logger.warning(f"Failed to cleanup {file_path}: {str(e)}")
            return False

    def get_file_info(self, file_path: Path) -> dict:
        """
        Get information about a file.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with file information
        """
        try:
            stat = file_path.stat()
            return {
                "name": file_path.name,
                "extension": file_path.suffix,
                "size_bytes": stat.st_size,
                "size_mb": stat.st_size / (1024 * 1024),
                "exists": True
            }
        except Exception:
            return {
                "name": file_path.name if file_path else "unknown",
                "extension": file_path.suffix if file_path else "",
                "size_bytes": 0,
                "size_mb": 0,
                "exists": False
            }