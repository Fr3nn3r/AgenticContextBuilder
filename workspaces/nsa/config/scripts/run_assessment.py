#!/usr/bin/env python3
"""
Claims Assessment Reasoning Agent - Test Runner

Invokes the claims_assessment prompt on claim_facts.json files and saves results.

Usage:
    python workspaces/nsa/config/scripts/run_assessment.py --claim 65258
    python workspaces/nsa/config/scripts/run_assessment.py --all
    python workspaces/nsa/config/scripts/run_assessment.py --claim 65258 --dry-run
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports (5 levels up from workspaces/nsa/config/scripts/)
REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from context_builder.services.assessment_audit import (
    create_assessment_client,
    log_assessment_decision,
)
from context_builder.utils.prompt_loader import load_prompt
from context_builder.storage.workspace_paths import get_active_workspace_path


# JSON Schema for assessment output validation
ASSESSMENT_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "claim_id", "decision", "confidence_score", "checks", "payout"],
    "properties": {
        "schema_version": {"type": "string"},
        "claim_id": {"type": "string"},
        "decision": {"enum": ["APPROVE", "REJECT", "REFER_TO_HUMAN"]},
        "decision_rationale": {"type": "string"},
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["check_number", "check_name", "result"],
                "properties": {
                    "check_number": {"type": ["integer", "string"]},
                    "check_name": {"type": "string"},
                    "result": {"enum": ["PASS", "FAIL", "INCONCLUSIVE"]},
                    "details": {"type": "string"},
                }
            }
        },
        "payout": {
            "type": "object",
            "required": ["final_payout", "currency"],
            "properties": {
                "total_claimed": {"type": "number", "minimum": 0},
                "non_covered_deductions": {"type": "number", "minimum": 0},
                "covered_subtotal": {"type": "number", "minimum": 0},
                "coverage_percent": {"type": ["number", "integer"]},
                "after_coverage": {"type": "number", "minimum": 0},
                "deductible": {"type": "number", "minimum": 0},
                "final_payout": {"type": "number", "minimum": 0},
                "currency": {"type": "string"},
            }
        },
        "assumptions": {"type": "array"},
        "fraud_indicators": {"type": "array"},
        "recommendations": {"type": "array"},
    }
}


def load_assumptions() -> dict:
    """Load assumptions.json from workspace config."""
    workspace_path = get_active_workspace_path()
    assumptions_path = workspace_path / "config" / "assumptions.json"

    if not assumptions_path.exists():
        logging.getLogger(__name__).warning(
            f"No assumptions.json found at {assumptions_path}"
        )
        return {}

    with open(assumptions_path, "r", encoding="utf-8") as f:
        return json.load(f)


def lookup_part_coverage(item: dict, assumptions: dict) -> dict:
    """
    Lookup part coverage from assumptions.

    Returns a dict with:
    - lookup_method: "part_number", "keyword", "excluded_keyword", or "not_found"
    - system: the system this part belongs to (if found)
    - component: specific component name (if found)
    - covered: True, False, or None (if not found)
    - action: what to do if not found (e.g., "REFER_TO_HUMAN")
    """
    mapping = assumptions.get("part_system_mapping", {})
    desc = item.get("description", "").upper()  # Use upper for excluded keywords

    # Check excluded items first (these are never covered)
    excluded = assumptions.get("excluded_items", {})
    excluded_keywords = excluded.get("keywords", [])
    for keyword in excluded_keywords:
        if keyword.upper() in desc:
            return {
                "lookup_method": "excluded_keyword",
                "matched_keyword": keyword,
                "covered": False,
                "reason": "excluded_item",
            }

    # Try part number
    part_num = item.get("item_code", "")
    by_part_number = mapping.get("by_part_number", {})
    if part_num in by_part_number:
        result = by_part_number[part_num].copy()
        result["lookup_method"] = "part_number"
        return result

    # Try keyword matching (case-insensitive)
    desc_lower = item.get("description", "").lower()
    by_keyword = mapping.get("by_keyword", {})
    for keyword, info in by_keyword.items():
        if keyword.lower() in desc_lower:
            result = info.copy()
            result["lookup_method"] = "keyword"
            result["matched_keyword"] = keyword
            return result

    # Not found - return default action
    return {
        "lookup_method": "not_found",
        "covered": None,
        "action": assumptions.get("business_rules", {})
        .get("unknown_part_coverage", {})
        .get("action", "REFER_TO_HUMAN"),
        "reason": assumptions.get("business_rules", {})
        .get("unknown_part_coverage", {})
        .get("reason", "Part not found in coverage lookup table"),
    }


def lookup_authorization(shop_name: str, assumptions: dict) -> dict:
    """
    Lookup shop authorization status from assumptions.

    Returns a dict with:
    - lookup_method: "exact_name", "pattern", or "not_found"
    - authorized: True, False, or None
    - action: what to do if not found
    """
    partners = assumptions.get("authorized_partners", {})

    if not shop_name:
        return {
            "lookup_method": "not_found",
            "authorized": None,
            "action": partners.get("_default_if_unknown", "REFER_TO_HUMAN"),
            "reason": "No shop name provided",
        }

    # Try exact name match first
    by_name = partners.get("by_name", {})
    for name, info in by_name.items():
        if name.lower() in shop_name.lower() or shop_name.lower() in name.lower():
            result = info.copy()
            result["lookup_method"] = "exact_name"
            result["matched_name"] = name
            return result

    # Try pattern matching
    by_pattern = partners.get("by_pattern", [])
    for pattern_info in by_pattern:
        pattern = pattern_info.get("pattern", "")
        try:
            if re.match(pattern, shop_name, re.IGNORECASE):
                result = pattern_info.copy()
                result["lookup_method"] = "pattern"
                return result
        except re.error:
            continue

    # Not found
    return {
        "lookup_method": "not_found",
        "authorized": None,
        "action": partners.get("_default_if_unknown", "REFER_TO_HUMAN"),
        "reason": "Shop not found in authorized partners list",
    }


def get_fact_value(claim_facts: dict, fact_name: str) -> str | None:
    """Extract a fact value from claim_facts by name."""
    facts = claim_facts.get("facts", [])
    for fact in facts:
        if fact.get("name") == fact_name:
            return fact.get("value")
    return None


def enrich_claim_facts(claim_facts: dict, assumptions: dict) -> dict:
    """
    Pre-process claim facts using assumptions lookup.
    Adds deterministic coverage flags before sending to LLM.

    Adds:
    - _coverage_lookup to each line item in structured_data
    - _shop_authorization_lookup at top level
    - _assumptions_version for traceability
    - _enrichment_summary with lookup statistics
    """
    log = logging.getLogger(__name__)

    if not assumptions:
        return claim_facts

    enriched = claim_facts.copy()

    # Add assumptions version for traceability
    enriched["_assumptions_version"] = assumptions.get("schema_version", "unknown")
    enriched["_assumptions_updated_at"] = assumptions.get("updated_at", "unknown")

    # Track lookup statistics
    stats = {
        "covered": 0,
        "not_covered": 0,
        "unknown": 0,
        "covered_amount": 0.0,
        "not_covered_amount": 0.0,
        "unknown_amount": 0.0,
        "unknown_items": [],  # Track for logging
    }

    # Enrich line items with coverage info
    if "structured_data" in enriched and "line_items" in enriched["structured_data"]:
        enriched["structured_data"] = enriched["structured_data"].copy()
        enriched["structured_data"]["line_items"] = []

        for item in claim_facts["structured_data"]["line_items"]:
            enriched_item = item.copy()
            coverage = lookup_part_coverage(item, assumptions)
            enriched_item["_coverage_lookup"] = coverage
            enriched["structured_data"]["line_items"].append(enriched_item)

            # Track statistics
            price = item.get("total_price", 0) or 0
            if coverage.get("covered") is True:
                stats["covered"] += 1
                stats["covered_amount"] += price
            elif coverage.get("covered") is False:
                stats["not_covered"] += 1
                stats["not_covered_amount"] += price
            else:
                stats["unknown"] += 1
                stats["unknown_amount"] += price
                # Track high-value unknown items for logging
                if price > 100:
                    stats["unknown_items"].append({
                        "description": item.get("description", "")[:40],
                        "price": price,
                    })

    # Log coverage lookup summary
    total_items = stats["covered"] + stats["not_covered"] + stats["unknown"]
    if total_items > 0:
        log.info(
            f"Coverage lookup: {stats['covered']} covered (CHF {stats['covered_amount']:.0f}), "
            f"{stats['not_covered']} not covered (CHF {stats['not_covered_amount']:.0f}), "
            f"{stats['unknown']} unknown (CHF {stats['unknown_amount']:.0f})"
        )

        # Warn about high-value unknown items
        if stats["unknown_items"]:
            log.warning(
                f"Unknown coverage for {len(stats['unknown_items'])} high-value items (>CHF 100): "
                f"{', '.join(i['description'] for i in stats['unknown_items'][:5])}"
                + ("..." if len(stats["unknown_items"]) > 5 else "")
            )

    # Enrich repair shop authorization
    shop_name = get_fact_value(enriched, "garage_name")
    if shop_name:
        auth = lookup_authorization(shop_name, assumptions)
        enriched["_shop_authorization_lookup"] = auth

        # Log shop authorization result
        if auth.get("authorized") is True:
            log.info(f"Shop authorization: AUTHORIZED ({auth.get('lookup_method')}: {shop_name})")
        elif auth.get("authorized") is False:
            log.warning(f"Shop authorization: NOT AUTHORIZED ({shop_name})")
        else:
            log.warning(
                f"Shop authorization: UNKNOWN - {auth.get('action', 'REFER_TO_HUMAN')} "
                f"({shop_name})"
            )

    # Add enrichment summary to output
    enriched["_enrichment_summary"] = {
        "total_line_items": total_items,
        "covered_count": stats["covered"],
        "covered_amount": round(stats["covered_amount"], 2),
        "not_covered_count": stats["not_covered"],
        "not_covered_amount": round(stats["not_covered_amount"], 2),
        "unknown_count": stats["unknown"],
        "unknown_amount": round(stats["unknown_amount"], 2),
    }

    # Compress line items to reduce token count (filter items < 50 CHF)
    if "structured_data" in enriched and "line_items" in enriched["structured_data"]:
        compressed = compress_line_items(enriched)
        enriched["_line_items_summary"] = compressed["_line_items_summary"]
        enriched["_primary_repairs"] = compressed["_primary_repairs"]
        enriched["structured_data"]["line_items"] = compressed["line_items"]

        log.info(
            f"Line items compressed: {compressed['_line_items_summary']['total_items']} → "
            f"{compressed['_line_items_summary']['filtered_items']} items, "
            f"{len(compressed['_primary_repairs'])} primary repairs identified"
        )

    # Compute check inputs summary (for LLM "fast path")
    check_inputs = compute_check_inputs(enriched, assumptions)

    # Build output with _check_inputs FIRST for LLM visibility
    # This ensures critical check inputs are at the TOP of the JSON,
    # reducing "lost in the middle" problems for large claims
    ordered = {
        "_check_inputs": check_inputs,
        "_shop_authorization_lookup": enriched.pop("_shop_authorization_lookup", {}),
        "_enrichment_summary": enriched.pop("_enrichment_summary", {}),
        "_line_items_summary": enriched.pop("_line_items_summary", {}),
        "_primary_repairs": enriched.pop("_primary_repairs", []),
    }
    ordered.update(enriched)

    return ordered


def compute_check_inputs(claim_facts: dict, assumptions: dict) -> dict:
    """
    Pre-compute all check inputs for fast LLM processing.

    This creates a summary section at the TOP of the enriched facts with
    all the key values needed for each check, reducing the "lost in the middle"
    problem for large claims.
    """
    facts = claim_facts.get("facts", [])
    structured = claim_facts.get("structured_data", {})

    def get_fact(name: str):
        for f in facts:
            if f.get("name") == name:
                return f.get("value")
        return None

    # Check 1: Policy validity inputs
    check_1 = {
        "policy_start": get_fact("start_date"),
        "policy_end": get_fact("end_date"),
        "claim_date": get_fact("document_date"),
        "km_limited_to": get_fact("km_limited_to"),
        "current_odometer": get_fact("odometer_km") or get_fact("vehicle_current_km"),
    }

    # Check 4a: Shop authorization (copy from enrichment)
    check_4a = claim_facts.get("_shop_authorization_lookup", {})

    # Check 4b: Service compliance
    service_entries = structured.get("service_entries", [])
    last_service = None
    if service_entries:
        # Get last service date
        for entry in reversed(service_entries):
            if entry.get("service_date"):
                last_service = entry.get("service_date")
                break

    check_4b = {
        "last_service_date": last_service,
        "service_count": len(service_entries),
        "claim_date": get_fact("document_date"),
    }

    # Check 5: Coverage summary (from enrichment)
    summary = claim_facts.get("_enrichment_summary", {})
    check_5 = {
        "total_items": summary.get("total_line_items", 0),
        "covered_count": summary.get("covered_count", 0),
        "covered_total": summary.get("covered_amount", 0),
        "not_covered_count": summary.get("not_covered_count", 0),
        "not_covered_total": summary.get("not_covered_amount", 0),
        "unknown_count": summary.get("unknown_count", 0),
        "unknown_total": summary.get("unknown_amount", 0),
    }

    return {
        "check_1_policy_validity": check_1,
        "check_4a_shop_auth": check_4a,
        "check_4b_service": check_4b,
        "check_5_coverage": check_5,
    }


def identify_primary_repairs(line_items: list, threshold: float = 500.0) -> list:
    """
    Identify primary repair components (high-value covered parts).

    These are the main components being repaired, not supporting items
    like labor, fees, gaskets, or bolts.
    """
    primary = []
    for item in line_items:
        coverage = item.get("_coverage_lookup", {})
        price = item.get("total_price", 0) or 0
        item_type = item.get("item_type", "")

        # Primary = high value + not labor/fee + covered or unknown
        if price >= threshold and item_type not in ("labor", "fee"):
            if coverage.get("covered") in (True, None):
                primary.append({
                    "description": item.get("description"),
                    "item_code": item.get("item_code"),
                    "total_price": price,
                    "system": coverage.get("system"),
                    "covered": coverage.get("covered"),
                })
    return primary


def compress_line_items(
    claim_facts: dict,
    small_item_threshold: float = 50.0
) -> dict:
    """
    Create compressed line items representation.

    Filters out small items (<50 CHF) to reduce token count while
    preserving important repair details.
    """
    structured = claim_facts.get("structured_data", {})
    line_items = structured.get("line_items", [])

    # Summary by type
    by_type = {"parts": 0.0, "labor": 0.0, "fee": 0.0, "other": 0.0}
    by_type_count = {"parts": 0, "labor": 0, "fee": 0, "other": 0}

    for item in line_items:
        item_type = item.get("item_type", "other") or "other"
        price = item.get("total_price", 0) or 0
        if item_type in by_type:
            by_type[item_type] += price
            by_type_count[item_type] += 1
        else:
            by_type["other"] += price
            by_type_count["other"] += 1

    # Primary repairs only
    primary = identify_primary_repairs(line_items)

    # Filtered line items (exclude small items)
    filtered = [
        item for item in line_items
        if (item.get("total_price", 0) or 0) >= small_item_threshold
    ]

    return {
        "_line_items_summary": {
            "total_items": len(line_items),
            "filtered_items": len(filtered),
            "by_type_amount": {k: round(v, 2) for k, v in by_type.items()},
            "by_type_count": by_type_count,
        },
        "_primary_repairs": primary,
        "line_items": filtered,  # Replace full list with filtered
    }


def compute_input_hash(data: dict) -> str:
    """Compute SHA-256 hash of input data for audit trail."""
    json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


def validate_assessment(assessment: dict) -> tuple[bool, list[str]]:
    """
    Validate assessment against schema and business rules.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    required = ["schema_version", "claim_id", "decision", "confidence_score", "payout"]
    for field in required:
        if field not in assessment:
            errors.append(f"Missing required field: {field}")

    # Validate decision enum
    decision = assessment.get("decision")
    if decision and decision not in ("APPROVE", "REJECT", "REFER_TO_HUMAN"):
        errors.append(f"Invalid decision value: {decision}")

    # Validate confidence score range
    confidence = assessment.get("confidence_score")
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            errors.append(f"Confidence score must be between 0 and 1: {confidence}")

    # Validate payout structure
    payout = assessment.get("payout", {})
    if "final_payout" not in payout:
        errors.append("Missing payout.final_payout")
    if "currency" not in payout:
        errors.append("Missing payout.currency")

    # Note: Business rule for REJECT/REFER_TO_HUMAN payout=0 is handled by
    # enforce_business_rules() rather than failing validation. This allows
    # the LLM to calculate payout even for referrals, then we auto-correct.

    return len(errors) == 0, errors


def enforce_business_rules(assessment: dict) -> dict:
    """
    Enforce business rules on the assessment output.

    Rules:
    - REJECT/REFER_TO_HUMAN must have final_payout = 0
    """
    decision = assessment.get("decision")

    if decision in ("REJECT", "REFER_TO_HUMAN"):
        if "payout" in assessment:
            original_payout = assessment["payout"].get("final_payout", 0)
            if original_payout > 0:
                assessment["payout"]["final_payout"] = 0
                assessment["payout"]["_original_payout_before_enforcement"] = original_payout
                assessment["payout"]["_enforcement_note"] = (
                    f"Payout set to 0 because decision is {decision}"
                )

    return assessment


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test claims with expected outcomes
TEST_CLAIMS = {
    "65258": "cylinder head - should approve",
    "65196": "hydraulic valve - should approve",
    "65157": "transmission - should reject (fraud)",
    "65128": "trunk lock - should reject (not covered)",
}


def load_claim_facts(claim_id: str) -> dict:
    """Load claim_facts.json for a given claim."""
    workspace_path = get_active_workspace_path()
    facts_path = workspace_path / "claims" / claim_id / "context" / "claim_facts.json"

    if not facts_path.exists():
        raise FileNotFoundError(f"claim_facts.json not found at: {facts_path}")

    with open(facts_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fix_common_json_errors(json_str: str) -> str:
    """Fix common JSON errors from LLM output."""
    # Fix unquoted values like "check_number": 1b -> "check_number": "1b"
    # Match patterns like : followed by alphanumeric with letters (not pure numbers)
    json_str = re.sub(
        r':\s*(\d+[a-zA-Z][a-zA-Z0-9]*)\s*([,\}\]])',
        r': "\1"\2',
        json_str
    )
    # Also fix patterns like 1b, at start of arrays
    json_str = re.sub(
        r'\[\s*(\d+[a-zA-Z][a-zA-Z0-9]*)\s*,',
        r'["\1",',
        json_str
    )
    return json_str


def extract_json_from_response(response_text: str) -> dict | None:
    """Extract JSON object from markdown response."""
    # Look for JSON code block
    json_match = re.search(r"```json\s*\n(.*?)\n```", response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Initial JSON parse failed: {e}, attempting fixes...")
            # Try to fix common errors
            fixed_json = fix_common_json_errors(json_str)
            try:
                return json.loads(fixed_json)
            except json.JSONDecodeError as e2:
                logger.warning(f"Failed to parse JSON even after fixes: {e2}")
                return None
    return None


def extract_markdown_report(response_text: str) -> str:
    """Extract markdown report (everything before the JSON block)."""
    # Find where the JSON block starts
    json_start = response_text.find("```json")
    if json_start > 0:
        return response_text[:json_start].strip()
    return response_text.strip()


def run_assessment(claim_id: str, dry_run: bool = False) -> dict:
    """
    Run assessment on a single claim.

    Args:
        claim_id: The claim ID to assess
        dry_run: If True, only show what would be done without calling API

    Returns:
        Dictionary with assessment results
    """
    logger.info(f"Running assessment for claim {claim_id}")

    # Load claim facts
    claim_facts = load_claim_facts(claim_id)

    # Load assumptions and enrich claim facts with lookup results
    assumptions = load_assumptions()
    if assumptions:
        logger.info(f"Loaded assumptions v{assumptions.get('schema_version', '?')}")
        claim_facts = enrich_claim_facts(claim_facts, assumptions)
        logger.info("Enriched claim facts with coverage and authorization lookups")

    # Compute input hash for audit trail (before any LLM processing)
    input_hash = compute_input_hash(claim_facts)
    logger.info(f"Input hash: {input_hash}")

    # Save enriched facts to separate file for audit trail
    workspace_path = get_active_workspace_path()
    output_dir = workspace_path / "claims" / claim_id / "context"
    output_dir.mkdir(parents=True, exist_ok=True)

    enriched_path = output_dir / "claim_facts_enriched.json"
    with open(enriched_path, "w", encoding="utf-8") as f:
        json.dump(claim_facts, f, indent=2)
    logger.info(f"Saved enriched facts to: {enriched_path}")

    claim_facts_json = json.dumps(claim_facts, indent=2)

    # Load and render prompt
    prompt_data = load_prompt("claims_assessment", claim_facts_json=claim_facts_json)
    config = prompt_data["config"]
    messages = prompt_data["messages"]

    logger.info(f"Loaded prompt: {config.get('name', 'unnamed')}")
    logger.info(f"Model: {config.get('model', 'gpt-4o')}, Temperature: {config.get('temperature', 0.2)}")

    if dry_run:
        logger.info("[DRY RUN] Would call OpenAI API with:")
        logger.info(f"  - Model: {config.get('model', 'gpt-4o')}")
        logger.info(f"  - Messages: {len(messages)} messages")
        logger.info(f"  - Max tokens: {config.get('max_tokens', 8192)}")
        return {"status": "dry_run", "claim_id": claim_id}

    # Call OpenAI API with audited client for token tracking
    audited_client = create_assessment_client(claim_id=claim_id)

    logger.info("Calling OpenAI API (audited)...")
    response = audited_client.chat_completions_create(
        model=config.get("model", "gpt-4o"),
        messages=messages,
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 8192),
    )
    call_id = audited_client.get_call_id()

    response_text = response.choices[0].message.content

    # Extract markdown report and JSON
    markdown_report = extract_markdown_report(response_text)
    assessment_json = extract_json_from_response(response_text)

    if assessment_json is None:
        logger.warning("Could not extract structured JSON from response")
        assessment_json = {
            "schema_version": "claims_assessment_v1",
            "claim_id": claim_id,
            "error": "Failed to extract structured JSON from LLM response",
            "raw_response": response_text
        }

    # Validate assessment output
    is_valid, validation_errors = validate_assessment(assessment_json)
    if not is_valid:
        logger.error(f"Assessment validation failed: {validation_errors}")
        invalid_result = {
            "status": "invalid",
            "claim_id": claim_id,
            "errors": validation_errors,
            "input_hash": input_hash,
            "processed_at": datetime.now().isoformat(),
        }
        # Save invalid assessment
        json_path = output_dir / "assessment.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(invalid_result, f, indent=2)
        logger.info(f"Saved invalid assessment to: {json_path}")
        return {
            "status": "invalid",
            "claim_id": claim_id,
            "errors": validation_errors,
            "json_path": str(json_path),
        }

    # Enforce business rules (e.g., payout=0 for REJECT)
    assessment_json = enforce_business_rules(assessment_json)

    # Add metadata
    assessment_json["_meta"] = {
        "model": config.get("model", "gpt-4o"),
        "temperature": config.get("temperature", 0.2),
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "processed_at": datetime.now().isoformat(),
        "input_hash": input_hash,
        "assumptions_version": assumptions.get("schema_version") if assumptions else None,
        "assumptions_updated_at": assumptions.get("updated_at") if assumptions else None,
    }

    # Save markdown report
    report_path = output_dir / "assessment_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    logger.info(f"Saved markdown report to: {report_path}")

    # Save JSON assessment
    json_path = output_dir / "assessment.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(assessment_json, f, indent=2)
    logger.info(f"Saved JSON assessment to: {json_path}")

    # Log summary
    decision = assessment_json.get("decision", "UNKNOWN")
    confidence = assessment_json.get("confidence_score", 0)
    payout_data = assessment_json.get("payout", {})
    payout_amount = payout_data.get("final_payout", "N/A")

    # Log assessment decision to compliance ledger
    try:
        log_assessment_decision(
            claim_id=claim_id,
            decision=decision,
            confidence_score=confidence if isinstance(confidence, float) else 0.0,
            payout=payout_data,
            checks=assessment_json.get("checks", []),
            llm_call_id=call_id,
            rationale_summary=assessment_json.get("decision_rationale"),
            metadata={
                "model": config.get("model"),
                "input_hash": input_hash,
                "assumptions_version": assumptions.get("schema_version") if assumptions else None,
            },
        )
        logger.info("Assessment decision logged to compliance ledger")
    except Exception as e:
        logger.warning(f"Failed to log assessment decision to compliance ledger: {e}")

    logger.info(f"Assessment complete: Decision={decision}, Confidence={confidence}, Payout={payout_amount}")

    return {
        "status": "success",
        "claim_id": claim_id,
        "decision": decision,
        "confidence_score": confidence,
        "final_payout": payout_amount,
        "report_path": str(report_path),
        "json_path": str(json_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run Claims Assessment Reasoning Agent on claim_facts.json"
    )
    parser.add_argument(
        "--claim",
        type=str,
        help="Specific claim ID to assess (e.g., 65258)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run assessment on all test claims"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without calling API"
    )

    args = parser.parse_args()

    if not args.claim and not args.all:
        parser.error("Must specify either --claim or --all")

    claims_to_process = []

    if args.all:
        claims_to_process = list(TEST_CLAIMS.keys())
        logger.info(f"Processing all {len(claims_to_process)} test claims")
    else:
        claims_to_process = [args.claim]

    results = []
    for claim_id in claims_to_process:
        expected = TEST_CLAIMS.get(claim_id, "unknown")
        logger.info(f"\n{'='*60}")
        logger.info(f"Claim {claim_id}: {expected}")
        logger.info(f"{'='*60}")

        try:
            result = run_assessment(claim_id, dry_run=args.dry_run)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to assess claim {claim_id}: {e}")
            results.append({
                "status": "error",
                "claim_id": claim_id,
                "error": str(e)
            })

    # Print summary
    print("\n" + "="*60)
    print("ASSESSMENT SUMMARY")
    print("="*60)

    for result in results:
        claim_id = result["claim_id"]
        expected = TEST_CLAIMS.get(claim_id, "unknown")
        status = result.get("status", "unknown")

        if status == "success":
            decision = result.get("decision", "?")
            confidence = result.get("confidence_score", 0)
            payout = result.get("final_payout", "N/A")
            print(f"  {claim_id}: {decision} (confidence: {confidence}, payout: {payout})")
            print(f"           Expected: {expected}")
        elif status == "dry_run":
            print(f"  {claim_id}: [DRY RUN] Expected: {expected}")
        else:
            print(f"  {claim_id}: ERROR - {result.get('error', 'unknown')}")

    print("="*60)


if __name__ == "__main__":
    main()
