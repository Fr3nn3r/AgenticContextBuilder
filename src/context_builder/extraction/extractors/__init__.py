"""
Document field extractors.

Importing this module registers all extractors with the ExtractorFactory.
"""

# Import to trigger auto-registration
from context_builder.extraction.extractors.generic import GenericFieldExtractor

__all__ = ["GenericFieldExtractor"]
