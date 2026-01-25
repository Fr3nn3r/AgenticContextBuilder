# UI Capabilities to Sharpen Claims Assessment

This is grounded in `docs/ASSESSMENT_FEEDBACK.md`.

## Capabilities to Build
- **Evidence-first check review**: Each check shows PASS/FAIL/INCONCLUSIVE with explicit evidence provenance (doc, page, field path, confidence). Missing evidence is visually flagged and blocks PASS.
- **Assumptions pane**: First-class assumptions table per run with `check_number`, `field`, `assumed_value`, `reason`, `impact`, plus `assumption_count` and `critical_assumptions` summary for routing.
- **Unknowns & missing-evidence tracking**: Per-check �missing critical evidence� list, and a run-level summary of unknowns. Force INCONCLUSIVE when critical evidence is missing.
- **Normalization view**: Explicit display of normalized dates and numeric fields (ISO dates, currency, odometer). Show raw vs normalized values for audit.
- **Deterministic mappings surfaced**: Read-only �part ? system� mapping resolution pane with source and version (not inferred by the model).
- **Schema validation & output health**: Live JSON schema validation errors, with a retry/fix flow if required fields are missing.
- **Extraction quality gate review**: Surface per-document quality gate status (pass/warn/fail), reasons, missing required fields, and evidence-rate thresholds; allow routing to re-extract or refer-to-human.
- **Evaluation dashboard**: Confusion matrix (strict scoring), accuracy by bucket, and warnings if `REFER_TO_HUMAN` is being counted as PASS.
- **Drift and quality monitoring**: Run-level metrics: assumption rate, missing-field rate, INCONCLUSIVE rate, and appeal outcomes trend.
- **Prompt & policy versioning**: Show prompt version used, policy rule set, and evaluation set version for each run.
- **Human-in-the-loop triage**: A �needs human� queue driven by low confidence/high-impact assumptions or missing critical evidence.

## How Pros Do It
- **Hard gate on evidence**: Require explicit, provenance-linked evidence to pass any check; otherwise INCONCLUSIVE/REFER_TO_HUMAN.
- **Separate extraction from reasoning**: Deterministic extraction + normalization first, then assessment; models never infer mappings like �Ventil ? system.�
- **Strict evaluation**: Confusion matrices and per-bucket metrics; no �auto-pass� for REFER_TO_HUMAN unless policy explicitly allows.
- **Versioned everything**: Prompts, schemas, policies, and evaluation sets are all versioned and visible in UI.
- **Assumptions as a risk signal**: Assumption count and critical assumption flags are first-class routing signals.
- **UI designed for auditability**: Every decision is traceable to source docs; raw + normalized values are side-by-side.
