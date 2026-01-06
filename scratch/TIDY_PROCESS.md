my output folder looks a bit messy I like things tidy what do you sugest? 

Yep — this is the classic “it worked, therefore it multiplied” folder 😄. The fix is to separate **immutable inputs** from **derived artifacts**, and to stop encoding meaning in filenames.

Here’s a tidy structure that stays clean even when you rerun pipelines 100 times.

---

## The core principles (why your folder is messy)

Right now you’re mixing:

* raw-ish stuff (DI markdown, original PDFs)
* intermediate (context.json)
* outputs (extraction.json)
* run logs (process-summary)
* multiple runs mixed together

Pros fix this with:

1. **one canonical place for raw inputs**
2. **one canonical place for “doc registry” metadata**
3. **runs are append-only and isolated**
4. **derived artifacts never sit next to raw inputs**

---

## Recommended folder structure (file-based, “enterprise tidy”)

### Option A (best): “Data lake + runs”

```
data/
  claims/
    <claim_id>/
      claim.json                 # claim-level metadata (optional)
      docs/
        <doc_id>/
          raw/
            original.pdf
          di/
            di.md                 # page-split markdown (or di_pages.json)
          meta/
            inventory.json        # doc metadata (hashes, size, etc.)

  registry/
    claims_index.json             # quick index for UI
    doc_index.json                # doc_id -> path lookup

runs/
  <run_id>/
    manifest.json                 # which docs processed, versions, hashes
    outputs/
      extraction/
        <doc_id>.json
      inspections/
        <claim_id>.json
    metrics/
      extraction_metrics.json
      inspection_metrics.json
    logs/
      process-summary.json
```

✅ Clean separation
✅ You can delete a run without losing raw inputs
✅ You can compare runs side-by-side
✅ UI can read from `registry/*` and “latest run” pointers

---

## Doc IDs: stop fighting filenames

Instead of file names like `29_01_2024_085647_PARTE_POLICIAL_(8)_acquired.md`, create a stable `doc_id` based on hash:

* `doc_id = sha1(file_bytes)[:12]` (or md5, you already compute it)
* keep the original filename as metadata in `inventory.json`

So you store:

```
docs/<doc_id>/raw/original.pdf
docs/<doc_id>/di/di.md
docs/<doc_id>/meta/doc.json
```

and `doc.json` contains:

* original filename
* doc_type
* language
* hashes
* claim_id
* ingest timestamp

This is how pros avoid exploding filenames.

---

## What to do with your current files

Right now you have:

* `*_acquired.md` (DI output)
* `*.pdf-context.json` (your context builder)
* `*.extraction.json` (your extraction result)
* `inventory.json`, `process-summary.json`

### Map them cleanly:

**Raw PDF**
→ `docs/<doc_id>/raw/original.pdf`

**Azure DI markdown (`*_acquired.md`)**
→ `docs/<doc_id>/di/di.md`
(or better: convert to `di_pages.json` if you want offsets stable)

**`pdf-context.json`**
This is “derived,” not raw. Put it under a run:
→ `runs/<run_id>/outputs/context/<doc_id>.json`
(or under `docs/<doc_id>/meta/context.json` if you consider it deterministic & stable)

**`*.extraction.json`**
Always run-scoped:
→ `runs/<run_id>/outputs/extraction/<doc_id>.json`

**`process-summary.json`**
Run-scoped:
→ `runs/<run_id>/logs/process-summary.json`

**`inventory.json`**
Make it canonical:
→ `registry/doc_index.json` + per-claim `claim_index.json`

---

## “Tidy but practical” minimal version (if you want less change)

If you don’t want a registry yet, do this:

```
claims/
  <claim_id>/
    docs/
      <doc_id>/
        raw/original.pdf
        di/di.md
        meta/doc.json
    runs/
      <run_id>/
        extraction/<doc_id>.json
        context/<doc_id>.json
        logs/process-summary.json
```

That alone will eliminate 90% of the mess.

---

## Naming conventions (simple rules)

* Never write output files next to inputs.
* Never use spaces or parentheses in stored filenames (store original name in metadata).
* Everything derived goes under `runs/<run_id>/...`
* Anything that can be recomputed should live in a run folder, not next to raw.

---

## One decision you need to make

Do you want your extraction outputs to be:

* **(1) per-document** (`<doc_id>.json`) — best for scaling, reuse, and UI
  or
* **(2) per-claim** (one big JSON) — simpler but harder to diff and rerun

I recommend **per-document**, with a claim-level “manifest” that points to doc outputs.

-------> ANSWER: (1) per-document


* where the root folder for all the claims datasets is data\04-Claims-Motor-Ecuador
* doc_id should be md5 (you already compute it)


Now “di” is a vendor-specific implementation detail. The tidy way is to name folders by **semantic role**, not by tool.

PRIORIZE thee following design:

### Rename the concept

Instead of `di/`, use a generic layer:

* `source/` = original artifact (PDF, images)
* `text/` = extracted text (from *any* method)
* `layout/` = optional structure (pages, tables, boxes)
* `meta/` = doc registry + hashes + doc type
* `runs/` = anything produced by a pipeline run (extraction, context, inspections, logs)

Then Azure DI becomes just one *producer* of `text/`.

---

## Recommended doc folder structure (tool-agnostic, supports images/vision)

Per document:

```
docs/<doc_id>/
  source/
    original.pdf
    pages/
      0001.png
      0002.png
  text/
    pages.json              # canonical: page -> text + offsets
    raw/
      azure_di.md           # optional: keep the raw DI md for trace/debug
      vision_ocr.json       # optional raw from other extractor
  meta/
    doc.json                # canonical metadata + hashes + doc_type
```

### Why this works

* PDFs and images are both first-class (`source/pages/*.png` covers scans)
* Your pipeline always reads from **`text/pages.json`** (stable interface)
* You can keep raw outputs from DI/vision for debugging without polluting everything

**Key idea:** choose **one canonical “text representation”** that all extractors consume.

---

## Canonical text format (the interface all downstream steps use)

Make `text/pages.json` the single truth for extracted text.

Example:

```json
{
  "schema_version": "doc_text_v1",
  "doc_id": "doc_abc123",
  "page_count": 3,
  "pages": [
    {
      "page": 1,
      "text": "....",
      "source": "azure_di",
      "quality": { "readability": "pass" }
    },
    {
      "page": 2,
      "text": "....",
      "source": "vision_ocr",
      "quality": { "readability": "warn" }
    }
  ]
}
```

Now your extraction stage doesn’t care whether text came from:

* Azure DI
* OCR / Vision
* a different vendor tomorrow

It only consumes `doc_text_v1`.

---

## Where “vision ingestion” fits cleanly

Treat “vision ingestion” as just another way to populate `text/pages.json`.

### Ingestion outputs (tool-agnostic)

* Always produce `text/pages.json`
* Optionally store tool-specific raw under `text/raw/…`

### Quality gate decides *when to use vision*

* If DI text unreadable or missing required fields → generate/refresh `text/pages.json` using vision OCR for those pages (or whole doc)

This makes vision a **fallback**, not a special case that pollutes your filesystem.

---

## Runs stay separate (still important)

Your *derived* outputs should be run-scoped:

```
runs/<run_id>/
  manifest.json
  outputs/
    extraction/<doc_id>.json
    context/<doc_id>.json
    inspections/<claim_id>.json
  logs/process-summary.json
  metrics/extraction_metrics.json
```

This keeps “what happened when” clean, and lets you compare runs.

---

## Minimal migration plan from your current “messy” folder

You already have:

* `*_acquired.md` (DI markdown)
* `*.pdf-context.json`
* `*.extraction.json`
* `inventory.json`

### Map them:

* `*_acquired.md` → `docs/<doc_id>/text/raw/azure_di.md`
* also create `docs/<doc_id>/text/pages.json` from that md (page-split)
* `*.pdf-context.json` → `runs/<run_id>/outputs/context/<doc_id>.json`
* `*.extraction.json` → `runs/<run_id>/outputs/extraction/<doc_id>.json`
* `inventory.json` → `registry/doc_index.json` (or per-claim `meta/claim.json`)

---

## Naming: avoid “implementation words” everywhere

Use these stable semantic names:

* `source/`
* `text/`
* `meta/`
* `runs/`

If you keep vendor outputs, put them under `text/raw/azure_di.*`, but never let them define your system boundaries.

---

## One choice to lock in (important)

Do you want the canonical text format to be:

* **A)** `pages.json` (recommended; stable offsets, easy provenance)
* **B)** `pages/*.md` files (human friendly but harder to track offsets cleanly)

-----> ANSWER: A



