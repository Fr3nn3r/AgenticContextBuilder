# CLAUDE.md - ContextBuilder

## Principles
**Correctness > Security > Maintainability (SSOT) > Simplicity (YAGNI) > Style**

- **Trivial** (typos, small bugfix): implement immediately
- **Non-trivial**: 3-6 bullet plan, ask only blocking questions, proceed with assumptions if needed
- **SSOT**: One place for state/logic; no duplication
- **Naming**: Self-documenting (`pendingClaims` not `data`)
- **Conventions**: Python snake_case, TypeScript camelCase, PascalCase classes
- **Testing**: PyTest/Jest for new/changed logic

## Project Overview

Insurance claims document processing pipeline:
1. **Ingest** docs (PDF/image/text) via Azure DI or OpenAI Vision
2. **Classify** doc types (LOB-agnostic router)
3. **Extract** fields with provenance
4. **Quality gate** (pass/warn/fail)
5. **QA Console** for human labeling

**Stack**: Python 3.9+/FastAPI/Pydantic | React 18/TypeScript/Tailwind/Vite | File-based JSON

## Architecture

```
Input → Pipeline (discovery→run→paths→text→state)
      → Ingestion (Azure DI/OpenAI Vision)
      → Classification → Extraction → Quality Gate
      → Output: output/claims/{claim_id}/docs/|runs/
      → QA Console (FastAPI + React)
```

## Key Paths

**Backend** (`src/context_builder/`):
- `pipeline/run.py` - orchestration
- `classification/openai_classifier.py` - doc type router
- `extraction/extractors/generic.py` - field extraction
- `extraction/specs/doc_type_catalog.yaml` - doc types (SSOT)
- `api/main.py` - FastAPI endpoints

**Frontend** (`ui/src/`):
- `App.tsx` - routing, state
- `components/DocumentReview.tsx` - flat doc list review
- `components/ClaimReview.tsx` - claim-scoped review
- `components/FieldsTable.tsx` - field labeling (shortcuts: 1/2/3, n/p)
- `types/index.ts`, `api/client.ts`

## Doc Types (LOB-agnostic)

`fnol_form`, `insurance_policy`, `police_report`, `invoice`, `id_document`, `vehicle_registration`, `certificate`, `medical_report`, `travel_itinerary`, `customer_comm`, `supporting_document`

## Data Structures

**ExtractionResult**: `{schema_version, run:{run_id,model}, doc:{doc_id,doc_type,confidence}, pages[], fields:[{name,value,normalized_value,confidence,status,provenance}], quality_gate:{status,missing_required_fields}}`

**LabelResult**: `{schema_version, doc_id, claim_id, review:{reviewer,reviewed_at,notes}, field_labels:[{field_name,state,truth_value}], doc_labels:{doc_type_correct}}`

## Commands

```bash
# Backend (use script to avoid port conflicts)
.\scripts\dev-restart.ps1          # Kill stale processes + start fresh

# Backend (manual)
uvicorn context_builder.api.main:app --reload --port 8000

# Frontend
cd ui && npm run dev

# Pipeline
python -m context_builder.cli acquire -p azure-di -o output/claims input/
python -m context_builder.cli classify -o output/claims
python -m context_builder.cli extract -o output/claims --model gpt-4o

# Testing (use script for Windows compatibility)
.\scripts\test.ps1                 # Run all tests
.\scripts\test.ps1 tests/unit/     # Run specific tests
.\scripts\test.ps1 -k "quality"    # Run tests matching pattern
```

## Helper Scripts (`scripts/`)

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `dev-restart.ps1` | Kill uvicorn + restart clean | Backend not responding, port conflicts |
| `kill-uvicorn.ps1` | Kill uvicorn processes only | Quick cleanup without restart |
| `test.ps1` | Run pytest with Windows flags | All test runs (avoids temp dir errors) |
| `worktree-new.ps1` | Create isolated git worktree | Parallel feature development |
| `worktree-remove.ps1` | Remove worktree + branch | Clean up after merge |
| `worktree-list.ps1` | List all worktrees | See active parallel work |

## Session Protocol

**Tasks are persistent, context is ephemeral.** All important state lives in task files.

### Starting a Session
```
> Read tasks/1_in-progress/ to see active work
> Read tasks/0_todo/ to pick new work
```

### Before Clearing Context
1. Update task file with progress and handoff notes
2. Fill "Resume Instructions" section
3. Commit task file changes

### Multi-Window Coordination
Use git worktrees for parallel feature development:
```powershell
./scripts/worktree-new.ps1 feature-name   # Creates sibling folder + branch
./scripts/worktree-list.ps1               # See all active worktrees
./scripts/worktree-remove.ps1 feature-name # Clean up after merge
```

### When to Clear vs Continue
| Context Usage | Task Status | Action |
|---------------|-------------|--------|
| >70% | Any | Write handoff, clear |
| >50% | Complete | Clear, start fresh |
| <50% | In progress | Continue |
| Any | Switching tasks | Clear |

**Full protocol**: See `tasks/3_instructions/SESSION-PROTOCOL.md`

## Troubleshooting

**Server management:** Do not start or stop dev servers (uvicorn, npm run dev) automatically. Always ask the user to manage servers manually to avoid spawning duplicate processes. Only start/stop servers if the user explicitly requests it.

**Env vars not loading / Code changes not taking effect:**
Multiple uvicorn processes may be running. Auto-reload spawns new processes but old ones keep serving requests.

**Quick fix:** Run `.\scripts\kill-uvicorn.ps1` then restart.

**Manual diagnosis:**
```powershell
# Check for multiple processes on port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select OwningProcess

# Identify uvicorn processes specifically
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*' } | Select ProcessId, CommandLine

# Kill only uvicorn processes (safer than killing all Python)
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Then restart fresh
uvicorn context_builder.api.main:app --reload --port 8000
```

See `tests/unit/test_azure_di_impl.py::TestEnvironmentVariableLoading` for regression tests.

## Folders

- `plans/` - **Always** save implementation plans here when using plan mode. Use naming: `YYYYMMDD-Meaningful-Name.md` (e.g., `20260114-Auth-System-Refactor.md`)
- `phases/` - write summary after each phase
- `scratch/` - temp notes, ignore unless referenced
- `tasks/` - Task tracking (persistent across sessions):
  - `0_todo/` - Pending work
  - `1_in-progress/` - Active tasks (one owner per task)
  - `2_done/` - Completed work
  - `3_instructions/` - Reusable guides (TASK-TEMPLATE.md, SESSION-PROTOCOL.md)

## Glossary

| Term | Definition |
|------|------------|
| Batch | Pipeline execution with specific versions; produces extraction outputs, gates, logs |
| Label | Human record per doc+field with truth state |
| Labeled | truth_value exists (ground truth) |
| Unlabeled | No truth recorded yet |
| Unverifiable | Reviewer cannot establish truth (with reason) |
| Truth value | Human-authoritative correct value |
| Extracted value | System-produced value from batch |
| Correct | extracted == truth (normalized) |
| Incorrect | extracted exists but != truth |
| Missing | truth exists but no extraction |
| Accuracy | Correct/(Correct+Incorrect+Missing) over LABELED fields |
| Provenance | Page ref, quote, offsets linking value to source |
| Quality Gate | Doc status: PASS/WARN/FAIL based on extraction health |
