"""
Document field extraction module.

Provides doc-type-specific extractors with provenance tracking,
normalization, validation, and quality gates.
"""

from context_builder.extraction.base import (
    FieldExtractor,
    ExtractorFactory,
    CandidateSpan,
    generate_run_id,
)
from context_builder.extraction.spec_loader import (
    DocTypeSpec,
    FieldRule,
    load_spec,
    get_spec,
    list_available_specs,
)
from context_builder.extraction.page_parser import (
    ParsedPage,
    parse_azure_di_markdown,
    find_text_position,
    find_quote_in_pages,
)
from context_builder.extraction.normalizers import (
    normalize_uppercase_trim,
    normalize_date_to_iso,
    normalize_plate,
    get_normalizer,
    get_validator,
)

# Import extractors to trigger auto-registration with ExtractorFactory
from context_builder.extraction import extractors

__all__ = [
    # Base classes
    "FieldExtractor",
    "ExtractorFactory",
    "CandidateSpan",
    "generate_run_id",
    # Spec loading
    "DocTypeSpec",
    "FieldRule",
    "load_spec",
    "get_spec",
    "list_available_specs",
    # Page parsing
    "ParsedPage",
    "parse_azure_di_markdown",
    "find_text_position",
    "find_quote_in_pages",
    # Normalizers
    "normalize_uppercase_trim",
    "normalize_date_to_iso",
    "normalize_plate",
    "get_normalizer",
    "get_validator",
]
