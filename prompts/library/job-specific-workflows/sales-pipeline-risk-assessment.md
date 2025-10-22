# Sales: Pipeline Risk Assessment & Deal Prioritization

```
You are a sales operations analyst conducting pipeline health analysis for forecast accuracy.

### TASK
Analyze the pipeline data below and provide risk assessment with prioritization recommendations.

### PIPELINE DATA
"""
[SALES REP OR MANAGER PASTES: CRM export with deals, stages, amounts, close dates,
activities, last contact dates, deal age, stakeholders, next steps]
"""

### TEAM CONTEXT
Quota: [$ amount]
Quarter: [Q# YYYY]
Days Remaining: [Number]
Team Size: [Number of reps]
Current Forecast: [$ amount]

### REQUIRED OUTPUT FORMAT

**PIPELINE HEALTH OVERVIEW**

Total Pipeline Value: [$X]
Weighted Pipeline Value: [$X] (based on stage probabilities)
Quota Attainment Projection: [X%]
Coverage Ratio: [Pipeline $ / Quota = X.XX]

Health Status: [Healthy / At Risk / Critical]
- Justification: [2-3 sentences with specific metrics]

### RISK SEGMENTATION

Classify each deal into risk categories:

**HIGH RISK DEALS (Likely to slip or lose)**

Deal: [Company Name] - [$Amount] - Stage: [Stage] - Close: [Date]
- Risk Score: [1-10]
- Risk Factors:
  - Factor 1: [Specific issue - e.g., "No activity in 14 days"]
    - Impact: [How this affects close probability]
  - Factor 2: [e.g., "Champion left company"]
    - Impact: [How this affects close probability]
  - Factor 3: [e.g., "Pushed close date 2x already"]
    - Impact: [How this affects close probability]
- Recommended Action: [Specific next step with owner and deadline]
- Forecast Recommendation: [Remove from forecast / Reduce probability / Push to next quarter]

[Repeat for all high-risk deals]

**MEDIUM RISK DEALS (Need attention)**

[Same format - deals that could go either way]

**ON TRACK DEALS (Progressing normally)**

[Same format - deals with healthy progression]

### DEAL VELOCITY ANALYSIS

**Stalled Deals:**
[Deals with no meaningful activity in >X days based on stage]

Deal: [Company] - Stalled for: [Days]
- Last Activity: [Date and type]
- Stage: [Current stage]
- Problem Diagnosis: [Why it's stuck]
- Unstick Strategy:
  1. [Specific action to re-engage]
  2. [Escalation if needed]
  3. [Timeline for decision: move forward or disqualify]

**Accelerating Deals:**
[Deals moving faster than average]

Deal: [Company] - Stage Change: [From X to Y in Z days]
- Acceleration Factors: [What's driving speed]
- Watch For: [Potential pitfalls when deals move too fast]
- Capture Strategy: [How to maintain momentum]

### STAGE-BY-STAGE ANALYSIS

For each pipeline stage:

**[Stage Name]** - [X deals] - [$Y total value]

Average Time in Stage: [Days]
Expected Close Rate: [Historical %]
Current Concerns:
- [Specific issue with deals at this stage]

Conversion Bottlenecks:
- Issue: [What's preventing progression]
- Affected Deals: [How many]
- Solution: [What needs to happen]

Required Actions This Week:
- [ ] [Action to move deals forward]
- [ ] [Action to move deals forward]

### ACTIVITY-BASED RISK INDICATORS

**Engagement Health Metrics:**

| Deal | Last Email | Last Call | Last Meeting | Activities (30d) | Risk Level |
|------|-----------|-----------|--------------|------------------|------------|
| [Company] | [Days ago] | [Days ago] | [Days ago] | [Count] | [H/M/L] |

Interpretation:
- Red Flags: [Which patterns indicate trouble]
- Healthy Patterns: [What good engagement looks like]

### STAKEHOLDER COVERAGE ANALYSIS

For deals >$X:

**[Company Name] - [$Amount]**

Buying Committee Coverage:
- Economic Buyer: [Identified? Engaged? Champion status?]
- Technical Buyer: [Identified? Engaged? Concerns?]
- User Buyer: [Identified? Engaged? Advocate?]
- Coach/Champion: [Who? Reliability?]

Coverage Score: [X/4 mapped, Y/4 engaged]
Risk: [What's missing and why it matters]
Action: [How to fill gaps]

### COMPETITIVE INTELLIGENCE IN PIPELINE

Deals with Known Competition:

**[Company] - vs. [Competitor]**
- Their Status: [Stage they're at]
- Our Position: [Winning/Even/Losing]
- Key Differentiator: [Our winning angle]
- Vulnerability: [Where they're beating us]
- Counter Strategy: [Specific actions to win]

### CLOSE DATE INTEGRITY ASSESSMENT

**Deals with Close Dates This Month:**

| Deal | Amount | Date | Days Left | Next Step | Date Set By | Confidence |
|------|--------|------|-----------|-----------|-------------|------------|
| [Co] | [$] | [Date] | [#] | [Step] | [Who] | [%] |

Red Flags:
- [Deals with close dates but no next meeting scheduled]
- [Deals with close dates but missing stakeholders]
- [Deals with close dates but stalled activity]

Realistic Close Forecast:
- Committed: [$X] - [List companies]
- Likely: [$X] - [List companies]
- Possible: [$X] - [List companies]
- Removed: [$X] - [List companies and why]

### RESOURCE ALLOCATION RECOMMENDATIONS

**Deals Requiring Leadership Involvement:**
1. [Company] - [$Amount]
   - Why: [Strategic importance / Large size / Stuck / Competitive]
   - Specific Ask: [Executive meeting / Reference call / Custom terms]
   - Owner: [Which executive] - By When: [Date]

**Deals Needing Solution Engineering:**
[Prioritized list with technical hurdles]

**Deals Ready to Close:**
[Prioritized list needing paperwork/legal/procurement support]

### PIPELINE GENERATION REQUIREMENTS

**Gap Analysis:**
Current Pipeline: [$X]
Required to Hit Quota: [$Y]
Gap: [$Z]

To Close Gap:
- New Deals Needed: [#] (at average deal size of [$X])
- OR Expansion of Existing: [Which deals could grow]
- OR Acceleration Strategy: [How to close faster]

**Lead Source Performance:**
[If data available]
- Source: [Type] - Deals: [#] - Close Rate: [%] - Average: [$]
- Recommendation: [Double down / Maintain / Reduce investment]

### FORECAST ACCURACY CHECK

**Historical Pattern Analysis:**
[If previous quarter data available]

Last Quarter:
- Forecasted: [$X]
- Actual: [$Y]
- Variance: [+/-%]
- Common Slip Reasons: [Pattern in what didn't close]

This Quarter - Avoid Repeats:
- [ ] [Check specific to past slippage pattern]
- [ ] [Check specific to past slippage pattern]

### ACTION PLAN BY ROLE

**For Sales Reps:**

High Priority (This Week):
1. [Action] on [Deal] - Why: [Risk mitigation / Acceleration / Closing]
2. [Action] on [Deal] - Why: [Risk mitigation / Acceleration / Closing]
3. [Action] on [Deal] - Why: [Risk mitigation / Acceleration / Closing]

Medium Priority (This Month):
[List 3-5 actions]

**For Sales Manager:**

Deal Reviews Needed:
- [Deal] with [Rep] - Focus: [Specific risk / strategy]

Coaching Opportunities:
- [Pattern across multiple deals] - Rep Training Needed: [Topic]

Forecasting Adjustments:
- Move [Deal] from [Stage/Forecast Category] to [Stage/Forecast Category]
- Rationale: [Specific evidence]

### PIPELINE HYGIENE ISSUES

Data Quality Problems:
- [ ] [X deals missing next steps]
- [ ] [Y deals with close dates in past]
- [ ] [Z deals with incomplete contact info]

Required CRM Cleanup:
1. [Specific update needed] - Owner: [Who] - By: [Date]

### DEAL PRIORITIZATION FRAMEWORK

**Priority Score = (Deal Size × Close Probability × Strategic Value) / Days to Close**

Calculated Priorities:

| Rank | Company | Score | Amount | Probability | Days Left | Action Required |
|------|---------|-------|--------|-------------|-----------|-----------------|
| 1 | [Co] | [#] | [$] | [%] | [#] | [What to do now] |
| 2 | [Co] | [#] | [$] | [%] | [#] | [What to do now] |
| 3 | [Co] | [#] | [$] | [%] | [#] | [What to do now] |

Focus 80% of efforts on top 5 deals.

### SUCCESS METRICS & TRACKING

Weekly Check-Ins:
- Metric: [What to measure]
- Target: [Number/percentage]
- Action if Below: [What to do]

Example:
- New qualified opportunities added: Target 5/week
- Deals advancing stages: Target 3/week
- High-risk deals re-engaged: Target 2/week

### QUARTER-END STRATEGY

Deals That Could Close Early:
- [Company] - Incentive: [What might accelerate]
- Action: [Specific proposal to advance]

Deals to Push to Next Quarter:
- [Company] - Why: [Not real/Not ready/Low probability]
- Benefits: [Clean forecast + focus resources]

### RISK MITIGATION PLAYBOOK

If Forecast Shortfall Projected:

**Option 1: Accelerate Current Deals**
- Target: [Which deals]
- Method: [Specific incentives/concessions]
- Risk: [What we give up]

**Option 2: Expand Deal Sizes**
- Target: [Which deals could grow]
- Method: [Upsell motion]
- Probability: [Likelihood of success]

**Option 3: Aggressive New Pipeline**
- Source: [Where to find deals]
- Timeframe: [Can they close this quarter?]
- Resource: [What's needed]

**Recommended Approach:** [Which option(s) and why]

```
