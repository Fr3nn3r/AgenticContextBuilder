# Content Research Plan

Research required to enrich the content strategy for the Claims AI case study.

---

## Summary

| Category | Research Items | Estimated Effort |
|----------|---------------|------------------|
| Internal (Project Team) | 8 items | 6-10 hours total |
| External (Market Research) | 6 items | 4-6 hours total |

---

# Part 1: Internal Research (Project Team)

This research requires access to your codebase, logs, metrics, and domain expertise. No external sources needed.

---

## 1.1 Full Failure Catalog Extraction

**What's needed:**
A comprehensive catalog of 10-15 failure modes with root cause, fix, and regression test for each. The case study only documents 4-5.

**Why it matters:**
The "Failure Modes Library" flagship asset and LinkedIn Series C require more examples. This is your most shareable content.

**Data source:**
- Evaluation iteration logs (60+ documented iterations)
- Git commit history for bug fixes
- Any internal post-mortems or debugging notes

**How to execute:**

1. Locate the metrics history file mentioned in the case study
2. For each iteration where accuracy changed significantly (positive or negative), extract:
   - What broke or was fixed
   - Root cause (extraction bug, matching bug, calculation bug, missing rule)
   - The fix applied
   - Whether a regression test was added
3. Categorize failures into types:
   - Extraction failures (OCR, field parsing)
   - Matching failures (keyword gaps, LLM hallucination)
   - Calculation failures (formula bugs, order of operations)
   - Coverage logic failures (missing rules, edge cases)
   - Data quality failures (missing documents, bad input)
4. For each failure, write a 3-sentence story: symptom → cause → fix

**Output format:**

```yaml
failure_modes:
  - id: FM-001
    name: "Substring matching false positive"
    category: matching
    symptom: "EGR valve classified as brake component"
    root_cause: "3-letter substring 'asr' found inside longer word"
    fix: "Symmetric guard requiring exact match for short tokens"
    regression_test: true
    severity: high
    publishable: true
    anonymization_notes: "Safe to publish as-is"
```

**Owner:** Engineer with access to evaluation logs
**Effort:** 2-3 hours

---

## 1.2 Tier Cascade Percentages

**What's needed:**
Exact percentages for how many line items are handled by each matching tier.

**Why it matters:**
LinkedIn Series B and the Reference Architecture need specific numbers: "Tier 1 handles X% of items with zero LLM cost."

**Data source:**
- Coverage analysis logs from evaluation runs
- Match method field in coverage decisions

**How to execute:**

1. Query the evaluation dataset (50 claims, ~150+ line items per run)
2. For each line item, extract the `match_method` field (rule/keyword/LLM)
3. Calculate:
   - % handled by Tier 1 (rule engine)
   - % handled by Tier 2 (keyword matcher)
   - % handled by Tier 3 (LLM fallback)
4. Break down by coverage decision:
   - % of COVERED items by tier
   - % of EXCLUDED items by tier
   - % of REFER items by tier
5. Calculate average confidence score per tier

**Output format:**

```markdown
## Tier Cascade Performance

| Tier | Method | % of Items | Avg Confidence | LLM Cost |
|------|--------|------------|----------------|----------|
| 1 | Rule Engine | 42% | 1.00 | $0.00 |
| 2 | Keyword Matcher | 38% | 0.82 | $0.00 |
| 3 | LLM Fallback | 20% | 0.71 | $X.XX |
```

**Owner:** Engineer with access to evaluation outputs
**Effort:** 1 hour

---

## 1.3 Token Economics Calculation

**What's needed:**
Hard numbers on LLM cost per claim, token consumption breakdown, and ROI framing.

**Why it matters:**
LinkedIn Series E (Economics) and the Exec Playbook need concrete cost data. "Token budgets are like reinsurance" needs actual numbers.

**Data source:**
- LLM audit logs (token counts per call)
- OpenAI/Azure pricing
- Claim processing run summaries

**How to execute:**

1. From a representative sample of 20+ claims, extract:
   - Total tokens consumed (input + output)
   - Tokens by pipeline stage (classification, extraction, coverage analysis)
   - Number of LLM calls per claim
2. Calculate:
   - Average tokens per claim
   - Median tokens per claim
   - 95th percentile (tail risk)
   - Cost per claim at current pricing (GPT-4o: $5/1M input, $15/1M output)
3. Compare:
   - LLM cost vs. estimated human adjuster time (15-30 min @ hourly rate)
   - Cost per decision vs. average claim value (CHF 1,450)
4. Document the cost control mechanisms:
   - Token cap thresholds (warn at 40K, fail at 60K)
   - Max items per claim (35)
   - Concurrency limits

**Output format:**

```markdown
## Token Economics Summary

| Metric | Value |
|--------|-------|
| Avg tokens per claim | 28,400 |
| Median tokens per claim | 24,100 |
| 95th percentile | 52,000 |
| Avg LLM cost per claim | $0.18 |
| Avg human time saved | 22 min |
| Cost per minute saved | $0.008 |
```

**Owner:** Engineer with access to run logs
**Effort:** 1-2 hours

---

## 1.4 Multilingual Parsing Examples

**What's needed:**
Specific before/after examples of German, French, and Italian parsing challenges.

**Why it matters:**
The blog post "Multilingual claims docs: what breaks first" needs concrete examples beyond the brief mentions in the case study.

**Data source:**
- Keyword mapping configuration files
- Extraction test cases
- OCR output samples

**How to execute:**

1. From keyword mappings, extract 5-7 examples per category:
   - German compound words (e.g., "Abgasrückführungsventil")
   - French equivalents (e.g., "vanne EGR")
   - German/French synonym pairs
2. From extraction tests, document:
   - Date format variations handled
   - Number format edge cases (Swiss thousands separator)
   - Currency symbol positions
3. From OCR outputs, find examples of:
   - Umlaut recognition challenges (ä, ö, ü → ae, oe, ue)
   - Mixed-language documents
   - Handwritten annotations on printed forms
4. Document any language-specific accuracy differences

**Output format:**

```markdown
## Multilingual Parsing Challenges

### German Compound Words
| German Term | Decomposition | Component Category |
|-------------|---------------|-------------------|
| Abgasrückführungsventil | Abgas + rückführung + ventil | Exhaust system |
| Wasserpumpengehäuse | Wasser + pumpen + gehäuse | Cooling system |

### Cross-Language Synonyms
| German | French | Category |
|--------|--------|----------|
| Wasserpumpe | Pompe à eau | Cooling |
| Kupplung | Embrayage | Transmission |
```

**Owner:** Domain expert or engineer familiar with vocabulary config
**Effort:** 1-2 hours

---

## 1.5 Vendor Scorecard Formalization

**What's needed:**
A scoring rubric with pass/fail criteria for each vendor evaluation question.

**Why it matters:**
The "Vendor Evaluation Scorecard" flagship asset needs more than questions—it needs a grading system.

**Data source:**
- Your own experience building the system
- Implicit criteria from the case study
- Domain knowledge of what "good" looks like

**How to execute:**

1. List the 20 vendor questions implied by the strategy:
   - Data requirements and quality
   - Evaluation methodology
   - Audit and compliance
   - Cost controls
   - Safety and human-in-loop
2. For each question, define:
   - What a "green flag" answer looks like
   - What a "yellow flag" answer looks like
   - What a "red flag" answer looks like
3. Weight the questions by importance (must-have vs nice-to-have)
4. Create a scoring mechanism (points or traffic light)

**Output format:**

```markdown
## Vendor Evaluation Rubric

### Question 1: "How do you measure accuracy on unseen data?"

| Rating | Answer Pattern |
|--------|---------------|
| Green | "We use a holdout set with X% of data never seen during development" |
| Yellow | "We use cross-validation on our training data" |
| Red | "We measure accuracy on our demo dataset" / no clear answer |

**Weight:** Must-have
**Why it matters:** Dev vs holdout gap reveals true generalization
```

**Owner:** Project lead or senior engineer
**Effort:** 2-3 hours

---

## 1.6 Payout Accuracy Deep Dive

**What's needed:**
Understanding why payout accuracy is only 28% even when decision accuracy is 98%.

**Why it matters:**
This is a nuance worth exploring in content. Correct approve/deny ≠ correct amount.

**Data source:**
- Evaluation results with payout comparisons
- Mismatch analysis logs

**How to execute:**

1. For the 25 correctly approved claims in the evaluation set, categorize payout mismatches:
   - Within 5% of ground truth (7 claims)
   - 5-15% off (X claims)
   - 15%+ off (Y claims)
2. For each mismatch bucket, identify root causes:
   - Line item coverage disagreements
   - Reimbursement rate calculation differences
   - Deductible interpretation differences
   - VAT handling differences
3. Determine which mismatches are:
   - System bugs (fixable)
   - Ground truth ambiguity (adjuster discretion)
   - Missing data (policy details not in documents)

**Output format:**

```markdown
## Payout Accuracy Analysis

| Bucket | Count | Primary Cause |
|--------|-------|---------------|
| Within 5% | 7 | Correct |
| 5-15% off | 10 | Line item coverage disagreement |
| 15%+ off | 8 | Reimbursement rate edge cases |
```

**Owner:** Engineer with access to evaluation comparisons
**Effort:** 1-2 hours

---

## 1.7 QA Console Screenshots (Sanitized)

**What's needed:**
Sanitized screenshots or mockups of the QA console for the "Provenance is the UI" content.

**Why it matters:**
LinkedIn post 10 and the Auditability blog need visual proof of provenance tracking.

**Data source:**
- QA console application
- Test claims with non-sensitive data

**How to execute:**

1. Load a test claim with synthetic or fully anonymized data
2. Capture screenshots showing:
   - Document split view (fields left, source right)
   - Provenance highlighting (click field → source highlighted)
   - Coverage reasoning view (per-line-item decisions)
   - Triage buckets (Approved/Needs Review/Rejected)
3. Sanitize any visible data:
   - Replace real names with "Max Mustermann" / "Jean Dupont"
   - Replace VINs with synthetic patterns
   - Replace policy numbers with "POL-XXXX-XXXX"
4. Export as PNG with consistent branding

**Output format:**
3-5 sanitized screenshots in `assets/` folder

**Owner:** Anyone with access to QA console
**Effort:** 30 min - 1 hour

---

## 1.8 Ground Truth Methodology Documentation

**What's needed:**
A writeup of how you built and maintained the ground truth dataset.

**Why it matters:**
"Ground truth is the foundation of everything" is a key lesson. The Benchmark Kit needs methodology guidance.

**Data source:**
- Internal documentation
- Knowledge from whoever built the ground truth

**How to execute:**

1. Document the ground truth creation process:
   - How claims were selected (random? stratified? edge cases?)
   - Who labeled them (adjusters? engineers? both?)
   - What fields were labeled (decision, payout, denial reason, per-line coverage?)
   - How disagreements were resolved
2. Document the labeling schema:
   - Decision categories (Approve, Deny, Refer)
   - Denial reason taxonomy
   - Payout calculation fields
3. Document quality control:
   - Inter-annotator agreement (if measured)
   - Review process for edge cases
   - How ground truth was updated when errors were found
4. Calculate effort metrics:
   - Time per claim to label
   - Total person-hours invested

**Output format:**

```markdown
## Ground Truth Methodology

### Claim Selection
- 84 claims sampled from 6-month production period
- Stratified by: approval rate, claim value, vehicle brand, language

### Labeling Process
- Primary labeler: Senior claims adjuster (15 years experience)
- Review: Engineering team for calculation verification
- Time per claim: ~12 minutes average

### Schema
- Decision: Approve | Deny | Refer
- Denial reasons: 8 categories (see taxonomy)
- Payout: Gross covered, net payout, calculation steps
- Per-line-item: Coverage decision with explanation
```

**Owner:** Project lead or domain expert
**Effort:** 1 hour

---

# Part 2: External Research (Market/Industry)

This research requires web searches, industry reports, and competitor analysis. No internal data needed.

---

## 2.1 Industry Benchmarks for Claims Processing

**What's needed:**
External data points on manual claims processing time, error rates, and automation adoption.

**Why it matters:**
The Exec Playbook and ROI content need industry context beyond your single case study.

**Sources to check:**

1. **McKinsey / BCG / Deloitte insurance reports**
   - Search: "insurance claims automation 2024 2025"
   - Search: "intelligent document processing insurance benchmark"
   - Look for: automation rates, time savings, error reduction

2. **ACORD / Insurance Information Institute**
   - Industry standards bodies often publish processing benchmarks
   - Search: "claims processing time benchmark insurance"

3. **Vendor case studies (Hyperscience, Indico, ABBYY, Kofax)**
   - Competitors publish case studies with metrics
   - Extract: claimed accuracy, time savings, ROI figures
   - Note: these are marketing numbers, treat skeptically

4. **Gartner / Forrester on IDP**
   - Search: "intelligent document processing market 2025"
   - Look for: adoption rates, common challenges, maturity models

**How to execute:**

1. Allocate 1-2 hours for web research
2. For each source, extract:
   - Metric claimed
   - Context (industry, geography, sample size)
   - Source credibility (peer-reviewed > consulting > vendor)
3. Create a reference table with citations
4. Flag metrics that contradict each other

**Output format:**

```markdown
## Industry Benchmarks

| Metric | Value | Source | Notes |
|--------|-------|--------|-------|
| Avg claims processing time (manual) | 15-20 min | McKinsey 2024 | P&C insurance, US market |
| IDP accuracy (vendor claimed) | 85-95% | Vendor avg | Marketing figures, likely optimistic |
| Automation adoption rate | 23% | Forrester 2024 | Large insurers only |
```

**Effort:** 1-2 hours

---

## 2.2 Regulatory Landscape (EU/Swiss Insurance AI)

**What's needed:**
Overview of regulatory requirements for AI in insurance decisions, especially EU AI Act implications.

**Why it matters:**
The Auditability content and Compliance-focused assets need regulatory grounding.

**Sources to check:**

1. **EU AI Act text and guidance**
   - Search: "EU AI Act insurance claims high risk"
   - Check if claims automation is classified as high-risk AI

2. **FINMA (Swiss Financial Market Supervisory Authority)**
   - Search: "FINMA AI guidance insurance"
   - Look for: explainability requirements, audit requirements

3. **EIOPA (European Insurance Authority)**
   - Search: "EIOPA AI governance insurance"
   - Look for: model risk management, algorithmic decision-making

4. **Industry associations (Swiss Insurance Association, Insurance Europe)**
   - May have position papers on AI adoption

**How to execute:**

1. Focus on finding 3-5 authoritative sources
2. Extract specific requirements:
   - Explainability mandates
   - Human oversight requirements
   - Audit trail requirements
   - Consumer notification requirements
3. Note effective dates and transition periods
4. Identify gaps where guidance is unclear

**Output format:**

```markdown
## Regulatory Requirements Summary

### EU AI Act
- **Classification:** Claims automation likely "high-risk" under Annex III
- **Requirements:** Human oversight, risk management, documentation
- **Effective:** August 2025 (full enforcement 2026)

### FINMA Guidance
- **Requirement:** Explainability for automated decisions affecting customers
- **Requirement:** Audit trail for model decisions
- **Status:** Guidance, not binding regulation (as of 2024)
```

**Effort:** 1-2 hours

---

## 2.3 Competitor Positioning Analysis

**What's needed:**
Understanding of how competitors (IDP vendors, claims automation vendors) position themselves.

**Why it matters:**
The Vendor Scorecard and differentiation messaging need competitive context.

**Vendors to research:**

| Category | Vendors |
|----------|---------|
| Horizontal IDP | Hyperscience, Indico, ABBYY, Kofax, Amazon Textract |
| Insurance-specific | Shift Technology, Tractable, Snapsheet, Duck Creek |
| Claims automation | Guidewire, One Inc, Hi Marley |

**How to execute:**

1. Visit each vendor's website (30 min total)
2. For each, extract:
   - Key claims/positioning (accuracy, speed, cost)
   - Target customer (enterprise, mid-market, SMB)
   - Technical approach (rules, ML, LLM, hybrid)
   - Differentiators claimed
   - Obvious gaps or weaknesses
3. Look for customer case studies with metrics
4. Note pricing models if public

**Output format:**

```markdown
## Competitor Positioning

### Hyperscience
- **Positioning:** "Automate any document workflow"
- **Claimed accuracy:** 99%+ (marketing)
- **Approach:** ML-based extraction, human-in-loop
- **Gap:** Generic platform, not insurance-specific

### Shift Technology
- **Positioning:** "AI-native insurance decisions"
- **Focus:** Fraud detection, not claims processing
- **Approach:** ML models trained on claims data
- **Gap:** Requires large training data, black-box models
```

**Effort:** 1-2 hours

---

## 2.4 Common Objections and Concerns

**What's needed:**
A list of common objections that claims executives raise about AI automation.

**Why it matters:**
The Workshop Deck and Exec Playbook need to preemptively address concerns.

**Sources to check:**

1. **LinkedIn discussions**
   - Search: "claims automation concerns" or "insurance AI risks"
   - Look at comments on vendor posts
   - Note recurring skepticism themes

2. **Industry conference recordings/summaries**
   - InsureTech Connect, DIA, Insurance Innovators
   - Search for panel discussions on AI in claims

3. **Reddit / Blind / industry forums**
   - Search: "claims automation" in insurance subreddits
   - Look for practitioner skepticism

4. **Published surveys**
   - Search: "insurance executives AI adoption barriers"

**How to execute:**

1. Compile a list of 10-15 common objections
2. Categorize by stakeholder:
   - Claims executives (job displacement, accuracy, liability)
   - IT/Compliance (security, audit, integration)
   - Finance (ROI, hidden costs, maintenance)
3. For each objection, note:
   - How often it appears (common vs rare)
   - Whether you have a direct answer from your case study
   - Whether it's a legitimate concern or misconception

**Output format:**

```markdown
## Common Objections

### From Claims Executives
1. "AI will miss edge cases that experienced adjusters catch"
   - Frequency: Very common
   - Our answer: Holdout testing, triage buckets, human review for edge cases

2. "Accuracy claims from vendors are always inflated"
   - Frequency: Very common
   - Our answer: Dev vs holdout gap honesty, demand holdout testing

### From IT/Compliance
1. "We can't explain AI decisions to regulators"
   - Frequency: Common
   - Our answer: Provenance chain, decision records, not a black box
```

**Effort:** 1 hour

---

## 2.5 Claims Processing Terminology Glossary

**What's needed:**
A glossary of industry-standard terms to ensure content uses correct terminology.

**Why it matters:**
Credibility depends on using the right words. "Claims adjudication" vs "claims processing" matters to insiders.

**Sources to check:**

1. **ACORD data standards**
   - Official insurance data model definitions

2. **ISO claims management standards**
   - ISO 27001 for data, industry-specific standards

3. **Vendor documentation**
   - How do established players define terms?

4. **Wikipedia / Investopedia**
   - Basic definitions for cross-checking

**Terms to define:**

- Adjudication vs. processing vs. automation
- Straight-through processing (STP)
- First notice of loss (FNOL)
- Subrogation
- Indemnity vs. liability
- Excess / deductible / franchise
- Coverage / peril / exclusion

**How to execute:**

1. Create a glossary of 15-20 key terms
2. For each term, note:
   - Standard definition
   - How you use it (if different)
   - Regional variations (US vs UK vs EU)
3. Use this glossary to audit content before publishing

**Output format:**

```markdown
## Glossary

| Term | Definition | Usage Note |
|------|------------|------------|
| Adjudication | The process of deciding claim validity and payout | Use for the decision, not the whole process |
| STP (Straight-through processing) | Claims processed without human intervention | Industry-standard term for full automation |
| Excess | Amount the policyholder pays before coverage applies | UK/EU term; US uses "deductible" |
```

**Effort:** 30 min - 1 hour

---

## 2.6 Visual Inspiration / Design References

**What's needed:**
Examples of well-designed technical diagrams and infographics in the B2B/insurance space.

**Why it matters:**
The 9 visuals in the strategy need to be "clean, branded, and reusable." Need design direction.

**Sources to check:**

1. **Dribbble / Behance**
   - Search: "B2B infographic" "technical architecture diagram"
   - Look for: clean, minimal, professional styles

2. **Competitor marketing materials**
   - Vendor one-pagers and architecture diagrams
   - Note what works and what looks generic

3. **Consulting firm reports**
   - McKinsey, BCG, Deloitte visuals
   - These set the bar for "executive-ready"

4. **Technical blogs**
   - Stripe, Figma, Linear engineering blogs
   - Modern, clean technical communication

**How to execute:**

1. Save 10-15 examples of diagrams you like
2. Note what makes them effective:
   - Color palette
   - Typography
   - Information hierarchy
   - Use of icons vs text
3. Create a mood board for your visual style
4. Share with designer (or use as self-reference)

**Output format:**
Folder of reference images with notes on what to emulate

**Effort:** 30 min

---

# Part 3: Research Prioritization

## Immediate (Before First Content)

| Research | Owner | Effort | Blocks |
|----------|-------|--------|--------|
| Tier Cascade Percentages | Engineer | 1 hr | LinkedIn Series B, Reference Architecture |
| Failure Catalog Extraction | Engineer | 2-3 hr | LinkedIn Series C, Failure Modes Library |
| Sanitized Screenshots | Anyone | 30 min | LinkedIn post 10, Auditability content |

## Before Flagship Assets

| Research | Owner | Effort | Blocks |
|----------|-------|--------|--------|
| Token Economics | Engineer | 1-2 hr | Exec Playbook, LinkedIn Series E |
| Vendor Scorecard Formalization | Lead | 2-3 hr | Vendor Scorecard asset |
| Industry Benchmarks | Anyone | 1-2 hr | Exec Playbook context |
| Ground Truth Methodology | Lead | 1 hr | Benchmark Kit |

## Can Defer

| Research | Owner | Effort | Blocks |
|----------|-------|--------|--------|
| Regulatory Landscape | Anyone | 1-2 hr | Compliance blog posts |
| Competitor Positioning | Anyone | 1-2 hr | Differentiation messaging |
| Multilingual Examples | Engineer | 1-2 hr | Multilingual blog post |
| Payout Accuracy Deep Dive | Engineer | 1-2 hr | Advanced content |
| Common Objections | Anyone | 1 hr | Workshop deck |
| Glossary | Anyone | 30 min | Quality control |
| Visual References | Anyone | 30 min | Design phase |

---

# Part 4: Research Tracking Template

Use this template to track research completion:

```markdown
## Research Log

| ID | Research Item | Owner | Status | Started | Completed | Output Location |
|----|---------------|-------|--------|---------|-----------|-----------------|
| I-1 | Failure Catalog | TBD | Not Started | - | - | - |
| I-2 | Tier Percentages | TBD | Not Started | - | - | - |
| I-3 | Token Economics | TBD | Not Started | - | - | - |
| I-4 | Multilingual Examples | TBD | Not Started | - | - | - |
| I-5 | Vendor Scorecard | TBD | Not Started | - | - | - |
| I-6 | Payout Analysis | TBD | Not Started | - | - | - |
| I-7 | QA Screenshots | TBD | Not Started | - | - | - |
| I-8 | Ground Truth Methodology | TBD | Not Started | - | - | - |
| E-1 | Industry Benchmarks | TBD | Not Started | - | - | - |
| E-2 | Regulatory Landscape | TBD | Not Started | - | - | - |
| E-3 | Competitor Analysis | TBD | Not Started | - | - | - |
| E-4 | Common Objections | TBD | Not Started | - | - | - |
| E-5 | Terminology Glossary | TBD | Not Started | - | - | - |
| E-6 | Visual References | TBD | Not Started | - | - | - |
```

---

*Document created: 2026-02-06*
*Last updated: 2026-02-06*
