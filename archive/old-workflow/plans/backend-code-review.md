## Backend Code Review (Pipeline/Services)

Findings are ordered by severity.

### High Severity
1) **Cancelled runs can leave claims moved to input without cleanup**  
`src/context_builder/api/services/pipeline.py:102–168`  
If a run is cancelled after `move_to_input()` but before per‑claim processing, `_run_pipeline` returns without `cleanup_staging()` / `cleanup_input()`. This can strand input folders and break later runs.  
**Fix:** On any early cancel/return, iterate `input_paths` and cleanup.

2) **No authorization / admin gating on pipeline endpoints**  
`src/context_builder/api/main.py:1060–1149`  
Pipeline actions are open. Requirements say admin‑only.  
**Fix:** Add auth/role guard (API key/header or RBAC) for `/api/pipeline/*`.

3) **“Partial” run status is not represented**  
`src/context_builder/api/services/pipeline.py:247–288`  
Mixed success/failure sets status to `COMPLETED`.  
**Fix:** Add `PARTIAL` to `PipelineStatus` and set explicitly.

### Medium Severity
4) **Run listing is in‑memory only**  
`src/context_builder/api/services/pipeline.py:309–343`, `src/context_builder/api/main.py:1170–1185`  
`list_pipeline_runs()` returns only active runs; history disappears on restart.  
**Fix:** Load persisted runs from output/registry or global run dir on startup.

5) **Start pipeline accepts empty claim list**  
`src/context_builder/api/main.py:1054–1108`  
Empty `claim_ids` creates a run with no docs.  
**Fix:** Validate non‑empty list (400).

6) **Audit trail not implemented**  
Requirement says audit all actions; no durable audit log.  
**Fix:** Append JSONL audit log for start/cancel/delete/status.

### Low Severity / Operational
7) **Cancel does not persist run snapshot**  
Cancelled runs may never be written to global run dir.  
**Fix:** Persist run state on cancel.

8) **Single model field for both classifier/extractor**  
`PipelineRunRequest` and persisted run model don’t track separate models.  
**Fix:** Add `classifier_model` and `extractor_model` fields.

### Testing Gaps
- No unit tests for cancellation cleanup or persisted run listing.
- No tests for auth/role gating on pipeline endpoints.
