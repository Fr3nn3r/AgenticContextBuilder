"""
Pydantic schema for policy logic extraction with normalized recursive structure.

This schema uses a normalized format with fixed 'op' and 'args' fields instead of
dynamic keys, preventing hallucinated operators and enabling strict validation.
The chain-of-thought pattern forces reasoning before logic generation.
"""

from __future__ import annotations
from typing import List, Union
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class LogicOp(str, Enum):
    """Enumeration of all allowed JSON Logic operators."""

    AND = "and"
    OR = "or"
    NOT = "!"
    IF = "if"
    EQ = "=="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    VAR = "var"
    IN = "in"
    ADD = "+"
    SUB = "-"
    MULT = "*"
    DIV = "/"


class LogicNode(BaseModel):
    """
    Normalized recursive node for JSON Logic trees.

    Uses fixed 'op' and 'args' fields instead of dynamic keys like {"==": [...]}
    to prevent hallucinated operators and enable strict schema validation.
    """

    model_config = ConfigDict(extra="forbid")

    # Note: No description on enum field to avoid $ref + description conflict in OpenAI strict mode
    op: LogicOp = Field(...)
    args: List[Union[LogicNode, str, int, float, bool, None]] = Field(
        ...,
        description="List of arguments. Can be primitive values or nested LogicNode instances."
    )


class RuleDefinition(BaseModel):
    """A single extracted policy rule with normalized logic representation."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Unique identifier for the rule (e.g., 'rule_001', 'coverage_jewelry')"
    )
    description: str = Field(
        ...,
        description="Human-readable summary of what the rule does"
    )
    source_ref: str = Field(
        ...,
        description="Reference to paragraph/section where the rule was found"
    )
    # Note: No description on LogicNode field to avoid $ref + description conflict in OpenAI strict mode
    logic: LogicNode = Field(...)


class PolicyAnalysis(BaseModel):
    """
    Complete policy logic extraction with enforced chain-of-thought reasoning.

    CRITICAL ORDERING: The chain_of_thought field comes FIRST to force the model
    to reason through the logic before generating the formal logic trees.
    This significantly improves the quality and accuracy of extracted logic.
    """

    model_config = ConfigDict(extra="forbid")

    # FIRST: Chain of thought - forces reasoning before logic generation
    chain_of_thought: str = Field(
        ...,
        description=(
            "Step-by-step legal analysis of the policy text. "
            "Break down each clause by identifying: "
            "1) Triggers (what events activate the rule), "
            "2) Conditions (what must be true), "
            "3) Actions (what happens), "
            "4) Limits (caps or constraints), "
            "5) Exclusions (what invalidates the rule). "
            "This reasoning must happen BEFORE generating the normalized logic."
        )
    )

    # SECOND: The extracted logic rules
    rules: List[RuleDefinition] = Field(
        ...,
        description=(
            "List of policy rules extracted as normalized logic trees. "
            "Each rule represents a distinct logical statement from the policy. "
            "Uses LogicOp enum for operators and nested LogicNode structure. "
            "Variables use prefixes: 'claim.' for dynamic facts, 'policy.' for static values."
        )
    )
