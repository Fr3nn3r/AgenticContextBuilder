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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    DecisionSource,
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
    # Prompt file for primary repair identification (without .md)
    primary_repair_prompt_name: str = "primary_repair"
    # Prompt file for coverage classification (LLM-first mode, without .md)
    classify_prompt_name: str = "coverage_classify"
    # Prompt file for labor linkage classification (without .md)
    labor_linkage_prompt_name: str = "labor_linkage"

    # Descriptions too vague for confident coverage determination.
    # Matched (uppercased) to trigger confidence capping.
    vague_description_terms: Set[str] = field(default_factory=lambda: {
        "PART", "PARTS", "PIECE", "PIECES", "PIÈCE", "PIÈCES",
        "MISC", "MISCELLANEOUS", "DIVERS", "DIVERSE",
        "OTHER", "OTHERS", "AUTRE", "AUTRES",
        "ITEM", "ITEMS", "ARTICLE", "ARTICLES",
        "ARRIVEE", "ARRIVAL", "LIVRAISON",
        "WORK", "TRAVAIL", "SERVICE", "SERVICES",
        "MATERIAL", "MATERIEL", "MATÉRIEL",
        "ARBEIT", "ARBEIT:",
    })

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "LLMMatcherConfig":
        """Create config from dictionary."""
        raw_vague = config.get("vague_description_terms")
        vague = {t.upper() for t in raw_vague} if raw_vague else None

        kwargs: Dict[str, Any] = dict(
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
            primary_repair_prompt_name=config.get("primary_repair_prompt_name", "primary_repair"),
            classify_prompt_name=config.get("classify_prompt_name", "coverage_classify"),
            labor_linkage_prompt_name=config.get("labor_linkage_prompt_name", "labor_linkage"),
        )
        if vague is not None:
            kwargs["vague_description_terms"] = vague
        return cls(**kwargs)


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
        The set of vague terms is configurable via
        ``LLMMatcherConfig.vague_description_terms``.

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

        if desc in self.config.vague_description_terms:
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
                       detail=trace_detail,
                       decision_source=DecisionSource.LLM)

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
                             "model": self.config.model},
                     decision_source=DecisionSource.LLM)
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
    # LLM-first coverage classification (classify_items)
    # ------------------------------------------------------------------

    def classify_items(
        self,
        items: List[Dict[str, Any]],
        covered_components: Dict[str, List[str]],
        excluded_components: Optional[Dict[str, List[str]]] = None,
        keyword_hints: Optional[List[Optional[Dict[str, Any]]]] = None,
        part_number_hints: Optional[List[Optional[Dict[str, Any]]]] = None,
        claim_id: Optional[str] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        covered_parts_in_claim: Optional[List[Dict[str, str]]] = None,
        repair_context_description: Optional[str] = None,
    ) -> List[LineItemCoverage]:
        """Classify ALL items using the LLM with keyword/part-number hints.

        Unlike ``batch_match()`` which is a fallback for unmatched items,
        this method is designed as the primary classification stage.  Each
        item's prompt is enriched with advisory hints from the keyword
        matcher and part-number lookup, giving the LLM more context
        without those matchers making coverage decisions.

        Args:
            items: Line item dicts (description, item_type, item_code,
                   total_price, repair_context_description).
            covered_components: Policy's covered components by category.
            excluded_components: Excluded components by category.
            keyword_hints: Parallel list of keyword hint dicts (or None
                per item) from ``KeywordMatcher.generate_hints()``.
            part_number_hints: Parallel list of part-number hint dicts
                (or None per item) from ``PartNumberLookup.lookup_as_hint()``.
            claim_id: Claim ID for audit trail.
            on_progress: Callback after each LLM call (increment=1).
            covered_parts_in_claim: Covered parts from prior rule stage.
            repair_context_description: Global repair context description.

        Returns:
            List of LineItemCoverage in same order as *items*.
        """
        if not items:
            return []

        excluded_components = excluded_components or {}
        covered_categories = list(covered_components.keys())

        # Enrich each item dict with hint context before passing to _match_single.
        # We inject hints into the repair_context_description field which the
        # prompt builder already embeds in the user message.
        enriched_items: List[Dict[str, Any]] = []
        for i, item in enumerate(items):
            enriched = dict(item)  # shallow copy

            # Build hint text to inject into the item's context
            hint_parts: List[str] = []

            kw_hint = keyword_hints[i] if keyword_hints and i < len(keyword_hints) else None
            if kw_hint:
                kw_text = (
                    f"Keyword hint: '{kw_hint.get('keyword', '')}' maps to "
                    f"category '{kw_hint.get('category', '')}'"
                )
                if kw_hint.get("component"):
                    kw_text += f" (component: {kw_hint['component']})"
                kw_text += f" [confidence: {kw_hint.get('confidence', 0):.2f}]"
                if kw_hint.get("has_consumable_indicator"):
                    kw_text += " (consumable indicator present)"
                hint_parts.append(kw_text)

            pn_hint = part_number_hints[i] if part_number_hints and i < len(part_number_hints) else None
            if pn_hint:
                pn_text = (
                    f"Part lookup: '{pn_hint.get('part_number', '')}' identified as "
                    f"'{pn_hint.get('component', '')}' in category "
                    f"'{pn_hint.get('system', '')}'"
                )
                if pn_hint.get("covered") is not None:
                    pn_text += f" (covered={pn_hint['covered']})"
                hint_parts.append(pn_text)

            # Merge hints with existing repair context
            existing_ctx = (
                enriched.get("repair_context_description")
                or repair_context_description
                or ""
            )
            if hint_parts:
                hint_block = " | ".join(hint_parts)
                enriched["repair_context_description"] = (
                    f"{hint_block}. {existing_ctx}".strip()
                    if existing_ctx
                    else hint_block
                )
            elif existing_ctx:
                enriched["repair_context_description"] = existing_ctx

            enriched_items.append(enriched)

        # Use the classify-specific prompt template for LLM-first mode.
        # Temporarily swap prompt_name so _build_prompt_messages picks up
        # the new template, then restore the original after the batch call.
        original_prompt_name = self.config.prompt_name
        self.config.prompt_name = self.config.classify_prompt_name
        try:
            return self.batch_match(
                items=enriched_items,
                covered_categories=covered_categories,
                covered_components=covered_components,
                excluded_components=excluded_components,
                claim_id=claim_id,
                on_progress=on_progress,
                covered_parts_in_claim=covered_parts_in_claim,
            )
        finally:
            self.config.prompt_name = original_prompt_name

    # ------------------------------------------------------------------
    # LLM labor linkage (links labor items to parts)
    # ------------------------------------------------------------------

    def classify_labor_linkage(
        self,
        labor_items: List[Dict[str, Any]],
        parts_items: List[Dict[str, Any]],
        primary_repair: Optional[Dict[str, Any]] = None,
        claim_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Link labor items to parts and determine labor coverage.

        Makes ONE batch LLM call that sees ALL labor and ALL parts together.
        The model determines which labor items are mechanically necessary for
        which covered parts.

        Args:
            labor_items: List of dicts with keys: index, description,
                item_code, total_price, coverage_status.
            parts_items: List of dicts with keys: index, description,
                item_code, total_price, coverage_status, coverage_category,
                matched_component.
            primary_repair: Optional dict with keys: component, category,
                is_covered. Provides repair context.
            claim_id: Claim ID for audit trail.

        Returns:
            List of dicts with keys: index, is_covered, linked_part_index,
            confidence, reasoning.
            On failure, all items are returned with is_covered=False.
        """
        if not labor_items:
            return []

        messages = self._build_labor_linkage_prompt(
            labor_items, parts_items, primary_repair,
        )

        client = self._get_client()
        client.set_context(
            claim_id=claim_id,
            call_purpose="labor_linkage",
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
                    max_tokens=1024,
                    response_format={"type": "json_object"},
                )
                self._llm_calls += 1

                content = response.choices[0].message.content
                return self._parse_labor_linkage_response(
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
                        "Labor linkage LLM call failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        attempt + 1, max_attempts, e, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Labor linkage classification failed after %d attempts: %s",
                        max_attempts, e,
                    )

        self._llm_calls += 1
        return [
            {
                "index": item["index"],
                "is_covered": False,
                "linked_part_index": None,
                "confidence": 0.0,
                "reasoning": f"LLM call failed after {max_attempts} attempts: {last_error}",
            }
            for item in labor_items
        ]

    def _build_labor_linkage_prompt(
        self,
        labor_items: List[Dict[str, Any]],
        parts_items: List[Dict[str, Any]],
        primary_repair: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """Build prompt messages for labor linkage classification.

        Tries workspace prompt file first, then inline fallback.
        """
        # Format parts with coverage status
        parts_lines = []
        for item in parts_items:
            status = item.get("coverage_status", "unknown")
            cat = item.get("coverage_category") or "N/A"
            comp = item.get("matched_component") or "N/A"
            code_str = item.get("item_code") or "N/A"
            parts_lines.append(
                f"  [{item['index']}] {item['description']} | "
                f"code={code_str} | price={item.get('total_price', 0):.2f} CHF | "
                f"status={status} | category={cat} | component={comp}"
            )
        parts_text = "\n".join(parts_lines) if parts_lines else "  (no parts)"

        # Format labor items
        labor_lines = []
        for item in labor_items:
            code_str = item.get("item_code") or "N/A"
            labor_lines.append(
                f"  [{item['index']}] {item['description']} | "
                f"code={code_str} | price={item.get('total_price', 0):.2f} CHF"
            )
        labor_text = "\n".join(labor_lines)

        # Format primary repair context
        primary_text = ""
        if primary_repair:
            primary_text = (
                f"\nPrimary repair: {primary_repair.get('component', 'unknown')} "
                f"({primary_repair.get('category', 'unknown')}, "
                f"covered={primary_repair.get('is_covered', False)})\n"
            )

        try:
            from context_builder.utils.prompt_loader import load_prompt

            prompt_data = load_prompt(
                self.config.labor_linkage_prompt_name,
                parts_text=parts_text,
                labor_text=labor_text,
                primary_repair_text=primary_text,
            )
            return prompt_data["messages"]
        except FileNotFoundError:
            logger.debug(
                "Prompt file '%s' not found, using inline labor linkage prompt",
                self.config.labor_linkage_prompt_name,
            )

        # Inline fallback
        system_prompt = (
            "You are an automotive repair labor analyst for a warranty "
            "insurance company.\n\n"
            "Given the parts and labor from a repair invoice, determine "
            "which labor items are mechanically necessary for which parts.\n\n"
            "LABOR IS COVERED when:\n"
            "- It is for installing, removing, or replacing a COVERED part\n"
            "- It is access labor (removing components to reach the covered "
            "part)\n"
            "- It is fluid draining/refilling required by the disassembly\n"
            "- It is the repair work itself on a covered component\n\n"
            "LABOR IS NOT COVERED when:\n"
            "- It is standalone diagnostic/investigative labor with no "
            "covered part\n"
            "- It is for an unrelated system (not mechanically connected)\n"
            "- It is cleaning, environmental fees, or rental car\n"
            "- It is battery charging or unrelated calibration\n\n"
            "For each labor item, return whether it should be covered and "
            "which part (by index) it is linked to.\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"labor_items": [{"index": <int>, "is_covered": <bool>, '
            '"linked_part_index": <int or null>, '
            '"confidence": <float 0-1>, "reasoning": "<brief>"}]}'
        )
        user_prompt = (
            f"Parts in this invoice:\n{parts_text}\n\n"
            f"Labor items to evaluate:\n{labor_text}\n"
            f"{primary_text}\n"
            "For each labor item, determine if it is mechanically necessary "
            "for a covered part. Link it to the most relevant part by index. "
            "Return JSON."
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_labor_linkage_response(
        self,
        content: str,
        labor_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Parse the LLM response for labor linkage classification.

        Args:
            content: Raw JSON response from LLM
            labor_items: Original labor items (for index reference)

        Returns:
            List of dicts with index, is_covered, linked_part_index,
            confidence, reasoning.
        """
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            llm_results = data.get("labor_items", [])

            by_index = {}
            for r in llm_results:
                idx = r.get("index")
                if idx is not None:
                    by_index[idx] = r

            results = []
            for item in labor_items:
                idx = item["index"]
                if idx in by_index:
                    r = by_index[idx]
                    results.append({
                        "index": idx,
                        "is_covered": bool(r.get("is_covered", False)),
                        "linked_part_index": r.get("linked_part_index"),
                        "confidence": float(r.get("confidence", 0.5)),
                        "reasoning": r.get("reasoning", "No reasoning provided"),
                    })
                else:
                    results.append({
                        "index": idx,
                        "is_covered": False,
                        "linked_part_index": None,
                        "confidence": 0.0,
                        "reasoning": "Missing from LLM response (conservative default)",
                    })

            return results

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse labor linkage response: %s", e)
            return [
                {
                    "index": item["index"],
                    "is_covered": False,
                    "linked_part_index": None,
                    "confidence": 0.0,
                    "reasoning": f"Failed to parse LLM response: {str(e)[:200]}",
                }
                for item in labor_items
            ]

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

    # ------------------------------------------------------------------
    # Primary repair identification (single LLM call per claim)
    # ------------------------------------------------------------------

    def determine_primary_repair(
        self,
        all_items: List[Dict[str, Any]],
        covered_components: Dict[str, List[str]],
        claim_id: Optional[str] = None,
        repair_description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Identify the primary repair component using LLM.

        Makes ONE LLM call that examines all line items and identifies which
        item represents the main repair being performed.

        Args:
            all_items: List of dicts with keys: index, description, item_type,
                       total_price, coverage_status, coverage_category
            covered_components: Policy's covered components by category
            claim_id: Claim ID for audit trail
            repair_description: Damage/diagnostic context from claim documents
                (error codes, fault descriptions, repair reason)

        Returns:
            Dict with: primary_item_index, component, category, confidence,
            reasoning. Returns None on failure (caller falls back to heuristic).
        """
        if not all_items:
            return None

        messages = self._build_primary_repair_prompt(
            all_items, covered_components, repair_description,
        )

        client = self._get_client()
        client.set_context(
            claim_id=claim_id,
            call_purpose="primary_repair_identification",
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
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "json_object"},
                )
                self._llm_calls += 1

                content = response.choices[0].message.content
                return self._parse_primary_repair_response(
                    content, all_items,
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
                        "Primary repair LLM call failed (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        attempt + 1, max_attempts, e, delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Primary repair identification failed after %d attempts: %s",
                        max_attempts, e,
                    )

        self._llm_calls += 1
        return None

    def _build_primary_repair_prompt(
        self,
        all_items: List[Dict[str, Any]],
        covered_components: Dict[str, List[str]],
        repair_description: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build prompt messages for primary repair identification.

        Tries workspace prompt file first, then inline fallback.
        """
        # Format line items with index, description, type, price, category
        item_lines = []
        for item in all_items:
            category = item.get("coverage_category") or "N/A"
            item_lines.append(
                f"  [{item['index']}] {item['description']} | "
                f"type={item.get('item_type', 'unknown')} | "
                f"price={item.get('total_price', 0):.2f} CHF | "
                f"category={category}"
            )
        items_text = "\n".join(item_lines)

        # Format covered components
        comp_lines = []
        for category, parts in covered_components.items():
            if parts:
                parts_list = ", ".join(parts[:15])
                if len(parts) > 15:
                    parts_list += f", ... ({len(parts)} total)"
                comp_lines.append(f"  - {category}: {parts_list}")
        comp_text = "\n".join(comp_lines) if comp_lines else "  (none)"

        # Format repair description context
        repair_context_text = repair_description or ""

        try:
            from context_builder.utils.prompt_loader import load_prompt

            prompt_data = load_prompt(
                self.config.primary_repair_prompt_name,
                line_items=items_text,
                covered_components=comp_text,
                repair_description=repair_context_text,
            )
            return prompt_data["messages"]
        except FileNotFoundError:
            logger.debug(
                "Prompt file '%s' not found, using inline primary repair prompt",
                self.config.primary_repair_prompt_name,
            )

        # Inline fallback
        repair_context_block = ""
        if repair_description:
            repair_context_block = (
                f"\n\nDiagnostic / damage context from claim documents:\n"
                f"{repair_description}\n"
            )

        system_prompt = (
            "You are an automotive repair analyst for a warranty insurance "
            "company. Given a repair invoice, identify the PRIMARY component "
            "whose failure CAUSED the repair visit.\n\n"
            "RULES:\n"
            "1. Use the diagnostic error codes and damage description (if "
            "provided) as the strongest signal for what actually failed.\n"
            "2. Look at labor descriptions to understand the repair narrative "
            "(e.g. 'Mechatronik' labor = electronic/control unit work).\n"
            "3. The most expensive part is NOT necessarily the primary -- "
            "a part can be expensive yet only replaced opportunistically "
            "while the transmission/engine is open.\n"
            "4. Do NOT pick consumables, fasteners, gaskets, or fluids.\n"
            "5. A part costing less than 5% of the total invoice is almost "
            "certainly ancillary. Only select it as primary if the labor "
            "descriptions explicitly name that component as the repair subject.\n"
            "6. If diagnostic codes point to a specific component (e.g. "
            "parking brake solenoid, control unit), that component is the "
            "primary -- even if another part costs more.\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"primary_item_index": <int>, "component": "<english_type>", '
            '"category": "<coverage_category>", "confidence": <float 0-1>, '
            '"reasoning": "<brief>"}'
        )
        user_prompt = (
            f"Line items:\n{items_text}\n\n"
            f"Policy covered components:\n{comp_text}\n"
            f"{repair_context_block}\n"
            "Which line item represents the PRIMARY repair component -- "
            "the component whose failure caused the repair visit? "
            "Return the item index."
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_primary_repair_response(
        self,
        content: str,
        all_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Parse the LLM response for primary repair identification.

        Args:
            content: Raw JSON response from LLM
            all_items: Original items (for index validation)

        Returns:
            Dict with primary_item_index, component, category, confidence,
            reasoning. Returns None if parsing fails or index is invalid.
        """
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())

            primary_index = data.get("primary_item_index")
            if primary_index is None:
                logger.warning("LLM primary repair response missing primary_item_index")
                return None

            primary_index = int(primary_index)
            if primary_index < 0 or primary_index >= len(all_items):
                logger.warning(
                    "LLM returned out-of-range primary_item_index=%d (valid: 0-%d)",
                    primary_index, len(all_items) - 1,
                )
                return None

            return {
                "primary_item_index": primary_index,
                "component": data.get("component"),
                "category": data.get("category"),
                "confidence": float(data.get("confidence", 0.5)),
                "reasoning": data.get("reasoning", "No reasoning provided"),
            }

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Failed to parse primary repair response: %s", e)
            return None

    def get_llm_call_count(self) -> int:
        """Get the number of LLM calls made."""
        return self._llm_calls

    def reset_call_count(self) -> None:
        """Reset the LLM call counter."""
        self._llm_calls = 0
