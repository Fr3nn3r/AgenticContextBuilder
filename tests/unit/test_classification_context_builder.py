"""
Unit tests for classification context builder.

Tests tiered truncation, cue snippet extraction, and edge cases.
"""

import pytest

from context_builder.classification.context_builder import (
    ClassificationContext,
    CueSnippet,
    build_classification_context,
    extract_cue_snippets,
    load_all_cue_phrases,
    normalize_for_matching,
    SHORT_DOC_THRESHOLD,
)


class TestNormalizeForMatching:
    """Tests for text normalization."""

    def test_lowercases_text(self):
        assert normalize_for_matching("HELLO World") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_for_matching("hello   world\n\tfoo") == "hello world foo"

    def test_strips_edges(self):
        assert normalize_for_matching("  hello  ") == "hello"

    def test_empty_string(self):
        assert normalize_for_matching("") == ""


class TestLoadAllCuePhrases:
    """Tests for cue phrase loading from catalog."""

    def test_loads_cues_from_catalog(self, tmp_path):
        """Test loading cues from a catalog file."""
        catalog = tmp_path / "doc_type_catalog.yaml"
        catalog.write_text(
            """doc_types:
  - doc_type: test_type
    description: Test doc
    cues:
      - fnol
      - invoice
      - police report
""",
            encoding="utf-8",
        )
        cues = load_all_cue_phrases(catalog_path=catalog)
        assert len(cues) > 0
        cues_lower = [c.lower() for c in cues]
        assert "fnol" in cues_lower
        assert "invoice" in cues_lower
        assert "police report" in cues_lower

    def test_removes_duplicates(self, tmp_path):
        """Test that duplicate cues are removed."""
        catalog = tmp_path / "doc_type_catalog.yaml"
        catalog.write_text(
            """doc_types:
  - doc_type: type_a
    description: A
    cues: [fnol, claim, report]
  - doc_type: type_b
    description: B
    cues: [claim, invoice, report]
""",
            encoding="utf-8",
        )
        cues = load_all_cue_phrases(catalog_path=catalog)
        cues_lower = [c.lower() for c in cues]
        assert len(cues_lower) == len(set(cues_lower))


class TestExtractCueSnippets:
    """Tests for cue snippet extraction."""

    def test_finds_single_cue(self):
        pages = [(1, "This is a claim report for the incident.")]
        cues = ["claim report"]

        snippets = extract_cue_snippets(pages, cues)

        assert len(snippets) == 1
        assert snippets[0].cue == "claim report"
        assert snippets[0].page_num == 1
        assert "claim report" in snippets[0].text.lower()

    def test_finds_multiple_cues(self):
        pages = [(1, "FNOL form submitted. Policy number 12345.")]
        cues = ["FNOL", "policy number"]

        snippets = extract_cue_snippets(pages, cues)

        assert len(snippets) == 2
        matched_cues = {s.cue.lower() for s in snippets}
        assert "fnol" in matched_cues
        assert "policy number" in matched_cues

    def test_respects_max_snippets(self):
        # Create text with many cue matches
        text = "invoice receipt bill total payment factura"
        pages = [(1, text)]
        cues = ["invoice", "receipt", "bill", "total", "payment", "factura"]

        snippets = extract_cue_snippets(pages, cues, max_snippets=3)

        assert len(snippets) <= 3

    def test_skips_very_short_cues(self):
        pages = [(1, "ID card and VIN number")]
        cues = ["ID", "VIN"]  # Both are 2-3 chars

        snippets = extract_cue_snippets(pages, cues)

        # "ID" should be skipped (too short), "VIN" is exactly 3 chars
        assert len(snippets) <= 1

    def test_case_insensitive_matching(self):
        pages = [(1, "this is an FNOL form")]
        cues = ["fnol"]

        snippets = extract_cue_snippets(pages, cues)

        assert len(snippets) == 1

    def test_multiple_pages(self):
        pages = [
            (1, "Page one with invoice"),
            (2, "Page two with receipt"),
            (3, "Page three with nothing"),
        ]
        cues = ["invoice", "receipt"]

        snippets = extract_cue_snippets(pages, cues)

        assert len(snippets) == 2
        page_nums = {s.page_num for s in snippets}
        assert page_nums == {1, 2}

    def test_adds_ellipsis_when_truncated(self):
        long_text = "A" * 500 + " invoice " + "B" * 500
        pages = [(1, long_text)]
        cues = ["invoice"]

        snippets = extract_cue_snippets(pages, cues, context_chars=50)

        assert len(snippets) == 1
        assert snippets[0].text.startswith("...")
        assert snippets[0].text.endswith("...")

    def test_empty_pages(self):
        pages = []
        cues = ["invoice"]

        snippets = extract_cue_snippets(pages, cues)

        assert len(snippets) == 0

    def test_no_matching_cues(self):
        pages = [(1, "This document has no relevant keywords")]
        cues = ["invoice", "FNOL", "police report"]

        snippets = extract_cue_snippets(pages, cues)

        assert len(snippets) == 0

    def test_avoids_duplicate_overlapping_snippets(self):
        # When one cue is contained within another's match range, skip it
        # "policy number" at position 10 covers positions 10-22
        # If we search for "policy" alone, it would match at position 10
        # but that's within the already-covered range
        pages = [(1, "Check the policy number 12345 in the document")]
        cues = ["policy number", "policy"]

        snippets = extract_cue_snippets(pages, cues)

        # Should find "policy number" but not duplicate with just "policy"
        assert len(snippets) == 1
        assert snippets[0].cue == "policy number"


class TestBuildClassificationContext:
    """Tests for the main context building function."""

    def test_short_document_uses_full_text(self):
        # Create short document under threshold
        pages = ["Page one content.", "Page two content."]
        total_chars = sum(len(p) for p in pages)
        assert total_chars < SHORT_DOC_THRESHOLD

        result = build_classification_context(pages)

        assert result.tier == "full"
        assert "Page one content" in result.text
        assert "Page two content" in result.text
        assert result.pages_included == 2

    def test_long_document_uses_optimized_context(self):
        # Create document over threshold
        pages = ["A" * 2000] * 10  # 20K chars, 10 pages
        total_chars = sum(len(p) for p in pages)
        assert total_chars > SHORT_DOC_THRESHOLD

        result = build_classification_context(pages, cue_phrases=[])

        assert result.tier == "optimized"
        assert "=== DOCUMENT START ===" in result.text
        assert "=== FINAL PAGE ===" in result.text

    def test_includes_first_two_pages(self):
        pages = [f"Page {i} unique content xyz{i}" for i in range(10)]
        # Make it long enough
        pages = [p + " " * 1000 for p in pages]

        result = build_classification_context(pages, cue_phrases=[])

        assert "Page 0 unique content xyz0" in result.text
        assert "Page 1 unique content xyz1" in result.text

    def test_includes_last_page(self):
        pages = [f"Page {i} content" for i in range(10)]
        pages = [p + " " * 1000 for p in pages]

        result = build_classification_context(pages, cue_phrases=[])

        assert "Page 9 content" in result.text

    def test_extracts_cue_snippets_from_middle_pages(self):
        pages = [
            "Page 0 intro",
            "Page 1 header",
            "Page 2 middle content",
            "Page 3 has FNOL claim report here",  # Should be found
            "Page 4 more middle",
            "Page 5 ending",
        ]
        pages = [p + " " * 1500 for p in pages]

        result = build_classification_context(pages, cue_phrases=["FNOL", "claim report"])

        # Should find cues in middle pages
        assert result.snippets_found > 0
        assert "KEY SNIPPETS" in result.text

    def test_empty_pages_list(self):
        result = build_classification_context([])

        assert result.tier == "full"
        assert result.text == ""
        assert result.pages_included == 0

    def test_single_page_document(self):
        pages = ["Single page document content."]

        result = build_classification_context(pages)

        assert result.tier == "full"
        assert "Single page document content" in result.text

    def test_two_page_document_over_threshold(self):
        # Two long pages that exceed threshold
        pages = ["A" * 3000, "B" * 3000]

        result = build_classification_context(pages, cue_phrases=[])

        # Should be optimized but only include first 2 pages (all pages)
        assert result.tier == "optimized"
        assert "DOCUMENT START" in result.text
        # No final page section since we only have 2 pages
        assert result.pages_included == 2

    def test_three_page_document_includes_all_sections(self):
        pages = ["A" * 2000, "B" * 2000, "C" * 2000]

        result = build_classification_context(pages, cue_phrases=[])

        assert result.tier == "optimized"
        assert "DOCUMENT START" in result.text
        assert "FINAL PAGE" in result.text
        assert result.pages_included == 3

    def test_metadata_tracking(self):
        pages = ["A" * 2000] * 5

        result = build_classification_context(pages, cue_phrases=[])

        assert result.total_chars == 10000
        assert result.tier == "optimized"
        assert isinstance(result.cues_matched, list)

    def test_loads_cues_from_catalog_when_none_provided(self):
        pages = [
            "Page 0",
            "Page 1",
            "Page 2 with invoice and receipt",
            "Page 3",
        ]
        pages = [p + " " * 2000 for p in pages]

        # Don't pass cue_phrases - should load from catalog
        result = build_classification_context(pages, cue_phrases=None)

        # Should have loaded cues and found matches
        assert result.tier == "optimized"


class TestClassificationContextDataclass:
    """Tests for the ClassificationContext dataclass."""

    def test_default_values(self):
        ctx = ClassificationContext(text="test", tier="full")

        assert ctx.text == "test"
        assert ctx.tier == "full"
        assert ctx.total_chars == 0
        assert ctx.pages_included == 0
        assert ctx.snippets_found == 0
        assert ctx.cues_matched == []

    def test_all_fields(self):
        ctx = ClassificationContext(
            text="test",
            tier="optimized",
            total_chars=10000,
            pages_included=5,
            snippets_found=3,
            cues_matched=["invoice", "FNOL"],
        )

        assert ctx.total_chars == 10000
        assert ctx.pages_included == 5
        assert ctx.snippets_found == 3
        assert ctx.cues_matched == ["invoice", "FNOL"]


class TestCueSnippetDataclass:
    """Tests for the CueSnippet dataclass."""

    def test_creation(self):
        snippet = CueSnippet(
            cue="invoice",
            page_num=3,
            text="...surrounding invoice text...",
            match_position=150,
        )

        assert snippet.cue == "invoice"
        assert snippet.page_num == 3
        assert snippet.text == "...surrounding invoice text..."
        assert snippet.match_position == 150
