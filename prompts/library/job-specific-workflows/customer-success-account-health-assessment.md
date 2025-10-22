# Customer Success: Account Health Assessment & Risk Identification

```
You are a customer success strategist conducting account health reviews to prevent churn and identify expansion opportunities.

### TASK
Analyze the customer account data below and provide a comprehensive health assessment with action plans.

### ACCOUNT DATA
"""
[CSM PASTES: Usage metrics, support tickets, NPS/CSAT scores, product adoption data,
contract details, stakeholder engagement, communication history, business outcomes]
"""

### ACCOUNT CONTEXT
Account: [Company Name]
Tier: [Enterprise/Mid-Market/SMB]
ARR: [$Amount]
Contract Start: [Date]
Renewal Date: [Date] - [Days until renewal]
Seats/Licenses: [Number]
Primary Use Case: [What they use product for]

### REQUIRED OUTPUT FORMAT

**EXECUTIVE HEALTH SUMMARY**

Overall Health Score: [0-100]
- Calculation: [Show formula used]
- Trend: [↑ Improving / → Stable / ↓ Declining]
- 30-Day Change: [+/- points]

Health Status: [🟢 Healthy / 🟡 At Risk / 🔴 Critical]

One-Sentence Assessment: [Concise summary of account state]

Immediate Action Required: [Yes/No - If yes, what specifically]

### HEALTH DIMENSION ANALYSIS

**1. PRODUCT ADOPTION**

Adoption Score: [0-100]

Usage Metrics:
- Active Users: [X] of [Y] licenses = [%]
- Login Frequency: [X times per week/month]
- Feature Utilization: [X] of [Y] key features used = [%]
- Power User Count: [Number of users with >X actions/week]

Adoption Depth by Feature:

| Feature | Adoption % | Trend | Industry Benchmark | Status |
|---------|-----------|-------|-------------------|--------|
| [Feature] | [%] | [↑/→/↓] | [%] | [Above/At/Below] |

Red Flags:
- [ ] Core feature unused ([Feature] - 0 usage in [timeframe])
- [ ] Declining usage ([% drop] over [timeframe])
- [ ] License waste ([%] unused seats)
- [ ] Single user dependency ([Name] is only active power user)

Green Lights:
- [ ] Expanding usage ([% increase] over [timeframe])
- [ ] Cross-team adoption ([# departments] using product)
- [ ] Advanced feature usage ([Feature] actively used)

Recommended Actions:
1. [Specific action to improve adoption]
   - Owner: [CSM/Customer/Joint]
   - Timeline: [Days/weeks]
   - Success Metric: [How to measure improvement]

**2. BUSINESS VALUE REALIZATION**

Value Score: [0-100]

Stated Goals from Kickoff:
1. [Original goal] - Status: [Achieved/In Progress/Not Started/At Risk]
   - Target: [Specific metric]
   - Current: [Actual metric]
   - Gap: [Difference]

2. [Another goal]
[Same format]

Quantified Outcomes:
- ROI Delivered: [Calculate based on time saved, revenue increased, costs reduced]
- Payback Period: [Months] (Target was [X] months)
- Business Impact: [Specific measurable outcome]

Customer Can Articulate Value: [Yes/No/Unclear]
- Evidence: [Quote from recent conversation / Lack of clear answer]

Expansion Indicators:
- [ ] Achieving original goals (creates case for more)
- [ ] Expressed new use cases (signal of additional needs)
- [ ] Other teams inquiring about product (organic spread)
- [ ] Customer references value in exec meetings (champion strength)

Value Realization Risks:
- [ ] Goals not defined/measured (no proof of value)
- [ ] Results below expectations (not seeing ROI)
- [ ] Value not communicated to leadership (no exec visibility)

Recommended Actions:
1. [Specific action to demonstrate/increase value]
   - Owner: [Who]
   - Timeline: [When]
   - Success Metric: [How measured]

**3. ENGAGEMENT & RELATIONSHIP**

Engagement Score: [0-100]

Stakeholder Map:

| Name | Role | Influence | Champion? | Engagement Level | Last Contact | Sentiment |
|------|------|-----------|-----------|-----------------|--------------|-----------|
| [Name] | [Title] | [High/Med/Low] | [Yes/No] | [Active/Moderate/Low] | [Date] | [😊/😐/😟] |

Relationship Health:
- Executive Sponsor: [Identified/Engaged/Strong] or [Missing/Weak]
- Day-to-Day Champion: [Name] - Strength: [Strong/Moderate/Weak]
- Power User Community: [# of advocates] users who love the product
- Detractors: [# or names] users with negative sentiment

Communication Patterns:
- Initiated by Customer: [X] times in [timeframe]
- Initiated by Us: [X] times in [timeframe]
- Ratio: [Customer:Us] - Ideal is [X:Y]
- Response Time: [Avg hours for customer to reply]
- Meeting Attendance: [% of scheduled calls they attend]

Red Flags:
- [ ] Champion left company or changed roles
- [ ] Executive sponsor unresponsive
- [ ] Customer only contacts us with problems (reactive only)
- [ ] Meeting cancellations ([#] in past [timeframe])
- [ ] Slow/no responses to outreach

Green Lights:
- [ ] Multiple champions across departments
- [ ] Proactive feature requests (engaged in roadmap)
- [ ] Willing to be a reference
- [ ] Invite us to strategy meetings

Recommended Actions:
1. [Specific action to strengthen relationships]
   - Owner: [CSM or escalate to whom]
   - Timeline: [When]
   - Success Metric: [Evidence of improvement]

**4. SUPPORT & TECHNICAL HEALTH**

Support Score: [0-100]

Ticket Metrics:
- Total Tickets (past 90 days): [#]
- Avg per Month: [#]
- Trend: [Increasing/Stable/Decreasing]
- Severity Distribution: [# Critical, # High, # Medium, # Low]

Time to Resolution:
- Avg: [Hours/days]
- Compared to SLA: [Within/Exceeding]
- Customer Satisfaction: [% positive]

Issue Patterns:
- Recurring Issue: [Issue type] - [# occurrences]
  - Impact: [What this affects]
  - Root Cause: [Technical/Training/Product gap]
  - Resolution: [What needs to happen]

Red Flags:
- [ ] Escalated tickets ([#] in past [timeframe])
- [ ] Same issue repeating (not resolved at root cause)
- [ ] Critical issues ([#] severity 1-2 tickets)
- [ ] Customer frustration in tickets (tone/language indicates dissatisfaction)

Green Lights:
- [ ] Decreasing ticket volume (getting more self-sufficient)
- [ ] Only low-severity tickets (no major blockers)
- [ ] High CSAT on resolutions

Recommended Actions:
1. [Specific action to improve support experience]
   - Owner: [Support/CSM/Product]
   - Timeline: [When]
   - Success Metric: [Fewer tickets/Faster resolution/Higher CSAT]

**5. FINANCIAL & CONTRACT HEALTH**

Financial Score: [0-100]

Contract Details:
- ARR: [$X]
- Contract Term: [Length]
- Renewal Date: [Date] - Days Left: [#]
- Auto-renewal: [Yes/No]
- Notice Period: [Days before renewal]

Payment History:
- On-time Payments: [X] of [Y] = [%]
- Late Payments: [List any with dates]
- Billing Issues: [Any disputes/credits]

Pricing & Value Alignment:
- Current Price per User: [$X]
- Market Rate: [$Y]
- Discounts Applied: [%]
- Value Perception: [Expensive/Fair/Bargain based on customer feedback]

Expansion Potential:
- Unused Features: [Features they don't use but could benefit from]
- Additional Users: [Potential to add X more users based on Y]
- Upsell Products: [Other products relevant to their needs]
- Cross-sell Opportunities: [Related products they don't have]

Contraction Risk:
- [ ] Requesting to reduce seats
- [ ] Talking about budget cuts
- [ ] Comparing to cheaper alternatives
- [ ] Usage declining (don't need as much)

Red Flags:
- [ ] Price increase at renewal (may cause sticker shock)
- [ ] Customer mentioned budget review
- [ ] Late payment(s)
- [ ] Procurement investigating alternatives

Green Lights:
- [ ] Expressed interest in additional features
- [ ] Asked about adding users
- [ ] Company raised funding/growing
- [ ] Expanded to new teams organically

Recommended Actions:
1. [Specific action related to renewal/expansion]
   - Owner: [CSM/Sales/Finance]
   - Timeline: [When]
   - Success Metric: [Renewed/Expanded by $X]

### CHURN RISK ASSESSMENT

**Churn Probability: [%] - [Low/Medium/High/Critical]**

Risk Factors Present:

| Risk Factor | Severity | Evidence | Weight | Mitigation |
|-------------|----------|----------|--------|------------|
| [Factor] | [H/M/L] | [Specific data point] | [Points] | [What to do] |

Total Risk Score: [Sum of weighted factors]

Historical Churn Patterns:
[If data available, note similar accounts that churned]
- Account Profile: [Similar characteristics]
- Churn Reason: [Why they left]
- Early Warning Signs: [What we should have caught]
- Lessons Applied: [How this informs current account]

**If High/Critical Risk:**

Churn Save Plan:

Immediate Actions (This Week):
1. [Action] - Owner: [Who] - Completion: [When]
2. [Action] - Owner: [Who] - Completion: [When]

Executive Escalation:
- Escalate to: [Your exec / Their exec]
- Meeting Needed: [Yes/No] - If yes, attendees: [Who]
- Agenda: [What to discuss]

Value Reinforcement:
- Proof Points to Share: [Specific outcomes they've achieved]
- ROI Calculation: [Updated business case]
- Roadmap Preview: [Upcoming features that address their needs]

### EXPANSION OPPORTUNITY ANALYSIS

**Expansion Potential: [$X] - [Low/Medium/High]**

Expansion Pathways:

**1. Add Users**
- Current: [X] users
- Potential: [Y] additional users based on [Evidence]
- ARR Impact: [$Z]
- Timing: [Quarter to target]
- Pitch: [Why they should add users now]

**2. Upgrade Tier/Add Features**
- Current Plan: [Tier]
- Recommended: [Higher tier or add-on features]
- Additional Value: [What they get]
- ARR Impact: [$Z]
- Timing: [Quarter to target]
- Pitch: [Tie to goals they have]

**3. Cross-Sell Related Product**
- Current Products: [List]
- Recommended: [Product]
- Use Case: [How it helps them]
- ARR Impact: [$Z]
- Timing: [Quarter to target]
- Pitch: [Tie to current challenges]

Total Expansion Opportunity: [$X]

Expansion Readiness:
- [ ] High product satisfaction
- [ ] Achieving business goals
- [ ] Budget availability indicated
- [ ] Champion can advocate internally
- [ ] Executive sponsor supportive

Expansion Blockers:
- [ ] [Specific blocker] - Mitigation: [How to address]

### ACTION PLAN

**Prioritized Actions for Next 30 Days:**

**Priority 1: Critical (Do immediately)**
1. [Action]
   - Why Critical: [Risk or opportunity]
   - Owner: [Name]
   - Deadline: [Date]
   - Success Criteria: [How we know it worked]

**Priority 2: Important (Do this month)**
[Same format for 3-5 actions]

**Priority 3: Beneficial (Do if time allows)**
[Same format for 2-3 actions]

### SUCCESS PLAN UPDATE

**Quarterly Success Plan:**

This Quarter Goals:
1. [Goal] - Status: [On Track/At Risk/Off Track]
   - Owner: [Customer stakeholder]
   - Our Support: [What CSM is doing]
   - Next Milestone: [What's next] by [When]

2. [Goal]
[Same format]

Next Quarter Preview:
- Recommended Focus: [What to prioritize next]
- New Capabilities to Introduce: [Features launching]
- Business Review: [Schedule EBR if needed]

### COMMUNICATION PLAN

**Internal Communication:**

Notify:
- [ ] Account Executive (if sales implications)
- [ ] Support Team (if technical issues)
- [ ] Product Team (if feature requests/bugs)
- [ ] Leadership (if at-risk or big expansion opportunity)

Message: [Summary of account status and asks]

**Customer Communication:**

Next Touchpoint: [Date] - [Type: Check-in/Business Review/Training]

Agenda:
- Review: [What to discuss]
- Introduce: [New feature/team member]
- Plan: [Next steps/goals]

Pre-work Needed:
- [ ] [Prep item] by [Date]
- [ ] [Prep item] by [Date]

### EXECUTIVE BUSINESS REVIEW PREP

**EBR Status:** [Scheduled for [Date] / Need to schedule / Not yet appropriate]

If EBR Needed:

Recommended Timing: [When and why]
Attendees: [Their execs + our execs]
Agenda:
1. Value delivered (outcomes achieved)
2. Usage trends and insights
3. Strategic roadmap alignment
4. Success plan for next quarter
5. Partnership opportunities

Materials to Prepare:
- [ ] ROI calculations
- [ ] Usage analytics
- [ ] Success stories from their teams
- [ ] Roadmap preview
- [ ] Expansion proposal (if appropriate)

### BENCHMARKING

**How This Account Compares:**

| Metric | This Account | Peer Average | Top Quartile | Status |
|--------|-------------|--------------|--------------|--------|
| Adoption % | [%] | [%] | [%] | [Above/At/Below] |
| User Activity | [Score] | [Score] | [Score] | [Above/At/Below] |
| NPS | [Score] | [Score] | [Score] | [Above/At/Below] |
| Support Tickets | [#/month] | [#/month] | [#/month] | [Lower/Same/Higher] |
| Expansion % | [%] | [%] | [%] | [Above/At/Below] |

Insights:
- Where We're Strong: [What's working well comparatively]
- Where We're Weak: [What needs attention]
- Realistic Target: [Which benchmark to aim for and when]

### TRACKING & FOLLOW-UP

**Check-in Schedule:**

| Date | Type | Purpose | Completed | Notes |
|------|------|---------|-----------|-------|
| [Date] | [Call/Email/Review] | [What to cover] | [ ] | |

**Health Score Tracking:**

| Date | Score | Change | Key Events |
|------|-------|--------|------------|
| [Date] | [Score] | [+/-] | [What happened this period] |

Set Alert:
- If health score drops below [X] → [Trigger escalation process]
- If no customer engagement for [X days] → [Proactive outreach]

### RENEWAL STRATEGY

**Days Until Renewal: [#]**

Renewal Confidence: [%]

Renewal Timeline:

| Timeframe | Action | Owner | Status |
|-----------|--------|-------|--------|
| 90 days before | Begin renewal conversation | CSM | [ ] |
| 60 days before | Present ROI and expansion opportunity | CSM + AE | [ ] |
| 45 days before | Contract review and negotiations | AE | [ ] |
| 30 days before | Final approvals | Customer + Us | [ ] |
| 14 days before | Contract signed | Legal + Procurement | [ ] |

Renewal Playbook:
- [ ] Build business case (ROI calculations)
- [ ] Identify decision makers
- [ ] Address objections proactively
- [ ] Present expansion opportunity
- [ ] Lock in renewal before renewal date

### CONTINGENCY PLANNING

**If Things Go Wrong:**

Scenario 1: Customer raises pricing concern
- Response: [Specific talking points and value reinforcement]
- Escalation: [When to involve sales leadership]

Scenario 2: Champion leaves company
- Response: [How to quickly build new relationships]
- Escalation: [When to get executive sponsor involved]

Scenario 3: Usage drops significantly
- Response: [Intervention strategy]
- Escalation: [When to create formal save plan]

**If Things Go Right:**

Scenario 1: Strong renewal + expansion
- Capture: [Case study/reference/testimonial]
- Leverage: [For more expansions or references]

Scenario 2: Customer becomes advocate
- Activate: [Speaking opportunity/review/reference]
- Reward: [Recognition or benefits]

```
