"""Evidence offset resolution for extraction results.

Post-processes extraction results to fill missing character offsets
by searching for text quotes in page content.

Also backfills provenance for fields with values but no evidence by:
1. Searching Azure DI tables for exact cell matches (most precise)
2. Falling back to page text search
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    PageContent,
    CellReference,
)
from context_builder.extraction.page_parser import find_text_position


def _normalize_for_search(value: str) -> str:
    """Normalize a value for fuzzy searching.

    Handles:
    - Swiss number formats (27'000 -> 27000)
    - German number formats (27.000 -> 27000)
    - Currency symbols
    - Extra whitespace
    """
    if not value:
        return ""

    # Remove Swiss thousand separators (apostrophe)
    result = re.sub(r"(\d)'(\d)", r"\1\2", value)
    # Remove German thousand separators (dot followed by 3 digits)
    result = re.sub(r"(\d)\.(\d{3})(?=\D|$)", r"\1\2", result)
    # Normalize whitespace
    result = re.sub(r"\s+", " ", result).strip()

    return result


def _find_value_in_azure_di_tables(
    azure_di: Dict[str, Any],
    value: str,
) -> Optional[Tuple[int, int, int, CellReference, str]]:
    """Search for a value in Azure DI table cells.

    Args:
        azure_di: Azure DI output dictionary
        value: Value to search for

    Returns:
        Tuple of (page, char_start, char_end, cell_ref, matched_content) or None
    """
    if not azure_di or not value:
        return None

    raw_output = azure_di.get("raw_azure_di_output", {})
    tables = raw_output.get("tables", [])

    if not tables:
        return None

    # Normalize the search value
    search_value = _normalize_for_search(value.lower())

    for table_idx, table in enumerate(tables):
        cells = table.get("cells", [])

        for cell in cells:
            cell_content = cell.get("content", "")
            if not cell_content:
                continue

            # Normalize cell content for comparison
            normalized_content = _normalize_for_search(cell_content.lower())

            # Check for exact match or contained match
            if search_value == normalized_content or search_value in normalized_content:
                # Get cell's character span
                spans = cell.get("spans", [])
                if spans:
                    span = spans[0]
                    char_start = span.get("offset", 0)
                    char_end = char_start + span.get("length", len(cell_content))
                else:
                    char_start = 0
                    char_end = 0

                # Get page number from bounding regions
                bounding_regions = cell.get("boundingRegions", [])
                page = bounding_regions[0].get("pageNumber", 1) if bounding_regions else 1

                cell_ref = CellReference(
                    table_index=table_idx,
                    row_index=cell.get("rowIndex", 0),
                    column_index=cell.get("columnIndex", 0),
                )

                return (page, char_start, char_end, cell_ref, cell_content)

    return None


def _find_value_in_page_text(
    pages: List[PageContent],
    value: str,
) -> Optional[Tuple[int, int, int, str]]:
    """Search for a value in page text content.

    Uses multiple matching strategies:
    1. Exact match
    2. Case-insensitive match
    3. Normalized numbers match (Swiss/German formats)

    Args:
        pages: List of page content
        value: Value to search for

    Returns:
        Tuple of (page, char_start, char_end, matched_text) or None
    """
    if not pages or not value:
        return None

    # Try exact match first
    for page in pages:
        pos = find_text_position(page.text, value)
        if pos:
            return (page.page, pos[0], pos[1], value)

    # Try normalized search (handles Swiss 27'000 and German 27.000 formats)
    normalized_value = _normalize_for_search(value)

    for page in pages:
        # Normalize page text
        normalized_text = _normalize_for_search(page.text)

        # Find in normalized text
        pos = normalized_text.lower().find(normalized_value.lower())
        if pos >= 0:
            # Try to find the original text around this position
            # Note: position may be slightly off due to normalization, so we use approximate
            return (page.page, pos, pos + len(normalized_value), value)

    return None


def backfill_evidence_from_values(
    result: ExtractionResult,
    azure_di: Optional[Dict[str, Any]] = None,
) -> ExtractionResult:
    """Backfill provenance for fields that have values but no evidence.

    For each field with a value but empty provenance:
    1. If Azure DI is available, search tables for exact cell matches (most precise)
    2. Fall back to searching page text

    Args:
        result: ExtractionResult with fields that may be missing provenance
        azure_di: Optional Azure DI data for table-aware matching

    Returns:
        Updated ExtractionResult with backfilled provenance
    """
    for field in result.fields:
        # Skip fields that already have provenance
        if field.provenance:
            continue

        # Skip fields with no value
        if not field.value:
            continue

        # Skip placeholder values
        if field.value_is_placeholder:
            continue

        value_str = str(field.value) if not isinstance(field.value, str) else field.value

        # Strategy 1: Search Azure DI tables (most precise)
        if azure_di:
            table_match = _find_value_in_azure_di_tables(azure_di, value_str)
            if table_match:
                page, char_start, char_end, cell_ref, matched_text = table_match
                field.provenance.append(FieldProvenance(
                    page=page,
                    method="di_text",
                    text_quote=matched_text,
                    char_start=char_start,
                    char_end=char_end,
                    match_quality="backfill_table_cell",
                    cell_ref=cell_ref,
                ))
                field.has_verified_evidence = True
                continue

        # Strategy 2: Search page text
        text_match = _find_value_in_page_text(result.pages, value_str)
        if text_match:
            page, char_start, char_end, matched_text = text_match
            field.provenance.append(FieldProvenance(
                page=page,
                method="di_text",
                text_quote=matched_text,
                char_start=char_start,
                char_end=char_end,
                match_quality="backfill_text_search",
            ))
            field.has_verified_evidence = True

    return result


def resolve_evidence_offsets(
    result: ExtractionResult,
    azure_di: Optional[Dict[str, Any]] = None,
) -> ExtractionResult:
    """
    Post-process extraction to fill missing char offsets and backfill missing provenance.

    Two-phase approach:
    1. For fields WITH provenance but missing offsets: resolve char_start/char_end
    2. For fields WITH values but NO provenance: backfill from Azure DI tables or page text

    Updates:
    - provenance.char_start / char_end
    - provenance.match_quality
    - field.has_verified_evidence

    Args:
        result: ExtractionResult with fields that may have missing offsets
        azure_di: Optional Azure DI data for table-aware evidence backfill

    Returns:
        The same ExtractionResult with updated offsets and evidence flags
    """
    pages_by_num = {p.page: p for p in result.pages}

    # Phase 1: Resolve existing provenance with missing offsets
    for field in result.fields:
        field_verified = False

        for prov in field.provenance:
            # Skip if already has valid offsets (non-zero) AND not marked as placeholder
            # Placeholder provenance needs resolution even if char_end > 0
            # (some extractors set char_end=len(quote) as a placeholder value)
            if (prov.char_start > 0 or prov.char_end > 0) and prov.match_quality != "placeholder":
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

    # Phase 2: Backfill provenance for fields with values but no evidence
    result = backfill_evidence_from_values(result, azure_di)

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
