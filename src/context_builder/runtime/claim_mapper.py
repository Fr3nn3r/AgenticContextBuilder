"""
Claim Data Model - Component 2 of the schema-driven architecture.

Primary Responsibility: "Inflation"
Takes flat key-value pairs from the UI and inflates them into the deep JSON
structure required by the logic engine.

SOLID Principle: Interface Segregation Principle (ISP)
The engine requires a specific shape of data. We don't force the engine to parse
our entire internal database object - we project only what the policy asks for.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import re

from context_builder.runtime.validators import validate_all_fields, ValidationError


class ClaimMapper(ABC):
    """
    Abstract interface for claim data mapping.

    Defines the contract for transforming flat UI data into nested engine data.
    """

    @abstractmethod
    def inflate(self, flat_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inflate flat key-value pairs into nested JSON structure.

        Args:
            flat_data: Flat dictionary from UI (e.g., {"claim.header.claim_type": "liability"})
            schema: Schema dictionary defining the structure

        Returns:
            Nested dictionary (e.g., {"claim": {"header": {"claim_type": "liability"}}})
        """
        pass

    @abstractmethod
    def validate(self, flat_data: Dict[str, Any], schema: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate flat data against schema.

        Args:
            flat_data: Flat dictionary from UI
            schema: Schema dictionary

        Returns:
            List of validation errors (empty if valid)
        """
        pass


class SchemaBasedClaimMapper(ClaimMapper):
    """
    Concrete implementation of ClaimMapper.

    Inflates flat data using dot-notation keys and array bracket notation.

    Examples:
        "claim.header.claim_type" -> {"claim": {"header": {"claim_type": ...}}}
        "claim.parties.claimants[0].role" -> {"claim": {"parties": {"claimants": [{"role": ...}]}}}
    """

    def validate(self, flat_data: Dict[str, Any], schema: Dict[str, Any]) -> List[ValidationError]:
        """
        Validate flat data against schema using validators module.

        Args:
            flat_data: Flat dictionary from UI
            schema: Schema dictionary

        Returns:
            List of validation errors (empty if valid)
        """
        return validate_all_fields(flat_data, schema)

    def inflate(self, flat_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inflate flat key-value pairs into nested structure.

        Algorithm:
        1. Parse each key using dot notation (e.g., "claim.header.claim_type")
        2. Handle array indices (e.g., "claim.parties.claimants[0].role")
        3. Build nested dictionaries and arrays
        4. Return fully inflated structure

        Args:
            flat_data: Flat dictionary from UI
            schema: Schema dictionary (used for reference, not transformation)

        Returns:
            Nested dictionary matching the structure required by logic engine
        """
        result = {}

        for flat_key, value in flat_data.items():
            if value is None:
                # Skip None values (optional fields not filled)
                continue

            self._set_nested_value(result, flat_key, value)

        return result

    def _set_nested_value(self, target: Dict[str, Any], flat_key: str, value: Any) -> None:
        """
        Set a value in nested dictionary using dot-notation key.

        Handles both object notation (dots) and array notation (brackets).

        Examples:
            "claim.header.claim_type" -> target["claim"]["header"]["claim_type"] = value
            "claim.parties.claimants[0].role" -> target["claim"]["parties"]["claimants"][0]["role"] = value

        Args:
            target: Dictionary to modify (mutated in place)
            flat_key: Dot-notation key with optional array indices
            value: Value to set
        """
        # Parse the key into segments
        segments = self._parse_key(flat_key)

        # Navigate/create nested structure
        current = target
        for i, segment in enumerate(segments[:-1]):  # All but last segment
            if isinstance(segment, int):
                # Array index
                if not isinstance(current, list):
                    raise ValueError(f"Expected array at segment {i} of key '{flat_key}', got {type(current)}")

                # Extend array if needed
                while len(current) <= segment:
                    current.append({})

                current = current[segment]
            else:
                # Object key
                if segment not in current:
                    # Peek at next segment to decide if we need a list or dict
                    next_segment = segments[i + 1]
                    if isinstance(next_segment, int):
                        current[segment] = []
                    else:
                        current[segment] = {}

                current = current[segment]

        # Set the final value
        last_segment = segments[-1]
        if isinstance(last_segment, int):
            if not isinstance(current, list):
                raise ValueError(f"Expected array for final segment of key '{flat_key}', got {type(current)}")
            while len(current) <= last_segment:
                current.append(None)
            current[last_segment] = value
        else:
            current[last_segment] = value

    def _parse_key(self, flat_key: str) -> List[str | int]:
        """
        Parse a flat key into segments.

        Examples:
            "claim.header.claim_type" -> ["claim", "header", "claim_type"]
            "claim.parties.claimants[0].role" -> ["claim", "parties", "claimants", 0, "role"]
            "claim.parties.claimants[2].attributes.is_driver" ->
                ["claim", "parties", "claimants", 2, "attributes", "is_driver"]

        Args:
            flat_key: Dot-notation key with optional array indices

        Returns:
            List of segments (strings for keys, integers for array indices)
        """
        segments = []

        # Split by dots, but preserve array notation
        parts = flat_key.split(".")

        for part in parts:
            # Check if part contains array notation: "claimants[0]"
            match = re.match(r"^([^\[]+)\[(\d+)\]$", part)
            if match:
                key_name = match.group(1)
                index = int(match.group(2))
                segments.append(key_name)
                segments.append(index)
            else:
                segments.append(part)

        return segments
