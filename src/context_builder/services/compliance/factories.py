"""Factories for compliance record creation.

This module provides centralized factories for creating compliance records
with proper hash computation and ID generation. Using factories ensures
consistent record creation across the codebase.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from context_builder.schemas.decision_record import (
    DecisionOutcome,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
    EvidenceCitation,
    RuleTrace,
)


class DecisionRecordFactory:
    """Factory for creating DecisionRecord instances with proper hashing.

    This factory centralizes decision record creation and ensures:
    - Consistent ID generation (dec_<12-char-hex>)
    - Proper hash chain linking via previous_hash callback
    - Standardized timestamp formatting

    Usage:
        factory = DecisionRecordFactory(get_previous_hash=ledger.get_last_hash)
        record = factory.create_classification_decision(
            doc_type="invoice",
            confidence=0.95,
            ...
        )
    """

    def __init__(self, get_previous_hash: Callable[[], str]):
        """Initialize the factory.

        Args:
            get_previous_hash: Callable that returns the hash of the previous
                              record in the chain. Should return "GENESIS" if
                              no previous records exist.
        """
        self._get_previous_hash = get_previous_hash

    @staticmethod
    def generate_decision_id() -> str:
        """Generate a unique decision ID.

        Returns:
            Decision ID in format: dec_<12-char-hex>
        """
        return f"dec_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def compute_hash(record: DecisionRecord) -> str:
        """Compute SHA-256 hash of a decision record.

        The hash is computed over all fields except record_hash itself.
        This creates a tamper-evident seal on the record content.

        Args:
            record: The decision record to hash.

        Returns:
            Hex-encoded SHA-256 hash string.
        """
        # Create a copy of the record data without the hash field
        record_dict = record.model_dump()
        record_dict.pop("record_hash", None)

        # Serialize deterministically (sorted keys, no whitespace)
        serialized = json.dumps(record_dict, sort_keys=True, separators=(",", ":"), default=str)

        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _create_base_record(
        self,
        decision_type: DecisionType,
        rationale: DecisionRationale,
        outcome: DecisionOutcome,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version_bundle_id: Optional[str] = None,
        actor_type: str = "system",
        actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Create a base decision record with common fields.

        Args:
            decision_type: Type of decision being recorded.
            rationale: Explanation and evidence for the decision.
            outcome: Result of the decision.
            claim_id: Associated claim identifier.
            doc_id: Associated document identifier.
            run_id: Pipeline run identifier.
            version_bundle_id: Reference to version bundle snapshot.
            actor_type: Type of actor ('system' or 'human').
            actor_id: Identifier for the actor.
            metadata: Additional metadata.

        Returns:
            DecisionRecord with all common fields populated.
        """
        return DecisionRecord(
            decision_id=self.generate_decision_id(),
            decision_type=decision_type,
            created_at=datetime.utcnow().isoformat() + "Z",
            previous_hash=self._get_previous_hash(),
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            version_bundle_id=version_bundle_id,
            rationale=rationale,
            outcome=outcome,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata=metadata or {},
        )

    def create_classification_decision(
        self,
        doc_type: str,
        confidence: float,
        summary: str,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version_bundle_id: Optional[str] = None,
        llm_call_id: Optional[str] = None,
        language: Optional[str] = None,
        evidence_citations: Optional[List[EvidenceCitation]] = None,
        rule_traces: Optional[List[RuleTrace]] = None,
        actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Create a classification decision record.

        Args:
            doc_type: The classified document type.
            confidence: Classification confidence (0-1).
            summary: Human-readable summary of the classification rationale.
            claim_id: Associated claim identifier.
            doc_id: Associated document identifier.
            run_id: Pipeline run identifier.
            version_bundle_id: Reference to version bundle snapshot.
            llm_call_id: ID of the LLM call that produced this decision.
            language: Detected document language.
            evidence_citations: Source citations supporting the classification.
            rule_traces: Rules applied during classification.
            actor_id: Identifier for the actor (e.g., classifier name).
            metadata: Additional metadata.

        Returns:
            DecisionRecord for a classification decision.
        """
        rationale = DecisionRationale(
            summary=summary,
            confidence=confidence,
            rule_traces=rule_traces or [],
            evidence_citations=evidence_citations or [],
            llm_call_id=llm_call_id,
        )

        outcome = DecisionOutcome(
            doc_type=doc_type,
            doc_type_confidence=confidence,
            language=language,
        )

        return self._create_base_record(
            decision_type=DecisionType.CLASSIFICATION,
            rationale=rationale,
            outcome=outcome,
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            version_bundle_id=version_bundle_id,
            actor_id=actor_id or "openai_classifier",
            metadata=metadata,
        )

    def create_extraction_decision(
        self,
        fields_extracted: List[Dict[str, Any]],
        confidence: float,
        summary: str,
        quality_gate_status: Optional[str] = None,
        missing_required_fields: Optional[List[str]] = None,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version_bundle_id: Optional[str] = None,
        llm_call_id: Optional[str] = None,
        evidence_citations: Optional[List[EvidenceCitation]] = None,
        rule_traces: Optional[List[RuleTrace]] = None,
        actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Create an extraction decision record.

        Args:
            fields_extracted: List of extracted fields with values.
            confidence: Extraction confidence (0-1).
            summary: Human-readable summary of the extraction.
            quality_gate_status: Quality gate result (pass/warn/fail).
            missing_required_fields: Required fields that were not extracted.
            claim_id: Associated claim identifier.
            doc_id: Associated document identifier.
            run_id: Pipeline run identifier.
            version_bundle_id: Reference to version bundle snapshot.
            llm_call_id: ID of the LLM call that produced this decision.
            evidence_citations: Source citations for extracted values.
            rule_traces: Rules applied during extraction.
            actor_id: Identifier for the actor (e.g., extractor name).
            metadata: Additional metadata.

        Returns:
            DecisionRecord for an extraction decision.
        """
        rationale = DecisionRationale(
            summary=summary,
            confidence=confidence,
            rule_traces=rule_traces or [],
            evidence_citations=evidence_citations or [],
            llm_call_id=llm_call_id,
        )

        outcome = DecisionOutcome(
            fields_extracted=fields_extracted,
            quality_gate_status=quality_gate_status,
            missing_required_fields=missing_required_fields,
        )

        return self._create_base_record(
            decision_type=DecisionType.EXTRACTION,
            rationale=rationale,
            outcome=outcome,
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            version_bundle_id=version_bundle_id,
            actor_id=actor_id or "generic_extractor",
            metadata=metadata,
        )

    def create_quality_gate_decision(
        self,
        status: str,
        confidence: float,
        summary: str,
        missing_required_fields: Optional[List[str]] = None,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version_bundle_id: Optional[str] = None,
        rule_traces: Optional[List[RuleTrace]] = None,
        actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Create a quality gate decision record.

        Args:
            status: Quality gate result (pass/warn/fail).
            confidence: Confidence in the gate decision (0-1).
            summary: Human-readable summary of the gate decision.
            missing_required_fields: Required fields that are missing.
            claim_id: Associated claim identifier.
            doc_id: Associated document identifier.
            run_id: Pipeline run identifier.
            version_bundle_id: Reference to version bundle snapshot.
            rule_traces: Rules applied during quality gate evaluation.
            actor_id: Identifier for the actor.
            metadata: Additional metadata.

        Returns:
            DecisionRecord for a quality gate decision.
        """
        rationale = DecisionRationale(
            summary=summary,
            confidence=confidence,
            rule_traces=rule_traces or [],
            evidence_citations=[],
        )

        outcome = DecisionOutcome(
            quality_gate_status=status,
            missing_required_fields=missing_required_fields,
        )

        return self._create_base_record(
            decision_type=DecisionType.QUALITY_GATE,
            rationale=rationale,
            outcome=outcome,
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            version_bundle_id=version_bundle_id,
            actor_id=actor_id or "quality_gate",
            metadata=metadata,
        )

    def create_human_review_decision(
        self,
        summary: str,
        field_corrections: Optional[List[Dict[str, Any]]] = None,
        doc_type_correction: Optional[str] = None,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version_bundle_id: Optional[str] = None,
        evidence_citations: Optional[List[EvidenceCitation]] = None,
        actor_id: Optional[str] = None,
        notes: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Create a human review decision record.

        Args:
            summary: Human-readable summary of the review.
            field_corrections: Fields corrected by the reviewer.
            doc_type_correction: Corrected document type if overridden.
            claim_id: Associated claim identifier.
            doc_id: Associated document identifier.
            run_id: Pipeline run identifier.
            version_bundle_id: Reference to version bundle snapshot.
            evidence_citations: Source citations for corrections.
            actor_id: Identifier for the human reviewer.
            notes: Additional reviewer notes.
            metadata: Additional metadata.

        Returns:
            DecisionRecord for a human review decision.
        """
        rationale = DecisionRationale(
            summary=summary,
            confidence=1.0,  # Human review is authoritative
            rule_traces=[],
            evidence_citations=evidence_citations or [],
            notes=notes,
        )

        outcome = DecisionOutcome(
            field_corrections=field_corrections,
            doc_type_correction=doc_type_correction,
        )

        return self._create_base_record(
            decision_type=DecisionType.HUMAN_REVIEW,
            rationale=rationale,
            outcome=outcome,
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            version_bundle_id=version_bundle_id,
            actor_type="human",
            actor_id=actor_id,
            metadata=metadata,
        )

    def create_override_decision(
        self,
        original_value: Any,
        override_value: Any,
        override_reason: str,
        summary: str,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        version_bundle_id: Optional[str] = None,
        evidence_citations: Optional[List[EvidenceCitation]] = None,
        actor_type: str = "human",
        actor_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionRecord:
        """Create an override decision record.

        Args:
            original_value: The original value being overridden.
            override_value: The new value after override.
            override_reason: Reason for the override.
            summary: Human-readable summary of the override.
            claim_id: Associated claim identifier.
            doc_id: Associated document identifier.
            run_id: Pipeline run identifier.
            version_bundle_id: Reference to version bundle snapshot.
            evidence_citations: Source citations supporting the override.
            actor_type: Type of actor ('system' or 'human').
            actor_id: Identifier for the actor.
            metadata: Additional metadata.

        Returns:
            DecisionRecord for an override decision.
        """
        rationale = DecisionRationale(
            summary=summary,
            confidence=1.0,  # Overrides are explicit decisions
            rule_traces=[],
            evidence_citations=evidence_citations or [],
            notes=override_reason,
        )

        outcome = DecisionOutcome(
            original_value=original_value,
            override_value=override_value,
            override_reason=override_reason,
        )

        return self._create_base_record(
            decision_type=DecisionType.OVERRIDE,
            rationale=rationale,
            outcome=outcome,
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            version_bundle_id=version_bundle_id,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata=metadata,
        )
