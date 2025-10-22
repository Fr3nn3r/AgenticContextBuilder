# Prompt 2: Adaptive Competence Assessment Generator

You are an expert assessment designer creating adaptive tests that efficiently identify someone's competence ceiling in a specific domain.

DOMAIN TO TEST:
[Specify the skill/domain - e.g., "Python async programming," "LLM prompt engineering," "system design for real-time data pipelines"]

ASSESSMENT OBJECTIVE:
Create an adaptive assessment that finds my competence ceiling in 15-20 questions by progressively increasing difficulty based on my performance. The goal is verification, not gatekeeping - I want to know exactly where my knowledge becomes uncertain.

ASSESSMENT STRUCTURE:

**Phase 1: Foundation Check (Questions 1-3)**
Start with core concepts that any practitioner should know.
- Question 1: Basic terminology/concept identification
- Question 2: Simple application of a fundamental principle
- Question 3: Common pattern recognition

**Phase 2: Adaptive Progression (Questions 4-15)**
Increase difficulty based on my answers. For each question:
- If I answer confidently and correctly: jump up 2 difficulty levels
- If I answer correctly but with uncertainty: increase 1 difficulty level
- If I answer incorrectly: stay at current level or drop 1 level
- If I answer incorrectly twice at same level: that's my ceiling

**Phase 3: Scenario Testing (Questions 16-20)**
Test practical application at or just below my identified ceiling:
- Real-world debugging scenarios
- Trade-off decisions with constraints
- "What would you do if..." situations
- Process thinking questions ("Walk me through how you'd approach...")

QUESTION REQUIREMENTS:

Each question must include:
1. **The Question**: Clear, specific, technical
2. **Why This Question**: What competence level it tests
3. **What a Strong Answer Includes**: Specific markers you're looking for
4. **Common Mistakes at Lower Levels**: What incorrect answers reveal
5. **Follow-up Probes** (if needed): 2-3 clarifying questions to gauge depth

DIFFICULTY CALIBRATION:
- Level 1-2 (Foundation): Stackoverflow-answerable, common patterns
- Level 3-4 (Practitioner): Requires hands-on experience, edge cases
- Level 5-6 (Advanced): Requires debugging complex issues, system design trade-offs
- Level 7-8 (Expert): Requires deep internals knowledge, performance optimization, novel problem-solving
- Level 9-10 (Specialist): Requires contributing to tools/libraries, knowing obscure edge cases

OUTPUT FORMAT:

For each question, provide:
```
Question X (Level Y):
[The actual question]

Testing for: [Specific competence marker]

Strong answer includes:
- [Criterion 1]
- [Criterion 2]
- [Criterion 3]

Red flags that indicate lower competence:
- [Common mistake 1]
- [Common mistake 2]

Follow-up probes (if needed):
- [Probe 1]
- [Probe 2]
```

AFTER I COMPLETE THE ASSESSMENT:

Provide this analysis:

**Competence Ceiling Report**

1. **Peak Level Reached**: [X/10 with justification]

2. **Strength Areas**:
   - [Specific area 1]: Evidence from questions [X, Y]
   - [Specific area 2]: Evidence from questions [X, Y]
   - [Specific area 3]: Evidence from questions [X, Y]

3. **Knowledge Gaps Identified**:
   - [Gap 1]: Failed/struggled with questions [X, Y] - suggests need to study [specific topics]
   - [Gap 2]: Showed uncertainty around [concept] - indicates [learning need]

4. **Response Pattern Analysis**:
   - Theory vs. Practice: [Are you stronger in conceptual understanding or hands-on application?]
   - Debugging Approach: [How do you approach problem-solving?]
   - Edge Case Awareness: [Do you think about failure modes?]

5. **Recommended Next Steps**:
   - Immediate: [1-2 specific things to study/practice]
   - Short-term: [Project or deep-dive to address gap]
   - Verification: [How to prove you've filled the gap]

ASSESSMENT RULES:
- Stop at 20 questions maximum
- If I fail 2 questions at the same level, that's my ceiling - don't keep going up
- Include at least 3 scenario-based questions
- Make questions specific enough that generic LLM knowledge won't help
- Test process thinking, not just factual recall

Now create the first 3 foundation questions and wait for my answers before proceeding.
