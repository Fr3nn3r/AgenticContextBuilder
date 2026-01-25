# Questions for Adjuster

**Date:** 2026-01-25
**Context:** Gaps identified when comparing `claims_assessment.md` prompt against adjuster notes from claims 65258, 65196, 65157, 65128.

---

## Gap 4: Documentation Requirements for Costly Repairs

In your notes (claim 65157), you wrote:
> "In cases where entire units need to be replaced, which is very costly, we want to know exactly how the defect manifests and how, when, and where it occurred. A cost estimate alone is not sufficient here."

**Questions:**
1. How do you identify an "entire unit" replacement? Is it:
   - Specific component names (e.g., "transmission", "engine block", "cylinder head")?
   - A cost threshold (e.g., >CHF 3,000)?
   - Both?
2. What specific documentation do you require in these cases?
   - Error memory extract?
   - Photos of the defect?
   - Written explanation from repair shop?
3. Should the AI flag these for REFER_TO_HUMAN, or can it proceed if documentation is present in the claim facts?

---

## Gap 5: Error Memory / Fault Code Verification

In your notes (claim 65157), you wrote:
> "We check the error memory entry together with what was offered to see whether the repair is justified. Usually based on experience or the internet."

**Questions:**
1. What exactly is an "error memory entry"? Is this:
   - OBD fault codes (e.g., P0301)?
   - Manufacturer-specific diagnostic codes?
   - Timestamps from the vehicle's ECU?
2. How do you verify the repair is "justified"? What makes a repair NOT justified given an error code?
3. Can you give an example of a mismatch (error code vs repair offered) that would cause rejection?

---

## Gap 6: Part Number Research for Unknown Parts

In your notes (claim 65196), you wrote:
> "First, I need to find out exactly what kind of valve it is... by searching the internet."

And (claim 65128):
> "If a component or the main component has a strange or unknown name, we try to find out what kind of component it is and where it belongs based on the part number."

**Questions:**
1. How often do you encounter unknown parts that require internet research? (e.g., 1 in 10 claims? 1 in 50?)
2. What sources do you use for research? (OEM parts catalogs, Google, specific databases?)
3. Would it be acceptable for the AI to flag unknown parts for human review instead of researching?

---

## Part/Coverage Mapping Assumptions

We currently use a lookup table (`assumptions.json`) to map part numbers and keywords to coverage decisions.

**Questions:**
1. Can you review the current mapping and confirm it matches your understanding?
2. Are there common parts we're missing from the lookup?
3. For parts not in the lookup, what's the default assumption:
   - Assume NOT covered (conservative)?
   - Assume covered (generous)?
   - Always refer to human?

---

## Next Steps

Please review these questions and provide your answers. We will update the AI prompt based on your responses.
