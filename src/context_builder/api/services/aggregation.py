"""Aggregation service for combining extracted facts from multiple documents."""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from context_builder.schemas.claim_facts import (
    AggregatedFact,
    AggregatedLineItem,
    AggregatedServiceEntry,
    ClaimFacts,
    FactProvenance,
    LineItemProvenance,
    SourceDocument,
    StructuredClaimData,
)
from context_builder.storage.filesystem import FileStorage

logger = logging.getLogger(__name__)

# =============================================================================
# DOCUMENT-SPECIFIC FIELDS
# =============================================================================
# These fields are inherently tied to their source document type and should NOT
# be reconciled across document types. Each doc type gets its own namespaced
# version: e.g., "service_history.document_date" vs "cost_estimate.document_date"
#
# This prevents false "conflicts" when the same field name has different
# (but valid) values in different document types.
# =============================================================================

DEFAULT_DOCUMENT_SPECIFIC_FIELDS: Set[str] = {
    "document_date",
    "document_number",
    "document_id",
    "issuer",
    "issuer_name",
    "issuer_address",
    "recipient",
    "recipient_name",
    "recipient_address",
}


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
        self._document_specific_fields: Optional[Set[str]] = None

    def get_document_specific_fields(self) -> Set[str]:
        """Get the set of document-specific fields (loaded once and cached).

        These fields are namespaced by doc_type during aggregation to prevent
        false conflicts between different document types.

        Returns:
            Set of field names that are document-specific.
        """
        if self._document_specific_fields is not None:
            return self._document_specific_fields

        # Start with defaults
        fields = set(DEFAULT_DOCUMENT_SPECIFIC_FIELDS)

        # Try to load overrides from workspace config
        config_path = self.storage.output_root / "config" / "aggregation.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                if config and "document_specific_fields" in config:
                    custom_fields = config["document_specific_fields"]
                    if isinstance(custom_fields, list):
                        # Replace defaults with custom list
                        fields = set(custom_fields)
                        logger.info(
                            f"Loaded {len(fields)} document-specific fields from config"
                        )
            except Exception as e:
                logger.warning(f"Failed to load aggregation config: {e}")

        self._document_specific_fields = fields
        return fields

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
        Also attaches structured_data to candidates when available.

        Document-specific fields (like document_date) are namespaced by doc_type
        to prevent false conflicts: e.g., "service_history.document_date".

        Args:
            extractions: List of (doc_id, doc_type, filename, extraction_data) tuples.
            run_id: Run ID for provenance.

        Returns:
            Dict mapping field names to list of candidate values.
        """
        candidates: Dict[str, List[dict]] = defaultdict(list)
        doc_specific_fields = self.get_document_specific_fields()

        for doc_id, doc_type, filename, extraction in extractions:
            fields = extraction.get("fields", [])
            # Get structured_data from extraction (contains full component lists, etc.)
            structured_data = extraction.get("structured_data", {}) or {}

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

                # Check if this field has corresponding structured data
                # (e.g., covered_components, excluded_components, coverage_scale)
                structured_value = structured_data.get(name)

                # Determine the aggregation key:
                # - Document-specific fields are namespaced: "doc_type.field_name"
                # - Claim-level fields use just the field name
                if name in doc_specific_fields:
                    aggregation_key = f"{doc_type}.{name}"
                else:
                    aggregation_key = name

                candidate = {
                    "name": aggregation_key,  # Use namespaced name
                    "original_name": name,     # Keep original for reference
                    "value": value,
                    "normalized_value": normalized_value,
                    "confidence": confidence,
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "filename": filename,
                    "extraction_run_id": run_id,
                    "page": provenance.get("page"),
                    "text_quote": provenance.get("text_quote"),
                    "char_start": provenance.get("char_start"),
                    "char_end": provenance.get("char_end"),
                    "structured_value": structured_value,
                }

                candidates[aggregation_key].append(candidate)

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

            # Get structured_value if available (for complex fields like covered_components)
            structured_value = primary.get("structured_value")

            fact = AggregatedFact(
                name=field_name,
                value=primary["value"],
                normalized_value=primary.get("normalized_value"),
                confidence=primary["confidence"],
                selected_from=FactProvenance(
                    doc_id=primary["doc_id"],
                    doc_type=primary["doc_type"],
                    extraction_run_id=primary["extraction_run_id"],
                    page=primary.get("page"),
                    text_quote=primary.get("text_quote"),
                    char_start=primary.get("char_start"),
                    char_end=primary.get("char_end"),
                ),
                structured_value=structured_value,
            )
            facts.append(fact)

        return facts

    def collect_structured_data(
        self, extractions: List[Tuple[str, str, str, dict]], run_id: str
    ) -> Optional[StructuredClaimData]:
        """Collect line items and service entries from extractions.

        Args:
            extractions: List of (doc_id, doc_type, filename, extraction_data) tuples.
            run_id: Run ID for provenance.

        Returns:
            StructuredClaimData with line items and/or service entries, or None if none found.
        """
        all_line_items = []
        all_service_entries = []

        for doc_id, doc_type, filename, extraction in extractions:
            structured = extraction.get("structured_data")
            if not structured:
                continue

            provenance = LineItemProvenance(
                doc_id=doc_id,
                doc_type=doc_type,
                filename=filename,
                extraction_run_id=run_id,
            )

            # Collect line items from cost estimates
            if doc_type == "cost_estimate":
                line_items = structured.get("line_items", [])
                for item in line_items:
                    all_line_items.append(
                        AggregatedLineItem(
                            item_code=item.get("item_code"),
                            description=item.get("description", ""),
                            quantity=item.get("quantity"),
                            unit=item.get("unit"),
                            unit_price=item.get("unit_price"),
                            total_price=item.get("total_price"),
                            item_type=item.get("item_type"),
                            page_number=item.get("page_number"),
                            source=provenance,
                        )
                    )

            # Collect service entries from service history
            if doc_type == "service_history":
                service_entries = structured.get("service_entries", [])
                for entry in service_entries:
                    all_service_entries.append(
                        AggregatedServiceEntry(
                            service_type=entry.get("service_type"),
                            service_date=entry.get("service_date"),
                            mileage_km=entry.get("mileage_km"),
                            order_number=entry.get("order_number"),
                            work_performed=entry.get("work_performed"),
                            additional_work=entry.get("additional_work"),
                            service_provider_name=entry.get("service_provider_name"),
                            service_provider_address=entry.get("service_provider_address"),
                            is_authorized_partner=entry.get("is_authorized_partner"),
                            source=provenance,
                        )
                    )

        if all_line_items or all_service_entries:
            if all_line_items:
                logger.info(f"Collected {len(all_line_items)} line items from cost estimates")
            if all_service_entries:
                logger.info(f"Collected {len(all_service_entries)} service entries from service history")
            return StructuredClaimData(
                line_items=all_line_items if all_line_items else None,
                service_entries=all_service_entries if all_service_entries else None,
            )

        return None

    def aggregate_claim_facts(
        self, claim_id: str, claim_run_id: str, run_id: Optional[str] = None
    ) -> ClaimFacts:
        """Aggregate facts from all documents in a claim.

        Args:
            claim_id: Claim identifier.
            claim_run_id: Claim run ID to associate with this aggregation.
            run_id: Optional specific extraction run ID. If not provided, uses latest complete.

        Returns:
            ClaimFacts object with aggregated facts.

        Raises:
            AggregationError: If no complete runs exist or aggregation fails.
        """
        # Find extraction run to use
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

        # Collect structured data (line items from cost estimates)
        structured_data = self.collect_structured_data(extractions, run_id)

        # Build source documents list
        sources = [
            SourceDocument(doc_id=doc_id, filename=filename, doc_type=doc_type)
            for doc_id, doc_type, filename, _ in extractions
        ]

        return ClaimFacts(
            claim_id=claim_id,
            generated_at=datetime.utcnow(),
            claim_run_id=claim_run_id,
            extraction_runs_used=[run_id],
            run_policy="latest_complete",
            facts=facts,
            sources=sources,
            structured_data=structured_data,
        )

    def write_claim_facts(self, claim_id: str, facts: ClaimFacts) -> Path:
        """Write aggregated facts to claim run directory.

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

        from context_builder.storage.claim_run import ClaimRunStorage

        claim_run_storage = ClaimRunStorage(claim_folder)
        try:
            output_path = claim_run_storage.write_to_claim_run(
                facts.claim_run_id,
                "claim_facts.json",
                facts.model_dump(mode="json"),
            )
            logger.info(f"Wrote claim_facts.json to {output_path}")
            return output_path
        except Exception as e:
            raise AggregationError(f"Failed to write claim_facts.json: {e}")
