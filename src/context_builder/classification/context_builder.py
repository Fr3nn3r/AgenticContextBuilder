"""
Classification context builder for optimizing LLM token usage.

Implements tiered context truncation with cue-based snippet extraction
to reduce token costs while maintaining classification accuracy.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

# Character threshold for "short" documents that get full text
SHORT_DOC_THRESHOLD = 5000

# Default surrounding context for cue snippets (chars before/after match)
SNIPPET_CONTEXT_CHARS = 200

# Maximum snippets to extract from middle pages
MAX_CUE_SNIPPETS = 8


@dataclass
class ClassificationContext:
    """Result of building optimized classification context.

    Attributes:
        text: The optimized context text to send to the LLM.
        tier: Strategy used ("full" or "optimized").
        total_chars: Total characters in the original document.
        pages_included: Number of pages included in context.
        snippets_found: Number of cue snippets found and included.
        cues_matched: List of cue phrases that were matched.
        sources: Structured source information for audit logging.
    """

    text: str
    tier: str  # "full" or "optimized"
    total_chars: int = 0
    pages_included: int = 0
    snippets_found: int = 0
    cues_matched: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CueSnippet:
    """A snippet of text surrounding a matched cue phrase."""

    cue: str
    page_num: int
    text: str
    match_position: int


def load_all_cue_phrases(catalog_path: Optional[Path] = None) -> List[str]:
    """
    Load all cue phrases from the doc_type_catalog.yaml.

    Returns a flat list of all cues across all document types.
    """
    if catalog_path is None:
        catalog_path = (
            Path(__file__).parent.parent
            / "extraction"
            / "specs"
            / "doc_type_catalog.yaml"
        )

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = yaml.safe_load(f)

        all_cues = []
        for doc_type in catalog.get("doc_types", []):
            cues = doc_type.get("cues", [])
            all_cues.extend(cues)

        # Remove duplicates while preserving order
        seen = set()
        unique_cues = []
        for cue in all_cues:
            cue_lower = cue.lower()
            if cue_lower not in seen:
                seen.add(cue_lower)
                unique_cues.append(cue)

        logger.debug(f"Loaded {len(unique_cues)} unique cue phrases from catalog")
        return unique_cues

    except Exception as e:
        logger.warning(f"Failed to load cue phrases from catalog: {e}")
        return []


def normalize_for_matching(text: str) -> str:
    """
    Normalize text for fuzzy cue matching.

    Handles OCR errors by normalizing whitespace and common substitutions.
    """
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    # Common OCR substitutions (0/O, 1/l/I, etc.)
    # Keep it simple - just lowercase and collapse spaces
    return text.lower().strip()


def extract_cue_snippets(
    pages: List[Tuple[int, str]],
    cue_phrases: List[str],
    max_snippets: int = MAX_CUE_SNIPPETS,
    context_chars: int = SNIPPET_CONTEXT_CHARS,
) -> List[CueSnippet]:
    """
    Extract snippets of text surrounding matched cue phrases.

    Uses fuzzy matching to handle OCR errors and text variations.

    Args:
        pages: List of (page_number, page_text) tuples
        cue_phrases: List of cue phrases to search for
        max_snippets: Maximum number of snippets to return
        context_chars: Characters of context before/after match

    Returns:
        List of CueSnippet objects, sorted by page number then position
    """
    snippets: List[CueSnippet] = []
    # Track covered ranges to avoid overlapping snippets (page_num -> list of (start, end))
    covered_ranges: dict = {}

    # Sort cues by length descending to prioritize longer, more specific matches
    sorted_cues = sorted(cue_phrases, key=len, reverse=True)

    for page_num, page_text in pages:
        if len(snippets) >= max_snippets:
            break

        normalized_text = normalize_for_matching(page_text)
        if page_num not in covered_ranges:
            covered_ranges[page_num] = []

        for cue in sorted_cues:
            if len(snippets) >= max_snippets:
                break

            normalized_cue = normalize_for_matching(cue)

            # Skip very short cues (too many false positives)
            if len(normalized_cue) < 3:
                continue

            # Find all matches in the normalized text
            pos = 0
            while True:
                match_pos = normalized_text.find(normalized_cue, pos)
                if match_pos == -1:
                    break

                # Check if this position is already covered by another snippet
                is_covered = False
                for start_r, end_r in covered_ranges[page_num]:
                    if start_r <= match_pos <= end_r:
                        is_covered = True
                        break
                if is_covered:
                    pos = match_pos + 1
                    continue

                # Extract surrounding context from original text
                start = max(0, match_pos - context_chars)
                end = min(len(page_text), match_pos + len(cue) + context_chars)

                # Expand to word boundaries (limited to 50 extra chars max)
                word_boundary_limit = 50
                expand_start = start
                while expand_start > 0 and (start - expand_start) < word_boundary_limit:
                    if page_text[expand_start - 1] in " \n\t":
                        break
                    expand_start -= 1
                start = expand_start

                expand_end = end
                while expand_end < len(page_text) and (expand_end - end) < word_boundary_limit:
                    if page_text[expand_end] in " \n\t":
                        break
                    expand_end += 1
                end = expand_end

                snippet_text = page_text[start:end].strip()

                # Add ellipsis if truncated
                if start > 0:
                    snippet_text = "..." + snippet_text
                if end < len(page_text):
                    snippet_text = snippet_text + "..."

                # Mark this range as covered
                covered_ranges[page_num].append((match_pos, match_pos + len(normalized_cue)))

                snippets.append(
                    CueSnippet(
                        cue=cue,
                        page_num=page_num,
                        text=snippet_text,
                        match_position=match_pos,
                    )
                )

                pos = match_pos + len(normalized_cue)

    # Sort by page number, then position
    snippets.sort(key=lambda s: (s.page_num, s.match_position))

    return snippets[:max_snippets]


def build_classification_context(
    pages: List[str],
    cue_phrases: Optional[List[str]] = None,
    short_doc_threshold: int = SHORT_DOC_THRESHOLD,
    max_snippets: int = MAX_CUE_SNIPPETS,
) -> ClassificationContext:
    """
    Build optimized context for document classification.

    Implements tiered truncation:
    - Short docs (< threshold): Use full text
    - Longer docs: First 2 pages + last page + cue snippets

    Args:
        pages: List of page texts (0-indexed)
        cue_phrases: Optional list of cue phrases; loads from catalog if None
        short_doc_threshold: Character count threshold for "short" documents
        max_snippets: Maximum cue snippets to include

    Returns:
        ClassificationContext with optimized text and metadata
    """
    if not pages:
        return ClassificationContext(
            text="",
            tier="full",
            total_chars=0,
            pages_included=0,
        )

    total_chars = sum(len(p) for p in pages)
    sources: List[Dict[str, Any]] = []

    # Tier 1: Short documents - use full text
    if total_chars < short_doc_threshold:
        logger.debug(f"Short document ({total_chars} chars), using full text")
        # Track all pages as sources
        for i, page_text in enumerate(pages):
            sources.append({
                "source_type": "page",
                "page_number": i + 1,
                "char_start": 0,
                "char_end": len(page_text),
                "content_preview": page_text[:200] if page_text else "",
                "selection_criteria": "full_document",
            })
        return ClassificationContext(
            text="\n\n".join(pages),
            tier="full",
            total_chars=total_chars,
            pages_included=len(pages),
            sources=sources,
        )

    # Tier 2: Longer documents - optimized context
    logger.debug(
        f"Long document ({total_chars} chars, {len(pages)} pages), using optimized context"
    )

    if cue_phrases is None:
        cue_phrases = load_all_cue_phrases()

    context_parts = []
    pages_included = 0
    cues_matched = []

    # First 2 pages (document header/title)
    first_pages = pages[:2]
    context_parts.append("=== DOCUMENT START ===\n" + "\n\n".join(first_pages))
    pages_included += len(first_pages)

    # Track first pages as sources
    for i, page_text in enumerate(first_pages):
        sources.append({
            "source_type": "page",
            "page_number": i + 1,
            "char_start": 0,
            "char_end": len(page_text),
            "content_preview": page_text[:200] if page_text else "",
            "selection_criteria": "document_start",
        })

    # Last page (signatures, form footers) if more than 2 pages
    if len(pages) > 2:
        context_parts.append("=== FINAL PAGE ===\n" + pages[-1])
        pages_included += 1
        sources.append({
            "source_type": "page",
            "page_number": len(pages),
            "char_start": 0,
            "char_end": len(pages[-1]),
            "content_preview": pages[-1][:200] if pages[-1] else "",
            "selection_criteria": "document_end",
        })

    # Cue-based snippets from middle pages
    middle_pages = pages[2:-1] if len(pages) > 3 else []
    if middle_pages and cue_phrases:
        # Create (page_num, text) tuples for snippet extraction
        indexed_pages = [(i + 3, text) for i, text in enumerate(middle_pages)]
        snippets = extract_cue_snippets(indexed_pages, cue_phrases, max_snippets)

        if snippets:
            snippet_texts = []
            for s in snippets:
                snippet_texts.append(f"[Page {s.page_num}] {s.text}")
                cues_matched.append(s.cue)
                # Track cue snippets as sources
                sources.append({
                    "source_type": "cue_match",
                    "page_number": s.page_num,
                    "char_start": s.match_position,
                    "char_end": s.match_position + len(s.text),
                    "content_preview": s.text[:200] if s.text else "",
                    "selection_criteria": f"cue_phrase:{s.cue}",
                    "metadata": {"cue": s.cue},
                })

            context_parts.append("=== KEY SNIPPETS ===\n" + "\n---\n".join(snippet_texts))

    final_text = "\n\n".join(context_parts)

    return ClassificationContext(
        text=final_text,
        tier="optimized",
        total_chars=total_chars,
        pages_included=pages_included,
        snippets_found=len(cues_matched),
        cues_matched=list(set(cues_matched)),  # Deduplicate
        sources=sources,
    )
