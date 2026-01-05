"""Base classes and factory for document field extractors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Type, Any
import re

from context_builder.schemas.extraction_result import (
    ExtractionResult,
    ExtractedField,
    FieldProvenance,
    QualityGate,
    ExtractionRunMetadata,
    DocumentMetadata,
    PageContent,
)
from context_builder.extraction.page_parser import ParsedPage, find_text_position
from context_builder.extraction.spec_loader import DocTypeSpec, get_spec


@dataclass
class CandidateSpan:
    """A text span that may contain a field value."""
    page: int
    text: str
    char_start: int
    char_end: int
    hint_matched: str


class FieldExtractor(ABC):
    """
    Abstract base class for document-type-specific extractors.

    Subclasses implement extraction logic for specific document types
    (loss_notice, police_report, insurance_policy).
    """

    def __init__(self, spec: DocTypeSpec, model: str = "gpt-4o"):
        """
        Initialize extractor with document type spec.

        Args:
            spec: DocTypeSpec defining fields and rules
            model: LLM model to use for extraction
        """
        self.spec = spec
        self.model = model

    @property
    def doc_type(self) -> str:
        """Document type this extractor handles."""
        return self.spec.doc_type

    @abstractmethod
    def extract(
        self,
        pages: List[PageContent],
        doc_meta: DocumentMetadata,
        run_metadata: ExtractionRunMetadata,
    ) -> ExtractionResult:
        """
        Extract fields from document pages.

        Args:
            pages: List of parsed page content
            doc_meta: Document metadata
            run_metadata: Run metadata for tracking

        Returns:
            ExtractionResult with all extracted fields and quality gate
        """
        pass

    def _find_candidate_spans(
        self,
        pages: List[PageContent],
        hints: List[str],
        window_size: int = 800,
    ) -> List[CandidateSpan]:
        """
        Find text spans around hint keywords for targeted extraction.

        Args:
            pages: Document pages
            hints: Keywords to search for
            window_size: Characters to extract around each hit

        Returns:
            List of candidate spans with context
        """
        candidates = []
        half_window = window_size // 2

        for page in pages:
            page_text = page.text
            page_lower = page_text.lower()

            for hint in hints:
                hint_lower = hint.lower()
                start_pos = 0

                # Find all occurrences of this hint
                while True:
                    pos = page_lower.find(hint_lower, start_pos)
                    if pos < 0:
                        break

                    # Extract window around the hint
                    window_start = max(0, pos - half_window)
                    window_end = min(len(page_text), pos + len(hint) + half_window)

                    candidates.append(CandidateSpan(
                        page=page.page,
                        text=page_text[window_start:window_end],
                        char_start=window_start,
                        char_end=window_end,
                        hint_matched=hint,
                    ))

                    start_pos = pos + 1

        return candidates

    def _find_field_candidates(
        self,
        pages: List[PageContent],
        field_name: str,
    ) -> List[CandidateSpan]:
        """Find candidates for a specific field using its hints."""
        hints = self.spec.get_field_hints(field_name)
        return self._find_candidate_spans(pages, hints)

    def _build_quality_gate(
        self,
        fields: List[ExtractedField],
    ) -> QualityGate:
        """
        Evaluate quality gate based on extracted fields.

        Args:
            fields: List of extracted fields

        Returns:
            QualityGate with status and reasons
        """
        reasons = []
        missing_required = []

        # Check required fields
        for field_name in self.spec.required_fields:
            field = next((f for f in fields if f.name == field_name), None)
            if not field or field.status == "missing":
                missing_required.append(field_name)
                reasons.append(f"Missing required field: {field_name}")

        # Calculate metrics
        present_fields = [f for f in fields if f.status == "present"]
        fields_with_evidence = [f for f in present_fields if f.provenance]

        required_present = len([
            f for f in present_fields
            if f.name in self.spec.required_fields
        ])
        required_total = len(self.spec.required_fields)
        required_ratio = required_present / required_total if required_total > 0 else 1.0

        evidence_rate = (
            len(fields_with_evidence) / len(present_fields)
            if present_fields else 0.0
        )

        # Determine status
        if missing_required:
            status = "fail"
        elif evidence_rate < 0.7:
            status = "warn"
            reasons.append(f"Low evidence rate: {evidence_rate:.1%}")
        else:
            status = "pass"

        return QualityGate(
            status=status,
            reasons=reasons,
            missing_required_fields=missing_required,
            needs_vision_fallback=False,  # Can be set by subclass
        )

    def _create_missing_field(self, field_name: str) -> ExtractedField:
        """Create an ExtractedField for a field that wasn't found."""
        return ExtractedField(
            name=field_name,
            value=None,
            normalized_value=None,
            confidence=0.0,
            status="missing",
            provenance=[],
            value_is_placeholder=False,
        )


class ExtractorFactory:
    """
    Factory for creating document-type-specific extractors.

    Uses registry pattern for extensibility.
    """

    _registry: Dict[str, Type[FieldExtractor]] = {}

    @classmethod
    def register(cls, doc_type: str, extractor_class: Type[FieldExtractor]):
        """
        Register an extractor class for a document type.

        Args:
            doc_type: Document type name
            extractor_class: Extractor class to register
        """
        cls._registry[doc_type] = extractor_class

    @classmethod
    def create(cls, doc_type: str, **kwargs) -> FieldExtractor:
        """
        Create an extractor for the given document type.

        Args:
            doc_type: Document type to create extractor for
            **kwargs: Additional arguments passed to extractor

        Returns:
            FieldExtractor instance

        Raises:
            ValueError: If no extractor registered for doc_type
        """
        if doc_type not in cls._registry:
            available = list(cls._registry.keys())
            raise ValueError(
                f"No extractor registered for doc_type '{doc_type}'. "
                f"Available: {available}"
            )

        extractor_class = cls._registry[doc_type]
        spec = get_spec(doc_type)
        return extractor_class(spec=spec, **kwargs)

    @classmethod
    def list_available(cls) -> List[str]:
        """List all registered document types."""
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, doc_type: str) -> bool:
        """Check if a document type has a registered extractor."""
        return doc_type in cls._registry


def generate_run_id() -> str:
    """Generate a unique run ID based on current timestamp."""
    return datetime.utcnow().strftime("run_%Y-%m-%dT%H:%M:%SZ")
