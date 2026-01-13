# Phase 3: Backend Pipeline Service - Complete

## Summary
Created backend infrastructure for async pipeline execution with WebSocket-based real-time progress updates.

## Files Created
- `src/context_builder/api/services/pipeline.py` - PipelineService class with:
  - Async pipeline execution with background tasks
  - Run tracking with per-document phase status
  - Cancellation support with asyncio.Event
  - Progress callback integration

- `tests/unit/test_pipeline_service.py` - 15 unit tests covering:
  - Service initialization
  - Run ID generation
  - Start pipeline (creates tracking, initializes doc progress)
  - Cancel pipeline
  - Get run status
  - Cancellation checking
  - Data classes (DocProgress, PipelineRun, enums)

## Files Modified
- `src/context_builder/api/services/__init__.py` - Export new service and enums
- `src/context_builder/api/main.py` - Added:
  - WebSocket ConnectionManager for broadcasting
  - Pipeline endpoints:
    - `POST /api/pipeline/run` - Start pipeline
    - `POST /api/pipeline/cancel/{run_id}` - Cancel pipeline
    - `GET /api/pipeline/status/{run_id}` - Get run status
    - `GET /api/pipeline/runs` - List all runs
  - WebSocket endpoint:
    - `WS /api/pipeline/ws/{run_id}` - Real-time progress

## Key Types

```python
class DocPhase(Enum):
    PENDING, INGESTING, CLASSIFYING, EXTRACTING, DONE, FAILED

class PipelineStatus(Enum):
    PENDING, RUNNING, COMPLETED, FAILED, CANCELLED

@dataclass
class DocProgress:
    doc_id, claim_id, filename, phase, error

@dataclass
class PipelineRun:
    run_id, claim_ids, status, docs, started_at, completed_at, summary
```

## WebSocket Protocol

**Server -> Client:**
```json
{"type": "sync", "run_id": "...", "status": "...", "docs": {...}}
{"type": "doc_progress", "doc_id": "...", "phase": "...", "error": ...}
{"type": "run_complete", "run_id": "...", "status": "...", "summary": {...}}
{"type": "run_cancelled", "run_id": "..."}
{"type": "ping"}
```

**Client -> Server:**
```
"pong" (keepalive response)
```

## Test Results
```
15 passed in 1.09s
```

## How to Test Manually
```bash
# Start API server
uvicorn context_builder.api.main:app --reload --port 8000

# Start pipeline (assuming files already uploaded)
curl -X POST "http://localhost:8000/api/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{"claim_ids": ["TEST-001"]}'

# Check status
curl "http://localhost:8000/api/pipeline/status/{run_id}"

# WebSocket (use wscat or browser)
wscat -c "ws://localhost:8000/api/pipeline/ws/{run_id}"
```
