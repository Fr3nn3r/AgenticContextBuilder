# ContextBuilder

Insurance claims document processing: Ingest → Classify → Extract → Quality Gate → QA Console

## Stack
Python 3.9+ / FastAPI / Pydantic | React 18 / TypeScript / Tailwind | File-based JSON

## Commands
```bash
# Backend
.\scripts\dev-restart.ps1                    # Kill stale + start fresh
uvicorn context_builder.api.main:app --reload --port 8000

# Frontend
cd ui && npm run dev

# Tests
.\scripts\test.ps1                           # All tests (Windows-safe)
cd ui && npx playwright test                 # E2E tests

# Pipeline
python -m context_builder.cli extract -o output/claims --model gpt-4o
```

## Conventions
- Python: snake_case | TypeScript: camelCase | Classes: PascalCase
- Test new/changed logic with PyTest or Jest
- Do not start/stop dev servers automatically - ask user first

## Context Management
- **BACKLOG.md** - All tasks (todo/doing/done). Update before clearing context.
- **.claude/docs/** - Reference docs (architecture, compliance, testing). Read when needed.
- Before `/clear`: Add handoff notes to BACKLOG.md under your task

## Key Paths
- Backend: `src/context_builder/` (pipeline/, classification/, extraction/, api/)
- Frontend: `ui/src/` (App.tsx, components/, pages/)
- Specs: `extraction/specs/doc_type_catalog.yaml` (doc types SSOT)
- Output: `output/claims/{claim_id}/docs/` and `runs/`
