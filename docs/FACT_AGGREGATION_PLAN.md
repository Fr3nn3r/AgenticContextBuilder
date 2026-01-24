# Fact Aggregation Plan

This plan assumes:
- Use the latest *complete* run per document (latest-run strategy).
- Output goes into a claim-level **context** folder.
- Include **all** candidate values (not just conflicts).

## 1) Latest-Run Strategy

Goal: pick the most recent extraction output per document as the source of truth, while still retaining all evidence candidates from that run.

Selection policy:
- Only consider runs with `.complete` and a `manifest.json`.
- Sort by `manifest.ended_at` (fallback to `started_at`) descending.
- For each document, select the latest run that has `runs/<run_id>/extraction/<doc_id>.json`.

Notes:
- If a latest run has missing fields, still use it but mark field status as missing; don’t backfill from older runs unless explicitly requested.
- If needed later, add a “prefer-pass” fallback policy, but **not** in this plan.

## 2) Output Location: Claim Context

Create a claim-level context file that aggregates extracted facts.

Proposed output:
- `workspaces/<workspace>/claims/<claim_id>/context/claim_facts.json`

Create `context/` under the claim root (not inside any run) so the file represents a consolidated view across runs.

## 3) Include All Candidates

Each fact keeps:
- A **selected** value (best from latest run).
- **All candidates** from the same run (even if they match or conflict).

Why:
- Full audit trail for evidence.
- Easier future re-ranking without reruns.

## Aggregation Steps (Implementation Outline)

1. Discover runs for claim
   - `workspaces/<ws>/claims/<claim_id>/runs/<run_id>/...`

2. For each document:
   - Find latest run with extraction file.
   - Load extraction result, doc metadata, and pages.

3. Build candidate list
   - For each extracted field with `status == "present"`:
     - candidate = {field_name, value, normalized_value, confidence, doc_id, doc_type, run_id, provenance[]}

4. Resolve evidence offsets (optional pass)
   - If `char_start`/`char_end` missing, locate `text_quote` in `pages.json` using `find_text_position`.
   - Attach page number, offsets to provenance.

5. Select primary value
   - Simple: highest confidence.
   - Store all candidates as `alternatives`.

6. Write `claim_facts.json`
   - Include metadata: generation time, run selection policy, list of source docs.

## Suggested `claim_facts.json` Schema

```json
{
  "claim_id": "65157",
  "generated_at": "2026-01-24T15:30:00Z",
  "run_policy": "latest_complete",
  "facts": [
    {
      "name": "policy_number",
      "value": "ABC123",
      "normalized_value": "ABC123",
      "confidence": 0.92,
      "selected_from": {
        "doc_id": "...",
        "doc_type": "policy",
        "run_id": "run_...",
        "page": 2,
        "text_quote": "Policy No: ABC123",
        "char_start": 1450,
        "char_end": 1468
      },
      "alternatives": [
        {"value": "ABC123", "doc_id": "...", "page": 1, "run_id": "run_..."},
        {"value": "ABC12B", "doc_id": "...", "page": 3, "run_id": "run_..."}
      ]
    }
  ],
  "sources": [
    {"doc_id": "...", "filename": "KV.pdf", "doc_type": "cost_estimate"}
  ]
}
```
