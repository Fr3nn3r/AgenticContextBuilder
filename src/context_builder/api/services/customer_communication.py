"""Customer communication service for generating draft emails."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from context_builder.utils.prompt_loader import load_prompt
from context_builder.services.llm_audit import AuditedOpenAIClient, get_llm_audit_service
from context_builder.storage.workspace_paths import get_workspace_logs_dir

logger = logging.getLogger(__name__)


class CustomerDraftRequest(BaseModel):
    """Request for generating a customer communication draft."""

    language: str = "en"  # "en" or "de"


class CustomerDraftResponse(BaseModel):
    """Response containing the generated draft."""

    subject: str
    body: str
    language: str
    claim_id: str
    tokens_used: int = 0


class CustomerCommunicationService:
    """Service for generating customer-facing email drafts based on claim assessments."""

    PROMPT_NAME = "customer_communication_draft"

    def __init__(self):
        """Initialize the customer communication service."""
        # Initialize OpenAI client with audit logging (uses Azure OpenAI if configured)
        try:
            from context_builder.services.openai_client import get_openai_client

            self.client = get_openai_client()

            audit_service = get_llm_audit_service()
            self.audited_client = AuditedOpenAIClient(self.client, audit_service)

            logger.debug("CustomerCommunicationService initialized successfully")
        except ImportError:
            raise ValueError(
                "OpenAI package not installed. "
                "Please install it with: pip install openai"
            )
        except ValueError as e:
            raise ValueError(str(e))

    def _load_prompt_config(self) -> Dict[str, Any]:
        """Load prompt configuration from markdown file."""
        prompt_data = load_prompt(self.PROMPT_NAME)
        return prompt_data["config"]

    def _extract_notable_checks(
        self, checks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract notable checks (FAIL or INCONCLUSIVE) from assessment."""
        notable = []
        for check in checks:
            if check.get("result") in ("FAIL", "INCONCLUSIVE"):
                notable.append(
                    {
                        "check_name": check.get("check_name", "Unknown"),
                        "result": check.get("result"),
                        "details": check.get("details", ""),
                    }
                )
        return notable

    def _extract_policyholder_name(
        self, claim_facts: Optional[Dict[str, Any]]
    ) -> str:
        """Extract policyholder name from claim facts.

        Args:
            claim_facts: The claim facts data containing aggregated facts

        Returns:
            Policyholder name if found, empty string otherwise
        """
        if not claim_facts:
            return ""

        facts = claim_facts.get("facts", [])
        for fact in facts:
            if fact.get("name") == "policyholder_name":
                return fact.get("value", "") or ""

        return ""

    def generate_draft(
        self,
        claim_id: str,
        assessment: Dict[str, Any],
        claim_facts: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> CustomerDraftResponse:
        """Generate a customer communication draft based on assessment.

        Args:
            claim_id: The claim identifier
            assessment: The claim assessment data
            claim_facts: The claim facts data (for policyholder name)
            language: Target language ("en" or "de")

        Returns:
            CustomerDraftResponse with subject, body, and metadata
        """
        # Set audit context
        self.audited_client.set_context(
            claim_id=claim_id,
            call_purpose="customer_communication",
        )

        # Extract data from assessment
        decision = assessment.get("decision", "REFER_TO_HUMAN")
        decision_rationale = assessment.get("decision_rationale", "")
        checks = assessment.get("checks", [])
        payout = assessment.get("payout")
        currency = assessment.get("currency") or assessment.get("payout_breakdown", {}).get("currency") or "CHF"

        # Get policyholder name from claim facts
        policyholder_name = self._extract_policyholder_name(claim_facts)

        # Extract notable checks
        notable_checks = self._extract_notable_checks(checks)

        # Load and render prompt
        prompt_data = load_prompt(
            self.PROMPT_NAME,
            language=language,
            claim_id=claim_id,
            policyholder_name=policyholder_name or "",
            decision=decision,
            decision_rationale=decision_rationale or "Assessment completed.",
            notable_checks=notable_checks,
            payout=payout,
            currency=currency,
        )

        from context_builder.services.openai_client import get_default_model

        config = prompt_data["config"]
        messages = prompt_data["messages"]

        # Make LLM call (use Azure deployment as default if configured)
        response = self.audited_client.chat_completions_create(
            model=config.get("model", get_default_model()),
            messages=messages,
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 1024),
            response_format={"type": "json_object"},
        )

        # Parse response
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from LLM")

        result = json.loads(content)

        # Calculate tokens used
        tokens_used = 0
        if response.usage:
            tokens_used = response.usage.total_tokens

        return CustomerDraftResponse(
            subject=result.get("subject", ""),
            body=result.get("body", ""),
            language=result.get("language", language),
            claim_id=claim_id,
            tokens_used=tokens_used,
        )


# Singleton instance
_service_instance: Optional[CustomerCommunicationService] = None


def get_customer_communication_service() -> CustomerCommunicationService:
    """Get or create the customer communication service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = CustomerCommunicationService()
    return _service_instance
