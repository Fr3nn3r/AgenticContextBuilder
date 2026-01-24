# Backend Maintainability Refactoring Plan

## Overview
This plan addresses the "god file" problem in the backend through pragmatic refactoring focused on high-ROI, low-risk changes. The goal is improved maintainability without over-engineering.

---

## Phase 1: Quick Wins (Low Risk, High ROI)

### 1.1 Split `api/main.py` into FastAPI Routers

**Current state**: 3031 lines with 65 endpoints mixed with app setup, auth, and services.

**Target structure**:
```
src/context_builder/api/
├── main.py                    # ~150 lines: App setup, CORS, lifespan, router registration
├── dependencies.py            # ~200 lines: Auth deps, service getters, globals
├── websocket.py               # ~50 lines: ConnectionManager for pipeline progress
├── routers/
│   ├── __init__.py
│   ├── claims.py              # 6 endpoints: /api/claims, /api/claims/{id}/docs
│   ├── documents.py           # 6 endpoints: /api/docs/{id}, /api/docs/{id}/source
│   ├── auth.py                # 3 endpoints: /api/auth/login, logout, me
│   ├── admin_users.py         # 4 endpoints: /api/admin/users CRUD
│   ├── admin_workspaces.py    # 5 endpoints: /api/admin/workspaces CRUD
│   ├── pipeline.py            # 12 endpoints: /api/pipeline/* (run, status, configs)
│   ├── insights.py            # 15 endpoints: /api/insights/*
│   ├── classification.py      # 5 endpoints: /api/classification/*
│   ├── upload.py              # 8 endpoints: /api/upload/*
│   ├── compliance.py          # 8 endpoints: /api/compliance/*
│   ├── evolution.py           # 2 endpoints: /api/evolution/*
│   └── system.py              # 3 endpoints: /health, /api/version
```

**Files to modify**:
- `src/context_builder/api/main.py` - Reduce to app setup only
- Create all files in `src/context_builder/api/routers/`
- Create `src/context_builder/api/dependencies.py`
- Create `src/context_builder/api/websocket.py`

**Migration order** (lowest risk first):
1. Create `dependencies.py` - Extract service getters and auth dependencies
2. Create `websocket.py` - Extract ConnectionManager
3. Create `routers/system.py` - Simple health/version endpoints (test the pattern)
4. Create `routers/auth.py` - Self-contained auth endpoints
5. Create remaining routers in order of independence

**Key dependencies to preserve**:
- Service singletons (`_pipeline_service`, `_auth_service`, etc.) stay in `dependencies.py`
- `DATA_DIR`/`STAGING_DIR` globals stay in `dependencies.py`
- `ws_manager` singleton stays in `websocket.py`, imported by `routers/pipeline.py`

---

### 1.2 Extract Pipeline Stages to Separate Modules

**Current state**: `pipeline/run.py` (1460 lines) contains stage classes + orchestration + helpers.

**Target structure**:
```
src/context_builder/pipeline/
├── run.py                     # ~500 lines: process_claim, process_document, orchestration
├── stages.py                  # Existing: Stage protocol, PipelineRunner
├── stages/
│   ├── __init__.py            # Re-exports all stages
│   ├── context.py             # DocumentContext, PhaseTimings, DocResult, ClaimResult
│   ├── ingestion.py           # IngestionStage + _ingest_document, _ingest_with_provider
│   ├── classification.py      # ClassificationStage + _load_existing_classification
│   └── extraction.py          # ExtractionStage + _run_extraction
├── helpers/
│   ├── __init__.py
│   ├── metadata.py            # _get_git_info, _compute_templates_hash, manifest writing
│   └── io.py                  # _write_json, _write_json_atomic (or keep in writer.py)
```

**Files to modify**:
- `src/context_builder/pipeline/run.py` - Keep orchestration, remove stage implementations
- Create `src/context_builder/pipeline/stages/` package
- Update `src/context_builder/pipeline/__init__.py` to re-export

**Migration order**:
1. Create `stages/context.py` - Move dataclasses (DocumentContext, PhaseTimings, etc.)
2. Create `stages/ingestion.py` - Move IngestionStage + helpers
3. Create `stages/classification.py` - Move ClassificationStage + helpers
4. Create `stages/extraction.py` - Move ExtractionStage + helpers
5. Update imports in `run.py` to use new modules

**Backwards compatibility**:
- `process_document()` and `process_claim()` stay in `run.py`
- All existing callers (CLI, API) work unchanged

---

### 1.3 Centralize Configuration Loading

**Current state**: `.env` loaded in 3 places (api/main.py, pipeline/run.py, cli.py) at import time.

**Target**: Single explicit startup function called once.

**Create**: `src/context_builder/startup.py`
```python
"""Centralized application startup and configuration."""

_initialized = False

def initialize(env_path: Path | None = None) -> None:
    """Load .env and initialize workspace context. Call once at app startup."""
    global _initialized
    if _initialized:
        return

    # 1. Load .env
    # 2. Initialize workspace paths
    # 3. Validate active workspace
    _initialized = True

def reinitialize_workspace(workspace_id: str) -> None:
    """Reset all caches after workspace switch."""
    # 1. Reset workspace_paths cache
    # 2. Reset tenant config cache
    # 3. Reset LLM audit service
    # 4. Update DATA_DIR/STAGING_DIR
```

**Files to modify**:
- Create `src/context_builder/startup.py`
- `src/context_builder/api/main.py` - Remove import-time .env loading, call `startup.initialize()` in lifespan
- `src/context_builder/pipeline/run.py` - Remove import-time .env loading
- `src/context_builder/cli.py` - Call `startup.initialize()` at start of `main()`
- `src/context_builder/api/services/workspace.py` - Call `startup.reinitialize_workspace()` after activate

---

## Phase 2: Structural Improvements (If Causing Pain)

### 2.1 Replace Global DATA_DIR/STAGING_DIR

**Current state**: Module-level globals mutated at runtime.

**Target**: Request-scoped dependency injection via FastAPI `Depends()`.

**Approach**:
```python
# In dependencies.py
def get_workspace_context() -> WorkspaceContext:
    """Get current workspace paths. Called per-request."""
    return WorkspaceContext(
        claims_dir=get_workspace_claims_dir(),
        logs_dir=get_workspace_logs_dir(),
        staging_dir=get_workspace_staging_dir(),
    )

# In routers
@router.get("/api/claims")
def list_claims(workspace: WorkspaceContext = Depends(get_workspace_context)):
    service = ClaimsService(workspace.claims_dir)
    ...
```

**Files to modify**:
- `src/context_builder/api/dependencies.py` - Add `get_workspace_context()`
- All router files - Update endpoints to use dependency
- Service classes - Accept paths as constructor args instead of reading globals

**Note**: This is a larger change. Only do if the globals are causing actual bugs or test flakiness.

---

### 2.2 Unify Run Metadata Building

**Current state**: Manifest/summary/metrics creation logic duplicated or scattered.

**Target**: Single shared module for run metadata.

**Create**: `src/context_builder/pipeline/metadata.py`
```python
"""Unified run metadata building for manifests, summaries, and metrics."""

def build_manifest(run_id, claim_id, doc_count, stage_config, ...) -> dict: ...
def build_summary(claim_id, run_id, results, elapsed, ...) -> dict: ...
def compute_phase_aggregates(results: list[DocResult]) -> dict: ...
```

**Files to modify**:
- Create `src/context_builder/pipeline/metadata.py`
- `src/context_builder/pipeline/run.py` - Import from metadata module
- Any other files that build similar structures

---

## Implementation Order

### Week 1: Foundation
1. Create `api/dependencies.py` - Extract from main.py
2. Create `api/websocket.py` - Extract ConnectionManager
3. Create `startup.py` - Centralize .env loading
4. Update main.py/cli.py to use startup.py

### Week 2: Router Extraction
5. Create `routers/system.py` (health, version)
6. Create `routers/auth.py`
7. Create `routers/claims.py` + `routers/documents.py`
8. Create `routers/admin_users.py` + `routers/admin_workspaces.py`
9. Create remaining routers

### Week 3: Pipeline Stages
10. Create `pipeline/stages/context.py`
11. Create `pipeline/stages/ingestion.py`
12. Create `pipeline/stages/classification.py`
13. Create `pipeline/stages/extraction.py`
14. Clean up `pipeline/run.py`

### Week 4 (If Needed): Phase 2
15. Implement workspace context dependency injection
16. Unify run metadata building

---

## Verification Plan

### After Each Router Extraction
```bash
# Run backend tests
python -m pytest tests/unit/ --no-cov -q

# Start dev server and verify endpoints work
uvicorn context_builder.api.main:app --reload --port 8000

# Test specific router endpoints via curl or UI
```

### After Pipeline Stage Extraction
```bash
# Run pipeline-specific tests
python -m pytest tests/unit/test_pipeline*.py -v

# Run extraction CLI to verify pipeline works
python -m context_builder.cli extract --model gpt-4o --claim-id test
```

### After Startup Centralization
```bash
# Verify API starts correctly
uvicorn context_builder.api.main:app --reload --port 8000

# Verify CLI loads config correctly
python -m context_builder.cli --help

# Test workspace switching
# POST /api/admin/workspaces/{id}/activate → verify caches reset
```

---

## Files Summary

### New Files to Create
- `src/context_builder/api/dependencies.py`
- `src/context_builder/api/websocket.py`
- `src/context_builder/api/routers/__init__.py`
- `src/context_builder/api/routers/system.py`
- `src/context_builder/api/routers/auth.py`
- `src/context_builder/api/routers/claims.py`
- `src/context_builder/api/routers/documents.py`
- `src/context_builder/api/routers/admin_users.py`
- `src/context_builder/api/routers/admin_workspaces.py`
- `src/context_builder/api/routers/pipeline.py`
- `src/context_builder/api/routers/insights.py`
- `src/context_builder/api/routers/classification.py`
- `src/context_builder/api/routers/upload.py`
- `src/context_builder/api/routers/compliance.py`
- `src/context_builder/api/routers/evolution.py`
- `src/context_builder/startup.py`
- `src/context_builder/pipeline/stages/__init__.py`
- `src/context_builder/pipeline/stages/context.py`
- `src/context_builder/pipeline/stages/ingestion.py`
- `src/context_builder/pipeline/stages/classification.py`
- `src/context_builder/pipeline/stages/extraction.py`

### Files to Modify
- `src/context_builder/api/main.py` - Major reduction
- `src/context_builder/pipeline/run.py` - Major reduction
- `src/context_builder/cli.py` - Use startup.py
- `src/context_builder/api/services/workspace.py` - Use startup.reinitialize_workspace()
- `src/context_builder/pipeline/__init__.py` - Update exports

---

## Risk Mitigation

1. **Incremental extraction**: Move one router at a time, test after each
2. **Import compatibility**: Keep re-exports in original locations during transition
3. **Test coverage**: Run full test suite after each major change
4. **Rollback plan**: Git commit after each successful extraction
