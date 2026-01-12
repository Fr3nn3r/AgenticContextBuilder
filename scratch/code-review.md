# SOLID Code Review

## Findings (Ordered by Severity)

### High
- **SRP violation: API module mixes routing, data access, aggregation, and formatting.** `api/main.py` contains route handlers, filesystem scans, risk scoring, and label/extraction aggregation. This makes change isolation hard and encourages tight coupling. Extract these into service modules (e.g., `services/claims_service.py`, `services/docs_service.py`, `services/insights_service.py`) and keep route handlers thin.
  - `src/context_builder/api/main.py:1`
- **SRP + OCP violation: pipeline orchestration is monolithic.** `process_document()` handles ingestion, classification, extraction, output writing, and reuse logic in one function. Adding a new stage or alternate runner requires editing this core path. Introduce stage objects with a common interface and a pipeline runner that iterates stages.
  - `src/context_builder/pipeline/run.py:304`
- **DIP violation: concrete dependencies are instantiated inside core logic.** The pipeline directly constructs `IngestionFactory` providers and `OpenAI` clients rather than receiving them via interfaces or factory injection. This complicates testing and makes swapping providers harder. Pass dependencies into `process_claim`/`process_document` or use an explicit DI container.
  - `src/context_builder/pipeline/run.py:160`
  - `src/context_builder/extraction/extractors/generic.py:64`

### Medium
- **OCP violation: adding doc types requires modifying several modules.** While specs are data-driven, `InsightsAggregator` hard-codes `SUPPORTED_DOC_TYPES`, and UI/insights logic assumes specific types. Consider reading available specs dynamically and letting the UI filter/label based on spec metadata rather than hard-coded lists.
  - `src/context_builder/api/insights.py:27`
- **ISP violation: storage interface is oversized and mixes concerns.** `FileStorage` handles listing, indexing, doc access, labels, and run data. Consumers that only need one slice depend on the whole class. Split into smaller interfaces (e.g., `DocStore`, `LabelStore`, `RunStore`) with a façade for API usage.
  - `src/context_builder/storage/filesystem.py:18`
- **LSP risk: subclasses do not enforce consistent error contracts.** Ingestion implementations raise different exception types and sometimes return partial data. The base class promises `Dict[str, Any]` but not consistent error/warning metadata. Standardize error envelopes to keep callers from depending on provider-specific behavior.
  - `src/context_builder/ingestion.py:12`
  - `src/context_builder/impl/openai_vision_ingestion.py:150`

### Low
- **SRP/UI component complexity: large components blend data loading, state orchestration, and rendering.** Example: `DocReview` manages API calls, label state transitions, and layout. Extract data hooks and reducer-style state management to improve maintainability and testability.
  - `ui/src/components/DocReview.tsx:1`
- **OCP/UI: hard-coded rendering logic for review states.** Field labeling logic and status badges are embedded in components; adding new states (e.g., "needs_review") requires touching multiple components. Centralize state-to-UI mapping in a helper or config map.
  - `ui/src/components/FieldsTable.tsx:1`

## SOLID-Focused Recommendations
- **Introduce pipeline stage interfaces**: `Stage.run(context) -> context` with explicit inputs/outputs. This isolates stage-specific changes and aligns with OCP.
- **Move orchestration to a `PipelineRunner`** that accepts stage list and a context object. Keep filesystem writes in a `ResultWriter` service.
- **Refactor API module into services**: `ClaimsService`, `DocumentsService`, `InsightsService`, `LabelsService` with route handlers delegating.
- **Split `FileStorage` into read/write roles** and define small protocols; keep a façade for API convenience.
- **Create UI hooks** like `useDocReview(docId)` and `useLabelState` to separate data access and presentation.

## Testing Gaps (SOLID-related)
- No direct unit tests for service boundaries because modules aren’t separated. Once services exist, add contract tests for each service and a small integration suite for routes.

## Notes
- These findings focus on architectural alignment with SOLID rather than bug risk. Some current choices are pragmatic; apply refactors where extensibility and test isolation are priorities.
