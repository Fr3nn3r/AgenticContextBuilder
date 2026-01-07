Here’s how to ask for a “quick code review + basic tests” that’s **high leverage**, **low churn**, and doesn’t trigger a refactor spiral.

---

## What you tell senior devs (the intent)

“We’re about to treat the next run as a **release-candidate baseline**. I want 1–2 focused review passes and a thin test harness that catches obvious breakage/regressions, without reorganizing the codebase.”

---

## Scope boundaries (explicitly prevent refactor creep)

**Do:**

* correctness, reliability, reproducibility checks
* small fixes that reduce risk of bad run artifacts
* add minimal tests around the most failure-prone parts

**Don’t:**

* restructure folders/modules
* rewrite pipeline architecture
* swap frameworks
* optimize performance unless there’s a bug

---

## The “quick review” checklist (what they must verify)

### 1) Run safety (highest priority)

* A run creates a unique run_id and doesn’t overwrite unless `--force`.
* If a doc fails, run continues and error is recorded (no silent drop).
* Outputs are written atomically (no half JSON).

### 2) Determinism of identifiers

* `doc_id` stable across reruns for same file.
* `claim_id` stable and consistent.

### 3) Schema correctness

* Extraction output always conforms to `extraction_result_v1` (even on failure: has status/error_code).
* Label parsing is robust (handles unknown, missing fields, etc.).

### 4) Evidence/provenance integrity

* Provenance never points to wrong doc/page.
* Evidence missing is explicitly flagged, not implied.

### 5) Error taxonomy consistency

* Every failure maps to a known error code.
* No raw exceptions leaking to UI without classification.

### 6) Metrics sanity

* Metrics exclude doc_type_wrong by default (or at least segment it).
* “Reviewed/labeled” is label-based, not run-based.
* Metrics are computed against the intended label set (latest labels).

---

## Basic tests (thin harness, big payoff)

Ask for **6–10 tests total**, no more. They should run in seconds.

### A) Unit tests (fast)

1. **Normalizers**

* date parsing → ISO
* plate normalization
* trimming/uppercasing

2. **DocTypeSpec validation**

* required_fields not empty
* fields are unique
* supported types list loads

### B) Contract tests (most important)

3. **ExtractionResult schema test**

* run extractor on 1 fixture doc_text
* validate JSON against the schema
* assert provenance exists for key field

4. **Label parsing test**

* load a sample `label_v1`
* assert it maps to expected internal objects

### C) Pipeline smoke test (end-to-end but tiny)

5. **Smoke run on a mini dataset**

* 1 claim folder with 2 docs
* run CLI
* assert:

  * run folder created
  * manifest + summary + metrics + log exist
  * `.complete` exists
  * outputs exist for doc_ids
  * no uncaught exception

### D) Metrics sanity test

6. **Metrics computation sanity**

* fixed labels + fixed extraction outputs
* assert computed accuracy/presence/evidence match expected numbers

That’s enough to catch the “baseline run killer” bugs.

---

## What “done” looks like (so they don’t overwork it)

* Review: 60–90 minutes total, 2 reviewers max
* Tests: green locally + in CI (if you have it; otherwise just local)
* Output: a short “RC readiness note” with:

  * what was checked
  * what was fixed
  * known limitations
  * go/no-go for running baseline

---

## How to keep iteration fast after baseline

Add a tiny rule:

* Any change to extraction logic must update:

  * extractor version string
  * run manifest
  * rerun smoke test

This prevents silent drift.

---

## Copy-paste message to your seniors

“Before the next extraction run, please do a release-candidate pass without refactoring. Scope: verify run safety (no overwrite, atomic writes), stable IDs, schema validity for extraction/labels, evidence/provenance correctness, consistent error codes, and metrics sanity (label-based reviewed, run-based evaluated). Add a thin test harness: normalizers, spec validation, extraction schema contract, label parsing, one CLI smoke run on a mini dataset, and a metrics sanity test. Target: <10 tests, fast, no architecture changes. Deliver a short RC readiness note and go/no-go.”
