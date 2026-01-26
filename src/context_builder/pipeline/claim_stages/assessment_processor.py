"""Assessment processor for claim-level pipeline.

This processor evaluates a claim based on aggregated facts and produces
a decision (APPROVE, REJECT, REFER_TO_HUMAN) with supporting checks and rationale.

All LLM calls are logged via the compliance audit service.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from openai import OpenAI

from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.pipeline.claim_stages.processing import (
    Processor,
    ProcessorConfig,
    register_processor,
)
from context_builder.services.llm_audit import AuditedOpenAIClient, get_llm_audit_service
from context_builder.storage.workspace_paths import get_workspace_logs_dir

logger = logging.getLogger(__name__)


class AssessmentProcessor:
    """Processor that evaluates claims and produces assessment decisions.

    Uses the aggregated facts from reconciliation to run checks and
    produce a decision with confidence score and rationale.
    """

    processor_type: str = "assessment"

    def __init__(self):
        """Initialize the assessment processor."""
        # OpenAI client will be created lazily
        self._client: Optional[OpenAI] = None
        self._audited_client: Optional[AuditedOpenAIClient] = None

    def _ensure_client(self) -> None:
        """Ensure OpenAI client is initialized."""
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY not found in environment variables. "
                    "Please set it in your .env file."
                )
            self._client = OpenAI(api_key=api_key, timeout=120)
            audit_service = get_llm_audit_service(get_workspace_logs_dir())
            self._audited_client = AuditedOpenAIClient(self._client, audit_service)

    def process(
        self,
        context: ClaimContext,
        config: ProcessorConfig,
        on_token_update: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Execute assessment processing.

        Args:
            context: The claim context with aggregated facts.
            config: The processor configuration with prompt.
            on_token_update: Optional callback for token streaming updates.

        Returns:
            Assessment result dictionary with decision, checks, etc.
        """
        self._ensure_client()

        logger.info(f"Running assessment for claim {context.claim_id}")

        if not context.aggregated_facts:
            raise ValueError(f"No aggregated facts available for claim {context.claim_id}")

        # Set audit context
        self._audited_client.set_context(
            claim_id=context.claim_id,
            run_id=context.run_id,
            call_purpose="assessment",
        )

        # Build prompt with facts
        system_prompt, user_prompt = self._build_prompts(
            config.prompt_content or "",
            context.aggregated_facts,
            context.claim_id,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call LLM with retries
        result = self._call_with_retry(
            messages=messages,
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            on_token_update=on_token_update,
        )

        # Add metadata to result
        result["claim_id"] = context.claim_id
        result["prompt_version"] = config.prompt_version
        result["model"] = config.model

        logger.info(
            f"Assessment complete for {context.claim_id}: "
            f"decision={result.get('decision')}, "
            f"confidence={result.get('confidence_score')}"
        )

        return result

    def _build_prompts(
        self,
        prompt_template: str,
        facts: Dict[str, Any],
        claim_id: str,
    ) -> tuple[str, str]:
        """Build system and user prompts for assessment.

        Args:
            prompt_template: The prompt template from config.
            facts: Aggregated claim facts.
            claim_id: The claim identifier.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        # Format facts as JSON for injection
        facts_json = json.dumps(facts, indent=2, default=str)

        # If prompt has system/user sections, split them
        if "---USER---" in prompt_template:
            parts = prompt_template.split("---USER---", 1)
            system_prompt = parts[0].strip()
            user_template = parts[1].strip() if len(parts) > 1 else ""
        else:
            # Use entire template as system prompt
            system_prompt = prompt_template
            user_template = ""

        # Build user prompt with facts
        user_prompt = f"""Evaluate the following claim:

Claim ID: {claim_id}

Aggregated Facts:
```json
{facts_json}
```

{user_template}

Provide your assessment as a JSON object with the following structure:
{{
  "decision": "APPROVE" | "REJECT" | "REFER_TO_HUMAN",
  "confidence_score": 0.0-1.0,
  "decision_rationale": "Explanation of the decision",
  "checks": [
    {{
      "check_number": 1,
      "check_name": "Name of check",
      "result": "PASS" | "FAIL" | "INCONCLUSIVE",
      "details": "Details about the check result",
      "evidence_refs": ["ref1", "ref2"]
    }}
  ],
  "assumptions": [
    {{
      "check_number": 1,
      "field": "field_name",
      "assumed_value": "value",
      "reason": "Why this was assumed",
      "confidence_impact": "high" | "medium" | "low"
    }}
  ],
  "fraud_indicators": [
    {{
      "indicator": "Description of indicator",
      "severity": "high" | "medium" | "low",
      "details": "Supporting details"
    }}
  ],
  "payout": {{
    "total_claimed": 0,
    "non_covered_deductions": 0,
    "covered_subtotal": 0,
    "coverage_percent": 0,
    "after_coverage": 0,
    "deductible": 0,
    "final_payout": 0,
    "currency": "CHF"
  }},
  "recommendations": ["List of recommendations"]
}}"""

        return system_prompt, user_prompt

    def _call_with_retry(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        on_token_update: Optional[Callable[[int, int], None]] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """Call OpenAI API with retry logic.

        Args:
            messages: List of message dicts.
            model: Model to use.
            temperature: Temperature setting.
            max_tokens: Max tokens for response.
            on_token_update: Optional callback for token updates.
            retries: Number of retry attempts.

        Returns:
            Parsed JSON response.

        Raises:
            ValueError: If all retries fail.
        """
        last_error = None
        total_input_tokens = 0
        total_output_tokens = 0

        for attempt in range(retries):
            try:
                logger.debug(f"Assessment API call attempt {attempt + 1}/{retries}")

                response = self._audited_client.chat_completions_create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )

                # Track token usage
                if response.usage:
                    total_input_tokens = response.usage.prompt_tokens
                    total_output_tokens = response.usage.completion_tokens

                    if on_token_update:
                        on_token_update(total_input_tokens, total_output_tokens)

                    logger.debug(
                        f"Token usage: {total_input_tokens} input + "
                        f"{total_output_tokens} output = "
                        f"{response.usage.total_tokens} total"
                    )

                # Extract and parse response
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")

                result = json.loads(content)
                return result

            except json.JSONDecodeError as e:
                last_error = ValueError(f"Failed to parse JSON response: {e}")
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")

            except Exception as e:
                last_error = ValueError(f"API call failed: {e}")
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

            # Exponential backoff before retry
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        raise last_error


# Create singleton instance and register with processor registry
_assessment_processor = AssessmentProcessor()
register_processor("assessment", _assessment_processor)
