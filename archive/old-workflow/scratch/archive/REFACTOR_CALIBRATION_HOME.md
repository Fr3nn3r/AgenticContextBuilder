## Dev brief: Replace “Calibration Home” with “Extraction" (global run)

### Goal

Make the current “Calibration Home” screen a **global run control-room** that clearly shows:

* selected **global run**
* run scope + status
* phase metrics for **Ingestion → Classification → Extraction**
* coverage + quality summaries
  No baseline/compare actions on this page.

---

## 1) Rename + purpose copy

* Rename page title: **Extraction**
* Subtitle: “Global metrics for one run across all processed claims.”

Remove “Calibration Home” language.

---

## 2) Run selection UX (replace dropdown)

The dropdown is not usable at scale.

### Replace with a left “Run History” panel (clickable list)

* Group by date
* Each run item shows:

  * timestamp (local)
  * run_id (shortened)
  * extractor version (and templates version if available)
  * docs processed count
  * status badge: `Complete | Partial | Failed`
  * “Latest” tag if applicable

Clicking a run updates the main panel.

(If you want to keep the dropdown temporarily, keep it only as a secondary control, but the list is primary.)

---

## 3) Add a “Run context header” (must-have)

At top of main panel show:

* Run ID (full on hover)
* Timestamp
* Status (Complete/Partial/Failed)
* Duration
* Scope: `Claims: X • Docs: Y • Doc types: …`
* Versions: extractor, templates, model/provider (if known)

This prevents KPI misinterpretation.

---

## 4) Phase cards (primary structure)

Top row: three cards (or four if you split “Quality Gate”):

### A) Ingestion

* Docs discovered
* Docs ingested
* Skipped (duplicates/unsupported)
* Failed ingest count
* Ingestion duration

### B) Classification

* Docs classified
* Low-confidence count
* Distribution (loss_notice / police_report / policy) counts
* Classification duration

### C) Extraction

* Docs attempted
* Docs succeeded
* Docs failed (with top error codes)
* Extraction duration

### D) Quality Gate (optional but recommended)

* PASS / WARN / FAIL counts
* Needs vision candidates count
* Evidence rate (from outputs)

> Important: All these are **run-scoped** metrics.

---

## 5) Coverage section (make label vs run explicit)

Show two bars:

* **Label coverage (truth)**: labeled docs / total docs (run-agnostic)
* **Run coverage (predictions)**: docs with extraction output in this run / total docs (run-scoped)

If label set isn’t global yet, at least label the definition clearly.

---

## 6) Doc Type Scoreboard (run-scoped)

Table by doc_type:

* docs in run
* extraction success rate
* gate pass/warn/fail
* field presence (required)
* evidence rate

Avoid showing “accuracy” here unless you have stored ground-truth values (otherwise it’s misleading). If you do have truth values, label it explicitly: “Accuracy vs Ground Truth”.

---

## 7) Quality summary (run-scoped)

Replace the current “Text Quality Good/Warn/Poor” with something that’s either:

* machine-derived text quality (if you have it), or
* extraction error breakdown (top 3 error codes)

If text quality is still based on doc labels you plan to drop, don’t surface it here.

---

## 8) No baseline/compare on this page

Explicitly remove:

* “Set as baseline”
* “Compare runs / Compare to baseline”
  These belong to a separate “Calibration” page.

---

## Definition of Done

* A user can answer in 10 seconds:

  1. What run am I looking at?
  2. Did it complete? What scope?
  3. Where did failures occur: ingest/classify/extract?
  4. How many docs were actually processed in this run?

* Run list is usable with 100+ runs (no giant dropdown).
