Got it: **claim-first stays**. Then the design goal is:

> A claim row is a *container*, but the **work happens at the document level**.

So we keep your expandable claim list, but we remove claims-QA baggage and make the expanded area a proper **document calibration queue**.

Here’s what to tell the team.

---

## 1) Rename + reposition (so the UI stops lying)

### Screen name

* **Claim Workspace** (or **Claim Document Pack**)
  Subtitle: “Document extraction calibration and labeling”

### Row status language

Replace “Risk / Flags” semantics with extraction semantics.

Top-of-page KPI:

* `19 claims`
* `Docs labeled: 42 / 120`
* `Docs failing gate: 11`
* `Needs vision: 6`

This instantly tells the truth.

---

## 2) Claim list: keep claim-first, but change the columns

### Remove / de-emphasize (not relevant for extraction calibration)

* Risk Score
* Loss Type
* Amount

You can keep LOB and claim ID, but the rest should be extraction-centric.

### Suggested claim row columns (high-signal)

* **Claim ID**
* **LOB** (optional)
* **Docs** (e.g., `5`)
* **Labeled** (e.g., `2/5`)
* **Gate** (e.g., `1 PASS • 3 WARN • 1 FAIL`)
* **Needs Vision** (e.g., `1`)
* **Last processed** (date/time)

This is a *work queue* summary.

### Filters that matter (top bar)

* Doc gate status: PASS/WARN/FAIL (filters claims where any doc matches)
* “Has unlabeled docs”
* “Needs vision”
* Doc type (loss_notice / police_report / policy)
* Search by Claim ID (keep)

---

## 3) Expanded claim section: make it a “Document Pack Queue”

When you expand a claim, don’t just list docs as a flat list.

### Add a mini header in the expanded area

**“Document Pack”**

* `5 documents • 2 labeled • 1 fail`

Add an action button:

* **Review next unlabeled** (one click takes you to the next doc that needs review)

### Document rows inside the claim (these columns)

* **Document name** (display original filename)
* **Doc type** + confidence (e.g., `police_report • 0.80`)
* **Text quality** (Good/Warn/Bad)
* **Extraction gate** (PASS/WARN/FAIL)
* **Missing required fields** (e.g., `incident_date`)
* **Labeled** (Yes/No)

Sort order inside claim:

1. FAIL
2. WARN
3. Unlabeled
4. PASS labeled

This makes reviewers productive instantly.

### Badges (make them meaningful)

Replace “Extracted” with:

* **Gate: PASS**
* **Gate: WARN**
* **Gate: FAIL**
  and a small pill:
* **Labeled** / **Unlabeled**
* **Needs Vision** (if applicable)

---

## 4) Document Review screen: tighten it for calibration work

Keep the two-pane layout but adjust semantics and actions.

### Rename the screen

* **Extraction Review** (subtitle: “Validate fields against source text”)

### Top bar (sticky)

* Doc name + claim ID
* Doc type + confidence
* Text source (DI / Vision) and Text quality
* Gate status (PASS/WARN/FAIL)
* Buttons:

  * **Save review**
  * **Next unlabeled doc** (within the same claim, then next claim)

### Right pane: extracted fields (make it faster to label)

For each field:

* Human label + technical key:

  * **Incident date** (`incident_date`)
* Value + normalized (already good)
* Confidence (keep small)
* Evidence snippet (clickable)
* Buttons:

  * ✅ Correct
  * ❌ Wrong (shows corrected value input)
  * ? Cannot verify (rename from unknown)

Add **keyboard shortcuts**:

* 1/2/3 for correct/wrong/cannot verify
* n for next field
* N for next unlabeled doc

This turns it from “pretty demo” into a real tool.

---

## 5) Fix the evidence click (must-have)

Tell them this is non-negotiable for trust.

### Required provenance format

Each field must provide:

* page
* char_start
* char_end
* text_quote

### UI behavior on evidence click

* switch to provenance page
* scroll to char_start
* highlight the span
* if offsets missing, fallback to searching `text_quote` in that page

If they implement only one improvement, make it this one.

---

## 6) Copy + labels (make terms semantically dense)

Replace:

* “Claims Review” → **Claim Workspace**
* “Document Review” → **Extraction Review**
* “PASS” → **Gate: PASS** (explicit)
* “unknown” → **Cannot verify**
* “present” → **Extracted**
* “Save Labels” → **Save review**

Also show:

* **Run ID** + extractor version (small text)
  This signals “calibration program,” not “UI prototype.”

---

## 7) Super crisp ticket you can paste to them

Here’s the exact instruction block:

**Ticket: Refactor Claim-first UI into Extraction Calibration UX**

* Keep claim-first list with expandable claim rows.
* Replace claim table columns with extraction-work metrics: Docs, Labeled, Gate summary (PASS/WARN/FAIL counts), Needs Vision, Last processed.
* In expanded claim view, show a document queue with columns: Document name, Doc type+confidence, Text quality, Extraction gate, Missing required fields, Labeled yes/no. Sort by FAIL → WARN → Unlabeled → PASS.
* Rename screens: “Claim Workspace” and “Extraction Review”.
* Add “Review next unlabeled” CTA at claim level and “Next unlabeled doc” on review screen.
* Evidence click must navigate to exact location in text: use provenance `{page,char_start,char_end,text_quote}` to jump+highlight; fallback to quote search.
* Rename labeling: correct / wrong / cannot verify; add keyboard shortcuts 1/2/3, n/N.

---
