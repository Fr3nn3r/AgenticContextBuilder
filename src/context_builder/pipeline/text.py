"""Text module: build canonical pages.json from raw text content."""

import hashlib
import re
from typing import Any, Dict, List

from context_builder.schemas.extraction_result import PageContent

SCHEMA_VERSION = "doc_text_v1"

# Azure DI page marker patterns:
# <!-- PageNumber="1" --> or <!-- PageNumber="Página 1 de 20" -->
PAGE_MARKER_PATTERN = re.compile(
    r'<!--\s*PageNumber\s*=\s*["\']?(?:P[aá]gina\s+)?(\d+)(?:\s+de\s+\d+)?["\']?\s*-->',
    re.IGNORECASE
)


def _split_by_page_markers(text_content: str) -> List[Dict[str, Any]]:
    """
    Split text content by Azure DI page markers.

    Returns list of {page: int, text: str} dicts.
    If no markers found, returns single page with all content.
    """
    # Find all page markers with their positions
    matches = list(PAGE_MARKER_PATTERN.finditer(text_content))

    if not matches:
        # No page markers found - treat as single page
        return [{"page": 1, "text": text_content}]

    pages = []

    for i, match in enumerate(matches):
        page_num = int(match.group(1))
        start_pos = match.end()

        # End position is either the next marker or end of content
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(text_content)

        page_text = text_content[start_pos:end_pos].strip()

        if page_text:  # Only add non-empty pages
            pages.append({"page": page_num, "text": page_text})

    # Handle text before the first marker (if any)
    if matches and matches[0].start() > 0:
        pre_text = text_content[:matches[0].start()].strip()
        if pre_text:
            # Prepend to first page or create page 0
            if pages:
                pages[0]["text"] = pre_text + "\n\n" + pages[0]["text"]
            else:
                pages.insert(0, {"page": 1, "text": pre_text})

    return pages if pages else [{"page": 1, "text": text_content}]


def build_pages_json(
    text_content: str,
    doc_id: str,
    source_type: str = "preextracted_txt",
) -> Dict[str, Any]:
    """
    Build canonical pages.json from text content.

    Parses Azure DI page markers (<!-- PageNumber="X" -->) to split
    content into separate pages. Falls back to single page if no
    markers are found.

    Args:
        text_content: Full text content (may contain page markers)
        doc_id: Document identifier
        source_type: Source identification string

    Returns:
        Dict conforming to doc_text_v1 schema
    """
    page_splits = _split_by_page_markers(text_content)

    pages = []
    for p in page_splits:
        text_md5 = hashlib.md5(p["text"].encode("utf-8")).hexdigest()
        pages.append({
            "page": p["page"],
            "text": p["text"],
            "source": source_type,
            "text_md5": text_md5,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "doc_id": doc_id,
        "page_count": len(pages),
        "pages": pages,
    }


def _split_by_azure_di_spans(
    text_content: str,
    azure_di_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Split text content using Azure DI page spans.

    Uses offset/length from Azure DI raw output to split content
    into pages. This is more reliable than page markers when
    markers are corrupted or missing.

    Args:
        text_content: The markdown/text content from Azure DI
        azure_di_data: The azure_di.json data with raw_azure_di_output

    Returns:
        List of {page: int, text: str} dicts.
    """
    raw_output = azure_di_data.get("raw_azure_di_output", {})
    pages_info = raw_output.get("pages", [])

    if not pages_info:
        return [{"page": 1, "text": text_content}]

    pages = []
    for page_info in pages_info:
        page_num = page_info.get("pageNumber", len(pages) + 1)
        spans = page_info.get("spans", [])

        if not spans:
            continue

        # Combine all spans for this page
        page_text_parts = []
        for span in spans:
            offset = span.get("offset", 0)
            length = span.get("length", 0)
            if offset < len(text_content):
                end = min(offset + length, len(text_content))
                page_text_parts.append(text_content[offset:end])

        page_text = "".join(page_text_parts).strip()
        if page_text:
            pages.append({"page": page_num, "text": page_text})

    return pages if pages else [{"page": 1, "text": text_content}]


def build_pages_json_from_azure_di(
    azure_di_data: Dict[str, Any],
    doc_id: str,
) -> Dict[str, Any]:
    """
    Build canonical pages.json from Azure DI JSON data.

    Uses page spans from raw Azure DI output for reliable page splitting,
    bypassing potentially corrupted page markers in the text content.

    Args:
        azure_di_data: The azure_di.json data dict
        doc_id: Document identifier

    Returns:
        Dict conforming to doc_text_v1 schema
    """
    # Get text content from raw output
    raw_output = azure_di_data.get("raw_azure_di_output", {})
    text_content = raw_output.get("content", "")

    if not text_content:
        return {
            "schema_version": SCHEMA_VERSION,
            "doc_id": doc_id,
            "page_count": 0,
            "pages": [],
        }

    page_splits = _split_by_azure_di_spans(text_content, azure_di_data)

    pages = []
    for p in page_splits:
        text_md5 = hashlib.md5(p["text"].encode("utf-8")).hexdigest()
        pages.append({
            "page": p["page"],
            "text": p["text"],
            "source": "azure_di",
            "text_md5": text_md5,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "doc_id": doc_id,
        "page_count": len(pages),
        "pages": pages,
    }


def pages_json_to_page_content(pages_json: Dict[str, Any]) -> List[PageContent]:
    """
    Convert pages.json dict to list of PageContent for extraction.

    Used to bridge to existing extraction system.

    Args:
        pages_json: Dict with pages array

    Returns:
        List of PageContent pydantic models
    """
    # Defensive check: ensure pages_json and pages array exist
    if not pages_json:
        return []
    pages = pages_json.get("pages") or []
    return [
        PageContent(
            page=p["page"],
            text=p["text"],
            text_md5=p.get("text_md5", ""),
        )
        for p in pages
    ]
