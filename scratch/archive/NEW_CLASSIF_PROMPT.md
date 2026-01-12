


We're going to update our classifier (NB: I added 2 new file specs in src\context_builder\extraction\specs)

our new classifier prompt is as follows:


---
name: Claims Document Classification (Generic Router)
model: gpt-4o
temperature: 0.1
max_tokens: 1200
description: Classifies insurance claim documents across LOBs and geographies. Router only (light hints, no deep extraction).
schema_ref: DocumentClassificationRouterV1
---

system: |
  You are an insurance claims document classifier. Your job is to ROUTE each document to the correct document_type
  using the document content (not the filename). You must be accurate and conservative: if unsure, choose supporting_document
  and lower confidence rather than forcing a wrong type.

  You will be given:
  1) A list of allowed document types with short definitions and cue phrases.
  2) The document text content (may be noisy OCR).

  Output must be valid JSON and follow this schema:
  - document_type: one of the allowed types
  - language: primary language code (e.g., "en", "es", "fr")
  - confidence: number from 0.0 to 1.0 representing how confident you are in the document_type
  - summary: 1-2 sentences describing what the document is
  - signals: array of 2-5 short strings explaining the strongest evidence for the chosen type (e.g., headings/keywords/layout cues)
  - key_hints: OPTIONAL object with at most 3 lightweight hints ONLY if clearly present (do not guess).
      Allowed keys in key_hints: policy_number, claim_reference, incident_date, vehicle_plate, invoice_number, total_amount, currency

  Rules:
  - Do NOT rely on the filename for classification; it may be wrong.
  - Do NOT perform full field extraction. Only populate key_hints if the value is obvious.
  - If content is empty/garbled, set confidence low and choose supporting_document.
  - Never invent values. If unclear, omit key_hints or leave it empty.

user: |
  Allowed document types (choose exactly one):
  {{ doc_type_catalog }}

  Document filename (do NOT rely on it for classification, informational only):
  {{ filename }}

  Document content:
  {{ text_content }}


+++++++++++++++++++++++++++++++++ END PROMPT

Notice we need to inject the document catalog

1) Template-driven doc type catalog (source of truth)

Implement

Create specs/doc_type_catalog.yaml as the single source of truth for classification:

Each entry:

doc_type

description (1 sentence)

cues (3–8 keywords/headings, language-agnostic when possible - english by default)

2) Classifier prompt injection (dynamic)
Implement

Modify classifier code to build doc_type_catalog dynamically from doc_type_catalog.yaml and inject into the prompt.

Prompt output must include:

document_type, language, confidence, summary, signals[]

key_hints optional (max 3 fields)

Acceptance

classifier always uses the catalog from disk (not static text).

unit test: catalog loads + prompt is rendered with all types.

++++++++++++++++++++++ 
design chat:

currently I have the version of the template in the filenmae as well as the file itself, it may be useful to keep all files available for history in the UI? not sure that's the best practice though... what do you suggest?

### Best practice (what I’d do)

1. **One “current” template per doc type**

* `templates/loss_notice.yaml`
* `templates/police_report.yaml`
* etc.

2. **Versioning is metadata, not filename**
   Inside the file:

```yaml
doc_type: loss_notice
version: v1
```

3. **Archive old versions in a separate folder**

* `templates/_archive/loss_notice_v0.yaml`
* `templates/_archive/loss_notice_v1.yaml`

Or keep them in git tags/releases and don’t ship them in the runtime folder.

### What the UI should show

UI should show **only the current templates** by default:

* doc types supported
* fields extracted
* version

Optional: add a small “History” drawer later (nice-to-have), but you can get 95% of the value by:

* showing the current version
* and showing which version was used in each run (from run manifest)

### Why filenames-with-versions hurts you

* Your loader now needs logic to pick “latest”
* People will accidentally load the wrong one
* It creates “duplicate doc types” confusion

### Simple recommendation

* **Rename files to stable names now** (no version in filename)
* Keep old versions either:

  * in git (preferred), or
  * in `templates/_archive/` (good enough)

That keeps runtime simple and still preserves history when you need it.
