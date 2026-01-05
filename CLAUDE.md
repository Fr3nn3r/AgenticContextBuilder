### **CLAUDE.md (compact)**

**Priority order (if conflict):** Correctness > Security/Privacy > Maintainability (SSOT) > Simplicity (YAGNI) > Style.

**Operating mode**

* **Trivial changes** (typos, renames, small bugfix, isolated file, low risk): implement immediately.
* **Non-trivial** (touches core logic, auth/billing/data model, migrations, multi-file refactor, performance, security):

  1. 3–6 bullet plan
  2. Ask only *blocking* questions (max 5)
  3. If answers missing, proceed with clearly stated assumptions + smallest safe change.

**Architecture**

* Enforce **SSOT**: one place for state/logic; no duplicated rules.
* Apply **SOLID** pragmatically; **no speculative refactors**.
* Prefer standard libraries and existing project patterns.

**Error handling**

* Never swallow errors. Log once at boundaries with context **without secrets**.
* Use typed/custom errors internally; convert to user-safe messages at API/UI edges.

**Code style**

* Self-documenting naming; booleans read naturally; include units when ambiguous.
* Minimal comments: explain **why**, edge cases, or non-obvious constraints.
* Follow language conventions (Py: snake_case; TS: camelCase; classes PascalCase; constants SCREAMING_SNAKE).

**Testing**

* Add/update unit tests for new/changed logic paths (PyTest/Jest).
* Don’t rewrite test architecture unless asked.

**Context**

* If domain rules missing, consult `PROJECT_CONTEXT.md`. If still unclear, state assumptions. 