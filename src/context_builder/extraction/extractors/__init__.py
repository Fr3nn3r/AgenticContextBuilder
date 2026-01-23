"""
Document field extractors.

Importing this module registers all extractors with the ExtractorFactory.
"""

# Import to trigger auto-registration of generic extractor for all doc types
from context_builder.extraction.extractors.generic import GenericFieldExtractor

# Import custom extractors (these override generic registration for specific doc types)
from context_builder.extraction.extractors.nsa_guarantee import NsaGuaranteeExtractor

# Register custom extractors (override generic for specific doc types)
from context_builder.extraction.base import ExtractorFactory

ExtractorFactory.register("nsa_guarantee", NsaGuaranteeExtractor)

__all__ = ["GenericFieldExtractor", "NsaGuaranteeExtractor"]
