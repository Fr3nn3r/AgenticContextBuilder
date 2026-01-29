## Ingestion naming cleanup (planning only)

This document captures a proposed rename map for the ingestion-related backend
structure. No code changes are applied yet. The goal is higher semantic density
and removing generic buckets like `impl`.

### Goals

- Replace `impl/` with an explicit domain location for providers.
- Move root-level `ingestion.py` into a dedicated package.
- Make provider filenames readable without internal acronyms.
- Keep runtime behavior and provider keys stable.

### Proposed structure

```
src/context_builder/
  ingestion/
    __init__.py
    providers/
      azure_document_intelligence.py
      openai_vision.py
      tesseract.py
```

### Rename map (files/directories)

- `src/context_builder/ingestion.py`
  → `src/context_builder/ingestion/__init__.py`

- `src/context_builder/impl/`
  → `src/context_builder/ingestion/providers/`

- `src/context_builder/impl/azure_di_ingestion.py`
  → `src/context_builder/ingestion/providers/azure_document_intelligence.py`

- `src/context_builder/impl/openai_vision_ingestion.py`
  → `src/context_builder/ingestion/providers/openai_vision.py`

- `src/context_builder/impl/tesseract_ingestion.py`
  → `src/context_builder/ingestion/providers/tesseract.py`

### Import rename map (high-level)

- `from context_builder.ingestion import ...`
  remains valid, but the module becomes a package at `ingestion/__init__.py`.

- `from context_builder.impl.azure_di_ingestion import AzureDocumentIntelligenceIngestion`
  → `from context_builder.ingestion.providers.azure_document_intelligence import AzureDocumentIntelligenceIngestion`

- `from context_builder.impl.openai_vision_ingestion import OpenAIVisionIngestion`
  → `from context_builder.ingestion.providers.openai_vision import OpenAIVisionIngestion`

- `from context_builder.impl.tesseract_ingestion import TesseractIngestion`
  → `from context_builder.ingestion.providers.tesseract import TesseractIngestion`

### Optional class name refinements

If you want more explicit class roles, consider:

- `OpenAIVisionIngestion` → `OpenAIVisionIngestionProvider`
- `TesseractIngestion` → `TesseractIngestionProvider`
- `AzureDocumentIntelligenceIngestion` → `AzureDocumentIntelligenceProvider`

These are optional and can be deferred to avoid churn.

### Provider keys (no change recommended)

Keep factory registration keys stable for compatibility:

- `openai`
- `tesseract`
- `azure-di`

If clearer keys are desired later, add aliases instead of breaking changes.

