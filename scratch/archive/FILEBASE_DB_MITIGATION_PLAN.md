Here are clear senior-dev instructions to implement **(1) a storage abstraction** and **(2) indexes**, without turning it into a refactor marathon.

---

## Goal

Keep filesystem as the system of record, but:

1. isolate all reads/writes behind a **Storage interface** (so DB swap later is painless),
2. generate **indexes** so the UI can query fast without scanning folders.

No schema redesign. No moving files. Minimal code churn.

---

# 1) Storage abstraction (minimal, practical)

## Scope

Create a new module: `context_builder/storage/` and route all backend file IO through it. Frontend should never touch disk directly.

## Required interface (Python)

Define an abstract base + a filesystem implementation.

### `Storage` methods (keep tight)

* `list_claims() -> list[ClaimRef]`
* `list_docs(claim_id) -> list[DocRef]`
* `get_doc(doc_id) -> DocBundle`
  (doc metadata + available artifacts + paths)
* `get_doc_text(doc_id) -> DocText` (pages.json)
* `get_extraction(run_id, doc_id) -> ExtractionResult | None`
* `get_label(doc_id) -> Label | None` (latest.json)
* `save_label(doc_id, label) -> None` (atomic write)
* `list_runs() -> list[RunRef]` (from global `output/runs/`)
* `get_run(run_id) -> RunBundle` (manifest + metrics + summary)
* `get_templates() -> TemplatesBundle`

### Non-goals

* no caching layer yet (can add later)
* no DB implementation yet
* no massive object model; simple dataclasses/pydantic models ok

## Implementation requirements

* **Atomic writes** for labels (`tmp` + rename)
* **Path resolution** happens only in the storage layer
* All consumers use ids (`claim_id`, `doc_id`, `run_id`), not paths

## “Definition of done”

* Search codebase for direct `open()` calls in backend; only Storage uses them (except tests).
* Existing UI features still work, now backed by Storage.

---

# 2) Indexes (fast query without scanning)

## Philosophy

Indexes are derived artifacts. Rebuildable. Treated like “cache,” not truth.

## Index types

Create `output/registry/` and write:

1. `doc_index.jsonl` (one line per doc)
2. `label_index.jsonl` (one line per doc with label summary)
3. `run_index.jsonl` (one line per run: metadata + pointers)
   Optional later:

* `field_truth_index.jsonl` (per doc_id+field when LABELED)

**Use JSONL** (append-friendly, fast streaming).

## Doc index record (minimum)

Each line:

* `doc_id`, `claim_id`, `doc_type`, `filename`
* artifact availability: `has_pdf`, `has_text`, `has_images`
* timestamps (ingested_at if available)
* stable hashes if available (pdf_md5/text_md5)

## Label index record (minimum)

Each line:

* `doc_id`, `claim_id`
* `has_label` (bool)
* `labeled_fields_count`
* `unverifiable_fields_count`
* `unlabeled_fields_count`
* `updated_at` (from label file)
* optional: `doc_type_override` if you keep it

## Run index record (minimum)

Each line:

* `run_id`, `started_at`, `status` (`complete|partial|failed`)
* `extractor_version`, `templates_version`
* `claims_count`, `docs_processed_count`
* pointers: `manifest_path`, `metrics_path`

## Build/update strategy

Implement a CLI:

* `context_builder.cli index build --root <output_root>`

  * scans filesystem once
  * writes fresh JSONL indexes (and maybe a `registry_meta.json`)
* Optional:

  * `index refresh --incremental` later

For MVP: **full rebuild is fine**.

## Backend usage

* For list screens (Claim Document Pack, Run list), backend should read indexes first.
* For doc detail, backend loads concrete files via Storage.

## Consistency rule

* Index build should run after each extraction run completes (can be a pipeline step), or manually.

## “Definition of done”

* UI no longer scans folders; claim/doc lists load fast using indexes.
* Rebuilding indexes doesn’t change truth, only speeds up discovery.

---

# Migration plan (low disruption)

1. Implement Storage, keep current paths intact.
2. Add index builder CLI.
3. Modify backend list endpoints to use indexes.
4. Keep fallbacks: if index missing → do a slower scan (with a warning).

---

# Quick acceptance checklist (for you to verify)

* [ ] Can I delete `output/registry/*` and rebuild with one command?
* [ ] Does the app still work after rebuild?
* [ ] Are labels written atomically and always loaded from `docs/<doc_id>/labels/latest.json`?
* [ ] Does run list come from global `output/runs/` rather than per-claim folders?

---


Feedback on the output tree: 

Perfect — your tree is actually in a good place already:

* You have **global runs**: `output/runs/<run_id>/…` ✅
* You have **claim roots**: `output/claims/<claim_folder>/…` ✅
* Some claims have **docs/** with doc_id folders ✅
* Some claims still have **per-claim runs** under the claim folder (fine for now; your global run is the UI source of truth)

Below is how I’d tailor the **Storage abstraction + indexes** to *exactly* what you have, with minimal churn.

---

## 1) What to standardize (conceptually) from this tree

### Claim identifier

Your claim folders are inconsistent in naming (`25-01-VH-7068967` vs `ROBO_TOTAL_-24-01-VH-…`). Don’t fight the folder names.

**Best practice now:** treat folder name as `claim_folder_id`, and read the real `claim_id` from:

* global run manifest, or
* a claim-level metadata file (add later), or
* doc meta (`docs/<doc_id>/meta/doc.json` should include claim_id)

So your Storage/Index layer should not assume claim_id can be parsed reliably from folder names.

---

## 2) Storage abstraction: how to resolve things with your current layout

Your Storage implementation should treat these as the canonical discovery roots:

* **Global runs**: `output/runs/`
* **Claims**: `output/claims/`

### Global run selection

UI run selector should list only:

* `output/runs/<run_id>/.complete` runs

Everything else is noise.

### How to locate docs

Docs appear under:

* `output/claims/<claim_folder>/docs/<doc_id>/…`

So `Storage.get_doc(doc_id)` should be backed by an index lookup (see below), not by filesystem search.

---

## 3) Index design customized to your tree

Create `output/registry/` with:

### A) `doc_index.jsonl` (required)

Build it by scanning:

* `output/claims/*/docs/*/meta/doc.json`

Each record should include:

```json
{
  "doc_id": "2baad7c5814d",
  "claim_folder": "ROBO_TOTAL_24-07-VH-7053863_MBG7356",
  "claim_id": "24-07-VH-7053863",
  "doc_type": "police_report",
  "filename": "DENUNCIA 1.png",
  "paths": {
    "doc_root": "output/claims/.../docs/2baad7c5814d",
    "pdf": "output/claims/.../docs/.../source/original.pdf",
    "text_pages": "output/claims/.../docs/.../text/pages.json",
    "images_dir": "output/claims/.../docs/.../source/pages"
  },
  "available": { "pdf": true, "text": true, "images": true },
  "hashes": { "pdf_md5": "...", "text_md5": "..." }
}
```

Notes:

* `claim_id` should come from `doc.json` if possible (prefer this).
* If `doc.json` doesn’t include claim_id yet, store `claim_folder` and keep `claim_id` null for now.

### B) `run_index.jsonl` (required)

Build it by scanning:

* `output/runs/*/manifest.json` where `.complete` exists

Each record should include:

```json
{
  "run_id": "run_20260107_094028_034cc09",
  "status": "complete",
  "started_at": "...",
  "extractor_version": "...",
  "templates_version": "...",
  "claims_count": 18,
  "docs_count": 67,
  "paths": {
    "run_root": "output/runs/run_...",
    "manifest": "output/runs/run_.../manifest.json",
    "metrics": "output/runs/run_.../metrics.json",
    "summary": "output/runs/run_.../summary.json"
  }
}
```

### C) `label_index.jsonl` (recommended)

Build it by scanning:

* `output/claims/*/docs/*/labels/latest.json` (if exists)

Each record:

* doc_id
* has_label
* labeled_fields_count / unverifiable_count / unlabeled_count
* updated_at (if present)

This powers fast “docs labeled” counts without opening lots of files.

---

## 4) How to handle per-claim runs (your current `output/claims/.../runs/...`)

You do **not** need to delete or refactor these immediately.

**Instruction:** ignore them for UI selection.

* UI run selector uses **global** runs only (`output/runs/`)
* When rendering a doc for a selected global run, the backend reads predictions from the global run outputs (or from pointers inside the global manifest).

If global run output isn’t stored centrally yet and still lives in claim folders, then the global `manifest.json` must contain pointers to the per-claim run outputs.

---

## 5) Index builder CLI (one command)

Implement:

`context_builder.cli index build --root output`

It should:

1. rebuild doc_index.jsonl
2. rebuild label_index.jsonl
3. rebuild run_index.jsonl
4. write `registry_meta.json` with build timestamp + counts

For MVP: full rebuild is fine.

---

## 6) Quick sanity checks (important)

From your screenshot, you already have:

* `output/runs/run_20260107_094028_034cc09/metrics.json` ✅
* `.complete` ✅

So the “too many runs” UI issue can be solved immediately by:

* only listing runs from `output/runs/*` with `.complete`
* using `run_index.jsonl`

---

## What I’d ask your devs to do *first*

1. Ensure every `docs/<doc_id>/meta/doc.json` includes:

   * `doc_id`, `claim_id`, `doc_type`, `filename`
2. Implement `doc_index.jsonl` + `run_index.jsonl` build
3. Update the backend list endpoints to use the indexes

That’s the biggest speed/clarity win with minimal refactor.


Nice — this is already close to what you need. Two things are missing that will matter immediately for indexes + UI:

## What’s missing / weak in `doc.json`

1. **claim_id** (or claim_folder id)
   Without it, you can’t group docs into a claim pack reliably (your folder names aren’t parse-safe).

2. **paths / availability** (or enough info to infer them)
   The UI needs to know whether PDF/text/images/json exist without probing the filesystem repeatedly.

Everything else looks good.

---

## Minimal changes I’d ask devs to make (low churn)

### 1) Add `claim_id` (required)

Add one field:

```json
"claim_id": "24-07-VH-7053863"
```

If you don’t have a true claim id at ingest time, then add:

```json
"claim_folder": "ROBO_TOTAL_24-07-VH-7053863_MBG7356"
```

…but ideally store the actual `claim_id`.

### 2) Add a lightweight `artifacts` availability block (recommended)

Add a small section that the UI/indexer can use:

```json
"artifacts": {
  "pdf": true,
  "text_pages": true,
  "images": false,
  "extraction_json": true
}
```

This can be computed during ingest/acquire and stored once.

### 3) Clarify hashes (tiny consistency)

Right now `doc_id` is not the same as `file_md5` (doc_id is short). That’s fine, but be explicit:

* keep `doc_id` as your short id
* keep `file_md5` as full hash

No change needed; just make sure everyone treats `doc_id` as the primary key.

---

## Doc index record you can build from this

Once you add `claim_id`, your indexer can produce a `doc_index.jsonl` record like:

* `doc_id`
* `claim_id`
* `doc_type`
* `doc_type_confidence`
* `language`
* `original_filename`
* `page_count`
* `created_at`
* `artifacts` (availability)
* (optional) `paths` (either store or derive deterministically)

---

## Short instructions for devs (copy/paste)

“Update `docs/<doc_id>/meta/doc.json` to include `claim_id` (required). Add an `artifacts` availability object so the UI/indexer can know what exists without scanning. Everything else can remain as-is. This enables reliable claim grouping and fast `doc_index.jsonl` creation.”



