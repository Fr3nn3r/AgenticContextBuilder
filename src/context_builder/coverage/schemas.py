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

    # Exclusion reason (populated by rule engine / analyzer for NOT_COVERED items)
    exclusion_reason: Optional[str] = Field(
        None, description="Reason key for non-coverage (e.g. 'fee', 'consumable', 'component_excluded')"
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
    total_covered_gross: float = Field(
        0.0,
        description="Sum of covered item prices at 100% (before coverage_percent)",
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
    coverage_percent_missing: bool = Field(
        False, description="True when coverage_percent could not be determined"
    )


class CoverageInputs(BaseModel):
    """Input parameters used for coverage analysis."""

    vehicle_km: Optional[int] = Field(None, description="Vehicle odometer reading in km")
    vehicle_age_years: Optional[float] = Field(
        None, description="Vehicle age in years (from first registration to claim date)"
    )
    coverage_percent: Optional[float] = Field(
        None, description="Coverage percentage from mileage scale"
    )
    coverage_percent_effective: Optional[float] = Field(
        None, description="Effective coverage percent after age adjustment"
    )
    age_threshold_years: Optional[int] = Field(
        None, description="Age threshold from policy (e.g., 8 from 'Dès 8 ans'). None if policy has no age rule."
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


class PrimaryRepairResult(BaseModel):
    """Result of primary repair component determination.

    Identifies the main component being repaired, used by the screener
    to decide coverage verdict. Determined via a three-tier approach:
    1. Deterministic: highest-value covered parts item
    2. Repair context: labor-derived primary component
    3. LLM fallback: focused LLM call (when tiers 1-2 fail)
    """

    component: Optional[str] = Field(None, description="Component type (e.g., 'timing_chain')")
    category: Optional[str] = Field(None, description="Coverage category (e.g., 'engine')")
    description: Optional[str] = Field(None, description="Original item description")
    is_covered: Optional[bool] = Field(None, description="Whether the component is covered by policy")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Confidence in the determination")
    determination_method: str = Field(
        "none", description="How primary was determined: 'deterministic', 'repair_context', 'llm', 'none'"
    )
    source_item_index: Optional[int] = Field(
        None, description="Index of the source line item (for deterministic method)"
    )


class NonCoveredExplanation(BaseModel):
    """Adjuster-ready explanation for a group of non-covered items."""

    exclusion_reason: str = Field(
        ..., description="Reason string (from rule config or analyzer)"
    )
    items: List[str] = Field(
        default_factory=list, description="Item descriptions in this group"
    )
    item_codes: List[Optional[str]] = Field(
        default_factory=list, description="Item codes (parallel to items)"
    )
    category: Optional[str] = Field(
        None, description="Coverage category (if sub-grouped by category)"
    )
    total_amount: float = Field(
        0.0, description="Sum of not_covered_amount in this group"
    )
    explanation: str = Field(
        ..., description="Adjuster-ready explanation text"
    )
    policy_reference: Optional[str] = Field(
        None, description="Policy clause reference"
    )
    match_confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Minimum confidence in this group"
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

    # Primary repair determination
    primary_repair: Optional[PrimaryRepairResult] = Field(
        None, description="Primary repair component determination result"
    )

    # Non-covered explanations (post-processing)
    non_covered_explanations: Optional[List[NonCoveredExplanation]] = Field(
        None, description="Grouped explanations for non-covered items"
    )
    non_covered_summary: Optional[str] = Field(
        None, description="Summary string of non-covered items"
    )

    # Processing metadata
    metadata: CoverageMetadata = Field(
        default_factory=CoverageMetadata, description="Processing metadata"
    )
