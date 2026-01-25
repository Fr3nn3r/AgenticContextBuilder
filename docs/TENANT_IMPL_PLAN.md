# Tenant Configuration Management

## Overview

Tenant-scoped configuration allows workspace-specific prompts, extraction specs, and settings to override repo defaults. This enables multi-tenant deployments where each tenant can customize behavior without modifying shared code.

## Goals

- Keep one API instance per tenant while sharing the codebase
- Isolate tenant-specific prompts, extraction specs, and settings
- Make configuration changes deployable by swapping a workspace path
- Preserve compliance traceability by snapshotting config per run

## Directory Layout (per workspace)

```
workspaces/{tenant_id}/
  claims/                           # Document storage
  runs/                             # Pipeline run outputs
    {run_id}/
      config_snapshot/              # Full config copy per run
      manifest.json                 # Includes workspace_config_hash
  logs/                             # Compliance logs
  registry/                         # Indexes
  config/                           # Tenant configuration (NEW)
    tenant.yaml                     # Tenant metadata and feature flags
    prompts/                        # Prompt overrides
      claims_document_classification.md
      generic_extraction.md
    extraction_specs/               # Spec overrides
      doc_type_catalog.yaml
      {doc_type}.yaml
    ingestion/                      # (Phase 2)
      providers.yaml
```

## Configuration Precedence

1. **Workspace config** (`{workspace}/config/...`) — tenant overrides
2. **Repo defaults** (`src/context_builder/...`) — fallback

## Implementation Details

### 1. Workspace Config Path Helper

**File:** `src/context_builder/storage/workspace_paths.py`

```python
def get_workspace_config_dir() -> Path:
    """Get the config directory for the active workspace.
    Returns {workspace}/config or output/config as fallback.
    """
```

### 2. Prompt Override Mechanism

**File:** `src/context_builder/utils/prompt_loader.py`

- `_resolve_prompt_path(prompt_name)` checks workspace first, then repo
- Logs which path is used at DEBUG level
- Supports all existing prompt features (frontmatter, Jinja2 templates)

**Override path:** `{workspace}/config/prompts/{name}.md`
**Fallback path:** `src/context_builder/prompts/{name}.md`

### 3. Extraction Specs Override

**File:** `src/context_builder/extraction/spec_loader.py`

- `_resolve_spec_path(doc_type)` checks workspace first, then repo
- `list_available_specs()` returns union of both locations
- Supports both new format (`{doc_type}.yaml`) and legacy format (`{doc_type}_v0.yaml`)

**Override path:** `{workspace}/config/extraction_specs/{doc_type}.yaml`
**Fallback path:** `src/context_builder/extraction/specs/{doc_type}.yaml`

### 4. Doc Type Catalog Override

**File:** `src/context_builder/classification/openai_classifier.py`

- `_resolve_catalog_path()` checks workspace first, then repo
- Catalog is loaded once at classifier initialization

**Override path:** `{workspace}/config/extraction_specs/doc_type_catalog.yaml`
**Fallback path:** `src/context_builder/extraction/specs/doc_type_catalog.yaml`

### 5. Tenant Config Schema

**File:** `src/context_builder/config/tenant.py`

```python
class TenantConfig(BaseModel):
    tenant_id: str                              # Required, validated format
    tenant_name: str | None                     # Human-readable name
    feature_flags: dict[str, bool]              # Feature toggles
    allowed_ingestion_providers: list[str]      # Phase 2
    metadata: dict[str, Any]                    # Audit/tracking data
```

**Helper functions:**
- `load_tenant_config(path)` — Load from YAML file
- `get_tenant_config()` — Cached loader (call `reset_tenant_config_cache()` on workspace switch)
- `is_feature_enabled(name, default)` — Check feature flag
- `is_provider_allowed(provider)` — Check provider allowlist (phase 2)

**Example `tenant.yaml`:**
```yaml
tenant_id: acme-insurance
tenant_name: ACME Insurance Corp
feature_flags:
  pii_enabled: true
  strict_quality_gate: false
allowed_ingestion_providers:
  - azure-di
  - openai
metadata:
  region: us-west
  contract_tier: enterprise
```

### 6. Compliance Traceability

**File:** `src/context_builder/pipeline/run.py`

**Config Hash:**
- `_compute_workspace_config_hash()` computes SHA-256 over all files in `{workspace}/config/**`
- Hash includes relative paths + file contents for structure awareness
- Stored as `workspace_config_hash` in `manifest.json`

**Config Snapshot:**
- `_snapshot_workspace_config(run_paths)` copies entire config directory
- Stored at `runs/{run_id}/config_snapshot/`
- Enables exact reproduction of any historical run

**Manifest additions:**
```json
{
  "workspace_config_hash": "abc123...",
  "version_bundle_id": "vb_xyz789"
}
```

## Deployment Model

1. Each tenant runs one API process pointing to a tenant workspace
2. Set active workspace via:
   - `active_workspace_id` in `.contextbuilder/workspaces.json`
   - Or `RENDER_WORKSPACE_PATH` environment variable
3. Deploy config changes by updating files under `{workspace}/config/`

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Config snapshot | Full snapshot per run | Enables exact reproduction for compliance audits |
| Model override | Not supported | Models are specified in prompt frontmatter, keeping config simpler |
| Ingestion providers | Deferred to phase 2 | Core override mechanism needed first |

## Testing

**Test file:** `tests/unit/test_workspace_config_overrides.py`

| Test Class | Coverage |
|------------|----------|
| `TestPromptLoaderOverride` | Workspace override, repo fallback |
| `TestSpecLoaderOverride` | Workspace override, repo fallback, union listing |
| `TestCatalogOverride` | Workspace override, repo fallback |
| `TestTenantConfig` | Schema validation, loading, caching |
| `TestWorkspaceConfigHash` | Hash computation, determinism |
| `TestWorkspaceConfigSnapshot` | Snapshot creation |

**Run tests:**
```bash
python -m pytest tests/unit/test_workspace_config_overrides.py -v
```

## Future Work (Phase 2)

- [ ] Ingestion provider routing via `providers.yaml`
- [ ] Runtime hooks for tenant config (e.g., enforce quality gate settings)
- [ ] Admin UI for tenant config management
- [ ] Config validation on workspace activation
