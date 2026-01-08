Yep — you’ve discovered the real issue: you currently have **claim-scoped runs**, not **workspace-scoped runs**.

So the dropdown is showing you “run IDs” that exist *inside each claim folder*, and there is no single “run that processed the whole dataset,” because it was never recorded at the global level.

That’s why it feels messy and why “Latest” appears a million times: it’s *latest per claim*, not *latest overall*.

## What “pro” looks like (simple)

You need **two layers**:

### 1) A global workspace run (one per execution)

`output/runs/<run_id>/...`
Contains:

* `manifest.json` (which claims/docs were included)
* `metrics.json` (overall KPIs)
* `summary.json` (overall counts + failures)
* `claims.json` index (optional)
* `.complete`

### 2) Optional per-claim outputs (for locality)

Still fine to keep per-claim extracted artifacts if you want, but they should be *referenced* from the global run.

---

## Minimal fix (no serious refactor)

Don’t move all files right now. Just **add a global run registry + aggregation step**.

### Add: `output/runs/<run_id>/` (new)

When you run the pipeline across `output/claims/*`:

1. create `output/runs/<run_id>/manifest.json`
2. write `output/runs/<run_id>/logs/run.log`
3. aggregate metrics into `output/runs/<run_id>/metrics.json`
4. write `output/runs/<run_id>/summary.json`
5. create `.complete`

### Manifest should include pointers to per-claim outputs

Example:

```json
{
  "run_id": "run_20260106_212719_a1784ec",
  "claims": [
    {
      "claim_id": "24-06-VH-7054370",
      "claim_run_path": "output/claims/ROBO_TOTAL_24-06-VH-7054370_GTK9199/runs/run_20260106_212719_a1784ec/"
    }
  ]
}
```

So you don’t need to reorganize per-claim run folders yet.

---

## UI fix (immediate)

Update the run dropdown to load runs from:

* **`output/runs/`** (global runs only)

Not from each claim folder.

Then:

* Claim Document Pack screen uses global run selector
* To render a claim row, it looks up that claim’s outputs for the selected global run via manifest pointers

If a claim wasn’t processed in that run:

* show “Not in run”

---

## What to tell your devs (copy/paste)

“We need workspace-level runs. Right now we only have claim-level runs under `output/claims/<claim>/runs/<run_id>`, which makes run selection meaningless globally. Please add a global run registry at `output/runs/<run_id>/` with manifest/summary/metrics/.complete for runs executed across multiple claims. Do not refactor file locations yet: the global manifest can reference existing per-claim run folders. Update the UI run selector to read only from `output/runs/`.”

---

## Why this matters

Once you have global runs:

* baseline is one run id, universally
* comparisons are real
* dropdown becomes sane
* “Latest” means something

If you paste your current CLI behavior (does `acquire` run across all claims in the input folder at once?) and I’ll suggest exactly where in the code to create the global run folder + how to aggregate metrics across claims.
