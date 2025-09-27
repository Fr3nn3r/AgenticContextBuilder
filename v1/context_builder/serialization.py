# intake/serialization.py
# Centralized serialization utilities for JSON conversion
# Handles Pydantic models and other complex objects

from typing import Any


def to_jsonable(obj: Any) -> Any:
    """
    Convert Pydantic models and other objects to JSON-serializable format.

    This function recursively processes objects to ensure they can be
    serialized to JSON, handling Pydantic models, dictionaries, and lists.

    Args:
        obj: The object to convert to JSON-serializable format

    Returns:
        A JSON-serializable version of the input object
    """
    if hasattr(obj, 'model_dump'):
        # It's a Pydantic model
        return obj.model_dump()
    elif isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_jsonable(item) for item in obj]
    else:
        return obj