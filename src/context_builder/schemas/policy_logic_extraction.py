"""
Pydantic schema for policy logic extraction - Phase 1 (v2.0)
Updated for 'Assignment Logic' and 'Micro-Chain-of-Thought'.
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
    # Special operator for flagging ambiguous terms requiring human review
    HUMAN_FLAG = "human_flag"


class RuleType(str, Enum):
    """Categorizes the intent of the rule for downstream processing."""

    LIMIT = "limit"  # Returns a number (the limit amount)
    DEDUCTIBLE = "deductible"  # Returns a number (the deductible amount)
    EXCLUSION = "exclusion"  # Returns a boolean (True = excluded)
    CONDITION = "condition"  # Returns a boolean (True = condition met)
    CALCULATION = "calculation"  # Returns a number (complex math)


class LogicNode(BaseModel):
    """
    Normalized recursive node for JSON Logic trees.

    CRITICAL:
    - For 'LIMIT' or 'DEDUCTIBLE' rules, the logic must RETURN A VALUE (Number), not a Boolean.
    - Use 'if' operators to assign values based on conditions.
    """

    model_config = ConfigDict(extra="forbid")

    op: LogicOp = Field(...)
    args: List[Union[LogicNode, str, int, float, bool, None]] = Field(
        ...,
        description=(
            "Arguments for the operator. "
            "Variables MUST use the Standard UDM paths (e.g., 'claim.loss.cause_primary', 'policy.limit.flood')."
        ),
    )


class RuleDefinition(BaseModel):
    """
    A single extracted policy rule with Micro-CoT reasoning.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Unique identifier (e.g., 'rule_flood_limit', 'exclusion_war').",
    )
    name: str = Field(..., description="Short, human-readable name for the rule.")
    type: RuleType = Field(...)
    # Micro-CoT: Reasoning stays with the rule
    reasoning: str = Field(
        ...,
        description=(
            "Micro-Chain-of-Thought: Explain WHY you constructed the logic this way. "
            "Identify the specific text triggers and why you chose specific UDM variables. "
            "Explain how the logic handles assignment (e.g., 'If Cause is Flood, return 10M')."
        ),
    )
    source_ref: str = Field(
        ...,
        description="Verbatim or near-verbatim quote from the text that justifies this rule.",
    )
    logic: LogicNode = Field(...)


class PolicyAnalysis(BaseModel):
    """
    Container for the extraction output.
    Note: Global CoT is removed in favor of Rule-level 'reasoning'.
    """

    model_config = ConfigDict(extra="forbid")

    rules: List[RuleDefinition] = Field(
        ...,
        description="List of extracted rules, each with its own reasoning and logic.",
    )
