# Pipeline Control Center — Requirements & Plan

## Goal
Provide a power‑user screen to run, monitor, and manage pipeline operations (ingest → classify → extract → metrics) for claims/documents with safe controls and rich observability.

## Assumptions (confirmed)
- **Admin-only** access.
- **Existing claim discovery only** (no local path picker).
- **Manual runs only** (no scheduling in v1).
- **Progress via log tailing** (or log-derived polling).
- **Separate model selection** for classifier and extractor.
- **Run deletion allowed** from UI.
- **Audit all actions**.

## Requirements (Power‑User)

### Core Operations
- **Run pipeline by input path**: pick an input folder and output root.
- **Run by claim/doc selection**: select claims/docs to process (from discovery/index).
- **Stage control**: choose stages (ingest/classify/extract) consistent with `StageConfig`.
- **Run ID control**: auto‑generate or set a custom `run_id`.
- **Force/overwrite**: toggle `--force` behavior.
- **Model selection**: choose model used for classification/extraction where supported.
- **Compute metrics**: on/off switch (matches `compute_metrics`).

### Re‑run / Partial Runs
- **Re‑run extraction only** for a subset of docs (reuse ingest/classify).
- **Re‑run classify + extract** for docs with new classifier/model.
- **Reuse detection**: surface whether ingestion/classification outputs were reused.

### Monitoring & Feedback
- **Live progress**: per‑claim and per‑document progress.
- **Run status**: success/partial/fail + counts.
- **Artifacts**: links to manifest, summary, metrics, logs.
- **Errors**: list failures with phase (ingestion/classification/extraction) and error text.
- **Quality gate**: display pass/warn/fail counts.

### Safety & Controls
- **Dry‑run**: preview what would be processed (claims/docs count).
- **Cancel**: stop an in‑progress run (best effort).
- **Confirm risky actions**: overwrite existing run, run on large batches.

### Power‑User Utilities
- **Recent runs list**: filter by status/run_id/date.
- **Search & filter**: by claim_id, doc_type, status, stage.
- **Export**: download run summary/metrics JSON.
- **Index health**: show whether indexes exist and if stale.

### Access & Permissions
- **Role‑gated actions**: run pipeline, force overwrite, delete runs.
- **Read‑only mode**: view only.

## Open Questions
None for now.

## Implementation Plan (Phased)

### Phase A — UX + Data Model
- Define run request payload schema (stages, run_id, force, model, input path).
- Define run status response schema (progress, counts, errors, artifacts).
- Create UI page skeleton with two panes:
  - Left: **Run Config** (inputs, stages, model, options).
  - Right: **Run Monitor** (progress, logs, artifacts, errors).

### Phase B — API Wiring
- Add/extend API endpoint to trigger runs (or CLI wrapper service).
- Add endpoint to list runs + fetch run details (manifest/summary/metrics).
- Add endpoint for logs/streaming (or periodic polling).

### Phase C — UI Build
- Run Config form with validation + dry‑run.
- Run Monitor panel with live updates and error list.
- Recent runs table with filters and quick open.

### Phase D — Hardening
- Permission checks + confirmations.
- Abort/cancel mechanism (if supported).
- Consistency checks with indexes and run reuse.

## UI Spec (Concrete)

### Page Layout
- **Header**: “Pipeline Control Center” + environment badge (dev/staging/prod) + admin‑only badge.
- **Left panel (Run Config)**: form to compose a run.
- **Right panel (Run Monitor)**: live status, logs, errors, artifacts.
- **Bottom panel (Recent Runs)**: table with filters and actions.

### Run Config Form
**Inputs**
- **Claim selection**
  - Multi‑select list of discovered claims (with doc count).
  - Search by claim ID / folder.
- **Stages**
  - Checkboxes: `Ingest`, `Classify`, `Extract`.
  - Presets: Full, Classify+Extract, Extract Only.
- **Run ID**
  - Auto‑generate (default) or custom run_id.
- **Model selection**
  - Classifier model (dropdown).
  - Extractor model (dropdown).
- **Options**
  - `Force overwrite` (toggle).
  - `Compute metrics` (toggle).
  - `Dry run` (toggle).
- **Buttons**
  - `Start Run`
  - `Preview` (dry‑run without execution)
  - `Reset`

**Validation**
- Must select at least one claim.
- If `Extract` is selected and `Classify` is not, show warning (allowed but risky).
- Run ID must be unique unless `Force overwrite` is enabled.

### Run Monitor Panel
- **Status header**: run_id, status (running/success/partial/failed), start time, elapsed time.
- **Progress**:
  - Overall progress bar (claims + docs).
  - Per‑claim progress list (claim_id, processed/total).
- **Phase metrics** (from summary):
  - ingestion/classification/extraction counts + durations.
  - quality gate: pass/warn/fail.
- **Errors list**:
  - doc_id, filename, phase, error message.
- **Artifacts**:
  - links to `manifest.json`, `summary.json`, `metrics.json`, `run.log`.
- **Actions**:
  - `Cancel run` (if running).
  - `Open run folder` (if local).
  - `Export summary` (download JSON).

### Recent Runs Table
- Columns: run_id, status, model(s), claims_count, docs_processed, started_at, completed_at.
- Filters: status, date range, model, claim_id.
- Row actions: open run, delete run, download summary.

## API Contract (Proposed)

### POST /api/pipeline/runs
**Request**
```json
{
  "claim_ids": ["claim_001", "claim_002"],
  "run_id": "run_20260112_120000_abc1234",
  "stages": ["ingest", "classify", "extract"],
  "classifier_model": "gpt-4o",
  "extractor_model": "gpt-4o-mini",
  "force": false,
  "compute_metrics": true,
  "dry_run": false
}
```
**Response**
```json
{ "run_id": "run_20260112_120000_abc1234", "status": "queued" }
```

### GET /api/pipeline/runs
List recent runs with filters.

### GET /api/pipeline/runs/{run_id}
Return manifest + summary + metrics + status.

### GET /api/pipeline/runs/{run_id}/logs
Tail or stream logs (polling ok).

### DELETE /api/pipeline/runs/{run_id}
Delete run (admin only).

### POST /api/pipeline/runs/{run_id}/cancel
Cancel active run.

## Audit Requirements
- Log every run start/stop/cancel/delete with:
  - user, timestamp, request payload, result status.

## Wireframe Notes (Text)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Pipeline Control Center                              [env] [admin] [user]   │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ Run Config                    │ Run Monitor                                  │
│ [Claim multi-select + search] │ Run: run_20260112_120000_abc1234   [Running]  │
│ [Stages: ☐Ingest ☐Classify ☐Extract | Presets]                                │
│ [Run ID: auto/custom]         │ Progress: ███████░  68%                      │
│ [Classifier model dropdown]   │ Claims: claim_001 4/6   claim_002 1/3         │
│ [Extractor model dropdown]    │ Phase metrics + quality gate                 │
│ [Force] [Metrics] [Dry run]   │ Errors list (doc_id, phase, msg)             │
│ [Start] [Preview] [Reset]     │ Artifacts (manifest/summary/metrics/log)     │
│                               │ [Cancel] [Export JSON] [Open folder]         │
├──────────────────────────────────────────────────────────────────────────────┤
│ Recent Runs (filters: status/date/model/claim)                               │
│ run_id | status | models | claims | docs | started | completed | actions     │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### Page Layout
- `PipelineControlCenterPage`
  - `RunConfigPanel`
  - `RunMonitorPanel`
  - `RecentRunsTable`
  - `TopBar`

### Run Config
- `ClaimMultiSelect`
- `StageSelector` (checkboxes + presets)
- `RunIdInput`
- `ModelSelectors` (classifier, extractor)
- `RunOptionsToggles` (force/metrics/dry-run)
- `RunActions` (start/preview/reset)

### Run Monitor
- `RunStatusHeader`
- `ProgressBar`
- `ClaimProgressList`
- `PhaseMetricsSummary`
- `QualityGateSummary`
- `ErrorList`
- `ArtifactsLinks`
- `RunActionsBar` (cancel/export/open)

### Recent Runs
- `RunFilters`
- `RunsTable`
- `RunRowActions` (open/delete/download)

## Implementation Task Breakdown

### UI
1. Create page scaffold + layout grid.
2. Implement Run Config controls with validation.
3. Implement Run Monitor panel (static mock data first).
4. Implement Recent Runs table + filters.
5. Wire API calls + polling.
6. Add admin‑only gating + confirmations.

### API / Backend
1. Define run request/response schemas.
2. Implement run trigger endpoint (calls pipeline).
3. Implement run status + logs endpoint.
4. Implement run delete + cancel endpoints.
5. Add audit logging.

### Testing
1. Unit tests for run config validation.
2. Unit tests for API client methods.
3. UI smoke tests for main panels.

## Next Step
Please answer the open questions. I’ll refine the requirements and turn this into a concrete UI spec (fields, states, and API contract).
