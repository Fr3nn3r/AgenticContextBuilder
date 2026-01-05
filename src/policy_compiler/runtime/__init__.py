"""
Runtime execution components for schema-driven claims processing.

This module implements the 4 core components of the schema-driven architecture:
1. Dynamic Form Generator (UI) - widget_factory, streamlit_app
2. Claim Data Model (Data Layer) - claim_mapper, validators
3. Logic Adaptor (Business Logic) - evaluator
4. Result Interpreter (Presentation) - result_interpreter

Architecture follows SOLID principles:
- OCP: Form generator open for new fields, closed for modification
- ISP: Claim mapper projects only required fields
- DIP: Logic adaptor depends on IEvaluator abstraction
- SRP: Each component has single responsibility
"""

from policy_compiler.runtime.evaluator import IEvaluator, NeuroSymbolicEvaluator
from policy_compiler.runtime.claim_mapper import ClaimMapper, SchemaBasedClaimMapper
from policy_compiler.runtime.result_interpreter import ResultInterpreter
from policy_compiler.runtime.schema_loader import load_schema, load_logic

__all__ = [
    "IEvaluator",
    "NeuroSymbolicEvaluator",
    "ClaimMapper",
    "SchemaBasedClaimMapper",
    "ResultInterpreter",
    "load_schema",
    "load_logic",
]
