# Prompt Token Analysis & Attention Dilution

**Date:** 2026-01-25
**Prompt:** `workspaces/nsa/config/prompts/claims_assessment.md`
**Model:** GPT-4o (128K context)

---

## Token Counts

| Component | Tokens |
|-----------|--------|
| **Prompt template** | 4,694 |
| **Claim 65128 (smallest)** | 13,891 → Total: ~19K |
| **Claim 65196** | 17,442 → Total: ~22K |
| **Claim 65157** | 23,794 → Total: ~28K |
| **Claim 65258 (largest)** | 56,979 → Total: ~62K |

---

## Risk Assessment

**GPT-4o specs:**
- Context window: 128K tokens
- Sweet spot for reliable reasoning: **<32K tokens**
- "Lost in the middle" degradation starts: **~40K-60K**
- Hard limit concerns: **>80K**

**Current situation:**
- 3 of 4 claims are in the safe zone (<32K)
- Claim 65258 at **62K** is in the degradation risk zone
- The prompt at 4.7K is lean and well-structured

---

## When Attention Dilution Becomes Real

Research (including Anthropic's and OpenAI's own findings) shows:

1. **Information at the start and end** of context is recalled well
2. **Information in the middle** gets progressively "lost" as context grows
3. **Complex reasoning over many facts** degrades faster than simple retrieval

For claims assessment (7 sequential checks with calculations), the risks are:
- Model might "forget" a fraud indicator buried in the middle of 57K tokens of facts
- Payout calculation might miss a line item deep in the document
- Check dependencies (e.g., coverage % affects payout) could get confused

---

## Decision Framework: When to Split

| Scenario | Action |
|----------|--------|
| Total input <30K | Single prompt, no concerns |
| Total input 30K-50K | Monitor for errors, consider splitting if accuracy drops |
| Total input >50K | **Recommend splitting** |
| Facts >40K alone | Almost certainly need to split |

---

## Splitting Strategies (When Needed)

### Option 1: Two-Pass Assessment

```
Pass 1: Eligibility Checks (1, 1b, 2, 3, 4)
  - Input: Policy facts + service history + basic claim info
  - Output: PASS/FAIL/REFER for each check

Pass 2: Payout Calculation (5, 6, 7)
  - Input: Line items + coverage lookups + results from Pass 1
  - Output: Final decision + payout
```

### Option 2: Pre-filter the Facts

Before assessment, run a lightweight pass to extract only the relevant facts for each check. This dramatically reduces token count.

### Option 3: Summarize Large Documents

- Service history often bloats the facts - summarize to key entries only
- Line items: group similar items, summarize small-value ones

---

## Recommendations

1. **Don't split yet** - the prompt is well-structured and 3/4 claims are in the safe zone
2. **Add a facts size check** in the pipeline - flag claims >40K tokens for:
   - Human review, OR
   - Automatic fact summarization before assessment
3. **If adding the 6 missing adjuster checks**, the prompt grows ~1.5K tokens max - still acceptable
4. **For large claims (65258-sized)**, consider a pre-processing step to summarize or filter facts before assessment

---

## Related Documents

- [PROMPT_VS_ADJUSTER_ANALYSIS.md](./PROMPT_VS_ADJUSTER_ANALYSIS.md) - Gap analysis of prompt vs actual adjuster workflow
