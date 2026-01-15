You’re designing it correctly — your instinct is solid: this screen should be the **global run control room**, not a vague “home.” The confusion you’re feeling is a symptom of one missing anchor: **the run lifecycle + scope must be explicit everywhere.**

## Feedback on your prompt (and your design thinking)

### What you got right

* **Rename to “Extraction”**: yes. Even better: **“Extraction Run Overview”** or **“Run Overview”**. “Calibration Home” is fuzzy and doesn’t say what it does.
* **Global run level**: yes. This screen should describe one run across the whole dataset (not per claim).
* **3 phases (ingestion → classification → extraction)**: yes. That’s exactly how pros structure operational dashboards because it tells you where failures originate.
* **Dropdown is unfriendly**: yes. A long dropdown of run IDs is the “raw filesystem leaking into UI” problem. A **Run History list** is the pro pattern.

### Your blindspots (small but important)

1. **You’re mixing two sources of truth without naming them**

   * Labels (human truth) are run-agnostic
   * Run outputs (predictions, gates, failures) are run-scoped
     Your screen must show both without blending them, otherwise KPIs look “wrong” (like your 2.2% presence issue earlier).

2. **You need to define “scope of the run”**
   A global run might include:

   * all claims
   * a subset (test)
   * only certain doc types
     If you don’t show “Run scope: X claims, Y docs, doc types: …”, your KPIs can be misread.

3. **You’re missing “completion state”**
   Pro run dashboards always show:

   * status: running / complete / failed / partial
   * duration
   * error counts
     Without this, you can’t trust the numbers.

4. **Run selection UX needs “meaning,” not IDs**
   A list is better than dropdown, but also add *meaningful labels*:

   * timestamp
   * extractor version
   * docs processed
   * PASS/WARN/FAIL summary
     Otherwise it’s still just IDs in a different wrapper.

---

## What I recommend (pro approach, minimal complexity)

### Rename + reposition

* Page title: **Extraction Run Overview**
* Subtitle: “Global metrics for a single run across all processed claims.”

### Replace dropdown with Run History panel

Left panel:

* grouped by date
* shows each run with:

  * time
  * extractor version
  * processed docs count
  * status badge (PASS/WARN/FAIL or Complete/Partial)
  * “Latest” tag

This solves usability and makes “many runs” non-annoying.

### Make the 3 phases the primary structure (top row)

Instead of generic KPIs, use three phase cards:

**Ingestion**

* docs discovered
* docs ingested
* duplicates skipped
* failures

**Classification**

* docs classified
* low-confidence count
* doc-type distribution
* (optional) misclassification rate if doc_type overrides exist

**Extraction**

* extraction succeeded
* gate pass/warn/fail counts
* required-field presence
* evidence rate
* needs-vision candidates

### Keep “Coverage” but label it clearly

Show two progress bars with explicit labels:

* **Label coverage (truth)**: labeled docs / total docs
* **Run coverage (predictions)**: docs with extraction output in this run / total docs

### Add “Run metadata strip”

At top-right (or under title):

* run_id, timestamp
* extractor version, templates version, model (if relevant)
* duration
* scope: claims count, docs count, doc types included

---

## About the mock you asked for

The mock concept is right: **run history left + phase cards top + coverage/scoreboards below**. That’s the standard pattern used in serious data/ML ops tooling because it matches how humans debug pipelines.

---

## One last recommendation (so this becomes a true control room)

Add two actions:

* **Set as baseline**
* **Compare to baseline**
  Even if “Compare” just shows deltas on the same screen (no extra page), it turns this from a static report into a calibration program.

If you want, I can turn this into a short dev brief (“Implement v2 of Run Overview”) with exact sections and what each KPI means, so the screen becomes self-explanatory.
