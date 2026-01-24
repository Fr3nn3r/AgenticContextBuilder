#!/usr/bin/env python3
"""
Claims Assessment Reasoning Agent - Test Runner

Invokes the claims_assessment prompt on claim_facts.json files and saves results.

Usage:
    python scripts/run_assessment.py --claim 65258
    python scripts/run_assessment.py --all
    python scripts/run_assessment.py --claim 65258 --dry-run
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from openai import OpenAI

from context_builder.utils.prompt_loader import load_prompt
from context_builder.storage.workspace_paths import get_active_workspace_path

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

    # Call OpenAI API
    client = OpenAI()

    logger.info("Calling OpenAI API...")
    response = client.chat.completions.create(
        model=config.get("model", "gpt-4o"),
        messages=messages,
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 8192),
    )

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

    # Add metadata
    assessment_json["_meta"] = {
        "model": config.get("model", "gpt-4o"),
        "temperature": config.get("temperature", 0.2),
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "processed_at": datetime.now().isoformat(),
    }

    # Save outputs
    workspace_path = get_active_workspace_path()
    output_dir = workspace_path / "claims" / claim_id / "context"
    output_dir.mkdir(parents=True, exist_ok=True)

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
    payout = assessment_json.get("payout", {}).get("final_payout", "N/A")

    logger.info(f"Assessment complete: Decision={decision}, Confidence={confidence}, Payout={payout}")

    return {
        "status": "success",
        "claim_id": claim_id,
        "decision": decision,
        "confidence_score": confidence,
        "final_payout": payout,
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
