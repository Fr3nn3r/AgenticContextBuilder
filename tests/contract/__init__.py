"""Contract tests for compliance storage backends.

Contract tests define the behavior that all implementations of a protocol
must satisfy. They are abstract test classes that are inherited by
concrete test classes for each backend implementation.

This pattern ensures:
- All backends behave consistently
- New backends are automatically tested against the contract
- Behavioral changes are detected across all implementations

Usage:
    from tests.contract import DecisionStorageContractTests

    class TestFileDecisionContract(DecisionStorageContractTests):
        def create_storage(self, tmp_path):
            return FileDecisionStorage(tmp_path)

The test classes use pytest fixtures and are designed to be inherited.
Each subclass must implement the `create_storage` method to provide
the specific backend being tested.
"""

from tests.contract.decision_storage_contract import DecisionStorageContractTests
from tests.contract.llm_storage_contract import LLMCallStorageContractTests

__all__ = [
    "DecisionStorageContractTests",
    "LLMCallStorageContractTests",
]
