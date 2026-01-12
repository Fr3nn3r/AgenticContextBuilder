# Phase 0: Baseline and Inventory

**Completed:** 2026-01-12

## Summary
Captured the current API call flows, pipeline stages, and ingestion providers/error handling patterns to anchor the refactor plan.

## Inventory
- API call flows: `src/context_builder/api/main.py` mixes FileStorage lookups (doc bundle, labels, extractions) with direct filesystem scans for claims, docs, and run summaries; insights endpoints delegate to `InsightsAggregator`.
- Pipeline stages: discovery -> ingestion (source copy, ingestion provider, pages.json) -> classification (context JSON + doc.json) -> extraction (run-scoped JSON) -> summary/metrics/manifest outputs under `output/claims/{claim}/runs/{run}`.
- Storage usage: `FileStorage` provides index-backed doc/run lookup with filesystem fallback; labels live in `docs/{doc_id}/labels/latest.json`, run artifacts under `runs/{run_id}/`.

## Ingestion Providers & Error Handling
- Providers registered via `IngestionFactory`: `openai`, `tesseract`, `azure-di`.
- Errors surface as `IngestionError` subclasses (`FileNotSupportedError`, `APIError`, `ConfigurationError`); pipeline catches exceptions in `process_document`, records `failed_phase`, and writes error details into run summaries.
