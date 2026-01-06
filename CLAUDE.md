# CLAUDE.md - ContextBuilder Project Guide

## Principles (Priority Order)
**Correctness > Security/Privacy > Maintainability (SSOT) > Simplicity (YAGNI) > Style**

### Operating Mode
- **Trivial changes** (typos, renames, small bugfix): implement immediately
- **Non-trivial** (core logic, data model, multi-file refactor):
  1. 3-6 bullet plan
  2. Ask only *blocking* questions (max 5)
  3. If answers missing, proceed with stated assumptions + smallest safe change

### Code Standards
- **SSOT**: One place for state/logic; no duplicated rules
- **SOLID** pragmatically; no speculative refactors
- **Naming**: Self-documenting, semantic density (`pendingClaims` not `data`)
- **Comments**: Explain *why*, edge cases, non-obvious constraints only
- **Conventions**: Python snake_case, TypeScript camelCase, classes PascalCase
- **Error handling**: Never swallow errors; log at boundaries without secrets
- **Testing**: Add/update unit tests for new/changed logic (PyTest/Jest)

---

## Project Overview

**ContextBuilder** is an **insurance claims document processing pipeline** that:
1. **Ingests** documents (PDFs, images, text) via Azure DI or OpenAI Vision
2. **Classifies** document types (loss_notice, police_report, insurance_policy)
3. **Extracts** structured fields with provenance tracking
4. **Assesses** quality with automated gates (pass/warn/fail)
5. **Enables** human QA labeling via React UI

**Tech Stack:**
- Backend: Python 3.9+, FastAPI, OpenAI/Azure APIs, Pydantic
- Frontend: React 18, TypeScript, Tailwind CSS, Vite
- Storage: File-based JSON (no database)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT DOCUMENTS                          │
│                   (PDFs, Images, Text files)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PIPELINE (src/context_builder/pipeline/)                        │
│  discovery.py → run.py → paths.py → text.py → state.py          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   INGESTION   │   │ CLASSIFICATION  │   │   EXTRACTION    │
│   (impl/)     │   │(classification/)│   │  (extraction/)  │
├───────────────┤   ├─────────────────┤   ├─────────────────┤
│ Azure DI      │   │ OpenAI Classify │   │ GenericExtractor│
│ OpenAI Vision │   │ Doc type detect │   │ Field specs     │
│ Tesseract     │   │ Language detect │   │ Normalizers     │
└───────────────┘   └─────────────────┘   └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ OUTPUT: output/claims/{claim_id}/                               │
│  ├─ docs/{doc_id}/meta/, text/, source/                         │
│  └─ runs/{run_id}/extraction/, context/, labels/, logs/         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ QA CONSOLE (api/ + ui/)                                         │
│  FastAPI backend → React frontend (Claim Workspace)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Modules

### Backend (`src/context_builder/`)

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `pipeline/` | Orchestration | `run.py` (main), `discovery.py`, `paths.py` |
| `impl/` | Ingestion providers | `azure_di_ingestion.py`, `openai_vision_ingestion.py` |
| `classification/` | Document type detection | `openai_classifier.py` |
| `extraction/` | Field extraction | `extractors/generic.py`, `spec_loader.py`, `normalizers.py` |
| `schemas/` | Pydantic models | `extraction_result.py`, `label.py` |
| `api/` | FastAPI backend | `main.py` |
| `utils/` | Helpers | `prompt_loader.py`, `hashing.py`, `file_utils.py` |

### Frontend (`ui/src/`)

| Component | Purpose |
|-----------|---------|
| `App.tsx` | Main routing, state management |
| `ClaimsTable.tsx` | Claim Workspace - list with KPIs, filters, Document Pack Queue |
| `DocReview.tsx` | Extraction Review - split view for labeling |
| `FieldsTable.tsx` | Field display with keyboard shortcuts (1/2/3, n/p) |
| `PageViewer.tsx` | Document text with provenance highlighting |
| `Sidebar.tsx` | Navigation |
| `types/index.ts` | TypeScript interfaces |
| `api/client.ts` | API client functions |

---

## Data Flow

```
Document → Discovery → Ingestion → pages.json → Classification → Extraction → Quality Gate
                                                                      ↓
                                                              ExtractionResult
                                                              (fields + provenance)
                                                                      ↓
                                                              Human QA Labels
```

### Key Data Structures

**ExtractionResult** (output of extraction):
```python
{
  "schema_version": "extraction_result_v1",
  "run": { "run_id", "model", "extractor_version", "input_hashes" },
  "doc": { "doc_id", "doc_type", "doc_type_confidence", "language", "page_count" },
  "pages": [{ "page", "text", "text_md5" }],
  "fields": [{
    "name", "value", "normalized_value", "confidence",
    "status": "present|missing|uncertain",
    "provenance": [{ "page", "char_start", "char_end", "text_quote" }]
  }],
  "quality_gate": { "status": "pass|warn|fail", "missing_required_fields" }
}
```

**LabelResult** (human QA output):
```python
{
  "schema_version": "label_v1",
  "doc_id", "claim_id",
  "review": { "reviewer", "reviewed_at", "notes" },
  "field_labels": [{ "field_name", "judgement": "correct|incorrect|unknown" }],
  "doc_labels": { "doc_type_correct", "text_readable" }
}
```

---

## Output Folder Structure

```
output/claims/{claim_id}/
├── docs/{doc_id}/
│   ├── source/original.{pdf|jpg|txt}
│   ├── text/pages.json
│   └── meta/doc.json
└── runs/{run_id}/
    ├── extraction/{doc_id}.json
    ├── context/{doc_id}.json
    ├── labels/{doc_id}.labels.json
    └── logs/summary.json
```

---

## Running the Project

### Backend API
```bash
cd src/context_builder
uvicorn api.main:app --reload --port 8000
```

### Frontend UI
```bash
cd ui
npm install
npm run dev    # Development (port 5173)
npm run build  # Production build
```

### Pipeline CLI
```bash
# Process documents
python -m context_builder.cli acquire -p azure-di -o output/claims input/

# Classification only
python -m context_builder.cli classify -o output/claims

# Extraction only
python -m context_builder.cli extract -o output/claims --model gpt-4o
```

### Environment Variables (.env)
```
OPENAI_API_KEY=sk-...
AZURE_DI_ENDPOINT=https://...
AZURE_DI_API_KEY=...
```

---

## Design Patterns

1. **Factory Pattern**: `IngestionFactory`, `ExtractorFactory`, `ClassifierFactory`
2. **Two-Pass Extraction**: Candidate finding (keyword hints) → LLM refinement
3. **Schemas in Python, Prompts in Markdown**: Pydantic + Jinja2 templates
4. **Provenance Tracking**: Every extracted value linked to source text location
5. **Quality Gates**: Automated pass/warn/fail based on required fields

---

## Key File Paths (Quick Reference)

**Backend Core:**
- `src/context_builder/pipeline/run.py` - Main orchestration
- `src/context_builder/extraction/extractors/generic.py` - Field extraction
- `src/context_builder/extraction/spec_loader.py` - Field specs (YAML)
- `src/context_builder/api/main.py` - FastAPI endpoints
- `src/context_builder/schemas/extraction_result.py` - Output schema

**Frontend Core:**
- `ui/src/App.tsx` - Main app with routing
- `ui/src/components/ClaimsTable.tsx` - Claim Workspace UI
- `ui/src/components/DocReview.tsx` - Extraction Review UI
- `ui/src/components/FieldsTable.tsx` - Field labeling with shortcuts
- `ui/src/types/index.ts` - TypeScript types

**Configuration:**
- `pyproject.toml` - Python dependencies
- `ui/package.json` - Frontend dependencies
- `.env` - API keys (not committed)

---

## Notes

- **scratch/ folder**: Contains temporary working notes - IGNORE unless explicitly referenced with full path
- **Extraction specs**: Located in `src/context_builder/extraction/specs/*.yaml`
- **Prompts**: Located in `src/context_builder/prompts/*.md` (Jinja2 templates)
