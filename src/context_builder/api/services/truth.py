"""Truth registry API services."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from context_builder.storage import FileStorage
from context_builder.storage.truth_store import TruthStore

logger = logging.getLogger(__name__)


@dataclass
class DocInstance:
    doc_id: str
    claim_id: str
    doc_type: str
    original_filename: str


class TruthService:
    """Service for listing canonical truth entries with run comparisons."""

    def __init__(self, claims_dir: Path):
        self.claims_dir = claims_dir
        self.output_root = claims_dir.parent
        self.truth_root = self.output_root / "registry" / "truth"
        self.storage = FileStorage(self.output_root)

    def list_truth_entries(
        self,
        file_md5: Optional[str] = None,
        doc_type: Optional[str] = None,
        claim_id: Optional[str] = None,
        reviewer: Optional[str] = None,
        reviewed_after: Optional[str] = None,
        reviewed_before: Optional[str] = None,
        field_name: Optional[str] = None,
        state: Optional[str] = None,
        outcome: Optional[str] = None,
        run_id: Optional[str] = None,
        filename: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.truth_root.exists() or not self._has_truth_entries():
            self._migrate_from_labels()
            if not self.truth_root.exists() or not self._has_truth_entries():
                return {"runs": [], "entries": []}

        runs = self._list_runs(run_id)
        file_index = self._build_file_md5_index(doc_type, claim_id, filename, search)

        reviewed_after_dt = self._parse_dt(reviewed_after)
        reviewed_before_dt = self._parse_dt(reviewed_before)

        entries: List[Dict[str, Any]] = []
        for truth_path in self._iter_truth_files():
            try:
                with open(truth_path, "r", encoding="utf-8") as f:
                    truth = json.load(f)
            except (json.JSONDecodeError, IOError) as exc:
                logger.warning("Failed to load truth file %s: %s", truth_path, exc)
                continue

            file_md5_value = (
                truth.get("input_hashes", {}).get("file_md5")
                or truth_path.parent.name
            )
            if file_md5 and file_md5_value != file_md5:
                continue

            review = truth.get("review", {})
            reviewer_value = review.get("reviewer", "")
            if reviewer and reviewer_value != reviewer:
                continue

            reviewed_at = review.get("reviewed_at")
            if reviewed_at:
                reviewed_dt = self._parse_dt(reviewed_at)
                if reviewed_after_dt and reviewed_dt and reviewed_dt < reviewed_after_dt:
                    continue
                if reviewed_before_dt and reviewed_dt and reviewed_dt > reviewed_before_dt:
                    continue

            doc_instances = file_index.get(file_md5_value, [])
            if doc_type and not any(d.doc_type == doc_type for d in doc_instances):
                continue
            if claim_id and not any(d.claim_id == claim_id for d in doc_instances):
                continue
            if filename and not any(filename.lower() in d.original_filename.lower() for d in doc_instances):
                continue

            field_rows = self._build_field_rows(
                truth=truth,
                file_md5=file_md5_value,
                doc_instances=doc_instances,
                runs=runs,
                field_name=field_name,
                state=state,
            )

            if outcome and not self._has_outcome(field_rows, outcome):
                continue

            entry = {
                "file_md5": file_md5_value,
                "content_md5": truth.get("input_hashes", {}).get("content_md5", ""),
                "review": review,
                "doc_labels": truth.get("doc_labels", {}),
                "source_doc_ref": truth.get("source_doc_ref", {}),
                "doc_instances": [
                    {
                        "doc_id": d.doc_id,
                        "claim_id": d.claim_id,
                        "doc_type": d.doc_type,
                        "original_filename": d.original_filename,
                    }
                    for d in doc_instances
                ],
                "fields": field_rows,
            }
            entries.append(entry)

        return {"runs": runs, "entries": entries}

    def _iter_truth_files(self) -> Iterable[Path]:
        for truth_dir in self.truth_root.iterdir():
            if not truth_dir.is_dir():
                continue
            truth_file = truth_dir / "latest.json"
            if truth_file.exists():
                yield truth_file

    def _has_truth_entries(self) -> bool:
        if not self.truth_root.exists():
            return False
        for truth_dir in self.truth_root.iterdir():
            if not truth_dir.is_dir():
                continue
            if (truth_dir / "latest.json").exists():
                return True
        return False

    def _list_runs(self, run_id: Optional[str]) -> List[str]:
        if run_id:
            return [run_id]
        return [r.run_id for r in self.storage.list_runs()]

    def _build_file_md5_index(
        self,
        doc_type: Optional[str],
        claim_id: Optional[str],
        filename: Optional[str],
        search: Optional[str],
    ) -> Dict[str, List[DocInstance]]:
        index: Dict[str, List[DocInstance]] = {}
        for claim_dir in self.claims_dir.iterdir():
            if not claim_dir.is_dir() or claim_dir.name.startswith("."):
                continue

            docs_dir = claim_dir / "docs"
            if not docs_dir.exists():
                continue

            for doc_dir in docs_dir.iterdir():
                if not doc_dir.is_dir():
                    continue
                meta_path = doc_dir / "meta" / "doc.json"
                if not meta_path.exists():
                    continue
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except (json.JSONDecodeError, IOError):
                    continue

                file_md5 = meta.get("file_md5")
                if not file_md5:
                    continue

                doc_instance = DocInstance(
                    doc_id=meta.get("doc_id", doc_dir.name),
                    claim_id=meta.get("claim_id", claim_dir.name),
                    doc_type=meta.get("doc_type", "unknown"),
                    original_filename=meta.get("original_filename", ""),
                )

                if doc_type and doc_instance.doc_type != doc_type:
                    continue
                if claim_id and doc_instance.claim_id != claim_id:
                    continue
                if filename and filename.lower() not in doc_instance.original_filename.lower():
                    continue
                if search:
                    search_lower = search.lower()
                    if (
                        search_lower not in doc_instance.original_filename.lower()
                        and search_lower not in doc_instance.doc_id.lower()
                        and search_lower not in doc_instance.claim_id.lower()
                        and search_lower not in file_md5.lower()
                    ):
                        continue

                index.setdefault(file_md5, []).append(doc_instance)

        return index

    def _build_field_rows(
        self,
        truth: Dict[str, Any],
        file_md5: str,
        doc_instances: List[DocInstance],
        runs: List[str],
        field_name: Optional[str],
        state: Optional[str],
    ) -> List[Dict[str, Any]]:
        fields = []
        extraction_cache: Dict[tuple[str, str], Optional[Dict[str, Any]]] = {}

        for label in truth.get("field_labels", []):
            label_field_name = label.get("field_name")
            if not label_field_name:
                continue
            if field_name and label_field_name != field_name:
                continue
            label_state = label.get("state")
            if state and label_state != state:
                continue

            run_values: Dict[str, Any] = {}
            for run_id in runs:
                extraction = self._find_extraction_for_file_md5(
                    extraction_cache, run_id, file_md5, doc_instances
                )
                if not extraction:
                    run_values[run_id] = None
                    continue

                ext_field = next(
                    (f for f in extraction.get("fields", []) if f.get("name") == label_field_name),
                    None,
                )
                if not ext_field:
                    run_values[run_id] = {
                        "value": None,
                        "normalized_value": None,
                        "outcome": self._outcome(label_state, label.get("truth_value"), None),
                    }
                    continue

                normalized_value = ext_field.get("normalized_value") or ext_field.get("value")
                run_values[run_id] = {
                    "value": ext_field.get("value"),
                    "normalized_value": normalized_value,
                    "outcome": self._outcome(label_state, label.get("truth_value"), normalized_value),
                }

            fields.append({
                "field_name": label_field_name,
                "state": label_state,
                "truth_value": label.get("truth_value"),
                "runs": run_values,
            })

        return fields

    def _find_extraction_for_file_md5(
        self,
        cache: Dict[tuple[str, str], Optional[Dict[str, Any]]],
        run_id: str,
        file_md5: str,
        doc_instances: List[DocInstance],
    ) -> Optional[Dict[str, Any]]:
        cache_key = (run_id, file_md5)
        if cache_key in cache:
            return cache[cache_key]

        extraction = None
        for doc in doc_instances:
            extraction = self.storage.get_extraction(run_id, doc.doc_id, doc.claim_id)
            if extraction:
                break

        cache[cache_key] = extraction
        return extraction

    @staticmethod
    def _outcome(state: Optional[str], truth_value: Optional[str], extracted_value: Optional[str]) -> Optional[str]:
        if state in ("LABELED", "CONFIRMED"):
            if extracted_value is None:
                return "missing"
            return "correct" if extracted_value == truth_value else "incorrect"
        if state == "UNVERIFIABLE":
            return "unverifiable"
        if state == "UNLABELED":
            return "unlabeled"
        return None

    @staticmethod
    def _has_outcome(field_rows: List[Dict[str, Any]], outcome: str) -> bool:
        for row in field_rows:
            for run_data in row.get("runs", {}).values():
                if run_data and run_data.get("outcome") == outcome:
                    return True
        return False

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _migrate_from_labels(self) -> None:
        """Backfill canonical truth from existing per-doc labels."""
        truth_store = TruthStore(self.output_root)
        migrated = 0

        for claim_dir in self.claims_dir.iterdir():
            if not claim_dir.is_dir() or claim_dir.name.startswith("."):
                continue

            docs_dir = claim_dir / "docs"
            if not docs_dir.exists():
                continue

            for doc_dir in docs_dir.iterdir():
                if not doc_dir.is_dir():
                    continue

                label_path = doc_dir / "labels" / "latest.json"
                meta_path = doc_dir / "meta" / "doc.json"
                if not label_path.exists() or not meta_path.exists():
                    continue

                try:
                    with open(label_path, "r", encoding="utf-8") as f:
                        label_data = json.load(f)
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except (json.JSONDecodeError, IOError):
                    continue

                file_md5 = meta.get("file_md5")
                if not file_md5:
                    continue

                truth_payload = {
                    **label_data,
                    "schema_version": "label_v3",
                    "input_hashes": {
                        "file_md5": file_md5,
                        "content_md5": meta.get("content_md5", ""),
                    },
                    "source_doc_ref": {
                        "claim_id": label_data.get("claim_id") or meta.get("claim_id", ""),
                        "doc_id": label_data.get("doc_id") or meta.get("doc_id", doc_dir.name),
                        "original_filename": meta.get("original_filename", ""),
                    },
                }

                try:
                    truth_store.save_truth_by_file_md5(file_md5, truth_payload)
                    migrated += 1
                except IOError:
                    continue

        if migrated:
            logger.info("Backfilled %s canonical truth entries from labels.", migrated)
