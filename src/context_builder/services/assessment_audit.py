"""Assessment audit helpers for token tracking and compliance logging.

This module provides helpers to integrate assessment LLM calls with the
compliance system, ensuring tokens are tracked in llm_calls.jsonl and
assessment decisions are logged to the compliance ledger.

Usage:
    from context_builder.services.assessment_audit import (
        create_assessment_client,
        log_assessment_decision,
    )

    # Create audited client
    client = create_assessment_client(claim_id="65258")
    response = client.chat_completions_create(...)
    call_id = client.get_call_id()

    # Log decision
    log_assessment_decision(
        claim_id="65258",
        decision="APPROVE",
        confidence_score=0.95,
        payout={"final_payout": 1500, "currency": "CHF"},
        checks=[{"check_name": "coverage", "result": "PASS"}],
        llm_call_id=call_id,
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from context_builder.schemas.decision_record import (
    DecisionOutcome,
    DecisionRationale,
    DecisionRecord,
    DecisionType,
)
from context_builder.services.compliance.factories import DecisionRecordFactory
from context_builder.services.compliance.file import FileDecisionStorage
from context_builder.services.llm_audit import (
    AuditedOpenAIClient,
    create_audited_client,
)
from context_builder.storage.workspace_paths import get_workspace_logs_dir

logger = logging.getLogger(__name__)


def create_assessment_client(
    claim_id: str,
    run_id: Optional[str] = None,
) -> AuditedOpenAIClient:
    """Create an audited OpenAI client configured for assessment calls.

    The client will automatically log all LLM calls to llm_calls.jsonl
    with the appropriate context (claim_id, call_purpose="assessment").

    Args:
        claim_id: The claim ID being assessed.
        run_id: Optional run identifier for grouping calls.

    Returns:
        AuditedOpenAIClient configured for assessment use.

    Example:
        client = create_assessment_client(claim_id="65258")
        response = client.chat_completions_create(
            model="gpt-4o",
            messages=[...],
            temperature=0.2,
            max_tokens=8192,
        )
        call_id = client.get_call_id()  # Use for decision linking
    """
    client = create_audited_client()
    client.set_context(
        claim_id=claim_id,
        run_id=run_id,
        call_purpose="assessment",
    )
    logger.debug(f"Created assessment client for claim {claim_id}")
    return client


def log_assessment_decision(
    claim_id: str,
    decision: str,
    confidence_score: float,
    payout: Dict[str, Any],
    checks: List[Dict[str, Any]],
    llm_call_id: Optional[str] = None,
    rationale_summary: Optional[str] = None,
    run_id: Optional[str] = None,
    version_bundle_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DecisionRecord:
    """Log an assessment decision to the compliance ledger.

    Creates a DecisionRecord with type ASSESSMENT and appends it to
    decisions.jsonl with proper hash chain linking.

    Args:
        claim_id: The claim ID that was assessed.
        decision: The assessment decision (APPROVE/REJECT/REFER_TO_HUMAN).
        confidence_score: Confidence in the decision (0-1).
        payout: Payout calculation details (final_payout, currency, etc.).
        checks: List of checks performed with results.
        llm_call_id: Optional ID of the LLM call that produced this decision.
        rationale_summary: Human-readable summary of the decision rationale.
        run_id: Optional run identifier.
        version_bundle_id: Optional version bundle reference.
        metadata: Additional metadata to include.

    Returns:
        The DecisionRecord that was logged.

    Example:
        record = log_assessment_decision(
            claim_id="65258",
            decision="APPROVE",
            confidence_score=0.95,
            payout={"final_payout": 1500, "currency": "CHF"},
            checks=[
                {"check_name": "coverage_validation", "result": "PASS"},
                {"check_name": "fraud_indicators", "result": "PASS"},
            ],
            llm_call_id="llm_abc123def456",
            rationale_summary="All checks passed, claim approved for payout.",
        )
    """
    logs_dir = get_workspace_logs_dir()
    storage = FileDecisionStorage(logs_dir)
    factory = DecisionRecordFactory(get_previous_hash=storage.get_last_hash)

    # Build the summary if not provided
    if rationale_summary is None:
        rationale_summary = f"Assessment decision: {decision} (confidence: {confidence_score:.2f})"

    # Build llm_call_ids list
    llm_call_ids = [llm_call_id] if llm_call_id else []

    # Create rationale
    rationale = DecisionRationale(
        summary=rationale_summary,
        confidence=confidence_score,
        llm_call_ids=llm_call_ids,
    )

    # Create outcome with assessment-specific fields
    outcome = DecisionOutcome(
        assessment_decision=decision,
        assessment_payout=payout,
        assessment_checks=checks,
        assessment_confidence=confidence_score,
    )

    # Create the decision record
    record = DecisionRecord(
        decision_id=factory.generate_decision_id(),
        decision_type=DecisionType.ASSESSMENT,
        claim_id=claim_id,
        run_id=run_id,
        version_bundle_id=version_bundle_id,
        rationale=rationale,
        outcome=outcome,
        actor_type="system",
        actor_id="assessment_agent",
        metadata=metadata or {},
    )

    # Append to storage (this computes hash chain)
    record = storage.append(record)

    logger.info(
        f"Logged assessment decision for claim {claim_id}: "
        f"{decision} (confidence: {confidence_score:.2f}, "
        f"payout: {payout.get('final_payout', 'N/A')} {payout.get('currency', '')})"
    )

    return record
