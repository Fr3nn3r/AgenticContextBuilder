---
name: architecture
description: "System architecture reference — pipeline flow, components, data structures. Use /architecture when you need to understand the system design."
allowed-tools: Read, Glob, Grep
---

# Architecture Reference

This is the ContextBuilder system architecture. Use this as a reference when you need to understand the system design, pipeline flow, or data structures. You can cross-reference with live code using Read, Glob, and Grep tools.

## Pipeline Flow

```
Input Documents (PDF/image/text)
    |
Ingestion (Azure DI or OpenAI Vision)
    |
Classification (OpenAI -> doc type)
    |
Extraction (OpenAI -> fields with provenance)
    |
Quality Gate (pass/warn/fail)
    |
Active Workspace (workspaces/{workspace_id}/)
    +-- claims/{claim_id}/docs/{doc_id}/
    |   +-- extraction.json
    |   +-- labels/
    +-- runs/{run_id}/
    +-- logs/ (decisions.jsonl, llm_calls.jsonl)
    +-- registry/ (truth store, indexes)
```

## Workspaces

Workspaces are isolated storage locations (like separate databases).

- **Registry**: `.contextbuilder/workspaces.json` tracks all workspaces
- **Active workspace**: Determines where backend reads/writes
- **Switch**: Admin UI or `POST /api/workspaces/{id}/activate`
- **Service**: `src/context_builder/api/services/workspace.py`

## Key Components

### Backend (`src/context_builder/`)

| Module | Purpose |
|--------|---------|
| `pipeline/run.py` | Orchestrates full pipeline execution |
| `classification/openai_classifier.py` | Routes docs to correct type |
| `extraction/extractors/generic.py` | Extracts fields per doc type |
| `extraction/specs/doc_type_catalog.yaml` | Doc type definitions (SSOT) |
| `api/main.py` | FastAPI REST endpoints |
| `services/decision_ledger.py` | Compliance audit trail |
| `services/llm_audit.py` | LLM call logging |

### Frontend (`ui/src/`)

| Component | Purpose |
|-----------|---------|
| `App.tsx` | Routing, global state |
| `components/ClaimReview.tsx` | Claim-scoped document review |
| `components/FieldsTable.tsx` | Field labeling (1/2/3, n/p shortcuts) |
| `pages/BatchWorkspace.tsx` | Batch context with tabs |

## Data Structures

### ExtractionResult
```json
{
  "schema_version": "1.0",
  "run": { "run_id": "...", "model": "gpt-4o" },
  "doc": { "doc_id": "...", "doc_type": "invoice", "confidence": 0.95 },
  "fields": [
    {
      "name": "claim_number",
      "value": "CLM-001",
      "confidence": 0.9,
      "provenance": { "page": 1, "quote": "Claim #CLM-001" }
    }
  ],
  "quality_gate": { "status": "PASS" }
}
```

### LabelResult
```json
{
  "schema_version": "1.0",
  "doc_id": "...",
  "review": { "reviewer": "user@example.com", "reviewed_at": "..." },
  "field_labels": [
    { "field_name": "claim_number", "state": "correct", "truth_value": "CLM-001" }
  ]
}
```

## Doc Types

`fnol_form`, `insurance_policy`, `police_report`, `invoice`, `id_document`, `vehicle_registration`, `certificate`, `medical_report`, `travel_itinerary`, `customer_comm`, `supporting_document`

## Tips

- To find all pipeline stages: `Glob("src/context_builder/pipeline/stages/*.py")`
- To find all API routers: `Glob("src/context_builder/api/routers/*.py")`
- To find all Pydantic schemas: `Glob("src/context_builder/schemas/*.py")`
- To check doc type catalog: `Read("src/context_builder/extraction/specs/doc_type_catalog.yaml")`
