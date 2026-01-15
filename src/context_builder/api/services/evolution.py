"""Evolution tracking service for pipeline scope and accuracy over time."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from context_builder.schemas.decision_record import ScopeSnapshot, VersionBundle
from context_builder.storage.version_bundles import VersionBundleStore

logger = logging.getLogger(__name__)


@dataclass
class EvolutionDataPoint:
    """Single point in the evolution timeline."""

    spec_hash: str
    first_seen: str
    last_seen: str
    bundle_count: int

    # Scope metrics
    doc_types_count: int
    doc_types_list: List[str]
    total_fields: int
    fields_by_type: Dict[str, int]

    # Accuracy metrics (from representative run)
    representative_run_id: str
    accuracy_rate: Optional[float]
    correct_count: int
    incorrect_count: int
    missing_count: int
    docs_evaluated: int

    # Version info
    model_name: str
    contextbuilder_version: str
    git_commit: Optional[str]


@dataclass
class DocTypeAppearance:
    """A doc type's state at a specific spec version."""

    spec_hash: str
    field_count: int
    accuracy_rate: Optional[float] = None
    correct: int = 0
    incorrect: int = 0
    missing: int = 0


@dataclass
class DocTypeEvolution:
    """Evolution of a single doc type across versions."""

    doc_type: str
    first_version: str
    current_fields: int
    appearances: List[DocTypeAppearance] = field(default_factory=list)


@dataclass
class EvolutionSummary:
    """Complete evolution data for the dashboard."""

    timeline: List[EvolutionDataPoint]
    spec_versions: List[str]  # Ordered list of spec hashes

    # Overall progression
    scope_growth: Dict[str, Any]
    accuracy_trend: Dict[str, Any]

    # Per doc-type evolution
    doc_type_matrix: List[DocTypeEvolution]


class EvolutionService:
    """Service for tracking pipeline evolution over time."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.bundle_store = VersionBundleStore(data_dir)

    def get_evolution_timeline(self) -> Dict[str, Any]:
        """Get the full evolution timeline with scope and accuracy metrics.

        Returns:
            EvolutionSummary as a dict with timeline, scope_growth, accuracy_trend.
        """
        # Get all bundles
        all_bundles = self.bundle_store.get_all_bundles()

        if not all_bundles:
            return self._empty_summary()

        # Group bundles by extraction_spec_hash
        spec_groups: Dict[str, List[tuple[str, VersionBundle]]] = defaultdict(list)
        for run_id, bundle in all_bundles:
            spec_hash = bundle.extraction_spec_hash or "unknown"
            spec_groups[spec_hash].append((run_id, bundle))

        # Build timeline data points
        timeline: List[EvolutionDataPoint] = []

        for spec_hash, bundles in spec_groups.items():
            # Sort by created_at within group
            bundles.sort(key=lambda x: x[1].created_at)

            first_bundle = bundles[0][1]
            last_bundle = bundles[-1][1]

            # Use most recent run as representative
            representative_run_id = bundles[-1][0]

            # Get scope from snapshot (prefer last bundle's snapshot)
            scope = last_bundle.scope_snapshot or first_bundle.scope_snapshot
            if scope:
                doc_types_list = scope.doc_types
                doc_types_count = len(scope.doc_types)
                total_fields = scope.total_fields
                fields_by_type = scope.fields_by_type
            else:
                doc_types_list = []
                doc_types_count = 0
                total_fields = 0
                fields_by_type = {}

            # Get accuracy from eval summary
            eval_summary = self._get_eval_summary(representative_run_id)
            accuracy_rate = None
            correct_count = 0
            incorrect_count = 0
            missing_count = 0
            docs_evaluated = 0

            if eval_summary:
                correct_count = eval_summary.get("correct", 0)
                incorrect_count = eval_summary.get("incorrect", 0)
                missing_count = eval_summary.get("missing", 0)
                docs_evaluated = eval_summary.get("docs_evaluated", 0)

                total_outcomes = correct_count + incorrect_count + missing_count
                if total_outcomes > 0:
                    accuracy_rate = round(100 * correct_count / total_outcomes, 1)

            point = EvolutionDataPoint(
                spec_hash=spec_hash[:12],  # Short hash for display
                first_seen=first_bundle.created_at,
                last_seen=last_bundle.created_at,
                bundle_count=len(bundles),
                doc_types_count=doc_types_count,
                doc_types_list=doc_types_list,
                total_fields=total_fields,
                fields_by_type=fields_by_type,
                representative_run_id=representative_run_id,
                accuracy_rate=accuracy_rate,
                correct_count=correct_count,
                incorrect_count=incorrect_count,
                missing_count=missing_count,
                docs_evaluated=docs_evaluated,
                model_name=last_bundle.model_name,
                contextbuilder_version=last_bundle.contextbuilder_version,
                git_commit=last_bundle.git_commit[:8] if last_bundle.git_commit else None,
            )
            timeline.append(point)

        # Sort timeline by first_seen
        timeline.sort(key=lambda x: x.first_seen)

        # Compute scope growth
        scope_growth = self._compute_scope_growth(timeline)

        # Compute accuracy trend
        accuracy_trend = self._compute_accuracy_trend(timeline)

        # Build doc type matrix
        doc_type_matrix = self._build_doc_type_matrix(timeline)
        spec_versions = [p.spec_hash for p in timeline]

        return {
            "timeline": [self._datapoint_to_dict(p) for p in timeline],
            "spec_versions": spec_versions,
            "scope_growth": scope_growth,
            "accuracy_trend": accuracy_trend,
            "doc_type_matrix": [self._doc_type_evolution_to_dict(d) for d in doc_type_matrix],
        }

    def get_doc_type_matrix(self) -> Dict[str, Any]:
        """Get just the doc type evolution matrix.

        Returns:
            Dict with doc_types list and spec_versions.
        """
        summary = self.get_evolution_timeline()
        return {
            "doc_types": summary.get("doc_type_matrix", []),
            "spec_versions": summary.get("spec_versions", []),
        }

    def _get_eval_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Load eval summary for a run if available."""
        eval_path = self.data_dir / "runs" / run_id / "eval" / "summary.json"
        if not eval_path.exists():
            return None

        try:
            with open(eval_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to load eval summary for {run_id}: {e}")
            return None

    def _compute_scope_growth(self, timeline: List[EvolutionDataPoint]) -> Dict[str, Any]:
        """Compute scope growth metrics from timeline."""
        if not timeline:
            return {
                "start_doc_types": 0,
                "end_doc_types": 0,
                "start_fields": 0,
                "end_fields": 0,
                "doc_types_added": [],
                "fields_delta": 0,
            }

        first = timeline[0]
        last = timeline[-1]

        start_types = set(first.doc_types_list)
        end_types = set(last.doc_types_list)
        added_types = list(end_types - start_types)

        return {
            "start_doc_types": first.doc_types_count,
            "end_doc_types": last.doc_types_count,
            "start_fields": first.total_fields,
            "end_fields": last.total_fields,
            "doc_types_added": added_types,
            "fields_delta": last.total_fields - first.total_fields,
        }

    def _compute_accuracy_trend(self, timeline: List[EvolutionDataPoint]) -> Dict[str, Any]:
        """Compute accuracy trend metrics from timeline."""
        # Filter to points with accuracy data
        with_accuracy = [p for p in timeline if p.accuracy_rate is not None]

        if not with_accuracy:
            return {
                "start_accuracy": None,
                "end_accuracy": None,
                "delta": None,
                "trend": "no_data",
            }

        first = with_accuracy[0]
        last = with_accuracy[-1]

        delta = round(last.accuracy_rate - first.accuracy_rate, 1) if first.accuracy_rate else 0

        if delta > 2:
            trend = "improving"
        elif delta < -2:
            trend = "regressing"
        else:
            trend = "stable"

        return {
            "start_accuracy": first.accuracy_rate,
            "end_accuracy": last.accuracy_rate,
            "delta": delta,
            "trend": trend,
        }

    def _build_doc_type_matrix(
        self, timeline: List[EvolutionDataPoint]
    ) -> List[DocTypeEvolution]:
        """Build per-doc-type evolution across all versions."""
        # Collect all doc types ever seen
        all_doc_types: Dict[str, DocTypeEvolution] = {}

        for point in timeline:
            for doc_type in point.doc_types_list:
                if doc_type not in all_doc_types:
                    all_doc_types[doc_type] = DocTypeEvolution(
                        doc_type=doc_type,
                        first_version=point.spec_hash,
                        current_fields=point.fields_by_type.get(doc_type, 0),
                        appearances=[],
                    )

                # Add appearance
                field_count = point.fields_by_type.get(doc_type, 0)
                all_doc_types[doc_type].appearances.append(
                    DocTypeAppearance(
                        spec_hash=point.spec_hash,
                        field_count=field_count,
                        accuracy_rate=point.accuracy_rate,  # Overall accuracy (per-type would need more data)
                    )
                )
                all_doc_types[doc_type].current_fields = field_count

        return list(all_doc_types.values())

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary when no data available."""
        return {
            "timeline": [],
            "spec_versions": [],
            "scope_growth": {
                "start_doc_types": 0,
                "end_doc_types": 0,
                "start_fields": 0,
                "end_fields": 0,
                "doc_types_added": [],
                "fields_delta": 0,
            },
            "accuracy_trend": {
                "start_accuracy": None,
                "end_accuracy": None,
                "delta": None,
                "trend": "no_data",
            },
            "doc_type_matrix": [],
        }

    def _datapoint_to_dict(self, point: EvolutionDataPoint) -> Dict[str, Any]:
        """Convert EvolutionDataPoint to dict."""
        return {
            "spec_hash": point.spec_hash,
            "first_seen": point.first_seen,
            "last_seen": point.last_seen,
            "bundle_count": point.bundle_count,
            "doc_types_count": point.doc_types_count,
            "doc_types_list": point.doc_types_list,
            "total_fields": point.total_fields,
            "fields_by_type": point.fields_by_type,
            "representative_run_id": point.representative_run_id,
            "accuracy_rate": point.accuracy_rate,
            "correct_count": point.correct_count,
            "incorrect_count": point.incorrect_count,
            "missing_count": point.missing_count,
            "docs_evaluated": point.docs_evaluated,
            "model_name": point.model_name,
            "contextbuilder_version": point.contextbuilder_version,
            "git_commit": point.git_commit,
        }

    def _doc_type_evolution_to_dict(self, dte: DocTypeEvolution) -> Dict[str, Any]:
        """Convert DocTypeEvolution to dict."""
        return {
            "doc_type": dte.doc_type,
            "first_version": dte.first_version,
            "current_fields": dte.current_fields,
            "appearances": [
                {
                    "spec_hash": a.spec_hash,
                    "field_count": a.field_count,
                    "accuracy_rate": a.accuracy_rate,
                }
                for a in dte.appearances
            ],
        }
