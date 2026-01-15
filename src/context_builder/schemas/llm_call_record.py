"""LLM Call Record schema for compliance audit trails.

This module defines the data structure for recording LLM API calls,
capturing all information needed for compliance auditing including
request details, response content, token usage, timing, and decision context.

Schema version: 1.1.0
- 1.0.0: Initial schema
- 1.1.0: Added InjectedContext for prompt provenance tracking
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class InjectedContextSource:
    """Describes a source of context injected into a prompt.

    Used to track provenance of text included in LLM prompts, enabling
    auditors to see exactly which parts of documents were shown to the model.
    """

    source_type: str  # "page", "snippet", "cue_match", "field_hint", "candidate_span"
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    content_preview: Optional[str] = None  # First ~200 chars for audit review
    selection_criteria: Optional[str] = None  # Why this source was selected
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InjectedContext:
    """Metadata about context injected into an LLM prompt.

    Captures what text was included in a prompt and why, enabling auditors
    to understand the exact information the model had access to when making
    a decision.

    Attributes:
        context_tier: Strategy used for context selection ("full", "optimized", "full_retry")
        total_source_chars: Total characters in the original document(s)
        injected_chars: Characters actually included in the prompt
        sources: Detailed breakdown of each text source included
        cues_matched: Classification cue phrases that were found (for classification calls)
        field_hints_used: Field specifications used to guide extraction (for extraction calls)
        template_variables: Variables substituted into prompt templates
    """

    context_tier: str = "full"
    total_source_chars: int = 0
    injected_chars: int = 0
    sources: List[InjectedContextSource] = field(default_factory=list)
    cues_matched: List[str] = field(default_factory=list)
    field_hints_used: List[str] = field(default_factory=list)
    template_variables: Dict[str, str] = field(default_factory=dict)


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

    # Injected context for prompt provenance (added in schema 1.1.0)
    injected_context: Optional[InjectedContext] = None
