"""Tenant configuration schema and loader.

This module provides tenant-specific configuration that can override
default behavior per workspace. Configuration is loaded from
{workspace}/config/tenant.yaml.

Currently used for validation only; runtime hooks may be added in future phases.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from context_builder.storage.workspace_paths import get_workspace_config_dir

logger = logging.getLogger(__name__)

# Valid ingestion provider names
VALID_INGESTION_PROVIDERS = {"azure-di", "openai", "tesseract"}


class IngestionRouteRule(BaseModel):
    """Rule for routing documents to specific ingestion providers based on filename.

    Attributes:
        pattern: Regex pattern to match against the filename (not full path).
        provider: Ingestion provider name (azure-di, openai, tesseract).
        description: Optional human-readable description of the rule.
    """

    pattern: str = Field(
        ...,
        description="Regex pattern to match against filename",
        min_length=1,
    )
    provider: str = Field(
        ...,
        description="Ingestion provider name (azure-di, openai, tesseract)",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the rule",
    )

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that provider is a known ingestion provider."""
        if v not in VALID_INGESTION_PROVIDERS:
            raise ValueError(
                f"Unknown provider '{v}'. Valid providers: {sorted(VALID_INGESTION_PROVIDERS)}"
            )
        return v

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """Validate that pattern is a valid regex."""
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{v}': {e}")
        return v


class TenantConfig(BaseModel):
    """Tenant-specific configuration schema.

    Loaded from {workspace}/config/tenant.yaml to provide tenant-scoped
    settings that override repo defaults.

    Attributes:
        tenant_id: Unique identifier for this tenant/workspace.
        tenant_name: Human-readable name for the tenant.
        feature_flags: Feature toggles for enabling/disabling functionality.
        allowed_ingestion_providers: List of allowed ingestion providers (phase 2).
        metadata: Additional tenant metadata for audit/tracking.
    """

    tenant_id: str = Field(
        ...,
        description="Unique identifier for this tenant/workspace",
        min_length=1,
    )
    tenant_name: Optional[str] = Field(
        default=None,
        description="Human-readable name for the tenant",
    )
    feature_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Feature toggles for enabling/disabling functionality",
    )
    allowed_ingestion_providers: List[str] = Field(
        default_factory=list,
        description="List of allowed ingestion providers (enforced in phase 2)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional tenant metadata for audit/tracking",
    )
    ingestion_routes: List[IngestionRouteRule] = Field(
        default_factory=list,
        description="Ordered list of regex rules for routing files to ingestion providers",
    )

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate tenant_id format."""
        # Allow alphanumeric, hyphens, underscores
        import re
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "tenant_id must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v

    def is_feature_enabled(self, feature_name: str, default: bool = False) -> bool:
        """Check if a feature flag is enabled.

        Args:
            feature_name: Name of the feature to check.
            default: Default value if feature not specified.

        Returns:
            True if feature is enabled, False otherwise.
        """
        return self.feature_flags.get(feature_name, default)

    def is_provider_allowed(self, provider: str) -> bool:
        """Check if an ingestion provider is allowed.

        Args:
            provider: Name of the provider to check.

        Returns:
            True if provider is allowed or no restrictions set.
        """
        # If no providers specified, all are allowed
        if not self.allowed_ingestion_providers:
            return True
        return provider in self.allowed_ingestion_providers

    def get_provider_for_filename(self, filename: str) -> Optional[str]:
        """Get the ingestion provider for a filename based on routing rules.

        Evaluates ingestion_routes in order and returns the provider for
        the first matching pattern. Returns None if no pattern matches,
        indicating default extension-based routing should be used.

        Args:
            filename: The filename (not full path) to match against patterns.

        Returns:
            Provider name if a pattern matches, None otherwise.
        """
        for rule in self.ingestion_routes:
            if re.match(rule.pattern, filename):
                logger.debug(
                    f"Filename '{filename}' matched pattern '{rule.pattern}' -> {rule.provider}"
                )
                return rule.provider
        return None


def load_tenant_config(config_path: Optional[Path] = None) -> Optional[TenantConfig]:
    """Load tenant configuration from YAML file.

    Args:
        config_path: Optional explicit path to tenant.yaml.
            If not provided, uses {workspace}/config/tenant.yaml.

    Returns:
        TenantConfig if file exists and is valid, None otherwise.

    Raises:
        ValueError: If file exists but contains invalid configuration.
    """
    if config_path is None:
        workspace_config = get_workspace_config_dir()
        config_path = workspace_config / "tenant.yaml"

    if not config_path.exists():
        logger.debug(f"No tenant config found at {config_path}")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            logger.warning(f"Empty tenant config at {config_path}")
            return None

        config = TenantConfig.model_validate(data)
        logger.debug(f"Loaded tenant config for {config.tenant_id} from {config_path}")
        return config

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in tenant config {config_path}: {e}")
    except Exception as e:
        raise ValueError(f"Failed to load tenant config from {config_path}: {e}")


# Cached tenant config (loaded once per session)
_cached_config: Optional[TenantConfig] = None
_cache_initialized: bool = False


def get_tenant_config(force_reload: bool = False) -> Optional[TenantConfig]:
    """Get the current tenant configuration (cached).

    Args:
        force_reload: If True, reload from disk even if cached.

    Returns:
        TenantConfig if available, None otherwise.
    """
    global _cached_config, _cache_initialized

    if force_reload or not _cache_initialized:
        _cached_config = load_tenant_config()
        _cache_initialized = True

    return _cached_config


def reset_tenant_config_cache() -> None:
    """Reset the tenant config cache.

    Call this after workspace switch to ensure fresh config lookup.
    """
    global _cached_config, _cache_initialized
    _cached_config = None
    _cache_initialized = False
