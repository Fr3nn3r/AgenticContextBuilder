# ContextBuilder

Insurance claims document processing: Ingest → Classify → Extract → Quality Gate → QA Console

## Stack
Python 3.9+ / FastAPI / Pydantic | React 18 / TypeScript / Tailwind | File-based JSON

## Workspaces

Data is stored in **workspaces** (isolated storage locations). The active workspace determines where the backend reads/writes.

```
.contextbuilder/workspaces.json     # Registry: lists workspaces, tracks active
workspaces/{workspace_id}/          # Each workspace contains:
  ├── claims/{claim_id}/docs/       # Documents and extractions
  ├── runs/                         # Pipeline run logs
  ├── logs/                         # Compliance logs (decisions, LLM calls)
  ├── registry/                     # Truth store, indexes
  └── config/                       # Prompt configs
```

**Switch workspace**: Admin UI → Workspaces, or `POST /api/workspaces/{id}/activate`

## Commands
```bash
# Backend
.\scripts\dev-restart.ps1                    # Kill stale + start fresh
uvicorn context_builder.api.main:app --reload --port 8000

# Frontend
cd ui && npm run dev

# Tests - IMPORTANT: Run targeted test files, not full suite
python -m pytest tests/unit/test_storage.py -v --tb=short   # Specific file
python -m pytest tests/unit/ -k "label" --tb=short          # By keyword
cd ui && npx playwright test labeling                        # E2E by name

# Pipeline (uses active workspace from .contextbuilder/workspaces.json)
python -m context_builder.cli extract --model gpt-4o
```

## Conventions
- Python: snake_case | TypeScript: camelCase | Classes: PascalCase
- Test new/changed logic with PyTest or Jest
- Do not start/stop dev servers automatically - ask user first

## Testing Best Practices
- **Never run full test suite** (`tests/unit/`) - collection of 900+ tests is slow and causes background task pileup
- **Always target specific files**: `python -m pytest tests/unit/test_storage.py -v`
- **Use `-k` for keyword filtering**: `pytest -k "label" --tb=short`
- **One test command at a time** - wait for completion before running another
- **Use `--tb=short`** for concise error output

## Context Management
- **BACKLOG.md** - All tasks (todo/doing/done). Update before clearing context.
- **.claude/docs/** - Reference docs (architecture, compliance, testing). Read when needed.
- Before `/clear`: Add handoff notes to BACKLOG.md under your task

## Key Paths
- Backend: `src/context_builder/` (pipeline/, classification/, extraction/, api/)
- Frontend: `ui/src/` (App.tsx, components/, pages/)
- Specs: `extraction/specs/doc_type_catalog.yaml` (doc types SSOT)
- Workspace service: `api/services/workspace.py`
