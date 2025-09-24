# intake/exceptions.py
# Base exception classes for the intake system

from typing import Optional


class IntakeError(Exception):
    """Base exception class for all intake-related errors."""

    def __init__(self, message: str, error_type: str = "intake_error", original_error: Optional[Exception] = None):
        """
        Initialize the IntakeError.

        Args:
            message: Error message
            error_type: Type of error for categorization
            original_error: Original exception if this is a wrapped error
        """
        self.message = message
        self.error_type = error_type
        self.original_error = original_error
        super().__init__(self.message)