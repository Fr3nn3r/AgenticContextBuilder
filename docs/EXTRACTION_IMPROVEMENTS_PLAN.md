# Extraction Improvement Plan (Evidence Quality)

Goal: improve extraction outputs so aggregated facts have stronger, machine-verifiable provenance.

## 1) Populate Exact Evidence Offsets

Problem:
- Many fields have `char_start=0` / `char_end=0`, which makes evidence hard to verify.

Plan:
- After LLM extraction, for each `FieldProvenance.text_quote`, locate it in the page text.
- Use `find_text_position` from `src/context_builder/extraction/page_parser.py`.
- Store resolved `char_start`/`char_end` for each provenance entry.

Implementation sketch:
- Add a post-processing step in the extractor base or in the run pipeline:
  - Input: `pages` + `fields[].provenance[]`
  - Output: updated provenance with offsets.

## 2) Normalize Field Values Consistently

Problem:
- Some fields only include `value` but normalization rules vary per extractor.

Plan:
- Implement canonical normalizers per field type (dates, money, plates, VINs, policy numbers).
- Write normalized values into `normalized_value` for all fields.

## 3) Improve Provenance Granularity for Tables

Problem:
- Line items use a single placeholder provenance (e.g., "[35 line items across 3 pages]").

Plan:
- For line items, attach provenance for each item (page + quote, or at least row start/end markers).
- If exact row location is unavailable, store per-page evidence with a bounded text window for each item.

## 4) Add Evidence Confidence Scoring

Problem:
- Downstream aggregation can’t distinguish a weak guess from strong evidence.

Plan:
- Compute a simple evidence score, e.g.:
  - +1 for exact text match
  - +1 if match length > N
  - +1 if page has matching label/header
- Store it as `provenance_score` at field level.

## 5) Include Source Metadata in Provenance

Problem:
- Aggregators must look up doc/run info separately.

Plan:
- Add optional fields in `FieldProvenance`:
  - `doc_id`, `doc_type`, `run_id`, `file_md5`, `content_md5`

## 6) Enforce Evidence Requirements per Field

Problem:
- Fields can be marked present without evidence.

Plan:
- Extend quality gate rules to require evidence for critical fields.
- If missing evidence, downgrade confidence or mark as `warn`.

## 7) Add a Validation Pass

Problem:
- Numeric totals sometimes don’t reconcile (e.g., subtotal + VAT != total).

Plan:
- Add per-doc validation rules in extraction results (e.g., totals reconcile within tolerance).
- Write validation status into `_extraction_meta`.

## 8) Persist Extraction Input Context

Problem:
- Hard to reproduce extraction decisions later.

Plan:
- Store the resolved `pages.json` hash and `spec` version hash in extraction result metadata.
- This is already partially in run metadata; ensure it’s included per extraction file.

## 9) Backfill Evidence (Batch Utility)

Plan:
- Create a CLI utility to reprocess existing extraction outputs and fill in missing offsets using current pages.
- This avoids rerunning LLMs.

## 10) Tests

- Add unit tests for:
  - Quote position resolution
  - Normalization helpers
  - Line item provenance expansion
  - Validation rules
