"""Coverage analysis module for line item coverage determination.

This module provides a preprocessing system that analyzes line items from
cost estimates against policy coverage, producing structured coverage data
before the assessment stage.

Architecture:
    Reconciliation -> Enrichment -> [Coverage Analysis] -> Assessment
                                            |
                                            v
                                coverage_analysis.json
"""

from context_builder.coverage.schemas import (
    CoverageAnalysisResult,
    CoverageSummary,
    LineItemCoverage,
    MatchMethod,
    CoverageStatus,
)
from context_builder.coverage.rule_engine import RuleEngine
from context_builder.coverage.keyword_matcher import KeywordMatcher
from context_builder.coverage.analyzer import CoverageAnalyzer

__all__ = [
    "CoverageAnalysisResult",
    "CoverageSummary",
    "LineItemCoverage",
    "MatchMethod",
    "CoverageStatus",
    "RuleEngine",
    "KeywordMatcher",
    "CoverageAnalyzer",
]
