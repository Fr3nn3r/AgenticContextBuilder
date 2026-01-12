# Implementation Plan for SOLID Refactor

## Goals
- Separate routing from business logic in the API.
- Modularize the pipeline into composable stages with clear interfaces.
- Introduce dependency injection for external providers to improve testability.
- Break storage responsibilities into smaller interfaces.
- Simplify UI components by moving data and state management into hooks.

## Scope
- Backend: API services, pipeline runner and stages, storage interfaces, ingestion error contracts.
- UI: data hooks and state-to-UI mapping utilities.
- Tests: service unit tests and route-level integration tests.

## Phase 0: Baseline and Inventory
- Map current call flows for `api/main.py`, `pipeline/run.py`, and storage usage.
- Enumerate current pipeline steps and identify inputs/outputs per step.
- Identify all ingestion providers and current error handling patterns.

## Phase 1: API Service Layer
- Create `src/context_builder/api/services/` with:
  - `ClaimsService`
  - `DocumentsService`
  - `InsightsService`
  - `LabelsService`
- Move filesystem scans, aggregations, and formatting logic into services.
- Update `api/main.py` to delegate to services and keep handlers thin.
- Add unit tests for each service with mocked storage.

## Phase 2: Pipeline Stages and Runner
- Define a `Stage` protocol/interface: `run(context) -> context`.
- Implement a `PipelineRunner` that accepts an ordered list of stages.
- Split `process_document` into discrete stages:
  - Ingestion
  - Classification
  - Extraction
  - Persistence/Output writing
  - Reuse/Cache handling
- Keep filesystem writes behind a `ResultWriter` service.
- Add tests for each stage in isolation and a runner integration test.

## Phase 3: Dependency Injection
- Add explicit dependency parameters to `process_claim`/`process_document`.
- Introduce factories or provider registries for ingestion and LLM clients.
- Ensure default constructors are centralized (e.g., in CLI or app startup).
- Add tests that inject fake providers to validate behavior.

## Phase 4: Storage Interface Split
- Define small protocols:
  - `DocStore` (document access and listing)
  - `LabelStore` (label CRUD)
  - `RunStore` (run metadata and results)
- Refactor `FileStorage` to implement these protocols.
- Add a facade that aggregates stores for API use.
- Update service layer to depend on narrow interfaces.

## Phase 5: Ingestion Error Contract
- Define a standard error envelope (e.g., `IngestionResult` with `data`, `warnings`, `errors`).
- Update all ingestion providers to return consistent results or raise a shared exception type.
- Add tests asserting a uniform error contract across providers.

## Phase 6: UI Hook Extraction and State Mapping
- Create hooks:
  - `useDocReview(docId)` for data loading
  - `useLabelState` for label transitions
- Centralize review state-to-UI mapping in a helper/config map.
- Refactor `DocReview` and `FieldsTable` to consume hooks/utilities.
- Add component tests for the mapping logic and hook-driven renders.

## Testing Plan
- Unit tests for all services and stages.
- Integration tests for API routes using the service layer.
- UI component tests for state mapping and hook outputs.

## Deliverables
- New service modules and refactored `api/main.py`.
- Stage-based pipeline runner with stage tests.
- Updated storage interfaces and facade.
- Uniform ingestion error contract.
- UI hooks and simplified components.
- Test coverage for new boundaries.
