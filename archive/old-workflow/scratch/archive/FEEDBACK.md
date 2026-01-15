The PO has now fully specified the intended product shape:

* This is a **focused document extraction calibration tool** (not ClaimEval), rebranded to **ContextBuilder**.
* Workflow is **claim-first** with a **claim-level review route**, and reviewers should be able to process claims sequentially in dataset order with **Prev/Next** navigation that **auto-opens the next unlabeled document**.
* Labeling is **document-level only** (no field-level adjudication needed right now), with doc type correctness as **yes/no/unsure**.
* “Needs vision” remains meaningful but should be **non-column signal** (badge/indicator inside the doc pack and doc header).
* Review page must provide **compact doc navigation** inside claim review (doc strip/list), show richer context at top, and move doc label controls up near the header and save action.
* Add a new **Extraction Templates** screen showing supported doc types, extracted fields, and full template/spec detail (read-only).
* Viewer must support tabs: **Text / PDF / Image / JSON**, rendered conditionally. PDF viewer should be embedded and chosen with **future highlighting** in mind.

## Developer feedback (structured tickets; assume strong engineers)

### 0) Rebrand / Scope cleanup

**Rename product:** ClaimEval → **ContextBuilder** (logo/text, page titles, any hardcoded strings).
**Remove unrelated nav + panels:**

* Remove: QA Insights, Reports, Settings (unless needed for basic config), demo reviewer panel bottom-left.
* Keep minimal nav:

  * **Claim Document Pack** (claim list)
  * **Claim Review** (claim-level review route, can be hidden from nav if accessed via list)
  * **Extraction Templates** (new)

**Acceptance:** UI looks like a dedicated extraction calibration tool with no ClaimEval/QA modules.

---

### 1) Claim list screen: rename + refine claim-first queue

**Rename screen:** “Claim Workspace” → **Claim Document Pack**.
**Keep claim-first list with expandable claim rows** (as current), but:

#### 1.1 Remove / adjust columns

* Remove claim table column **Needs vision**.
* Claim columns should remain extraction-calibration oriented:

  * Claim ID, LOB, Docs, Labeled (x/y), Gate summary (PASS/WARN/FAIL counts), Last processed.

#### 1.2 “Needs vision” becomes a non-column signal

* Keep “needs vision” as:

  * a **badge** within the expanded document list rows (e.g., “Needs vision”),
  * and optionally a small icon/badge in the claim row if *any* doc in the pack needs vision (but not its own column).

#### 1.3 Expanded claim row (Document Pack)

* Keep “Review next unlabeled” CTA.
* Ensure doc rows show compactly:

  * doc name
  * doc type (and confidence if available)
  * gate status
  * labeled/unlabeled
  * “needs vision” badge when applicable
* Sort docs within pack by: **Unlabeled first**, then FAIL/WARN, then PASS labeled (or Unlabeled+FAIL/WARN at top; keep predictable).

**Acceptance:** reviewer can expand a claim and clearly see which docs require attention; “needs vision” is visible but not a column.

---

### 2) Claim Review (new/updated): one route per claim, doc navigation inside

**Routing:** Implement **one route per claim**, e.g. `/claims/:claimId/review`.
This page is the primary review workspace.

#### 2.1 Global claim navigation (topmost)

At the very top of the page, add:

* **Prev claim / Next claim** arrows.
* Navigation follows **full dataset order** (not filtered order).
* On entering a claim (via prev/next or deep link), **auto-open the next unlabeled doc** in that claim.

  * If all labeled, open first doc (or last opened doc).

#### 2.2 Claim header context (top section)

Show clear claim context:

* Claim ID + LOB
* Document pack summary: `# docs`, `# unlabeled`, gate counts
* Run metadata: `run_id`, extractor version (small text)

#### 2.3 Doc navigation strip/list (within claim)

Add a compact, clickable list of docs at top of workspace (horizontal strip or vertical mini list):

* Each doc item shows:

  * **Doc type**
  * **Gate status** (PASS/WARN/FAIL)
  * **Labeled/Unlabeled**
  * (Optional small icons: needs vision)
* Clicking a doc switches the active doc in-place (no route change needed beyond query param optional).

#### 2.4 Document-level controls near the top (not bottom)

Move document label controls to the document header area:

* **Doc type correct**: yes / no / unsure (document-level label)
* **Notes** (document-level) placed near **Save review**
* Remove reviewer name field.

#### 2.5 Save & next ergonomics

Buttons:

* **Save review** (saves doc-level label + notes)
* **Next unlabeled doc** (within claim)
* Optional: “Mark remaining docs as ‘unsure’ ” (only if you think it helps throughput; otherwise skip)

**Acceptance:** reviewer can process a claim end-to-end without going back to the list; next/prev claim is one click; doc switching is instant.

---

### 3) Document Viewer tabs: Text / PDF / Image / JSON

In the Claim Review document section, implement conditional tabs depending on availability:

* **Text** tab: from canonical `text/pages.json` (or equivalent)
* **PDF** tab: embedded PDF viewer when original PDF exists
* **Image** tab: for standalone image documents (and optionally page images if available)
* **JSON** tab: show both

  * extraction result JSON
  * doc text JSON (pages)
    (either as sub-tabs or a dropdown)

#### PDF viewer choice

Pick a viewer with a path to future highlighting:

* Prefer **pdf.js-based** viewer (React wrapper) so you can later add text-layer highlights or custom overlays.
* Ensure viewer supports:

  * page navigation programmatically
  * text selection layer (for future highlight)
  * zoom

**Acceptance:** tabs only appear when artifacts exist; PDF view is embedded and stable; JSON view is readable.

---

### 4) Evidence navigation behavior (must support Text now; PDF/Image later)

Even though labels are doc-level only, keep evidence navigation because it builds trust and will matter once field-level returns.

**Text tab (must):**

* Clicking any evidence snippet (or “jump to evidence” action) navigates to:

  * correct page
  * scroll to `char_start`
  * highlight `char_start..char_end`
* Fallback: search `text_quote` on page and highlight first match.

**PDF tab (v1):**

* On evidence click, at least navigate to the correct page.
* Highlighting can be deferred but choose viewer accordingly.

---

### 5) New screen: Extraction Templates (read-only)

Add top-level nav item: **Extraction Templates**.

Screen shows:

* Supported doc types list
* For selected doc type:

  * extracted fields (required vs optional)
  * normalization + validation rules
  * hint patterns (if available)
  * current extractor/prompt version info

Data source:

* Backend should expose `GET /api/templates` generated from your DocTypeSpec registry (single source of truth, no manual duplication).

**Acceptance:** business/PO can understand supported types and extracted fields without reading code.

---

### 6) Backend API updates (support claim-level review + templates + viewer availability)

Provide a claim review payload endpoint, e.g.:

* `GET /api/claims/:claimId/review` returns:

  * claim metadata
  * ordered doc list for claim with status fields:

    * doc_id, doc_type, gate_status, labeled_status, needs_vision, available_views
  * default `active_doc_id` (next unlabeled)
  * optionally: links to prev/next claim IDs (dataset order)

* `GET /api/docs/:docId` returns:

  * doc metadata
  * text pages (for Text tab)
  * extraction output (for JSON tab)
  * source artifact presence (PDF/image flags)
  * saved doc label + notes if exist

* `POST /api/docs/:docId/review` saves:

  * doc_type_correct = yes/no/unsure
  * notes
  * (optionally) text_quality doc-level label if you keep it

* `GET /api/templates` returns templates as described.

**Acceptance:** frontend does not touch filesystem; it relies entirely on API.

---

### 7) UI cleanup checklist (explicit removals)

* Remove ClaimEval naming in header/sidebar/footer.
* Remove demo reviewer panel bottom-left.
* Remove unused nav items as per scope.
* Ensure the “Claim Document Pack” list is the entry point; Claim Review can be accessed from doc/claim actions.

---

If you want this to land fast, I’d implement in this order:

1. Rebrand + remove nav/panels
2. Claim Review route per claim + doc strip + doc-level labels + prev/next claims
3. Viewer tabs (Text + PDF first, then Image/JSON)
4. Extraction Templates screen
5. Evidence click → page/offset highlight (Text tab)
