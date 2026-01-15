Playwright is perfect here — but keep it **thin and high-signal**, like a seatbelt, not a full crash-test lab.

## What to implement in Playwright (the “pro MVP” suite)

### 1) Smoke: app loads + core nav works

* Load ContextBuilder
* Assert sidebar shows only: **Claim Document Pack**, **Calibration Insights**, **Extraction Templates** (and whatever you kept)
* Navigate to each screen without errors

✅ Catches broken builds, routing, missing assets.

---

### 2) Run context: run selector works everywhere it matters

On **Claim Document Pack**:

* Assert Run selector exists (default “Latest”)
* Switch to another run
* Assert claim row gate counts / doc badges update (or at least the run label changes + a loading state appears)

On **Calibration Insights**:

* Assert run context header shows run_id + extractor version
* Switch run and confirm KPIs change (or show “no data for this run” gracefully)

✅ Catches the biggest integrity risk: UI showing mixed-run data.

---

### 3) Claim review flow: next/prev + doc navigation strip

* Open a claim review
* Assert **Prev/Next claim** controls exist
* Assert doc strip exists and shows doc_type + labeled/unlabeled + gate
* Click a different doc in the strip, verify header updates to that doc name/type

✅ Validates the primary workflow is stable.

---

### 4) Evidence navigation (Text tab) — must work

* In claim review, go to a doc with at least one field that has provenance
* Click an evidence snippet
* Assert:

  * correct page selected
  * highlighted span exists (or “evidence located” marker)
  * viewport scrolled near the highlight

✅ This is the trust lever; if it breaks, debugging becomes painful.

---

### 5) Save review persists (labels)

* Make a doc-level label change (doc type correct: yes/no/unsure) + add notes
* Click **Save review**
* Reload the page
* Assert the selection + notes persisted

✅ Catches broken write paths and “it looked saved” bugs.

---

### 6) Templates screen contract

* Open **Extraction Templates**
* Assert the 3 supported doc types appear
* Click each and verify fields list shows required vs optional

✅ Ensures spec visibility stays accurate.

---

## How to structure Playwright tests (so they don’t become brittle)

* Use **data-testid** attributes for:

  * run selector
  * claim rows
  * doc strip items
  * save button
  * evidence links
  * highlight marker
* Avoid matching raw text content except for headers/titles.
* Seed a small fixture dataset (2 claims) for deterministic tests.

---

## Bonus: add 1 visual regression test (optional, high ROI)

Pick **one** canonical viewport (e.g., 1440×900) and snapshot:

* Claim Document Pack
* Claim Review
* Calibration Insights

Use Playwright’s screenshot compare with a small threshold.

✅ Catches spacing/typography regressions with minimal effort.

---

# UI look & feel review (usability + consistency): what I recommend

Two parts: a quick heuristic pass + a consistency system.

## A) Quick heuristic checklist (what to fix first)

Ask your devs to check:

* **Typography hierarchy**: KPIs readable from 1 meter away (big numbers, clear labels)
* **Consistent naming**: “Run”, “Labels”, “Evaluated”, “Gate” mean the same everywhere
* **Whitespace discipline**: tables dense enough to scan; avoid dead zones
* **Primary CTA consistency**:

  * “Save review” always same position and style
  * “Next unlabeled” always available in review context
* **Status visuals**:

  * PASS/WARN/FAIL consistently colored and styled
  * “needs vision” shown as subtle badge/icon, not a column

## B) Add a lightweight “Design Contract”

Tell devs to define:

* base spacing scale (4/8/12/16)
* type scale (H1/H2/body/label)
* standard components:

  * KPI card
  * status badge
  * table row
  * filter pill
  * run selector

This reduces “each screen invented its own style.”

---

## What I would do next (order)

1. Implement Playwright tests 1–5 (smoke, run selector, claim review flow, evidence jump, save persists)
2. Add 1 visual snapshot test for Insights (since you’re iterating layout there)
3. Do a UI consistency pass after tests are green, not before

---

If you paste your route list (or the nav items + URLs) and confirm whether your UI is React Router/Next.js/etc., I can give you a ready-to-run Playwright test outline with suggested `data-testid` names.
