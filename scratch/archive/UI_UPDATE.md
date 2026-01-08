Not complicated if you give them the right contract. The trick is: **don’t ask them to “understand your pipeline.”** Ask them to build a UI against **stable API responses** and a **file-based backend** that hides the folder structure.

Here’s exactly what to tell them.

---

## What you tell the devs (the brief)

### Goal

Build an **Extraction QA Console** UI that:

* lists claims and documents
* shows canonical per-page text (`text/pages.json`)
* shows extraction results (fields + evidence)
* lets a reviewer label fields (correct/wrong/unknown) and saves labels to disk
* no database

### Key principle

**UI never reads the filesystem directly.**
It calls a tiny backend API. The backend adapts to the new folder structure.

---

## Data contract the UI should rely on (don’t expose file paths)

### 1) Claims list

`GET /api/claims`

Response:

```json
{
  "claims": [
    { "claim_id": "claim_001", "doc_count": 12, "last_run_id": "run_..." }
  ]
}
```

### 2) Docs list per claim

`GET /api/claims/{claim_id}/docs`

Response:

```json
{
  "claim_id": "claim_001",
  "docs": [
    {
      "doc_id": "doc_abc123",
      "original_name": "AVISO_DE_SINIESTRO.pdf",
      "doc_type": "loss_notice",
      "language": "es",
      "page_count": 2,
      "text_status": "pass",
      "latest_extraction": { "run_id": "run_...", "quality_gate": "warn" },
      "has_labels": true
    }
  ]
}
```

### 3) Document detail (the main review payload)

`GET /api/docs/{doc_id}`

Response:

```json
{
  "doc": {
    "doc_id": "doc_abc123",
    "claim_id": "claim_001",
    "original_name": "AVISO_DE_SINIESTRO.pdf",
    "doc_type": "loss_notice",
    "language": "es"
  },
  "text": {
    "schema_version": "doc_text_v1",
    "page_count": 2,
    "pages": [
      { "page": 1, "text": "...." },
      { "page": 2, "text": "...." }
    ]
  },
  "extraction": {
    "schema_version": "extraction_result_v1",
    "run_id": "run_...",
    "quality_gate": { "status": "warn", "reasons": ["low_evidence_rate"] },
    "fields": [
      {
        "name": "incident_date",
        "value": "2024-01-13",
        "confidence": 0.78,
        "provenance": [
          { "page": 1, "text_quote": "Fecha del incidente: 13/01/2024", "char_start": 1024, "char_end": 1058 }
        ]
      }
    ]
  },
  "labels": null
}
```

### 4) Save labels (write JSON file)

`POST /api/docs/{doc_id}/labels`

Body:

```json
{
  "schema_version": "label_v1",
  "reviewer": "fred",
  "field_labels": [
    { "field_name": "incident_date", "judgement": "correct", "correct_value": "2024-01-13" }
  ],
  "doc_labels": { "doc_type_correct": true, "text_readable": "pass" }
}
```

Backend writes:
`docs/<doc_id>/labels/latest.json` (or versioned)

Return:

```json
{ "ok": true }
```

---

## UI changes required (what they actually need to update)

Tell them these are the only changes:

### A) Replace the “DI markdown” assumption

Previously: UI may have loaded `*_acquired.md` directly.
Now: UI must render **canonical text** from `text.pages[]`.

So the text viewer becomes:

* page selector
* shows `pages[i].text`
* highlight evidence using `char_start/char_end` when provided

### B) Evidence highlighting (nice-to-have but easy)

When user clicks an extracted field:

* jump to the provenance page
* highlight the substring in the page text using offsets
  If offsets missing, just show the `text_quote`.

### C) No file paths in UI

They must stop using filenames as identifiers. Use:

* `doc_id`
* `claim_id`
* `run_id`

Original filename is display-only.

### D) Labels are first-class

UI adds per-field triage buttons:

* ✅ correct / ❌ wrong / ❓ unknown
  and an optional “correct value” input shown only when ❌ wrong

---

## Backend changes required (developer-friendly)

This is where the structure change lives. The UI stays stable.

Backend responsibilities:

* scan registry / claim folders and build doc list
* load `docs/<doc_id>/text/pages.json`
* load latest extraction result from `runs/<run_id>/outputs/extraction/<doc_id>.json`
* load labels from `docs/<doc_id>/labels/latest.json` if present
* write labels atomically

This is not hard—just disciplined IO.

---

## Acceptance criteria (so you get what you want)

Give them these checkboxes:

1. UI loads a claim list and doc list without showing filesystem paths
2. Doc review screen shows per-page text from `doc_text_v1`
3. Fields show value + confidence + evidence quote
4. Clicking a field jumps to the right page
5. Reviewer can label fields and save; refresh shows labels persisted
6. Works offline/on-prem with local backend (no cloud)

---

## Is it complicated?

No. It’s mostly **wiring to a clearer API** and removing assumptions about “DI files.” The refactor is typically:

* 1–2 days backend (if the folder structure is stable)
* 1–2 days frontend (swap data sources + add labels UI)

The only “gotcha” is evidence highlighting offsets—optional at first.

---

## One choice you should make now (so devs don’t churn)

Where should labels be stored?

* **Option 1:** `docs/<doc_id>/labels/latest.json` (simple)
* **Option 2:** `runs/<run_id>/labels/<doc_id>.json` (labels tied to a run)

I recommend **Option 1** because labels are “human truth” and should persist across runs.

ANSWER: 1
