"""Token pricing constants and cost calculation utilities.

Contains hardcoded pricing for common LLM models (per 1M tokens).
Pricing as of January 2025 - update as needed.
"""

from typing import Optional


# Model pricing (USD per 1M tokens) - January 2025
MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI GPT-4o family
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-05-13": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
    # OpenAI GPT-4 Turbo
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-2024-04-09": {"input": 10.00, "output": 30.00},
    "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
    # OpenAI GPT-4
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-0613": {"input": 30.00, "output": 60.00},
    # OpenAI GPT-3.5
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-3.5-turbo-0125": {"input": 0.50, "output": 1.50},
    # Anthropic Claude
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

# Default model for unknown models
DEFAULT_MODEL = "gpt-4o"


def get_model_pricing(model: str) -> dict[str, float]:
    """Get pricing for a model, with fallback to default.

    Args:
        model: Model name/identifier

    Returns:
        Dict with 'input' and 'output' pricing per 1M tokens
    """
    # Try exact match first
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # Try prefix matching for versioned models
    for known_model in MODEL_PRICING:
        if model.startswith(known_model) or known_model.startswith(model):
            return MODEL_PRICING[known_model]

    # Return default pricing
    return MODEL_PRICING[DEFAULT_MODEL]


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing_override: Optional[dict[str, float]] = None,
) -> float:
    """Calculate cost in USD for a single LLM call.

    Args:
        model: Model name/identifier
        prompt_tokens: Number of input/prompt tokens
        completion_tokens: Number of output/completion tokens
        pricing_override: Optional custom pricing dict with 'input' and 'output' keys

    Returns:
        Cost in USD (rounded to 6 decimal places)
    """
    pricing = pricing_override or get_model_pricing(model)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)


def format_cost(cost_usd: float) -> str:
    """Format cost for display.

    Args:
        cost_usd: Cost in USD

    Returns:
        Formatted string (e.g., "$1.23" or "$0.0012")
    """
    if cost_usd >= 0.01:
        return f"${cost_usd:.2f}"
    elif cost_usd >= 0.0001:
        return f"${cost_usd:.4f}"
    else:
        return f"${cost_usd:.6f}"


def format_tokens(tokens: int) -> str:
    """Format token count for display.

    Args:
        tokens: Token count

    Returns:
        Formatted string (e.g., "1.2M", "45.3K", "892")
    """
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    else:
        return str(tokens)
