"""
Pydantic schema for policy symbol extraction.

This schema models the output of the Symbol Table Extractor prompt,
which extracts defined terms and explicit variables from insurance contracts.
"""

from typing import List
from pydantic import BaseModel, ConfigDict, Field


class DefinedTerm(BaseModel):
    """A term with a specific legal definition in the insurance contract."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(
        ..., description="The term name (e.g., 'Bodily Injury')"
    )
    definition_verbatim: str = Field(
        ..., description="The exact text defining the term"
    )
    simplified_meaning: str = Field(
        ..., description="A short, 1-sentence summary of the definition for quick reference"
    )
    scope: str = Field(
        ..., description="'Global' or specific section name where the term applies"
    )
    source_ref: str = Field(
        ..., description="Header or ID where the definition was found"
    )


class ExplicitVariable(BaseModel):
    """A hardcoded variable (limit, sub-limit, deductible) from the contract."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., description="Variable name (e.g., 'Jewelry Sub-limit')"
    )
    value: str = Field(
        ..., description="The value (e.g., '5,000')"
    )
    unit: str = Field(
        ..., description="Currency or unit (e.g., 'CHF', 'Days')"
    )
    context: str = Field(
        ..., description="Brief context (e.g., 'Per occurrence')"
    )


class PolicySymbolExtraction(BaseModel):
    """Complete symbol table extraction from an insurance contract."""

    model_config = ConfigDict(extra="forbid")

    defined_terms: List[DefinedTerm] = Field(
        ...,
        description="List of terms with specific legal definitions"
    )
    explicit_variables: List[ExplicitVariable] = Field(
        ...,
        description="List of hardcoded variables (limits, deductibles, etc.)"
    )
