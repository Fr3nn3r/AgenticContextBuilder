"""Insights-focused API services."""

from pathlib import Path
from typing import Optional

from context_builder.api import insights as insights_module


class InsightsService:
    """Service layer for insights aggregation."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def get_overview(self) -> dict:
        aggregator = insights_module.InsightsAggregator(self.data_dir)
        return aggregator.get_overview()

    def get_doc_type_metrics(self) -> list:
        aggregator = insights_module.InsightsAggregator(self.data_dir)
        return aggregator.get_doc_type_metrics()

    def get_priorities(self, limit: int) -> list:
        aggregator = insights_module.InsightsAggregator(self.data_dir)
        return aggregator.get_priorities(limit=limit)

    def get_field_details(self, doc_type: str, field: str, run_id: Optional[str]) -> dict:
        aggregator = insights_module.InsightsAggregator(self.data_dir, run_id=run_id)
        return aggregator.get_field_details(doc_type, field)

    def get_examples(
        self,
        doc_type: Optional[str],
        field: Optional[str],
        outcome: Optional[str],
        run_id: Optional[str],
        limit: int,
    ) -> list:
        aggregator = insights_module.InsightsAggregator(self.data_dir, run_id=run_id)
        return aggregator.get_examples(
            doc_type=doc_type,
            field_name=field,
            outcome=outcome,
            limit=limit,
        )

    def list_runs(self) -> list:
        return insights_module.list_all_runs(self.data_dir)

    def list_runs_detailed(self) -> list:
        return insights_module.list_detailed_runs(self.data_dir)

    def get_run_overview(self, run_id: str) -> dict:
        aggregator = insights_module.InsightsAggregator(self.data_dir, run_id=run_id)
        return {
            "run_metadata": aggregator.get_run_metadata(),
            "overview": aggregator.get_overview(),
        }

    def get_run_doc_types(self, run_id: str) -> list:
        aggregator = insights_module.InsightsAggregator(self.data_dir, run_id=run_id)
        return aggregator.get_doc_type_metrics()

    def get_run_priorities(self, run_id: str, limit: int) -> list:
        aggregator = insights_module.InsightsAggregator(self.data_dir, run_id=run_id)
        return aggregator.get_priorities(limit=limit)

    def compare_runs(self, baseline: str, current: str) -> dict:
        return insights_module.compare_runs(self.data_dir, baseline, current)

    def get_baseline(self) -> dict:
        baseline_id = insights_module.get_baseline(self.data_dir)
        return {"baseline_run_id": baseline_id}

    def set_baseline(self, run_id: str) -> dict:
        insights_module.set_baseline(self.data_dir, run_id)
        return {"status": "ok", "baseline_run_id": run_id}

    def clear_baseline(self) -> dict:
        insights_module.clear_baseline(self.data_dir)
        return {"status": "ok"}
