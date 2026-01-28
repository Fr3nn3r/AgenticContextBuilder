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
    LineItemsSummary,
    PrimaryRepair,
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

        DEPRECATED: This method is deprecated. Use collect_latest_extractions()
        for cross-run aggregation which selects the latest extraction per document.

        Args:
            claim_id: Claim identifier.

        Returns:
            Run ID of the latest complete run, or None if no complete runs exist.
        """
        import warnings
        warnings.warn(
            "find_latest_complete_run is deprecated. Use collect_latest_extractions() for cross-run aggregation.",
            DeprecationWarning,
            stacklevel=2,
        )
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

        DEPRECATED: This method is deprecated. Use collect_latest_extractions()
        for cross-run aggregation which selects the latest extraction per document.

        Args:
            claim_id: Claim identifier.
            run_id: Run identifier.

        Returns:
            List of tuples: (doc_id, doc_type, filename, extraction_data)
        """
        import warnings
        warnings.warn(
            "load_extractions is deprecated. Use collect_latest_extractions() for cross-run aggregation.",
            DeprecationWarning,
            stacklevel=2,
        )
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

    def collect_latest_extractions(
        self, claim_id: str
    ) -> List[Tuple[str, str, str, str, dict]]:
        """Collect the latest extraction for each document across all runs.

        For each document in the claim, finds the most recent extraction file
        regardless of which run produced it. This allows partial re-extractions
        to "patch" previous runs.

        Args:
            claim_id: Claim identifier.

        Returns:
            List of tuples: (doc_id, run_id, doc_type, filename, extraction_data)
        """
        claim_folder = self.storage._find_claim_folder(claim_id)
        if not claim_folder:
            return []

        runs_dir = claim_folder / "runs"
        if not runs_dir.exists():
            return []

        # Step 1: Find all extractions across all runs
        # Key: doc_id, Value: list of (run_id, run_timestamp, extraction_path)
        doc_extractions: Dict[str, List[Tuple[str, str, Path]]] = defaultdict(list)

        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            if not (run_dir.name.startswith("run_") or run_dir.name.startswith("BATCH-")):
                continue

            extraction_dir = run_dir / "extraction"
            if not extraction_dir.exists():
                continue

            # Extract timestamp from run_id for sorting
            run_timestamp = self._extract_run_timestamp(run_dir.name)

            for ext_file in extraction_dir.glob("*.json"):
                doc_id = ext_file.stem
                doc_extractions[doc_id].append((run_dir.name, run_timestamp, ext_file))

        # Step 2: For each document, select the latest extraction
        results = []
        for doc_id, extractions in doc_extractions.items():
            # Sort by timestamp descending, take first
            extractions.sort(key=lambda x: x[1], reverse=True)
            run_id, _, ext_path = extractions[0]

            try:
                with open(ext_path, "r", encoding="utf-8") as f:
                    extraction = json.load(f)

                doc_info = extraction.get("doc", {})
                doc_type = doc_info.get("doc_type", "unknown")

                doc_meta = self.storage.get_doc_metadata(doc_id, claim_id)
                filename = (
                    doc_meta.get("original_filename", f"{doc_id}.pdf")
                    if doc_meta
                    else f"{doc_id}.pdf"
                )

                results.append((doc_id, run_id, doc_type, filename, extraction))

            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load extraction {ext_path}: {e}")
                continue

        return results

    def _extract_run_timestamp(self, run_id: str) -> str:
        """Extract sortable timestamp from run_id.

        Format: run_YYYYMMDD_HHMMSS_hash -> YYYYMMDD_HHMMSS
        """
        parts = run_id.split("_")
        if len(parts) >= 3 and parts[0] == "run":
            return f"{parts[1]}_{parts[2]}"
        # Fallback to full string for sorting
        return run_id

    def build_candidates(
        self, extractions: List[Tuple[str, str, str, str, dict]]
    ) -> Dict[str, List[dict]]:
        """Build candidate list from all extractions.

        Groups candidates by field name. Only includes fields with status="present".
        Also attaches structured_data to candidates when available.

        Document-specific fields (like document_date) are namespaced by doc_type
        to prevent false conflicts: e.g., "service_history.document_date".

        IMPORTANT: Provenance fields (page, text_quote, char_start, char_end)
        must all come from the same source extraction to ensure highlighting
        works correctly in the UI.

        Args:
            extractions: List of (doc_id, run_id, doc_type, filename, extraction_data) tuples.

        Returns:
            Dict mapping field names to list of candidate values.
        """
        candidates: Dict[str, List[dict]] = defaultdict(list)
        doc_specific_fields = self.get_document_specific_fields()

        for doc_id, run_id, doc_type, filename, extraction in extractions:
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

    def _summarize_line_items(
        self,
        line_items: List[AggregatedLineItem],
        primary_threshold: float = 500.0,
    ) -> Tuple[LineItemsSummary, List[PrimaryRepair]]:
        """Summarize line items for token reduction.

        Args:
            line_items: List of aggregated line items.
            primary_threshold: Minimum price to be considered a primary repair.

        Returns:
            Tuple of (summary, primary_repairs).
        """
        # Initialize counters
        by_type: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "total": 0.0, "items": []}
        )
        covered_total = 0.0
        not_covered_total = 0.0
        unknown_coverage_total = 0.0
        total_amount = 0.0

        primary_repairs = []

        for item in line_items:
            price = item.total_price or 0.0
            total_amount += price
            item_type = item.item_type or "unknown"

            # Track by type
            by_type[item_type]["count"] += 1
            by_type[item_type]["total"] += price
            # Only store first 5 descriptions per type to limit size
            if len(by_type[item_type]["items"]) < 5:
                by_type[item_type]["items"].append(item.description[:50])

            # Check coverage (from _coverage_lookup if present)
            # The coverage lookup is attached during enrichment, not aggregation
            # For now, track as unknown - will be updated by enrichment
            unknown_coverage_total += price

            # Identify primary repairs (high-value items)
            if price >= primary_threshold:
                primary_repairs.append(
                    PrimaryRepair(
                        description=item.description,
                        item_code=item.item_code,
                        total_price=price,
                        item_type=item.item_type,
                        covered=None,  # Will be set by enrichment
                        coverage_reason=None,
                    )
                )

        # Sort primary repairs by price descending
        primary_repairs.sort(key=lambda x: x.total_price, reverse=True)

        # Convert defaultdict to regular dict for serialization
        by_type_dict = {k: dict(v) for k, v in by_type.items()}

        summary = LineItemsSummary(
            total_items=len(line_items),
            total_amount=round(total_amount, 2),
            by_type=by_type_dict,
            covered_total=round(covered_total, 2),
            not_covered_total=round(not_covered_total, 2),
            unknown_coverage_total=round(unknown_coverage_total, 2),
        )

        return summary, primary_repairs

    def collect_structured_data(
        self,
        extractions: List[Tuple[str, str, str, str, dict]],
        max_line_items: int = 30,
    ) -> Optional[StructuredClaimData]:
        """Collect line items and service entries from extractions.

        Also computes summary statistics and identifies primary repairs
        to reduce token usage for large claims.

        For claims with many line items (>max_line_items), only the top items
        by value are kept in the line_items array. The full summary is always
        computed from ALL items before filtering.

        Args:
            extractions: List of (doc_id, run_id, doc_type, filename, extraction_data) tuples.
            max_line_items: Maximum number of line items to keep (default 30).
                Items are sorted by total_price descending, top N kept.

        Returns:
            StructuredClaimData with line items and/or service entries, or None if none found.
        """
        all_line_items = []
        all_service_entries = []

        for doc_id, run_id, doc_type, filename, extraction in extractions:
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

            # Compute summary and primary repairs for line items
            # Summary is computed from ALL items before any filtering
            line_items_summary = None
            primary_repairs = None
            filtered_line_items = all_line_items

            if all_line_items:
                line_items_summary, primary_repairs = self._summarize_line_items(all_line_items)

                # Filter to top N items by value if exceeds limit
                if len(all_line_items) > max_line_items:
                    # Sort by total_price descending
                    sorted_items = sorted(
                        all_line_items,
                        key=lambda x: x.total_price or 0.0,
                        reverse=True,
                    )
                    filtered_line_items = sorted_items[:max_line_items]
                    logger.info(
                        f"Filtered line items from {len(all_line_items)} to {max_line_items} "
                        f"(top by value)"
                    )

                logger.info(
                    f"Line items summary: {line_items_summary.total_items} items total, "
                    f"CHF {line_items_summary.total_amount:.2f}, "
                    f"{len(primary_repairs)} primary repairs (>500 CHF), "
                    f"{len(filtered_line_items)} items in output"
                )

            return StructuredClaimData(
                line_items=filtered_line_items if filtered_line_items else None,
                service_entries=all_service_entries if all_service_entries else None,
                line_items_summary=line_items_summary,
                primary_repairs=primary_repairs if primary_repairs else None,
            )

        return None

    def aggregate_claim_facts(self, claim_id: str, claim_run_id: str) -> ClaimFacts:
        """Aggregate facts from latest extraction per document (cross-run).

        Uses cross-run collection: for each document, finds the most recent
        extraction regardless of which run produced it. This allows partial
        re-extractions to improve claim data without re-processing all documents.

        Args:
            claim_id: Claim identifier.
            claim_run_id: Claim run ID to associate with this aggregation.

        Returns:
            ClaimFacts object with aggregated facts.

        Raises:
            AggregationError: If no extractions exist for the claim.
        """
        logger.info(f"Aggregating facts for claim {claim_id} (cross-run)")

        # Collect latest extraction per document across all runs
        extractions = self.collect_latest_extractions(claim_id)
        if not extractions:
            raise AggregationError(f"No extractions found for claim '{claim_id}'")

        # Track which runs were used
        runs_used = sorted(set(run_id for _, run_id, _, _, _ in extractions))
        logger.info(
            f"Collected {len(extractions)} extractions from {len(runs_used)} run(s)"
        )

        # Build candidates (updated signature - no run_id param)
        candidates = self.build_candidates(extractions)
        logger.info(f"Built candidates for {len(candidates)} fields")

        # Select primary values
        facts = self.select_primary(candidates)
        logger.info(f"Selected {len(facts)} aggregated facts")

        # Collect structured data (updated signature - no run_id param)
        structured_data = self.collect_structured_data(extractions)

        # Build source documents list (5-tuple format)
        sources = [
            SourceDocument(doc_id=doc_id, filename=filename, doc_type=doc_type)
            for doc_id, _, doc_type, filename, _ in extractions
        ]

        return ClaimFacts(
            claim_id=claim_id,
            generated_at=datetime.utcnow(),
            claim_run_id=claim_run_id,
            extraction_runs_used=runs_used,
            run_policy="latest_per_document",
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
