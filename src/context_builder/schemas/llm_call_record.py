"""LLM Call Record schema for compliance audit trails.

This module defines the data structure for recording LLM API calls,
capturing all information needed for compliance auditing including
request details, response content, token usage, timing, and decision context.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


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
