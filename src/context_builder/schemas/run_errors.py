"""Error taxonomy for pipeline runs.

Provides stable error codes for classifying document processing failures.
These codes should be used in summary.json and logs for consistent categorization.
"""

from enum import Enum


class RunErrorCode(str, Enum):
    """Stable error codes for document processing failures."""

    # Document classification issues
    DOC_NOT_SUPPORTED = "DOC_NOT_SUPPORTED"  # Doc type not in supported list
    CLASSIFY_LOW_CONF = "CLASSIFY_LOW_CONF"  # Classification confidence too low

    # Text extraction issues
    TEXT_MISSING = "TEXT_MISSING"  # No text could be extracted
    TEXT_UNREADABLE = "TEXT_UNREADABLE"  # Text quality too poor

    # Extraction issues
    EXTRACT_SCHEMA_INVALID = "EXTRACT_SCHEMA_INVALID"  # Schema validation failed
    EXTRACT_EXCEPTION = "EXTRACT_EXCEPTION"  # Exception during extraction

    # Output issues
    OUTPUT_WRITE_FAILED = "OUTPUT_WRITE_FAILED"  # Failed to write output file

    # Catch-all
    UNKNOWN_EXCEPTION = "UNKNOWN_EXCEPTION"  # Unexpected error


class RunFlag(str, Enum):
    """Flags for document processing (not errors, but notable conditions)."""

    VISION_RECOMMENDED = "VISION_RECOMMENDED"  # Document may benefit from vision OCR


class DocStatus(str, Enum):
    """Processing status for a document."""

    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


class TextSource(str, Enum):
    """Source of text extraction."""

    DI_TEXT = "di_text"  # Azure Document Intelligence
    VISION_OCR = "vision_ocr"  # OpenAI Vision OCR
    TESSERACT = "tesseract"  # Local Tesseract OCR
    RAW_TEXT = "raw_text"  # Direct text file
    NONE = "none"  # No text extracted


class TextReadability(str, Enum):
    """Text quality assessment."""

    GOOD = "good"
    WARN = "warn"
    BAD = "bad"
