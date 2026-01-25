# Week 3: Pipeline Stage Extraction Plan

## Objective
Extract stages and helpers from `pipeline/run.py` (1470 lines) to reduce it to ~400 lines of orchestration logic.

---

## Current File Analysis

| Section | Lines | Description |
|---------|-------|-------------|
| Dataclasses | 75-180 (~105) | IngestionResult, PhaseTimings, StageConfig, etc. |
| I/O Helpers | 182-190, 53-73 (~30) | _write_json, _write_json_atomic, _get_workspace_logs_dir |
| Metadata Helpers | 192-372 (~180) | Git info, hashes, manifest, snapshots |
| Ingestion Logic | 374-587 (~213) | _ingest_document, _ingest_with_provider, _load_existing_ingestion |
| Classification Helper | 589-615 (~26) | _load_existing_classification |
| Stage Classes | 617-898 (~281) | DocumentContext, IngestionStage, ClassificationStage, ExtractionStage |
| process_document | 900-1011 (~111) | Document orchestration |
| _run_extraction | 1013-1108 (~95) | Extraction execution |
| _compute_phase_aggregates | 1110-1173 (~63) | Aggregate metrics |
| process_claim | 1175-1471 (~296) | Claim orchestration |

---

## Extraction Plan

### File 1: `pipeline/stages/__init__.py`
Re-export all stage classes and context for easy imports.

```python
from context_builder.pipeline.stages.context import (
    DocumentContext,
    DocResult,
    ClaimResult,
    PhaseTimings,
    StageConfig,
    PipelineProviders,
    IngestionResult,
)
from context_builder.pipeline.stages.ingestion import IngestionStage
from context_builder.pipeline.stages.classification import ClassificationStage
from context_builder.pipeline.stages.extraction import ExtractionStage

__all__ = [
    "DocumentContext",
    "DocResult",
    "ClaimResult",
    "PhaseTimings",
    "StageConfig",
    "PipelineProviders",
    "IngestionResult",
    "IngestionStage",
    "ClassificationStage",
    "ExtractionStage",
]
```

### File 2: `pipeline/stages/context.py` (~120 lines)
Move all dataclasses that represent pipeline state:

| Class | Current Lines | Purpose |
|-------|---------------|---------|
| `IngestionResult` | 75-82 | Result of document ingestion |
| `PhaseTimings` | 85-92 | Per-phase timing breakdown |
| `StageConfig` | 95-135 | Stage-selective execution config |
| `PipelineProviders` | 138-145 | DI for external providers |
| `DocResult` | 148-168 | Single document result |
| `ClaimResult` | 171-180 | Claim processing result |
| `DocumentContext` | 617-672 | Mutable context between stages |

**Dependencies:**
- `context_builder.pipeline.discovery.DiscoveredDocument`
- `context_builder.pipeline.paths.DocPaths, RunPaths`
- `context_builder.pipeline.writer.ResultWriter`
- `context_builder.schemas.run_errors.PipelineStage`

### File 3: `pipeline/stages/ingestion.py` (~230 lines)
Move ingestion stage and helpers:

| Item | Current Lines | Purpose |
|------|---------------|---------|
| `IngestionStage` class | 676-735 | Stage class with run() method |
| `_ingest_document()` | 374-440 | Main ingestion router |
| `_ingest_with_provider()` | 442-558 | Provider-specific ingestion |
| `_load_existing_ingestion()` | 560-587 | Load from existing pages.json |

**Dependencies:**
- `context_builder.config.tenant.get_tenant_config`
- `context_builder.pipeline.text.build_pages_json, build_pages_json_from_azure_di`
- Stage context classes from `context.py`

### File 4: `pipeline/stages/classification.py` (~110 lines)
Move classification stage and helper:

| Item | Current Lines | Purpose |
|------|---------------|---------|
| `ClassificationStage` class | 738-829 | Stage class with run() method |
| `_load_existing_classification()` | 589-615 | Load from existing doc.json |

**Dependencies:**
- Stage context classes from `context.py`

### File 5: `pipeline/stages/extraction.py` (~180 lines)
Move extraction stage and runner:

| Item | Current Lines | Purpose |
|------|---------------|---------|
| `ExtractionStage` class | 832-898 | Stage class with run() method |
| `_run_extraction()` | 1013-1108 | Actual extraction execution |

**Dependencies:**
- `context_builder.extraction.extractors`
- `context_builder.pipeline.text.pages_json_to_page_content`
- `context_builder.schemas.extraction_result`
- `context_builder.services.compliance.pii`
- Stage context classes from `context.py`

### File 6: `pipeline/helpers/__init__.py`
Re-export helper functions.

### File 7: `pipeline/helpers/metadata.py` (~180 lines)
Move manifest and metadata helpers:

| Function | Current Lines | Purpose |
|----------|---------------|---------|
| `_get_git_info()` | 192-218 | Get git commit info |
| `_compute_templates_hash()` | 220-234 | Hash extraction specs |
| `_compute_workspace_config_hash()` | 236-263 | Hash workspace config |
| `_snapshot_workspace_config()` | 265-303 | Copy config to run snapshot |
| `_write_manifest()` | 317-367 | Write manifest.json |
| `_mark_run_complete()` | 369-372 | Create .complete marker |
| `_compute_phase_aggregates()` | 1110-1173 | Aggregate phase metrics |

**Dependencies:**
- `context_builder.pipeline.paths.RunPaths`
- `context_builder.pipeline.writer.ResultWriter`
- `context_builder.storage.workspace_paths.get_workspace_config_dir`

### File 8: `pipeline/helpers/io.py` (~40 lines)
Move I/O helpers:

| Function | Current Lines | Purpose |
|----------|---------------|---------|
| `_get_workspace_logs_dir()` | 53-73 | Derive logs dir from output base |
| `_write_json()` | 182-185 | Write JSON with utf-8 |
| `_write_json_atomic()` | 187-190 | Atomic JSON write |

### File 9: `pipeline/run.py` (~400 lines remaining)
Keep orchestration only:

| Item | Current Lines | Purpose |
|------|---------------|---------|
| Module docstring + imports | 1-50 | Setup |
| `_setup_run_logging()` | 305-315 | Run-specific logging |
| `process_document()` | 900-1011 | Document orchestration |
| `process_claim()` | 1175-1471 | Claim orchestration |

---

## Migration Order (Lowest Risk First)

### Step 1: Create `stages/context.py`
- Move all dataclasses
- Update imports in `run.py` to import from new location
- Run tests

### Step 2: Create `helpers/io.py` and `helpers/metadata.py`
- Move helper functions
- Update imports in `run.py`
- Run tests

### Step 3: Create `stages/ingestion.py`
- Move IngestionStage and ingestion helpers
- Update imports
- Run tests

### Step 4: Create `stages/classification.py`
- Move ClassificationStage and classification helper
- Update imports
- Run tests

### Step 5: Create `stages/extraction.py`
- Move ExtractionStage and _run_extraction
- Update imports
- Run tests

### Step 6: Create `__init__.py` files
- Add re-exports for clean API
- Verify all imports still work
- Run full test suite

---

## Backwards Compatibility

To maintain compatibility during migration:

1. **Keep re-exports in `run.py`** for any classes/functions imported externally:
   ```python
   # Backwards compatibility re-exports
   from context_builder.pipeline.stages.context import (
       DocResult, ClaimResult, StageConfig, ...
   )
   ```

2. **Update `pipeline/__init__.py`** to export from new locations

3. **Check external callers:**
   - `cli.py` - imports `process_claim`, `StageConfig`, `PipelineStage`
   - `api/routers/pipeline.py` - imports `process_claim`, `process_document`
   - Test files - various imports

---

## Verification After Each Step

```bash
# Run unit tests
python -m pytest tests/unit/ --no-cov -q \
  --ignore=tests/unit/test_compliance_factory.py \
  --ignore=tests/unit/test_crypto.py \
  --ignore=tests/unit/test_encryption.py \
  --ignore=tests/unit/test_encrypted_decision_storage.py \
  --ignore=tests/unit/test_encrypted_llm_storage.py \
  --ignore=tests/unit/test_envelope_encryption.py

# Verify imports work
python -c "from context_builder.pipeline.run import process_claim, process_document; print('OK')"
python -c "from context_builder.pipeline.stages import IngestionStage, ClassificationStage, ExtractionStage; print('OK')"

# Run pipeline CLI to verify end-to-end
python -m context_builder.cli pipeline --help
```

---

## Expected Result

| File | Before | After |
|------|--------|-------|
| `pipeline/run.py` | 1470 lines | ~400 lines |
| `pipeline/stages/context.py` | - | ~120 lines |
| `pipeline/stages/ingestion.py` | - | ~230 lines |
| `pipeline/stages/classification.py` | - | ~110 lines |
| `pipeline/stages/extraction.py` | - | ~180 lines |
| `pipeline/helpers/metadata.py` | - | ~180 lines |
| `pipeline/helpers/io.py` | - | ~40 lines |

**Total: ~1260 lines** (slight increase due to imports/docstrings, but much better organized)

---

## Risk Mitigation

1. **Git commit after each step** - Easy rollback if something breaks
2. **Run tests after each extraction** - Catch issues early
3. **Keep re-exports** - External code continues to work
4. **Incremental migration** - One file at a time

---

## Open Questions

1. Should `_setup_run_logging()` go to helpers or stay in run.py?
   - **Recommendation:** Keep in run.py since it's only used there

2. Should we create a `stages/base.py` for the Stage protocol?
   - **Recommendation:** No, `pipeline/stages.py` already exists with `PipelineRunner`

3. Should `IngestionResult` go in `context.py` or `ingestion.py`?
   - **Recommendation:** Keep in `context.py` with other dataclasses for consistency
