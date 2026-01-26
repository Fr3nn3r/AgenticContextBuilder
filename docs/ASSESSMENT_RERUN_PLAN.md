# Re-run Assessment with History & Live Progress

## Overview

Add capability to re-run claims assessment from the frontend with:
- History of all previous assessments preserved
- Live progress updates via WebSocket (token counts with up/down arrows)
- Floating progress card in bottom-right corner

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  CLAIM PIPELINE (new - wraps existing document pipeline)        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │Reconciliation│ -> │  Processing  │ -> │ Processing:      │  │
│  │   (stub)     │    │   (router)   │    │ Assessment (NSA) │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                   │                     │             │
│         └───────────────────┴─────────────────────┘             │
│                         WebSocket                               │
│                    (token up/down counts)                       │
└─────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

| Stage | Scope | Purpose |
|-------|-------|---------|
| ingestion | document | Existing - extract text from documents |
| classification | document | Existing - identify document type |
| extraction | document | Existing - extract structured fields |
| **reconciliation** | claim | **New** - aggregate facts across documents/runs |
| **processing** | claim | **New** - apply business logic (assessment, payout, etc.) |

### Key Design Decisions

1. **Claim pipeline wraps document pipeline** - Document-level stages unchanged, claim-level stages added separately
2. **Processing auto-discovery** - Customer implementations discovered from workspace config folder
3. **Keep all history** - Never delete previous assessments
4. **Disable concurrent runs** - Button disabled while assessment running
5. **Manual prompt versioning** - Version from YAML frontmatter in prompt.md

---

## Phase 1: Backend Core Infrastructure

### New Files

| File | Purpose |
|------|---------|
| `pipeline/claim_stages/__init__.py` | `ClaimStage` Protocol, `ClaimPipelineRunner` |
| `pipeline/claim_stages/context.py` | `ClaimContext` dataclass |
| `pipeline/claim_stages/reconciliation.py` | Stub that loads aggregated facts (TODO: proper impl) |
| `pipeline/claim_stages/processing.py` | Base class with auto-discovery registry |

### ClaimContext Dataclass

```python
@dataclass
class ClaimContext:
    claim_id: str
    workspace_id: str
    run_id: str

    # Loaded by reconciliation
    aggregated_facts: Optional[Dict] = None

    # Set by processing
    processing_type: str = "assessment"
    processing_result: Optional[Dict] = None

    # For streaming
    on_token_update: Optional[Callable[[int, int], None]] = None  # (input, output)

    # Compliance
    version_bundle_id: Optional[str] = None
    prompt_version: Optional[str] = None

    # Status
    status: str = "pending"
    error: Optional[str] = None
    current_stage: str = "setup"
```

### ClaimStage Protocol

```python
class ClaimStage(Protocol):
    """Protocol for claim-level pipeline stages."""

    name: str

    def run(self, context: ClaimContext) -> ClaimContext:
        """Execute stage logic and return updated context."""
```

---

## Phase 2: Assessment History Storage

### Current Structure (overwritten)
```
{workspace}/claims/{claim_id}/context/assessment.json
```

### New Structure (versioned)
```
{workspace}/claims/{claim_id}/context/
├── assessment.json              # Latest (copy for backwards compat)
└── assessments/
    ├── 2026-01-26T10-14-22_v1.2.0.json
    ├── 2026-01-26T15-30-00_v1.2.1.json
    └── index.json               # List of all assessments with metadata
```

### index.json Schema

```json
{
  "assessments": [
    {
      "id": "2026-01-26T10-14-22_v1.2.0",
      "filename": "2026-01-26T10-14-22_v1.2.0.json",
      "timestamp": "2026-01-26T10:14:22Z",
      "prompt_version": "1.2.0",
      "extraction_bundle_id": "abc123",
      "decision": "APPROVE",
      "confidence_score": 0.95,
      "is_current": false
    }
  ]
}
```

---

## Phase 3: WebSocket Streaming

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/claims/{claim_id}/assessment/run` | Start assessment, returns run_id |
| WS | `/api/claims/{claim_id}/assessment/ws/{run_id}` | Stream progress |

### WebSocket Message Types

**Server -> Client:**
```python
{"type": "stage", "stage": "reconciliation", "status": "running"}
{"type": "stage", "stage": "reconciliation", "status": "complete"}
{"type": "stage", "stage": "processing:assessment", "status": "running"}
{"type": "tokens", "input": 1250, "output": 89}
{"type": "tokens", "input": 1250, "output": 156}
{"type": "complete", "decision": "APPROVE", "assessment_id": "..."}
{"type": "error", "message": "..."}
```

---

## Phase 4: Processing Auto-Discovery

### Workspace Config Structure

```
{workspace}/config/
└── processing/
    └── assessment/
        ├── config.yaml          # Processing config
        └── prompt.md            # Assessment prompt with version in frontmatter
```

### config.yaml

```yaml
type: assessment
version: "1.2.0"
model: gpt-4o
temperature: 0.2
max_tokens: 4096
prompt_file: prompt.md
```

### prompt.md Frontmatter

```yaml
---
version: "1.2.0"
description: "NSA claims assessment prompt"
---
system:
You are a claims assessor...
```

### Auto-Discovery Logic

```python
@classmethod
def discover_processors(cls, workspace_config_dir: Path) -> Dict[str, ProcessorConfig]:
    """Scan {workspace}/config/processing/ for processor configs."""
    processors = {}
    processing_dir = workspace_config_dir / "processing"
    if processing_dir.exists():
        for subdir in processing_dir.iterdir():
            if subdir.is_dir() and (subdir / "config.yaml").exists():
                processors[subdir.name] = load_processor_config(subdir)
    return processors
```

---

## Phase 5: Frontend Changes

### New Components

| Component | Purpose |
|-----------|---------|
| `AssessmentProgressCard.tsx` | Floating bottom-right progress card |
| `useAssessmentWebSocket.ts` | WebSocket hook for assessment streaming |

### Modified Components

| Component | Changes |
|-----------|---------|
| `ClaimAssessmentTab.tsx` | Add "Re-run" button, "View previous" link, version display |
| `ClaimExplorer/index.tsx` | WebSocket connection management |

### AssessmentProgressCard Design

```
┌─────────────────────────────┐
│ Running Assessment...       │
│                             │
│  ↑ 1,250 tokens             │
│  ↓ 156 tokens               │
│                             │
│  Stage: Processing          │
│  ████████░░░░░░░ 60%        │
└─────────────────────────────┘
```

---

## File Changes Summary

### Backend Core (new files)
- `src/context_builder/pipeline/claim_stages/__init__.py`
- `src/context_builder/pipeline/claim_stages/context.py`
- `src/context_builder/pipeline/claim_stages/reconciliation.py`
- `src/context_builder/pipeline/claim_stages/processing.py`

### Backend Core (modify)
- `src/context_builder/api/routers/claims.py` - Add run + WebSocket endpoints
- `src/context_builder/api/services/assessment.py` - History storage

### Frontend (new files)
- `ui/src/components/ClaimExplorer/AssessmentProgressCard.tsx`
- `ui/src/hooks/useAssessmentWebSocket.ts`

### Frontend (modify)
- `ui/src/components/ClaimExplorer/ClaimAssessmentTab.tsx`

---

## Implementation Order

1. **Phase 1**: Backend core infrastructure (claim stages)
2. **Phase 2**: Assessment history storage
3. **Phase 3**: WebSocket streaming endpoints
4. **Phase 4**: Processing auto-discovery
5. **Phase 5**: Frontend components

---

## Future Considerations

- **Proper reconciliation**: Currently stub that loads facts. TODO: implement conflict resolution across extraction runs.
- **Additional processors**: `processing:payout`, `processing:fraud`, etc.
- **Batch assessment**: Run assessment across multiple claims
- **Assessment comparison**: UI to diff two assessment versions
