# intake/services/models.py
# Models for shared services

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from ..exceptions import IntakeError


class PromptVersionConfig(BaseModel):
    """Configuration metadata for a prompt loaded from file."""
    template: str = Field(..., description="The prompt template text")
    model: str = Field(default="gpt-4o", description="AI model to use for this prompt")
    max_tokens: int = Field(default=2048, description="Maximum tokens for response")
    temperature: float = Field(default=0.1, description="Temperature for response generation")
    description: Optional[str] = Field(None, description="Human-readable description of prompt purpose")
    output_format: Optional[str] = Field(None, description="Expected output format: 'json' or 'text' (default)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional model parameters")


class PromptError(IntakeError):
    """Exception for prompt-related errors."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, error_type="prompt_error", original_error=original_error)