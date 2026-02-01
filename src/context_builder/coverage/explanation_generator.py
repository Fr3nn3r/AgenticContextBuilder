"""Post-processing generator for non-covered item explanations.

Groups non-covered line items by exclusion reason and produces
adjuster-ready explanation text.

Two modes:
  1. **LLM mode** (default when ``llm_client`` is provided): Sends grouped
     items + policy context to an LLM that rewrites technical reasoning into
     clean English explanations.  Falls back to template mode on failure.
  2. **Template mode** (``llm_client=None``): Deterministic template fill
     from customer YAML config — no network calls.

Customer config provides reason labels, explanation templates, and policy
references.  Core code provides the grouping algorithm and LLM/template-fill
framework.
"""

import json as _json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from context_builder.coverage.schemas import (
    CoverageAnalysisResult,
    CoverageStatus,
    LineItemCoverage,
    NonCoveredExplanation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default reason-inference patterns (backward compat for legacy results
# that lack the exclusion_reason field).  Customer config can override.
# ---------------------------------------------------------------------------
_DEFAULT_REASON_PATTERNS: List[Tuple[str, str]] = [
    (r"^Fee items \(", "fee"),
    (r"exclusion pattern:", "exclusion_pattern"),
    (r"Consumable item not covered:", "consumable"),
    (r"non-covered pattern:", "non_covered_labor"),
    (r"Generic description", "generic_description"),
    (r"\[OVERRIDE: Component is in excluded list\]", "component_excluded"),
    (r"\[DEMOTED:", "demoted_no_anchor"),
    (r"\[REVIEW: category", "category_not_covered"),
    (r"not in policy's exhaustive parts list", "component_not_in_list"),
    (r"explicitly excluded by policy", "component_excluded"),
    (r"which is not covered", "category_not_covered"),
]


@dataclass
class TemplateEntry:
    """A single explanation template with optional policy reference."""

    explanation_template: Optional[str] = None
    policy_reference: Optional[str] = None


@dataclass
class ExplanationConfig:
    """Configuration for the explanation generator.

    All customer-specific vocabulary lives here — loaded from YAML at
    runtime.  Core code only sees the structure.
    """

    templates: Dict[str, TemplateEntry] = field(default_factory=dict)
    category_templates: Dict[str, TemplateEntry] = field(default_factory=dict)
    category_subgroup_reasons: List[str] = field(default_factory=list)
    summary_template: str = (
        "{count} item(s) ({currency} {total}) are not covered. {reasons_list}"
    )
    reason_patterns: List[Tuple[str, str]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> "ExplanationConfig":
        """Load config from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        templates: Dict[str, TemplateEntry] = {}
        for reason, entry in data.get("templates", {}).items():
            if isinstance(entry, dict):
                templates[reason] = TemplateEntry(
                    explanation_template=entry.get("explanation"),
                    policy_reference=entry.get("policy_reference"),
                )

        category_templates: Dict[str, TemplateEntry] = {}
        for cat, entry in data.get("category_templates", {}).items():
            if isinstance(entry, dict):
                category_templates[cat] = TemplateEntry(
                    explanation_template=entry.get("explanation"),
                    policy_reference=entry.get("policy_reference"),
                )

        reason_patterns: List[Tuple[str, str]] = []
        for rp in data.get("reason_patterns", []):
            if isinstance(rp, dict) and "pattern" in rp and "reason" in rp:
                reason_patterns.append((rp["pattern"], rp["reason"]))

        return cls(
            templates=templates,
            category_templates=category_templates,
            category_subgroup_reasons=data.get("category_subgroup_reasons", []),
            summary_template=data.get(
                "summary_template",
                "{count} item(s) ({currency} {total}) are not covered. {reasons_list}",
            ),
            reason_patterns=reason_patterns,
        )

    @classmethod
    def default(cls) -> "ExplanationConfig":
        """Minimal English fallback config."""
        return cls(
            templates={
                "fee": TemplateEntry(
                    explanation_template="Fee items are not covered by the policy.",
                ),
                "consumable": TemplateEntry(
                    explanation_template="Consumable items are not covered.",
                ),
                "exclusion_pattern": TemplateEntry(
                    explanation_template="Items matching standard exclusion patterns.",
                ),
                "non_covered_labor": TemplateEntry(
                    explanation_template="Diagnostic/investigative labor is not covered.",
                ),
                "generic_description": TemplateEntry(
                    explanation_template="Insufficient description for coverage determination.",
                ),
                "component_excluded": TemplateEntry(
                    explanation_template="Component is on the policy exclusion list.",
                ),
                "component_not_in_list": TemplateEntry(
                    explanation_template=(
                        "Component is not in the policy's exhaustive parts list"
                        " for category '{category}'."
                    ),
                ),
                "category_not_covered": TemplateEntry(
                    explanation_template=(
                        "Category '{category}' is not covered by the policy."
                    ),
                ),
                "demoted_no_anchor": TemplateEntry(
                    explanation_template=(
                        "Labor not covered: no covered parts to anchor this work."
                    ),
                ),
            },
            category_subgroup_reasons=[
                "category_not_covered",
                "component_not_in_list",
                "component_excluded",
            ],
        )


def infer_exclusion_reason(
    item: LineItemCoverage,
    reason_patterns: Optional[List[Tuple[str, str]]] = None,
) -> str:
    """Infer exclusion reason from match_reasoning text (backward compat).

    Used when ``item.exclusion_reason`` is not set (legacy results).

    Args:
        item: Line item coverage result.
        reason_patterns: Optional list of (regex, reason) pairs.  Falls
            back to built-in defaults if not provided.

    Returns:
        Reason string (e.g. ``"fee"``, ``"consumable"``).
    """
    patterns = reason_patterns or _DEFAULT_REASON_PATTERNS
    text = item.match_reasoning or ""
    for pattern, reason in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return reason
    return "other"


class ExplanationGenerator:
    """Groups non-covered items and produces adjuster-ready explanations.

    Supports two modes:
      - **LLM mode**: pass ``llm_client`` + ``covered_components`` to
        ``generate()`` and the generator will call the LLM once to rewrite
        all group explanations.  Falls back to template mode on error.
      - **Template mode** (default): deterministic template fill from config.
    """

    # Default prompt name (resolved by prompt_loader)
    PROMPT_NAME = "non_covered_explanation"

    def __init__(self, config: Optional[ExplanationConfig] = None):
        self.config = config or ExplanationConfig.default()

    def generate(
        self,
        result: CoverageAnalysisResult,
        currency: str = "CHF",
        covered_components: Optional[Dict[str, List[str]]] = None,
        excluded_components: Optional[Dict[str, List[str]]] = None,
        llm_client: Optional[Any] = None,
    ) -> Tuple[List[NonCoveredExplanation], str]:
        """Generate explanations for all non-covered items.

        Args:
            result: Coverage analysis result with line items.
            currency: Currency code for summary.
            covered_components: Policy's covered components by category
                (required for LLM mode).
            excluded_components: Policy's excluded components by category.
            llm_client: An ``AuditedOpenAIClient`` instance.  When provided,
                the generator will make one LLM call to rewrite all group
                explanations.  When ``None``, uses template-fill mode.

        Returns:
            Tuple of (explanations list, summary string).
        """
        # 1. Filter non-covered items (NOT_COVERED + REVIEW_NEEDED)
        non_covered = [
            item
            for item in result.line_items
            if item.coverage_status
            in (CoverageStatus.NOT_COVERED, CoverageStatus.REVIEW_NEEDED)
        ]

        if not non_covered:
            return [], ""

        # 2. Classify each item
        classified: List[Tuple[str, LineItemCoverage]] = []
        for item in non_covered:
            reason = item.exclusion_reason or infer_exclusion_reason(
                item, self.config.reason_patterns or None
            )
            classified.append((reason, item))

        # 3. Group by composite key
        groups: Dict[
            Tuple[str, Optional[str]], List[LineItemCoverage]
        ] = {}
        for reason, item in classified:
            if reason in self.config.category_subgroup_reasons:
                key = (reason, item.coverage_category)
            else:
                key = (reason, None)
            groups.setdefault(key, []).append(item)

        # 4. Build explanations (template-fill first, then optionally LLM-rewrite)
        explanations: List[NonCoveredExplanation] = []
        for (reason, category), items in groups.items():
            explanation_text = self._resolve_template(reason, category)
            policy_ref = self._resolve_policy_reference(reason, category)
            total = sum(item.not_covered_amount for item in items)
            min_conf = min(item.match_confidence for item in items)

            # If no template, fall back to first item's match_reasoning
            if not explanation_text:
                explanation_text = items[0].match_reasoning

            explanations.append(
                NonCoveredExplanation(
                    exclusion_reason=reason,
                    items=[item.description for item in items],
                    item_codes=[item.item_code for item in items],
                    category=category,
                    total_amount=round(total, 2),
                    explanation=explanation_text,
                    policy_reference=policy_ref,
                    match_confidence=min_conf,
                )
            )

        # 5. Sort by total_amount descending (biggest groups first)
        explanations.sort(key=lambda e: e.total_amount, reverse=True)

        # 5b. LLM rewrite (if client provided)
        if llm_client is not None and covered_components:
            explanations = self._llm_rewrite(
                explanations,
                currency=currency,
                covered_components=covered_components,
                excluded_components=excluded_components or {},
                llm_client=llm_client,
            )

        # 6. Generate summary
        total_amount = round(
            sum(e.total_amount for e in explanations), 2
        )
        reason_labels = sorted(
            {e.exclusion_reason for e in explanations}
        )
        reasons_list = ", ".join(reason_labels)

        summary = self.config.summary_template.format(
            count=len(non_covered),
            currency=currency,
            total=f"{total_amount:.2f}",
            reasons_list=reasons_list,
        )

        return explanations, summary

    # ------------------------------------------------------------------
    # LLM rewrite
    # ------------------------------------------------------------------

    def _llm_rewrite(
        self,
        explanations: List[NonCoveredExplanation],
        *,
        currency: str,
        covered_components: Dict[str, List[str]],
        excluded_components: Dict[str, List[str]],
        llm_client: Any,
    ) -> List[NonCoveredExplanation]:
        """Rewrite explanation text via a single LLM call.

        On any failure the original template-filled explanations are
        returned unchanged (graceful fallback).
        """
        try:
            messages = self._build_llm_messages(
                explanations,
                currency=currency,
                covered_components=covered_components,
                excluded_components=excluded_components,
            )
            response = llm_client.chat_completions_create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.0,
                max_tokens=1500,
            )
            content = response.choices[0].message.content
            rewritten = self._parse_llm_response(content, explanations)
            return rewritten
        except Exception:
            logger.warning(
                "LLM rewrite of non-covered explanations failed; "
                "falling back to template explanations",
                exc_info=True,
            )
            return explanations

    def _build_llm_messages(
        self,
        explanations: List[NonCoveredExplanation],
        *,
        currency: str,
        covered_components: Dict[str, List[str]],
        excluded_components: Dict[str, List[str]],
    ) -> List[Dict[str, str]]:
        """Build OpenAI-format messages for the rewrite prompt.

        Tries to load the prompt from a markdown file first (using the
        standard prompt_loader), falling back to an inline prompt.
        """
        # Prepare group data for the prompt
        groups_data = []
        for idx, exp in enumerate(explanations, 1):
            groups_data.append({
                "group": idx,
                "exclusion_reason": exp.exclusion_reason,
                "category": exp.category,
                "total_amount": exp.total_amount,
                "items": exp.items,
                "technical_reasoning": exp.explanation,
            })

        # Try prompt file first
        try:
            from context_builder.utils.prompt_loader import load_prompt

            prompt_data = load_prompt(
                self.PROMPT_NAME,
                covered_components=covered_components,
                excluded_components=excluded_components,
                groups=groups_data,
                currency=currency,
            )
            return prompt_data["messages"]
        except FileNotFoundError:
            logger.debug(
                f"Prompt file '{self.PROMPT_NAME}' not found, using inline prompt"
            )

        # Inline fallback
        return self._build_inline_messages(
            groups_data,
            currency=currency,
            covered_components=covered_components,
            excluded_components=excluded_components,
        )

    @staticmethod
    def _build_inline_messages(
        groups_data: List[Dict[str, Any]],
        *,
        currency: str,
        covered_components: Dict[str, List[str]],
        excluded_components: Dict[str, List[str]],
    ) -> List[Dict[str, str]]:
        """Build inline prompt messages (used when no .md file found)."""
        system_msg = (
            "You are writing coverage denial explanations for an insurance "
            "adjuster. Write in English. Be concise (1-2 sentences per group). "
            "Do not invent policy clause numbers. When a part is not in the "
            "covered list, cite the actual covered parts for that category."
        )

        # Build policy context
        lines = ["## Policy coverage"]
        for cat, parts in covered_components.items():
            lines.append(f"- **{cat}**: {', '.join(parts)}")

        if excluded_components:
            lines.append("")
            lines.append("## Policy exclusions")
            for cat, parts in excluded_components.items():
                lines.append(f"- **{cat}**: {', '.join(parts)}")

        lines.append("")
        lines.append("## Non-covered items to explain")
        lines.append("")

        for g in groups_data:
            cat_label = f" ({g['category']})" if g.get("category") else ""
            lines.append(
                f"### Group {g['group']}: {g['exclusion_reason']}{cat_label}"
            )
            lines.append(f"Items ({g['total_amount']} {currency}):")
            for item in g["items"]:
                lines.append(f"- {item}")
            lines.append(f"Technical reasoning: {g['technical_reasoning']}")
            lines.append("")

        lines.append('Respond in JSON:')
        lines.append('[')
        lines.append('  {"group": 1, "explanation": "..."},')
        lines.append('  ...')
        lines.append(']')

        user_msg = "\n".join(lines)

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    @staticmethod
    def _parse_llm_response(
        content: str,
        explanations: List[NonCoveredExplanation],
    ) -> List[NonCoveredExplanation]:
        """Parse LLM JSON response and apply to explanations.

        Expected format: ``[{"group": 1, "explanation": "..."}, ...]``

        Returns a new list with updated explanation text.  On parse error,
        raises so the caller can fall back.
        """
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[: -3].rstrip()

        items = _json.loads(text)

        # Build lookup: group number -> explanation text
        lookup: Dict[int, str] = {}
        for item in items:
            group_num = item.get("group")
            expl_text = item.get("explanation")
            if group_num is not None and expl_text:
                lookup[int(group_num)] = expl_text

        # Apply to explanations (1-indexed)
        updated: List[NonCoveredExplanation] = []
        for idx, exp in enumerate(explanations, 1):
            if idx in lookup:
                updated.append(exp.model_copy(update={
                    "explanation": lookup[idx],
                    "policy_reference": None,
                }))
            else:
                updated.append(exp)

        return updated

    def _resolve_template(
        self, reason: str, category: Optional[str]
    ) -> Optional[str]:
        """Look up explanation template for a reason/category pair."""
        # Check category-specific template first (for sub-grouped reasons)
        if category and category in self.config.category_templates:
            cat_entry = self.config.category_templates[category]
            if cat_entry.explanation_template:
                return cat_entry.explanation_template.format(
                    category=category or ""
                )

        # Fall back to reason template
        entry = self.config.templates.get(reason)
        if entry and entry.explanation_template:
            return entry.explanation_template.format(
                category=category or ""
            )

        return None

    def _resolve_policy_reference(
        self, reason: str, category: Optional[str]
    ) -> Optional[str]:
        """Look up policy reference for a reason/category pair."""
        # Check category-specific first
        if category and category in self.config.category_templates:
            cat_entry = self.config.category_templates[category]
            if cat_entry.policy_reference:
                return cat_entry.policy_reference

        # Fall back to reason-level
        entry = self.config.templates.get(reason)
        if entry:
            return entry.policy_reference

        return None
