# Client Guidance & Adjuster Session Plan

**Date**: 2026-01-30
**Context**: 50-claim eval set, 20+ iterations, best accuracy 86% (eval_20260130_155703)

## What to Tell the Client

We've validated against 50 of your historical claims. The system gets the approve/reject decision right ~80-85% of the time. It's strongest on clear-cut denials where the part isn't on the coverage list. Payout amounts are less reliable — even when the decision is correct, the calculated amount often doesn't match yours. We're not at a point where this runs unsupervised, but it could meaningfully speed up your adjusters as a first-pass recommendation tool.

Don't oversell. 86% on a 50-claim set we've iterated on 20 times is not the same as 86% in production. Position it as a triage tool, not an autopilot.

## What to Ask the Client

These are the things we can't figure out from the data alone.

### 1. Error tolerance — which direction hurts more?

"If the system wrongly approves a claim that should be denied, what's the cost? vs. wrongly denying one that should be approved?"

This determines whether we tune for low FAR (protect their money) or low FRR (protect customer experience). Right now we're trading these off blindly.

### 2. Production distribution

"Out of your last 500 claims, roughly what percentage get approved vs denied?"

Our eval set is 50/50. If production is 70/30, our metrics shift. We need to know the base rate.

### 3. What "correct amount" means

`amount_mismatch` is our #1 error. But we're comparing against decision letter amounts. Ask: "Does the amount on the decision letter always match the final payment? Do adjusters ever override or adjust after the letter goes out?"

The ground truth might itself be noisy.

### 4. Fresh claims for blind testing

"Can you give us 30 recent claims with decisions that we haven't seen? We want to test on claims we haven't tuned against."

This is the single most valuable thing they can provide.

### 5. Operating model

"Do you want this to auto-decide straightforward cases and escalate edge cases? Or do you want every claim reviewed by an adjuster with the system's recommendation?"

This changes what accuracy threshold matters.

## What to Do With the Adjusters

This is where we'll get the most value. Specific things to walk through:

### A. Walk through 5-7 error claims together

Pick a mix from the latest eval errors:

- 2-3 `amount_mismatch` claims — have the adjuster calculate the payout step by step while you watch. Where does our calculation diverge from theirs?
- 1-2 `false_approve` claims — the system approved but should have denied. Ask: "What made you deny this?" The denial reason is in the ground truth but it's terse.
- 1-2 `component_coverage` false rejects — the system said "not covered" but the adjuster approved. Ask: "How did you determine this part is covered?"

### B. Understand their coverage lookup process

Our biggest swing factor is component coverage (1-18 errors depending on config). Ask:

- "When you see a part name you don't recognize, what do you look up and where?"
- "Is there a master list, or is it judgment?"
- "Do you ever call the shop to clarify what a part is?"

This tells us whether our `assumptions.json` coverage tables can ever be complete, or if there's inherent ambiguity that requires human judgment.

### C. Get their deductible/payout logic on paper

Our `amount_mismatch` errors are persistent. Ask them to walk through the exact calculation for 3 approved claims:

- Gross amount → which line items are covered → coverage percentage → cap → deductible → VAT → final payout
- Record every step. Compare against what our screening payout engine computes. The divergence point will be specific and fixable.

### D. Ask about the claims they find hard

"Which claims take you the longest to decide? What makes them hard?"

This tells us where the system will struggle in production, beyond what our 50-claim set reveals.

## Statistical Context

With n=50, our confidence intervals are wide:

| Metric | Measured | 95% CI (Wilson) | Implication |
|--------|----------|-----------------|-------------|
| Accuracy | 86% (43/50) | ~74-93% | Directional, not precise |
| FRR | 16% (4/25) | ~6-35% | Too few positives to be confident |
| FAR | 12% (3/25) | ~4-30% | Same issue |

### What 50 claims CAN tell us

- **Rough accuracy range**: We're between 74-93%, not 50% or 95%
- **Systematic error patterns**: component_coverage, service_compliance, amount_mismatch are real structural issues
- **Config sensitivity**: Accuracy swings 18-86% across iterations; even same-code runs vary by 5-10%

### What 50 claims CANNOT tell us

- **Precise production metrics**: ±10% CI is too wide to quote a number
- **Rare failure modes**: Anything <5% occurrence may not appear in 50 claims
- **Overfitting**: 20+ iterations on the same set — need a holdout set to validate
- **Amount accuracy**: Only ~20 approved claims have amounts to compare — very low statistical power
- **Distribution shifts**: All claims are from one 3-month window, one product, one geography

## Key Takeaway

The adjuster session is more valuable than another 10 iterations on the same 50 claims. The error patterns are clear — what we lack is understanding of their decision process to close the gaps.
