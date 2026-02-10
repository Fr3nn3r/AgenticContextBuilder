"""Composite Confidence Index (CCI) package.

Collects data-quality signals from every pipeline stage and computes
a single composite confidence score with full traceability.
"""

from context_builder.confidence.collector import ConfidenceCollector
from context_builder.confidence.scorer import ConfidenceScorer
from context_builder.confidence.stage import ConfidenceStage

__all__ = [
    "ConfidenceCollector",
    "ConfidenceScorer",
    "ConfidenceStage",
]
