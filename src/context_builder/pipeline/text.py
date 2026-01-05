"""Text module: build canonical pages.json from raw text content."""

import hashlib
from typing import Any, Dict, List

from context_builder.schemas.extraction_result import PageContent

SCHEMA_VERSION = "doc_text_v1"


def build_pages_json(
    text_content: str,
    doc_id: str,
    source_type: str = "preextracted_txt",
) -> Dict[str, Any]:
    """
    Build canonical pages.json from text content.

    Since .pdf.txt files don't have page boundary info, we treat
    the entire content as a single page.

    Args:
        text_content: Full text content
        doc_id: Document identifier
        source_type: Source identification string

    Returns:
        Dict conforming to doc_text_v1 schema
    """
    text_md5 = hashlib.md5(text_content.encode("utf-8")).hexdigest()

    return {
        "schema_version": SCHEMA_VERSION,
        "doc_id": doc_id,
        "page_count": 1,
        "pages": [
            {
                "page": 1,
                "text": text_content,
                "source": source_type,
                "text_md5": text_md5,
            }
        ],
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
    return [
        PageContent(
            page=p["page"],
            text=p["text"],
            text_md5=p["text_md5"],
        )
        for p in pages_json["pages"]
    ]
