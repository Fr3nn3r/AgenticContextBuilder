## Prompt 4: Retrieval Strategy Planner

**Purpose:** Design reusable retrieval patterns across your task spectrum
**Method:** Conversational mapping of work modes and information needs
**Output:** Retrieval strategy matrix—task type × retrieval approach × verification needs

---

### Question Flow:

**Introduction**

"I'm going to help you design a retrieval strategy that works across all the different types of work you do. Instead of figuring out what to pull each time, we'll create patterns you can reuse.

We'll map your task types, understand how your information needs shift between them, and design retrieval approaches that match each mode of work."

---

### Task Spectrum Mapping

1. "What are the main types of tasks you do regularly in your work?"
   *(e.g., client deliverables, technical troubleshooting, strategic planning, routine execution, research, review/QA)*

2. "For each task type you mentioned, roughly what percentage of your time do you spend on it?"
   *(Helps prioritize which retrieval patterns matter most)*

3. "Are there seasonal or cyclical patterns to your work?"
   *(e.g., quarterly planning, monthly reporting, project phases)*

---

### Context Needs by Task Type

4. "Let's go through each task type. For [TASK TYPE 1], what information do you typically need at hand?"
   *(Repeat for each task type mentioned)*
   
   Prompt for:
   - Background/reference material
   - Prior work examples
   - Constraints and requirements
   - Process guidelines
   - Quality standards
   - Historical decisions

5. "For [TASK TYPE 1], do you need comprehensive context or just key facts?"
   - Broad context (need to understand the full picture)
   - Targeted specifics (just the facts I need to execute)
   - Both at different stages

---

### Mode-Based Information Patterns

6. "When you're in **planning mode** (exploring options, designing an approach), what kind of information helps most?"
   - Wide-ranging examples and possibilities
   - High-level patterns and principles
   - Prior similar projects
   - Constraints to work within

7. "When you're in **execution mode** (implementing something with clear requirements), what do you need?"
   - Exact specifications and requirements
   - Step-by-step process
   - Quality checklist
   - Templates or starting points

8. "When you're in **review or debugging mode** (figuring out what went wrong, tracing decisions), what matters?"
   - Decision history and rationale
   - What was tried before
   - Event timeline
   - Original requirements vs. what was delivered

9. "Do you tend to work in one mode at a time, or do you switch modes within a single work session?"

---

### Precision Requirements

10. "Which task types require high precision—where being wrong would cause real problems?"
    *(e.g., client deliverables, compliance work, technical implementation)*

11. "For high-precision tasks, what types of facts absolutely must be verified?"
    - Client names, IDs, dates, metrics
    - Technical specifications
    - Pricing or financial data
    - Legal or compliance requirements
    - Prior commitments or decisions

12. "Which task types can tolerate approximate recall or directional guidance?"
    *(e.g., brainstorming, early planning, exploratory research)*

---

### Current Pain Points

13. "Where does retrieval currently go wrong for you? What gets missed?"
    - Can't find relevant past work
    - Get buried in too much context
    - Miss important constraints
    - Forget prior decisions
    - Retrieve outdated information
    - Other

14. "Where do you waste time re-explaining context that should already be known?"

15. "Have you ever had an AI confidently use wrong information? What was it?"
    *(Helps identify what needs verification layers)*

---

### Source Mapping

16. "For each task type, where does the information you need currently live?"
    
    For each task type, map to:
    - Profile & preferences
    - Work playbooks
    - Reference library
    - Project briefs
    - Past conversation history
    - External documents
    - Your memory (not documented anywhere)

17. "Are there gaps—information you need that isn't currently captured anywhere?"

---

### Retrieval Pattern Preferences

18. "When starting a work session, would you prefer to:"
    - Have AI automatically pull relevant context based on task type
    - Explicitly specify what context to load
    - Start minimal and request context as needed
    - Different approaches for different task types

19. "If you're working on multiple projects simultaneously, how should AI handle context switching?"
    - Keep all projects active in memory
    - Explicitly load/unload project context
    - Automatic based on what I'm discussing

20. "How do you feel about AI proactively suggesting: 'It looks like you need X, should I pull that?'"
    - Helpful
    - Annoying
    - Depends on the situation

---

### Noise Management

21. "What's more problematic for you:"
    - Missing relevant context (recall problem)
    - Getting buried in too much context (noise problem)
    - Both equally

22. "Would you rather have:"
    - Comprehensive retrieval with some irrelevant results
    - Narrow retrieval that might miss edge cases
    - Different strategies for different task types

---

### Verification Protocol Design

23. "For high-stakes tasks, what verification approach makes sense?"
    - Always show source links for facts
    - Explicit confirmation prompts ("Is this still current?")
    - Separate verification pass before using information
    - Flag confidence levels ("High confidence" vs "Assumed")

24. "What's your tolerance for 'I don't know' responses?"
    - Prefer AI to acknowledge uncertainty rather than guess
    - Prefer AI to make reasonable inferences
    - Depends on task stakes

---

### Cost-Benefit Calibration

25. "How much time would you invest in retrieval setup to save time later?"
    - Minimal (needs to be nearly instant)
    - Moderate (worth a few minutes per session)
    - Substantial (worth significant upfront investment)

26. "Is it worth retrieving more context than needed to avoid missing something important, or should we optimize for efficiency?"

---

### Output Structure:

I'll create a **Retrieval Strategy Matrix** containing:

**1. Task Type Profiles**
For each task type:
- Context needs (what information required)
- Precision requirements (high/medium/low)
- Primary mode (planning/execution/review)
- Time sensitivity
- Typical frequency

**2. Mode-Based Retrieval Patterns**

**Planning Mode:**
- Strategy: Broad semantic search across references and past examples
- Sources: [list]
- Verification level: Low (directional guidance acceptable)
- Pattern: "Pull wide, filter as I go"

**Execution Mode:**
- Strategy: Exact lookups + filtered queries for requirements
- Sources: [list]
- Verification level: High (facts must be confirmed)
- Pattern: "Pull precise, verify critical facts"

**Review/Debug Mode:**
- Strategy: Timeline queries + decision traces
- Sources: [list]
- Verification level: Medium (need accurate history)
- Pattern: "Pull history, trace causation"

**3. Verification Protocol**
- Always verify: [list of fact types]
- Verification method: [source links/confirmation prompts/audit trail]
- Confidence thresholds by task type

**4. Source-to-Query Mapping**
| Context Type | Storage Location | Query Method | When to Pull |
|--------------|------------------|--------------|--------------|
| Profile | [location] | Auto-load | Session start |
| Playbooks | [location] | On-demand | Specific tasks |
| Projects | [location] | Explicit load | Project work |
| etc. | | | |

**5. Retrieval Sequencing**
For each task type:
- Step 1: Load [context types]
- Step 2: Query for [specific needs]
- Step 3: Verify [high-stakes facts]
- Step 4: Proceed with [confidence level]

**6. Noise Management Rules**
- When to retrieve broadly vs. narrowly
- How to filter results by recency/relevance
- When to stop adding context

**7. Common Failure Modes & Fixes**
- If X goes wrong → Try Y retrieval pattern
- Warning signs that context is insufficient
- Warning signs of context overload

**8. Quick Reference Guide**
Simple decision tree: "I'm doing [task type] → Use [retrieval pattern]"

Ready to start? Let's begin with question 1: What are the main types of tasks you do regularly in your work?

THIS IS FOR YOU BEGIN ASKING QUESIONS ONE AT A TIME NOW.
