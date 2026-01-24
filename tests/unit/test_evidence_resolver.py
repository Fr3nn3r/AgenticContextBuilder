"""Tests for evidence offset resolution."""

import pytest

from context_builder.extraction.evidence_resolver import (
    resolve_evidence_offsets,
    resolve_single_provenance,
)
from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    PageContent,
    DocumentMetadata,
    ExtractionRunMetadata,
    QualityGate,
)


def make_page(page_num: int, text: str) -> PageContent:
    """Create a test page."""
    import hashlib
    return PageContent(
        page=page_num,
        text=text,
        text_md5=hashlib.md5(text.encode()).hexdigest(),
    )


def make_field(
    name: str,
    value: str,
    provenance: list[FieldProvenance] | None = None,
) -> ExtractedField:
    """Create a test field."""
    return ExtractedField(
        name=name,
        value=value,
        normalized_value=value,
        confidence=0.9,
        status="present",
        provenance=provenance or [],
        value_is_placeholder=False,
        has_verified_evidence=False,
    )


def make_result(
    fields: list[ExtractedField],
    pages: list[PageContent],
) -> ExtractionResult:
    """Create a test extraction result."""
    return ExtractionResult(
        schema_version="extraction_result_v1",
        run=ExtractionRunMetadata(
            run_id="test_run",
            extractor_version="v1.0.0",
            model="gpt-4o",
            prompt_version="v1",
        ),
        doc=DocumentMetadata(
            doc_id="doc_001",
            claim_id="claim_001",
            doc_type="test_doc",
            doc_type_confidence=0.95,
            language="en",
            page_count=len(pages),
        ),
        pages=pages,
        fields=fields,
        quality_gate=QualityGate(status="pass"),
    )


class TestResolveEvidenceOffsets:
    """Tests for resolve_evidence_offsets function."""

    def test_resolves_zero_offsets(self):
        """Should resolve 0/0 offsets when quote is found in page."""
        pages = [make_page(1, "This is some test text with a quote here.")]
        prov = FieldProvenance(
            page=1,
            method="llm_parse",
            text_quote="test text",
            char_start=0,
            char_end=0,
        )
        field = make_field("test_field", "test", [prov])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].char_start == 13
        assert result.fields[0].provenance[0].char_end == 22
        assert result.fields[0].provenance[0].match_quality == "resolved"
        assert result.fields[0].has_verified_evidence is True

    def test_preserves_existing_offsets(self):
        """Should not modify already-set offsets."""
        pages = [make_page(1, "Some text here")]
        prov = FieldProvenance(
            page=1,
            method="di_text",
            text_quote="text",
            char_start=5,
            char_end=9,
        )
        field = make_field("test_field", "text", [prov])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].char_start == 5
        assert result.fields[0].provenance[0].char_end == 9
        assert result.fields[0].provenance[0].match_quality == "exact"
        assert result.fields[0].has_verified_evidence is True

    def test_handles_placeholder_quotes(self):
        """Should mark placeholder quotes and not verify evidence."""
        pages = [make_page(1, "Some content")]
        prov = FieldProvenance(
            page=1,
            method="llm_parse",
            text_quote="[Component list extraction]",
            char_start=0,
            char_end=0,
        )
        field = make_field("components", "data", [prov])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].match_quality == "placeholder"
        assert result.fields[0].has_verified_evidence is False

    def test_handles_not_found_quotes(self):
        """Should mark quotes not found in page."""
        pages = [make_page(1, "Completely different text")]
        prov = FieldProvenance(
            page=1,
            method="llm_parse",
            text_quote="nonexistent quote",
            char_start=0,
            char_end=0,
        )
        field = make_field("test_field", "value", [prov])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].match_quality == "not_found"
        assert result.fields[0].has_verified_evidence is False

    def test_handles_missing_page(self):
        """Should mark page_not_found when page doesn't exist."""
        pages = [make_page(1, "Page one text")]
        prov = FieldProvenance(
            page=5,  # Page 5 doesn't exist
            method="llm_parse",
            text_quote="some quote",
            char_start=0,
            char_end=0,
        )
        field = make_field("test_field", "value", [prov])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].match_quality == "page_not_found"
        assert result.fields[0].has_verified_evidence is False

    def test_multiple_provenances(self):
        """Should handle fields with multiple provenance entries."""
        pages = [
            make_page(1, "First page with value1"),
            make_page(2, "Second page with value2"),
        ]
        field = make_field("test_field", "values", [
            FieldProvenance(
                page=1,
                method="llm_parse",
                text_quote="value1",
                char_start=0,
                char_end=0,
            ),
            FieldProvenance(
                page=2,
                method="llm_parse",
                text_quote="value2",
                char_start=0,
                char_end=0,
            ),
        ])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].match_quality == "resolved"
        assert result.fields[0].provenance[1].match_quality == "resolved"
        assert result.fields[0].has_verified_evidence is True

    def test_case_insensitive_match(self):
        """Should match quotes case-insensitively."""
        pages = [make_page(1, "Text with UPPERCASE content")]
        prov = FieldProvenance(
            page=1,
            method="llm_parse",
            text_quote="uppercase",
            char_start=0,
            char_end=0,
        )
        field = make_field("test_field", "value", [prov])
        result = make_result([field], pages)

        result = resolve_evidence_offsets(result)

        assert result.fields[0].provenance[0].match_quality == "resolved"
        assert result.fields[0].has_verified_evidence is True


class TestResolveSingleProvenance:
    """Tests for resolve_single_provenance function."""

    def test_resolves_in_specified_page(self):
        """Should find quote in the specified page."""
        pages = [
            make_page(1, "Page one content"),
            make_page(2, "Page two with target text"),
        ]
        prov = FieldProvenance(
            page=2,
            method="llm_parse",
            text_quote="target text",
            char_start=0,
            char_end=0,
        )

        prov = resolve_single_provenance(prov, pages)

        assert prov.char_start == 14
        assert prov.char_end == 25
        assert prov.match_quality == "resolved"
        assert prov.page == 2

    def test_fallback_to_other_pages(self):
        """Should search other pages if not found in specified page."""
        pages = [
            make_page(1, "Page one with the quote"),
            make_page(2, "Page two no match"),
        ]
        prov = FieldProvenance(
            page=2,  # Wrong page
            method="llm_parse",
            text_quote="the quote",
            char_start=0,
            char_end=0,
        )

        prov = resolve_single_provenance(prov, pages)

        assert prov.page == 1  # Corrected to page 1
        assert prov.match_quality == "resolved_different_page"

    def test_preserves_existing_valid_offsets(self):
        """Should not modify provenance with valid offsets."""
        pages = [make_page(1, "Some text")]
        prov = FieldProvenance(
            page=1,
            method="di_text",
            text_quote="text",
            char_start=5,
            char_end=9,
        )

        result = resolve_single_provenance(prov, pages)

        assert result.char_start == 5
        assert result.char_end == 9
        assert result.match_quality == "exact"
