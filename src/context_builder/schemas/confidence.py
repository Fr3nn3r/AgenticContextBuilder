"""Pydantic models for the Composite Confidence Index (CCI).

The CCI aggregates data-quality signals from every pipeline stage into
a single, traceable confidence score.  It is computed after the Decision
stage and stored both in the Decision Dossier (compact ``ConfidenceIndex``)
and as a standalone ``confidence_summary.json`` (full ``ConfidenceSummary``).
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────


class ConfidenceBand(str, Enum):
    """Qualitative band derived from the composite score."""

    HIGH = "high"          # >= 0.80
    MODERATE = "moderate"  # >= 0.55
    LOW = "low"            # < 0.55


# ── Signal / Component models ────────────────────────────────────────


class SignalSnapshot(BaseModel):
    """A single raw signal collected from an upstream stage."""

    signal_name: str = Field(description="Dotted signal name, e.g. 'extraction.avg_field_confidence'")
    raw_value: Optional[float] = Field(default=None, description="Original value before normalisation")
    normalized_value: float = Field(description="Value mapped to 0-1 range")
    source_stage: str = Field(description="Pipeline stage that produced this signal")
    description: str = Field(default="", description="Human-readable explanation of the signal")


class ComponentScore(BaseModel):
    """One of the five CCI components (weighted sub-score)."""

    component: str = Field(description="Component name, e.g. 'document_quality'")
    score: float = Field(description="Arithmetic mean of signals (0-1)")
    weight: float = Field(description="Configured weight for this component")
    weighted_contribution: float = Field(description="score * weight (before normalisation)")
    signals_used: List[SignalSnapshot] = Field(
        default_factory=list,
        description="Signals that contributed to this component",
    )
    notes: str = Field(default="", description="Extra info (e.g. 'weight redistributed')")


# ── Compact model (embedded in Decision Dossier) ─────────────────────


class ConfidenceIndex(BaseModel):
    """Compact CCI payload embedded in the Decision Dossier."""

    composite_score: float = Field(description="Overall CCI score 0-1")
    band: ConfidenceBand = Field(description="Qualitative band: high / moderate / low")
    components: Dict[str, float] = Field(
        default_factory=dict,
        description="Component name -> score mapping",
    )


# ── Full breakdown (standalone file) ─────────────────────────────────


class ConfidenceSummary(BaseModel):
    """Full CCI breakdown persisted as ``confidence_summary.json``."""

    schema_version: str = Field(default="confidence_summary_v1")
    claim_id: str = Field(description="Claim identifier")
    claim_run_id: str = Field(description="Run that produced this summary")
    composite_score: float = Field(description="Overall CCI score 0-1")
    band: ConfidenceBand = Field(description="Qualitative band")
    component_scores: List[ComponentScore] = Field(
        default_factory=list,
        description="Per-component breakdown",
    )
    weights_used: Dict[str, float] = Field(
        default_factory=dict,
        description="Component -> weight mapping (after redistribution)",
    )
    signals_collected: List[SignalSnapshot] = Field(
        default_factory=list,
        description="All raw signals collected",
    )
    stages_available: List[str] = Field(
        default_factory=list,
        description="Pipeline stages that had data available",
    )
    stages_missing: List[str] = Field(
        default_factory=list,
        description="Pipeline stages with no data",
    )
    flags: List[str] = Field(
        default_factory=list,
        description="Warning flags (e.g. 'extraction data missing')",
    )
