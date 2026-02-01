"""Assessment processor for claim-level pipeline.

This processor evaluates a claim based on aggregated facts and produces
a decision (APPROVE, REJECT, REFER_TO_HUMAN) with supporting checks and rationale.

All LLM calls are logged via the compliance audit service.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from context_builder.services.openai_client import get_openai_client

from context_builder.pipeline.claim_stages.context import ClaimContext
from context_builder.pipeline.claim_stages.processing import (
    Processor,
    ProcessorConfig,
    register_processor,
)
from context_builder.services.llm_audit import AuditedOpenAIClient, get_llm_audit_service
from context_builder.storage.workspace_paths import get_workspace_logs_dir
from context_builder.schemas.assessment_response import (
    AssessmentResponse,
    MIN_EXPECTED_CHECKS,
    validate_assessment_completeness,
)

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
        self._client = None
        self._audited_client: Optional[AuditedOpenAIClient] = None

    def _ensure_client(self) -> None:
        """Ensure OpenAI client is initialized (uses Azure OpenAI if configured)."""
        if self._client is None:
            self._client = get_openai_client()
            audit_service = get_llm_audit_service(get_workspace_logs_dir())
            self._audited_client = AuditedOpenAIClient(self._client, audit_service)

    # ── Screening → Assessment mapping helpers ──────────────────────

    @staticmethod
    def _map_screening_checks(screening_checks: List[Dict]) -> List[Dict]:
        """Map ScreeningCheck dicts to CheckResult dicts.

        Field renames:
            check_id → check_number
            verdict  → result  (SKIPPED → NOT_CHECKED)
            reason   → details
            evidence dict keys → evidence_refs list
        """
        verdict_map = {
            "PASS": "PASS",
            "FAIL": "FAIL",
            "INCONCLUSIVE": "INCONCLUSIVE",
            "SKIPPED": "NOT_CHECKED",
        }
        mapped = []
        for sc in screening_checks:
            mapped.append({
                "check_number": sc["check_id"],
                "check_name": sc["check_name"],
                "result": verdict_map.get(sc["verdict"], "INCONCLUSIVE"),
                "details": sc.get("reason", ""),
                "evidence_refs": list(sc.get("evidence", {}).keys()),
            })
        return mapped

    @staticmethod
    def _map_screening_payout(payout_data: Dict) -> Dict:
        """Map ScreeningPayoutCalculation dict to PayoutCalculation dict.

        Key renames:
            covered_total     → covered_subtotal
            not_covered_total → non_covered_deductions
            deductible_amount → deductible
        Computed:
            total_claimed = covered_total + not_covered_total
            coverage_percent: float → int
            after_coverage = capped_amount (coverage % already applied)
            capped_amount = capped_amount when max_coverage_applied else None
        """
        covered = payout_data.get("covered_total", 0.0)
        not_covered = payout_data.get("not_covered_total", 0.0)
        coverage_pct = payout_data.get("coverage_percent")
        max_cov_applied = payout_data.get("max_coverage_applied", False)
        capped = payout_data.get("capped_amount", 0.0)

        return {
            "total_claimed": covered + not_covered,
            "non_covered_deductions": not_covered,
            "covered_subtotal": covered,
            "coverage_percent": int(coverage_pct) if coverage_pct is not None else 0,
            "after_coverage": capped,
            "max_coverage_applied": max_cov_applied,
            "capped_amount": capped if max_cov_applied else None,
            "deductible": payout_data.get("deductible_amount", 0.0),
            "after_deductible": payout_data.get("after_deductible", 0.0),
            "vat_adjusted": payout_data.get("vat_adjusted", False),
            "vat_deduction": payout_data.get("vat_deduction", 0.0),
            "policyholder_type": payout_data.get("policyholder_type", "individual"),
            "final_payout": payout_data.get("final_payout", 0.0),
            "currency": payout_data.get("currency", "CHF"),
        }

    @staticmethod
    def _zero_payout() -> Dict:
        """Return a zeroed PayoutCalculation dict for auto-rejects without payout data."""
        return {
            "total_claimed": 0.0,
            "non_covered_deductions": 0.0,
            "covered_subtotal": 0.0,
            "coverage_percent": 0,
            "after_coverage": 0.0,
            "max_coverage_applied": False,
            "capped_amount": None,
            "deductible": 0.0,
            "after_deductible": 0.0,
            "vat_adjusted": False,
            "vat_deduction": 0.0,
            "policyholder_type": "individual",
            "final_payout": 0.0,
            "currency": "CHF",
        }

    @staticmethod
    def _extract_fraud_indicators(screening_checks: List[Dict]) -> List[Dict]:
        """Extract fraud indicators from hard-fail screening checks.

        Checks with verdict=FAIL and is_hard_fail=True become
        FraudIndicator dicts with severity="high".
        """
        indicators = []
        for sc in screening_checks:
            if sc.get("verdict") == "FAIL" and sc.get("is_hard_fail"):
                indicators.append({
                    "indicator": f"Hard fail: {sc['check_name']}",
                    "severity": "high",
                    "details": sc.get("reason", ""),
                })
        return indicators

    # ── Auto-reject response builder ─────────────────────────────────

    def _build_auto_reject_response(
        self, claim_id: str, screening: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a complete AssessmentResponse dict for auto-rejected claims.

        Args:
            claim_id: The claim identifier.
            screening: The screening result dict (ScreeningResult.model_dump()).

        Returns:
            Validated AssessmentResponse dict.
        """
        # Map screening checks (1–5b)
        checks = self._map_screening_checks(screening.get("checks", []))

        # Synthesize check 6 (payout_calculation)
        has_payout = screening.get("payout") is not None
        checks.append({
            "check_number": "6",
            "check_name": "payout_calculation",
            "result": "PASS" if has_payout else "NOT_CHECKED",
            "details": (
                "Payout computed by screening"
                if has_payout
                else f"Payout not computed: {screening.get('payout_error', 'unknown')}"
            ),
            "evidence_refs": [],
        })

        # Synthesize check 7 (final_decision)
        checks.append({
            "check_number": "7",
            "check_name": "final_decision",
            "result": "FAIL",
            "details": screening.get("auto_reject_reason", "Auto-rejected by screening"),
            "evidence_refs": [],
        })

        # Map payout — keep breakdown for transparency but zero final_payout
        # on rejection (a rejected claim must never show a positive payout).
        if screening.get("payout"):
            payout = self._map_screening_payout(screening["payout"])
            payout["final_payout"] = 0.0
        else:
            payout = self._zero_payout()

        # Build fraud indicators from hard fails
        fraud_indicators = self._extract_fraud_indicators(screening.get("checks", []))

        # Assemble the response dict
        response_dict = {
            "schema_version": "claims_assessment_v2",
            "assessment_method": "auto_reject",
            "claim_id": claim_id,
            "assessment_timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": "REJECT",
            "decision_rationale": screening.get(
                "auto_reject_reason", "Auto-rejected by screening"
            ),
            "confidence_score": 1.0,
            "checks": checks,
            "payout": payout,
            "data_gaps": [],
            "fraud_indicators": fraud_indicators,
            "recommendations": ["Claim auto-rejected by deterministic screening."],
        }

        # Validate via Pydantic
        validated = AssessmentResponse.model_validate(response_dict)

        # Run completeness check
        warnings = validate_assessment_completeness(validated)
        if warnings:
            for warning in warnings:
                logger.warning(f"Auto-reject validation warning: {warning}")

        return validated.model_dump()

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
        logger.info(f"Running assessment for claim {context.claim_id}")

        if not context.aggregated_facts:
            raise ValueError(f"No aggregated facts available for claim {context.claim_id}")

        # Check for auto-reject from screening (before initializing OpenAI client)
        screening = context.screening_result  # Dict or None

        if screening and screening.get("auto_reject"):
            logger.info(
                f"Auto-rejecting claim {context.claim_id}: "
                f"{screening.get('auto_reject_reason')}"
            )
            result = self._build_auto_reject_response(context.claim_id, screening)
            result["claim_id"] = context.claim_id
            result["prompt_version"] = config.prompt_version
            result["model"] = "none (auto-reject)"
            if on_token_update:
                on_token_update(0, 0)
            return result

        # LLM path: initialize OpenAI client
        self._ensure_client()

        # Set audit context
        self._audited_client.set_context(
            claim_id=context.claim_id,
            run_id=context.run_id,
            call_purpose="assessment",
        )

        # Build prompt with facts (inject screening context if available)
        system_prompt, user_prompt = self._build_prompts(
            config.prompt_content or "",
            context.aggregated_facts,
            context.claim_id,
            screening=screening if screening and not screening.get("auto_reject") else None,
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

        # Override APPROVE → REJECT when payout is zero
        final_payout = (result.get("payout") or {}).get("final_payout", 0.0)
        if result.get("decision") == "APPROVE" and final_payout <= 0:
            logger.info(
                f"Overriding APPROVE → REJECT for claim {context.claim_id}: "
                f"final_payout={final_payout}"
            )
            result["decision"] = "REJECT"
            result["decision_rationale"] = (
                f"Rejected: covered amount does not exceed deductible "
                f"(final payout: {final_payout:.2f}). "
                f"Original rationale: {result.get('decision_rationale', '')}"
            )

        # Zero payout when decision is REJECT (rejected claims must not show positive payout)
        if result.get("decision") == "REJECT" and final_payout > 0:
            logger.info(
                f"Zeroing payout for rejected claim {context.claim_id}: "
                f"final_payout was {final_payout}"
            )
            result.setdefault("payout", {})["final_payout"] = 0.0

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

    @staticmethod
    def _format_screening_context(screening: Dict[str, Any]) -> str:
        """Format screening results as structured text for LLM context.

        Produces a human-readable summary instead of raw JSON, organized as:
        - Check verdicts table
        - Checks requiring LLM resolution (INCONCLUSIVE / requires_llm)
        - Pre-computed payout summary
        """
        lines = ["## Pre-computed Screening Results", ""]

        # Check verdicts table
        checks = screening.get("checks", [])
        lines.append("### Check Verdicts")
        lines.append("| # | Check | Verdict | Details |")
        lines.append("|---|-------|---------|---------|")
        for check in checks:
            lines.append(
                f"| {check['check_id']} | {check['check_name']} "
                f"| {check['verdict']} | {check.get('reason', '')} |"
            )
        lines.append("")

        # Checks requiring LLM resolution
        llm_checks = [
            c for c in checks
            if c.get("verdict") == "INCONCLUSIVE" or c.get("requires_llm")
        ]
        if llm_checks:
            lines.append("### Checks Requiring Your Resolution")
            lines.append("")
            for check in llm_checks:
                lines.append(
                    f"**Check {check['check_id']}: {check['check_name']}** "
                    f"— {check['verdict']}"
                )
                lines.append(f"Reason: {check.get('reason', 'N/A')}")
                evidence = check.get("evidence", {})
                if evidence:
                    ev_str = json.dumps(evidence, default=str)
                    lines.append(f"Evidence: {ev_str}")
                lines.append("")

        # Pre-computed payout
        payout = screening.get("payout")
        if payout:
            currency = payout.get("currency", "CHF")
            # Use `or 0` instead of .get() defaults because keys may exist with None values
            lines.append("### Pre-computed Payout")
            lines.append(f"- Covered total: {currency} {payout.get('covered_total') or 0:,.2f}")
            lines.append(f"- Not covered total: {currency} {payout.get('not_covered_total') or 0:,.2f}")
            lines.append(f"- Coverage percent: {payout.get('coverage_percent') or 0}%")
            if payout.get("max_coverage_applied"):
                lines.append(
                    f"- Capped amount: {currency} {payout.get('capped_amount') or 0:,.2f} "
                    f"(max coverage applied)"
                )
            else:
                lines.append(
                    f"- After coverage: {currency} {payout.get('capped_amount') or 0:,.2f}"
                )
            lines.append(
                f"- Deductible: {currency} {payout.get('deductible_amount') or 0:,.2f} "
                f"({payout.get('deductible_percent') or 0}%, "
                f"min {currency} {payout.get('deductible_minimum') or 0:,.2f})"
            )
            lines.append(f"- After deductible: {currency} {payout.get('after_deductible') or 0:,.2f}")
            if payout.get("vat_adjusted"):
                lines.append(
                    f"- VAT deduction: {currency} {payout.get('vat_deduction') or 0:,.2f} "
                    f"({payout.get('policyholder_type', 'individual')})"
                )
            lines.append(f"- Final payout: {currency} {payout.get('final_payout') or 0:,.2f}")
            lines.append("")
        elif screening.get("payout_error"):
            lines.append("### Payout")
            lines.append(f"Payout not computed: {screening['payout_error']}")
            lines.append("")

        return "\n".join(lines)

    def _build_prompts(
        self,
        prompt_template: str,
        facts: Dict[str, Any],
        claim_id: str,
        screening: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Build system and user prompts for assessment.

        Args:
            prompt_template: The prompt template from config.
            facts: Aggregated claim facts.
            claim_id: The claim identifier.
            screening: Optional screening result dict to inject as context.

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

        # Build screening context block if available
        screening_block = ""
        if screening:
            screening_block = self._format_screening_context(screening) + "\n"

        # Build user prompt with facts
        user_prompt = f"""Evaluate the following claim:

Claim ID: {claim_id}
{screening_block}
Aggregated Facts:
```json
{facts_json}
```

{user_template}

Provide your assessment as JSON matching the response schema."""

        return system_prompt, user_prompt

    def _build_response_format(self) -> Dict[str, Any]:
        """Build the response_format parameter for structured JSON output.

        Attempts to use json_schema mode for strict enforcement.
        Falls back to json_object if schema mode is not supported.

        Returns:
            Response format dict for OpenAI API.
        """
        # Get JSON schema from Pydantic model
        schema = AssessmentResponse.model_json_schema()

        # OpenAI strict mode requires additionalProperties: false on all objects
        # and all properties must be required
        schema = self._prepare_schema_for_strict_mode(schema)

        # Use json_schema mode for strict enforcement
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "assessment_response",
                "strict": True,
                "schema": schema,
            },
        }

    def _prepare_schema_for_strict_mode(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare a JSON schema for OpenAI strict mode.

        OpenAI strict mode requires:
        - additionalProperties: false on all objects
        - All properties listed in required
        - No sibling keywords alongside $ref
        - $ref references must be resolved
        """
        import copy
        schema = copy.deepcopy(schema)
        defs = schema.get("$defs", {})

        # Recursively resolve $ref and fix all objects
        schema = self._resolve_and_fix(schema, defs)

        # Remove $defs since we've inlined everything
        schema.pop("$defs", None)
        return schema

    def _resolve_and_fix(self, schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolve $ref references and fix for strict mode."""
        import copy

        if not isinstance(schema, dict):
            return schema

        # Resolve $ref by inlining the definition
        if "$ref" in schema:
            ref_path = schema["$ref"]  # e.g. "#/$defs/CheckResult"
            def_name = ref_path.split("/")[-1]
            if def_name in defs:
                resolved = copy.deepcopy(defs[def_name])
                resolved = self._resolve_and_fix(resolved, defs)
                return resolved
            return schema

        # Fix object types
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
                for key, prop_schema in schema["properties"].items():
                    schema["properties"][key] = self._resolve_and_fix(prop_schema, defs)

        # Fix array items
        if schema.get("type") == "array" and "items" in schema:
            schema["items"] = self._resolve_and_fix(schema["items"], defs)

        # Fix anyOf/oneOf variants
        for key in ("anyOf", "oneOf"):
            if key in schema:
                schema[key] = [self._resolve_and_fix(v, defs) for v in schema[key]]

        # Fix allOf (merge into single schema)
        if "allOf" in schema:
            merged = {}
            for sub in schema["allOf"]:
                resolved = self._resolve_and_fix(sub, defs)
                merged.update(resolved)
            schema.pop("allOf")
            schema.update(merged)

        # Remove 'default' - not allowed in strict mode
        schema.pop("default", None)

        # Remove examples
        schema.pop("examples", None)

        return schema

    def _normalize_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize LLM response to match expected schema.

        Fixes common LLM non-compliance issues like using values
        that are valid for one field but not another.
        """
        # Valid check result values
        valid_check_results = {"PASS", "FAIL", "INCONCLUSIVE", "NOT_CHECKED"}

        for check in result.get("checks", []):
            if isinstance(check, dict) and check.get("result") not in valid_check_results:
                original = check["result"]
                check["result"] = "INCONCLUSIVE"
                logger.debug(
                    f"Normalized check result '{original}' -> 'INCONCLUSIVE' "
                    f"for check {check.get('check_name', '?')}"
                )

        return result

    def _call_with_retry(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        on_token_update: Optional[Callable[[int, int], None]] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """Call OpenAI API with retry logic and structured output validation.

        Args:
            messages: List of message dicts.
            model: Model to use.
            temperature: Temperature setting.
            max_tokens: Max tokens for response.
            on_token_update: Optional callback for token updates.
            retries: Number of retry attempts.

        Returns:
            Validated JSON response as dict.

        Raises:
            ValueError: If all retries fail or validation fails.
        """
        last_error = None
        total_input_tokens = 0
        total_output_tokens = 0
        use_strict_schema = True

        for attempt in range(retries):
            try:
                logger.debug(f"Assessment API call attempt {attempt + 1}/{retries}")

                # Build response format (try strict schema first, fall back to json_object)
                if use_strict_schema:
                    response_format = self._build_response_format()
                else:
                    response_format = {"type": "json_object"}

                response = self._audited_client.chat_completions_create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )

                # Track token usage
                if response.usage:
                    total_input_tokens = response.usage.prompt_tokens
                    total_output_tokens = response.usage.completion_tokens

                    if on_token_update:
                        on_token_update(total_input_tokens, total_output_tokens)

                    logger.info(
                        f"Assessment tokens: {total_input_tokens:,} input + "
                        f"{total_output_tokens:,} output = "
                        f"{response.usage.total_tokens:,} total"
                    )

                # Extract and parse response
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from API")

                result = json.loads(content)

                # Normalize LLM output before validation
                result = self._normalize_response(result)

                # Validate with Pydantic
                validated = AssessmentResponse.model_validate(result)

                # Check completeness
                warnings = validate_assessment_completeness(validated)
                if warnings:
                    for warning in warnings:
                        logger.warning(f"Assessment validation warning: {warning}")

                # Ensure minimum checks
                if len(validated.checks) < MIN_EXPECTED_CHECKS:
                    raise ValueError(
                        f"Incomplete assessment: only {len(validated.checks)} checks, "
                        f"expected at least {MIN_EXPECTED_CHECKS}"
                    )

                logger.info(
                    f"Assessment validated successfully with {len(validated.checks)} checks"
                )
                return validated.model_dump()

            except json.JSONDecodeError as e:
                last_error = ValueError(f"Failed to parse JSON response: {e}")
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")

            except ValueError as e:
                # Check if it's a schema mode not supported error
                error_msg = str(e).lower()
                if "json_schema" in error_msg or "response_format" in error_msg:
                    logger.warning(
                        f"json_schema mode not supported, falling back to json_object: {e}"
                    )
                    use_strict_schema = False
                    # Don't count this as an attempt, retry immediately
                    continue

                last_error = e
                logger.warning(f"Validation error on attempt {attempt + 1}: {e}")

            except Exception as e:
                # Check if it's a schema mode not supported error
                error_msg = str(e).lower()
                if "json_schema" in error_msg or "response_format" in error_msg:
                    logger.warning(
                        f"json_schema mode not supported, falling back to json_object: {e}"
                    )
                    use_strict_schema = False
                    # Don't count this as an attempt, retry immediately
                    continue

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
