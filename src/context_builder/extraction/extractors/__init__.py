"""
Document field extractors.

Importing this module registers all extractors with the ExtractorFactory.
"""

# Import to trigger auto-registration of generic extractor for all doc types
from context_builder.extraction.extractors.generic import GenericFieldExtractor

# Import custom extractors (these override generic registration for specific doc types)
from context_builder.extraction.extractors.nsa_guarantee import NsaGuaranteeExtractor
from context_builder.extraction.extractors.nsa_cost_estimate import NsaCostEstimateExtractor
from context_builder.extraction.extractors.nsa_service_history import NsaServiceHistoryExtractor

# Register custom extractors (override generic for specific doc types)
from context_builder.extraction.base import ExtractorFactory

ExtractorFactory.register("nsa_guarantee", NsaGuaranteeExtractor)
ExtractorFactory.register("cost_estimate", NsaCostEstimateExtractor)
ExtractorFactory.register("service_history", NsaServiceHistoryExtractor)

__all__ = ["GenericFieldExtractor", "NsaGuaranteeExtractor", "NsaCostEstimateExtractor", "NsaServiceHistoryExtractor"]
