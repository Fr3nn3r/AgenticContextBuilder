# Phase 1: API Service Layer

**Completed:** 2026-01-12

## Summary
Extracted claims/documents/insights/labels business logic into services, centralized API models, and slimmed route handlers. Added unit tests using mocked storage.

## Changes Made
- Added shared Pydantic models in `src/context_builder/api/models.py`.
- Added services under `src/context_builder/api/services/` with shared helpers in `src/context_builder/api/services/utils.py`.
- Refactored `src/context_builder/api/main.py` to delegate to services for claims, documents, labels, and insights.
- Added `tests/unit/test_api_services.py` covering each service with mocked storage.

## Verification
- Not run (not requested).
