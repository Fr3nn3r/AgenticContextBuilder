## What is an “AI-assisted coding ready” codebase?

It’s a codebase where a capable engineer can land a change in a few hours **without tribal knowledge**.

Agents need the same thing—just more strictly.

### The checklist that matters most

#### Reproducible setup

* one command bootstraps dev: `make setup` / `pnpm i` / `uv sync` / etc.
* pinned versions (node/python toolchain)
* minimal “do this manual thing in a hidden place”

#### Deterministic verification

* `make test` passes reliably
* `make lint` and formatting are consistent
* integration tests are runnable locally (even if slower)

#### Clear module boundaries

* “where to put things” is obvious
* interfaces exist at real seams (storage, external services, auth)

#### Good repo guidance for agents

* `AGENTS.md` with:

  * how to run tests
  * how to run lint
  * architecture rules
  * security rules (PII, logging)
    Codex is designed to read and follow that. ([OpenAI Developers][4])

#### Fast feedback loops

* tests run in minutes, not hours
* CI catches issues before you review

#### Unsafe things are hard to do

* secrets not in repo
* prod credentials unavailable in dev
* destructive commands gated by rules/approvals ([OpenAI Developers][3])

If you do nothing else: **make “run tests” reliable**. That’s the foundation of unattended autonomy.

---

## How do you enforce SOLID without triggering overengineering?

SOLID is great—until it becomes “Enterprise Patterns: The Musical.”

### The key: apply SOLID at boundaries, not everywhere

Use SOLID to protect places where change is expensive:

* external integrations
* storage
* auth
* domain logic
* compliance/PII workflows

Do **not** SOLID-ify every internal helper function.

### Add explicit anti-overengineering rules

Put these in `AGENTS.md` and your PR review checklist:

**Abstraction rules that prevent framework fever**

* **Rule of 3:** don’t create an abstraction until you have 3 real uses (or 2 implementations).
* **Interfaces only at seams:** external systems, storage, messaging, auth, or heavy test pain.
* **Prefer functions over class hierarchies** (unless language/ecosystem strongly pushes otherwise).
* **No DI containers** unless the codebase already uses one and it’s paying rent.
* **Avoid “future-proofing”** unless a real upcoming requirement is documented.

**A simple metric:**
If the change adds more files than tests, you’re probably building a cathedral.

### How to influence agent behavior (reliably)

Agents follow *examples + rules + friction*.

1. **Examples:** keep one or two “golden modules” that show your ideal style.
2. **Rules:** write them in `AGENTS.md` (Codex reads this) ([OpenAI Developers][4])
3. **Friction:** add linters, formatters, type checks, architectural tests (lightweight)

If you want one powerful trick:
**write a “preferred patterns” section with a few short code examples**. Agents copy patterns far more reliably than they follow abstract principles.

---

## What about front-end testing?

Front-end tests are where agents can accidentally create flaky nonsense, so structure matters.

### Use the “testing pyramid,” but modernized

1. **Unit tests** (fast)

* pure functions, utilities, reducers, validation

2. **Component tests** (most ROI)

* React Testing Library (or equivalent)
* test behavior: “user clicks → sees result”
* avoid testing implementation details

3. **E2E tests** (few, high value)

* Playwright or Cypress
* only critical user journeys:

  * login
  * onboarding happy path
  * core claim flow
  * payment flow (if relevant)

4. **Visual regression** (optional but very useful)

* Playwright screenshots or Chromatic-style tools
* catches “oops we broke layout” issues quickly

### Front-end flake reduction rules (important for autonomy)

* Prefer **role-based selectors** and stable test IDs (`data-testid`) only where needed
* Avoid time-based waits; use “expect eventually”
* Mock network in component tests (MSW is common)
* Keep snapshot tests minimal (snapshots are the junk drawer of testing)

### What to require from the agent on UI work

Add to your acceptance criteria:

* unit/component tests for new logic
* e2e only if it changes a critical flow
* don’t update snapshots blindly—explain why changes are expected

And put the commands in `AGENTS.md`:

* `pnpm test`
* `pnpm test:e2e`
* `pnpm lint`
  So the agent always knows how to verify. ([OpenAI Developers][4])

---
