# Handoff: Assessment Re-run Feature

**Date**: 2026-01-26
**Status**: All Phases Complete
**Plan Document**: `docs/ASSESSMENT_RERUN_PLAN.md`

---

## Summary

Adding capability to re-run claims assessment from the frontend with:
- History of all previous assessments preserved
- Live progress updates via WebSocket (token counts with up/down arrows)
- Floating progress card in bottom-right corner

## Architecture Decisions Made

1. **Claim pipeline wraps document pipeline** - Document-level stages (ingestion, classification, extraction) unchanged. New claim-level stages (reconciliation, processing) added separately.

2. **New stage terminology**:
   - `reconciliation` - Aggregates facts across documents/runs (currently stub)
   - `processing` - Generic business logic stage with subtypes (e.g., `processing:assessment`)

3. **Auto-discovery** - Processing types discovered from `{workspace}/config/processing/{type}/`

4. **History storage** - Keep all assessments forever (versioned files, not overwrite)

5. **Concurrent runs** - Disabled (button disabled while running)

6. **Prompt versioning** - Manual version in YAML frontmatter of prompt.md

---

## Completed (Phase 1)

### New Files Created

```
src/context_builder/pipeline/claim_stages/
├── __init__.py           # ClaimStage Protocol, ClaimPipelineRunner, exports
├── context.py            # ClaimContext, ClaimStageConfig, ClaimStageTimings
├── reconciliation.py     # Stub - loads claim_facts.json (TODO: proper impl)
└── processing.py         # Auto-discovery, processor registry
```

### Key Components

**ClaimContext** (`context.py`):
- `claim_id`, `workspace_path`, `run_id`
- `aggregated_facts` - loaded by reconciliation
- `processing_result` - set by processing
- `on_token_update` callback - for streaming token counts
- `on_stage_update` callback - for stage progress
- `prompt_version`, `extraction_bundle_id` - for versioning

**ClaimPipelineRunner** (`__init__.py`):
- Runs stages in order
- Calls phase start/end callbacks
- Early exit on error
- Notifies context of stage updates

**ReconciliationStage** (`reconciliation.py`):
- Currently just loads existing `claim_facts.json`
- Has TODO marker for proper conflict resolution across runs

**ProcessingStage** (`processing.py`):
- Auto-discovers from `{workspace}/config/processing/`
- Loads `config.yaml` and `prompt.md` with frontmatter version
- Uses registry pattern: `register_processor()`, `get_processor()`
- Delegates to registered processor implementations

### Verified Working

```bash
python -c "from context_builder.pipeline.claim_stages import ClaimContext, ClaimPipelineRunner, ReconciliationStage, ProcessingStage, register_processor; print('OK')"
```

---

## Completed Phases

### Phase 2: Assessment History Storage (Complete)

**Files modified**:
- `src/context_builder/api/services/assessment.py`:
  - Added `save_assessment()` - saves versioned assessment with timestamp
  - Added `get_assessment_by_id()` - retrieves specific historical assessment
  - Added `_get_assessments_dir()`, `_load_assessments_index()`, `_save_assessments_index()`
  - Updated `get_assessment_history()` - returns full history from index.json

**Storage structure**:
```
{workspace}/claims/{claim_id}/context/
├── assessment.json              # Latest (backwards compat)
└── assessments/
    ├── 2026-01-26T10-14-22_v1.0.0.json
    └── index.json               # Metadata for all assessments
```

### Phase 3: WebSocket Streaming (Complete)

**Files modified**:
- `src/context_builder/api/routers/claims.py`:
  - Added `POST /api/claims/{claim_id}/assessment/run` - starts assessment, returns run_id
  - Added `WS /api/claims/{claim_id}/assessment/ws/{run_id}` - streams progress
  - Added `GET /api/claims/{claim_id}/assessment/{assessment_id}` - get historical assessment
  - Added `GET /api/claims/{claim_id}/assessment/status/{run_id}` - get run status
- `src/context_builder/api/dependencies.py`:
  - Added `get_workspace_path()` helper

**WebSocket messages**:
```json
{"type": "sync", "run_id": "...", "claim_id": "...", "status": "..."}
{"type": "stage", "stage": "reconciliation", "status": "running"}
{"type": "tokens", "input": 1250, "output": 156}
{"type": "complete", "decision": "APPROVE", "assessment_id": "..."}
{"type": "error", "message": "..."}
```

### Phase 4: Assessment Processor Implementation (Complete)

**New files created**:
- `src/context_builder/pipeline/claim_stages/assessment_processor.py`:
  - `AssessmentProcessor` class implementing `Processor` protocol
  - Auto-registers as "assessment" processor on import
  - Calls OpenAI with audited client for compliance logging
  - Tracks token usage via callbacks

**Workspace config created**:
```
workspaces/nsa/config/processing/assessment/
├── config.yaml    # type, version, model settings
└── prompt.md      # Assessment prompt with YAML frontmatter version
```

### Phase 5: Frontend Components (Complete)

**New files created**:
- `ui/src/hooks/useAssessmentWebSocket.ts`:
  - `useAssessmentWebSocket()` hook for WebSocket connection management
  - Tracks progress state (stage, tokens, status)
  - Handles reconnection and cleanup

- `ui/src/components/ClaimExplorer/AssessmentProgressCard.tsx`:
  - Floating progress card in bottom-right corner
  - Shows stage progress, token counts with up/down arrows
  - Completion/error states with appropriate styling

**Files modified**:
- `ui/src/components/ClaimExplorer/ClaimAssessmentTab.tsx`:
  - Added "Re-run" button in decision banner
  - Added "History" link (when `onViewHistory` prop provided)
  - Integrated WebSocket hook for progress tracking
  - Shows progress card during assessment runs

---

## Related Changes Already Made (This Session)

1. **Branding update**: Changed "ContextBuilder" to "True AIm" across UI
2. **Logo**: Added `ui/public/trueaim-logo.png`
3. **Currency fix**: Assessment payout now shows actual currency (CHF) instead of hardcoded $

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `docs/ASSESSMENT_RERUN_PLAN.md` | Full implementation plan |
| `pipeline/claim_stages/` | New claim-level pipeline (Phase 1) |
| `api/services/assessment.py` | Current assessment service (modify for Phase 2) |
| `api/routers/claims.py` | Claims API (modify for Phase 3) |
| `api/websocket.py` | Existing WebSocket manager (reuse pattern) |
| `components/ClaimExplorer/ClaimAssessmentTab.tsx` | Assessment UI (modify for Phase 5) |

---

## Commands

```bash
# Verify claim_stages module
python -c "from context_builder.pipeline.claim_stages import *; print('OK')"

# Run tests (if any added)
python -m pytest tests/unit/ -k "claim_stages" --no-cov -q
```

---

## Notes

- Reconciliation is a stub with TODO - proper implementation should resolve conflicts across extraction runs
- Processing auto-discovery requires `config.yaml` in each processor subdirectory
- Processor implementations must be registered via `register_processor()`
- WebSocket pattern exists for pipeline progress - adapt for assessment
