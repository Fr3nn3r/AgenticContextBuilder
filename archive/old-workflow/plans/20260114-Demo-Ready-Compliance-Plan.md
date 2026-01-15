# Demo-Ready Compliance Plan

## Goal
Prepare a stakeholder demo that showcases compliance capabilities while being defensible on security questions.

## Recommended Approach
**UI Demo Plan** + **Quick Backend Hardening** (from my review)

---

# Part 1: Backend Assessment (Reference)

## Executive Summary

The team has built a **solid foundation** for compliance but there are **critical gaps** that need attention before this can be trusted for production audits. The "audit-first minimum" from your requirements is approximately **60% complete**.

| "Audit-First Minimum" Requirement | Status | Trust Level |
|-----------------------------------|--------|-------------|
| 1. Append-only, tamper-evident ledger | ✅ Complete | HIGH |
| 2. Version pinning (model/prompt/rules/config) | ⚠️ Partial | MEDIUM |
| 3. Evidence provenance + RAG context capture | ⚠️ Partial | MEDIUM |
| 4. Human override capture with accountability | ✅ Complete | HIGH |
| 5. Replay/reconstruction mechanism | ⚠️ Partial | LOW |
| 6. Exportable evidence packs + queryability | ❌ Missing | NONE |

---

## Detailed Assessment by Requirement Category

### 1. CAPTURE REQUIREMENTS (Req 1-5)

| Requirement | Status | Details |
|-------------|--------|---------|
| Universal decision coverage | ✅ | Classifications, extractions, quality gates, human reviews, overrides all logged |
| Standard decision record schema | ✅ | `DecisionRecord` schema is comprehensive and consistent |
| Inputs + evidence pointers | ⚠️ | MD5 hashes captured; source metadata (origin, ingestion method) missing |
| Output completeness | ⚠️ | Results stored; alternatives/candidates not captured |
| AI context capture | ⚠️ | LLM calls logged excellently (95%); RAG/retrieved context NOT logged separately |

**What works well:**
- `LLMCallRecord` captures: model, temperature, max_tokens, full messages array, token usage, latency, retry tracking
- `AuditedOpenAIClient` auto-logs all OpenAI calls with context (claim_id, doc_id, run_id)
- Field-level provenance with page references and text quotes

**Critical gap:**
- **RAG context not logged** - Classification builds "cue snippets" but they're not stored as evidence artifacts. You cannot prove "what context was provided to the LLM" at decision time.

---

### 2. REPRODUCIBILITY & REPLAY (Req 6-9)

| Requirement | Status | Details |
|-------------|--------|---------|
| Replayable decision reconstruction | ⚠️ | Metadata captured; exact replay not implemented or verified |
| Time semantics (event/decision/effective) | ❌ | Only `created_at` captured; no separation of event vs decision time |
| Version pinning for everything | ⚠️ | Schema exists; **hashes not computed** |
| Change impact traceability | ❌ | Not implemented |

**Critical gaps:**
1. **`prompt_template_hash` field exists but is NOT populated** - Cannot verify exact prompt version used
2. **`extraction_spec_hash` field exists but is NOT populated** - Cannot verify exact extraction specs
3. **No replay testing mechanism** - Cannot verify "would this produce the same result?"

**Code location:** `src/context_builder/storage/version_bundles.py` - hash computation methods exist but are incomplete

---

### 3. INTEGRITY & NON-REPUDIATION (Req 10-13)

| Requirement | Status | Details |
|-------------|--------|---------|
| Append-only semantics | ✅ | JSONL with atomic writes (temp-file-rename pattern) |
| Tamper evidence | ✅ | SHA-256 hash chain with `previous_hash` linking |
| Chain-of-custody for evidence | ⚠️ | Hashes captured; origin/transformation history missing |
| Idempotency and deduplication | ❌ | **NOT IMPLEMENTED - CRITICAL** |

**What works well:**
- `FileDecisionAppender` implements proper hash chain
- `verify_integrity()` validates entire chain
- AES-256-GCM encryption code exists in `crypto.py`

**Critical gap:**
- **No idempotency protection** - If a classification is retried due to timeout, both attempts log as separate decisions. This corrupts the audit trail.

---

### 4. HUMAN OVERSIGHT (Req 14-16)

| Requirement | Status | Details |
|-------------|--------|---------|
| Human actions as first-class events | ✅ | `HUMAN_REVIEW` and `OVERRIDE` decision types logged |
| Override accountability | ✅ | `actor_id`, `actor_type`, `override_reason` captured |
| Decision responsibility model | ❌ | Not implemented |

**What works well:**
- `LabelsService.save_labels()` creates compliance records for every human review
- Override value, reason, and actor all captured
- Timestamps preserved

**Minor gap:**
- Original extraction value not snapshotted alongside override (no before/after comparison)

---

### 5. EXPLAINABILITY (Req 17-18)

| Requirement | Status | Details |
|-------------|--------|---------|
| Traceable rationale | ⚠️ | `DecisionRationale` exists; `rule_traces` rarely populated |
| Audience-specific views | ❌ | Not implemented |

**Gap:** Rule traces are optional and mostly empty. The rationale is high-level summary only.

---

### 6. PRIVACY & DATA PROTECTION (Req 19-23)

| Requirement | Status | Details |
|-------------|--------|---------|
| Data minimization | ⚠️ | Some attention; no retention policies |
| PII separation strategy | ❌ | `PIIReference` stub exists; vault NOT implemented |
| Encryption everywhere | ❌ | **Code exists but NOT integrated** - all data in plaintext |
| Retention + legal hold | ❌ | Not implemented |
| Right-to-erasure | ❌ | Not implemented |

**Critical gap:**
- **Encryption NOT in use** - `EnvelopeEncryptor` class exists with proper AES-256-GCM but `EncryptedDecisionStorage` is not connected to the API. All decision records and LLM logs stored as plaintext JSONL.

---

### 7. ACCESS CONTROL (Req 24-26)

| Requirement | Status | Details |
|-------------|--------|---------|
| Least-privilege access control | ❌ | Roles defined (admin/reviewer/operator/auditor) but **NOT enforced** |
| Access logging | ⚠️ | Audit log exists for pipeline ops; compliance endpoint access NOT logged |
| Segregation of duties | ❌ | Not implemented |

**Critical gap:**
- Anyone can access `/api/compliance/ledger/decisions` regardless of role

---

### 8. OPERATIONAL RESILIENCE (Req 27-29)

| Requirement | Status | Details |
|-------------|--------|---------|
| High availability + durability | ⚠️ | File-based; no multi-zone/backup strategy |
| Disaster recovery | ❌ | Not defined |
| Incident readiness | ⚠️ | Hash chain verification exists; no anomaly detection |

---

### 9. INTEROPERABILITY & EXPORT (Req 30-32)

| Requirement | Status | Details |
|-------------|--------|---------|
| Queryability at scale | ⚠️ | Basic filters work; no aggregates or complex queries |
| Exportable evidence packs | ❌ | **NOT IMPLEMENTED** - explicitly out of scope in plan |
| API-first integration | ✅ | Endpoints exist and work |

**Critical gap:**
- **No export functionality at all** - Cannot generate audit reports, evidence packs, or bulk exports for regulators

---

### 10. GOVERNANCE (Req 33-35)

| Requirement | Status | Details |
|-------------|--------|---------|
| Control mapping | ❌ | Not implemented |
| Policy-as-data lifecycle | ⚠️ | Version bundles exist; approval/rollback not implemented |
| Testing evidence linkage | ❌ | Not implemented |

---

## Summary Scorecard

### By Implementation Quality

| Category | Completeness | Trust Level |
|----------|--------------|-------------|
| Decision logging | 90% | HIGH - can trust |
| Hash chain integrity | 95% | HIGH - can trust |
| LLM call auditing | 95% | HIGH - can trust |
| Human override capture | 85% | HIGH - can trust |
| Version bundle schema | 70% | MEDIUM - schema good, enforcement weak |
| Evidence provenance | 50% | MEDIUM - hashes yes, metadata no |
| RAG context capture | 20% | LOW - not logged separately |
| Reproducibility | 40% | LOW - hashes not computed |
| Idempotency | 0% | CRITICAL GAP |
| Encryption at rest | 5% | CRITICAL GAP - code exists, not used |
| Access control enforcement | 10% | CRITICAL GAP |
| Export functionality | 0% | CRITICAL GAP |
| PII handling | 5% | CRITICAL GAP |

### MUST Fix Before Production

1. **Idempotency** - Add idempotency tokens to prevent duplicate decision logging
2. **Encryption integration** - Connect `EncryptedDecisionStorage` to API
3. **Access control enforcement** - Apply role checks to compliance endpoints
4. **Version hash computation** - Actually compute `prompt_template_hash` and `extraction_spec_hash`

### SHOULD Fix for Compliance

5. **Export evidence packs** - Add endpoint to export decisions/evidence as JSON/CSV
6. **RAG context logging** - Store retrieved context snippets as evidence artifacts
7. **Access logging on compliance endpoints** - Log who queries the audit trail
8. **Time semantics** - Separate event_time vs decision_time

---

## Files to Review

| Purpose | File Path |
|---------|-----------|
| Decision record schema | `src/context_builder/schemas/decision_record.py` |
| File storage (append-only) | `src/context_builder/services/compliance/file/decision_storage.py` |
| Encryption (unused) | `src/context_builder/services/compliance/crypto.py` |
| Encrypted storage (stub) | `src/context_builder/services/compliance/encrypted/decision_storage.py` |
| LLM audit logging | `src/context_builder/services/llm_audit.py` |
| Version bundles | `src/context_builder/storage/version_bundles.py` |
| API endpoints | `src/context_builder/api/main.py` (lines ~200-300) |
| Human review logging | `src/context_builder/api/services/labels.py` |

---

---

# Prioritized Fix Plan (Production Reference)

## Priority 1: Critical Compliance Blockers

### 1.1 Add Idempotency Protection (Est. effort: Small)

**Problem:** Retries can create duplicate decision records, corrupting the audit trail.

**Fix:**
- Add `idempotency_key` field to `DecisionRecord` schema
- Check for existing records with same key before appending
- Generate idempotency key from: `{claim_id}_{doc_id}_{decision_type}_{content_hash}`

**Files to modify:**
- `src/context_builder/schemas/decision_record.py` - Add field
- `src/context_builder/services/compliance/file/decision_storage.py` - Add dedup check in `append()`
- `src/context_builder/services/compliance/encrypted/decision_storage.py` - Same

**Verification:** Unit test that appending same decision twice returns existing record.

---

### 1.2 Enable Encryption for Production (Est. effort: Small)

**Problem:** Encryption code exists but is NOT enabled by default.

**Current state:**
- `EncryptedDecisionStorage` is fully implemented
- Factory supports `ENCRYPTED_FILE` backend
- Default is plaintext `FILE`

**Fix:**
- Document how to enable encryption via env vars
- Add production config example with `COMPLIANCE_BACKEND_TYPE=encrypted_file`
- Generate and store a KEK for production use

**Required env vars for production:**
```bash
COMPLIANCE_BACKEND_TYPE=encrypted_file
COMPLIANCE_ENCRYPTION_KEY_PATH=/secure/path/to/master.key
```

**Files to modify:**
- None (code exists) - just configuration/documentation

**Verification:** Set env vars, restart API, verify decisions are encrypted in storage file.

---

### 1.3 Enforce Access Control on Compliance Endpoints (Est. effort: Medium)

**Problem:** Roles defined but compliance endpoints have no RBAC checks.

**Fix:**
- Add `require_role()` dependency to compliance endpoints
- Only `admin` and `auditor` should access `/api/compliance/*`
- Add endpoint-level access logging

**Files to modify:**
- `src/context_builder/api/main.py` - Add role dependencies to compliance routes
- `src/context_builder/api/services/auth.py` - Add access logging

**Verification:** Test that `reviewer` role gets 403 on compliance endpoints.

---

## Priority 2: Compliance Requirements Completion

### 2.1 Fix Version Hash Computation (Est. effort: Small)

**Problem:** `prompt_template_hash` and `extraction_spec_hash` return `None` due to path issues.

**Current state:** Code exists in `version_bundles.py` but paths don't resolve correctly at runtime.

**Fix:**
- Use `Path(__file__).parent.parent / "prompts"` as primary path (relative to module)
- Add logging when hash computation fails
- Verify hashes are populated in stored bundles

**Files to modify:**
- `src/context_builder/storage/version_bundles.py` - Fix path resolution

**Verification:** Create version bundle, check that hashes are non-null in bundle.json.

---

### 2.2 Log RAG Context as Evidence (Est. effort: Medium)

**Problem:** Classification builds "cue snippets" but doesn't store them as evidence.

**Fix:**
- Add `retrieved_context` field to `LLMCallRecord`
- Capture cue snippets in classification context builder
- Store as separate evidence artifact linked to decision

**Files to modify:**
- `src/context_builder/schemas/llm_call_record.py` - Add field
- `src/context_builder/classification/openai_classifier.py` - Capture context
- `src/context_builder/services/llm_audit.py` - Pass context to record

**Verification:** Query LLM calls for a classification, verify `retrieved_context` populated.

---

### 2.3 Add Export Evidence Pack Endpoint (Est. effort: Medium)

**Problem:** No way to export audit trail for regulators.

**Fix:**
- Add `GET /api/compliance/export/{claim_id}` endpoint
- Return JSON with: decisions, version bundles, LLM calls, evidence citations
- Support optional CSV format via Accept header

**Files to modify:**
- `src/context_builder/api/main.py` - Add export endpoint
- `src/context_builder/api/schemas/` - Add export response schema

**Verification:** Call endpoint with claim_id, verify complete evidence pack returned.

---

### 2.4 Add Access Logging for Compliance Endpoints (Est. effort: Small)

**Problem:** No record of who accessed audit data.

**Fix:**
- Log every request to `/api/compliance/*` endpoints
- Include: user_id, endpoint, query params, timestamp
- Store in separate access audit log

**Files to modify:**
- `src/context_builder/api/main.py` - Add middleware or dependency
- `src/context_builder/api/services/audit.py` - Add access log method

**Verification:** Query compliance endpoint, verify access logged.

---

## Priority 3: Future Enhancements (Nice to Have)

| Enhancement | Effort | Notes |
|-------------|--------|-------|
| Time semantics (event_time vs decision_time) | Small | Add fields to DecisionRecord |
| Retention policies | Medium | Add TTL and purge mechanism |
| PII vault separation | Large | Requires additional storage layer |
| Merkle tree structure | Medium | For efficient partial verification |
| Database backend | Large | For queryable compliance at scale |

---

## Testing Checklist (Production)

- [ ] Idempotency: Duplicate decision append returns existing record
- [ ] Encryption: Decisions encrypted at rest when env var set
- [ ] Access control: Non-auditor gets 403 on compliance endpoints
- [ ] Version hashes: Bundle contains non-null prompt/spec hashes
- [ ] RAG context: LLM calls contain retrieved_context field
- [ ] Export: Evidence pack contains all linked artifacts
- [ ] Access logging: Compliance endpoint access creates audit entry

---

# Part 2: Demo-Ready Implementation Plan

## Phase 0: Quick Backend Hardening (1-2 days)

**Goal:** Make the demo defensible if stakeholders ask security questions.

### 0.1 Enable Encryption (2 hours)
- Generate a master key: `python -c "from context_builder.services.compliance.crypto import generate_key_file; from pathlib import Path; generate_key_file(Path('keys/master.key'))"`
- Set env vars:
  ```bash
  COMPLIANCE_BACKEND_TYPE=encrypted_file
  COMPLIANCE_ENCRYPTION_KEY_PATH=keys/master.key
  ```
- **Demo talking point:** "All audit records are encrypted at rest with AES-256-GCM"

### 0.2 Add Role Check to Compliance Endpoints (2-4 hours)
- Add `require_role(["admin", "auditor"])` dependency to `/api/compliance/*` routes
- **Demo talking point:** "Only auditors can access the compliance ledger"

**Files:** `src/context_builder/api/main.py`

### 0.3 Fix Version Hash Paths (1-2 hours)
- Fix path resolution in `version_bundles.py` so `prompt_template_hash` is populated
- **Demo talking point:** "Every decision links to the exact prompt version used"

**Files:** `src/context_builder/storage/version_bundles.py`

---

## Phase A: UI Skeleton (1-2 days)

Add compliance nav section and stub pages:

| Route | Purpose |
|-------|---------|
| `/compliance/overview` | Dashboard with status cards |
| `/compliance/ledger` | Decision list with filters |
| `/compliance/ledger/:id` | Decision detail view |
| `/compliance/verification` | Hash chain integrity check |
| `/compliance/version-bundles` | Version bundle list |
| `/compliance/controls` | Control framework mapping |

**Files to create:**
- `ui/src/pages/compliance/Overview.tsx`
- `ui/src/pages/compliance/Ledger.tsx`
- `ui/src/pages/compliance/DecisionDetail.tsx`
- `ui/src/pages/compliance/Verification.tsx`
- `ui/src/pages/compliance/VersionBundles.tsx`
- `ui/src/pages/compliance/Controls.tsx`
- `ui/src/components/compliance/` (shared components)

---

## Phase B: Wire to APIs (2-3 days)

Connect UI to existing endpoints:

| UI Component | API Endpoint |
|--------------|--------------|
| Overview cards | `/api/compliance/ledger/verify`, `/api/compliance/ledger/decisions` |
| Ledger list | `/api/compliance/ledger/decisions` with filters |
| Decision detail | `/api/compliance/ledger/decisions?decision_id=X` |
| Verification | `/api/compliance/ledger/verify` |
| Version bundles | `/api/compliance/version-bundles`, `/api/compliance/version-bundles/{run_id}` |

**Hooks to create:**
- `ui/src/hooks/useComplianceApi.ts`
- `ui/src/api/compliance.ts`

---

## Phase C: Decision Detail UX (2-3 days)

Build tabbed decision detail page:

| Tab | Content |
|-----|---------|
| Summary | decision_type, outcome, confidence, timestamps |
| Rationale | summary, rule_traces, evidence_citations |
| Evidence | Input refs, doc links, provenance |
| Versions | version_bundle details |
| Human Actions | overrides, reviewer, reason |

---

## Phase D: Demo Polish (1-2 days)

### Verification Center
- Show hash chain status with visual indicator (green checkmark)
- Display last verified timestamp
- Button to re-run verification

### Export UX (Stubbed)
- Button with "Export Evidence Pack"
- Checklist showing what would be included
- Tooltip: "Coming soon - export to JSON/CSV/PDF"

### Control Mapping Page
- Map "Audit-First Minimum" to specific UI screens
- Provide one-page "What auditors can verify" narrative

---

## Demo Script

1. **Overview Dashboard** - "Here's our compliance posture at a glance"
2. **Verification Center** - "Click to verify hash chain integrity - tamper-evident"
3. **Decision Ledger** - "Every AI decision is logged with full context"
4. **Decision Detail** - "Drill into any decision - see rationale, evidence, versions"
5. **Version Bundles** - "We track exact model/prompt versions for reproducibility"
6. **Controls Page** - "How we map to compliance frameworks"

**If asked about security:**
- "Audit records encrypted at rest with AES-256-GCM"
- "Role-based access - only auditors see this data"
- "Hash chain ensures tamper evidence"

---

## Timeline

| Phase | Duration | Output |
|-------|----------|--------|
| Phase 0 | 1-2 days | Backend defensible |
| Phase A | 1-2 days | UI routes + stubs |
| Phase B | 2-3 days | Live data in UI |
| Phase C | 2-3 days | Decision detail complete |
| Phase D | 1-2 days | Demo polish |
| **Total** | **7-12 days** | **Demo-ready** |

---

## What to Defer (Post-Demo)

- Idempotency protection (production requirement)
- RAG context logging (production requirement)
- Export endpoint implementation (stub is fine for demo)
- PII vault (adoption plan Phase 1)
- Access logging (production requirement)
