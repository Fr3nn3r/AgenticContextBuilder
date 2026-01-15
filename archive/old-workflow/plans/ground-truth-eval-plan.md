# Ground Truth + Run Evaluation Implementation Plan

Date: 2026-01-13
Owner: Codex
Scope: Backend (storage + labeling + evaluation), minimal invasive changes.

## Goals
- Preserve existing per-claim labels and UI flows.
- Add canonical ground-truth store keyed by full file MD5.
- Enable cross-run evaluation using canonical truth, regardless of claim.
- Keep changes pragmatic; avoid schema churn in extraction outputs.

## Non-Goals (for now)
- Rewriting doc_id strategy or changing ingestion identity rules.
- Full audit history UI or DB storage.
- Large-scale refactor of storage interfaces.

## Proposed Data Model (new)
- Canonical truth path:
  - `output/registry/truth/{file_md5}/latest.json`
- Canonical truth payload (label_v3 compatible + metadata):
  - `schema_version: label_v3`
  - `doc_id` (instance doc_id)
  - `claim_id` (source claim)
  - `input_hashes`: `{ file_md5, content_md5 }`
  - `review`: `{ reviewed_at, reviewer, notes }`
  - `field_labels`: list
  - `doc_labels`: dict
  - `source_doc_ref`: `{ claim_id, doc_id, original_filename }`

## Work Breakdown

### 1) Truth store helper (new module)
- Add `src/context_builder/storage/truth_store.py`:
  - `get_truth_by_file_md5(file_md5)`
  - `save_truth_by_file_md5(file_md5, truth_payload)`
- Use atomic write (tmp + rename).

### 2) Label write-through
- Update `LabelsService.save_labels` to:
  - Read `doc.json` for `file_md5` + `content_md5`.
  - Save claim-local labels as today.
  - Save canonical truth to `registry/truth/{file_md5}/latest.json`.

### 3) Canonical truth read helpers
- Option A (minimal): use TruthStore directly in evaluation script only.
- Option B: add to `StorageFacade`/`LabelStore` (optional; only if needed).

### 4) Run evaluation script (new)
- Add `src/context_builder/pipeline/eval.py`:
  - Inputs: `output_root`, `run_id`.
  - For each extraction in run:
    - Load `doc.json` to get `file_md5`.
    - Load canonical truth; if missing, skip.
    - Compare extracted vs truth (use same normalization logic as insights, if available).
    - Emit per-doc eval: `output/runs/{run_id}/eval/{doc_id}.json`.
  - Emit run summary: `output/runs/{run_id}/eval/summary.json`.

### 5) CLI hook (optional but convenient)
- Add `python -m context_builder.cli eval run --run-id <id> --output output`.

### 6) Tests
- Unit tests for TruthStore (read/write).
- LabelsService test: verify canonical truth write with correct `file_md5`.
- Eval test: mock small extraction + truth files; verify counts.

### 7) Docs
- Add section to README:
  - Canonical truth location + purpose.
  - Eval command + outputs.

## Edge Cases / Notes
- Duplicate file_md5 across claims: canonical truth will be overwritten by latest label save.
  - (Future option: add truth_history.jsonl.)
- `content_md5` changes across runs due to OCR: truth uses `file_md5` as primary key.
- If `doc.json` missing `file_md5`, skip canonical write + warn.

## Estimated Steps
1. Implement TruthStore helper.
2. Update LabelsService to write through.
3. Implement evaluation script + summary.
4. Add CLI entry point (optional).
5. Add tests + docs.

## Success Criteria
- Labeling a doc writes canonical truth under `output/registry/truth/<file_md5>/latest.json`.
- Running eval produces per-doc eval files and summary counts.
- Existing UI flows continue to work unchanged.
