### 1) Add a run context header (everywhere)

At top of Claim Document Pack and Document Pack Review:

* **Run:** `<run_id>` (dropdown)
* **Extractor:** `vX.Y.Z`
* Tooltip: “Gate + extracted values shown are from this run.”

This instantly fixes 60% of confusion.

### 2) Rename “Gate” column to “Extraction Gate (Run)”

And add tooltip:

* PASS/WARN/FAIL based on required fields + evidence + extraction errors.

### 3) Replace “0%” with labeled chips

In the document list (left column), replace `0%` with:

* `Coverage: x/y` (always)
* `Accuracy: z%` (only if labels exist for this doc)
  Optional third:
* `Evidence: z%`

### 4) In the field cards, separate Prediction vs Label

For each field card:

**Prediction (Run run_...)**

* value
* badge: Extracted / Missing
* evidence link

**Label (Truth)**

* buttons: correct / wrong / cannot verify
* if already labeled, show current label state (e.g., “Label: correct”)

This makes it impossible to misread.

### 5) Add doc-level summary: “Labeled vs Not labeled”

At top of the right panel:

* “Label status: Saved / Not saved”
* “Fields labeled: x/y”

### 6) Fix the “Claim Number missing in loss_notice” confusion (bonus clarity)

If a field is **not expected** for this doc type, do not show “Missing” in red.
Show:

* “Not expected for loss_notice” (neutral)
  (or hide it by default and allow “show optional fields”).

This prevents “the system is failing” when the spec is wrong.

---

## Quick definitions you can keep in your head

* **Gate** = machine QC status, per doc, per run.
* **Extracted value** = prediction from selected run.
* **Your clicks** = label/truth saved to file (run-agnostic).
* **Accuracy** = comparison of run prediction vs labels (only meaningful when labeled).
