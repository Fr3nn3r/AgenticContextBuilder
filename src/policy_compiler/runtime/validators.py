"""
Schema-based validation for claim data.

Strict validation that enforces:
- Type checking (integer, boolean, string, number)
- Enum value validation
- Required field checking
- Clear error messages with field names
"""

from typing import Any, Dict, List


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, field_key: str, message: str):
        self.field_key = field_key
        self.message = message
        super().__init__(f"Validation error for '{field_key}': {message}")


def validate_field_type(field_key: str, value: Any, expected_type: str) -> None:
    """
    Validate that a value matches the expected type.

    Args:
        field_key: The field key (e.g., "claim.incident.attributes.watercraft_length")
        value: The value to validate
        expected_type: Expected type ("integer", "number", "boolean", "string")

    Raises:
        ValidationError: If type doesn't match
    """
    if value is None:
        # None is allowed (represents optional/not filled)
        return

    type_validators = {
        "integer": (int, lambda v: isinstance(v, int) and not isinstance(v, bool)),
        "number": (float, lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)),
        "boolean": (bool, lambda v: isinstance(v, bool)),
        "string": (str, lambda v: isinstance(v, str)),
    }

    if expected_type not in type_validators:
        raise ValidationError(
            field_key,
            f"Unknown type '{expected_type}' (must be integer, number, boolean, or string)"
        )

    expected_class, validator = type_validators[expected_type]

    if not validator(value):
        actual_type = type(value).__name__
        raise ValidationError(
            field_key,
            f"Expected {expected_type}, got {actual_type} (value: {value})"
        )


def validate_enum_value(field_key: str, value: Any, allowed_options: List[str]) -> None:
    """
    Validate that a value is in the allowed enum options.

    Args:
        field_key: The field key
        value: The value to validate
        allowed_options: List of allowed string values

    Raises:
        ValidationError: If value not in allowed options
    """
    if value is None:
        # None is allowed (represents not selected)
        return

    if not isinstance(value, str):
        raise ValidationError(
            field_key,
            f"Enum value must be a string, got {type(value).__name__}"
        )

    if value not in allowed_options:
        raise ValidationError(
            field_key,
            f"Value '{value}' not in allowed options: {', '.join(allowed_options)}"
        )


def validate_required_fields(
    flat_data: Dict[str, Any],
    schema: Dict[str, Any]
) -> List[str]:
    """
    Check that all required fields are present and non-None.

    Args:
        flat_data: Flat key-value dictionary from UI
        schema: Schema dictionary with field definitions

    Returns:
        List of missing required field keys (empty if all present)

    Note: Currently assumes all fields are optional unless explicitly marked required.
    """
    missing_fields = []

    sections = schema.get("sections", {})
    for section_name, section_data in sections.items():
        fields = section_data.get("fields", [])
        for field in fields:
            field_key = field.get("key")
            required = field.get("required", False)

            if required and (field_key not in flat_data or flat_data[field_key] is None):
                missing_fields.append(field_key)

    return missing_fields


def validate_all_fields(
    flat_data: Dict[str, Any],
    schema: Dict[str, Any]
) -> List[ValidationError]:
    """
    Validate all fields in flat_data against the schema.

    This is a comprehensive validation that checks:
    - Type correctness
    - Enum value validity
    - Required fields presence

    Args:
        flat_data: Flat key-value dictionary from UI
        schema: Schema dictionary with field definitions

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []

    # Check required fields
    missing_fields = validate_required_fields(flat_data, schema)
    for field_key in missing_fields:
        errors.append(ValidationError(field_key, "Required field is missing"))

    # Validate each field in flat_data
    field_definitions = {}
    sections = schema.get("sections", {})
    for section_name, section_data in sections.items():
        fields = section_data.get("fields", [])
        for field in fields:
            field_key = field.get("key")
            field_definitions[field_key] = field

    for field_key, value in flat_data.items():
        if value is None:
            continue  # Skip None values (optional fields)

        field_def = field_definitions.get(field_key)
        if not field_def:
            # Field not in schema - this is okay, might be extra data
            continue

        field_type = field_def.get("type")

        try:
            # Type validation
            if field_type in ("integer", "number", "boolean", "string"):
                validate_field_type(field_key, value, field_type)

            # Enum validation
            if field_type == "enum":
                options = field_def.get("options", [])
                validate_enum_value(field_key, value, options)

        except ValidationError as e:
            errors.append(e)

    return errors
