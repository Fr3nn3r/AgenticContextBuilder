"""Regression tests for compliance storage.

These tests ensure backward compatibility is maintained when refactoring
or adding new storage backends. They verify that:

1. Facade APIs remain unchanged (DecisionLedger, LLMAuditService)
2. Existing JSONL files remain readable after code changes
3. Public interfaces work as documented
"""
