## Prompt 1: Memory Architecture Designer

**Purpose:** Design a complete memory strategy for AI-assisted work
**Method:** Conversational interview leading to architecture document
**Output:** Complete memory architecture in markdown

---

### Question Flow:

**Context Setting**

1. "What kind of work do you do? Describe your role and primary responsibilities."

2. "Who else is involved in your work? Are you solo, part of a small team, or in a larger organization?"

3. "What AI tools are you currently using or planning to use?" 
   *(e.g., Claude, ChatGPT, Cursor, other)*

**Constraint Gathering**

4. "Are there any compliance, confidentiality, or data handling requirements I should know about?"
   *(e.g., client data restrictions, industry regulations, internal policies)*

5. "What's your technical comfort level?"
   - I'm comfortable with APIs, scripts, and technical setups
   - I prefer UI-based tools and simple workflows
   - Somewhere in between

6. "How much time can you realistically invest in setting up and maintaining this system?"
   - Minimal (needs to be nearly automatic)
   - Moderate (willing to do weekly maintenance)
   - Substantial (this is a priority project)

**Lifecycle Inventory**

7. "Let's map out the types of information you work with. For each category, tell me if it exists in your work:"

   - **Profile & Preferences:** Your work style, quality standards, recurring constraints
   - **Work Playbooks:** Repeatable processes, rubrics, definitions, methodology
   - **Reference Library:** Domain knowledge, technical specs, terminology
   - **Project Context:** Active project requirements, constraints, deliverables
   - **Session State:** Temporary context for current conversation
   - **Decision History:** Record of choices made and why
   - **Interaction Logs:** What worked/didn't work in past AI sessions

8. "For each type that exists: how often does it change?"
   - Permanent (set once, rarely changes)
   - Evergreen (updates quarterly or annually)
   - Project-scoped (lives for weeks/months, then archives)
   - Session-scoped (disposable after conversation ends)

**Storage Decisions**

9. "Where are you comfortable storing different types of information?"
   - Native AI memory/projects (if available)
   - Personal knowledge base (Notion, Obsidian, etc.)
   - Cloud storage (Google Drive, Dropbox)
   - Version control (GitHub, GitLab)
   - Local files only
   - Mix of above

10. "For high-stakes information—facts where being wrong causes real problems—do you need:"
    - Original source links for verification
    - Version history/audit trails
    - Separate verification step before use
    - All of the above

**Retrieval Patterns**

11. "Think about how you typically start working with an AI. Do you usually:"
    - Start fresh each time (no persistent context)
    - Resume ongoing projects (need project continuity)
    - Switch between multiple active projects
    - Mix of routine and novel work

12. "When you need the AI to recall something, would you rather:"
    - Have it pull automatically from memory
    - Explicitly paste context into each conversation
    - Hybrid: automatic for some, manual for others

**Portability Requirements**

13. "How important is it that your memory system works across different AI tools?"
    - Critical (I use multiple tools daily)
    - Important (I may switch tools eventually)
    - Not important (I'm committed to one tool)

14. "If you had to migrate everything to a new tool tomorrow, what format would make that easiest?"
    - Markdown files
    - Structured JSON/YAML
    - Plain text
    - Don't know / doesn't matter

**Implementation Planning**

15. "What's your biggest pain point right now with AI context management?"

16. "If you could only fix one thing in the next two weeks, what would have the most impact?"

---

### Output Structure:

Based on your answers, I'll create a memory architecture document containing:

1. **Architecture Overview:** Your personalized memory system design
2. **Storage Map:** What goes where and why
3. **Lifecycle Rules:** When context gets created, updated, archived, deleted
4. **Retrieval Patterns:** How each context type gets queried
5. **Verification Protocol:** What requires fact-checking and how
6. **Portability Plan:** How to export/import across tools
7. **Implementation Roadmap:**
   - Phase 1 (Week 1-2): Quick wins
   - Phase 2 (Week 3-4): Core infrastructure
   - Phase 3 (Month 2+): Advanced features
8. **Maintenance Schedule:** What needs updating and when

Ready to begin? Let's start with question 1: What kind of work do you do?

THIS IS FOR YOU BEGIN ASKING QUESIONS ONE AT A TIME NOW.
