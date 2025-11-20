"""
Context Builder - A tool for processing and extracting text from documents.

This package provides OCR and vision-based text extraction capabilities
for building context from various document formats.
"""

__version__ = "0.1.0"

from context_builder.acquisition import AcquisitionFactory, DataAcquisition

__all__ = [
    "AcquisitionFactory",
    "DataAcquisition",
]
