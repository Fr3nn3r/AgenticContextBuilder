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

## Git Worktrees (Multi-Agent Development)

This repo uses **git worktrees** to enable multiple agents to work in parallel on different features.

```
C:\Users\fbrun\Documents\GitHub\
├── AgenticContextBuilder/       # PRIMARY - main branch
├── AgenticContextBuilder-wt1/   # Worktree slot 1
├── AgenticContextBuilder-wt2/   # Worktree slot 2
└── AgenticContextBuilder-wt3/   # Worktree slot 3
```

**Agent checklist at session start:**
1. Verify your working directory: `pwd && git branch --show-current`
2. Check for uncommitted changes: `git status`
3. Sync with main if needed: `git fetch origin && git rebase origin/main`

**Key rules:**
- Always confirm you're in the correct worktree before making changes
- Do NOT merge to main without user approval
- Do NOT switch worktrees without user permission
- Commit frequently with descriptive messages

**Full documentation:** `.claude/docs/worktrees.md`

## Commands
```bash
# Backend
.\scripts\dev-restart.ps1                    # Kill stale + start fresh
uvicorn context_builder.api.main:app --reload --port 8000

# Frontend
cd ui && npm run dev

# Tests
python -m pytest tests/unit/ --no-cov -q                     # Full suite (~15s)
python -m pytest tests/unit/test_storage.py -v --tb=short    # Specific file
python -m pytest tests/unit/ -k "label" --tb=short           # By keyword
cd ui && npx playwright test labeling                        # E2E by name

# Pipeline (uses active workspace from .contextbuilder/workspaces.json)
python -m context_builder.cli extract --model gpt-4o
```

## Conventions
- Python: snake_case | TypeScript: camelCase | Classes: PascalCase
- Test new/changed logic with PyTest or Jest
- Do not start/stop dev servers automatically - ask user first

## Versioning & Commits

**Current version**: Check `pyproject.toml` (backend) and `ui/package.json` (frontend) - kept in sync.

### Semantic Versioning (MAJOR.MINOR.PATCH)
| Bump | When | Examples |
|------|------|----------|
| PATCH | Bug fixes, no API changes | Fix extraction bug, UI styling fix |
| MINOR | New features, backward-compatible | New doc type, new screen, new endpoint |
| MAJOR | Breaking changes | Workspace structure change, API breaking change |

### Commit Message Prefixes
Use these prefixes to indicate the type of change:
- `fix:` - Bug fix (triggers PATCH bump)
- `feat:` - New feature (triggers MINOR bump)
- `BREAKING CHANGE:` - Breaking change (triggers MAJOR bump)
- `chore:` - Maintenance, deps, configs (no version bump)
- `docs:` - Documentation only (no version bump)
- `refactor:` - Code restructure, no behavior change (no version bump)
- `test:` - Adding/updating tests (no version bump)

### Version Bump Script
```powershell
.\scripts\version-bump.ps1 patch    # 0.2.0 -> 0.2.1
.\scripts\version-bump.ps1 minor    # 0.2.0 -> 0.3.0
.\scripts\version-bump.ps1 major    # 0.2.0 -> 1.0.0
.\scripts\version-bump.ps1 patch -DryRun  # Preview only
```

### When to Bump
- Bump version **before releasing** or **after merging a feature branch**
- Group related commits, then bump once (don't bump on every commit)

## Testing Best Practices
- **Full suite is fast**: `python -m pytest tests/unit/ --no-cov -q` runs 850+ tests in ~15 seconds
- **Use `--no-cov`** to skip coverage collection (significantly faster)
- **Use `-k` for keyword filtering**: `pytest -k "label" --tb=short`
- **Use `--tb=short`** for concise error output
- **Known issues**: 4 encryption tests require `pycryptodome` package (skip with `--ignore`)

## Context Management
- **BACKLOG.md** - All tasks (todo/doing/done). Update before clearing context.
- **.claude/docs/** - Reference docs:
  - `architecture.md` - System design and component overview
  - `compliance.md` - Audit logging and regulatory requirements
  - `testing.md` - Test patterns and best practices
  - `worktrees.md` - Multi-agent parallel development setup
- Before `/clear`: Add handoff notes to BACKLOG.md under your task

## Key Paths
- Backend: `src/context_builder/` (pipeline/, classification/, extraction/, api/)
- Frontend: `ui/src/` (App.tsx, components/, pages/)
- Specs: `extraction/specs/doc_type_catalog.yaml` (doc types SSOT)
- Workspace service: `api/services/workspace.py`
