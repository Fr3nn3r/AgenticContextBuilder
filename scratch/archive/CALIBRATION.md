Yes — **build the Insights screen now**. You’ve done the hardest thing (field-level labels). The Insights UI is what turns this into a repeatable calibration program and tells you whether to (a) improve extraction for current types or (b) expand to new types.

Below is a developer briefing you can paste into a ticket.

---

## Developer briefing: Build “Calibration Insights” screen (ContextBuilder)

### Objective

Create a read-only **Calibration Insights** screen that uses field-level labels to answer:

* What is working? What is failing?
* Why is it failing (extractor miss vs normalization vs evidence vs doc type mismatch vs needs vision)?
* What should we improve next (highest ROI)?

Scope: only the **3 supported doc types** (loss_notice, police_report, insurance_policy). Ignore other docs for now.

---

## Inputs (conceptual)

Backend already has access to:

* **Templates/specs** for the 3 doc types (fields, required/optional)
* **Extraction outputs** (field values, normalized values, evidence/provenance, confidence)
* **Reviewer labels** per field (correct/wrong/cannot verify) + doc-level labels:

  * doc type correct (yes/no/unsure)
  * “needs vision extraction” (true/false)
* Claim/document metadata (claim_id, doc_id, doc_type, filename)

UI must not read filesystem directly; it consumes aggregated API responses.

---

## Key derived concepts (must implement)

### 1) Filter set (top controls)

* Doc type: all / loss_notice / police_report / insurance_policy
* Failure mode: all / extractor_miss / normalization / evidence_missing / doc_type_wrong / needs_vision / cannot_verify
* Field: all / specific field
* Show: all docs vs only labeled vs only failing

### 2) Failure taxonomy (core logic)

For each field on each reviewed document, derive a standardized outcome:

* **Correct_raw**: label correct AND extracted value matches label (raw)
* **Normalization_issue**: label indicates correct value exists, extractor got raw right but normalized wrong (or label “wrong” but raw matches)
* **Extractor_miss**: label indicates value present but extraction output is missing
* **False_positive**: extractor output present but label says wrong AND value not present
* **Evidence_missing**: extracted value present but no usable provenance/evidence OR evidence flagged as weak
* **Cannot_verify**: label cannot verify
* **Doc_type_wrong**: doc-level label says doc type incorrect (yes/no/unsure) → treat all field results for that doc as “tainted”
* **Needs_vision**: doc-level flag true (track separately; this is a lever, not a failure)

Important: Only compute field metrics for docs where doc type is **Correct = yes**. Show doc-type-wrong in its own panel.

---

## Screen layout requirements

### Section A — Overview KPIs (cards)

* Docs reviewed (supported types): `X`
* Docs with doc_type_wrong: `X`
* Docs flagged needs_vision: `X`
* Field presence rate (avg across required fields)
* Field accuracy (raw) (avg across required fields)
* Evidence rate (avg across extracted fields)

### Section B — “Where to strike next” (priority list)

A ranked list of 5–10 items: **(doc_type, field) → dominant failure mode + impact**
Example row content:

* `police_report • incident_date`
* Impact: “12/16 docs affected”
* Failure mix: “Extractor miss 8, normalization 2, evidence missing 2”
* Suggested fix bucket (derived):

  * If many normalization_issue → “Improve normalization”
  * If many extractor_miss + needs_vision low → “Improve span finding / prompt”
  * If many extractor_miss + needs_vision high → “Improve OCR/vision fallback”
  * If evidence_missing high → “Improve provenance capture”
  * If doc_type_wrong high → “Improve classification or template mapping”

Each item is clickable → drills into examples (Section D).

### Section C — Doc type scoreboard (table)

Rows: the 3 supported doc types.
Columns:

* Docs reviewed
* Doc type wrong (%)
* Needs vision (%)
* Required field presence %
* Required field accuracy (raw) %
* Evidence rate %
* “Top failing field” (by affected docs)

Clicking a row filters the whole screen to that doc type.

### Section D — Drilldown: Field detail + examples

When selecting a priority item or field:

* Breakdown chart (counts by failure mode)
* Examples table (10–30 rows):

  * claim_id
  * doc filename
  * extracted value (raw + normalized)
  * label (correct/wrong/cannot verify)
  * evidence status
  * needs_vision flag
  * link: **Open in Claim Review** at this doc and field

This is the most important developer usability feature: “show me the actual cases.”

---

## Navigation / deep links

Add deep links to reuse your existing Claim Review UX:

* `Open doc` should route to `/claims/:claim_id/review?doc_id=...&field=...`
* On load, Claim Review should auto-select the doc and scroll/highlight field evidence (Text tab). If PDF tab is active, at least navigate to (evidence) page.

---

## API expectations (high-level)

Provide aggregated endpoints (names flexible):

* `/api/insights/overview`
* `/api/insights/doc-types`
* `/api/insights/priorities`
* `/api/insights/field-details?doc_type=...&field=...`
* `/api/insights/examples?...filters...`

Aggregation should default to latest run outputs, combined with latest saved labels.

---

## Definition of Done

* Screen loads quickly and is usable for deciding “what to fix next.”
* Metrics exclude docs where doc_type is labeled wrong (but those are still reported separately).
* “Needs vision” is a first-class insight lever (badge + metric), not a column in the claim list.
* Every priority item can be backed by example cases and one-click navigation into review.

---

## Product decision note (for devs, not UI)

Do **not** expand to more doc types until Insights shows:

* required fields accuracy ≥ ~80% and evidence rate ≥ ~80% for current 3 types (rough heuristic).
  Insights exists to tell us when to expand.


+++++++++++++++++++


Perfect — this is enough to define the aggregation logic cleanly. Here’s the **backend join + metrics spec** your devs can implement to power the “Calibration Insights” screen.

---

## Backend pseudo-spec: Labels → Insights aggregation

### Inputs per document

For each `doc_id` in the 3 supported doc types, load:

1. **Label** (`label_v1`) — you provided:

* `doc_id`, `claim_id`
* `doc_labels.doc_type_correct` (bool)
* `doc_labels.text_readable` (good/warn/bad)
* `field_labels[]`: `{field_name, judgement: correct|wrong|unknown, notes}`

2. **Extraction result** (`extraction_result_v1`) — from latest run:

* `doc.doc_type`
* `fields[]`: `{name, value, normalized_value?, confidence, provenance[]}`
* `quality_gate.status` (pass/warn/fail)

3. **Template/spec** for that `doc_type`:

* required_fields[]
* optional_fields[]

---

## Core join

Create a unified record per (doc_id, field_name) for fields that appear in either:

* template fields (required + optional), and/or
* extraction output fields, and/or
* label field_labels

**Join key:** `(doc_id, field_name)`

* Label provides judgement.
* Extraction provides predicted value + evidence.
* Spec provides expectedness (required/optional).

---

## Filtering rules (very important)

### A) Doc type wrong handling

If `doc_labels.doc_type_correct == false`:

* Count doc in **DocTypeWrong panel**
* Exclude doc from field-level accuracy metrics by default
* Still show it in examples, with a “doc type wrong” tag

If `doc_type_correct` missing or unsure later:

* treat as “tainted” unless explicitly true

### B) Unknown judgements

If `judgement == "unknown"`:

* exclude from accuracy numerator/denominator (default)
* track separately as “Cannot verify rate”
* include in examples when drilling down

---

## Derived outcomes per (doc, field)

Compute these booleans:

* `is_required` / `is_optional` (from spec)
* `has_prediction`: extraction contains that field with a non-empty value
* `has_evidence`: provenance exists and has page + quote/anchor (whatever you support)
* `text_readable`: good/warn/bad (from doc label)
* `gate_status`: pass/warn/fail (from extraction)

### Outcome classification (simple, works now)

Given `judgement` and `has_prediction`:

* If `judgement == correct` and `has_prediction == true` → **Correct**
* If `judgement == correct` and `has_prediction == false` → **Extractor_miss**
* If `judgement == wrong` and `has_prediction == true` → **Incorrect**
* If `judgement == wrong` and `has_prediction == false` → **Correct_absent** (rare; keep as separate bucket)
* If `judgement == unknown` → **Cannot_verify**

Evidence overlay:

* If `has_prediction == true` and `has_evidence == false` → tag **Evidence_missing**

*(Normalization-specific issues can be added later once labels include corrected_value or raw-vs-normalized checks.)*

---

## Metrics to compute (for Insights screen)

### 1) Document-level metrics (by doc_type and overall)

* `docs_reviewed`
* `docs_doc_type_wrong`
* `docs_text_readable_good/warn/bad`
* `docs_gate_pass/warn/fail`
* `docs_with_any_unknown_fields` (optional)
* `docs_with_any_evidence_missing` (optional)

### 2) Field-level metrics (per doc_type, per field)

Compute on docs where `doc_type_correct == true`.

For each field:

* **Label coverage**: `% docs where a label exists for field`
* **Presence rate**: `% docs where has_prediction == true`
* **Accuracy**:

  * denominator = count of labelled docs with judgement in {correct, wrong}
  * numerator = count where judgement == correct AND has_prediction == true
* **Extractor miss rate**: judgement == correct AND has_prediction == false
* **Incorrect rate**: judgement == wrong AND has_prediction == true
* **Cannot verify rate**: judgement == unknown
* **Evidence rate**: among has_prediction == true, `% with has_evidence == true`

Also compute `affected_docs_count` per failure mode (used for prioritization).

### 3) Prioritization score (“Where to strike next”)

For each (doc_type, field), score by:

* `impact = affected_docs_count` (how many docs it hurts)
* `severity_weight`:

  * extractor_miss: 3
  * incorrect: 3
  * evidence_missing: 2
  * cannot_verify: 1
* `priority_score = Σ(weight * count)` across modes

Then show top N.

### 4) Example selection for drilldown

For a selected (doc_type, field, failure_mode):
Return up to 30 examples:

* claim_id, doc_id, filename
* judgement
* predicted value (if any)
* evidence status
* gate status
* text_readable
* link to claim review route

---

## API payloads (keep simple)

### `GET /api/insights/overview`

Return:

* totals (docs reviewed, doc type wrong, text quality distribution)
* overall accuracy/evidence rates (weighted by required fields)
* latest run metadata

### `GET /api/insights/doc-types`

Return table rows per doc_type with metrics.

### `GET /api/insights/priorities?limit=10`

Return ranked list with:

* doc_type, field_name
* counts per failure mode
* recommended fix bucket (see below)

### `GET /api/insights/field-details?doc_type=...&field=...`

Return breakdown counts + rates + top notes (optional).

### `GET /api/insights/examples?...`

Return examples list with deep link.

---

## “Recommended fix bucket” heuristics (simple + effective)

Given a priority item’s failure mix:

* Mostly **Extractor_miss** + text_readable good → “Improve span finding / extraction”
* Mostly **Extractor_miss** + text_readable bad/warn → “Add/Improve vision fallback”
* Mostly **Evidence_missing** → “Improve provenance capture”
* High **DocTypeWrong** for this doc_type → “Fix classification/template mapping”
* High **Unknown** → “Improve reviewability (show PDF/text better) or add clearer evidence”

---

## One small note about your current label format

You have `reviewer: "system"` — PO wanted reviewer name removed in UI, but it’s fine in the file. For Insights, ignore reviewer.

---