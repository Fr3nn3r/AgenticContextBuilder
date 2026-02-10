# Meeting Analysis: NSA & True Aim — 2026-02-02

---

## Key Answers Obtained from Stefano

Comparing against what was planned to ask (from `docs/client-guidance-and-adjuster-session.md`), here's what was obtained:

### 1. Production distribution — ANSWERED
- Production is 65-70% approved / 30-35% rejected. The eval set was 50/50, so this is a significant calibration point. FRR/FAR metrics need recalculating against this base rate.

### 2. Error tolerance — which direction hurts more? — PARTIALLY ANSWERED
- Stefano said **false rejection is the "best error"** (i.e., the least harmful). He'd rather the system wrongly rejects a valid claim (the customer can appeal) than wrongly approves a fraudulent/non-covered one. This is a clear design parameter.

### 3. Expected workflow — ANSWERED
- Three-bucket triage: **Rejected / Needs Review / 100% Approved**, plus an estimated cost and flagging of non-covered parts. This is concrete product spec.

### 4. Service compliance nuance — ANSWERED
- Service compliance is only checked **if relevant to the claimed part** and if the service is actually overdue. Overdue determination varies by manufacturer — Stefano looks it up on Google. The 5-year blanket rule is a reasonable safety net but too coarse. He confirmed that overdue services sometimes get resolved concurrently (client does the service while claim is processed).

### 5. Shop authorization — ANSWERED
- All shops accepted by default. Only blocked if NSA is unhappy with their work. This is essentially a non-issue for automation — can drop or downweight this check.

### 6. Policy payment status — NEW INSIGHT
- Claim 6498 was rejected because the dealer didn't pay the policy premium. This info lives in NSA's internal system, **not in the current API**. Identified the need for a policy-payment-status API endpoint.

### 7. Assistance coverage limits — ANSWERED
- Towing: 300 CHF. Rental vehicle: 100 CHF/day, max 1,000 CHF. No failures observed in this area.

### 8. Part lookup process — PARTIALLY ANSWERED
- Stefano uses "AutoText" or Google for unknown parts. He confirmed the volume of part names is large and a scalable solution is needed. He pointed to the **AutoText API** (likely "Audatex" or similar) — insurance companies typically have full licenses, and NSA could potentially piggyback on an insurer's license.

### 9. Coverage ambiguity (commercial gestures) — CONFIRMED
- Approval depends on multiple factors: part's relation to a listed part, type of guarantee, dealer performance. Some approvals are effectively judgment calls. This confirms the intuition that some ground-truth approvals are "noise" that can't (and shouldn't) be replicated.

---

## Outstanding Questions — Still Unanswered

| # | Question from prep | Status |
|---|-------------------------|--------|
| **Amount calculation walkthrough** | **NOT DONE.** Prep doc (section C) called for walking through the exact payout calculation step-by-step with an adjuster for 3 claims. One calculation was shown (claim 64358) but Stefano didn't calculate it himself step-by-step. The labor-inclusion ambiguity remains unsolved. |
| **"Which claims take you the longest?"** | **NOT ASKED.** Section D of prep — understanding where adjusters struggle — didn't come up. |
| **Fresh blind test set confirmation** | **PARTIALLY.** The 30 new claims were acknowledged but not formally framed as a hold-out test. Unclear if Stefano understands these shouldn't overlap with tuning data going forward. |
| **False approval vs false rejection cost in monetary terms** | **VAGUE.** Stefano said false rejection is the "best error" but the actual cost differential wasn't pinned down. Prep asked "what's the cost?" — got a directional preference but not a quantified answer. |
| **Keyword list review by Stefano** | **REQUESTED but not completed.** Asked him to review it. No commitment with a timeline. |
| **DPA/NDA** | **Identified as needed** by Dave, but not signed. Stefano needs to send their existing DPA. This is blocking larger data transfers. |

---

## Feedback

### What went well

- **Right questions asked early.** Production distribution (30-35% rejected) and error tolerance (false rejection = "best error") were the two highest-value answers from the prep doc, and both were obtained within the first 6 minutes.
- **Showed the product live.** Walking through rejected claims, the coverage reasoning screen, and the feedback mechanism gave Stefano something concrete to react to. His feedback on claim 6560 (missing rejection rationale) and the valve gasket coverage was specific and actionable — that's the kind of signal you only get from showing real output.
- **Honest about limitations.** Admitting the amount calculation isn't perfect, that part lookups are using a workaround, and that the system is overfit to 50 claims builds trust. Stefano didn't flinch.
- **Dave's contribution was well-timed.** The client specification questionnaire and DPA suggestions added structure to what could have been a loose "we'll figure it out" ending. These are the kind of process guardrails that protect you later.

### Areas for improvement

- **Didn't get the adjuster walkthrough.** This was the single most valuable item in the prep doc ("The adjuster session is more valuable than another 10 iterations on the same 50 claims"). Calculations were shown to Stefano instead of asking him to calculate. The divergence point in payout logic remains unknown. Next meeting, hand him a claim and a pen and ask him to compute the payout while you watch.
- **Too much demo, not enough interrogation.** The meeting tilted toward presenting and Stefano reacting. The prep doc had 4 specific adjuster exercises (A-D). Parts of A (reviewed some errors) and B (coverage lookup) were covered, C (payout walkthrough) and D (hard claims) were skipped. The demo was useful but the extraction session was the higher priority.
- **The "false rejection is the best error" answer deserves pushback.** Stefano may be thinking about this from a customer-relations lens (easier to reverse a rejection than claw back a payment), but in a production tool that auto-rejects, false rejections create customer complaints and adjuster workload. Follow up: "If we auto-reject 20% of claims, and 5% of those are wrong, how does that impact your team?"
- **Action items are heavily skewed to you.** Of the 11 next steps, 8 are yours, 2 are Stefano's, 1 is Dave's. The most valuable items (keyword list review, DPA, thinking about process integration) are on Stefano — but without deadlines or specifics, they'll drift. Pin dates on these.

---

## How to Make Next Steps Fast and Productive

1. **Run the 30 new claims immediately** — this is the hold-out test. Run before any further tuning. Document the raw accuracy. This is the "before" number.
2. **Send the questionnaire and app link this week** — quick wins that keep Stefano engaged. The questionnaire should formalize: error tolerance preference, expected workflow (the 3-bucket model), which checks are hard requirements vs. soft signals.
3. **Prioritize the policy API investigation** — the payment-status gap (claim 6498) and the missing covered-parts detail are both blocking issues. If the API can't provide these, you need to know now so you can design around OCR.
4. **Defer the OEM part API investment decision** — the AutoText/Audatex API is expensive and the ROI is unclear. Build the keyword database from the 80 claims (50 + 30), get Stefano to review it, and measure how far that gets you before spending money.
5. **Schedule a dedicated adjuster walkthrough session** — 30 minutes, just Stefano, 3 approved claims, step-by-step payout calculation. This is the highest-value activity not yet done. Don't bundle it with a demo or a progress update.
6. **Get the DPA moving in parallel** — this is on the critical path for receiving more data. Dave should follow up with Stefano this week.
