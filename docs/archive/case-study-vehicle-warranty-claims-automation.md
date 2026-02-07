# Case Study: Automating Vehicle Warranty Claims Processing with AI Document Intelligence

**From 18% to 98% Decision Accuracy in 7 Days**

---

## The Problem Nobody Talks About

A vehicle warranty claim lands on an adjuster's desk.

Five documents. Three languages. A cost estimate with 30 line items. A policy with coverage tiers, mileage-dependent reimbursement rates, and component exclusion lists buried on page two.

The adjuster opens each document. Cross-references part names against the coverage list. Checks the service history. Validates the policy dates. Calculates the payout using a formula involving deductibles, VAT, coverage caps, and reimbursement percentages.

**This takes 15-30 minutes per claim.** Multiply that by hundreds of claims per month.

76% of denied claims fail for a single reason: **the part is not covered by the policy.** A deterministic, lookup-based check. No judgment call required.

The industry knows this is automatable. The hard part is building a system that actually works on real documents, in production, with real accuracy.

---

## The Starting Point: Manual Processing at Scale

Our client is a **European vehicle warranty insurance provider** operating in a multilingual market (German, French, Italian). They process motor guarantee claims from a network of 79+ independent garages and authorized dealers across the country.

**The numbers that defined the problem:**

- 84 claims analyzed across the pilot period
- 50/50 approval-to-denial split in evaluation data (65-70% approval rate in production)
- Average approved payout: CHF 1,450 (median CHF 949)
- 23 vehicle brands represented, with German premium brands (VW, Mercedes, BMW, Audi) accounting for 54% of claim volume
- 14 distinct document types per claim workflow
- Average 4.9 documents per claim submission

Every claim required a human adjuster to:
1. Read and cross-reference multiple documents
2. Verify policy validity and coverage terms
3. Match claimed parts against coverage lists
4. Calculate payouts with mileage-dependent reimbursement tiers
5. Write a decision with supporting rationale

The company needed an **intelligent document processing (IDP)** solution that could handle the full lifecycle: ingestion, classification, extraction, screening, coverage analysis, and payout calculation. Not a proof of concept. A working system with measurable accuracy on real claims.

---

## Why Existing Approaches Fall Short

Most document processing tools solve one problem: they extract text from PDFs.

That gets you 10% of the way.

The real challenge in insurance claims automation is **cross-document reasoning.** A cost estimate means nothing without the policy. A service history means nothing without the manufacturer's maintenance intervals. A mileage reading means nothing without the coverage cap.

**Three specific failures we saw in the market:**

**1. Generic OCR pipelines can't handle domain complexity.**
A cost estimate from a Swiss repair garage contains line items in German with part numbers, labor codes, hourly rates, carry-forward subtotals across pages, and VAT calculations. Standard OCR tools extract text. They don't extract structured line items with part-category associations and coverage implications.

**2. Single-model approaches plateau early.**
Sending an entire claim to an LLM and asking "should this be approved?" produces inconsistent results. LLMs hallucinate part names, invent coverage rules, and can't reliably perform multi-step financial calculations. Our baseline accuracy with an LLM-only approach: **18%**.

**3. Rule-based systems can't scale to vocabulary.**
Insurance claims use thousands of part names across multiple languages. A "Wasserpumpe" in German is a "pompe a eau" in French. An "EGR valve" might be called "Abgasruckfuhrung" on one invoice and "vanne EGR" on another. Pure keyword matching breaks on the first synonym it hasn't seen.

The solution requires a **hybrid architecture**: deterministic rules where they work, keyword matching for known vocabulary, and LLM reasoning as a calibrated fallback. Each layer with explicit confidence scoring and provenance tracking.

---

## The Architecture: A Multi-Stage Pipeline with Confidence Scoring

We built an end-to-end **claims document processing pipeline** that processes raw documents through five stages, each with quality gates and audit logging.

### Stage 1: Document Ingestion (OCR + Text Extraction)

Raw PDFs and images enter the system through a pluggable ingestion layer. Three providers are supported:

- **Azure Document Intelligence** for production-grade OCR with table extraction
- **OpenAI Vision API** for image-heavy documents
- **Tesseract OCR** as a local fallback

Each page is extracted independently with character-level position tracking. This enables **provenance** later: every extracted field links back to a specific page, character range, and (for tables) cell reference.

**Key technical decision:** Page-level extraction rather than document-level. This matters for multi-page cost estimates where carry-forward totals span pages and headers repeat.

### Stage 2: Document Classification (AI-Powered Routing)

Each document is classified into one of 14 types using an LLM-powered router guided by a **document type catalog** defined in YAML.

Supported document types include:
- Vehicle warranty policies (guarantee documents)
- Repair cost estimates (Kostenvoranschlag / Devis)
- Service maintenance records
- Vehicle registration certificates
- Diagnostic reports (OBD fault codes)
- Claim decision letters
- Customer communications
- Damage evidence photos
- Invoices and delivery notes

The classification prompt includes **language-specific cues** in German, French, and Italian. For example, a "Fahrzeugausweis" (German), "Permis de circulation" (French), and "Licenza di circolazione" (Italian) all map to the same `vehicle_registration` type.

**Accuracy:** Classification runs at near-100% accuracy on the evaluation set. Misclassification is rare when the document type catalog is comprehensive.

### Stage 3: Structured Field Extraction with Quality Gates

This is where domain-specific extractors do the heavy lifting. Each document type has a dedicated **extraction spec** (YAML) defining required fields, optional fields, and field groups for LLM optimization.

**Example: Warranty policy extraction (51 fields across 4 parallel groups)**

| Group | Fields | Examples |
|-------|--------|----------|
| Policy & Policyholder | 13 | Policy number, guarantee type, start/end dates, waiting period |
| Vehicle Details | 11 | VIN, make, model, fuel type, first registration, current km |
| Coverage Options | 15 | Max coverage, excess percent, excess minimum, km limit, turbo/hybrid flags |
| Assistance & Mobility | 4 | Towing amount, rental per day, rental max per event |

**Example: Cost estimate extraction (multi-page, line-item level)**

The cost estimate extractor processes documents page-by-page, handling:
- Header extraction (garage, vehicle, dates) from page 1
- Line item extraction (part number, description, quantity, unit price, total, labor type) from all pages
- Carry-forward subtotals ("Ubertrag" in German) across pages
- Summary extraction (grand total, VAT, labor total) from the last page
- Total validation within CHF 5 tolerance

Each extracted field carries:
- **Confidence score** (0.0-1.0)
- **Provenance** (page number, character range, extraction method)
- **Quality gate verdict** (pass/warn/fail based on missing required fields)

Fields that fail the quality gate are routed for human review rather than silently passing bad data downstream.

### Stage 4: Screening and Coverage Analysis (The Decision Engine)

This is the core innovation. A **deterministic screening pipeline** runs 11 checks before any LLM-based assessment:

| Check | What It Validates | Verdict |
|-------|-------------------|---------|
| 0. Policy Enforcement | Is the policy in the rejected list? | Hard fail |
| 1. Policy Validity | Is the policy active on the damage date? | Hard fail |
| 1b. Damage Date | Is the claim date clear and valid? | Hard fail |
| 2. Service Compliance | Did the vehicle meet manufacturer service intervals? | Soft check |
| 2b. Shop Authorization | Is the repair shop authorized? | Informational |
| 3. Mileage | Does the odometer exceed the coverage limit? | Hard fail |
| 4. Damage Cause | Does the DTC code match an exclusion? | Conditional |
| 5. Component Coverage | Is the defective part in the coverage list? | Hard fail |
| 5b. Labor Follows Parts | Is labor anchored to a covered part? | Conditional |
| 5c. Hybrid Exclusion | Are hybrid-specific parts excluded by the policy? | Hard fail |
| 5d. Damage Cause Exclusion | Does the root cause match an excluded pattern? | Hard fail |

**Service compliance** alone required building a database of manufacturer-specific service intervals for 18 vehicle brands, covering petrol, diesel, hybrid, and electric variants. Each brand has different interval logic:

- VW Group: Dual system (fixed + LongLife), conservative fixed interval used
- Mercedes: Service A / Service B rotation
- Ford: EcoBoost-specific petrol intervals
- Electric vehicles: 30,000 km / 24 months (inspection only, no oil change)

### Coverage Analysis: The Three-Tier Matching Pipeline

For Check 5 (component coverage), each line item from the cost estimate goes through a **three-tier matching pipeline**, ordered from fastest/highest-confidence to slowest/lowest-confidence:

**Tier 1: Rule Engine** (confidence = 1.0)
- Deterministic matches: fee items, known exclusions, consumables, fasteners
- Handles patterns like "ENTSORGUNG" (disposal), "ADBLUE" (urea fluid), "MOTOROL" (engine oil)
- Zero ambiguity, zero latency

**Tier 2: Keyword Matcher** (confidence = 0.70-0.90)
- Maps German/French repair terms to component categories
- 30+ category mappings with synonyms: engine, transmission, suspension, brakes, electrical, cooling, etc.
- Umlaut normalization (a/o/u) for robust matching
- Cross-references matched category against the policy's explicit covered/excluded component list

**Tier 3: LLM Fallback** (confidence = 0.60-0.85)
- GPT-4o with structured prompts for ambiguous items
- Concurrency-optimized: 10 parallel calls with Azure rate limiting (900K tokens/min)
- Maximum 35 items per claim to control LLM cost
- Every call audited with token count, cost, and reasoning

**The cascade design matters.** Tier 1 handles 40-50% of items instantly. Tier 2 catches another 30-40%. The LLM only sees the genuinely ambiguous 10-20%. This keeps costs low and latency manageable while maintaining accuracy.

### Payout Calculation

After coverage analysis, the system calculates the payout:

1. Sum covered items (gross)
2. Apply maximum coverage cap (if policy specifies one)
3. Apply mileage-dependent reimbursement rate (40%-100% based on vehicle age/km)
4. Add VAT (8.1% in Switzerland)
5. Calculate deductible (percentage of subtotal, with a minimum floor)
6. Compute final payout

The financial structure follows predictable patterns: standardized deductibles (CHF 150 in 49% of claims), formulaic reimbursement tiers, and verifiable parts/labor splits (60% parts, 40% labor on average).

### Stage 5: QA Console and Human-in-the-Loop Review

A React-based web application provides:

- **Dashboard** with claim-level KPIs, decision distribution, and payout summaries
- **Document review** with split-view: extracted fields on the left, source document on the right
- **Provenance highlighting**: click any extracted field to see exactly where it came from in the source document
- **Three-bucket triage**: Rejected / Needs Review / Approved
- **Labeling interface** with keyboard shortcuts for rapid QA (1/2/3 for label states, n/p for navigation)
- **Coverage reasoning view**: per-line-item coverage decision with match method, confidence, and explanation
- **Assessment comparison**: side-by-side system decision vs. ground truth with error categorization

---

## The Implementation Journey: From 18% to 98%

### Week 1: Baseline and Architecture (Days 1-3)

**Starting accuracy: 18%**

The initial approach sent claim documents to GPT-4o and asked for a decision. The LLM produced plausible-sounding but unreliable results: hallucinated part names, invented coverage rules, and inconsistent financial calculations.

**Key insight:** LLMs are good at language understanding but bad at deterministic business rules. The architecture had to separate what requires judgment (is this part name a synonym for a covered component?) from what requires precision (is the policy valid on this date? does the mileage exceed the limit?).

The decision: build a **hybrid pipeline** where deterministic checks run first and the LLM only handles genuinely ambiguous items.

### Week 1: Screening + Coverage Pipeline (Days 3-5)

**Accuracy: 76% (Day 5)**

Implementing the 11-check screening pipeline and the three-tier coverage matching drove the biggest single improvement. The deterministic checks alone caught most denials correctly, and the keyword matcher handled the majority of coverage lookups.

**Challenge: Multi-language keyword matching.**
German repair terminology uses compound words. A "Abgasruckfuhrungsventil" (exhaust gas recirculation valve) is one word in German. The keyword matcher needed umlaut normalization, compound word decomposition, and synonym mapping across German and French.

We built a configuration-driven vocabulary system: YAML files mapping repair terms to component categories, loaded at runtime from workspace configuration. No hardcoded vocabulary in the core product.

### Week 1-2: Iteration and Refinement (Days 5-7)

**Accuracy: 88% (Day 6) -> 94% (Day 7) -> 98% (Day 8)**

The iteration cycle was tight:
1. Run evaluation against 50 ground-truth claims
2. Categorize every error (false approve, false reject, amount mismatch)
3. Identify the root cause pattern
4. Fix the specific issue (config change, rule addition, or code fix)
5. Re-run evaluation, verify fix and check for regressions

**60+ evaluation iterations** documented in a metrics history file, each tracking:
- Decision accuracy (correct approve + correct deny)
- False reject rate and false approve rate
- Amount accuracy (payout within 5% of ground truth)
- Top error categories with claim-level attribution

The progression from 88% to 98% required solving increasingly subtle problems:

- **Cross-category substring matching bug:** An EGR valve synonym ("abgasrueckfuehrung") contained the substring "asr" (anti-slip regulation, a brake component). The system found "asr" inside "abgasrueckfuehrung" and declared the EGR valve covered under brakes. Fix: symmetric guard requiring exact match when either term is 3 characters or fewer.

- **Labor demotion over-aggression:** When a part was covered, the associated installation labor should also be covered. The system was excluding labor items that couldn't be linked to a specific covered part number. Fix: labor promotion logic that inherits coverage from the parent repair.

- **Part-number normalization:** A Mercedes roof motor part number `A205 906 41 04` existed in the parts database but wasn't matched because of spacing differences in the OCR extraction. Fix: normalize all part numbers by stripping spaces and special characters before lookup.

### The Holdout Test: 77% on Unseen Data

After reaching 98% on the development set (50 claims), we ran a **holdout evaluation** on 30 previously unseen claims.

**Result: 76.7% decision accuracy (23/30 correct)**

The holdout revealed failure modes the development set didn't cover:

1. **Causal exclusion clauses:** A turbocharger is covered by the policy. But if the turbo failed because the engine (not covered) failed first, the policy denies coverage. The system evaluates each component independently; it doesn't reason about failure chains. This requires causal inference that goes beyond component lookup.

2. **Missing documents:** One claim was denied because the policy premium wasn't paid. This information lives in the insurer's internal system, not in any document the system can process. The system correctly referred the claim for human review due to insufficient data.

3. **Sub-component interpretation gaps:** A particulate filter sensor (DPF sensor) is functionally part of the exhaust system. The policy covers the exhaust system but only explicitly lists "catalytic converter" and "oxygen sensor." The system rejected the claim; the human adjuster approved it by interpreting the sensor as an exhaust sub-component.

4. **Excluded-component dominance:** A claim for a hose repair (excluded) was approved because a minor bolt (CHF 3.70, covered) was also on the invoice. The system selected the bolt as the "primary covered repair" and approved. Fix needed: when the highest-value line item is explicitly excluded, the system should flag the claim regardless of minor covered items.

**The holdout gap (98% vs 77%) is the honest measure of generalization.** It revealed that the system was solving the development set well but hadn't encountered the full distribution of real-world edge cases. Each holdout error was analyzed and documented with root cause, fix complexity, and priority.

---

## Technical Challenges and Solutions

### Challenge 1: Customer-Agnostic Core vs. Domain-Specific Configuration

The product had to work for any warranty insurance provider, not just this one.

**Solution: Workspace-based multi-tenant architecture**

The core product (`src/context_builder/`) contains generic pipeline stages, schemas, interfaces, and the matching framework. All customer-specific logic lives in **workspace configuration** loaded at runtime:

| Core Product (Generic) | Customer Config (Domain-Specific) |
|------------------------|-----------------------------------|
| Pipeline orchestration | Extraction specs and prompt templates |
| Coverage analyzer framework | Keyword mappings and component synonyms |
| Rule engine and matching pipeline | Screening checks and business rules |
| API routes, services, storage | Part number databases and assumptions |
| Base Pydantic schemas | Custom extractors for domain-specific document types |

Each workspace is isolated:
```
workspaces/{workspace_id}/
  claims/          # Claims data
  runs/            # Pipeline run logs
  config/          # Customer-specific configuration
    extractors/    # Custom Python extractors
    extraction_specs/  # YAML field specifications
    prompts/       # LLM prompt templates
    coverage/      # Coverage analysis config
    screening/     # Screening rules
```

Configuration files are auto-discovered at runtime using glob patterns (e.g., `*_keyword_mappings.yaml`). Adding a new customer means adding a new workspace directory with the right configuration files. No code changes to the core product.

### Challenge 2: Multi-Language Document Processing

Claims arrive in German, French, and occasionally Italian. The same document type uses different terminology in each language.

**Solution: Language-aware classification and extraction**

- The document type catalog includes classification cues in all supported languages
- Keyword mappings contain German and French synonyms for every repair term category
- Date parsing handles multiple formats: `20.01.2026`, `20/01/2026`, `"20 Janvier 2026"`, `"20. Januar 2026"`
- Number parsing handles Swiss conventions: `3 666,68` (space as thousands separator, comma as decimal)

**Impact:** German and French claims show comparable approval rates (49% vs 54%) with nearly identical average payouts. No measurable language bias in decision accuracy.

### Challenge 3: Cost Estimation at Scale

LLM calls are expensive. A single claim with 30 line items, processed through classification, extraction, and coverage analysis, can consume 40,000+ tokens.

**Solution: Tiered matching with cost controls**

- Rule engine and keyword matcher handle 80-90% of items with zero LLM cost
- LLM calls are capped at 35 items per claim
- Concurrency is optimized: 10 parallel LLM calls with rate limiting
- Every LLM call is logged with token count, model, and cost for ROI tracking
- Quality gates catch extraction failures early, before expensive downstream processing

**Token usage monitoring:** The system tracks token consumption per run with configurable thresholds (warn at 40K, fail at 60K tokens per claim). This prevents runaway costs from pathological documents.

### Challenge 4: Auditability and Compliance

Insurance is a regulated industry. Every automated decision must be traceable and explainable.

**Solution: Full provenance chain and audit logging**

- Every extracted field links to its source (page, character position, extraction method)
- Every coverage decision includes the match method (rule/keyword/LLM), confidence score, and human-readable explanation
- Every screening check records its verdict, evidence, and data sources
- All LLM calls are logged to an audit trail (model, prompt, response, tokens, cost)
- Decision records capture the full reasoning chain from document to verdict

The QA console allows adjusters to trace any decision back to the source document, see exactly which line items were covered or excluded, and understand why.

### Challenge 5: Payout Formula Precision

The payout calculation involves multiple interacting variables: covered amount, coverage cap, reimbursement rate, VAT, deductible percentage, deductible minimum. The **order of operations** matters.

**The bug that taught us:** During deep evaluation, we discovered the system was applying the mileage-dependent reimbursement rate **after** the deductible, while the insurer applies it **before.** This single formula error caused systematic overpayment on all claims with degraded rates (40%-60%).

**Example (40% reimbursement rate):**

| Step | System (Wrong) | Correct |
|------|---------------|---------|
| Gross covered | CHF 1,118.60 | CHF 1,118.60 |
| Apply rate | -- | CHF 447.44 |
| Add VAT (8.1%) | CHF 1,209.21 | CHF 483.69 |
| Deductible | CHF 150.00 | CHF 150.00 |
| Apply rate | CHF 423.68 | -- |
| **Final payout** | **CHF 423.68** | **CHF 333.69** |

A **27% overpayment** from a single operation-order error. This affected 8 of 50 evaluation claims. The fix was a 5-line code change. Finding it required line-by-line financial reconciliation across every mismatched claim.

**Lesson:** In insurance automation, the business logic is harder than the AI. Getting the LLM to classify a turbocharger correctly is one challenge. Getting the payout formula to match the insurer's internal calculation is another. The second one requires working with the actual adjuster, walking through calculations claim by claim.

---

## Results and Metrics

### Evaluation Set (50 Claims)

| Metric | Value |
|--------|-------|
| **Decision accuracy** | **98% (49/50 correct)** |
| Approved claims correctly identified | 25/25 (100%) |
| Denied claims correctly identified | 24/25 (96%) |
| False reject rate | 0% |
| False approve rate | 4% (1 claim) |
| Payout within 5% of ground truth | 28% (7/25 approved) |
| Denial reason match (exact or good) | 72% (18/25 denied) |

### Holdout Set (30 Unseen Claims)

| Metric | Value |
|--------|-------|
| **Decision accuracy** | **76.7% (23/30 correct)** |
| Approved claims correctly identified | 11/15 |
| Denied claims correctly identified | 12/15 |
| False reject rate | 26.7% |
| False approve rate | 20.0% |

### Error Distribution

| Error Type | Eval Set | Holdout |
|------------|----------|---------|
| False approve (should deny, approved) | 1 | 2 |
| False reject (should approve, denied) | 0 | 3 |
| Referral errors (REFER instead of decide) | 0 | 2 |
| Amount mismatch (correct decision, wrong payout) | 18 | 8 |

### Processing Characteristics

| Metric | Value |
|--------|-------|
| Document types supported | 14 |
| Vehicle brands in service interval DB | 18 |
| Screening checks | 11 deterministic |
| Coverage matching tiers | 3 (rules, keywords, LLM) |
| Keyword mapping categories | 30+ |
| Extraction fields (warranty policy) | 51 |
| Languages supported | German, French, Italian |
| Test suite | 850+ unit tests |

---

## What We Learned

### 1. Deterministic checks beat LLM judgment for structured rules.

76% of claim denials are "part not covered." This is a lookup, not a judgment call. The screening pipeline handles these with 100% confidence and zero LLM cost. Reserve the LLM for genuinely ambiguous cases.

### 2. The accuracy curve has diminishing returns.

Going from 18% to 76% took 3 days. Going from 76% to 98% took 4 more days. Each subsequent percentage point required deeper investigation, subtler fixes, and more edge case handling. The holdout gap (98% vs 77%) confirmed that real-world generalization requires significantly more data and iteration.

### 3. The payout formula is harder than the AI.

Getting the LLM to classify parts correctly is table stakes. Getting the financial calculation to match the insurer's exact formula requires sitting with an adjuster and walking through calculations by hand. No amount of prompt engineering solves an order-of-operations bug in business logic.

### 4. Provenance tracking is non-negotiable.

In a regulated industry, "the AI said so" is not an acceptable audit trail. Every extracted value, every coverage decision, and every screening verdict must trace back to a source document, page, and character position. This adds engineering complexity but is fundamental to trust and compliance.

### 5. Customer-agnostic architecture pays for itself immediately.

Separating the core product from customer-specific configuration meant that adding document types, keyword mappings, and screening rules required zero code changes to the product. The entire customer integration was done through YAML configuration files and custom extractor plugins.

### 6. Ground truth is the foundation of everything.

Without 50 manually verified claim decisions (with itemized payouts, coverage notes, and denial reasons), there would be no way to measure progress, identify bugs, or validate fixes. Building the ground truth dataset was the single highest-ROI investment in the project.

---

## Next Steps

The system is in active development with a clear path forward:

1. **Expand the ground truth dataset** beyond 80 claims to improve generalization
2. **Integrate with the insurer's policy management API** for real-time policy status checks
3. **Implement causal exclusion reasoning** for cascading-damage denial patterns
4. **Build a self-service configuration portal** for adjusters to update keyword mappings and coverage rules without developer involvement
5. **Deploy production triage workflow**: auto-reject high-confidence denials, auto-approve simple approvals, route edge cases for human review

The goal is not to replace adjusters. The goal is to give them back their time on the 76% of denials that are straightforward lookups, so they can focus their expertise on the 24% that actually require judgment.

---

*Built with [ContextBuilder](https://github.com/Fr3nn3r/AgenticContextBuilder) - an open-source insurance claims document processing pipeline.*

**Tech stack:** Python 3.9+ / FastAPI / Pydantic / React 18 / TypeScript / Tailwind CSS / OpenAI GPT-4o / Azure Document Intelligence

**Keywords:** intelligent document processing, IDP, insurance claims automation, warranty claims processing, document classification, structured data extraction, coverage analysis, claims screening, payout calculation, OCR pipeline, multi-language NLP, German French document processing, provenance tracking, quality gates, confidence scoring, human-in-the-loop, LLM integration, GPT-4o, Azure Document Intelligence, vehicle warranty insurance, motor guarantee, component coverage matching, keyword matching, rule engine, deterministic screening, hybrid AI architecture, claims triage, audit logging, compliance, multi-tenant architecture, workspace isolation, field extraction, cost estimate processing, line item analysis, deductible calculation, reimbursement tiers, Pydantic, FastAPI, React, TypeScript, file-based storage, JSONL indexing
