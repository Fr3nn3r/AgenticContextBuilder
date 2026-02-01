# Plan: NSA Minimum Viable Review Experience

**Date**: 2026-02-01
**Priority**: P0
**Goals**: (1) NSA sees progress/velocity, (2) NSA validates output async, (3) support efficient walkthroughs

---

## Core Insight

The product is already built. ClaimExplorer has 42 components — assessment display, coverage matrix, document viewer, payout breakdown, customer draft modal, and a WorkflowActionsPanel with rating/comments (wired to console, not persisted). The `reviewer` role already hides Pipeline, Templates, Admin, Compliance.

**The bottleneck is deployment, not features.**

---

## Three Phases

### Phase 0: "Come see what we built" — Deploy existing app

**Goal**: NSA can see the product on their 50 claims. Delivers Goal 1 (see progress) and Goal 3 (walkthrough support).

**Tasks:**

| Task | File/Location | Effort |
|---|---|---|
| SEC-01: Upgrade to bcrypt password hashing | `src/context_builder/api/services/users.py:66-74` | Low |
| SEC-02: Remove default credentials | `src/context_builder/api/services/users.py:81-103` | Low |
| SEC-03: Encrypt/hash session tokens | `src/context_builder/api/services/auth.py:64-76` | Medium |
| SEC-04: Add login rate limiting | API middleware | Low |
| SEC-05: Validate file magic bytes on upload | `src/context_builder/api/routers/upload.py:164-170` | Low |
| Deploy to accessible infrastructure | TBD (Vercel, Swiss VM, or cloud host) | Medium |
| Create NSA reviewer accounts | Admin panel or script | Low |
| Pre-load 50 eval claims with latest assessments | Already done — claims are in workspace | None |

**What NSA sees:**
- ClaimExplorer: assessment decisions, per-check results, payout breakdown, document viewer with highlighting
- Claims table: all 50 claims browsable
- Evaluation page: accuracy metrics
- Document review: PDFs, images, extracted data

**What's hidden (reviewer role):**
- Pipeline control, extraction templates, admin panel, compliance audit, cost tracking

---

### Phase 1: "Tell us if we're right" — Feedback loop

**Goal**: NSA reviews claims async, marks correct/incorrect. Delivers Goal 2 (validate without meetings).

**Tasks:**

| Task | Details | Effort |
|---|---|---|
| `POST /api/claims/{id}/feedback` endpoint | Save rating (correct/incorrect) + comment to `workspaces/nsa/claims/{id}/feedback.json` | Low |
| `GET /api/claims/{id}/feedback` endpoint | Retrieve feedback for display | Low |
| Wire WorkflowActionsPanel to backend | Replace `console.log` with API call. File: `ui/src/components/ClaimExplorer/WorkflowActionsPanel.tsx` | Low |
| Claims review list | New view or modify existing claims table: columns = claim ID, system decision, payout, review status (pending/reviewed/correct/incorrect) | Low-Medium |
| Feedback status badge | Show reviewed/pending on each claim in the list | Low |

**Feedback JSON schema:**
```json
{
  "claim_id": "64166",
  "reviewer": "stefano",
  "rating": "correct",
  "comment": "Decision correct, but payout should be CHF 1,450 not 1,506",
  "timestamp": "2026-02-03T14:30:00Z",
  "assessment_run_id": "clm_20260131_104745"
}
```

**How NSA uses it:**
1. Open claims list — see which claims are pending review
2. Click a claim — see the assessment in ClaimExplorer
3. Review decision, checks, payout, coverage
4. Click correct/incorrect, add optional comment
5. Move to next claim
6. Stefano reviews ~10 claims/day in 20 minutes

**What this enables for us:**
- Direct feedback on specific claims from the domain expert
- Error categorization without scheduling meetings
- Feedback becomes input for next eval iteration
- Track which claims NSA has validated vs. which are still pending

---

### Phase 2: "Here's WHY each item isn't covered" — Explain WHY feature

**Goal**: Every non-covered item has a policy-referenced explanation. Delivers the adjuster-facing value Stefano asked for.

**Full spec**: `plans/plan-explain-why-not-covered.md`

**UI tasks (after backend feature is built):**

| Task | Details | Effort |
|---|---|---|
| `NonCoveredExplanationsCard` component | Display grouped exclusions with policy references, amounts, confidence. Collapsible groups. | Medium |
| Add to ClaimAssessmentTab | New section below existing checks, before payout breakdown | Low |
| Per-item policy reference display | Show "General Terms, Section 4.2" or "Policy schedule, Option Turbo: Non couvert" inline | Low |
| Confidence indicator | If match_confidence < 0.8, show "needs verification" badge | Low |

**Example display:**

```
Non-Covered Items (3 groups, CHF 2,545.50 total)

▼ Consumables — CHF 85.50
  General Terms, Section 4.2 (Exclusions)
  "Oils, filters, and lubricants are consumable maintenance items,
   excluded from all guarantee types."
  • Motoröl 5W-40 (2.5L) — CHF 65.00
  • Ölfilter — CHF 20.50

▼ Turbo Components — CHF 2,340.00
  Policy Schedule — Option Turbo: Non couvert
  "Turbo and turbocharger components require the Turbo option.
   Your BASIC guarantee does not include this option."
  • Turbolader-Kompressor — CHF 2,340.00

▼ Diagnostic Labor — CHF 120.00
  General Terms, Section 4.2 (Exclusions)
  "Standalone diagnostic work and system testing are classified
   as investigative labor, not repair labor."
  • Diagnose / Fehlerspeicher auslesen — CHF 120.00
```

---

## What NOT to Build

| Skip | Reason |
|---|---|
| Client-specific dashboard/landing page | ClaimExplorer IS the dashboard |
| Client branding/theming | NSA cares about accuracy, not colors |
| New auth system for clients | Existing auth + reviewer role works |
| Client-specific API routes | Same endpoints, role-based access |
| Read-only mode toggle | Reviewer role already controls edit access |
| Client action audit trail | Not needed for feedback loop |
| Email notifications | Weekly meeting cadence is already in place |
| Progress/accuracy dashboard | Show eval results in meeting; build dashboard later if needed |

---

## Dev Team Assignments

Three independent work packages, can run in parallel (one per worktree):

### Worktree 1: Security hardening (Phase 0)

> Fix SEC-01 through SEC-05 in the backend. All documented in BACKLOG.md with file locations and effort estimates. No feature changes. Goal is to unblock deployment.

**Files to change:**
- `src/context_builder/api/services/users.py` (password hashing, default creds)
- `src/context_builder/api/services/auth.py` (session tokens)
- `src/context_builder/api/routers/upload.py` (file validation)
- New middleware for rate limiting

**Done when:** All 5 SEC items resolved, tests pass, no default passwords.

### Worktree 2: Feedback persistence (Phase 1)

> WorkflowActionsPanel already collects ratings and comments but logs to console. Wire it to a new endpoint that persists feedback to workspace storage. Add a review status column to the claims list. Keep it simple — JSON file per claim.

**Files to change:**
- New: `src/context_builder/api/routers/feedback.py` (new router)
- New: `src/context_builder/api/services/feedback.py` (storage logic)
- Modify: `ui/src/components/ClaimExplorer/WorkflowActionsPanel.tsx` (API call instead of console.log)
- Modify: claims list component (add review status column)

**Done when:** Stefano can open a claim, click correct/incorrect, add a comment, and it persists. Claims list shows which claims have been reviewed.

### Worktree 3: Explain WHY (Phase 2)

> See `plans/plan-explain-why-not-covered.md` for full spec. Backend: add policy references to exclusion rules, group NOT_COVERED items by reason, generate explanation templates. Frontend: add NonCoveredExplanationsCard to ClaimAssessmentTab.

**Files to change:**
- Backend: coverage analyzer, schemas, customer config
- Frontend: new component in `ui/src/components/ClaimExplorer/`
- Customer config: explanation templates in `workspaces/nsa/config/coverage/`

**Done when:** Every NOT_COVERED item has a policy-referenced explanation, grouped by reason, displayed in the assessment tab. Eval accuracy not regressed.

---

## Deployment: Azure Swiss VM

**Decision**: Azure VM in Switzerland (Swiss data residency). Azure subscription already exists.

**Infrastructure needed:**
- Azure VM (Switzerland North region) — Ubuntu, sized for FastAPI + React build
- Nginx reverse proxy (HTTPS termination, serve React static build, proxy `/api` to uvicorn)
- Let's Encrypt or Azure-managed SSL certificate
- DNS record (subdomain of trueaim.ai or dedicated)
- Firewall: expose 443 only, SSH via Azure Bastion or IP-restricted
- Workspace data stored on VM disk (or Azure Files mount if persistence matters beyond VM lifecycle)

**Deployment pipeline:**
1. Build React frontend (`npm run build`) → static files
2. Nginx serves static files + proxies `/api` to uvicorn on localhost:8000
3. Uvicorn runs FastAPI app with workspace data on local disk
4. Git pull or rsync for updates (automate later with CI/CD if needed)

**No Docker required for MVP** — direct install is faster to set up and debug. Containerize later.

---

## Success Criteria

| Goal | Metric | Phase |
|---|---|---|
| NSA sees progress | Stefano/Dave have logged in and browsed claims | Phase 0 |
| Async validation | Stefano has reviewed 20+ claims without a meeting | Phase 1 |
| Efficient walkthroughs | Adjuster session uses the UI, not Excel files | Phase 0 |
| Explain WHY value | Stefano says "this is what I need" for coverage explanations | Phase 2 |

---

## Dependencies & Blockers

| Blocker | Blocks | Owner |
|---|---|---|
| Security hardening (SEC-01–05) | Deployment (Phase 0) | Dev team |
| Infrastructure decision (where to deploy) | Deployment (Phase 0) | Fred |
| Adjuster session | Exact explanation wording, payout formula (Phase 2) | Fred + NSA |
| Business rules answers | Coverage accuracy improvements | NSA (Stefano/Dave) |
| Blind test set (20-30 fresh claims) | Production accuracy validation | NSA (Stefano) |

---

## References

- Strategy analysis: `docs/NSA-strategy-and-next-steps.md`
- Explain WHY spec: `plans/plan-explain-why-not-covered.md`
- Business rules review: `docs/NSA-BUSINESS-RULES-REVIEW.md`
- Security items: `BACKLOG.md` (SEC-01 through SEC-05)
- Eval process: `docs/EVAL-process.md`
- Current UI components: `ui/src/components/ClaimExplorer/` (42 components)
- Auth/roles: `ui/src/context/AuthContext.tsx`
- Feedback panel: `ui/src/components/ClaimExplorer/WorkflowActionsPanel.tsx`
