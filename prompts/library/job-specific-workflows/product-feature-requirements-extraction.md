# Product: Feature Requirements Extraction from Stakeholder Conversations

```
You are a senior product manager converting messy stakeholder input into structured, testable requirements.

### TASK
Extract and structure product requirements from the stakeholder notes below.

### STAKEHOLDER INPUT
"""
[PM PASTES: Meeting notes, Slack messages, email threads, customer feedback,
sales calls, support tickets - raw unstructured input]
"""

### CONTEXT
Product: [Name and description]
Current User Base: [Size and segment]
Strategic Priority: [High/Medium/Low]
Timeline Pressure: [Launch deadline if any]
Technical Constraints: [Known limitations]

### REQUIRED OUTPUT FORMAT

**PROBLEM STATEMENT CLARIFICATION**

User Pain Point: [Single sentence describing the core problem]
- Who Experiences This: [Specific user persona/segment]
- Frequency: [How often this happens - daily/weekly/monthly]
- Current Workaround: [What users do today]
- Cost of Problem: [Time wasted/Revenue lost/Churn risk - quantified]

Business Impact:
- Revenue Opportunity: [$ amount or % increase]
- Strategic Alignment: [Which company goal this supports]
- Competitive Pressure: [Do competitors have this / Are we losing deals]

### REQUIREMENTS BREAKDOWN

**USER STORIES (Structured Format)**

Epic: [High-level feature name]

Story 1: [User story title]
- As a: [Specific user type]
- I want to: [Capability]
- So that: [Business outcome]
- Acceptance Criteria:
  1. Given [context], when [action], then [result]
  2. Given [context], when [action], then [result]
  3. [List all testable conditions]
- Priority: [Must Have / Should Have / Nice to Have]
- Effort Estimate: [T-shirt size: S/M/L/XL]

[Repeat for 5-8 stories total]

**FUNCTIONAL REQUIREMENTS**

For each major capability:

Requirement [N]: [What the system must do]
- Input: [What data/actions come in]
- Processing: [What happens in the system]
- Output: [What the user sees/gets]
- Edge Cases: [What happens when X goes wrong]
- Dependencies: [What other features this needs]

### NON-FUNCTIONAL REQUIREMENTS

**Performance:**
- Response Time: [Maximum acceptable latency]
- Throughput: [Transactions/requests per second needed]
- Data Volume: [How much data this handles]

**Security:**
- Data Sensitivity: [What type of data is involved]
- Access Control: [Who can use this feature]
- Compliance: [GDPR/HIPAA/SOC2 considerations]

**Scalability:**
- Initial Load: [Expected usage at launch]
- Growth Projection: [Expected usage in 12 months]
- Breaking Point: [At what scale does this design fail]

### MISSING INFORMATION & QUESTIONS

**Critical Unknowns (Must answer before starting):**
1. [Question about user behavior]
   - Why It Matters: [What decision depends on this]
   - How to Find Out: [Research method needed]

2. [Question about technical feasibility]
   - Why It Matters: [What decision depends on this]
   - Who to Ask: [Engineering/Architecture/Security]

[List 3-5 critical questions]

**Assumptions to Validate:**
- Assumption: [What we're assuming is true]
- Risk if Wrong: [What breaks if assumption is false]
- Validation Method: [How to test this assumption]

[List 3-4 key assumptions]

### OUT OF SCOPE (V1)

Explicitly list what is NOT included:
1. [Feature/capability]
   - Why Deferred: [Rationale for exclusion]
   - Possible Future Version: [V2/V3/Never]

[List 4-6 out of scope items]

### SUCCESS METRICS

**Primary Metric:** [The one metric that determines success]
- Baseline: [Current state]
- Target: [Goal state]
- Measurement: [How we track this]
- Timeline: [When we measure]

**Secondary Metrics:**
- [Metric 2]: Baseline [X] → Target [Y]
- [Metric 3]: Baseline [X] → Target [Y]
- [Metric 4]: Baseline [X] → Target [Y]

**Leading Indicators (Early signals):**
- Week 1: [What to watch]
- Week 4: [What to watch]
- Week 8: [What to watch]

### RISK ASSESSMENT

**Technical Risks:**
- Risk: [What could go wrong technically]
- Probability: [High/Medium/Low]
- Mitigation: [How to reduce risk]

**Market Risks:**
- Risk: [User adoption concern]
- Probability: [High/Medium/Low]
- Mitigation: [How to reduce risk]

**Execution Risks:**
- Risk: [Timeline/resource concern]
- Probability: [High/Medium/Low]
- Mitigation: [How to reduce risk]

### DEPENDENCY MAP

**Upstream Dependencies (What we need first):**
- Dependency: [Feature/system/decision]
- Owner: [Team/person]
- Status: [Complete/In Progress/Not Started]
- Blocker Impact: [What we can't do without this]

**Downstream Impact (What depends on this):**
- Affected System: [What else needs to change]
- Impact Type: [Breaking/Integration/Documentation]
- Coordination Needed: [What other teams need to know]

### STAKEHOLDER ALIGNMENT

**Decision Makers:**
- Final Approval: [Who signs off]
- Technical Approval: [Engineering lead]
- Design Approval: [Design lead]
- Go-to-Market Approval: [Sales/Marketing lead if needed]

**Communication Plan:**
- Weekly Updates: [To whom]
- Launch Announcement: [To whom and when]
- Training Needed: [Which teams need education]

### NEXT STEPS & OWNERSHIP

Immediate Actions (This Week):
1. [Action] - Owner: [Name] - Due: [Date]
2. [Action] - Owner: [Name] - Due: [Date]
3. [Action] - Owner: [Name] - Due: [Date]

Design Phase (Weeks 2-3):
- Wireframes: [Owner] - Due: [Date]
- Technical Spec: [Owner] - Due: [Date]
- User Research: [Owner] - Due: [Date]

### PRD READINESS CHECKLIST

Before moving to engineering:
- [ ] All critical unknowns answered
- [ ] Success metrics approved by leadership
- [ ] Technical feasibility confirmed
- [ ] Design mocks completed
- [ ] Edge cases documented
- [ ] Out-of-scope items agreed upon

```
