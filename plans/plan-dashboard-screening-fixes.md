# Plan: Dashboard + Screening Fixes

## Goals
- Fix mutable default list fields in dashboard API models.
- Make dashboard service customer-agnostic via workspace config overrides.
- Prevent core tests from hard-depending on customer workspace modules.
- Document customer-repo changes needed (check 5c wiring) outside this repo.

## Steps
1. Update dashboard Pydantic models to use Field(default_factory=list) for list defaults.
2. Add optional dashboard config loader in API service and use it for:
   - ground_truth.json path
   - ground-truth PDF filename
   - result-code labels
   - default currency
3. Make NSA extractor test skip if NSA workspace module is not present.
4. Provide recommended changes for the NSA customer repo (check 5c implementation + wiring).

## Verification
- Run unit tests covering screening schema and dashboard types if available.
