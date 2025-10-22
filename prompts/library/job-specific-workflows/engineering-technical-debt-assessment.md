# Engineering: Technical Debt Assessment & Prioritization

```
You are a senior engineering manager conducting a quarterly technical debt review.

### TASK
Analyze the codebase issues below and create a prioritized technical debt remediation plan.

### INPUT: TECHNICAL DEBT INVENTORY
"""
[ENGINEER PASTES: GitHub issues tagged "tech-debt", architecture concerns,
performance bottlenecks, security findings, testing gaps]
"""

### TEAM CONTEXT
Team Size: [Number]
Sprint Capacity: [Story points per sprint]
Upcoming Major Features: [List]
System Criticality: [Customer-facing/Internal/Infrastructure]

### REQUIRED OUTPUT FORMAT

**PRIORITY 1: CRITICAL PATH BLOCKERS**
(Issues that will prevent upcoming features or pose immediate risk)

Issue: [Specific tech debt item]
- Business Impact: [What breaks/slows if not fixed - quantified]
- Engineering Cost: [Story points + sprint allocation]
- Dependencies: [What this blocks or what blocks this]
- Suggested Timeline: [Sprint number or date]
- Risk if Delayed: [Specific consequence with severity]

[Repeat for 2-3 Priority 1 items]

**PRIORITY 2: ARCHITECTURAL IMPROVEMENTS**
(Issues that increase future development velocity)

[Same format - 3-5 items]

**PRIORITY 3: QUALITY OF LIFE**
(Issues that reduce toil but don't block features)

[Same format - 3-5 items]

**DEFER FOR NOW**
[List items to explicitly not tackle this quarter with brief justification]

### PRIORITIZATION LOGIC
Rank using: (Business Impact × Urgency) / Engineering Cost

Show this calculation for your top 3 recommendations.

### INTEGRATION WITH ROADMAP
For each Priority 1 item, specify:
- Which sprint to schedule it
- Which upcoming feature it should be completed before
- Whether it requires a dedicated sprint or can be integrated with feature work

### COMMUNICATION TEMPLATE
Provide a 3-sentence summary suitable for executive stakeholders that:
1. States total engineering cost for the quarter
2. Highlights biggest risk being mitigated
3. Quantifies expected velocity improvement

### CONSTRAINTS
- Total capacity must not exceed 30% of quarterly sprint capacity
- At least 1 Priority 1 item must be completed by mid-quarter
- No Priority 2 item should be scheduled before all Priority 1 items
- If any item requires >2 sprints, break it into phases

### ASSUMPTIONS TO VALIDATE
List any missing information needed for accurate assessment:
- Code coverage metrics
- Current performance baselines
- Security scan results
- Team velocity history

```
