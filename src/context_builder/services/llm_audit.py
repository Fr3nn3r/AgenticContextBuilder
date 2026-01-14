"""LLM Audit Service for capturing all LLM API calls.

This module provides a wrapper around OpenAI API calls that logs every call
with full context for compliance audit trails. Each call is recorded with
prompts, responses, token usage, latency, and decision context linking.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMCallRecord:
    """Record of a single LLM API call.

    Captures all information needed for compliance audit:
    - Full request (model, params, messages)
    - Full response (content, finish reason)
    - Token usage and cost estimation
    - Timing and latency
    - Decision context linking
    """

    # Identity
    call_id: str = field(default_factory=lambda: f"llm_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # Request details
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    response_format: Optional[Dict[str, Any]] = None

    # Response details
    response_content: Optional[str] = None
    finish_reason: Optional[str] = None
    response_raw: Optional[Dict[str, Any]] = None

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # Timing
    latency_ms: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Decision context for linking
    decision_id: Optional[str] = None
    claim_id: Optional[str] = None
    doc_id: Optional[str] = None
    run_id: Optional[str] = None
    call_purpose: Optional[str] = None  # "classification", "extraction", "vision_ocr"

    # Retry tracking
    attempt_number: int = 1
    is_retry: bool = False
    previous_call_id: Optional[str] = None

    # Error tracking
    error: Optional[str] = None
    error_type: Optional[str] = None


class LLMAuditService:
    """Service for logging LLM API calls to JSONL file.

    Provides append-only storage for LLM call records with atomic writes.
    """

    def __init__(self, storage_dir: Path):
        """Initialize the LLM audit service.

        Args:
            storage_dir: Directory for storing the audit log (e.g., output/logs/)
        """
        self.storage_dir = Path(storage_dir)
        self.log_file = self.storage_dir / "llm_calls.jsonl"

    def _ensure_dir(self) -> None:
        """Ensure storage directory exists."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        """Log an LLM call record.

        Args:
            record: The call record to log

        Returns:
            The record (unchanged)
        """
        self._ensure_dir()

        # Ensure call_id is set
        if not record.call_id:
            record.call_id = f"llm_{uuid.uuid4().hex[:12]}"

        # Serialize the record
        line = json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n"

        # Write atomically
        tmp_file = self.log_file.with_suffix(".jsonl.tmp")
        try:
            existing_content = ""
            if self.log_file.exists():
                with open(self.log_file, "r", encoding="utf-8") as f:
                    existing_content = f.read()

            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(existing_content)
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

            tmp_file.replace(self.log_file)
            logger.debug(f"Logged LLM call {record.call_id}")

        except IOError as e:
            logger.warning(f"Failed to log LLM call: {e}")
            if tmp_file.exists():
                tmp_file.unlink()

        return record

    def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]:
        """Get a call record by ID.

        Args:
            call_id: The call identifier

        Returns:
            LLMCallRecord if found, None otherwise
        """
        if not self.log_file.exists():
            return None

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("call_id") == call_id:
                            return LLMCallRecord(**data)
                    except (json.JSONDecodeError, TypeError):
                        continue
        except IOError as e:
            logger.error(f"Failed to read LLM log: {e}")

        return None

    def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]:
        """Get all calls linked to a decision.

        Args:
            decision_id: The decision identifier

        Returns:
            List of matching call records
        """
        results = []
        if not self.log_file.exists():
            return results

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("decision_id") == decision_id:
                            results.append(LLMCallRecord(**data))
                    except (json.JSONDecodeError, TypeError):
                        continue
        except IOError as e:
            logger.error(f"Failed to read LLM log: {e}")

        return results


# Global singleton for convenience
_default_service: Optional[LLMAuditService] = None


def get_llm_audit_service(storage_dir: Optional[Path] = None) -> LLMAuditService:
    """Get or create the default LLM audit service.

    Args:
        storage_dir: Optional directory override

    Returns:
        LLMAuditService instance
    """
    global _default_service

    if storage_dir:
        return LLMAuditService(storage_dir)

    if _default_service is None:
        default_dir = Path("output/logs")
        _default_service = LLMAuditService(default_dir)

    return _default_service


class AuditedOpenAIClient:
    """Wrapper around OpenAI client that logs all calls.

    This wrapper intercepts all chat completion calls and logs them
    with full context for compliance audit trails.

    Usage:
        from openai import OpenAI
        client = OpenAI()
        audited = AuditedOpenAIClient(client, audit_service)

        # Set context for linking
        audited.set_context(claim_id="CLM001", doc_id="doc_abc")

        # Make calls as normal
        response = audited.chat_completions_create(
            model="gpt-4o",
            messages=[...],
        )
    """

    def __init__(
        self,
        client: Any,
        audit_service: Optional[LLMAuditService] = None,
        storage_dir: Optional[Path] = None,
    ):
        """Initialize the audited client wrapper.

        Args:
            client: The underlying OpenAI client
            audit_service: Optional audit service (creates default if None)
            storage_dir: Optional storage directory for audit logs
        """
        self.client = client
        self.audit_service = audit_service or get_llm_audit_service(storage_dir)

        # Context for linking calls to decisions
        self._claim_id: Optional[str] = None
        self._doc_id: Optional[str] = None
        self._run_id: Optional[str] = None
        self._decision_id: Optional[str] = None
        self._call_purpose: Optional[str] = None

        # Retry tracking
        self._attempt_number: int = 1
        self._previous_call_id: Optional[str] = None

    def set_context(
        self,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        call_purpose: Optional[str] = None,
    ) -> "AuditedOpenAIClient":
        """Set context for linking calls to decisions.

        Args:
            claim_id: Claim identifier
            doc_id: Document identifier
            run_id: Pipeline run identifier
            decision_id: Decision identifier for linking
            call_purpose: Purpose of the call (e.g., "classification")

        Returns:
            Self for chaining
        """
        if claim_id is not None:
            self._claim_id = claim_id
        if doc_id is not None:
            self._doc_id = doc_id
        if run_id is not None:
            self._run_id = run_id
        if decision_id is not None:
            self._decision_id = decision_id
        if call_purpose is not None:
            self._call_purpose = call_purpose
        return self

    def clear_context(self) -> "AuditedOpenAIClient":
        """Clear all context."""
        self._claim_id = None
        self._doc_id = None
        self._run_id = None
        self._decision_id = None
        self._call_purpose = None
        self._attempt_number = 1
        self._previous_call_id = None
        return self

    def mark_retry(self, previous_call_id: str) -> "AuditedOpenAIClient":
        """Mark the next call as a retry of a previous call.

        Args:
            previous_call_id: ID of the call being retried

        Returns:
            Self for chaining
        """
        self._attempt_number += 1
        self._previous_call_id = previous_call_id
        return self

    def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Create a chat completion with audit logging.

        Args:
            model: Model name
            messages: Chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            response_format: Response format specification
            **kwargs: Additional arguments passed to the client

        Returns:
            The chat completion response
        """
        call_id = f"llm_{uuid.uuid4().hex[:12]}"
        start_time = datetime.utcnow()
        start_ts = time.time()

        # Create the record
        record = LLMCallRecord(
            call_id=call_id,
            created_at=start_time.isoformat() + "Z",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=messages,
            response_format=response_format,
            start_time=start_time.isoformat() + "Z",
            claim_id=self._claim_id,
            doc_id=self._doc_id,
            run_id=self._run_id,
            decision_id=self._decision_id,
            call_purpose=self._call_purpose,
            attempt_number=self._attempt_number,
            is_retry=self._previous_call_id is not None,
            previous_call_id=self._previous_call_id,
        )

        try:
            # Make the actual API call
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                **kwargs,
            )

            end_time = datetime.utcnow()
            latency_ms = int((time.time() - start_ts) * 1000)

            # Extract response details
            record.response_content = response.choices[0].message.content if response.choices else None
            record.finish_reason = response.choices[0].finish_reason if response.choices else None
            record.end_time = end_time.isoformat() + "Z"
            record.latency_ms = latency_ms

            # Token usage
            if response.usage:
                record.prompt_tokens = response.usage.prompt_tokens
                record.completion_tokens = response.usage.completion_tokens
                record.total_tokens = response.usage.total_tokens

            # Log the successful call
            self.audit_service.log_call(record)

            # Reset retry state
            self._previous_call_id = None
            self._attempt_number = 1

            return response

        except Exception as e:
            end_time = datetime.utcnow()
            latency_ms = int((time.time() - start_ts) * 1000)

            record.end_time = end_time.isoformat() + "Z"
            record.latency_ms = latency_ms
            record.error = str(e)
            record.error_type = type(e).__name__

            # Log the failed call
            self.audit_service.log_call(record)

            # Store call_id for retry tracking
            self._previous_call_id = call_id

            raise

    def get_last_call_id(self) -> Optional[str]:
        """Get the ID of the last call made (for retry linking)."""
        return self._previous_call_id


def create_audited_client(
    storage_dir: Optional[Path] = None,
) -> AuditedOpenAIClient:
    """Create an audited OpenAI client.

    Args:
        storage_dir: Optional storage directory for audit logs

    Returns:
        AuditedOpenAIClient wrapping a new OpenAI client
    """
    from openai import OpenAI

    client = OpenAI()
    audit_service = get_llm_audit_service(storage_dir)
    return AuditedOpenAIClient(client, audit_service)
