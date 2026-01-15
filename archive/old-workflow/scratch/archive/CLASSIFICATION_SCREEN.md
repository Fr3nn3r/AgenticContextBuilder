Classification is a different job than extraction truth, and mixing them creates exactly the “this feels wrong” friction you’re noticing.

### Why it matters

* **Classification eval** asks: *“Did we pick the right doc_type?”*
* **Extraction eval** asks: *“Given the doc_type, did we extract the right fields?”*

If classification is wrong, extraction accuracy becomes meaningless. So you need a clean way to see and fix classification first.

---

## Pro approach (keep it simple)

You don’t need a big new app. Add a **Classification Review** screen that is run-aware and fast.

### What the screen should do

**Scope:** selected global run
**Unit of work:** documents (not fields)

For each doc:

* predicted `doc_type`
* `confidence`
* `signals` (2–5 short reasons from the classifier)
* quick preview (text/PDF tab)
* action: **Confirm / Change doc_type**
* optional: mark “Unsure” (if you want)

This produces a **doc_type override** (truth) stored per doc:

* default: assumed correct (no record)
* only store override when changed or unsure

### What it unlocks

* clean classifier accuracy KPIs per run
* confusion matrix (what gets confused with what)
* you can exclude “doc_type wrong” docs from extraction benchmark automatically

---

## Minimal screen structure

1. **Run header** (run id, extractor version, doc count)
2. KPI cards:

   * docs reviewed
   * overrides count
   * avg confidence
   * top confused pairs
3. Table:

   * doc_id / claim_id
   * predicted type + confidence
   * signals
   * current truth override (if any)
   * “Review” button

---

## Recommendation

Add this screen now, but keep it lightweight:

* no field-level truth here
* just doc_type truth/overrides

It will make your extraction benchmark cleaner and your workflow feel “correct.”


