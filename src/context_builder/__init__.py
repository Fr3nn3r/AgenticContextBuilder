"""
Context Builder - A tool for processing and extracting text from documents.

This package provides OCR and vision-based text extraction capabilities
for building context from various document formats.
"""

__version__ = "0.1.0"

from context_builder.ingestion import IngestionFactory, DataIngestion


def get_version() -> str:
    """Get ContextBuilder version from pyproject.toml.

    Returns:
        Version string, or "unknown" if not available.
    """
    try:
        from importlib.metadata import version

        return version("context-builder")
    except Exception:
        return __version__


__all__ = [
    "IngestionFactory",
    "DataIngestion",
    "get_version",
]
