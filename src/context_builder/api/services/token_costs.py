"""Token cost aggregation service.

Reads LLM call logs from llm_calls.jsonl and aggregates token usage and costs
for dashboards and reporting.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from context_builder.services.token_pricing import calculate_cost


class TokenCostsService:
    """Aggregates token usage and costs from llm_calls.jsonl."""

    def __init__(self, logs_dir: Path):
        """Initialize the service.

        Args:
            logs_dir: Path to workspace logs directory containing llm_calls.jsonl
        """
        self.logs_dir = logs_dir
        self.llm_calls_path = logs_dir / "llm_calls.jsonl"

    def _safe_int(self, value) -> int:
        """Safely convert a value to int, handling strings and None."""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def _read_calls(self) -> list[dict]:
        """Read all LLM call records from the log file.

        Returns:
            List of call records (dicts)
        """
        if not self.llm_calls_path.exists():
            return []

        calls = []
        with open(self.llm_calls_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        calls.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return calls

    def _enrich_call(self, call: dict) -> dict:
        """Add computed cost to a call record.

        Args:
            call: Raw call record

        Returns:
            Call record with 'cost_usd' field added
        """
        model = call.get("model", "gpt-4o") or "gpt-4o"
        prompt_tokens = self._safe_int(call.get("prompt_tokens"))
        completion_tokens = self._safe_int(call.get("completion_tokens"))
        cost = calculate_cost(model, prompt_tokens, completion_tokens)
        return {**call, "cost_usd": cost}

    def get_overview(self) -> dict:
        """Get overall token usage and cost summary.

        Returns:
            Dict with total_cost_usd, total_tokens, total_prompt_tokens,
            total_completion_tokens, total_calls, docs_processed,
            avg_cost_per_doc, avg_cost_per_call, primary_model
        """
        calls = self._read_calls()
        if not calls:
            return {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_calls": 0,
                "docs_processed": 0,
                "avg_cost_per_doc": 0.0,
                "avg_cost_per_call": 0.0,
                "primary_model": "N/A",
            }

        total_cost = 0.0
        total_prompt = 0
        total_completion = 0
        model_counts: dict[str, int] = defaultdict(int)
        doc_ids: set[str] = set()

        for call in calls:
            enriched = self._enrich_call(call)
            total_cost += enriched["cost_usd"]
            total_prompt += self._safe_int(call.get("prompt_tokens"))
            total_completion += self._safe_int(call.get("completion_tokens"))

            model = call.get("model", "unknown")
            model_counts[model] += 1

            doc_id = call.get("doc_id")
            if doc_id:
                doc_ids.add(doc_id)

        total_tokens = total_prompt + total_completion
        total_calls = len(calls)
        docs_processed = len(doc_ids)
        primary_model = max(model_counts, key=model_counts.get) if model_counts else "N/A"

        return {
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_calls": total_calls,
            "docs_processed": docs_processed,
            "avg_cost_per_doc": round(total_cost / docs_processed, 4) if docs_processed else 0.0,
            "avg_cost_per_call": round(total_cost / total_calls, 6) if total_calls else 0.0,
            "primary_model": primary_model,
        }

    def get_by_operation(self) -> list[dict]:
        """Get token usage and costs broken down by operation type.

        Returns:
            List of dicts with operation, tokens, prompt_tokens, completion_tokens,
            cost_usd, call_count, percentage
        """
        calls = self._read_calls()
        if not calls:
            return []

        # Aggregate by operation
        by_op: dict[str, dict] = defaultdict(
            lambda: {
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
                "call_count": 0,
            }
        )

        for call in calls:
            enriched = self._enrich_call(call)
            # Normalize operation name
            operation = call.get("call_purpose", "unknown") or "unknown"
            # Map to friendly names
            op_map = {
                "classification": "classification",
                "classify": "classification",
                "extraction": "extraction",
                "extract": "extraction",
                "vision": "vision_ocr",
                "vision_ocr": "vision_ocr",
                "ocr": "vision_ocr",
                "assessment": "assessment",
            }
            operation = op_map.get(operation, operation)

            by_op[operation]["tokens"] += (
                self._safe_int(call.get("prompt_tokens")) +
                self._safe_int(call.get("completion_tokens"))
            )
            by_op[operation]["prompt_tokens"] += self._safe_int(call.get("prompt_tokens"))
            by_op[operation]["completion_tokens"] += self._safe_int(call.get("completion_tokens"))
            by_op[operation]["cost_usd"] += enriched["cost_usd"]
            by_op[operation]["call_count"] += 1

        # Calculate percentages
        total_cost = sum(op["cost_usd"] for op in by_op.values())
        results = []
        for operation, data in by_op.items():
            pct = (data["cost_usd"] / total_cost * 100) if total_cost else 0
            results.append(
                {
                    "operation": operation,
                    "tokens": data["tokens"],
                    "prompt_tokens": data["prompt_tokens"],
                    "completion_tokens": data["completion_tokens"],
                    "cost_usd": round(data["cost_usd"], 4),
                    "call_count": data["call_count"],
                    "percentage": round(pct, 1),
                }
            )

        # Sort by cost descending
        results.sort(key=lambda x: x["cost_usd"], reverse=True)
        return results

    def get_by_run(self, limit: int = 20) -> list[dict]:
        """Get token usage and costs per pipeline run.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of dicts with run_id, timestamp, model, claims_count,
            docs_count, tokens, cost_usd, avg_cost_per_doc
        """
        calls = self._read_calls()
        if not calls:
            return []

        # Aggregate by run
        by_run: dict[str, dict] = defaultdict(
            lambda: {
                "timestamp": None,
                "model": None,
                "claim_ids": set(),
                "doc_ids": set(),
                "tokens": 0,
                "cost_usd": 0.0,
            }
        )

        for call in calls:
            run_id = call.get("run_id")
            if not run_id:
                continue

            enriched = self._enrich_call(call)
            data = by_run[run_id]

            # Track first timestamp and model
            if data["timestamp"] is None:
                data["timestamp"] = call.get("created_at")
                data["model"] = call.get("model", "unknown")

            if call.get("claim_id"):
                data["claim_ids"].add(call["claim_id"])
            if call.get("doc_id"):
                data["doc_ids"].add(call["doc_id"])

            data["tokens"] += (
                self._safe_int(call.get("prompt_tokens")) +
                self._safe_int(call.get("completion_tokens"))
            )
            data["cost_usd"] += enriched["cost_usd"]

        # Convert to list and compute metrics
        results = []
        for run_id, data in by_run.items():
            docs_count = len(data["doc_ids"])
            results.append(
                {
                    "run_id": run_id,
                    "timestamp": data["timestamp"],
                    "model": data["model"],
                    "claims_count": len(data["claim_ids"]),
                    "docs_count": docs_count,
                    "tokens": data["tokens"],
                    "cost_usd": round(data["cost_usd"], 4),
                    "avg_cost_per_doc": round(data["cost_usd"] / docs_count, 4)
                    if docs_count
                    else 0.0,
                }
            )

        # Sort by timestamp descending (most recent first)
        results.sort(key=lambda x: x["timestamp"] or "", reverse=True)
        return results[:limit]

    def get_by_claim(self, run_id: Optional[str] = None) -> list[dict]:
        """Get token costs per claim.

        Args:
            run_id: Optional run ID filter

        Returns:
            List of dicts with claim_id, docs_count, tokens, cost_usd
        """
        calls = self._read_calls()
        if not calls:
            return []

        # Filter by run if specified
        if run_id:
            calls = [c for c in calls if c.get("run_id") == run_id]

        # Aggregate by claim
        by_claim: dict[str, dict] = defaultdict(
            lambda: {"doc_ids": set(), "tokens": 0, "cost_usd": 0.0}
        )

        for call in calls:
            claim_id = call.get("claim_id")
            if not claim_id:
                continue

            enriched = self._enrich_call(call)
            data = by_claim[claim_id]

            if call.get("doc_id"):
                data["doc_ids"].add(call["doc_id"])

            data["tokens"] += (
                self._safe_int(call.get("prompt_tokens")) +
                self._safe_int(call.get("completion_tokens"))
            )
            data["cost_usd"] += enriched["cost_usd"]

        # Convert to list
        results = []
        for claim_id, data in by_claim.items():
            results.append(
                {
                    "claim_id": claim_id,
                    "docs_count": len(data["doc_ids"]),
                    "tokens": data["tokens"],
                    "cost_usd": round(data["cost_usd"], 4),
                }
            )

        # Sort by cost descending
        results.sort(key=lambda x: x["cost_usd"], reverse=True)
        return results

    def get_by_doc(self, claim_id: Optional[str] = None, run_id: Optional[str] = None) -> list[dict]:
        """Get token costs per document.

        Args:
            claim_id: Optional claim ID filter
            run_id: Optional run ID filter

        Returns:
            List of dicts with doc_id, claim_id, tokens, cost_usd, operations
        """
        calls = self._read_calls()
        if not calls:
            return []

        # Apply filters
        if run_id:
            calls = [c for c in calls if c.get("run_id") == run_id]
        if claim_id:
            calls = [c for c in calls if c.get("claim_id") == claim_id]

        # Aggregate by doc
        by_doc: dict[str, dict] = defaultdict(
            lambda: {"claim_id": None, "tokens": 0, "cost_usd": 0.0, "operations": set()}
        )

        for call in calls:
            doc_id = call.get("doc_id")
            if not doc_id:
                continue

            enriched = self._enrich_call(call)
            data = by_doc[doc_id]

            if data["claim_id"] is None:
                data["claim_id"] = call.get("claim_id")

            data["tokens"] += (
                self._safe_int(call.get("prompt_tokens")) +
                self._safe_int(call.get("completion_tokens"))
            )
            data["cost_usd"] += enriched["cost_usd"]

            operation = call.get("call_purpose")
            if operation:
                data["operations"].add(operation)

        # Convert to list
        results = []
        for doc_id, data in by_doc.items():
            results.append(
                {
                    "doc_id": doc_id,
                    "claim_id": data["claim_id"],
                    "tokens": data["tokens"],
                    "cost_usd": round(data["cost_usd"], 4),
                    "operations": list(data["operations"]),
                }
            )

        # Sort by cost descending
        results.sort(key=lambda x: x["cost_usd"], reverse=True)
        return results

    def get_daily_trend(self, days: int = 30) -> list[dict]:
        """Get daily token costs for trend chart.

        Args:
            days: Number of days to include

        Returns:
            List of dicts with date, tokens, cost_usd, call_count
        """
        calls = self._read_calls()
        if not calls:
            return []

        # Calculate cutoff date
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Aggregate by day
        by_day: dict[str, dict] = defaultdict(
            lambda: {"tokens": 0, "cost_usd": 0.0, "call_count": 0}
        )

        for call in calls:
            created_at = call.get("created_at")
            if not created_at:
                continue

            # Parse timestamp
            try:
                if "T" in created_at:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                continue

            # Skip if before cutoff
            if dt.replace(tzinfo=None) < cutoff:
                continue

            date_str = dt.strftime("%Y-%m-%d")
            enriched = self._enrich_call(call)

            by_day[date_str]["tokens"] += (
                self._safe_int(call.get("prompt_tokens")) +
                self._safe_int(call.get("completion_tokens"))
            )
            by_day[date_str]["cost_usd"] += enriched["cost_usd"]
            by_day[date_str]["call_count"] += 1

        # Convert to list and fill gaps
        results = []
        current = datetime.utcnow()
        for i in range(days):
            date = (current - timedelta(days=i)).strftime("%Y-%m-%d")
            data = by_day.get(date, {"tokens": 0, "cost_usd": 0.0, "call_count": 0})
            results.append(
                {
                    "date": date,
                    "tokens": data["tokens"],
                    "cost_usd": round(data["cost_usd"], 4),
                    "call_count": data["call_count"],
                }
            )

        # Reverse to chronological order
        results.reverse()
        return results

    def get_by_model(self) -> list[dict]:
        """Get token usage and costs broken down by model.

        Returns:
            List of dicts with model, tokens, cost_usd, call_count, percentage
        """
        calls = self._read_calls()
        if not calls:
            return []

        # Aggregate by model
        by_model: dict[str, dict] = defaultdict(
            lambda: {"tokens": 0, "cost_usd": 0.0, "call_count": 0}
        )

        for call in calls:
            model = call.get("model", "unknown") or "unknown"
            enriched = self._enrich_call(call)

            by_model[model]["tokens"] += (
                self._safe_int(call.get("prompt_tokens")) +
                self._safe_int(call.get("completion_tokens"))
            )
            by_model[model]["cost_usd"] += enriched["cost_usd"]
            by_model[model]["call_count"] += 1

        # Calculate percentages
        total_cost = sum(m["cost_usd"] for m in by_model.values())
        results = []
        for model, data in by_model.items():
            pct = (data["cost_usd"] / total_cost * 100) if total_cost else 0
            results.append(
                {
                    "model": model,
                    "tokens": data["tokens"],
                    "cost_usd": round(data["cost_usd"], 4),
                    "call_count": data["call_count"],
                    "percentage": round(pct, 1),
                }
            )

        # Sort by cost descending
        results.sort(key=lambda x: x["cost_usd"], reverse=True)
        return results
