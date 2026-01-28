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

| Worktree | Branch | Backend Port | Frontend Port |
|----------|--------|--------------|---------------|
| AgenticContextBuilder/ | main | 8000 | 5173 |
| AgenticContextBuilder-wt1/ | worktree/slot-1 | 8001 | 5174 |
| AgenticContextBuilder-wt2/ | worktree/slot-2 | 8002 | 5175 |
| AgenticContextBuilder-wt3/ | worktree/slot-3 | 8003 | 5176 |

**CRITICAL: Always use YOUR worktree's assigned ports when running dev servers.**

**Agent checklist at session start:**
1. Verify your working directory: `pwd && git branch --show-current`
2. Check for uncommitted changes: `git status`
3. Sync with main if needed: `git fetch origin && git rebase origin/main`
4. Use YOUR assigned ports when starting dev servers (see table above)

**Key rules:**
- Always confirm you're in the correct worktree before making changes
- Always use YOUR worktree's assigned ports - never use another worktree's ports
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

# Pipeline CLI (uses active workspace from .contextbuilder/workspaces.json)
python -m context_builder.cli pipeline <input_claims_folder>  # Run full pipeline
python -m context_builder.cli pipeline <input> --dry-run      # Preview without processing
python -m context_builder.cli pipeline <input> --stages ingest,classify  # Run specific stages
python -m context_builder.cli pipeline <input> --doc-types list          # List available doc types
python -m context_builder.cli pipeline <input> --doc-types fnol_form,police_report  # Filter doc types

# Other CLI commands
python -m context_builder.cli index build                     # Build registry indexes
python -m context_builder.cli aggregate --claim-id CLM-001    # Aggregate facts for a claim
python -m context_builder.cli eval run --run-id <run_id>      # Evaluate a run
```

## Conventions
- Python: snake_case | TypeScript: camelCase | Classes: PascalCase
- Test new/changed logic with PyTest or Jest
- Do not start/stop dev servers automatically - ask user first

## Architecture Rules (CRITICAL)

**NEVER add code to these files - they are being refactored:**
- `api/main.py` - Use existing routers or create new ones in `api/routers/`
- `pipeline/run.py` - Add stage logic to `pipeline/stages/` modules

**Where to put new code:**
| Adding... | Put it in... |
|-----------|--------------|
| New API endpoint | `api/routers/{domain}.py` (create if needed) |
| New business logic | `api/services/{domain}.py` |
| New pipeline behavior | `pipeline/stages/{stage}.py` |
| New storage logic | `storage/{domain}.py` |
| Shared data models | `schemas/` |

**Red flags - STOP and ask user:**
- Adding >50 lines to any single file
- Any edit to `api/main.py` or `pipeline/run.py`
- Duplicating logic that exists elsewhere

**Full guidelines:** `docs/DEVELOPER_GUIDELINES.md`

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

## Customer Configuration (CRITICAL)

Customer-specific extractors, prompts, and specs are stored in **separate git repos** (not in the main codebase).

> **WARNING**: Files in `workspaces/nsa/config/` are **GITIGNORED** in this repo.
> You MUST commit customer config changes to the **customer repo**, not here.

**Customer repo location:** `C:\Users\fbrun\Documents\GitHub\context-builder-nsa`

**Workflow:**
1. Edit in workspace: `workspaces/nsa/config/extractors/`, `extraction_specs/`, `prompts/`
2. Test: `python -m context_builder.cli pipeline --file "path/to/doc.pdf" --force`
3. Copy to customer repo:
   ```bash
   powershell -ExecutionPolicy Bypass -File "C:\Users\fbrun\Documents\GitHub\context-builder-nsa\copy-from-workspace.ps1"
   ```
4. Check status and commit in customer repo:
   ```bash
   git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" status
   git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" add <files>
   git -C "C:\Users\fbrun\Documents\GitHub\context-builder-nsa" commit -m "feat: description"
   ```

**Customer repos:**
- NSA: `C:\Users\fbrun\Documents\GitHub\context-builder-nsa` ([GitHub](https://github.com/Fr3nn3r/context-builder-nsa), private)

**Full documentation:** `.claude/docs/customer-config.md`

## Context Management
- **BACKLOG.md** - All tasks (todo/doing/done). Update before clearing context.
- **.claude/docs/** - Reference docs:
  - `architecture.md` - System design and component overview
  - `compliance.md` - Audit logging and regulatory requirements
  - `customer-config.md` - Customer-specific configuration workflow
  - `testing.md` - Test patterns and best practices
  - `worktrees.md` - Multi-agent parallel development setup
- Before `/clear`: Add handoff notes to BACKLOG.md under your task

## Key Paths
- Backend: `src/context_builder/` (pipeline/, classification/, extraction/, api/)
- Frontend: `ui/src/` (App.tsx, components/, pages/)
- Specs: `extraction/specs/doc_type_catalog.yaml` (doc types SSOT)
- Workspace service: `api/services/workspace.py`
