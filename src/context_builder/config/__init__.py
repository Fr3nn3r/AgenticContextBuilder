"""Tenant configuration management."""

from context_builder.config.tenant import (
    TenantConfig,
    load_tenant_config,
    get_tenant_config,
)

__all__ = [
    "TenantConfig",
    "load_tenant_config",
    "get_tenant_config",
]
