Here are crisp, senior-dev instructions to implement **run control + logs** without boiling the ocean. This is MVP “pro enough” and will make every future iteration measurable.

---

## Objective

Every pipeline execution (“run”) must be:

1. **reproducible** (know exactly what happened),
2. **auditable** (why did docs fail/skip),
3. **comparable** (KPIs per run vs labels),
4. **non-destructive** (no silent overwrites).

---

## Required run artifacts (write these files)

Create `runs/<run_id>/` and always write:

1. `manifest.json` — immutable run metadata
2. `summary.json` — per-doc outcomes + counters
3. `metrics.json` — computed KPIs (against latest labels)
4. `logs/run.log` — human-readable log file

If any of these are missing, the run is considered incomplete.

---

## Run ID + overwrite policy

* Generate `run_id` at start: `YYYYMMDD-HHMMSS_<short_git_sha>` (or UUID).
* Never overwrite an existing `run_id` unless `--force` is set.
* Default: if folder exists → error with clear message.

---

## `manifest.json` contents (must include)

* `run_id`, `started_at`, `ended_at`
* `command`: full CLI command string + args
* `cwd`, `hostname` (optional), `python_version`
* `git`: `commit_sha`, `is_dirty` (true/false)
* `pipeline_versions`:

  * `contextbuilder_version` (package version or commit)
  * `extractor_version` (your internal version string)
  * `templates_version` (hash of templates/spec bundle)
  * `model_provider` / `model_name` (if applicable)
  * `prompt_versions` (if applicable)
* `input`:

  * input root path
  * list of claim_ids included (or counts)
  * selection filters (doc types included)
* `output_paths`:

  * claims output root
  * runs root
* `counters_expected`:

  * expected claims/docs discovered before processing

**Important:** `templates_version` should be a deterministic hash of the template/spec files currently in use.

---

## `summary.json` contents (must include)

A structured per-doc record plus aggregated counts.

### Per-doc record fields

For each doc processed (or skipped), emit:

* `claim_id`, `doc_id`, `doc_type_predicted`, `doc_type_confidence`
* `status`: `processed | skipped | failed`
* `skip_reason` or `error_code` (enum)
* `text_source_used`: `di_text | vision_ocr | none`
* `text_readability`: `good | warn | bad` (if available)
* `extraction_gate`: `pass | warn | fail` (if available)
* `fields_extracted_count`
* `evidence_coverage`: fraction of extracted fields with provenance
* `output_paths`: pointers to written outputs (relative paths)

### Aggregates

* counts: discovered, processed, skipped, failed
* breakdowns by doc type and by error_code

---

## Error taxonomy (keep it small and stable)

Implement a short enum and use it everywhere:

* `DOC_NOT_SUPPORTED` (doc type not in the 3 supported)
* `TEXT_MISSING`
* `TEXT_UNREADABLE`
* `CLASSIFY_LOW_CONF`
* `EXTRACT_SCHEMA_INVALID`
* `EXTRACT_EXCEPTION`
* `OUTPUT_WRITE_FAILED`
* `UNKNOWN_EXCEPTION`
* `VISION_RECOMMENDED` (not an error, but a flag; can also be a field)

Avoid free-text errors in summary; logs can have stack traces.

---

## Logging requirements (run.log)

* Write structured logs to file (JSONL preferred) + readable console logs.
* Include `run_id`, `claim_id`, `doc_id` in log context.
* Log key lifecycle events:

  * discovery summary
  * per-doc start/end + duration
  * retries
  * fallbacks (DI→vision)
  * schema validation failures
  * write failures
* If exception: log stack trace and set per-doc `error_code`.

---

## `metrics.json` (computed after run completes)

Compute metrics using:

* predictions from this run
* **latest per-doc labels** (run-agnostic)

### Metrics to include

Overall:

* `label_coverage`: labeled_docs / total_docs (in supported types)
* `run_coverage`: docs_with_predictions_in_run / labeled_docs
* `required_field_presence` (weighted avg)
* `required_field_accuracy` (on labelled fields excluding unknown)
* `evidence_rate` (extracted fields with provenance)

Per doc type:

* docs processed, accuracy, presence, evidence, doc_type_wrong_rate, needs_vision_rate

Per field (top few only):

* top failing (doc_type, field_name) with failure-mode counts:

  * extractor_miss / incorrect / cannot_verify / evidence_missing

Also include:

* `baseline_run_id` if set globally (optional)

---

## Atomic writes + completeness marker

To avoid half-written runs:

* Write each JSON file via temp file + rename.
* Create `runs/<run_id>/.complete` only after all artifacts are written.

UI should consider only runs with `.complete` present.

---

## CLI changes (minimal)

Add flags:

* `--run-id` (optional override)
* `--runs-dir` (default `runs/`)
* `--force` (overwrite existing run folder)
* `--dry-run` (discovery only)
* `--metrics` (compute metrics at end; default on)

---

## Acceptance criteria (what “done” means)

1. Running the pipeline creates a new `runs/<run_id>/` folder with manifest/summary/metrics/logs.
2. No run overwrites another without `--force`.
3. Failures are classified by stable error codes.
4. Metrics are computed against latest labels and stored per run.
5. UI can list runs and display run metadata + KPIs.

---