"""LLM Audit Service for capturing all LLM API calls.

This module provides the LLMAuditService facade class and AuditedOpenAIClient
wrapper for logging LLM calls with full context for compliance audit trails.

For new code, prefer using FileLLMCallStorage directly via dependency injection:

    from context_builder.services.compliance import FileLLMCallStorage, LLMCallSink

    def make_calls(sink: LLMCallSink):
        sink.log_call(record)
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

# Import LLMCallRecord and InjectedContext from their canonical location in schemas
from context_builder.schemas.llm_call_record import (
    InjectedContext,
    LLMCallRecord,
)
from context_builder.services.compliance.file import FileLLMCallStorage
from context_builder.storage.workspace_paths import get_workspace_logs_dir

if TYPE_CHECKING:
    from context_builder.services.compliance.interfaces import LLMCallSink


class LLMAuditService:
    """Service for logging LLM API calls to JSONL file.

    This class is a facade that maintains the existing API while delegating
    to FileLLMCallStorage. For new code, prefer injecting LLMCallSink
    interface directly.

    Usage:
        service = LLMAuditService(Path("output/logs"))
        service.log_call(record)
    """

    def __init__(self, storage_dir: Path):
        """Initialize the LLM audit service.

        Args:
            storage_dir: Directory for storing the audit log (e.g., output/logs/)
        """
        self.storage_dir = Path(storage_dir)
        self._storage = FileLLMCallStorage(storage_dir)
        # Expose log_file for backwards compatibility
        self.log_file = self._storage.storage_path

    def log_call(self, record: LLMCallRecord) -> LLMCallRecord:
        """Log an LLM call record.

        Args:
            record: The call record to log

        Returns:
            The record (with call_id if generated)
        """
        return self._storage.log_call(record)

    def get_by_id(self, call_id: str) -> Optional[LLMCallRecord]:
        """Get a call record by ID.

        Args:
            call_id: The call identifier

        Returns:
            LLMCallRecord if found, None otherwise
        """
        return self._storage.get_by_id(call_id)

    def query_by_decision(self, decision_id: str) -> List[LLMCallRecord]:
        """Get all calls linked to a decision.

        Args:
            decision_id: The decision identifier

        Returns:
            List of matching call records
        """
        return self._storage.query_by_decision(decision_id)


# Global singleton for convenience
_default_service: Optional[LLMAuditService] = None


def get_llm_audit_service(storage_dir: Optional[Path] = None) -> LLMAuditService:
    """Get or create the default LLM audit service.

    When no storage_dir is provided, uses the active workspace's logs directory
    from .contextbuilder/workspaces.json. Falls back to output/logs only if
    no workspace is configured.

    Args:
        storage_dir: Optional directory override

    Returns:
        LLMAuditService instance
    """
    global _default_service

    if storage_dir:
        return LLMAuditService(storage_dir)

    if _default_service is None:
        # Use workspace-aware path instead of hardcoded output/logs
        default_dir = get_workspace_logs_dir()
        _default_service = LLMAuditService(default_dir)

    return _default_service


def reset_llm_audit_service() -> None:
    """Reset the global LLM audit service singleton.

    Call this after workspace switch to ensure the service
    is recreated with the new workspace's logs directory.
    """
    global _default_service
    _default_service = None


class AuditedOpenAIClient:
    """Wrapper around OpenAI client that logs all calls.

    This wrapper intercepts all chat completion calls and logs them
    with full context for compliance audit trails.

    The client accepts either an LLMAuditService (for backwards compatibility)
    or any LLMCallSink implementation (for interface-based injection).

    Usage:
        from openai import OpenAI
        client = OpenAI()

        # Option 1: With LLMAuditService (backwards compatible)
        audited = AuditedOpenAIClient(client, audit_service)

        # Option 2: With LLMCallSink interface (preferred for new code)
        from context_builder.services.compliance import FileLLMCallStorage
        sink = FileLLMCallStorage(Path("output/logs"))
        audited = AuditedOpenAIClient(client, sink)

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
        audit_service: Optional[Union[LLMAuditService, "LLMCallSink"]] = None,
        storage_dir: Optional[Path] = None,
    ):
        """Initialize the audited client wrapper.

        Args:
            client: The underlying OpenAI client
            audit_service: Optional audit service or LLMCallSink (creates default if None)
            storage_dir: Optional storage directory for audit logs (ignored if audit_service provided)
        """
        self.client = client

        # Accept either LLMAuditService or LLMCallSink
        if audit_service is not None:
            self._sink: "LLMCallSink" = audit_service
        else:
            self._sink = get_llm_audit_service(storage_dir)

        # Backwards compatibility: expose audit_service attribute
        # This will be the sink, which may or may not be an LLMAuditService
        self.audit_service = self._sink

        # Context for linking calls to decisions
        self._claim_id: Optional[str] = None
        self._doc_id: Optional[str] = None
        self._run_id: Optional[str] = None
        self._decision_id: Optional[str] = None
        self._call_purpose: Optional[str] = None

        # Retry tracking
        self._attempt_number: int = 1
        self._previous_call_id: Optional[str] = None

        # Injected context for prompt provenance tracking
        self._injected_context: Optional[InjectedContext] = None

    def set_injected_context(
        self,
        context: Optional[InjectedContext] = None,
    ) -> "AuditedOpenAIClient":
        """Set injected context metadata for the next LLM call.

        This method captures what context was injected into the prompt,
        enabling auditors to see exactly what information the model received.

        Args:
            context: InjectedContext describing what was included in the prompt

        Returns:
            Self for chaining
        """
        self._injected_context = context
        return self

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
        """Clear all context including injected context."""
        self._claim_id = None
        self._doc_id = None
        self._run_id = None
        self._decision_id = None
        self._call_purpose = None
        self._attempt_number = 1
        self._previous_call_id = None
        self._injected_context = None
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
            injected_context=self._injected_context,
        )

        # Clear injected context after use (it's per-call)
        self._injected_context = None

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
            self._sink.log_call(record)

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
            self._sink.log_call(record)

            # Store call_id for retry tracking
            self._previous_call_id = call_id

            raise

    def get_last_call_id(self) -> Optional[str]:
        """Get the ID of the last call made (for retry linking)."""
        return self._previous_call_id


def create_audited_client(
    storage_dir: Optional[Path] = None,
    sink: Optional["LLMCallSink"] = None,
) -> AuditedOpenAIClient:
    """Create an audited OpenAI client.

    Args:
        storage_dir: Optional storage directory for audit logs
        sink: Optional LLMCallSink to use (preferred over storage_dir)

    Returns:
        AuditedOpenAIClient wrapping a new OpenAI client
    """
    from openai import OpenAI

    client = OpenAI()

    if sink is not None:
        return AuditedOpenAIClient(client, sink)

    audit_service = get_llm_audit_service(storage_dir)
    return AuditedOpenAIClient(client, audit_service)
