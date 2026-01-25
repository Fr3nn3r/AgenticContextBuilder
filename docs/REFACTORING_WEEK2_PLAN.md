# Backend Refactoring - Week 2: Router Extraction

## Status Summary

### Week 1 Complete ✅
The following foundation work is done:
- `src/context_builder/startup.py` - Centralized .env loading and workspace initialization
- `src/context_builder/api/websocket.py` - WebSocket ConnectionManager
- `src/context_builder/api/dependencies.py` - All FastAPI dependencies and service getters
- Updated `main.py`, `cli.py`, `pipeline/run.py` to use new modules
- All tests pass (1049 passed)

### Current State
- `main.py`: 2723 lines (down from ~3150)
- Contains ~90 endpoints mixed with app setup
- Dependencies and services already extracted

---

## Week 2 Goal: Extract Endpoints to FastAPI Routers

Reduce `main.py` to ~150 lines (app setup, CORS, lifespan, router registration only).

### Target Structure
```
src/context_builder/api/
├── main.py                    # ~150 lines: App setup only
├── dependencies.py            # ✅ Already done
├── websocket.py               # ✅ Already done
├── routers/
│   ├── __init__.py
│   ├── system.py              # 3 endpoints: /health, /api/version
│   ├── auth.py                # 3 endpoints: /api/auth/login, logout, me
│   ├── admin_users.py         # 4 endpoints: /api/admin/users CRUD
│   ├── admin_workspaces.py    # 5 endpoints: /api/admin/workspaces CRUD
│   ├── claims.py              # 6 endpoints: /api/claims/*
│   ├── documents.py           # 6 endpoints: /api/docs/*
│   ├── pipeline.py            # 12 endpoints: /api/pipeline/*
│   ├── insights.py            # 15 endpoints: /api/insights/*
│   ├── classification.py      # 5 endpoints: /api/classification/*
│   ├── upload.py              # 8 endpoints: /api/upload/*
│   ├── compliance.py          # 8 endpoints: /api/compliance/*
│   ├── evolution.py           # 2 endpoints: /api/evolution/*
│   └── token_costs.py         # 7 endpoints: /api/token-costs/*
```

---

## Implementation Order (Lowest Risk First)

### Step 1: Create `routers/system.py`
Simple test of the pattern with health/version endpoints.

**Endpoints to extract:**
- `GET /health` and `GET /api/health`
- `GET /api/version`

**Template:**
```python
from fastapi import APIRouter
from context_builder.api.dependencies import get_project_root

router = APIRouter(tags=["system"])

@router.get("/health")
@router.get("/api/health")
def health_check():
    ...

@router.get("/api/version")
def get_version():
    ...
```

**In main.py, add:**
```python
from context_builder.api.routers import system
app.include_router(system.router)
```

### Step 2: Create `routers/auth.py`
Self-contained auth endpoints.

**Endpoints to extract:**
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Step 3: Create `routers/admin_users.py`
User management CRUD.

**Endpoints to extract:**
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{username}`
- `DELETE /api/admin/users/{username}`

### Step 4: Create `routers/admin_workspaces.py`
Workspace management.

**Endpoints to extract:**
- `GET /api/workspaces`
- `POST /api/workspaces`
- `GET /api/workspaces/{workspace_id}`
- `POST /api/workspaces/{workspace_id}/activate`
- `DELETE /api/workspaces/{workspace_id}`

### Step 5: Create `routers/claims.py`
Claims listing and detail endpoints.

### Step 6: Create `routers/documents.py`
Document endpoints.

### Step 7-13: Create remaining routers
Continue with pipeline, insights, classification, upload, compliance, evolution, token_costs.

---

## How to Extract a Router

1. **Create the router file:**
```python
# src/context_builder/api/routers/example.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from context_builder.api.dependencies import (
    get_example_service,
    get_current_user,
    CurrentUser,
)

router = APIRouter(prefix="/api/example", tags=["example"])

@router.get("/")
def list_items(
    current_user: CurrentUser = Depends(get_current_user),
):
    service = get_example_service()
    return service.list_items()
```

2. **Register in main.py:**
```python
from context_builder.api.routers import example
app.include_router(example.router)
```

3. **Remove the endpoint from main.py**

4. **Test:**
```bash
python -m pytest tests/unit/ --no-cov -q -k "example"
curl http://localhost:8000/api/example/
```

---

## Verification After Each Router

```bash
# Quick syntax check
python -c "from context_builder.api import main; print('OK')"

# Run tests
python -m pytest tests/unit/ --no-cov -q

# Manual check (if server running)
curl http://localhost:8000/api/health
```

---

## Key Points

1. **Import from dependencies.py** - All service getters and auth dependencies are there
2. **Keep Pydantic models in models.py** - Don't move request/response models to routers
3. **WebSocket endpoints** go in `routers/pipeline.py` (import `ws_manager` from `websocket.py`)
4. **Commit after each router** - Small, safe increments
5. **Update test patches if needed** - Some tests may patch `main.py` functions

---

## Files Reference

### Already Created (Week 1)
- `src/context_builder/startup.py`
- `src/context_builder/api/dependencies.py`
- `src/context_builder/api/websocket.py`

### To Create (Week 2)
- `src/context_builder/api/routers/__init__.py`
- `src/context_builder/api/routers/system.py`
- `src/context_builder/api/routers/auth.py`
- `src/context_builder/api/routers/admin_users.py`
- `src/context_builder/api/routers/admin_workspaces.py`
- `src/context_builder/api/routers/claims.py`
- `src/context_builder/api/routers/documents.py`
- `src/context_builder/api/routers/pipeline.py`
- `src/context_builder/api/routers/insights.py`
- `src/context_builder/api/routers/classification.py`
- `src/context_builder/api/routers/upload.py`
- `src/context_builder/api/routers/compliance.py`
- `src/context_builder/api/routers/evolution.py`
- `src/context_builder/api/routers/token_costs.py`

### To Modify
- `src/context_builder/api/main.py` - Remove endpoints, add router imports

---

## Expected Outcome

| Metric | Before | After Week 2 |
|--------|--------|--------------|
| `main.py` lines | 2723 | ~150 |
| Router files | 0 | 14 |
| Endpoints per file | ~90 | 2-15 |
