"""Pydantic schemas for coverage analysis results.

These schemas define the output format for coverage analysis, which determines
whether each line item from a cost estimate is covered by the insurance policy.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CoverageStatus(str, Enum):
    """Coverage determination status for a line item."""

    COVERED = "covered"
    NOT_COVERED = "not_covered"
    REVIEW_NEEDED = "review_needed"


class MatchMethod(str, Enum):
    """Method used to determine coverage."""

    RULE = "rule"  # Deterministic rule-based matching
    PART_NUMBER = "part_number"  # Part number lookup from database/assumptions
    KEYWORD = "keyword"  # German keyword mapping
    LLM = "llm"  # LLM fallback for ambiguous items
    MANUAL = "manual"  # Human override


class LineItemCoverage(BaseModel):
    """Coverage determination for a single line item."""

    # Original item data
    item_code: Optional[str] = Field(None, description="Part/labor code from cost estimate")
    description: str = Field(..., description="Item description (usually in German)")
    item_type: str = Field(..., description="Item type: parts, labor, or fee")
    total_price: float = Field(..., description="Total price for this item")

    # Coverage determination
    coverage_status: CoverageStatus = Field(
        ..., description="Coverage status: covered, not_covered, or review_needed"
    )
    coverage_category: Optional[str] = Field(
        None, description="Matched policy category (e.g., engine, chassis, brakes)"
    )
    matched_component: Optional[str] = Field(
        None, description="Specific component from policy that matched"
    )
    match_method: MatchMethod = Field(
        ..., description="Method used to determine coverage"
    )
    match_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for the match (0.0-1.0)"
    )
    match_reasoning: str = Field(
        ..., description="Human-readable explanation of the coverage decision"
    )

    # Coverage amounts (calculated based on status and coverage_percent)
    covered_amount: float = Field(
        0.0, description="Amount covered by policy (before excess)"
    )
    not_covered_amount: float = Field(
        0.0, description="Amount not covered by policy"
    )


class CoverageSummary(BaseModel):
    """Summary statistics for coverage analysis."""

    total_claimed: float = Field(0.0, description="Sum of all line item totals")
    total_covered_before_excess: float = Field(
        0.0, description="Total covered amount before applying excess"
    )
    total_not_covered: float = Field(
        0.0, description="Total of not-covered items"
    )
    excess_amount: float = Field(
        0.0, description="Excess/deductible amount to subtract"
    )
    total_payable: float = Field(
        0.0, description="Final amount payable after excess and coverage"
    )
    items_covered: int = Field(0, description="Count of covered items")
    items_not_covered: int = Field(0, description="Count of not-covered items")
    items_review_needed: int = Field(0, description="Count of items needing review")
    coverage_percent: Optional[float] = Field(
        None, description="Coverage percentage from scale (based on km)"
    )


class CoverageInputs(BaseModel):
    """Input parameters used for coverage analysis."""

    vehicle_km: Optional[int] = Field(None, description="Vehicle odometer reading in km")
    coverage_percent: Optional[float] = Field(
        None, description="Coverage percentage from scale"
    )
    excess_percent: Optional[float] = Field(
        None, description="Excess percentage from policy"
    )
    excess_minimum: Optional[float] = Field(
        None, description="Minimum excess amount from policy"
    )
    covered_categories: List[str] = Field(
        default_factory=list, description="Policy categories with coverage"
    )


class CoverageMetadata(BaseModel):
    """Metadata about the coverage analysis process."""

    rules_applied: int = Field(0, description="Count of items matched by rules")
    part_numbers_applied: int = Field(
        0, description="Count of items matched by part number lookup"
    )
    keywords_applied: int = Field(0, description="Count of items matched by keywords")
    llm_calls: int = Field(0, description="Count of LLM calls made")
    processing_time_ms: Optional[float] = Field(
        None, description="Processing time in milliseconds"
    )
    config_version: Optional[str] = Field(
        None, description="Version of coverage config used"
    )


class CoverageAnalysisResult(BaseModel):
    """Complete result of coverage analysis for a claim."""

    schema_version: Literal["coverage_analysis_v1"] = Field(
        "coverage_analysis_v1", description="Schema version identifier"
    )
    claim_id: str = Field(..., description="Claim identifier")
    claim_run_id: Optional[str] = Field(
        None, description="Claim run ID where this analysis is stored"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When analysis was performed"
    )

    # Analysis inputs
    inputs: CoverageInputs = Field(
        default_factory=CoverageInputs,
        description="Input parameters used for analysis",
    )

    # Line item coverage determinations
    line_items: List[LineItemCoverage] = Field(
        default_factory=list, description="Coverage determination for each line item"
    )

    # Summary statistics
    summary: CoverageSummary = Field(
        default_factory=CoverageSummary, description="Summary of coverage analysis"
    )

    # Processing metadata
    metadata: CoverageMetadata = Field(
        default_factory=CoverageMetadata, description="Processing metadata"
    )
