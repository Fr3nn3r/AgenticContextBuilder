"""
Policy Compiler - Schema generation and claims processing runtime

This package provides:
- execution: Form schema generation from policy logic
- runtime: Dynamic claims UI and rule execution engine

The policy_compiler consumes JSON outputs from context_builder pipeline
and generates executable claim processing applications.
"""

__version__ = "0.1.0"

# Export commonly used classes for convenience
from policy_compiler.execution.form_generator import FormGenerator
from policy_compiler.runtime import (
    load_schema,
    load_logic,
    SchemaBasedClaimMapper,
    NeuroSymbolicEvaluator,
    ResultInterpreter
)

__all__ = [
    "FormGenerator",
    "load_schema",
    "load_logic",
    "SchemaBasedClaimMapper",
    "NeuroSymbolicEvaluator",
    "ResultInterpreter",
]
