"""LLM matcher for ambiguous coverage items.

The LLM matcher is the fallback for items that couldn't be matched by
rules or keywords. It uses an audited OpenAI call to determine coverage.

Confidence levels:
- High confidence match: 0.75-0.85
- Medium confidence: 0.60-0.75
- Low confidence (<0.60): Flagged for review
"""

import json
import logging
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
    TraceAction,
)
from context_builder.coverage.trace import TraceBuilder

logger = logging.getLogger(__name__)


@dataclass
class LLMMatcherConfig:
    """Configuration for LLM matcher."""

    prompt_name: str = "coverage"  # Prompt file name (without .md)
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 512
    min_confidence_for_coverage: float = 0.60
    review_needed_threshold: float = 0.60
    # Lower threshold for "not covered" - we're more willing to deny than approve
    review_needed_threshold_not_covered: float = 0.40
    # Max concurrent LLM calls in batch_match (1 = sequential)
    max_concurrent: int = 3
    # Retry config for transient failures (rate limits, 5xx)
    max_retries: int = 3
    retry_base_delay: float = 1.0  # seconds, doubles each attempt
    retry_max_delay: float = 15.0  # cap on backoff delay
    # Prompt file for labor relevance classification (without .md)
    labor_relevance_prompt_name: str = "labor_relevance"

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "LLMMatcherConfig":
        """Create config from dictionary."""
        return cls(
            prompt_name=config.get("prompt_name", "coverage"),
            model=config.get("model", "gpt-4o"),
            temperature=config.get("temperature", 0.0),
            max_tokens=config.get("max_tokens", 512),
            min_confidence_for_coverage=config.get("min_confidence_for_coverage", 0.60),
            review_needed_threshold=config.get("review_needed_threshold", 0.60),
            review_needed_threshold_not_covered=config.get("review_needed_threshold_not_covered", 0.40),
            max_concurrent=config.get("max_concurrent", 3),
            max_retries=config.get("max_retries", 3),
            retry_base_delay=config.get("retry_base_delay", 1.0),
            retry_max_delay=config.get("retry_max_delay", 15.0),
            labor_relevance_prompt_name=config.get("labor_relevance_prompt_name", "labor_relevance"),
        )


@dataclass
class LLMMatchResult:
    """Result from LLM coverage analysis."""

    is_covered: bool
    category: Optional[str]
    matched_component: Optional[str]
    confidence: float
    reasoning: str


class LLMMatcher:
    """LLM-based coverage matching for ambiguous items.

    The LLM matcher is the final matcher in the coverage analysis pipeline,
    handling items that couldn't be definitively categorized by rules or keywords.
    """

    def __init__(
        self,
        config: Optional[LLMMatcherConfig] = None,
        audited_client: Optional[Any] = None,
    ):
        """Initialize the LLM matcher.

        Args:
            config: LLM matcher configuration
            audited_client: Optional pre-configured AuditedOpenAIClient
        """
        self.config = config or LLMMatcherConfig()
        self._client = audited_client
        self._llm_calls = 0

    def _get_client(self) -> Any:
        """Get or create the audited OpenAI client."""
        if self._client is None:
            from context_builder.services.llm_audit import create_audited_client

            self._client = create_audited_client()
        return self._client

    def _build_prompt_messages(
        self,
        description: str,
        item_type: str,
        covered_categories: List[str],
        covered_components: Dict[str, List[str]],
        excluded_components: Optional[Dict[str, List[str]]] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
        repair_context_description: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build the prompt messages for the LLM.

        Args:
            description: Item description
            item_type: Item type (parts, labor, fee)
            covered_categories: List of covered category names
            covered_components: Dict mapping category to list of component names
            excluded_components: Dict mapping category to list of excluded component names
            covered_parts_in_claim: List of covered parts from this claim (for labor context)
            repair_context_description: Section header or labor context for this item

        Returns:
            List of message dictionaries for OpenAI API
        """
        # Try to load from prompt file
        try:
            from context_builder.utils.prompt_loader import load_prompt

            prompt_data = load_prompt(
                self.config.prompt_name,
                description=description,
                item_type=item_type,
                covered_categories=covered_categories,
                covered_components=covered_components,
                excluded_components=excluded_components or {},
                covered_parts_in_claim=covered_parts_in_claim or [],
                repair_context_description=repair_context_description or "",
            )
            return prompt_data["messages"]
        except FileNotFoundError:
            logger.debug(
                f"Prompt file '{self.config.prompt_name}' not found, using inline prompt"
            )

        # Fallback to inline prompt
        # Format covered components for prompt
        components_text = ""
        for category, parts in covered_components.items():
            if parts:
                parts_list = ", ".join(parts[:10])  # Limit to 10 parts per category
                if len(parts) > 10:
                    parts_list += f", ... ({len(parts)} total)"
                components_text += f"- {category}: {parts_list}\n"

        system_prompt = """You are an automotive insurance coverage analyst.
Your task is to determine if a repair line item is covered under the policy.

Policy Coverage Information:
Covered Categories: {categories}

Covered Components by Category:
{components}

Rules:
1. Parts/labor that relate to covered components are COVERED
2. Consumables (oil, filters, fluids) are NOT COVERED
3. Environmental/disposal fees are NOT COVERED
4. Rental car fees are NOT COVERED
5. Diagnostic labor for covered components IS COVERED

Respond in JSON format:
{{
  "is_covered": true/false,
  "category": "matched category name or null",
  "matched_component": "specific component from list or null",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}""".format(
            categories=", ".join(covered_categories),
            components=components_text or "No specific components listed",
        )

        user_prompt = f"""Analyze this repair line item:

Description: {description}
Item Type: {item_type}

Determine if this item is covered under the policy."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_llm_response(self, content: str) -> LLMMatchResult:
        """Parse the LLM response JSON.

        Args:
            content: Raw response content from LLM

        Returns:
            Parsed LLMMatchResult
        """
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            return LLMMatchResult(
                is_covered=data.get("is_covered", False),
                category=data.get("category"),
                matched_component=data.get("matched_component"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "No reasoning provided"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return LLMMatchResult(
                is_covered=False,
                category=None,
                matched_component=None,
                confidence=0.0,
                reasoning=f"Failed to parse LLM response: {content[:200]}",
            )

    def _detect_vague_description(self, description: str) -> bool:
        """Detect descriptions too vague for confident coverage determination.

        Vague descriptions should trigger low confidence to ensure human review.

        Args:
            description: Item description to check

        Returns:
            True if description is vague, False otherwise
        """
        if not description:
            return True

        desc = description.strip().upper()

        # Very short descriptions (1-4 chars) are inherently vague
        # e.g., "VIS", "OIL" - but not "MOTOR", "PUMPE"
        if len(desc) <= 4:
            return True

        # Generic terms that don't indicate specific parts
        # Note: We explicitly list vague terms rather than using length/pattern rules
        # because valid component names like "ÖLPUMPE", "CONTACTEUR" would be wrongly flagged
        vague_terms = {
            "PART", "PARTS", "PIECE", "PIECES", "PIÈCE", "PIÈCES",
            "MISC", "MISCELLANEOUS", "DIVERS", "DIVERSE",
            "OTHER", "OTHERS", "AUTRE", "AUTRES",
            "ITEM", "ITEMS", "ARTICLE", "ARTICLES",
            "ARRIVEE", "ARRIVAL", "LIVRAISON",
            "WORK", "TRAVAIL", "SERVICE", "SERVICES",
            "MATERIAL", "MATERIEL", "MATÉRIEL",
            "ARBEIT", "ARBEIT:",
        }
        if desc in vague_terms:
            return True

        return False

    def _match_single(
        self,
        description: str,
        item_type: str,
        client: Any,
        item_code: Optional[str] = None,
        total_price: float = 0.0,
        covered_categories: Optional[List[str]] = None,
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        claim_id: Optional[str] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
        repair_context_description: Optional[str] = None,
    ) -> LineItemCoverage:
        """Match a single item using LLM with a specific client instance.

        This is the core matching logic, separated from client management
        so it can be used by both sequential and parallel batch modes.

        Args:
            description: Item description
            item_type: Item type (parts, labor, fee)
            client: AuditedOpenAIClient to use for this call
            item_code: Optional item code
            total_price: Item total price
            covered_categories: Categories covered by policy
            covered_components: Components per category from policy
            excluded_components: Excluded components per category from policy
            claim_id: Claim ID for audit context
            covered_parts_in_claim: List of covered parts from this claim (for labor context)
            repair_context_description: Section header or labor context for this item

        Returns:
            LineItemCoverage result
        """
        covered_categories = covered_categories or []
        covered_components = covered_components or {}
        excluded_components = excluded_components or {}

        # Build prompt
        messages = self._build_prompt_messages(
            description=description,
            item_type=item_type,
            covered_categories=covered_categories,
            covered_components=covered_components,
            excluded_components=excluded_components,
            covered_parts_in_claim=covered_parts_in_claim,
            repair_context_description=repair_context_description,
        )

        # Set context on the provided client
        client.set_context(
            claim_id=claim_id,
            call_purpose="coverage_analysis",
        )

        # Retry loop with exponential backoff + jitter
        last_error = None
        max_attempts = max(1, self.config.max_retries)

        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    # Mark as retry for audit trail
                    last_call_id = getattr(client, "get_last_call_id", lambda: None)()
                    if last_call_id and hasattr(client, "mark_retry"):
                        client.mark_retry(last_call_id)

                # Make LLM call
                response = client.chat_completions_create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"},
                )

                # Parse response
                content = response.choices[0].message.content
                result = self._parse_llm_response(content)

                # Cap confidence for vague descriptions to ensure human review
                confidence = result.confidence
                reasoning = result.reasoning
                vague_capped = False
                if self._detect_vague_description(description) and confidence > 0.50:
                    confidence = 0.50
                    vague_capped = True
                    reasoning = f"{reasoning} [Confidence capped: description too vague for confident determination]"

                # Determine coverage status with asymmetric thresholds:
                # - High bar (0.60) for approvals: be careful about paying out
                # - Low bar (0.40) for denials: customer can appeal if wrong
                if result.is_covered and confidence < self.config.review_needed_threshold:
                    status = CoverageStatus.REVIEW_NEEDED
                elif not result.is_covered and confidence < self.config.review_needed_threshold_not_covered:
                    status = CoverageStatus.REVIEW_NEEDED
                elif result.is_covered:
                    status = CoverageStatus.COVERED
                else:
                    status = CoverageStatus.NOT_COVERED

                if attempt > 0:
                    reasoning += f" [Succeeded on attempt {attempt + 1}]"

                # Build trace step with LLM audit metadata
                tb = TraceBuilder()
                trace_detail: Dict[str, Any] = {
                    "model": self.config.model,
                }
                # Extract token usage from response if available
                usage = getattr(response, "usage", None)
                if usage:
                    trace_detail["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
                    trace_detail["completion_tokens"] = getattr(usage, "completion_tokens", None)
                # Get call ID from audit client if available
                call_id_fn = getattr(client, "get_last_call_id", None)
                if call_id_fn:
                    trace_detail["call_id"] = call_id_fn()
                if vague_capped:
                    trace_detail["vague_description_cap"] = True
                    trace_detail["raw_confidence"] = result.confidence
                if attempt > 0:
                    trace_detail["retries"] = attempt

                tb.add("llm", TraceAction.MATCHED, reasoning,
                       verdict=status, confidence=confidence,
                       detail=trace_detail)

                return LineItemCoverage(
                    item_code=item_code,
                    description=description,
                    item_type=item_type,
                    total_price=total_price,
                    coverage_status=status,
                    coverage_category=result.category,
                    matched_component=result.matched_component,
                    match_method=MatchMethod.LLM,
                    match_confidence=confidence,
                    match_reasoning=reasoning,
                    decision_trace=tb.build(),
                    covered_amount=total_price if status == CoverageStatus.COVERED else 0.0,
                    not_covered_amount=0.0 if status == CoverageStatus.COVERED else total_price,
                )

            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    # Exponential backoff with full jitter to break thundering herd
                    base_delay = min(
                        self.config.retry_base_delay * (2 ** attempt),
                        self.config.retry_max_delay,
                    )
                    delay = random.uniform(0, base_delay)
                    logger.warning(
                        "LLM call failed for '%s' (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        description[:40], attempt + 1, max_attempts, e, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "LLM coverage analysis failed for '%s' after %d attempts: %s",
                        description[:40], max_attempts, e,
                    )

        fail_tb = TraceBuilder()
        fail_tb.add("llm", TraceAction.SKIPPED,
                     f"LLM analysis failed after {max_attempts} attempts: {str(last_error)}",
                     verdict=CoverageStatus.REVIEW_NEEDED, confidence=0.0,
                     detail={"reason": "llm_error", "retries": max_attempts,
                             "model": self.config.model})
        return LineItemCoverage(
            item_code=item_code,
            description=description,
            item_type=item_type,
            total_price=total_price,
            coverage_status=CoverageStatus.REVIEW_NEEDED,
            coverage_category=None,
            matched_component=None,
            match_method=MatchMethod.LLM,
            match_confidence=0.0,
            match_reasoning=f"LLM analysis failed after {max_attempts} attempts: {str(last_error)}",
            decision_trace=fail_tb.build(),
            covered_amount=0.0,
            not_covered_amount=total_price,
        )

    def match(
        self,
        description: str,
        item_type: str,
        item_code: Optional[str] = None,
        total_price: float = 0.0,
        covered_categories: Optional[List[str]] = None,
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        claim_id: Optional[str] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
        repair_context_description: Optional[str] = None,
    ) -> LineItemCoverage:
        """Match a single item using LLM.

        Args:
            description: Item description
            item_type: Item type (parts, labor, fee)
            item_code: Optional item code
            total_price: Item total price
            covered_categories: Categories covered by policy
            covered_components: Components per category from policy
            excluded_components: Excluded components per category from policy
            claim_id: Claim ID for audit context
            covered_parts_in_claim: List of covered parts from this claim (for labor context)
            repair_context_description: Section header or labor context for this item

        Returns:
            LineItemCoverage result
        """
        client = self._get_client()
        result = self._match_single(
            description=description,
            item_type=item_type,
            client=client,
            item_code=item_code,
            total_price=total_price,
            covered_categories=covered_categories,
            covered_components=covered_components,
            excluded_components=excluded_components,
            claim_id=claim_id,
            covered_parts_in_claim=covered_parts_in_claim,
            repair_context_description=repair_context_description,
        )
        self._llm_calls += 1
        return result

    def _create_thread_client(self) -> Any:
        """Create a per-thread AuditedOpenAIClient.

        Shares the underlying OpenAI SDK client (thread-safe via httpx)
        and the log sink (thread-safe via module-level lock), but gives
        each thread its own audit context state.
        """
        from context_builder.services.llm_audit import AuditedOpenAIClient

        base = self._get_client()
        return AuditedOpenAIClient(base.client, base._sink)

    def batch_match(
        self,
        items: List[Dict[str, Any]],
        covered_categories: Optional[List[str]] = None,
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        claim_id: Optional[str] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
    ) -> List[LineItemCoverage]:
        """Match multiple items using LLM.

        Uses parallel execution when max_concurrent > 1 and there are
        multiple items. Each worker thread gets its own AuditedOpenAIClient
        to avoid shared-state races on set_context().

        Args:
            items: List of line item dictionaries
            covered_categories: Categories covered by policy
            covered_components: Components per category from policy
            excluded_components: Excluded components per category from policy
            claim_id: Claim ID for audit context
            on_progress: Optional callback called after each LLM call with increment (1)
            covered_parts_in_claim: List of covered parts from this claim (for labor context)

        Returns:
            List of LineItemCoverage results (same order as input items)
        """
        if self.config.max_concurrent <= 1 or len(items) <= 1:
            return self._batch_match_sequential(
                items, covered_categories, covered_components,
                excluded_components, claim_id, on_progress,
                covered_parts_in_claim,
            )

        return self._batch_match_parallel(
            items, covered_categories, covered_components,
            excluded_components, claim_id, on_progress,
            covered_parts_in_claim,
        )

    def _batch_match_sequential(
        self,
        items: List[Dict[str, Any]],
        covered_categories: Optional[List[str]] = None,
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        claim_id: Optional[str] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
    ) -> List[LineItemCoverage]:
        """Match items sequentially (original behavior)."""
        results = []
        client = self._get_client()

        for item in items:
            result = self._match_single(
                description=item.get("description", ""),
                item_type=item.get("item_type", ""),
                client=client,
                item_code=item.get("item_code"),
                total_price=item.get("total_price") or 0.0,
                covered_categories=covered_categories,
                covered_components=covered_components,
                excluded_components=excluded_components,
                claim_id=claim_id,
                covered_parts_in_claim=covered_parts_in_claim,
                repair_context_description=item.get("repair_context_description"),
            )
            results.append(result)
            self._llm_calls += 1

            if on_progress:
                on_progress(1)

        logger.info(f"LLM matcher processed {len(items)} items sequentially with {self._llm_calls} LLM calls")
        return results

    def _batch_match_parallel(
        self,
        items: List[Dict[str, Any]],
        covered_categories: Optional[List[str]] = None,
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        claim_id: Optional[str] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
    ) -> List[LineItemCoverage]:
        """Match items in parallel using ThreadPoolExecutor.

        Each worker thread gets its own AuditedOpenAIClient instance
        (sharing the underlying httpx client and log sink).
        """
        call_count_lock = threading.Lock()
        progress_lock = threading.Lock()

        def match_one(index: int, item: Dict[str, Any]) -> Tuple[int, LineItemCoverage]:
            thread_client = self._create_thread_client()
            result = self._match_single(
                description=item.get("description", ""),
                item_type=item.get("item_type", ""),
                client=thread_client,
                item_code=item.get("item_code"),
                total_price=item.get("total_price") or 0.0,
                covered_categories=covered_categories,
                covered_components=covered_components,
                excluded_components=excluded_components,
                claim_id=claim_id,
                covered_parts_in_claim=covered_parts_in_claim,
                repair_context_description=item.get("repair_context_description"),
            )

            with call_count_lock:
                self._llm_calls += 1

            if on_progress:
                with progress_lock:
                    on_progress(1)

            return (index, result)

        max_workers = min(self.config.max_concurrent, len(items))
        results: List[Optional[LineItemCoverage]] = [None] * len(items)

        logger.info(
            f"LLM matcher starting parallel processing: {len(items)} items, "
            f"{max_workers} workers"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(match_one, i, item): i
                for i, item in enumerate(items)
            }

            for future in as_completed(futures):
                try:
                    index, result = future.result()
                    results[index] = result
                except Exception as e:
                    # Should not happen — _match_single catches internally.
                    # But defend against unexpected errors.
                    idx = futures[future]
                    item = items[idx]
                    logger.error(f"Unexpected error in parallel LLM match for item {idx}: {e}")
                    results[idx] = LineItemCoverage(
                        item_code=item.get("item_code"),
                        description=item.get("description", ""),
                        item_type=item.get("item_type", ""),
                        total_price=item.get("total_price") or 0.0,
                        coverage_status=CoverageStatus.REVIEW_NEEDED,
                        coverage_category=None,
                        matched_component=None,
                        match_method=MatchMethod.LLM,
                        match_confidence=0.0,
                        match_reasoning=f"Parallel LLM analysis failed: {str(e)}",
                        covered_amount=0.0,
                        not_covered_amount=item.get("total_price") or 0.0,
                    )
                    with call_count_lock:
                        self._llm_calls += 1

        logger.info(f"LLM matcher processed {len(items)} items in parallel with {self._llm_calls} LLM calls")
        return results

    # ------------------------------------------------------------------
    # Labor relevance classification (batch LLM call for Mode 2)
    # ------------------------------------------------------------------

    def classify_labor_for_primary_repair(
        self,
        labor_items: List[Dict[str, Any]],
        primary_component: str,
        primary_category: str,
        covered_parts_in_claim: List[Dict[str, str]],
        claim_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Classify which labor items are mechanically necessary for the primary repair.

        Makes ONE batch LLM call asking the model to evaluate all candidate
        labor items against the identified primary repair.

        Args:
            labor_items: List of dicts with keys: index, description, item_code, total_price
            primary_component: The primary repair component (e.g. "timing_chain")
            primary_category: The coverage category (e.g. "engine")
            covered_parts_in_claim: Covered parts for context
            claim_id: Claim ID for audit trail

        Returns:
            List of dicts with keys: index, is_relevant, confidence, reasoning.
            On failure, all items are returned with is_relevant=False.
        """
        if not labor_items:
            return []

        messages = self._build_labor_relevance_prompt(
            labor_items, primary_component, primary_category,
            covered_parts_in_claim,
        )

        client = self._get_client()
        client.set_context(
            claim_id=claim_id,
            call_purpose="labor_relevance_classification",
        )

        last_error = None
        max_attempts = max(1, self.config.max_retries)

        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    last_call_id = getattr(client, "get_last_call_id", lambda: None)()
                    if last_call_id and hasattr(client, "mark_retry"):
                        client.mark_retry(last_call_id)

                response = client.chat_completions_create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=1024,  # larger limit for batch response
                    response_format={"type": "json_object"},
                )
                self._llm_calls += 1

                content = response.choices[0].message.content
                return self._parse_labor_relevance_response(
                    content, labor_items,
                )

            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    base_delay = min(
                        self.config.retry_base_delay * (2 ** attempt),
                        self.config.retry_max_delay,
                    )
                    delay = random.uniform(0, base_delay)
                    logger.warning(
                        "Labor relevance LLM call failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        attempt + 1, max_attempts, e, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Labor relevance classification failed after %d attempts: %s",
                        max_attempts, e,
                    )

        self._llm_calls += 1
        # Conservative fallback: mark all as not relevant
        return [
            {
                "index": item["index"],
                "is_relevant": False,
                "confidence": 0.0,
                "reasoning": f"LLM call failed after {max_attempts} attempts: {last_error}",
            }
            for item in labor_items
        ]

    def _build_labor_relevance_prompt(
        self,
        labor_items: List[Dict[str, Any]],
        primary_component: str,
        primary_category: str,
        covered_parts_in_claim: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Build prompt messages for labor relevance classification.

        Tries workspace prompt file first, then core fallback, then inline.
        """
        # Format labor items and covered parts for the template
        labor_lines = []
        for item in labor_items:
            code_str = item.get("item_code") or "N/A"
            labor_lines.append(
                f"  {item['index']}: [{code_str}] {item['description']} "
                f"({item.get('total_price', 0):.2f} CHF)"
            )
        labor_text = "\n".join(labor_lines)

        parts_lines = []
        for part in covered_parts_in_claim:
            code_str = part.get("item_code") or "N/A"
            comp_str = f" ({part['matched_component']})" if part.get("matched_component") else ""
            parts_lines.append(f"  - [{code_str}] {part.get('description', '')}{comp_str}")
        parts_text = "\n".join(parts_lines) if parts_lines else "  (none)"

        try:
            from context_builder.utils.prompt_loader import load_prompt

            prompt_data = load_prompt(
                self.config.labor_relevance_prompt_name,
                primary_component=primary_component,
                primary_category=primary_category,
                covered_parts_text=parts_text,
                labor_items_text=labor_text,
            )
            return prompt_data["messages"]
        except FileNotFoundError:
            logger.debug(
                "Prompt file '%s' not found, using inline labor relevance prompt",
                self.config.labor_relevance_prompt_name,
            )

        # Inline fallback
        system_prompt = (
            "You are an automotive repair labor analyst.\n"
            "Given the primary repair being performed, determine which labor "
            "items are mechanically necessary to complete that specific repair.\n\n"
            "NECESSARY labor (is_relevant = true):\n"
            "- Removing/reinstalling components to access the repair area\n"
            "- Draining/refilling fluids required by the disassembly\n"
            "- The repair labor itself (removal/installation of the covered part)\n\n"
            "NOT NECESSARY labor (is_relevant = false):\n"
            "- Diagnostic/investigative labor\n"
            "- Battery charging\n"
            "- Calibration/programming of unrelated systems\n"
            "- Cleaning or conservation\n"
            "- Environmental/disposal fees\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"labor_items": [{"index": <int>, "is_relevant": <bool>, '
            '"confidence": <float 0-1>, "reasoning": "<brief>"}]}'
        )
        user_prompt = (
            f"Primary repair: {primary_component} ({primary_category})\n\n"
            f"Covered parts in this claim:\n{parts_text}\n\n"
            f"Uncovered labor items to evaluate:\n{labor_text}\n\n"
            "For each labor item, determine if it is mechanically necessary "
            "for the primary repair. Return JSON."
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_labor_relevance_response(
        self,
        content: str,
        labor_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Parse the LLM response for labor relevance classification.

        Args:
            content: Raw JSON response from LLM
            labor_items: Original labor items (for index reference)

        Returns:
            List of dicts with index, is_relevant, confidence, reasoning.
            Missing indices default to is_relevant=False (conservative).
        """
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            llm_results = data.get("labor_items", [])

            # Index the LLM results by index
            by_index = {}
            for r in llm_results:
                idx = r.get("index")
                if idx is not None:
                    by_index[idx] = r

            # Build output, defaulting missing indices to not relevant
            results = []
            for item in labor_items:
                idx = item["index"]
                if idx in by_index:
                    r = by_index[idx]
                    results.append({
                        "index": idx,
                        "is_relevant": bool(r.get("is_relevant", False)),
                        "confidence": float(r.get("confidence", 0.5)),
                        "reasoning": r.get("reasoning", "No reasoning provided"),
                    })
                else:
                    results.append({
                        "index": idx,
                        "is_relevant": False,
                        "confidence": 0.0,
                        "reasoning": "Missing from LLM response (conservative default)",
                    })

            return results

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse labor relevance response: %s", e)
            return [
                {
                    "index": item["index"],
                    "is_relevant": False,
                    "confidence": 0.0,
                    "reasoning": f"Failed to parse LLM response: {str(e)[:200]}",
                }
                for item in labor_items
            ]

    def get_llm_call_count(self) -> int:
        """Get the number of LLM calls made."""
        return self._llm_calls

    def reset_call_count(self) -> None:
        """Reset the LLM call counter."""
        self._llm_calls = 0
