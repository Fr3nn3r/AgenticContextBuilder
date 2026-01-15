

Yes — and you *should*. Ingestion is expensive and mostly deterministic; classification/extraction are the parts you’ll iterate.

### The clean mental model

* **Ingestion produces immutable artifacts**: doc_id, raw file, canonical text (`pages.json`), doc metadata.
* **Runs produce derived artifacts**: classification + extraction outputs + metrics.

So you can re-run classification/extraction many times against the same ingested corpus.

---

## What to tell devs (simple, concrete)

### 1) Split the pipeline into explicit commands/modes

Support:

* `ingest` (or your existing `acquire`) → creates/updates doc store only
* `classify` → reads existing docs/text, writes run outputs only
* `extract` → reads existing docs/text + doc_type, writes run outputs only
* `run` (optional convenience) → ingest + classify + extract

### 2) Make “run” a derived snapshot, not a copy of inputs

When you run `classify`/`extract`, create a **global run folder**:

* `output/runs/<run_id>/manifest.json`
* `output/runs/<run_id>/classification/*.json`
* `output/runs/<run_id>/extraction/*.json`
* `output/runs/<run_id>/metrics.json`
* `.complete`

**Do not duplicate PDFs/text into the run folder.** Runs reference doc_ids.

### 3) Add flags for reuse / avoid re-ingest

Add CLI flags:

* `--use-existing-ingest` (default true)
* `--ingest` (explicitly run ingestion)
* `--force-reingest` (rare; only when input corpus changed)

### 4) Add selection controls

Let you run on subsets:

* `--doc-types fnol_form,police_report`
* `--claims <id1,id2>` or `--limit N`
* `--since <date>` (optional)

### 5) Define what happens if ingestion artifacts are missing

If a doc has no `text/pages.json`:

* classify/extract should skip with `TEXT_MISSING` (in run summary)
* not crash
* not silently drop

---

## What this means for the “run workflow” definition

Update your run concept:

* A **global run** can be:

  * `kind: ingest` (rare)
  * `kind: classify` (common)
  * `kind: extract` (common)
  * `kind: full` (ingest+classify+extract)

Run manifest must record:

* run_kind
* whether ingestion was performed or reused
* dataset snapshot (doc_ids included)
* versions (templates/extractor/prompt/model)

So yes: you can have many runs sharing the same ingested corpus.

---

## One sentence you can give them

“Make ingestion an immutable corpus step; make runs derived outputs. Add CLI modes so we can rerun classify/extract against existing ingested docs without re-ingesting.”
