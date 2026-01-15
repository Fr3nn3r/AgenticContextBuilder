You’re thinking about this exactly the right way: **split “classify” and “extract”** even if today your classifier grabs a few fields. Pros separate them because it makes quality gates, evals, and traceability *actually manageable*.

Below is a “pro-style” extraction design you can implement without a DB, and optionally with a light React UI that reads/writes JSON files locally.

---

## The pro mental model: extraction is a routed service

Your pipeline becomes:

1. **Ingest** → assign stable IDs, compute hashes, store raw files
2. **Classify** → doc_type + confidence + language + page count + (optional cheap hints)
3. **Extract** → doc-type–specific schema, normalized fields, provenance, confidence
4. **Quality Gate** → pass/warn/fail + reasons
5. **Inspections** → only run when upstream is “good enough” (or run in “uncertain” mode)

Key point: extraction isn’t “one thing”. It’s a **router** that chooses the right extractor based on doc_type.

---

## Should extraction be doc-type specific?

Yes. **100% yes.**
Extraction should be defined by a **DocTypeSpec**:

* which fields to extract
* required vs optional
* normalization rules
* validation rules
* preferred extraction strategy
* what “evidence” looks like (page/snippet)

This is how you avoid a mushy “extract everything from everything” approach.

---

## Which Python libraries should you use?

If you want “pro” without overengineering:

### Core

* **pydantic** (schemas + validation)
* **instructor** (LLM → strict pydantic output) *or* OpenAI structured outputs if you’re using that directly
* **python-dateutil** (date parsing)
* **rapidfuzz** (fuzzy matching for names/plates, optional)
* **tiktoken** (token estimation, optional but useful)

### PDF/Text helpers (only if you need)

* **pypdf** (extract per-page text, metadata)
* **pdfplumber** (if you need better layout-based text extraction)

You already have extracted text + context files, so you can start **without** touching PDF parsing again. Add OCR/vision only when quality gate fails.

---

## When do you need chunking?

Chunking is not a “default”. It’s a tool. Pros chunk for two reasons:

1. **Context limit / cost** (policy docs can be long)
2. **Precision** (you want the model to look at the *right* parts)

### Practical rule

* **No chunking** for short docs (loss notice, police report) if text fits comfortably.
* **Chunking + retrieval** for long docs (policy wording).

### Better than blind chunking: “Find → Extract”

Do it in two passes:

**Pass A: Candidate span finder (cheap + traceable)**

* regex/keywords (“Policy Number”, “No. de póliza”, “Fecha”, “Placa”, etc.)
* return a few snippets with page + offsets

**Pass B: Structured extraction on those snippets**

* feed only candidate snippets to the LLM
* output pydantic fields + evidence pointers

This keeps cost low and traceability high.

---

## How to ensure traceability (the pro way)

Every extracted field should be a record like:

```json
{
  "field": "incident_date",
  "value": "2024-01-13",
  "confidence": 0.78,
  "normalized": true,
  "provenance": [
    {
      "doc_id": "doc_abc123",
      "page": 1,
      "method": "text",
      "text_quote": "Fecha del incidente: 13/01/2024",
      "char_start": 1024,
      "char_end": 1058
    }
  ],
  "extractor": {
    "name": "loss_notice_v1",
    "model": "gpt-...",
    "prompt_version": "2026-01-05",
    "run_id": "run_2026-01-05T12:03:11Z"
  }
}
```

You don’t need bounding boxes on day 1. **Page + quote + offsets** is already “auditable enough” for an exec demo and for later governance.

Also: store hashes so you can prove “same input → same output” (or at least detect drift).

---

## Design the extraction step like a pro

### 1) Define `DocTypeSpec` for your 3 doc types (start small)

Example (conceptual):

* **loss_notice**

  * claim_number (required)
  * incident_date (required)
  * incident_location (optional)
  * vehicle_plate (optional)
* **police_report**

  * report_number (optional/required depending)
  * report_date (required)
  * incident_date (required)
  * location (optional)
* **insurance_policy** (later, more complex)

  * policy_number (required)
  * insured_name (optional)
  * coverage_start/end (optional)

Each field has:

* normalizer
* validator
* extraction hint patterns

### 2) Implement extractor modules per doc_type

Each module does:

* take `doc_text_by_page`
* run candidate finder
* run structured extraction (pydantic/instructor)
* normalize + validate
* produce field records + provenance

### 3) Add a quality gate output

Return:

* `status`: pass/warn/fail
* `reasons`: missing required fields / low confidence / no evidence / unreadable text
* `fallback_needed`: vision_ocr yes/no

This becomes your control lever.

---

## Should your classifier still extract a few fields?

It can, but treat them as **hints**, not truth.

Pattern:

* Classifier outputs `doc_type`, and maybe “likely claim_number found”
* Extractor confirms it, normalizes it, adds provenance, scores it

That separation is the difference between a demo and an enterprise pipeline.

---

## A light React front-end that makes you look *very* serious (no DB)

Yes — and it’s worth it if it helps your iteration loop.

### What it does (local-only)

* Loads `inventory.json`
* Lists claims → documents
* Shows:

  * left: PDF viewer (pdf.js) OR extracted text by page
  * right: extracted fields + evidence quotes
* Buttons per field:

  * ✅ Correct
  * ❌ Wrong
  * ❓ Unknown
* Writes `labels.json` next to the document folder

This gives you:

* labeling workflow (gold standard)
* extraction eval dataset
* “enterprise vibe” instantly

No DB needed. Just file writes.

---

## Your next 3 concrete build steps (do this in order)

### Step 1 — Freeze your extraction contract (1 day)

Create one JSON format that every extractor must produce:

* `doc_id`, `doc_type`, `fields[]`, `quality_gate`, `run_metadata`

### Step 2 — Implement `loss_notice` extractor end-to-end (1–2 days)

Do one doc type perfectly:

* candidate finder + structured extraction + provenance + quality gate

### Step 3 — Add the React “review & label” UI (2–3 days)

Keep it tiny, but functional.
This will accelerate your reps massively.

---

Great — having **Azure DI output split by page** is the cheat code. It lets you build a “pro” extractor with **high traceability** (page + quote + offsets) *without* chunking headaches.

Below is a clean, enterprise-style design you can implement now.

---

## 1) The extraction step you want: routed, doc-type–specific, evidence-first

### Core rule

**Classification predicts doc_type. Extraction confirms + structures.**
Classifier can output hints, but extraction owns truth, normalization, and provenance.

### Extraction architecture

* `ExtractorRouter(doc_type)` → calls a dedicated extractor module:

  * `extract_loss_notice_v1`
  * `extract_police_report_v1`
  * `extract_policy_v1` (later)

Each extractor follows the same contract, so downstream inspections don’t care *how* extraction happened.

---

## 2) Your extraction output contract (JSON shape you should standardize)

This is the “pro” piece that makes everything measurable and auditable.

```json
{
  "schema_version": "extraction_result_v1",
  "run": {
    "run_id": "run_2026-01-05T23:10:00Z",
    "extractor_version": "v1.0.0",
    "model": "gpt-...",
    "prompt_version": "loss_notice_v1_2026-01-05",
    "input_hashes": {
      "pdf_md5": "…",
      "di_text_md5": "…"
    }
  },
  "doc": {
    "doc_id": "doc_abc123",
    "claim_id": "claim_001",
    "doc_type": "loss_notice",
    "doc_type_confidence": 0.92,
    "language": "es",
    "page_count": 2
  },
  "pages": [
    {
      "page": 1,
      "text": "…azure di markdown for page 1…",
      "text_md5": "…"
    }
  ],
  "fields": [
    {
      "name": "claim_number",
      "value": "CN-24551-000217",
      "normalized_value": "CN-24551-000217",
      "confidence": 0.86,
      "status": "present",
      "provenance": [
        {
          "page": 1,
          "method": "di_text",
          "text_quote": "N° de siniestro: CN-24551-000217",
          "char_start": 1024,
          "char_end": 1056
        }
      ]
    }
  ],
  "quality_gate": {
    "status": "pass",
    "reasons": [],
    "missing_required_fields": [],
    "needs_vision_fallback": false
  }
}
```

### Why this is “enterprise”

* Every field is **auditable** (page + quote + offsets)
* You can run **regression tests** (stable schema + hashes)
* You can measure extraction quality independently from inspections

---

## 3) DocTypeSpec (how you define what to extract per doc type)

Yes: define extraction parameters **based on doc_type**. That’s how you stay crisp.

Here’s a simple spec format (YAML/JSON) you can keep in repo:

### `loss_notice` spec (v0)

```yaml
doc_type: loss_notice
required_fields:
  - claim_number
  - incident_date
optional_fields:
  - incident_location
  - vehicle_plate
field_rules:
  claim_number:
    normalize: uppercase_trim
    validate: non_empty
    hints:
      - "siniestro"
      - "claim"
      - "n°"
  incident_date:
    normalize: date_to_iso
    validate: is_date
    hints:
      - "fecha"
      - "date"
  vehicle_plate:
    normalize: plate_normalize
    validate: plate_like
    hints:
      - "placa"
      - "plate"
quality_gate:
  pass_if:
    - required_present_ratio >= 1.0
    - evidence_rate >= 0.8
  warn_if:
    - evidence_rate < 0.8
  fail_if:
    - required_present_ratio < 1.0
```

### `police_report` spec (v0)

```yaml
doc_type: police_report
required_fields:
  - incident_date
optional_fields:
  - report_number
  - report_date
  - location
  - vehicle_plate
field_rules:
  report_number:
    normalize: uppercase_trim
    validate: non_empty
    hints: ["parte", "reporte", "acta", "no."]
  report_date:
    normalize: date_to_iso
    validate: is_date
    hints: ["fecha de emisión", "fecha del reporte"]
  incident_date:
    normalize: date_to_iso
    validate: is_date
    hints: ["fecha del hecho", "ocurrido", "incidente"]
quality_gate:
  pass_if:
    - required_present_ratio >= 1.0
    - evidence_rate >= 0.7
```

This gives you a clean place to evolve extraction without touching code everywhere.

---

## 4) Chunking: you can mostly ignore it (for now)

Because DI is already **page-split**, your default strategy should be:

* **No chunking** for loss notice / police report
* Use **page-level extraction** with a “candidate span finder”:

  * search for hint keywords
  * pull ±500–1500 chars around hits
  * run structured extraction only on those snippets

You only need real chunking when you hit **long policy wordings**. That’s Phase 2.

---

## 5) Traceability: do this and you’ll look “serious” instantly

Minimum viable traceability for each extracted field:

* `page`
* `text_quote`
* `char_start/end`
* `method`: `di_text` vs `vision_ocr` vs `llm_parse`
* `confidence`
* `input hashes`

That’s enough for:

* QA review
* governance discussions
* “why did the model say that?” moments

---

## 6) Redacted dataset + placeholders: yes, extract them intentionally

Since the dataset is redacted, treat placeholders as valid values.

Two practical wins:

1. Extract `insured_name_placeholder` (e.g., `"PERSON_1"`) and check consistency across docs.
2. Add a field-level flag:

   * `value_is_placeholder: true/false`

This lets you build your consistency inspections without needing real PII.

---

## 7) A “pro” lightweight React frontend (no DB) that actually works

You have two good options:

### Option A — Pure static web app + “download labels”

* User loads `inventory.json` and extraction results via file upload
* UI shows doc + extracted fields
* Reviewer clicks Correct/Wrong/Unknown
* App generates a `labels.json` download

✅ zero server, zero DB
⚠️ labels need to be manually placed back into folders

### Option B — Local tiny server that reads/writes JSON (still no DB)

* Run a tiny Node/Python server on the customer server
* React app calls:

  * `GET /claims`
  * `GET /doc/:id`
  * `POST /labels/:doc_id` (writes JSON file)
* Still file-based storage; no database

✅ feels enterprise (because it saves)
✅ easiest for iteration
✅ still “on-prem”

If you’re willing to run a tiny server process, Option B is the sweet spot.

### UI screens (minimum)

1. **Claims list** (from inventory)
2. **Doc review**

   * Left: page text (DI markdown) and/or PDF viewer
   * Right: extracted fields (with evidence quote)
   * Buttons: Correct / Wrong / Unknown
   * “Needs vision” toggle if text unreadable
3. **Run summary**

   * pass/warn/fail counts
   * evidence rate
   * missing required fields leaderboard

This is enough to impress claims leadership *and* power your eval loop.

---

## 8) What you should build next (in order)

### Step 1 (today): Freeze the extraction contract

Create:

* `schemas/extraction_result_v1.json`
* `schemas/label_v1.json`
* `specs/loss_notice_v0.yaml`
* `specs/police_report_v0.yaml`

### Step 2 (1–2 days): Implement `loss_notice` extractor end-to-end

* candidate span finder
* structured extraction
* normalization + validation
* provenance
* quality gate

### Step 3 (2–3 days): Build the React “Extraction QA Console”

Start with Option A (downloads). Upgrade to Option B when you want file writes.

---

## Quick final question (so I tailor the UI approach)

Do you prefer:

* **A)** zero backend (download labels), or
* **B)** tiny local backend (writes labels JSON to disk)?

Answer: B

B it is — **tiny local backend + file-based storage** is the sweet spot: it feels “enterprise,” enables fast reps, and still avoids a DB.

Here’s a pro design you can implement in a week, end-to-end.

---

## Target architecture (no DB, but “real system” vibes)

### Files on disk (source of truth)

Per claim folder:

```
claim_001/
  inventory.json                 (optional, can also be global)
  docs/
    AVISO_DE_SINIESTRO.pdf
    AVISO_DE_SINIESTRO.di.md     (Azure DI per-page markdown)
    AVISO_DE_SINIESTRO.context.json   (your current context)
  extraction/
    AVISO_DE_SINIESTRO.extraction.json  (ExtractionResult v1)
  labels/
    AVISO_DE_SINIESTRO.labels.json      (Label v1)
```

Global:

```
data/
  inventory.json     (index of claims/docs)
schemas/
  extraction_result_v1.json
  label_v1.json
specs/
  loss_notice_v0.yaml
  police_report_v0.yaml
runs/
  run_2026-01-05T2310Z/
    summary.json
    metrics.json
```

---

## Backend API (minimal endpoints)

You only need 6 endpoints:

1. List claims/docs
   `GET /api/claims`

2. List docs for a claim
   `GET /api/claims/{claim_id}/docs`

3. Get a document payload (text-by-page + extraction result + label if exists)
   `GET /api/docs/{doc_id}`

4. Save labels (writes JSON to disk)
   `POST /api/docs/{doc_id}/labels`

5. Trigger extraction for a doc (optional convenience)
   `POST /api/docs/{doc_id}/extract`

6. Get run metrics / dashboard summary
   `GET /api/runs/latest`

That’s enough for a serious “Extraction QA Console”.

---

## Extraction contract (what your extractor must output)

Your extractor should write `*.extraction.json` with these sections:

* `doc` (ids + type + language)
* `pages` (page text, and **page-level hashes**)
* `fields[]` (value + normalized + confidence + **provenance**)
* `quality_gate` (pass/warn/fail + reasons)
* `run` (run_id, prompt version, model, input hashes)

### Field record (the money-maker)

Each extracted field must include:

* `value`
* `normalized_value`
* `confidence` (even coarse)
* `provenance[]`: `{ page, method, text_quote, char_start, char_end }`

This is what makes it auditable.

---

## Label schema (gold standard + eval data)

Your UI writes `*.labels.json`. Keep it dead simple:

* per extracted field: correct / incorrect / unknown
* optional corrected value (for future training or rules)
* optional reviewer notes

Example:

```json
{
  "schema_version": "label_v1",
  "doc_id": "doc_abc123",
  "claim_id": "claim_001",
  "review": {
    "reviewed_at": "2026-01-05T23:40:00Z",
    "reviewer": "fred",
    "notes": ""
  },
  "field_labels": [
    {
      "field_name": "incident_date",
      "judgement": "correct",
      "correct_value": "2024-01-13",
      "notes": ""
    },
    {
      "field_name": "claim_number",
      "judgement": "unknown",
      "notes": "Not visible in DI text; needs vision."
    }
  ],
  "doc_labels": {
    "doc_type_correct": true,
    "text_readable": "warn"
  }
}
```

This becomes your benchmark dataset automatically.

---

## Extraction design (doc-type–specific, evidence-first)

### Router pattern

* Classifier outputs `doc_type`
* `ExtractorRouter` calls `extract_loss_notice()` / `extract_police_report()`

### DocTypeSpec-driven

Yes: define fields per doc type (required/optional), normalizers, and hint keywords.

### Two-pass “Find → Extract” (no chunking pain)

Since you have DI text split by page:

1. **Candidate finder (deterministic + traceable)**

* For each field, scan pages for hint keywords
* Pull a window around hits (e.g., ±800 chars)
* Record page + char offsets

2. **Structured extraction (LLM → schema)**

* Feed only candidate snippets
* Require the model to return **value + supporting quote**
* Then you map quote back to `{page, char_start/end}`

If candidate finder finds nothing or text is garbage:

* mark quality gate `needs_vision_fallback: true`

---

## “How pros do traceability” in practice

You don’t need bounding boxes on day 1.

**Page + quote + offsets + method** is enough to:

* show evidence in UI
* debug failures
* convince claims leadership you’re not hallucinating

Also keep hashes:

* `pdf_md5`
* `di_text_md5`
* `page_text_md5`

So you can prove “same input” and detect drift.

---

## React UI data flow (clean + simple)

### Screen 1: Claim list

* `GET /api/claims`
* select claim → list docs

### Screen 2: Doc review (main screen)

* `GET /api/docs/{doc_id}`
  returns:

  * doc metadata
  * DI text by page
  * extraction result (fields + provenance)
  * existing labels if present

UI layout:

* Left: page selector + DI markdown text viewer (or PDF)
* Right: table of extracted fields:

  * value
  * confidence
  * evidence quote (click → scroll left to that page + highlight)
  * buttons: ✅ correct / ❌ wrong / ❓ unknown
  * optional corrected value input

Save:

* `POST /api/docs/{doc_id}/labels` with `label_v1`

### Screen 3: Run summary

* `GET /api/runs/latest`
* show:

  * pass/warn/fail counts
  * required-field missing leaderboard
  * evidence rate
  * “needs vision fallback” rate

This is what makes you look like you’re running a real program.

---

## Backend implementation suggestion (FastAPI)

FastAPI is perfect for “local on customer server” and quick JSON IO.

Key engineering details to be “pro”:

* atomic writes: write temp file then rename
* file locks (or simple per-doc lock) to avoid corruption
* never overwrite raw inputs
* log every run to `runs/<run_id>/`

If you want, I can give you a minimal FastAPI skeleton with these endpoints and file-safe writes.

---

## What you should build next (tight sequence)

1. **Freeze schemas**: `extraction_result_v1` + `label_v1`
2. Implement one extractor end-to-end: **loss_notice**
3. Build backend endpoints (claims list + doc payload + save labels)
4. Build React doc review screen
5. Start labeling 20–30 docs → now you have evals and credibility

---

## One last choice (tiny but important)

For the UI evidence highlight: do you want to display

* **A)** DI markdown text only (fastest), or
* **B)** embedded PDF viewer (pdf.js) + show evidence quote separately?

Answer: B
