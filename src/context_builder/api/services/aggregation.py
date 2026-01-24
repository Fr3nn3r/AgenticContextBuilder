"""Aggregation service for combining extracted facts from multiple documents."""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from context_builder.schemas.claim_facts import (
    AggregatedFact,
    ClaimFacts,
    FactProvenance,
    SourceDocument,
)
from context_builder.storage.filesystem import FileStorage

logger = logging.getLogger(__name__)


class AggregationError(Exception):
    """Error during fact aggregation."""

    pass


class AggregationService:
    """Service for aggregating extracted facts from multiple documents into claim-level facts."""

    def __init__(self, storage: FileStorage):
        """Initialize aggregation service.

        Args:
            storage: FileStorage instance for accessing claims and extractions.
        """
        self.storage = storage

    def find_latest_complete_run(self, claim_id: str) -> Optional[str]:
        """Find the latest complete run for a claim.

        Args:
            claim_id: Claim identifier.

        Returns:
            Run ID of the latest complete run, or None if no complete runs exist.
        """
        claim_folder = self.storage._find_claim_folder(claim_id)
        if not claim_folder:
            return None

        runs_dir = claim_folder / "runs"
        if not runs_dir.exists():
            return None

        # Find all complete runs and sort by ended_at timestamp
        complete_runs: List[Tuple[str, str]] = []  # (run_id, ended_at)

        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            if not (run_dir.name.startswith("run_") or run_dir.name.startswith("BATCH-")):
                continue

            # Check for .complete marker
            if not (run_dir / ".complete").exists():
                continue

            # Get ended_at from summary or manifest
            ended_at = None
            summary_path = run_dir / "logs" / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                        ended_at = summary.get("completed_at")
                except (json.JSONDecodeError, IOError):
                    pass

            # Fallback to run_id as timestamp proxy (format: run_YYYYMMDD_HHMMSS_...)
            if not ended_at:
                ended_at = run_dir.name

            complete_runs.append((run_dir.name, ended_at))

        if not complete_runs:
            return None

        # Sort by ended_at descending and return latest
        complete_runs.sort(key=lambda x: x[1], reverse=True)
        return complete_runs[0][0]

    def load_extractions(
        self, claim_id: str, run_id: str
    ) -> List[Tuple[str, str, str, dict]]:
        """Load all extractions for a claim from a specific run.

        Args:
            claim_id: Claim identifier.
            run_id: Run identifier.

        Returns:
            List of tuples: (doc_id, doc_type, filename, extraction_data)
        """
        claim_folder = self.storage._find_claim_folder(claim_id)
        if not claim_folder:
            return []

        extraction_dir = claim_folder / "runs" / run_id / "extraction"
        if not extraction_dir.exists():
            return []

        results = []
        for ext_file in extraction_dir.glob("*.json"):
            doc_id = ext_file.stem
            try:
                with open(ext_file, "r", encoding="utf-8") as f:
                    extraction = json.load(f)

                # Get doc_type from extraction
                doc_info = extraction.get("doc", {})
                doc_type = doc_info.get("doc_type", "unknown")

                # Get filename from doc metadata
                doc_meta = self.storage.get_doc_metadata(doc_id, claim_id)
                filename = (
                    doc_meta.get("original_filename", f"{doc_id}.pdf")
                    if doc_meta
                    else f"{doc_id}.pdf"
                )

                results.append((doc_id, doc_type, filename, extraction))

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load extraction {ext_file}: {e}")
                continue

        return results

    def build_candidates(
        self, extractions: List[Tuple[str, str, str, dict]], run_id: str
    ) -> Dict[str, List[dict]]:
        """Build candidate list from all extractions.

        Groups candidates by field name. Only includes fields with status="present".

        Args:
            extractions: List of (doc_id, doc_type, filename, extraction_data) tuples.
            run_id: Run ID for provenance.

        Returns:
            Dict mapping field names to list of candidate values.
        """
        candidates: Dict[str, List[dict]] = defaultdict(list)

        for doc_id, doc_type, filename, extraction in extractions:
            fields = extraction.get("fields", [])

            for field in fields:
                # Only consider present fields
                if field.get("status") != "present":
                    continue

                name = field.get("name")
                if not name:
                    continue

                value = field.get("value")
                normalized_value = field.get("normalized_value")
                confidence = field.get("confidence", 0.0)

                # Get provenance details
                provenance_list = field.get("provenance", [])
                provenance = provenance_list[0] if provenance_list else {}

                candidate = {
                    "name": name,
                    "value": value,
                    "normalized_value": normalized_value,
                    "confidence": confidence,
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "filename": filename,
                    "run_id": run_id,
                    "page": provenance.get("page"),
                    "text_quote": provenance.get("text_quote"),
                    "char_start": provenance.get("char_start"),
                    "char_end": provenance.get("char_end"),
                }

                candidates[name].append(candidate)

        return candidates

    def select_primary(
        self, candidates: Dict[str, List[dict]]
    ) -> List[AggregatedFact]:
        """Select primary value for each field based on highest confidence.

        Args:
            candidates: Dict mapping field names to candidate values.

        Returns:
            List of AggregatedFact objects.
        """
        facts = []

        for field_name, field_candidates in candidates.items():
            if not field_candidates:
                continue

            # Sort by confidence descending and select highest
            sorted_candidates = sorted(
                field_candidates, key=lambda x: x["confidence"], reverse=True
            )
            primary = sorted_candidates[0]

            fact = AggregatedFact(
                name=field_name,
                value=primary["value"],
                normalized_value=primary.get("normalized_value"),
                confidence=primary["confidence"],
                selected_from=FactProvenance(
                    doc_id=primary["doc_id"],
                    doc_type=primary["doc_type"],
                    run_id=primary["run_id"],
                    page=primary.get("page"),
                    text_quote=primary.get("text_quote"),
                    char_start=primary.get("char_start"),
                    char_end=primary.get("char_end"),
                ),
            )
            facts.append(fact)

        return facts

    def aggregate_claim_facts(
        self, claim_id: str, run_id: Optional[str] = None
    ) -> ClaimFacts:
        """Aggregate facts from all documents in a claim.

        Args:
            claim_id: Claim identifier.
            run_id: Optional specific run ID. If not provided, uses latest complete run.

        Returns:
            ClaimFacts object with aggregated facts.

        Raises:
            AggregationError: If no complete runs exist or aggregation fails.
        """
        # Find run to use
        if run_id is None:
            run_id = self.find_latest_complete_run(claim_id)
            if not run_id:
                raise AggregationError(
                    f"No complete runs found for claim '{claim_id}'"
                )

        logger.info(f"Aggregating facts for claim {claim_id} from run {run_id}")

        # Load extractions
        extractions = self.load_extractions(claim_id, run_id)
        if not extractions:
            raise AggregationError(
                f"No extractions found for claim '{claim_id}' in run '{run_id}'"
            )

        logger.info(f"Loaded {len(extractions)} extractions")

        # Build candidates
        candidates = self.build_candidates(extractions, run_id)
        logger.info(f"Built candidates for {len(candidates)} fields")

        # Select primary values
        facts = self.select_primary(candidates)
        logger.info(f"Selected {len(facts)} aggregated facts")

        # Build source documents list
        sources = [
            SourceDocument(doc_id=doc_id, filename=filename, doc_type=doc_type)
            for doc_id, doc_type, filename, _ in extractions
        ]

        return ClaimFacts(
            claim_id=claim_id,
            generated_at=datetime.utcnow(),
            run_id=run_id,
            run_policy="latest_complete" if run_id else "specified",
            facts=facts,
            sources=sources,
        )

    def write_claim_facts(self, claim_id: str, facts: ClaimFacts) -> Path:
        """Write aggregated facts to claim context directory.

        Args:
            claim_id: Claim identifier.
            facts: ClaimFacts object to write.

        Returns:
            Path to written file.

        Raises:
            AggregationError: If claim folder not found or write fails.
        """
        claim_folder = self.storage._find_claim_folder(claim_id)
        if not claim_folder:
            raise AggregationError(f"Claim not found: {claim_id}")

        context_dir = claim_folder / "context"
        context_dir.mkdir(parents=True, exist_ok=True)

        output_path = context_dir / "claim_facts.json"
        tmp_path = output_path.with_suffix(".tmp")

        try:
            # Write to temp file first (atomic write pattern)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(
                    facts.model_dump(mode="json"),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            # Atomic rename
            tmp_path.replace(output_path)
            logger.info(f"Wrote claim_facts.json to {output_path}")
            return output_path

        except IOError as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise AggregationError(f"Failed to write claim_facts.json: {e}")
