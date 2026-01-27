"""
Centralized OpenAI client factory.

This module provides a factory function for creating OpenAI clients that
automatically uses Azure OpenAI when credentials are available.

Environment variables:
    # Azure OpenAI (preferred when available)
    AZURE_OPENAI_API_KEY      - Azure OpenAI API key
    AZURE_OPENAI_BASE_URL     - Azure OpenAI endpoint (e.g., https://xxx.openai.azure.com/openai/v1/)
    AZURE_OPENAI_ENDPOINT     - Alternative to BASE_URL (e.g., https://xxx.openai.azure.com/)
    AZURE_OPENAI_API_VERSION  - API version (default: 2024-02-15-preview)
    AZURE_OPENAI_DEPLOYMENT   - Default deployment name (default: gpt-4o)

    # Standard OpenAI (fallback)
    OPENAI_API_KEY            - OpenAI API key
"""

import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Default values
DEFAULT_API_VERSION = "2024-02-15-preview"
DEFAULT_DEPLOYMENT = "gpt-4o"


def _get_azure_endpoint() -> Optional[str]:
    """Get and normalize the Azure OpenAI endpoint."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_OPENAI_BASE_URL")
    if not endpoint:
        return None

    # Strip trailing slashes and /openai/v1 suffix if present
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/openai/v1"):
        endpoint = endpoint[: -len("/openai/v1")]
    elif endpoint.endswith("/openai"):
        endpoint = endpoint[: -len("/openai")]

    return endpoint


def is_azure_openai_configured() -> bool:
    """Check if Azure OpenAI credentials are configured."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = _get_azure_endpoint()
    return bool(api_key and endpoint)


def get_openai_client(api_key: Optional[str] = None):
    """
    Create an OpenAI client, using Azure OpenAI if configured.

    Args:
        api_key: Optional API key override. If not provided, uses environment variables.

    Returns:
        OpenAI or AzureOpenAI client instance.

    Raises:
        ValueError: If no valid credentials are found.
    """
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = _get_azure_endpoint()
    azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)

    # Use Azure OpenAI if credentials are available
    if azure_api_key and azure_endpoint:
        from openai import AzureOpenAI

        logger.debug(f"Creating AzureOpenAI client with endpoint: {azure_endpoint[:30]}...")
        return AzureOpenAI(
            api_key=azure_api_key,
            api_version=azure_api_version,
            azure_endpoint=azure_endpoint,
        )

    # Fall back to standard OpenAI
    standard_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if standard_api_key:
        from openai import OpenAI

        logger.debug("Creating standard OpenAI client")
        return OpenAI(api_key=standard_api_key)

    raise ValueError(
        "No OpenAI credentials found. Set either:\n"
        "  - AZURE_OPENAI_API_KEY + AZURE_OPENAI_BASE_URL (for Azure OpenAI)\n"
        "  - OPENAI_API_KEY (for standard OpenAI)"
    )


def get_default_model() -> str:
    """
    Get the default model/deployment name to use.

    For Azure OpenAI, returns the deployment name.
    For standard OpenAI, returns the model name.
    """
    if is_azure_openai_configured():
        return os.getenv("AZURE_OPENAI_DEPLOYMENT", DEFAULT_DEPLOYMENT)
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_client_and_model(
    api_key: Optional[str] = None, model: Optional[str] = None
) -> Tuple:
    """
    Get both client and appropriate model name.

    This is a convenience function that returns a properly configured
    client along with the model/deployment name to use.

    Args:
        api_key: Optional API key override.
        model: Optional model name override. If not provided, uses default.

    Returns:
        Tuple of (client, model_name)
    """
    client = get_openai_client(api_key)
    model_name = model or get_default_model()
    return client, model_name
