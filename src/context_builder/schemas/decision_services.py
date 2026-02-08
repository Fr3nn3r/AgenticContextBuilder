"""Pydantic models for external service interfaces used by the decision engine.

These models define the response shapes for pluggable services
(labor rate validation, parts classification) that the decision engine
may call during clause evaluation.  Implementations live in workspace
config (customer-specific), not in core.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LaborRateResult(BaseModel):
    """Response from labor rate validation service."""

    operation: str = Field(description="Operation / repair description")
    flat_rate_hours: Optional[float] = Field(
        default=None,
        description="Standard flat-rate hours for this operation",
    )
    max_hourly_rate: Optional[float] = Field(
        default=None,
        description="Maximum allowed hourly rate (CHF/EUR)",
    )
    is_within_guideline: bool = Field(
        default=True,
        description="Whether the claimed rate/hours are within guidelines",
    )
    excess_amount: float = Field(
        default=0.0,
        description="Amount exceeding guidelines (0 if within)",
    )
    currency: str = Field(default="CHF", description="Currency code")


class PartsClassification(BaseModel):
    """Response from parts classification service."""

    description: str = Field(description="Part description that was classified")
    item_code: Optional[str] = Field(default=None, description="Item/part code")
    is_wear_part: bool = Field(
        default=False,
        description="True if the part is a wear/consumable part",
    )
    is_body_component: bool = Field(
        default=False,
        description="True if the part is a body/chassis component",
    )
    is_consumable: bool = Field(
        default=False,
        description="True if the part is a consumable (oil, coolant, etc.)",
    )
    is_fluid: bool = Field(
        default=False,
        description="True if the part is a fluid (oil, brake fluid, etc.)",
    )
    is_cosmetic: bool = Field(
        default=False,
        description="True if the part is cosmetic (paint, trim, etc.)",
    )
