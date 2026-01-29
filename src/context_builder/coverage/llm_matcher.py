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
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from context_builder.coverage.schemas import (
    CoverageStatus,
    LineItemCoverage,
    MatchMethod,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMMatcherConfig:
    """Configuration for LLM matcher."""

    prompt_name: str = "nsa_coverage"  # Prompt file name (without .md)
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 512
    min_confidence_for_coverage: float = 0.60
    review_needed_threshold: float = 0.60
    # Lower threshold for "not covered" - we're more willing to deny than approve
    review_needed_threshold_not_covered: float = 0.40

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "LLMMatcherConfig":
        """Create config from dictionary."""
        return cls(
            prompt_name=config.get("prompt_name", "nsa_coverage"),
            model=config.get("model", "gpt-4o"),
            temperature=config.get("temperature", 0.0),
            max_tokens=config.get("max_tokens", 512),
            min_confidence_for_coverage=config.get("min_confidence_for_coverage", 0.60),
            review_needed_threshold=config.get("review_needed_threshold", 0.60),
            review_needed_threshold_not_covered=config.get("review_needed_threshold_not_covered", 0.40),
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

        # Get client and set context
        client = self._get_client()
        client.set_context(
            claim_id=claim_id,
            call_purpose="coverage_analysis",
        )

        try:
            # Make LLM call
            response = client.chat_completions_create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                response_format={"type": "json_object"},
            )

            self._llm_calls += 1

            # Parse response
            content = response.choices[0].message.content
            result = self._parse_llm_response(content)

            # Cap confidence for vague descriptions to ensure human review
            confidence = result.confidence
            reasoning = result.reasoning
            if self._detect_vague_description(description) and confidence > 0.50:
                confidence = 0.50
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
                covered_amount=total_price if status == CoverageStatus.COVERED else 0.0,
                not_covered_amount=0.0 if status == CoverageStatus.COVERED else total_price,
            )

        except Exception as e:
            logger.error(f"LLM coverage analysis failed: {e}")
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
                match_reasoning=f"LLM analysis failed: {str(e)}",
                covered_amount=0.0,
                not_covered_amount=total_price,
            )

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

        Note: This makes one LLM call per item. For many items,
        consider batching in the prompt or using keyword matching first.

        Args:
            items: List of line item dictionaries
            covered_categories: Categories covered by policy
            covered_components: Components per category from policy
            excluded_components: Excluded components per category from policy
            claim_id: Claim ID for audit context
            on_progress: Optional callback called after each LLM call with increment (1)
            covered_parts_in_claim: List of covered parts from this claim (for labor context)

        Returns:
            List of LineItemCoverage results
        """
        results = []

        for item in items:
            result = self.match(
                description=item.get("description", ""),
                item_type=item.get("item_type", ""),
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

            # Notify progress callback
            if on_progress:
                on_progress(1)

        logger.info(f"LLM matcher processed {len(items)} items with {self._llm_calls} LLM calls")
        return results

    def get_llm_call_count(self) -> int:
        """Get the number of LLM calls made."""
        return self._llm_calls

    def reset_call_count(self) -> None:
        """Reset the LLM call counter."""
        self._llm_calls = 0
