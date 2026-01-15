## A simple, elegant solution: “Ground Truth Registry per (doc_id, field_name)”

### Core principle

For each document + field, store a **ground truth value when known**, and treat it as **read-only by default**.

Then each run simply compares:

> extracted_value (this run) vs ground_truth_value (if exists)

### Label states (clean and minimal)

Replace “correct/wrong/unknown” with these truth states:

1. **CONFIRMED** (ground truth exists)

* `truth_value` stored
* frozen by default

2. **UNVERIFIABLE** (truth cannot be established from this doc)

* no truth value
* requires a reason (e.g., unreadable / not present / wrong doc type)

3. **UNLABELED** (no decision yet)

* no truth value, no status

That’s it. No more ambiguous “wrong”.

### How the UI behaves

* If state is **CONFIRMED**:

  * show **Ground truth value** (locked)
  * show extracted value for current run
  * show result: match/mismatch
  * add button: **“Edit ground truth”** → asks confirmation → unlocks

* If state is **UNVERIFIABLE**:

  * show reason + optional notes
  * allow user to change to CONFIRMED if they later can verify (e.g., after using PDF/vision)

* If **UNLABELED**:

  * user can set to CONFIRMED (must provide value) or UNVERIFIABLE (must pick reason)

### Critical: “Correct” click becomes “Confirm truth”

When user clicks “Match/Correct”, you store the **truth_value** (usually equal to current extracted value, but user can edit before confirming).

---

## How this supports comparing runs (the whole point)

Once truth is stored, you can compute for any run:

* match rate
* mismatch rate
* extractor misses vs truth
* normalization issues (if you compare normalized forms)

And you can do it automatically across runs without relabeling.

---

## Simple instructions for devs (copy/paste)

### 1) Update label schema to store truth

Extend `label_v1` field entries to:

* `state`: `CONFIRMED | UNVERIFIABLE | UNLABELED`
* `truth_value` (required when CONFIRMED)
* `unverifiable_reason` (required when UNVERIFIABLE)
* `updated_at`

Example:

```json
{
  "field_name": "incident_date",
  "state": "CONFIRMED",
  "truth_value": "2024-02-08",
  "updated_at": "2026-01-06T15:10:00Z"
}
```

For unverifiable:

```json
{
  "field_name": "claim_number",
  "state": "UNVERIFIABLE",
  "unverifiable_reason": "not_present_in_doc",
  "updated_at": "2026-01-06T15:12:00Z"
}
```

### 2) UI: rename concepts and enforce the workflow

Replace “Prediction” with **Extracted (selected run)**.

Each field card shows:

* Extracted value (this run)
* Ground truth (if CONFIRMED, locked)
* Result badge: Match / Mismatch / Missing / Unverifiable / Unlabeled

Actions:

* **Confirm truth** (writes CONFIRMED + truth_value)
* **Mark unverifiable** (requires reason)
* **Edit truth** (requires confirmation modal)

### 3) Comparison logic

For metrics, only compare runs against fields with `state == CONFIRMED`.

* UNVERIFIABLE and UNLABELED are excluded from accuracy denominator.
* But they’re tracked as separate rates (reviewability / coverage issues).

### 4) Migration of existing labels (no relabeling required)

* For each existing field label:

  * if `judgement == correct` and extracted value exists → create `CONFIRMED` with `truth_value = extracted value` (using baseline run value)
  * if `judgement == unknown` → `UNVERIFIABLE` with reason = `cannot_verify`
  * if `judgement == wrong` → set `UNLABELED` (or `UNVERIFIABLE` if notes indicate not present) because no truth value exists

This preserves your work and upgrades it into benchmarkable truth.

### 5) Guardrails

* Default truth is locked; edits require explicit confirmation.
* Always show which run supplied the extracted value currently displayed.

---

## Why this is “pro”

This is exactly how serious evaluation systems work:

* create a small truth set
* lock it
* compare every new run against it
* only edit truth deliberately
