"""Evidence offset resolution for extraction results.

Post-processes extraction results to fill missing character offsets
by searching for text quotes in page content.
"""

from typing import List, Optional

from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    PageContent,
)
from context_builder.extraction.page_parser import find_text_position


def resolve_evidence_offsets(result: ExtractionResult) -> ExtractionResult:
    """
    Post-process extraction to fill missing char offsets.

    For each field with provenance where char_start=0 and char_end=0,
    attempt to locate the text_quote in the corresponding page.

    Updates:
    - provenance.char_start / char_end
    - provenance.match_quality
    - field.has_verified_evidence

    Args:
        result: ExtractionResult with fields that may have missing offsets

    Returns:
        The same ExtractionResult with updated offsets and evidence flags
    """
    pages_by_num = {p.page: p for p in result.pages}

    for field in result.fields:
        field_verified = False

        for prov in field.provenance:
            # Skip if already has valid offsets (non-zero)
            if prov.char_start > 0 or prov.char_end > 0:
                prov.match_quality = prov.match_quality or "exact"
                field_verified = True
                continue

            # Skip placeholder quotes like "[Component list extraction]"
            if prov.text_quote.startswith("[") and prov.text_quote.endswith("]"):
                prov.match_quality = "placeholder"
                continue

            # Try to find quote in the specified page
            page = pages_by_num.get(prov.page)
            if not page:
                prov.match_quality = "page_not_found"
                continue

            position = find_text_position(page.text, prov.text_quote)
            if position:
                prov.char_start = position[0]
                prov.char_end = position[1]
                prov.match_quality = "resolved"
                field_verified = True
            else:
                prov.match_quality = "not_found"

        field.has_verified_evidence = field_verified

    return result


def resolve_single_provenance(
    prov: FieldProvenance,
    pages: List[PageContent],
) -> FieldProvenance:
    """
    Resolve offsets for a single provenance entry.

    Searches the specified page first, then falls back to all pages.

    Args:
        prov: FieldProvenance to resolve
        pages: List of document pages

    Returns:
        Updated FieldProvenance with resolved offsets if found
    """
    # Skip if already has valid offsets
    if prov.char_start > 0 or prov.char_end > 0:
        prov.match_quality = prov.match_quality or "exact"
        return prov

    # Skip placeholder quotes
    if prov.text_quote.startswith("[") and prov.text_quote.endswith("]"):
        prov.match_quality = "placeholder"
        return prov

    pages_by_num = {p.page: p for p in pages}

    # Try specified page first
    if prov.page in pages_by_num:
        page = pages_by_num[prov.page]
        position = find_text_position(page.text, prov.text_quote)
        if position:
            prov.char_start = position[0]
            prov.char_end = position[1]
            prov.match_quality = "resolved"
            return prov

    # Fall back to searching all pages
    for page in pages:
        if page.page == prov.page:
            continue  # Already tried this page
        position = find_text_position(page.text, prov.text_quote)
        if position:
            # Update page number if found on different page
            prov.page = page.page
            prov.char_start = position[0]
            prov.char_end = position[1]
            prov.match_quality = "resolved_different_page"
            return prov

    prov.match_quality = "not_found"
    return prov
