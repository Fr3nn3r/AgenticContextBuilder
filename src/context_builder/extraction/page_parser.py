"""Parse Azure Document Intelligence markdown output into page-level content."""

import hashlib
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ParsedPage:
    """Parsed page content from Azure DI markdown."""
    page: int
    text: str
    text_md5: str


def compute_md5(text: str) -> str:
    """Compute MD5 hash of text content."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def parse_azure_di_markdown(markdown_text: str) -> List[ParsedPage]:
    """
    Parse Azure Document Intelligence markdown into pages.

    Azure DI uses HTML comments to mark page boundaries:
    - <!-- PageBreak --> marks page boundaries
    - <!-- PageNumber="X" --> contains page number (optional)
    - <!-- PageHeader="..." --> page headers
    - <!-- PageFooter="..." --> page footers

    Args:
        markdown_text: Full Azure DI markdown output

    Returns:
        List of ParsedPage objects with page number, text, and MD5 hash
    """
    if not markdown_text or not markdown_text.strip():
        return []

    # Split on PageBreak markers
    # The pattern matches <!-- PageBreak --> with optional whitespace
    page_break_pattern = r"<!--\s*PageBreak\s*-->"
    raw_pages = re.split(page_break_pattern, markdown_text)

    pages = []
    for i, page_text in enumerate(raw_pages, start=1):
        # Clean up the page text
        cleaned_text = _clean_page_text(page_text)

        if not cleaned_text.strip():
            continue

        pages.append(ParsedPage(
            page=i,
            text=cleaned_text,
            text_md5=compute_md5(cleaned_text)
        ))

    # If no page breaks found, treat entire document as single page
    if not pages and markdown_text.strip():
        cleaned_text = _clean_page_text(markdown_text)
        pages.append(ParsedPage(
            page=1,
            text=cleaned_text,
            text_md5=compute_md5(cleaned_text)
        ))

    return pages


def _clean_page_text(text: str) -> str:
    """
    Clean page text by removing HTML comment markers but preserving content structure.

    Removes:
    - <!-- PageNumber="..." -->
    - <!-- PageHeader="..." -->
    - <!-- PageFooter="..." -->

    Preserves:
    - Actual text content
    - Markdown formatting
    - Tables and figures
    """
    # Remove page metadata comments (but not PageBreak which is handled separately)
    patterns = [
        r"<!--\s*PageNumber\s*=\s*[\"']?[^\"'>]*[\"']?\s*-->",
        r"<!--\s*PageHeader\s*=\s*[\"'][^\"']*[\"']\s*-->",
        r"<!--\s*PageFooter\s*=\s*[\"'][^\"']*[\"']\s*-->",
    ]

    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove excessive whitespace but preserve paragraph structure
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def find_text_position(page_text: str, quote: str) -> Optional[Tuple[int, int]]:
    """
    Find the character position of a quote within page text.

    Uses case-insensitive search and handles minor whitespace differences.

    Args:
        page_text: Full text of the page
        quote: Text quote to find

    Returns:
        Tuple of (char_start, char_end) or None if not found
    """
    if not quote or not page_text:
        return None

    # Try exact match first
    pos = page_text.find(quote)
    if pos >= 0:
        return (pos, pos + len(quote))

    # Try case-insensitive match
    page_lower = page_text.lower()
    quote_lower = quote.lower()
    pos = page_lower.find(quote_lower)
    if pos >= 0:
        return (pos, pos + len(quote))

    # Try with normalized whitespace
    def normalize_ws(s: str) -> str:
        return re.sub(r"\s+", " ", s)

    page_normalized = normalize_ws(page_text)
    quote_normalized = normalize_ws(quote)

    pos = page_normalized.lower().find(quote_normalized.lower())
    if pos >= 0:
        # Map back to original position (approximate)
        return (pos, pos + len(quote_normalized))

    return None


def find_quote_in_pages(
    pages: List[ParsedPage], quote: str
) -> Optional[Tuple[int, int, int]]:
    """
    Find a quote across all pages.

    Args:
        pages: List of parsed pages
        quote: Text to find

    Returns:
        Tuple of (page_number, char_start, char_end) or None if not found
    """
    for page in pages:
        position = find_text_position(page.text, quote)
        if position:
            return (page.page, position[0], position[1])
    return None


def extract_text_window(
    page_text: str, center_pos: int, window_size: int = 800
) -> Tuple[str, int, int]:
    """
    Extract a text window centered around a position.

    Args:
        page_text: Full page text
        center_pos: Center position for the window
        window_size: Total window size (half on each side)

    Returns:
        Tuple of (window_text, start_offset, end_offset)
    """
    half_window = window_size // 2
    start = max(0, center_pos - half_window)
    end = min(len(page_text), center_pos + half_window)

    return (page_text[start:end], start, end)
