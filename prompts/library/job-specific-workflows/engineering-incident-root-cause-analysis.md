# Engineering: Production Incident Root Cause Analysis

```
You are a senior site reliability engineer conducting post-incident analysis.

### TASK
Analyze the incident data below and produce a comprehensive root cause analysis with prevention measures.

### INCIDENT DATA
"""
[ENGINEER PASTES: Incident timeline, logs, metrics, alerts, customer impact data,
initial response actions]
"""

### SYSTEM CONTEXT
Service: [Name and purpose]
Architecture: [Microservices/Monolith/Hybrid]
Traffic Volume: [Requests/day or users]
SLA Targets: [Uptime %, latency thresholds]
On-Call Response Time: [Minutes]

### REQUIRED OUTPUT FORMAT

**INCIDENT SUMMARY**
- Start Time: [Timestamp with timezone]
- Detection Time: [Timestamp - how long until detected]
- Resolution Time: [Timestamp]
- Total Duration: [Hours:Minutes]
- Severity: [SEV 1-4 with justification]

**CUSTOMER IMPACT ANALYSIS**
- Users Affected: [Number or percentage]
- Business Impact: [Revenue lost, SLA breach, customer escalations - quantified]
- User Experience: [What customers saw/experienced - 2-3 sentences]
- Downstream Systems: [What other services were affected]

**ROOT CAUSE IDENTIFICATION**

Primary Root Cause: [Single specific technical failure]
- Technical Details: [What failed at the code/infrastructure level]
- Why It Happened: [Configuration error/Code bug/Capacity issue/Dependency failure]
- Why It Wasn't Caught: [Gap in monitoring/testing/review process]

Contributing Factors: [2-4 additional issues that made this worse]
- Factor 1: [Description]
  - How It Contributed: [Specific mechanism]
- Factor 2: [Description]
  - How It Contributed: [Specific mechanism]

**TIMELINE RECONSTRUCTION**

[Create a minute-by-minute timeline showing:]
HH:MM - [Event] - [System state] - [Team action if any]

**PREVENTION MEASURES**

Immediate Actions (Complete within 1 week):
1. [Specific technical fix]
   - Implementation: [Exact change to make]
   - Owner: [Team/person]
   - Verification: [How to confirm it works]

Short-Term Improvements (Complete within 1 month):
[Same format - 2-4 items]

Long-Term Investments (Complete within 1 quarter):
[Same format - 2-3 items]

### SYSTEM IMPROVEMENT RECOMMENDATIONS

Monitoring Enhancements:
- Missing Alert: [What alert would have caught this sooner]
- Dashboard Update: [What metrics need visibility]
- Threshold Adjustment: [What needs tuning]

Testing Gaps:
- Test Scenario: [What test case is missing]
- Load Testing: [What conditions weren't simulated]
- Chaos Engineering: [What failure mode to inject regularly]

### LEARNING DOCUMENTATION

Create a one-paragraph "Incident Lesson" suitable for team wiki:
- What happened (1 sentence)
- Why it matters (1 sentence)
- What changed (1 sentence)

### FOLLOW-UP ACTIONS

List exactly 5 action items in this format:
- Action: [Specific task]
- Owner: [Name or team]
- Due Date: [Specific date]
- Success Criteria: [How we know it's done]
- Tracking: [Ticket number to create]

### COMMUNICATION REQUIREMENTS

Executive Summary (for leadership):
[3 bullets, each 1 sentence]
- What failed and customer impact
- Root cause in business terms
- Cost of prevention vs. cost of recurrence

Customer Communication (if needed):
[2-3 sentence statement if customer notification is required]

### BLAMELESS ANALYSIS REQUIREMENT
Focus on system and process failures, not individual mistakes.
If human error is a factor, identify the system gap that allowed it (missing automation, unclear documentation, inadequate tooling).

```
