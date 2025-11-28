"""Chunk Refinement Orchestrator - Coordinates Extract → Lint → Refine loop.

This orchestrator implements the refinement flow at the chunk level:
1. Extract rules from chunk
2. Lint extracted rules
3. If violations found, refine failed rules
4. Merge refined rules back in-place
5. Re-lint to verify fixes

Single Responsibility: Coordinate the refinement workflow.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Callable, Optional

logger = logging.getLogger(__name__)


class ChunkRefinementOrchestrator:
    """
    Orchestrates the Extract → Lint → Refine loop for a single chunk.

    Responsibilities:
    - Call extractor to get initial rules
    - Call linter to validate rules
    - Call refiner to fix failed rules (if needed)
    - Merge refined rules back into extraction result
    - Track refinement metadata

    Follows Single Responsibility Principle: Only coordinates workflow.
    """

    def __init__(self):
        """Initialize orchestrator."""
        pass

    def _extract_failed_rules(
        self,
        extraction_result: Dict[str, Any],
        violations: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Extract failed rules from extraction result based on violations.

        Args:
            extraction_result: PolicyAnalysis dict from extractor
            violations: List of violation dicts from linter

        Returns:
            Tuple of (failed_rules_list, rule_id_to_index_map)
        """
        # Get all rule IDs that have violations
        failed_rule_ids = set(v.get("rule_id") for v in violations)

        # Extract failed rules and build index map
        rules = extraction_result.get("rules", [])
        failed_rules = []
        rule_id_to_index = {}

        for i, rule in enumerate(rules):
            rule_id = rule.get("id", "unknown")
            if rule_id in failed_rule_ids:
                failed_rules.append(rule)
                rule_id_to_index[rule_id] = i

        logger.debug(f"Extracted {len(failed_rules)} failed rules from {len(rules)} total rules")

        return failed_rules, rule_id_to_index

    def _merge_refined_rules(
        self,
        extraction_result: Dict[str, Any],
        refined_result: Dict[str, Any],
        rule_id_to_index: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Merge refined rules back into original extraction result (in-place replacement).

        Args:
            extraction_result: Original PolicyAnalysis dict
            refined_result: PolicyAnalysis dict with ONLY fixed rules from refiner
            rule_id_to_index: Map of rule_id → original index

        Returns:
            Updated extraction_result with refined rules merged in
        """
        refined_rules = refined_result.get("rules", [])

        logger.info(f"Merging {len(refined_rules)} refined rules back into extraction result")

        # Replace each refined rule at its original position
        for refined_rule in refined_rules:
            rule_id = refined_rule.get("id", "unknown")

            if rule_id in rule_id_to_index:
                original_index = rule_id_to_index[rule_id]
                extraction_result["rules"][original_index] = refined_rule
                logger.debug(f"Replaced rule {rule_id} at index {original_index}")
            else:
                logger.warning(
                    f"Refined rule {rule_id} not found in original extraction. "
                    f"This may indicate a refiner error (changed rule ID)."
                )

        # Track which rules were refined (metadata)
        if "_refinement_metadata" not in extraction_result:
            extraction_result["_refinement_metadata"] = {}

        extraction_result["_refinement_metadata"]["refined_rule_ids"] = [
            r.get("id") for r in refined_rules
        ]
        extraction_result["_refinement_metadata"]["refinement_count"] = len(refined_rules)

        return extraction_result

    def process_chunk_with_refinement(
        self,
        chunk_text: str,
        chunk_symbol_md: str,
        udm_context: str,
        chunk_index: int,
        total_chunks: int,
        chunk_file_path: Optional[Path],
        extractor: Any,  # OpenAILogicExtraction instance
        refiner: Any,  # PolicyLogicRefiner instance
        linter_func: Callable,  # validate_rules function
        save_report_func: Callable,  # save_validation_report function
        max_refinement_attempts: int = 1
    ) -> Tuple[Dict[str, Any], Any]:
        """
        Process chunk with Extract → Lint → Refine loop.

        Args:
            chunk_text: Text content of chunk
            chunk_symbol_md: Filtered symbol table markdown for this chunk
            udm_context: Static UDM schema markdown
            chunk_index: Index of this chunk (1-based)
            total_chunks: Total number of chunks
            chunk_file_path: Path to chunk text file (for saving reports)
            extractor: OpenAILogicExtraction instance
            refiner: PolicyLogicRefiner instance
            linter_func: Validation function (validate_rules)
            save_report_func: Report save function (save_validation_report)
            max_refinement_attempts: Maximum refinement attempts (default: 1)

        Returns:
            Tuple of (refined_chunk_result, final_validation_report)

        Raises:
            Exception: If extraction fails (propagated from extractor)
        """
        logger.info(f"[Chunk {chunk_index}/{total_chunks}] Starting Extract → Lint → Refine flow")

        # STEP 1: Extract rules
        logger.info(f"[Chunk {chunk_index}/{total_chunks}] Step 1: Extracting rules...")
        extraction_result = extractor.process_chunk(
            chunk_text=chunk_text,
            chunk_symbol_md=chunk_symbol_md,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_file_path=chunk_file_path
        )

        # STEP 2: Lint extracted rules
        logger.info(f"[Chunk {chunk_index}/{total_chunks}] Step 2: Linting extracted rules...")
        validation_report = linter_func(extraction_result)

        violations_count = validation_report.summary["violations"]
        logger.info(
            f"[Chunk {chunk_index}/{total_chunks}] Linter found {violations_count} violations "
            f"({validation_report.summary['critical_violations']} critical)"
        )

        # STEP 3: Refine if violations exist
        refinement_attempt = 0
        while violations_count > 0 and refinement_attempt < max_refinement_attempts:
            refinement_attempt += 1
            logger.info(
                f"[Chunk {chunk_index}/{total_chunks}] Step 3: Refinement attempt "
                f"{refinement_attempt}/{max_refinement_attempts}"
            )

            try:
                # Extract failed rules
                failed_rules, rule_id_to_index = self._extract_failed_rules(
                    extraction_result,
                    validation_report.violations
                )

                if not failed_rules:
                    logger.warning(
                        f"[Chunk {chunk_index}/{total_chunks}] No failed rules found despite "
                        f"{violations_count} violations. This may indicate a linter/extraction mismatch."
                    )
                    break

                # Call refiner
                logger.info(f"[Chunk {chunk_index}/{total_chunks}] Calling refiner for {len(failed_rules)} rules...")
                refined_result = refiner.refine_rules(
                    failed_rules=failed_rules,
                    violations=validation_report.violations,
                    chunk_symbol_md=chunk_symbol_md,
                    udm_context=udm_context,
                    chunk_file_path=chunk_file_path,
                    chunk_index=chunk_index,
                    attempt=refinement_attempt
                )

                # Merge refined rules back
                extraction_result = self._merge_refined_rules(
                    extraction_result,
                    refined_result,
                    rule_id_to_index
                )

                # Re-lint to verify fixes
                logger.info(f"[Chunk {chunk_index}/{total_chunks}] Re-linting after refinement...")
                validation_report = linter_func(extraction_result)
                violations_count = validation_report.summary["violations"]

                logger.info(
                    f"[Chunk {chunk_index}/{total_chunks}] After refinement: {violations_count} violations remain "
                    f"({validation_report.summary['critical_violations']} critical)"
                )

            except Exception as e:
                logger.error(
                    f"[Chunk {chunk_index}/{total_chunks}] Refinement attempt {refinement_attempt} failed: {e}"
                )
                logger.info(
                    f"[Chunk {chunk_index}/{total_chunks}] Falling back to original (unrefined) rules"
                )
                # Keep extraction_result as-is (original rules)
                break

        # STEP 4: Save chunk audit report
        if chunk_file_path:
            chunk_report_filename = f"chunk_{chunk_index:03d}_audit_report.json"
            logger.info(
                f"[Chunk {chunk_index}/{total_chunks}] Saving audit report: {chunk_report_filename}"
            )
            save_report_func(
                validation_report,
                str(chunk_file_path),
                filename=chunk_report_filename
            )

        # STEP 5: Return refined result + final validation report
        logger.info(
            f"[Chunk {chunk_index}/{total_chunks}] Refinement flow complete. "
            f"Final violations: {violations_count}"
        )

        return extraction_result, validation_report
