# Repository Guidelines

## Project Structure & Module Organization
- `src/context_builder/` holds the Python backend (pipeline, classification, extraction, storage, API). Key entry points are `cli.py` and `api/main.py`.
- `ui/` contains the React + TypeScript QA console (see `ui/src/` for pages/components).
- `tests/` contains Python test suites.
- `data/`, `examples/`, `media/`, and `prompts/` store sample inputs and assets.
- `output/` is a generated workspace for pipeline results (claims, runs, registry).
- Workspaces live under `workspaces/{workspace_id}/` and are selected via `.contextbuilder/workspaces.json`.

## Build, Test, and Development Commands
- `uv pip install -e .` or `pip install -e .`: install backend dependencies in editable mode.
- `python -m context_builder.cli pipeline <input_path> -o output/claims`: run the full pipeline on claim folders.
- `uvicorn api.main:app --reload --port 8000`: start the FastAPI backend from `src/context_builder`.
- `cd ui && npm install && npm run dev`: install and run the React QA console.
- `python -m context_builder.cli index build --root output`: rebuild JSONL indexes for fast lookup.

## Coding Style & Naming Conventions
- Python follows PEP 8 with type hints where practical. Use descriptive, lowercase module names.
- React/TSX uses PascalCase for components and `camelCase` for variables/functions.
- Keep spec and prompt files in `src/context_builder/extraction/specs/` and `src/context_builder/prompts/` using clear, domain-based names (e.g., `invoice.yaml`).

## Testing Guidelines
- Backend tests run with `pytest` (`pytest tests/ -v`).
- Coverage is optional but supported: `pytest tests/ --cov=context_builder --cov-report=html`.
- Test files follow `test_*.py` naming; keep fixtures close to their suites.

## Worktrees, Servers, and Cost Controls
- Confirm you are in the correct worktree before changes; do not switch worktrees without user permission.
- Use the assigned worktree ports when running dev servers; never use another worktree's ports.
- Do not start/stop dev servers automatically—ask the user first.
- Never run assess/pipeline on more than 3 claims at a time without explicit user permission.

## Core vs Customer Code Separation
- Core product code in `src/context_builder/` must remain customer-agnostic.
- Customer-specific vocabulary, rules, prompts, and extraction specs belong in workspace config (`workspaces/{id}/config/`).
- If adding customer-specific terms or rules to `src/`, stop and ask the user first.

## Architecture Constraints
- Do not add code to `api/main.py` or `pipeline/run.py`; use `api/routers/` and `pipeline/stages/` instead.
- If a change would add more than ~50 lines to a single file, stop and ask the user first.

## Customer Configuration Workflow
- Workspace config under `workspaces/{id}/config/` is gitignored in this repo.
- Commit customer config changes to the customer repo instead (e.g., `C:\Users\fbrun\Documents\GitHub\context-builder-nsa`).

## Commit & Pull Request Guidelines
- No explicit commit convention found; use concise, imperative messages (e.g., "Add extraction spec for invoices").
- PRs should include a clear description, any new CLI/API behavior, and screenshots for UI changes.
- Link related issues when applicable and note any data migration or output format changes.

## Configuration & Security Notes
- Use `.env` for API keys (`OPENAI_API_KEY`, optional Azure DI keys). Do not commit secrets.
- If adding new ingestion providers, register them via `IngestionFactory` and document required env vars.

## Planning & Context Management
- When using plan mode, store the plan file under `plans/`.
- Before clearing context, add handoff notes to `BACKLOG.md`.
