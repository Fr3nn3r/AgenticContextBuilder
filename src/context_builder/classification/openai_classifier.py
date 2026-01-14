"""OpenAI API implementation for document classification.

All LLM calls are logged via the compliance audit service.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

import yaml
from pydantic import ValidationError

from context_builder.classification import (
    DocumentClassifier,
    ClassifierFactory,
    APIError,
    ConfigurationError,
)
from context_builder.classification.context_builder import (
    build_classification_context,
    load_all_cue_phrases,
)
from context_builder.utils.prompt_loader import load_prompt
from context_builder.schemas.document_classification import DocumentClassification
from context_builder.services.llm_audit import AuditedOpenAIClient, get_llm_audit_service
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.services.compliance import (
    DecisionStorage,
    LLMCallSink,
)
from context_builder.schemas.decision_record import (
    DecisionRecord,
    DecisionType,
    DecisionRationale,
    DecisionOutcome,
)

logger = logging.getLogger(__name__)

# Path to doc type catalog
SPECS_DIR = Path(__file__).parent.parent / "extraction" / "specs"
DOC_TYPE_CATALOG_PATH = SPECS_DIR / "doc_type_catalog.yaml"


def load_doc_type_catalog() -> List[Dict[str, Any]]:
    """
    Load the document type catalog from YAML file.

    Returns:
        List of doc type entries with doc_type, description, and cues.

    Raises:
        ConfigurationError: If catalog file is missing or invalid.
    """
    if not DOC_TYPE_CATALOG_PATH.exists():
        raise ConfigurationError(
            f"Document type catalog not found: {DOC_TYPE_CATALOG_PATH}"
        )

    try:
        with open(DOC_TYPE_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("doc_types", [])
    except Exception as e:
        raise ConfigurationError(f"Failed to load doc type catalog: {e}")


def format_doc_type_catalog(doc_types: List[Dict[str, Any]]) -> str:
    """
    Format the doc type catalog for prompt injection.

    Args:
        doc_types: List of doc type entries from catalog.

    Returns:
        Formatted string suitable for prompt injection.
    """
    lines = []
    for entry in doc_types:
        doc_type = entry.get("doc_type", "unknown")
        description = entry.get("description", "")
        cues = entry.get("cues", [])
        cues_str = ", ".join(cues[:5])  # Limit to 5 cues for brevity
        lines.append(f"- {doc_type}: {description}")
        if cues_str:
            lines.append(f"  Cues: {cues_str}")
    return "\n".join(lines)


class OpenAIDocumentClassifier(DocumentClassifier):
    """
    OpenAI API implementation for document classification.

    This implementation follows the "Schemas in Python, Prompts in Markdown" pattern:
    - Schema: DocumentClassification Pydantic model defines output structure
    - Prompt: Configurable .md file defines instructions and configuration
    - Runner: This class orchestrates the API calls

    Acts as a router that identifies document type with signals/evidence,
    providing optional key_hints without deep field extraction.
    """

    def __init__(
        self,
        prompt_name: str = "claims_document_classification",
        audit_storage_dir: Optional[Path] = None,
        decision_storage: Optional[DecisionStorage] = None,
        llm_sink: Optional[LLMCallSink] = None,
    ):
        """
        Initialize OpenAI document classifier.

        Args:
            prompt_name: Name of prompt file in prompts/ directory (without .md)
            audit_storage_dir: Optional directory for audit log storage (used if
                decision_storage/llm_sink not provided)
            decision_storage: Optional DecisionStorage implementation for compliance
                logging. If not provided, creates default DecisionLedger.
            llm_sink: Optional LLMCallSink implementation for LLM call logging.
                If not provided, creates default audit service.
        """
        super().__init__()

        # Get API key from environment
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY not found in environment variables. "
                "Please set it in your .env file."
            )

        # Initialize OpenAI client
        try:
            from openai import OpenAI

            self.timeout = 60  # seconds
            self.retries = 3

            self.client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,  # We handle retries ourselves
            )

            # Initialize audited client for compliance logging
            # Use injected sink or create default audit service
            if llm_sink is not None:
                self.audited_client = AuditedOpenAIClient(self.client, llm_sink)
            else:
                audit_service = get_llm_audit_service(audit_storage_dir)
                self.audited_client = AuditedOpenAIClient(self.client, audit_service)

            logger.debug("OpenAI client initialized successfully")
        except ImportError:
            raise ConfigurationError(
                "OpenAI package not installed. "
                "Please install it with: pip install openai"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize OpenAI client: {e}")

        # Load prompt configuration
        self.prompt_name = prompt_name
        self._load_prompt_config()

        # Load document type catalog
        self._load_doc_type_catalog()

        # Context for audit logging (set during classification)
        self._audit_context: Dict[str, Optional[str]] = {
            "claim_id": None,
            "doc_id": None,
            "run_id": None,
        }

        # Initialize decision storage for compliance logging
        # Use injected storage or create default DecisionLedger
        if decision_storage is not None:
            self._decision_storage = decision_storage
        else:
            ledger_dir = audit_storage_dir or Path("output/logs")
            self._decision_storage = DecisionLedger(ledger_dir)

        logger.debug(
            f"Classifier initialized: model={self.model}, "
            f"max_tokens={self.max_tokens}, prompt={self.prompt_name}, "
            f"doc_types={len(self.doc_types)}"
        )

    def _load_prompt_config(self):
        """Load prompt configuration from markdown file."""
        try:
            prompt_data = load_prompt(self.prompt_name)
            self.prompt_config = prompt_data["config"]
            logger.debug(f"Loaded prompt: {self.prompt_config.get('name', 'unnamed')}")

            # Extract configuration
            self.model = self.prompt_config.get("model", "gpt-4o")
            self.max_tokens = self.prompt_config.get("max_tokens", 2048)
            self.temperature = self.prompt_config.get("temperature", 0.2)

        except Exception as e:
            raise ConfigurationError(f"Failed to load prompt configuration: {e}")

    def _load_doc_type_catalog(self):
        """Load and format the document type catalog for prompt injection."""
        self.doc_types = load_doc_type_catalog()
        self.doc_type_catalog_str = format_doc_type_catalog(self.doc_types)
        logger.debug(f"Loaded {len(self.doc_types)} document types from catalog")

    def _build_messages(
        self, text_content: str, filename: str
    ) -> list:
        """Build messages for API call using prompt template."""
        # Load and render prompt with variables including doc type catalog
        prompt_data = load_prompt(
            self.prompt_name,
            text_content=text_content,
            filename=filename,
            doc_type_catalog=self.doc_type_catalog_str,
        )
        return prompt_data["messages"]

    def set_audit_context(
        self,
        claim_id: Optional[str] = None,
        doc_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> "OpenAIDocumentClassifier":
        """Set context for audit logging.

        Args:
            claim_id: Claim identifier
            doc_id: Document identifier
            run_id: Pipeline run identifier

        Returns:
            Self for chaining
        """
        self._audit_context = {
            "claim_id": claim_id,
            "doc_id": doc_id,
            "run_id": run_id,
        }
        self.audited_client.set_context(
            claim_id=claim_id,
            doc_id=doc_id,
            run_id=run_id,
            call_purpose="classification",
        )
        return self

    def _call_api_with_retry(self, messages: list) -> Dict[str, Any]:
        """
        Call OpenAI API with retry logic for transient failures.

        All calls are logged via the compliance audit service.

        Args:
            messages: List of message dicts for the API

        Returns:
            Parsed JSON response

        Raises:
            APIError: If all retries fail
        """
        last_error = None

        for attempt in range(self.retries):
            try:
                logger.debug(f"API call attempt {attempt + 1}/{self.retries}")

                # Use audited client for compliance logging
                # Mark as retry if this is not the first attempt
                if attempt > 0:
                    last_call_id = self.audited_client.get_last_call_id()
                    if last_call_id:
                        self.audited_client.mark_retry(last_call_id)

                response = self.audited_client.chat_completions_create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )

                # Extract and parse response
                content = response.choices[0].message.content
                if not content:
                    raise APIError("Empty response from API")

                result = json.loads(content)

                # Log usage for cost tracking
                if response.usage:
                    logger.debug(
                        f"API usage: {response.usage.prompt_tokens} prompt + "
                        f"{response.usage.completion_tokens} completion = "
                        f"{response.usage.total_tokens} total tokens"
                    )

                return result

            except json.JSONDecodeError as e:
                last_error = APIError(f"Failed to parse JSON response: {e}")
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")

            except Exception as e:
                last_error = APIError(f"API call failed: {e}")
                logger.warning(f"API error on attempt {attempt + 1}: {e}")

            # Exponential backoff before retry
            if attempt < self.retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)

        raise last_error

    def _validate_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate API response against schema.

        Args:
            response: Raw API response dict

        Returns:
            Validated response dict

        Raises:
            ClassificationError: If validation fails
        """
        try:
            # Defensive check for None response
            if response is None:
                logger.warning("Received None response from API")
                return {
                    "document_type": "unknown",
                    "summary": "No response from classification API",
                    "language": "unknown",
                    "confidence": 0.0,
                }
            # Validate with Pydantic
            validated = DocumentClassification.model_validate(response)
            return validated.model_dump()
        except ValidationError as e:
            logger.warning(f"Schema validation failed: {e}")
            # Return response as-is if it has required fields
            if response and "document_type" in response and "summary" in response:
                return response
            raise

    def _classify_implementation(
        self, text_content: str, filename: str = ""
    ) -> Dict[str, Any]:
        """
        Implementation-specific classification logic.

        Args:
            text_content: Extracted text from document
            filename: Original filename (hint for classification)

        Returns:
            Dict with document_type, language, confidence, summary, signals, key_hints
        """
        # Build messages from prompt template
        messages = self._build_messages(text_content, filename)

        # Call API with retry
        response = self._call_api_with_retry(messages)

        # Validate and return
        result = self._validate_response(response)

        # Log decision to compliance ledger
        self._log_classification_decision(result, filename)

        return result

    def _log_classification_decision(
        self, result: Dict[str, Any], filename: str = ""
    ) -> None:
        """Log classification decision to the compliance ledger.

        Args:
            result: Classification result dict
            filename: Original filename
        """
        try:
            # Build decision rationale from classification signals
            signals = result.get("signals", [])
            summary = result.get("summary", "")
            confidence = result.get("confidence", 0.0)

            rationale = DecisionRationale(
                summary=f"Classified as {result.get('document_type', 'unknown')}: {summary}",
                confidence=confidence,
                llm_call_id=self.audited_client.get_last_call_id(),
                notes=f"Signals: {', '.join(signals)}" if signals else None,
            )

            # Build decision outcome
            outcome = DecisionOutcome(
                doc_type=result.get("document_type"),
                doc_type_confidence=confidence,
                language=result.get("language"),
            )

            # Create and log decision record
            record = DecisionRecord(
                decision_id="",  # Will be generated by ledger
                decision_type=DecisionType.CLASSIFICATION,
                claim_id=self._audit_context.get("claim_id"),
                doc_id=self._audit_context.get("doc_id"),
                run_id=self._audit_context.get("run_id"),
                rationale=rationale,
                outcome=outcome,
                actor_type="system",
                actor_id="openai_classifier",
                metadata={"filename": filename, "model": self.model},
            )

            self._decision_storage.append(record)
            logger.debug(f"Logged classification decision for doc_id={self._audit_context.get('doc_id')}")

        except Exception as e:
            # Don't fail classification if logging fails
            logger.warning(f"Failed to log classification decision: {e}")

    def classify_pages(
        self,
        pages: List[str],
        filename: str = "",
        confidence_threshold: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Classify document using page-based context optimization.

        For long documents, this method:
        1. Builds optimized context (first 2 + last page + cue snippets)
        2. Classifies using optimized context
        3. If confidence < threshold, retries with full text

        Args:
            pages: List of page texts (strings)
            filename: Original filename (hint for classification)
            confidence_threshold: If confidence below this, retry with full text

        Returns:
            Dict with document_type, language, confidence, summary, signals, key_hints
            Plus additional fields: context_tier, retried, token_savings_estimate
        """
        if not pages:
            from context_builder.classification import ClassificationError
            raise ClassificationError("Empty pages list provided")

        # Build optimized context
        ctx = build_classification_context(pages)

        logger.info(
            f"Classification context: tier={ctx.tier}, "
            f"total_chars={ctx.total_chars}, pages_included={ctx.pages_included}, "
            f"snippets={ctx.snippets_found}"
        )

        # First classification attempt with optimized context
        result = self.classify(ctx.text, filename)
        result["context_tier"] = ctx.tier
        result["retried"] = False

        # Estimate token savings (rough: 1 token ~= 4 chars)
        original_chars = ctx.total_chars
        optimized_chars = len(ctx.text)
        result["token_savings_estimate"] = max(0, (original_chars - optimized_chars) // 4)

        # Check if we need to retry with full text
        confidence = result.get("confidence", 0.0)
        if confidence < confidence_threshold and ctx.tier == "optimized":
            logger.info(
                f"Low confidence ({confidence:.2f} < {confidence_threshold}), "
                f"retrying with full text"
            )

            # Retry with full document text
            full_text = "\n\n".join(pages)
            result = self.classify(full_text, filename)
            result["context_tier"] = "full_retry"
            result["retried"] = True
            result["token_savings_estimate"] = 0  # No savings on retry

            logger.info(
                f"Retry result: confidence={result.get('confidence', 0.0):.2f}, "
                f"doc_type={result.get('document_type', 'unknown')}"
            )

        return result


# Auto-register with factory
ClassifierFactory.register("openai", OpenAIDocumentClassifier)
