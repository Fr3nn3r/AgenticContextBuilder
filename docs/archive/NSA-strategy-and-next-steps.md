# NSA Strategy & Next Steps

**Date**: 2026-02-01
**Context**: Analysis of two client meetings (Jan 20, Jan 27), internal dev guidance doc, 27 eval iterations (best 94%), and NSA API schema review.

---

## Stakeholders

| Person | Role | Key Perspective |
|--------|------|-----------------|
| Stefano Venditti | NSA, investor/advisor, domain expert | Prioritizes coverage check accuracy, wants "explain WHY" for non-covered parts |
| Dave | NSA, MGA operator, CFO background | Strong internal IT (developer Ian), API-ready system, wants clear integration boundary |
| Reuben John | TrueAim CEO | Manages relationship, positions product, fundraising |
| Fred Brunner | TrueAim CTO | Builds the system, needs to balance delivery vs. accuracy vs. scope |

---

## What NSA Actually Wants (from meetings)

### Stefano's priorities (Jan 27)
1. **Security on rejections** — high-confidence identification of denials
2. Process 60-70% of remaining claims with high accuracy
3. Don't try to solve 100% in step one
4. **Coverage check >> payout calculation** (said explicitly; payout may need a separate engine)
5. **Explain WHY** parts aren't covered, referencing policy terms/contract

### Dave's priorities (Jan 20)
1. Their IT (Ian) handles "bread and butter" — login, upload, formal checks, storage
2. TrueAim handles the hard part — reading documents, material coverage check
3. API integration — policy data delivered as structured JSON, not documents
4. ~30% of claims are denials, 25% are clear-cut — kick those out
5. Everything else gets a recommendation + confidence score for human review

### Agreed scope boundary
- TrueAim does NOT touch NSA's core system — API integration only
- TrueAim does NOT handle customer-facing communication (Fred flagged this risk internally)
- NSA's internal IT handles: login, upload, document storage, formal cover checks (dates, policy validity)
- TrueAim handles: document reading, material coverage check, assessment recommendation

---

## Current System Status

### Eval accuracy
- **Best**: 94% decision accuracy (eval #21, Jan 31)
- **Latest**: 88% (eval #23, with two known regressions)
- **27 iterations** on the same 50 claims — overfitting risk is real
- FAR (false approve rate) volatile: swings 0% to 37.5% across runs
- `amount_mismatch` is persistent #1 error (14-16 per run) but is payout, not decision

### If you exclude amount_mismatch (per Stefano's guidance)
Eval #21 has 3 actual decision errors out of 50 = **94% decision accuracy**. The 15 amount mismatches are correct decisions with wrong payout amounts.

### Open risks
- No blind test validation — need 20-30 fresh claims
- 40+ unanswered business rules (see `docs/NSA-BUSINESS-RULES-REVIEW.md`)
- Non-determinism in LLM components causes run-to-run variance

---

## NSA API Analysis

**Swagger**: `https://api.nsagarantie.com/swagger/index.html`
**Spec**: `https://api.nsagarantie.com/swagger/v1/swagger.json`

### What the API provides

| Data | Endpoint | Structured? |
|------|----------|-------------|
| Guarantee metadata (type, dates, duration, options) | `GET /v1/guarantees/{number}` | Yes |
| Vehicle (make, model, VIN, km, registration, fuel, transmission) | Nested in guarantee | Yes |
| Beneficiary (person/company, name, address) | Nested in guarantee | Yes |
| Guarantee types (products, pricing, eligibility rules) | `GET /v1/guarantee-types` | Yes |
| Policy PDF | `GET /v1/guarantees/{number}/policy` | Binary download |

### What the API does NOT provide
- **No covered parts/components list** — the 80-200 covered parts Dave mentioned are NOT in the API
- **No claims endpoint** — no `POST /claims`, no claims processing
- **No coverage details per guarantee type** — only `coverageOption4x4/Turbo/Hybrid` as opaque strings

### Implication
The covered parts list is either (a) implied by guarantee type name and lives in NSA's heads, (b) in the policy PDF, or (c) planned for a future API version. **PDF extraction for covered parts is still needed.**

The API replaces PDF extraction for: VIN, mileage, registration date, beneficiary, policy dates, guarantee type. Cost estimates, service history, and dashboard photos remain document-based.

---

## What to Tell NSA (progress update framing)

### Lead with
- System gets approve/reject decision right ~92-94% on 50 claims
- In best runs, 24/24 denied claims correctly denied (0% false approval rate) — addresses Stefano's "security on rejections"
- Coverage checking is the strongest module
- Payout deprioritized per Stefano's guidance

### Be honest about
- Need blind test set (20-30 unseen claims) to validate accuracy generalizes
- Payout amounts less reliable than decisions (14-16 amount mismatches)
- 40+ business rule questions need answers to improve further

### Ask for
1. **Adjuster session** — walk through 5-7 error claims together (highest-value next step)
2. **Blind test set** — 20-30 fresh claims with decisions
3. **Business rules review answers** — especially P0 items (shop auth, service compliance, coverage lists)
4. **Operating model clarification** — auto-decide + escalate, or recommend-only?

---

## Questions for NSA (from API analysis)

| # | Question | Why |
|---|----------|-----|
| 1 | Is the covered parts list per guarantee type available via API, or only in the policy PDF? | Determines if coverage check can be fully deterministic |
| 2 | Will there be a claims endpoint, or does TrueAim become the claims processing layer? | Defines integration architecture |
| 3 | How does NSA's system trigger TrueAim? Webhook, API call, file drop? | Determines integration entry point |
| 4 | What do `coverageOption4x4/Turbo/Hybrid` string fields actually contain? | Might be coverage descriptions or just labels |
| 5 | How many guarantee types exist? Is `GET /v1/guarantee-types` the definitive product list? | Each type needs a coverage mapping |

---

## Developer Priorities

### Now: Stabilize eval accuracy
- Fix eval #23 regressions (65129 empty `excluded_components`, 65060 age threshold)
- Re-run eval, confirm back at 94%
- Do NOT start new features

### Now: Small API integration task
- Build client for `GET /v1/guarantees/{number}` — map response to existing claim facts schema
- Call `GET /v1/guarantee-types` — map products to known coverage tiers (cache as reference data)
- This replaces PDF extraction for vehicle/beneficiary/policy fields (~1-2 days work)

### After adjuster session: Build with real requirements
- Payout calculation fix (using exact formula from adjuster walkthrough)
- "Explain WHY not covered" feature (using adjuster's actual workflow and format needs)
- Business rules answers turned into config updates, then re-eval

### Before any external access/deployment
- SEC-01 through SEC-05 (password hashing, default credentials, session tokens, rate limiting, file validation)

### Do not work on
- UI backlog (FEAT-17 through FEAT-38) — not relevant to NSA engagement
- AI Agent screen (FEAT-01 through FEAT-07) — future
- Claims API endpoint design — NSA doesn't have one yet
- Customer-facing communication automation — out of scope (Fred's call)

---

## Key Strategic Points

1. **The moat is the coverage check.** NSA has a fast developer (Ian) and good internal IT. They explicitly said they don't need TrueAim for commodity work. The material coverage check — reading documents + domain knowledge + AI — is what they can't build internally.

2. **Reframe amount_mismatch.** 14-16 "errors" are correct decisions with wrong amounts. Stefano deprioritized payout. Report decision accuracy (94%) as the headline metric.

3. **The adjuster session IS the product development.** The remaining errors (payout formula, ambiguous parts, business rules) can only be resolved by sitting with someone who processes claims daily. Code iteration has diminishing returns without this.

4. **Production architecture gets easier, not harder.** Structured API data for vehicle/policy fields means fewer extraction errors. Coverage check becomes more reliable. Current 94% may be conservative for production accuracy on those fields.

5. **Don't oversell, don't undersell.** 94% on 50 iterated claims is not 94% in production — but going from zero to here in 10 days with a working pipeline is a concrete result. Frame it honestly; Stefano and Dave are sophisticated enough to understand the nuance.

6. **Scope discipline.** Dave mentioned email management and customer communication in meeting 1. Fred correctly flagged this as out of scope in the internal debrief. Stay on the coverage check. Resist scope creep.

---

## Commitments Made to NSA

From meeting action items (Jan 20 + Jan 27):

| Commitment | Status |
|------------|--------|
| Fred to map parts to coverages with Stefano | In progress (via assumptions.json, eval iterations) |
| Stefano to send 40-50 claims with outcomes | Done (50 claims received, in eval set) |
| Fred to prioritize coverage checks over payout | Done (per Stefano's guidance) |
| Stefano to explain use case for "why not covered" via email | Pending — follow up |
| Stefano to provide API/policy data structure info | Partially done (API is public, but covered parts question remains) |
| Fred to deploy securely on Swiss infrastructure before giving Stefano access | Not started (security hardening needed first) |

---

## References

| Document | Path |
|----------|------|
| Business rules review (40+ questions) | `docs/NSA-BUSINESS-RULES-REVIEW.md` |
| Client guidance & adjuster session plan | `docs/client-guidance-and-adjuster-session.md` |
| Eval process & history | `docs/EVAL-process.md` |
| Eval metrics (machine-readable) | `workspaces/nsa/eval/metrics_history.json` |
| Ground truth | `data/08-NSA-Supporting-docs/claims_ground_truth.json` |
| Meeting notes (Jan 20) | `data/08-NSA-Supporting-docs/NSA Garantie & TrueAim.ai - 2026_01_20 16_56 CAT - Notes by Gemini.pdf` |
| Meeting notes (Jan 27) | `data/08-NSA-Supporting-docs/NSA _ True Aim - 2026_01_27 14_27 CAT - Notes by Gemini.pdf` |
| NSA API spec | `https://api.nsagarantie.com/swagger/v1/swagger.json` |
| Customer config repo | `C:\Users\fbrun\Documents\GitHub\context-builder-nsa` |
