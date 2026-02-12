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
    DecisionSource,
    LineItemCoverage,
    MatchMethod,
    CoverageStatus,
    NonCoveredExplanation,
)
from context_builder.coverage.rule_engine import RuleEngine
from context_builder.coverage.keyword_matcher import KeywordMatcher
from context_builder.coverage.analyzer import CoverageAnalyzer
from context_builder.coverage.explanation_generator import ExplanationGenerator

__all__ = [
    "CoverageAnalysisResult",
    "CoverageSummary",
    "DecisionSource",
    "LineItemCoverage",
    "MatchMethod",
    "CoverageStatus",
    "NonCoveredExplanation",
    "RuleEngine",
    "KeywordMatcher",
    "CoverageAnalyzer",
    "ExplanationGenerator",
]
