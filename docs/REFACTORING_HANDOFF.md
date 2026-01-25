# Backend Refactoring Handoff

**Date:** 2025-01-25
**Status:** Week 3 Complete - Pipeline Stage Extraction Done

## Summary

Backend refactoring is now complete across both the API layer and pipeline layer:
- `api/main.py`: 2723 → 160 lines (**94% reduction**)
- `pipeline/run.py`: 1470 → 479 lines (**67% reduction**)

## Completed Work

### Week 1: API Initialization Extraction
- Created `api/startup.py` - App initialization logic
- Created `api/websocket.py` - WebSocket connection manager
- Created `api/dependencies.py` - Service factories and auth dependencies

### Week 2: Router Extraction
Created 14 router files in `api/routers/`:

| Router | Lines | Endpoints | Description |
|--------|-------|-----------|-------------|
| `system.py` | ~50 | 3 | Health, version, debug |
| `auth.py` | ~80 | 4 | Login, logout, me, token refresh |
| `admin_users.py` | ~120 | 5 | User CRUD operations |
| `admin_workspaces.py` | ~150 | 7 | Workspace management |
| `claims.py` | ~95 | 5 | Claims listing, review, facts |
| `documents.py` | ~210 | 10 | Doc operations, templates, truth |
| `insights.py` | ~290 | 18 | Analytics, metrics, token costs |
| `evolution.py` | ~30 | 2 | Pipeline evolution tracking |
| `classification.py` | ~280 | 5 | Classification review UI |
| `upload.py` | ~180 | 8 | Document upload, staging |
| `pipeline.py` | ~530 | 14 + WS | Pipeline execution, configs |
| `compliance.py` | ~280 | 8 | Ledger, version bundles |

### Week 3: Pipeline Stage Extraction (Just Completed)
Extracted stages and helpers from `pipeline/run.py`:

| New File | Lines | Contents |
|----------|-------|----------|
| `stages/__init__.py` | 91 | Re-exports + PipelineRunner |
| `stages/context.py` | 176 | 7 dataclasses (DocumentContext, DocResult, etc.) |
| `stages/ingestion.py` | 296 | IngestionStage + ingestion helpers |
| `stages/classification.py` | 137 | ClassificationStage + helper |
| `stages/extraction.py` | 186 | ExtractionStage + run_extraction |
| `helpers/__init__.py` | 31 | Re-exports |
| `helpers/io.py` | 38 | JSON write utilities |
| `helpers/metadata.py` | 272 | Git info, manifest, hashes, snapshots |

**run.py now contains only:**
- `_setup_run_logging()` - Run-specific logging
- `process_document()` - Document orchestration
- `process_claim()` - Claim orchestration

## Test Results
```
1049 passed, 2 failed (pre-existing fnol_form issue), 6 skipped (crypto)
```

## Architecture After Refactoring

```
api/
├── main.py              # 160 lines - App setup only
├── dependencies.py      # Service factories, auth
├── startup.py           # Initialization
├── websocket.py         # WS connection manager
├── routers/             # 14 endpoint files
└── services/            # Business logic

pipeline/
├── run.py               # 479 lines - Orchestration only
├── stages/
│   ├── __init__.py      # Re-exports + PipelineRunner
│   ├── context.py       # Dataclasses
│   ├── ingestion.py     # IngestionStage
│   ├── classification.py # ClassificationStage
│   └── extraction.py    # ExtractionStage
├── helpers/
│   ├── __init__.py      # Re-exports
│   ├── io.py            # I/O utilities
│   └── metadata.py      # Manifest, git info, hashes
└── (other modules)      # discovery, paths, text, writer, etc.
```

---

## Next Steps (Phase 2 Options)

The major "god files" have been addressed. Further refactoring is optional based on priorities.

### Option A: Service Layer Refactoring (Medium Priority)
Move business logic out of routers into dedicated services:
- `claims_service.py` - Claims business logic
- `documents_service.py` - Document operations
- `insights_service.py` - Analytics calculations

**Benefit:** Cleaner separation, easier unit testing
**Effort:** 2-3 days

### Option B: Schema Consolidation (Low Priority)
- Move Pydantic models to `schemas/` directory
- Remove duplicate model definitions across files
- Add stricter validation

**Benefit:** Single source of truth for data models
**Effort:** 1-2 days

### Option C: Storage Layer Cleanup (Low Priority)
- Consolidate storage abstractions
- Remove deprecated code paths
- Improve error handling consistency

**Benefit:** Cleaner storage layer
**Effort:** 2-3 days

### Option D: Security Fixes (High Priority)
From BACKLOG.md - should be done before production:
- SEC-01: Upgrade password hashing (SHA-256 → bcrypt)
- SEC-02: Remove default credentials ("su" password)
- SEC-03: Encrypt session tokens
- SEC-04: Add login rate limiting

**Benefit:** Production security
**Effort:** 1 day

### Option E: Feature Work
The codebase is now well-structured. Could shift to feature work:
- Claim Explorer enhancements
- Additional extractors
- Dashboard improvements

---

## Breaking Changes

Helper functions renamed (underscore prefix removed):
| Old Name | New Location |
|----------|--------------|
| `_load_existing_ingestion` | `stages.ingestion.load_existing_ingestion` |
| `_load_existing_classification` | `stages.classification.load_existing_classification` |
| `_compute_workspace_config_hash` | `helpers.metadata.compute_workspace_config_hash` |
| `_snapshot_workspace_config` | `helpers.metadata.snapshot_workspace_config` |

All symbols remain importable from `pipeline.run` for backwards compatibility.

---

## Commands to Verify

```bash
# Check line counts
wc -l src/context_builder/api/main.py
wc -l src/context_builder/pipeline/run.py

# Verify imports
python -c "from context_builder.api import main; print('API OK')"
python -c "from context_builder.pipeline.run import process_claim, process_document; print('Pipeline OK')"

# Run tests
python -m pytest tests/unit/ --no-cov -q \
  --ignore=tests/unit/test_compliance_factory.py \
  --ignore=tests/unit/test_crypto.py \
  --ignore=tests/unit/test_encryption.py \
  --ignore=tests/unit/test_encrypted_decision_storage.py \
  --ignore=tests/unit/test_encrypted_llm_storage.py \
  --ignore=tests/unit/test_envelope_encryption.py
```

## Known Issues
1. **fnol_form catalog tests failing** - Pre-existing issue, not related to refactoring
2. **Crypto tests skipped** - Require `pycryptodome` package

## Reference
- Week 2 plan: `docs/REFACTORING_WEEK2_PLAN.md`
- Week 3 plan: `docs/REFACTORING_WEEK3_PLAN.md`
- Developer guidelines: `docs/DEVELOPER_GUIDELINES.md`

## Commits
- `02d4d4a` - fix: rename workspace nsa-2 to nsa
- `f6d74a1` - docs: add Week 2 router extraction plan
- `458ecfa` - refactor: extract startup, websocket, and dependencies from main.py
- `00d17be` - refactor: extract pipeline stages from run.py into modular structure
