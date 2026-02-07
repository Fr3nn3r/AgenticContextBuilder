## Backend naming opportunities (planning only)

This document captures additional naming cleanups observed in the Python backend.
No code changes are applied yet.

### 1) Disambiguate "run" across layers

Problem: "run" refers to both pipeline runs and claim-level runs.

Examples:
- `src/context_builder/storage/models.py` defines `RunRef`, `RunBundle`
- `src/context_builder/storage/claim_run.py` uses `ClaimRunStorage`
- `src/context_builder/schemas/claim_run.py` defines `ClaimRunManifest`

Suggested direction:
- Rename pipeline-level run models to `PipelineRunRef`, `PipelineRunBundle`
  (or `ExtractionRunRef`, `ExtractionRunBundle` if that better matches usage).
- Keep claim-level models explicitly prefixed with `ClaimRun*`.

---

### 2) Split API DTO names from domain/spec names

Problem: identical names appear in both API DTOs and extraction spec models.

Examples:
- `FieldRule`, `QualityGateRules`:
  - `src/context_builder/api/models.py`
  - `src/context_builder/extraction/spec_loader.py`

Suggested direction:
- Rename API DTOs to `ApiFieldRule`, `ApiQualityGateRules` (or add `Request` suffix)
- Rename spec models to `SpecFieldRule`, `SpecQualityGateRules`
- Alternatively, move API models to `api/dtos/` and enforce import style

---

### 3) Root `services/` vs `api/services/`

Problem: both directories contain "services" with different meanings.

Examples:
- `src/context_builder/services/llm_audit.py`
- `src/context_builder/api/services/claims.py`

Suggested direction:
- Rename root `services/` to `core/` or `domain/`
  to differentiate from HTTP-layer service facades.

---

### 4) Duplicate request/response classes across layers

Problem: same names exist in routers and service layer.

Examples:
- `CustomerDraftRequest`, `CustomerDraftResponse` in:
  - `src/context_builder/api/routers/claims.py`
  - `src/context_builder/api/services/customer_communication.py`

Suggested direction:
- Suffix DTOs in API layer: `CustomerDraftRequestDto`, `CustomerDraftResponseDto`
- Or reuse one shared DTO module to avoid duplication

---

### 5) "Doc" vs "Document" naming drift

Problem: abbreviated and full forms are mixed across the codebase.

Examples:
- `DocSummary`, `DocPayload`, `DocPaths`, `DocRef`
- `DocumentAnalysis`, `DocumentContext`

Suggested direction:
- Pick one convention per layer or globally.
- For global consistency: prefer full `Document*` names.
- For storage/pipeline internals: `Doc*` could be acceptable if used uniformly.

---

### 6) Confusing module naming around classification context

Problem: `classification/context_builder.py` name clashes with package branding.

Examples:
- `src/context_builder/classification/context_builder.py`
  (contains `ClassificationContext` and helper functions)

Suggested direction:
- Rename module to `classification_context.py` or `context.py`
  to reduce confusion and improve discoverability.

---

### 7) Duplicate "insights" modules in API layer

Problem: there is an API service *and* a large module in `api/insights.py`.

Examples:
- `src/context_builder/api/insights.py` (aggregation logic)
- `src/context_builder/api/services/insights.py` (service facade)

Suggested direction:
- Rename aggregator to `insights_aggregator.py`
- Keep `api/services/insights.py` as the API-facing service

---

### 8) Generic `utils` buckets

Problem: `utils/` and `api/services/utils.py` are catch-alls with broad names.

Examples:
- `src/context_builder/utils/file_utils.py`
- `src/context_builder/utils/filename_utils.py`
- `src/context_builder/api/services/utils.py`

Suggested direction:
- Rename to intent-specific modules:
  - `file_metadata.py`
  - `filename_sanitizer.py`
  - `claim_run_utils.py` / `run_lookup.py`

---

### 9) `coverage/` package ambiguity

Problem: "coverage" can mean test coverage or policy coverage.

Examples:
- `src/context_builder/coverage/`

Suggested direction:
- Rename to `policy_coverage/` or `coverage_analysis/`
  to make it domain-explicit.

