# Phase 2: Backend Upload Infrastructure - Complete

## Summary
Created backend infrastructure for uploading documents to pending claims in a staging area.

## Files Created
- `src/context_builder/api/services/upload.py` - UploadService class with:
  - File validation (PDF, PNG, JPG, TXT; max 100MB)
  - Claim ID validation (unique, alphanumeric)
  - Document staging management (add, remove, reorder)
  - Input preparation for pipeline execution
  - Cleanup functions

- `tests/unit/test_upload_service.py` - 29 unit tests covering:
  - Initialization
  - Claim ID validation
  - File type/size validation
  - Document add/remove/reorder
  - Claim management
  - Move to input
  - Cleanup operations

## Files Modified
- `src/context_builder/api/services/__init__.py` - Export new service
- `src/context_builder/api/main.py` - Added 7 new endpoints:
  - `POST /api/upload/claim/{claim_id}` - Upload files
  - `DELETE /api/upload/claim/{claim_id}` - Remove claim
  - `DELETE /api/upload/claim/{claim_id}/doc/{doc_id}` - Remove doc
  - `GET /api/upload/pending` - List pending claims
  - `PUT /api/upload/claim/{claim_id}/reorder` - Reorder docs
  - `GET /api/upload/claim/{claim_id}` - Get pending claim
  - `POST /api/upload/claim/{claim_id}/validate` - Validate claim ID

## Storage Structure
```
output/.pending/{claim_id}/
├── manifest.json       # Claim metadata, doc list, order
└── docs/
    ├── {uuid}.pdf
    ├── {uuid}.png
    └── ...

output/.input/{claim_id}/   # Temporary for pipeline
└── {original_filename}.*
```

## Test Results
```
29 passed in 1.61s
```

## How to Test Manually
```bash
# Start API server
uvicorn context_builder.api.main:app --reload --port 8000

# Upload a file
curl -X POST "http://localhost:8000/api/upload/claim/TEST-001" \
  -F "files=@document.pdf"

# List pending claims
curl "http://localhost:8000/api/upload/pending"

# Remove a document
curl -X DELETE "http://localhost:8000/api/upload/claim/TEST-001/doc/{doc_id}"
```
