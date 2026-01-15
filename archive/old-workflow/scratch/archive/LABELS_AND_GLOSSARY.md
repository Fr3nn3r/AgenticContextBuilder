## Updated dev instructions (with your renames)

### 1) Rename the label state

* Replace `CONFIRMED` with **`LABELED`** everywhere (schema, API, UI, metrics).
* States become:

  * `LABELED` (truth_value exists)
  * `UNLABELED` (no truth yet)
  * `UNVERIFIABLE` (explicitly cannot establish truth)

### 2) Rename computed outcomes (UI + metrics)

Stop showing “Match/Mismatch/Miss”. Use:

* **Correct** (formerly Match)
* **Incorrect** (formerly Mismatch)
* **Missing** (formerly Miss)

Outcome computation rules (per run, per field):

* **Correct**: extracted_value equals truth_value (after normalization)
* **Incorrect**: extracted_value exists but differs from truth_value
* **Missing**: extracted_value is empty/missing but truth_value exists
* **Unverifiable**: label state is UNVERIFIABLE (exclude from accuracy)
* **Unlabeled**: label state is UNLABELED (exclude from accuracy)

### 3) Storage rules (avoid drift)

* **Do not store correctness outcomes** in labels. They must be computed from:

  * run extraction outputs + labels truth_value
* You may store **run-level aggregate metrics snapshots** (`runs/<run_id>/metrics.json`) for history/trends.

### 4) Label schema update (minimal)

For each field label, store:

* `state: LABELED | UNLABELED | UNVERIFIABLE`
* `truth_value` (required when LABELED)
* `unverifiable_reason` (required when UNVERIFIABLE)
* `notes` (optional)
* `updated_at` (optional but helpful)

### 5) UI card behavior

* Replace “Ground Truth” wording with **Truth** or **Labeled value**.
* Unlabeled card actions:

  * **Save as labeled** (truth = extracted value)
  * **Set labeled value…** (input required)
  * **Mark unverifiable…** (reason required)
* Labeled card actions:

  * show extracted value (for selected run)
  * show labeled value (truth_value)
  * show computed outcome badge: Correct / Incorrect / Missing
  * **Edit labeled value** (requires confirmation)

### 6) Metrics definition update (Benchmark screen)

Accuracy is computed over **LABELED fields only**:

* **Accuracy = Correct / (Correct + Incorrect + Missing)**
  Also show coverage KPIs:
* **Docs with any labeled field / total docs**
* **Labeled fields / total target fields**



# Glossary (crisp definitions)

### Run

A single execution of the pipeline on a dataset with specific versions (extractor/templates/model). Produces extraction outputs, gates, logs, and metrics for that run.

### Global run

A run scoped across multiple claims/documents (the dataset-level run), used for UI selection and benchmarking.

### Extraction output

The values produced by the system for a document in a specific run, including provenance/evidence.

### Extraction Gate

A run-scoped quality status for a document: PASS/WARN/FAIL, derived from extraction health (required fields present, schema validity, evidence, unreadable text, etc.).

### Label

A human-authored record stored per document+field indicating whether we have established truth and what it is.

### Labeled

Label state meaning: a truth_value exists for that document+field. This is the benchmark “ground truth”.

### Unlabeled

Label state meaning: no truth decision/value has been recorded yet for that document+field.

### Unverifiable

Label state meaning: a reviewer explicitly cannot establish truth for that field from the available document(s). Should include a reason.

### Truth value

The human-authoritative correct value for a field in a given document (stored when state is LABELED).

### Extracted value

The system-produced value for a field from the selected run.

### Correct

Computed outcome (not stored as truth): extracted value equals truth value after normalization.

### Incorrect

Computed outcome (not stored as truth): extracted value exists but does not equal truth value.

### Missing

Computed outcome (not stored as truth): truth value exists but extracted value is missing/empty.

### Accuracy

Run-level metric computed over LABELED fields only:
Correct / (Correct + Incorrect + Missing)

### Coverage (Doc-level)

Docs with at least one LABELED field / total docs in scope.

### Coverage (Field-level)

Number of LABELED fields / total target fields (e.g., required+optional per template, or required only—must specify).

### Evidence / Provenance

Information that allows a human to verify an extracted value in the source (page reference, anchor/quote, offsets). Evidence is typically attached to extraction outputs.

### Target fields

The set of fields defined by the document template/spec for that doc type (required and optionally optional).

### Doc type override

A reviewer flag indicating the predicted doc type is wrong/unsure; used to exclude documents from benchmark scoring until corrected.
