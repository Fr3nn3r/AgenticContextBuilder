# Backend Maintainability Review

## Summary
This backend shows clear signs of “God files” and cross-cutting responsibilities. The largest modules mix orchestration, IO, and domain logic, which increases cognitive load, makes testing harder, and raises the risk of regressions. The main architectural opportunities are to split oversized modules, move IO to the edges, and formalize service interfaces so that orchestration does not depend on concrete filesystem layouts.

## Highest-Impact Risks
- **God files / mixed responsibilities**
  - `src/context_builder/api/main.py` mixes app setup, config loading, auth/workspace control, and all endpoints.
  - `src/context_builder/pipeline/run.py` mixes orchestration, IO, and business logic.
  - `src/context_builder/storage/filesystem.py` centralizes read, write, index, and delete operations.
  - `src/context_builder/api/insights.py` appears to embed heavy analytics logic.
  These files increase change risk and slow onboarding.

- **Global state + import-time side effects**
  - `.env` and workspace loading happens on import in multiple places.
  - Global mutable paths (`DATA_DIR`, `STAGING_DIR`) are updated at import.
  This makes behavior implicit and increases test fragility.

- **Tight coupling to filesystem layout**
  - Pipeline orchestration writes to paths directly.
  - Storage layer and API services also assume the same layout.
  This makes layout changes or storage backend swaps expensive.

- **Duplicated logic across CLI/API/pipeline**
  - Run metadata, summaries, and metrics are created and interpreted in multiple places.
  This risks drift and inconsistent behavior.

## Biggest Files (Maintainability Hotspots)
- `src/context_builder/api/main.py`
- `src/context_builder/pipeline/run.py`
- `src/context_builder/api/insights.py`
- `src/context_builder/cli.py`
- `src/context_builder/storage/filesystem.py`
- `src/context_builder/api/services/pipeline.py`

## Recommendations (Phased)

### Phase 1 — Quick wins (low risk, high ROI)
1) **Split `api/main.py` into routers**
   - Create router modules per domain: `claims`, `documents`, `pipeline`, `labels`, `workspaces`, `auth`.
   - Keep `main.py` for app creation + router registration only.

2) **Extract pipeline stages**
   - Move ingestion/classification/extraction stage logic into dedicated modules.
   - Keep `run.py` focused on orchestration and sequencing.

3) **Centralize configuration**
   - Introduce a single configuration loader invoked explicitly at startup.
   - Avoid import-time `.env` loads in modules.

4) **Thin the filesystem storage layer**
   - Split read/query vs write/mutation operations into separate classes.
   - Keep `FileStorage` as a facade that composes smaller components.

### Phase 2 — Structural improvements
1) **Introduce service interfaces**
   - API services should depend on storage/service interfaces, not concrete implementations.

2) **Unify run metadata building**
   - Move manifest/summary/metrics creation into one shared module.

3) **Repository abstractions for IO**
   - Introduce `RunRepository` and `DocumentRepository` to encapsulate filesystem layout.

4) **Reduce mutable global state**
   - Move workspace resolution into request-level dependencies or explicit service calls.

### Phase 3 — Strategic improvements
1) **Move heavy IO off request path**
   - Long indexing or aggregation should be async/background tasks.

2) **Formalize domain models**
   - Consolidate duplicated concepts (run summaries, doc metadata) into canonical schemas.

3) **Make storage backends pluggable**
   - Ensure orchestration depends only on the storage protocol, not on concrete paths.

## Guiding Principles
- **Single responsibility**: each module owns one thing.
- **IO at the edges**: orchestrators shouldn’t open files directly.
- **Explicit configuration**: no side effects on import.
- **Interface-first design**: separate domain logic from infrastructure.

## Suggested Next Steps
1) Split `api/main.py` into routers and a minimal app entrypoint.
2) Extract pipeline stage classes into a `pipeline/stages/` package.
3) Draft storage interface boundaries and update pipeline to use them.

---
If you want a file-by-file refactor plan, I can draft the exact move/rename steps and the order to minimize risk.
