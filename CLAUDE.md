# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# IMPORTANT
- never EVER take action unless the User explicitly tells you to.
- never EVER make assumptions -> ask questions.
- Read PROJECT_CONTEXT.md for project context.

## Development Guidelines

### Coding Standards: SOLID principles of software design
- **S – Single Responsibility Principle (SRP)**: A class should have one job only. Each class should have a single reason to change.
- **O –Open/Closed Principle (OCP)**: Code should be open for extension, closed for modification. We can new features without rewriting existing code.
- **L – Liskov Substitution Principle (LSP)**: A child class should respect the contract of the parent.
- **I – Interface Segregation Principle (ISP)**: Don’t force classes to implement methods they don’t need. Better to have many small, specific interfaces than one fat, do-everything interface.
- **D – Dependency Inversion Principle (DIP)**: Depend on abstractions (interfaces), not concrete implementations. High-level modules shouldn’t depend on low-level details. Both should depend on interfaces/contracts.

### What “good” looks like
High cohesion per file (one purpose), low coupling across files.
Functions ≤50–80 lines, files typically ≤200–400 lines.
Cross-cutting concerns (OpenAI calls, JSON cleaning, PDF page rendering, OCR) in small reusable modules.
Lazy imports for heavy deps (e.g., pdfium, PIL, pandas) in their specific modules/paths.

### Naming standards
1) Name by purpose, not by type or mechanics
  Bad: data, result, list1
  Good: pendingClaims, approvedInvoices, customerLookup
  Tip: Start names with a strong noun/verb: loadPolicies, issueRefund, riskScore.
2) Match scope → specificity
  Tiny/local var in 3 lines? i, row, sum is fine.
  Public API/class? Use full, precise names: ClaimDocumentClassifier, PaymentAuthorizationService.
3) Use domain language consistently
  Pick one term and stick to it: claimant or insured (not both).
  Prefer business terms over tech mush: policyLapseDate > expiryTs.
4) Encode meaning, not metadata
  Don’t add types: customerListArr ❌
  Do add units/context: timeoutMs, premiumCHF, createdAtUtc.
5) Boolean names read like statements
  isEligible, hasConsent, shouldRetry, canSettle.
  Avoid negatives of negatives: prefer isActive over isNotInactive.
6) Plurals and collections
  Singular for one, plural for many: claim, claims.
  For maps, say what’s keyed by what: claimsByCustomerId, ratesByCountry.
7) Avoid abbreviations unless they’re truly common
  Good: id, URL, CPU.
  Risky: cfg, pol, cust. If you must abbreviate, document once in the README or glossary.
8) Keep length as short as possible, as long as necessary
  calculateMonthlyPremium() ✔
  calculateMonthlyPremiumForHouseholdInSwissFrancs() ❌ (push details to parameters).
9) Be consistent with language conventions
  Python: snake_case for functions/vars, PascalCase for classes, UPPER_SNAKE for constants.
  JS/TS: camelCase vars/functions, PascalCase classes/components, SCREAMING_SNAKE constants.
  Java/C#: camelCase fields/params, PascalCase classes/methods.
  Files/folders follow the same story as symbols.
10) Functions: verb + object (+ qualifier)
  loadPolicy(), issueRefund(), recalculateRiskScore().
  Pure getters/setters: getPolicy(), setStatus(); booleans: isSettled().
11) Classes and modules: what they are
  ClaimValidator, PolicyRepository, PremiumCalculator, PaymentGatewayClient.
  Avoid Manager, Processor, Helper unless you truly can’t be more specific.
12) Events and handlers
  Events: past tense or noun: ClaimSubmitted, PaymentAuthorized.
  Handlers: onClaimSubmitted, handlePaymentAuthorized.
13) Error/exception names say the reason
  InvalidPolicyNumberError, InsufficientCoverageError, ConsentMissingError.
14) Migrations/feature flags
  Migrations: 2025_09_20_add_claim_index.
  Flags: ff_enableSmartTriage (with owner, expiry date in code comment).

### Anti-Complexity Philosophy
- BE VERY SUSPICIOUS OF EVERY COMPLICATION - simple = good, complex = bad
- Do exactly what's asked, nothing more
- Execute precisely what the user asks for, without additional features
- Constantly verify you're not adding anything beyond explicit instructions

### Communication Style
- Use simple & easy-to-understand language. write in short sentences
- Be CLEAR and STRAIGHT TO THE POINT
- EXPLAIN EVERYTHING CLEARLY & COMPLETELY
- Address ALL of user's points and questions clearly and completely.

### Misc
Prefer ASCII-only CLI output by default: use “[OK]”/“[X]” instead of ✓/✗ for cross-platform safety.
Use folder `scripts` to store temporary test scripts

### Minimal Comment Policy
1. Explain why, not what: Don’t repeat code in English, explain intent, business rules, or trade-offs
e.g. # Business rule: claims older than 2 years cannot be reopened
2. Document assumptions and edge cases
e.g. # Assumes travel insurance IDs are globally unique (not just per country)
3. Mark todos and decisions explicitly
e.g. // TODO: Replace with real OCR once accuracy >95%
4. Public APIs / Interfaces need a docstring
  Functions, classes, and modules exposed to other devs must explain:
    What it does
    Parameters (specifying units)
    Return value / side effects (exceptions)
5. Comment “why not” when code looks weird
e.g. # Using regex instead of JSON parser because input is malformed in legacy system
6. Keep comments close and current
  Outdated comments are worse than none
  If code changes, update or delete the comment

# IMPORTANT
- never EVER take action unless the User explicitly tells you to.
- never EVER make assumptions -> ask questions.
- Read PROJECT_CONTEXT.md for project context.