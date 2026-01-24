"""Unit tests for context_builder.pipeline.text module."""

import pytest

from context_builder.pipeline.text import (
    PAGE_MARKER_PATTERN,
    _split_by_page_markers,
    _split_by_azure_di_spans,
    build_pages_json,
    build_pages_json_from_azure_di,
)


class TestPageMarkerPattern:
    """Test the PAGE_MARKER_PATTERN regex."""

    def test_simple_english_marker(self):
        """Should match simple page number markers."""
        text = '<!-- PageNumber="1" -->'
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "1"

    def test_spanish_page_marker(self):
        """Should match Spanish 'Página X de Y' format."""
        text = '<!-- PageNumber="Página 5 de 20" -->'
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "5"

    def test_spanish_accent_variation(self):
        """Should match 'Pagina' without accent."""
        text = '<!-- PageNumber="Pagina 3 de 10" -->'
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "3"

    def test_single_quotes(self):
        """Should match single-quoted values."""
        text = "<!-- PageNumber='7' -->"
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "7"

    def test_no_quotes(self):
        """Should match unquoted values."""
        text = "<!-- PageNumber=12 -->"
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "12"

    def test_extra_whitespace(self):
        """Should handle extra whitespace."""
        text = '<!--  PageNumber  =  "4"  -->'
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "4"

    def test_case_insensitive(self):
        """Should match case-insensitively."""
        text = '<!-- PAGENUMBER="2" -->'
        match = PAGE_MARKER_PATTERN.search(text)
        assert match is not None
        assert match.group(1) == "2"


class TestSplitByPageMarkers:
    """Test the _split_by_page_markers function."""

    def test_no_markers_returns_single_page(self):
        """Content without markers should return as single page."""
        content = "This is some text without any page markers."
        result = _split_by_page_markers(content)

        assert len(result) == 1
        assert result[0]["page"] == 1
        assert result[0]["text"] == content

    def test_single_marker(self):
        """Single marker should create one page."""
        content = '<!-- PageNumber="1" -->\nPage one content here.'
        result = _split_by_page_markers(content)

        assert len(result) == 1
        assert result[0]["page"] == 1
        assert result[0]["text"] == "Page one content here."

    def test_multiple_markers(self):
        """Multiple markers should create multiple pages."""
        content = '''<!-- PageNumber="1" -->
First page content.
<!-- PageNumber="2" -->
Second page content.
<!-- PageNumber="3" -->
Third page content.'''

        result = _split_by_page_markers(content)

        assert len(result) == 3
        assert result[0]["page"] == 1
        assert "First page content" in result[0]["text"]
        assert result[1]["page"] == 2
        assert "Second page content" in result[1]["text"]
        assert result[2]["page"] == 3
        assert "Third page content" in result[2]["text"]

    def test_spanish_markers(self):
        """Should handle Spanish page markers."""
        content = '''<!-- PageNumber="Página 1 de 3" -->
Primera página.
<!-- PageNumber="Página 2 de 3" -->
Segunda página.
<!-- PageNumber="Página 3 de 3" -->
Tercera página.'''

        result = _split_by_page_markers(content)

        assert len(result) == 3
        assert result[0]["page"] == 1
        assert result[1]["page"] == 2
        assert result[2]["page"] == 3

    def test_text_before_first_marker(self):
        """Text before first marker should be prepended to first page."""
        content = '''Header text before markers.
<!-- PageNumber="1" -->
Page one content.'''

        result = _split_by_page_markers(content)

        assert len(result) == 1
        assert result[0]["page"] == 1
        assert "Header text before markers" in result[0]["text"]
        assert "Page one content" in result[0]["text"]

    def test_empty_page_skipped(self):
        """Empty pages should be skipped."""
        content = '''<!-- PageNumber="1" -->
<!-- PageNumber="2" -->
Page two has content.'''

        result = _split_by_page_markers(content)

        # Page 1 is empty, should be skipped
        assert len(result) == 1
        assert result[0]["page"] == 2

    def test_preserves_page_numbers(self):
        """Should preserve original page numbers, not renumber."""
        content = '''<!-- PageNumber="5" -->
Page five.
<!-- PageNumber="10" -->
Page ten.'''

        result = _split_by_page_markers(content)

        assert len(result) == 2
        assert result[0]["page"] == 5
        assert result[1]["page"] == 10


class TestBuildPagesJson:
    """Test the build_pages_json function."""

    def test_schema_version(self):
        """Should include correct schema version."""
        result = build_pages_json("content", "doc123")
        assert result["schema_version"] == "doc_text_v1"

    def test_doc_id(self):
        """Should include doc_id."""
        result = build_pages_json("content", "doc123")
        assert result["doc_id"] == "doc123"

    def test_page_count_single(self):
        """Should have page_count=1 for content without markers."""
        result = build_pages_json("No markers here", "doc123")
        assert result["page_count"] == 1

    def test_page_count_multiple(self):
        """Should count pages correctly."""
        content = '''<!-- PageNumber="1" -->
Page one.
<!-- PageNumber="2" -->
Page two.'''
        result = build_pages_json(content, "doc123")
        assert result["page_count"] == 2

    def test_pages_have_required_fields(self):
        """Each page should have required fields."""
        content = '<!-- PageNumber="1" -->\nTest content.'
        result = build_pages_json(content, "doc123", "azure_di")

        assert len(result["pages"]) == 1
        page = result["pages"][0]
        assert "page" in page
        assert "text" in page
        assert "source" in page
        assert "text_md5" in page
        assert page["source"] == "azure_di"

    def test_md5_computed_correctly(self):
        """MD5 should be computed for each page's text."""
        import hashlib

        content = '<!-- PageNumber="1" -->\nTest content.'
        result = build_pages_json(content, "doc123")

        page = result["pages"][0]
        expected_md5 = hashlib.md5(page["text"].encode("utf-8")).hexdigest()
        assert page["text_md5"] == expected_md5

    def test_integration_azure_di_format(self):
        """Integration test with realistic Azure DI format."""
        content = '''<!-- PageNumber="Página 1 de 20" -->

# CONSTANCIA DE ROBO TOTAL

**Número de Siniestro:** 24-02-VH-7053819
**Fecha:** 15/03/2024

<!-- PageNumber="Página 2 de 20" -->

## DATOS DEL ASEGURADO

| Campo | Valor |
|-------|-------|
| Nombre | Juan Pérez |
| Póliza | GTQ4558 |

<!-- PageNumber="Página 3 de 20" -->

## DESCRIPCIÓN DEL SINIESTRO

El vehículo fue robado en la madrugada del día 14 de marzo.'''

        result = build_pages_json(content, "74db882a11a9", "azure_di")

        assert result["page_count"] == 3
        assert result["pages"][0]["page"] == 1
        assert result["pages"][1]["page"] == 2
        assert result["pages"][2]["page"] == 3

        # Check content is in correct pages
        assert "CONSTANCIA DE ROBO" in result["pages"][0]["text"]
        assert "DATOS DEL ASEGURADO" in result["pages"][1]["text"]
        assert "DESCRIPCIÓN DEL SINIESTRO" in result["pages"][2]["text"]


class TestSplitByAzureDiSpans:
    """Test the _split_by_azure_di_spans function."""

    def test_no_raw_output_returns_single_page(self):
        """Missing raw output should return single page."""
        content = "Some content here"
        azure_di_data = {}
        result = _split_by_azure_di_spans(content, azure_di_data)

        assert len(result) == 1
        assert result[0]["page"] == 1
        assert result[0]["text"] == content

    def test_no_pages_returns_single_page(self):
        """Empty pages array should return single page."""
        content = "Some content here"
        azure_di_data = {"raw_azure_di_output": {"pages": []}}
        result = _split_by_azure_di_spans(content, azure_di_data)

        assert len(result) == 1
        assert result[0]["page"] == 1

    def test_single_page_span(self):
        """Single page with span should work correctly."""
        content = "Page one content here."
        azure_di_data = {
            "raw_azure_di_output": {
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": 22}]}
                ]
            }
        }
        result = _split_by_azure_di_spans(content, azure_di_data)

        assert len(result) == 1
        assert result[0]["page"] == 1
        assert result[0]["text"] == "Page one content here."

    def test_multiple_pages_with_spans(self):
        """Multiple pages with spans should split correctly."""
        content = "First page content.Second page content.Third page content."
        azure_di_data = {
            "raw_azure_di_output": {
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": 19}]},
                    {"pageNumber": 2, "spans": [{"offset": 19, "length": 20}]},
                    {"pageNumber": 3, "spans": [{"offset": 39, "length": 20}]},
                ]
            }
        }
        result = _split_by_azure_di_spans(content, azure_di_data)

        assert len(result) == 3
        assert result[0]["page"] == 1
        assert result[0]["text"] == "First page content."
        assert result[1]["page"] == 2
        assert result[1]["text"] == "Second page content."
        assert result[2]["page"] == 3
        assert result[2]["text"] == "Third page content."

    def test_realistic_azure_di_spans(self):
        """Test with realistic Azure DI span structure."""
        content = "Page 1 header and intro text here." + "Data table on page 2." + "Summary on page 3."
        azure_di_data = {
            "raw_azure_di_output": {
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": 34}]},
                    {"pageNumber": 2, "spans": [{"offset": 34, "length": 21}]},
                    {"pageNumber": 3, "spans": [{"offset": 55, "length": 18}]},
                ]
            }
        }
        result = _split_by_azure_di_spans(content, azure_di_data)

        assert len(result) == 3
        assert "header and intro" in result[0]["text"]
        assert "Data table" in result[1]["text"]
        assert "Summary" in result[2]["text"]

    def test_page_without_spans_skipped(self):
        """Pages without spans should be skipped."""
        content = "Page one.Page three."
        azure_di_data = {
            "raw_azure_di_output": {
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": 9}]},
                    {"pageNumber": 2, "spans": []},  # Empty spans
                    {"pageNumber": 3, "spans": [{"offset": 9, "length": 11}]},
                ]
            }
        }
        result = _split_by_azure_di_spans(content, azure_di_data)

        assert len(result) == 2
        assert result[0]["page"] == 1
        assert result[1]["page"] == 3


class TestBuildPagesJsonFromAzureDi:
    """Test the build_pages_json_from_azure_di function."""

    def test_empty_content(self):
        """Empty content should return empty pages."""
        azure_di_data = {"raw_azure_di_output": {"content": ""}}
        result = build_pages_json_from_azure_di(azure_di_data, "doc123")

        assert result["page_count"] == 0
        assert result["pages"] == []

    def test_schema_version(self):
        """Should include correct schema version."""
        azure_di_data = {
            "raw_azure_di_output": {
                "content": "Test content",
                "pages": [{"pageNumber": 1, "spans": [{"offset": 0, "length": 12}]}]
            }
        }
        result = build_pages_json_from_azure_di(azure_di_data, "doc123")
        assert result["schema_version"] == "doc_text_v1"

    def test_doc_id(self):
        """Should include doc_id."""
        azure_di_data = {
            "raw_azure_di_output": {
                "content": "Test",
                "pages": [{"pageNumber": 1, "spans": [{"offset": 0, "length": 4}]}]
            }
        }
        result = build_pages_json_from_azure_di(azure_di_data, "doc123")
        assert result["doc_id"] == "doc123"

    def test_source_is_azure_di(self):
        """Source should always be azure_di."""
        azure_di_data = {
            "raw_azure_di_output": {
                "content": "Test",
                "pages": [{"pageNumber": 1, "spans": [{"offset": 0, "length": 4}]}]
            }
        }
        result = build_pages_json_from_azure_di(azure_di_data, "doc123")
        assert result["pages"][0]["source"] == "azure_di"

    def test_md5_computed(self):
        """MD5 should be computed for page text."""
        import hashlib

        azure_di_data = {
            "raw_azure_di_output": {
                "content": "Test content",
                "pages": [{"pageNumber": 1, "spans": [{"offset": 0, "length": 12}]}]
            }
        }
        result = build_pages_json_from_azure_di(azure_di_data, "doc123")

        page = result["pages"][0]
        expected_md5 = hashlib.md5(page["text"].encode("utf-8")).hexdigest()
        assert page["text_md5"] == expected_md5

    def test_integration_multi_page(self):
        """Integration test with multi-page document."""
        azure_di_data = {
            "raw_azure_di_output": {
                "content": "Page one header.Page two body.Page three footer.",
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": 16}]},
                    {"pageNumber": 2, "spans": [{"offset": 16, "length": 14}]},
                    {"pageNumber": 3, "spans": [{"offset": 30, "length": 18}]},
                ]
            }
        }
        result = build_pages_json_from_azure_di(azure_di_data, "doc123")

        assert result["page_count"] == 3
        assert result["pages"][0]["page"] == 1
        assert result["pages"][1]["page"] == 2
        assert result["pages"][2]["page"] == 3
        assert "header" in result["pages"][0]["text"]
        assert "body" in result["pages"][1]["text"]
        assert "footer" in result["pages"][2]["text"]

    def test_page_break_markers_not_split_by_build_pages_json(self):
        """
        Regression test: build_pages_json does NOT split on <!-- PageBreak --> markers.

        This is the bug scenario. Azure DI produces <!-- PageBreak --> markers,
        but build_pages_json only looks for <!-- PageNumber="X" --> markers.
        Therefore, a multi-page document with only PageBreak markers would be
        treated as a single page by build_pages_json.

        This test documents the limitation and ensures we use
        build_pages_json_from_azure_di for Azure DI content.
        """
        # Content with PageBreak markers (what Azure DI produces)
        content = """Page one content.
<!-- PageBreak -->
Page two content.
<!-- PageBreak -->
Page three content."""

        # build_pages_json does NOT split on PageBreak (only PageNumber)
        result = build_pages_json(content, "doc123")

        # This is the bug: all pages collapsed into one
        assert result["page_count"] == 1
        assert "Page one" in result["pages"][0]["text"]
        assert "Page two" in result["pages"][0]["text"]
        assert "Page three" in result["pages"][0]["text"]

    def test_azure_di_spans_split_despite_pagebreak_markers(self):
        """
        Regression test: build_pages_json_from_azure_di correctly splits pages
        using spans, regardless of PageBreak markers in the text.

        This is the correct behavior when Azure DI data with spans is available.
        """
        # Content with PageBreak markers (as Azure DI produces them)
        content = """Page one content.
<!-- PageBreak -->
Page two content.
<!-- PageBreak -->
Page three content."""

        # Azure DI data with proper spans for each page
        azure_di_data = {
            "raw_azure_di_output": {
                "content": content,
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": 17}]},  # "Page one content."
                    {"pageNumber": 2, "spans": [{"offset": 36, "length": 17}]},  # "Page two content."
                    {"pageNumber": 3, "spans": [{"offset": 72, "length": 19}]},  # "Page three content."
                ]
            }
        }

        result = build_pages_json_from_azure_di(azure_di_data, "doc123")

        # This should correctly split into 3 pages
        assert result["page_count"] == 3
        assert result["pages"][0]["page"] == 1
        assert result["pages"][1]["page"] == 2
        assert result["pages"][2]["page"] == 3

    def test_nsa_guarantee_realistic_scenario(self):
        """
        Regression test: NSA Guarantee documents should be split correctly.

        This reproduces the real bug where a 12-page NSA Guarantee document
        was collapsed into 1 page because build_pages_json was used instead
        of build_pages_json_from_azure_di.
        """
        # Simplified version of NSA Guarantee document structure
        content = """# Spezifische Bedingungen der NSA Garantie
Policy: 624465
<!-- PageFooter="..." -->
<!-- PageBreak -->
## Abgedeckte Komponenten und Teile
Motor: Kolben, Zylinder...
<!-- PageFooter="..." -->
<!-- PageBreak -->
## Allgemeine Versicherungsbedingungen
AVB content here...
<!-- PageFooter="..." -->"""

        # Build Azure DI data with 3 pages
        page1_len = content.find("<!-- PageBreak -->")
        page2_start = page1_len + len("<!-- PageBreak -->\n")
        page2_end = content.find("<!-- PageBreak -->", page2_start)
        page3_start = page2_end + len("<!-- PageBreak -->\n")

        azure_di_data = {
            "raw_azure_di_output": {
                "content": content,
                "pages": [
                    {"pageNumber": 1, "spans": [{"offset": 0, "length": page1_len}]},
                    {"pageNumber": 2, "spans": [{"offset": page2_start, "length": page2_end - page2_start}]},
                    {"pageNumber": 3, "spans": [{"offset": page3_start, "length": len(content) - page3_start}]},
                ]
            }
        }

        # Using build_pages_json_from_azure_di should correctly split
        result = build_pages_json_from_azure_di(azure_di_data, "nsa_doc")

        assert result["page_count"] == 3
        assert "Spezifische Bedingungen" in result["pages"][0]["text"]
        assert "Abgedeckte Komponenten" in result["pages"][1]["text"]
        assert "Allgemeine Versicherungsbedingungen" in result["pages"][2]["text"]


class TestIngestionResultIntegration:
    """Test that the pipeline correctly uses Azure DI data for page splitting."""

    def test_ingestion_result_dataclass_exists(self):
        """IngestionResult should be importable from run module."""
        from context_builder.pipeline.run import IngestionResult

        result = IngestionResult(
            text_content="test",
            provider_name="azure-di",
            azure_di_data={"raw_azure_di_output": {"content": "test"}}
        )
        assert result.text_content == "test"
        assert result.provider_name == "azure-di"
        assert result.azure_di_data is not None

    def test_ingestion_result_without_azure_di_data(self):
        """IngestionResult should work without Azure DI data."""
        from context_builder.pipeline.run import IngestionResult

        result = IngestionResult(
            text_content="test content",
            provider_name="tesseract",
        )
        assert result.text_content == "test content"
        assert result.provider_name == "tesseract"
        assert result.azure_di_data is None
