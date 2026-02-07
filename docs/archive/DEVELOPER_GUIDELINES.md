# Developer Guidelines to Prevent Maintainability Drift

This document lists the practical principles and day-to-day habits that will keep the backend healthy and avoid large refactors later.

## Core Principles (keep these in mind for every PR)
1) **Single responsibility**: each file/class/module should have one clear job.
2) **IO at the edges**: keep filesystem/network calls in dedicated boundary layers.
3) **Explicit configuration**: no side effects on import; load config once at startup.
4) **Interface first**: depend on protocols/abstractions, not concrete implementations.
5) **Small changes, frequent cleanup**: refactor incrementally as you add features.

## Simple Practical Rules
- **Limit file size**: if a file crosses ~400–500 lines, split it.
- **No new “god files”**: new endpoints/services belong in small modules.
- **No copy-pasted logic**: extract shared logic into a helper/service.
- **No global mutable state**: avoid module-level variables that change at runtime.
- **Keep orchestration thin**: pipeline/controller code should call services, not do the work.
- **Avoid import-time side effects**: no env loading or workspace selection on import.

## Module Structure Expectations
- `api/` should only expose endpoints and request/response models.
- `api/services/` should contain business logic and call storage/services.
- `storage/` should contain data access only; avoid domain logic here.
- `pipeline/` should orchestrate stages, not implement stage internals.
- `schemas/` is the single source of truth for shared data models.

## Implementation Guidelines (what to do in code)
- **Add a new endpoint?**
  - Add a new router module if it doesn’t fit an existing one.
  - Keep endpoint functions small (<50 lines).

- **Add new pipeline behavior?**
  - Add or extend a stage module; keep orchestration minimal.
  - Don’t directly manipulate filesystem paths inside stage logic.

- **Add new storage behavior?**
  - Add a reader/writer or repo function, not logic in unrelated modules.
  - Keep file layout logic in one place.

- **Add shared logic?**
  - Extract into a helper/service and unit test it.

- **Add config?**
  - Put config loading in a single configuration module.
  - Pass config explicitly to services.

## Testing Discipline
- Add tests for any non-trivial logic introduced.
- Don’t merge large features without at least unit tests for new helpers/services.
- If new behavior touches storage, add an integration test for expected file outcomes.

## Review Checklist (for every PR)
- [ ] Does this change introduce or expand a “god file”?
- [ ] Can any logic be extracted into a service or helper?
- [ ] Are there new implicit dependencies or global side effects?
- [ ] Are we duplicating logic that already exists?
- [ ] Are we keeping IO and domain logic separated?

## Red Flags (pause and discuss if any occur)
- File grows by >200 lines in a single PR.
- New feature is implemented in `api/main.py` directly.
- Domain logic inside `storage/` or filesystem logic inside orchestration.
- Repeated logic across CLI/API/pipeline.

---
If you want these turned into a lint rule set or PR template, we can add that next.
