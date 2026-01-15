# Fix Hardcoded Paths - Workspace-Aware Storage

## Problem

Multiple services in `main.py` use hardcoded paths like `_PROJECT_ROOT / "output" / "config"` and `_PROJECT_ROOT / "output" / "logs"`, ignoring the active workspace. This causes files to be created in the wrong location.

## Affected Services

| Service | Current Path | Line |
|---------|--------------|------|
| `PromptConfigService` | `output/config` | 221 |
| `AuditService` | `output/config` | 234 |
| `UsersService` | `output/config` | 247 |
| `AuthService` | `output/config` | 260 |
| `ComplianceStorageConfig` | `output/logs` | 286 |

## Design Decision: Global vs Workspace-Scoped

**Global (`.contextbuilder/`)** - Shared across all workspaces:
- Users & authentication (users.json, sessions/)
- Audit logs (audit.json) - tracks all activity across workspaces

**Workspace-Scoped (`{workspace}/`)** - Per-workspace:
- Compliance logs (decisions, LLM calls)
- Pipeline prompt configs
- Claims data (already correct)

## Implementation Plan

### Step 1: Add helper function for config paths

Add a function that returns the appropriate config directory based on scope:

```python
def _get_global_config_dir() -> Path:
    """Get global config directory (.contextbuilder/)."""
    return _PROJECT_ROOT / ".contextbuilder"

def _get_workspace_config_dir() -> Path:
    """Get workspace-scoped config directory."""
    # DATA_DIR is {workspace}/claims, so parent is workspace root
    return DATA_DIR.parent / "config"
```

### Step 2: Update global services (users, auth, audit)

Change these to use `.contextbuilder/`:

```python
def get_users_service() -> UsersService:
    global _users_service
    if _users_service is None:
        config_dir = _get_global_config_dir()
        _users_service = UsersService(config_dir)
    return _users_service
```

Same pattern for `get_auth_service()` and `get_audit_service()`.

### Step 3: Update workspace-scoped services

Change `get_prompt_config_service()` and `get_compliance_config()` to use workspace path:

```python
def get_prompt_config_service() -> PromptConfigService:
    global _prompt_config_service
    if _prompt_config_service is None:
        config_dir = _get_workspace_config_dir()
        _prompt_config_service = PromptConfigService(config_dir)
    return _prompt_config_service

def get_compliance_config() -> ComplianceStorageConfig:
    global _compliance_config
    if _compliance_config is None:
        try:
            _compliance_config = ComplianceStorageConfig.from_env()
        except Exception:
            pass
        if _compliance_config is None:
            # Use workspace logs directory
            _compliance_config = ComplianceStorageConfig(
                storage_dir=DATA_DIR.parent / "logs"
            )
    return _compliance_config
```

### Step 4: Reset singletons on workspace switch

The `reset_services()` function already exists but needs to reset ALL singletons:

```python
def reset_services():
    """Reset all service singletons to pick up new workspace paths."""
    global _claims_service, _documents_service, _pipeline_service
    global _upload_service, _truth_service, _insights_service
    global _prompt_config_service, _compliance_config  # ADD THESE

    _claims_service = None
    _documents_service = None
    _pipeline_service = None
    _upload_service = None
    _truth_service = None
    _insights_service = None
    _prompt_config_service = None  # ADD
    _compliance_config = None      # ADD
```

Note: Do NOT reset `_users_service`, `_auth_service`, `_audit_service` since they're global.

### Step 5: Create workspace config directory on activation

Update `activate_workspace()` endpoint to ensure config dir exists:

```python
# In activate_workspace endpoint, after set_data_dir():
workspace_config_dir = Path(workspace.path) / "config"
workspace_config_dir.mkdir(exist_ok=True)
```

## Files to Modify

1. `src/context_builder/api/main.py`:
   - Add `_get_global_config_dir()` and `_get_workspace_config_dir()` helpers
   - Update 5 service getter functions
   - Update `reset_services()` to include workspace-scoped singletons
   - Update `activate_workspace()` to create config dir

## Migration Notes

- Existing files in `output/config/` (users.json, sessions/) should be moved to `.contextbuilder/`
- Or: first run will create new files in correct location, old data orphaned
