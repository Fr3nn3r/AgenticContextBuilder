# Compliance Foundation Priorities

## The Problem: Technical Debt That Can't Be Fixed Later

Some architectural decisions, if made wrong now, create **irreversible technical debt**. You can't retrofit these without:
- Migrating all existing data
- Breaking existing integrations
- Losing historical audit trail integrity
- Massive refactoring of core data flows

This document identifies **what must be built correctly from the start**.

---

## PRIORITY 1: Immutable Decision Ledger Schema (CRITICAL)

### Why Now?
If you add logging piecemeal across different features, you get:
- Inconsistent record formats
- Missing fields that can never be backfilled
- No way to query across decision types
- Audit failures due to incomplete records

### What to Lock Down Now

**Single unified schema for ALL decisions:**

```python
@dataclass
class DecisionRecord:
    # Identity
    decision_id: str          # UUID, immutable
    decision_type: str        # classification, extraction, quality_gate, human_review, override

    # Context references (NEVER store PII here - only refs)
    claim_id: str
    doc_id: str

    # Timestamps (all three required from day 1)
    event_time: str           # When the underlying event occurred
    decision_time: str        # When this decision was made
    recorded_time: str        # When this record was written (for replication)

    # Actor (system or human)
    actor_type: str           # "system" | "human"
    actor_identity: str       # model_id or user_id
    actor_role: str           # For humans: their role at decision time

    # Version bundle (CRITICAL - must capture at decision time)
    version_bundle: VersionBundle

    # Input references (not values - refs to immutable artifacts)
    input_refs: List[str]     # Content-addressed refs to inputs used

    # Output
    decision_output: Any      # The actual decision/value
    confidence: float | None  # If applicable
    alternatives: List[Any]   # Other options considered (for explainability)

    # Rationale (machine-readable)
    rationale: DecisionRationale

    # Integrity (added at write time)
    record_hash: str          # SHA-256 of this record
    previous_hash: str        # Hash of previous record (chain)

@dataclass
class VersionBundle:
    """Snapshot of ALL versions at decision time - CANNOT be reconstructed later"""
    code_version: str         # Git SHA
    model_id: str             # e.g., "gpt-4o-2024-05-13"
    prompt_version: str       # Hash or ID of prompt template
    config_version: str       # Hash of extraction config
    rules_version: str        # Hash of business rules
    schema_version: str       # Version of this schema itself

@dataclass
class DecisionRationale:
    rule_trace: List[str]     # Which rules fired
    evidence_citations: List[EvidenceCitation]  # What evidence was used
    explanation: str          # Human-readable summary
```

### Refactoring Cost If Skipped
- **HIGH**: Every existing logging call must be updated
- All historical records lack version_bundle - can never prove what version made them
- No hash chain means existing records can't be verified

---

## PRIORITY 2: Hash Chaining From Record #1 (CRITICAL)

### Why Now?
If you add tamper-evidence later:
- Existing records have no hashes - they're unverifiable forever
- You can't prove they weren't modified before hashing started
- Auditors will flag the gap period as non-compliant

### What to Implement Now

**Every append to the ledger must:**
1. Compute SHA-256 hash of the new record
2. Include hash of previous record in the new record
3. Write atomically (record + hash together)

```python
def append_decision(record: DecisionRecord, ledger_path: Path) -> str:
    # Get previous hash
    previous_hash = get_last_hash(ledger_path) or "GENESIS"

    # Set chain link
    record.previous_hash = previous_hash

    # Compute record hash (excluding the hash field itself)
    record_hash = compute_hash(record)
    record.record_hash = record_hash

    # Append atomically
    append_atomic(ledger_path, record)

    return record_hash
```

### Verification Function (needed for auditors)
```python
def verify_chain_integrity(ledger_path: Path) -> IntegrityReport:
    """Verify no records were modified or deleted"""
    records = read_all_records(ledger_path)

    expected_prev = "GENESIS"
    for i, record in enumerate(records):
        # Verify chain link
        if record.previous_hash != expected_prev:
            return IntegrityReport(valid=False, break_at=i, reason="chain_break")

        # Verify record hash
        computed = compute_hash(record, exclude=['record_hash'])
        if computed != record.record_hash:
            return IntegrityReport(valid=False, break_at=i, reason="hash_mismatch")

        expected_prev = record.record_hash

    return IntegrityReport(valid=True, record_count=len(records))
```

### Refactoring Cost If Skipped
- **IMPOSSIBLE TO FIX**: Records written without hashes can never be verified
- Must start new ledger and explain gap to auditors

---

## PRIORITY 3: PII Reference Architecture (CRITICAL)

### Why Now?
If PII is stored directly in the decision ledger:
- GDPR erasure requests require modifying "immutable" records
- You break integrity guarantees when you redact
- Separating later requires migrating ALL historical data
- Risk of PII leaking into exports, logs, error messages

### What to Implement Now

**Never store PII values in the ledger. Store references only.**

```python
# BAD - PII in ledger (can't erase without breaking integrity)
decision_record = {
    "claimant_name": "John Smith",      # PII!
    "policy_number": "POL-123456",      # PII!
    "extracted_ssn": "123-45-6789"      # PII!
}

# GOOD - References only (can erase PII without touching ledger)
decision_record = {
    "claimant_ref": "pii:person:a1b2c3",  # Reference to PII vault
    "policy_ref": "pii:policy:d4e5f6",     # Reference to PII vault
    "extracted_fields_ref": "pii:extract:g7h8i9"  # Reference to PII vault
}
```

**PII Vault Structure:**
```
output/
  pii_vault/
    persons/
      {person_id}.json.enc    # Encrypted, deletable
    policies/
      {policy_id}.json.enc
    extractions/
      {extraction_id}.json.enc

  decision_ledger/
    ledger.jsonl              # NO PII - only refs
```

### Erasure Without Breaking Integrity
```python
def handle_erasure_request(person_id: str):
    # Delete the PII (or delete encryption key)
    delete_pii_record(f"pii_vault/persons/{person_id}.json.enc")

    # Ledger remains intact - refs now point to deleted data
    # This is GDPR-compliant: data is erased, audit trail preserved

    # Log the erasure action (required)
    append_decision(DecisionRecord(
        decision_type="pii_erasure",
        actor_type="system",
        decision_output={"erased_ref": person_id, "reason": "gdpr_request"}
    ))
```

### Refactoring Cost If Skipped
- **EXTREME**: Must scan ALL records for PII
- Must create migration mapping (old value -> new ref)
- Risk of missing PII in nested fields
- Historical exports may have leaked PII - can't recall

---

## PRIORITY 4: LLM Call Capture At Invocation Time (HIGH)

### Why Now?
LLM calls are ephemeral. If you don't capture them at invocation:
- Prompts are lost forever
- RAG context can't be reconstructed
- Can't explain why model produced an output
- Can't replay or debug

### What to Implement Now

**Wrap every LLM call:**

```python
@dataclass
class LLMCallRecord:
    call_id: str              # UUID
    timestamp: str

    # Model details
    model_id: str             # "gpt-4o-2024-05-13"
    provider: str             # "openai" | "azure" | "anthropic"

    # Parameters (reproducibility)
    temperature: float
    max_tokens: int
    top_p: float

    # Prompts (FULL capture)
    system_prompt: str
    user_prompt: str
    tool_definitions: List[dict]  # If using function calling

    # RAG context (CRITICAL - can't reconstruct later)
    retrieved_context: List[RetrievedChunk]

    # Response
    response_content: str
    tool_calls: List[dict]    # If model called tools

    # Metadata
    token_usage: TokenUsage
    latency_ms: int

    # Link to decision
    decision_id: str          # Which decision this call supported

@dataclass
class RetrievedChunk:
    source_ref: str           # Reference to source document
    chunk_text: str           # Exact text provided to model
    relevance_score: float    # Why this chunk was selected
```

**Integration point:**
```python
# Wrap your existing LLM client
class AuditedLLMClient:
    def __init__(self, client, llm_log_path: Path):
        self.client = client
        self.log_path = llm_log_path

    def chat_completion(self, messages, **kwargs) -> tuple[Response, str]:
        # Capture before
        call_record = LLMCallRecord(
            call_id=str(uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            model_id=kwargs.get('model'),
            system_prompt=extract_system(messages),
            user_prompt=extract_user(messages),
            # ... capture all inputs
        )

        # Make call
        response = self.client.chat.completions.create(messages=messages, **kwargs)

        # Capture after
        call_record.response_content = response.choices[0].message.content
        call_record.token_usage = response.usage

        # Log atomically
        append_atomic(self.log_path, call_record)

        return response, call_record.call_id
```

### Refactoring Cost If Skipped
- **IMPOSSIBLE TO FIX**: Past LLM calls are lost forever
- Can't explain historical decisions
- Compliance failure for AI transparency requirements

---

## PRIORITY 5: Version Bundle Snapshot At Run Start (HIGH)

### Why Now?
If you don't snapshot all versions when a run starts:
- Can't prove which model/prompt/config produced an output
- Can't replay - don't know what versions to use
- Can't answer "what would change if we update X?"

### What to Implement Now

**At the START of every pipeline run:**

```python
def create_version_bundle() -> VersionBundle:
    return VersionBundle(
        code_version=get_git_sha(),
        model_id=get_configured_model(),
        prompt_version=hash_prompt_templates(),
        config_version=hash_extraction_config(),
        rules_version=hash_business_rules(),
        schema_version="decision_record_v1"
    )

def start_pipeline_run(claim_id: str) -> str:
    run_id = str(uuid4())

    # Snapshot versions NOW (not later)
    version_bundle = create_version_bundle()

    # Store immutably
    store_version_bundle(run_id, version_bundle)

    # Every decision in this run references this bundle
    return run_id
```

**Immutable version storage:**
```
output/
  version_bundles/
    {run_id}/
      bundle.json           # The version bundle
      prompts/              # Copy of actual prompt templates
        classification.txt
        extraction.txt
      configs/              # Copy of actual configs
        extraction_spec.yaml
```

### Refactoring Cost If Skipped
- **HIGH**: Historical runs have no version proof
- Must add version tracking retroactively with "unknown" values
- Auditors will question unversioned historical decisions

---

## PRIORITY 6: Append-Only Storage Pattern (MEDIUM-HIGH)

### Why Now?
If your storage allows UPDATE/DELETE:
- Audit trail can be silently modified
- No proof that history wasn't changed
- Must migrate to append-only later (breaking change)

### What to Implement Now

**Storage rules:**
1. Ledger files: APPEND only, never modify
2. Corrections: New "amendment" record, not UPDATE
3. Deletions: "Tombstone" record, not DELETE

```python
class AppendOnlyStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: dict) -> None:
        """Only operation allowed"""
        with open(self.path, 'a') as f:
            f.write(json.dumps(record) + '\n')

    def update(self, record_id: str, new_data: dict) -> None:
        """FORBIDDEN - raises error"""
        raise ImmutabilityViolation("Updates not allowed. Use amend() instead.")

    def delete(self, record_id: str) -> None:
        """FORBIDDEN - raises error"""
        raise ImmutabilityViolation("Deletes not allowed. Use tombstone() instead.")

    def amend(self, original_id: str, amendment: dict) -> None:
        """Correct a record by adding amendment record"""
        self.append({
            "record_type": "amendment",
            "amends": original_id,
            "amendment": amendment,
            "timestamp": datetime.utcnow().isoformat()
        })

    def tombstone(self, record_id: str, reason: str) -> None:
        """Mark record as logically deleted"""
        self.append({
            "record_type": "tombstone",
            "tombstones": record_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })
```

### Current Code That Violates This
- `labels.py`: Overwrites `latest.json` (should append versions)
- `truth_store.py`: Overwrites truth files (should version)
- `prompt_config.py`: Updates configs in place (should version)

### Refactoring Cost If Skipped
- **MEDIUM**: Must change storage patterns
- Existing overwritten data is lost
- Must explain gaps in audit trail

---

## IMPLEMENTATION ORDER

| Priority | Component | Effort | Why This Order |
|----------|-----------|--------|----------------|
| **1** | Decision Ledger Schema | Medium | Everything depends on this schema |
| **2** | Hash Chaining | Small | Must be in place before first record |
| **3** | PII Reference Architecture | Large | Must be in place before storing any PII |
| **4** | LLM Call Capture | Medium | Loses data every day it's not implemented |
| **5** | Version Bundle Snapshots | Small | Quick win, high value |
| **6** | Append-Only Patterns | Medium | Requires storage layer changes |

---

## WHAT CAN WAIT

These are important but CAN be added later without architectural pain:

| Feature | Why It Can Wait |
|---------|-----------------|
| Audience-specific views | Display layer, doesn't affect storage |
| Retention policies | Can add enforcement later |
| Access logging | Can add as middleware later |
| Export functionality | Read-only, doesn't affect storage |
| Compliance dashboards | UI, doesn't affect core data |
| Anomaly detection | Analytics layer, reads existing data |
| Approval workflows | Process layer, can wrap existing actions |

---

## SUMMARY: Build These Now or Pay Later

| Component | Cost to Fix Later | Complexity Now |
|-----------|-------------------|----------------|
| Decision Ledger Schema | Migrate all data | Define schema once |
| Hash Chaining | Unverifiable history | ~50 lines of code |
| PII Separation | Massive migration | Design pattern |
| LLM Call Capture | Lost forever | Wrapper function |
| Version Snapshots | Unverifiable history | ~30 lines of code |
| Append-Only Storage | Storage migration | Pattern enforcement |

**The math is clear**: A few hundred lines of foundational code now saves months of migration pain later.

---

## SPECIFIC CODE LOCATIONS THAT NEED TO CHANGE

### Priority 1: Decision Ledger Schema

**No existing code** - this is new infrastructure. Will need:
- New file: `src/context_builder/schemas/decision_record.py`
- New file: `src/context_builder/services/decision_ledger.py`

**Integration points where decisions are made:**

| File | Line | Current Behavior | Change Needed |
|------|------|------------------|---------------|
| `extraction/extractors/generic.py` | 90-97 | Returns `ExtractionResult` | Also log `DecisionRecord` for extraction |
| `classification/openai_classifier.py` | 286-289 | Returns classification dict | Also log `DecisionRecord` for classification |
| `api/services/labels.py` | 50 | Saves label to file | Also log `DecisionRecord` for human review |
| `api/services/labels.py` | 133 | Saves classification label | Also log `DecisionRecord` for classification override |

---

### Priority 2: Hash Chaining

**Current audit.py (lines 74-77)** - No integrity:
```python
# CURRENT - No hash, no chain
with open(self.audit_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(asdict(entry)) + "\n")
```

**Must change to:**
```python
# Add hash of previous record + hash of this record
entry.previous_hash = self._get_last_hash()
entry.record_hash = self._compute_hash(entry)
with open(self.audit_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(asdict(entry)) + "\n")
```

**Files to modify:**
| File | Change |
|------|--------|
| `api/services/audit.py:14-22` | Add `record_hash` and `previous_hash` to `AuditEntry` dataclass |
| `api/services/audit.py:74-77` | Add hash computation before write |
| `api/services/audit.py` (new) | Add `verify_chain_integrity()` method |

---

### Priority 3: PII Reference Architecture

**Current labels.py stores PII directly:**

`labels.py:37-48` - PII in label_data:
```python
label_data = {
    "schema_version": "label_v3",
    "doc_id": doc_id,           # OK - reference
    "claim_id": resolved_claim_id,  # May contain PII (name-based claim IDs)
    "review": {
        "reviewer": reviewer,   # PII - username
        ...
    },
    "field_labels": field_labels,  # Contains truth_value which may have PII
    ...
}
```

**Current truth_store.py stores PII directly:**

`truth_store.py:46-61` - Writes full payload:
```python
def save_truth_by_file_md5(self, file_md5: str, truth_payload: dict) -> None:
    # Writes entire payload including PII
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(truth_payload, f, ...)
```

**Changes needed:**

| File | Line | Current | Change |
|------|------|---------|--------|
| `schemas/label.py` | All | Direct PII | Add `pii_ref` fields, separate PII values |
| `api/services/labels.py` | 37-48 | PII in dict | Extract PII to vault, store refs |
| `storage/truth_store.py` | 46-61 | Full payload | Strip PII, store refs only |
| NEW | - | - | Create `storage/pii_vault.py` |

---

### Priority 4: LLM Call Capture

**Current extraction call (generic.py:163-177)** - No logging:
```python
def _llm_extract(self, context: str) -> Dict[str, Any]:
    # ... builds prompt ...
    response = self.client.chat.completions.create(
        model=self.model,
        temperature=self.temperature,
        max_tokens=self.max_tokens,
        response_format={"type": "json_object"},
        messages=messages,
    )
    # Response is used but not logged!
    content = response.choices[0].message.content
    return json.loads(content)
```

**Current classification call (openai_classifier.py:194-218)** - Logs usage but not full context:
```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=self.temperature,
    max_tokens=self.max_tokens,
    response_format={"type": "json_object"},
)
# Only logs token counts, not prompts/responses
if response.usage:
    logger.debug(f"API usage: {response.usage.prompt_tokens} prompt...")
```

**Files to modify:**

| File | Line | Change |
|------|------|--------|
| `extraction/extractors/generic.py` | 163-177 | Wrap call with LLM logger |
| `classification/openai_classifier.py` | 194-218 | Wrap call with LLM logger |
| `impl/openai_vision_ingestion.py` | (find call) | Wrap call with LLM logger |
| NEW | - | Create `services/llm_audit.py` with wrapper |

**All 3 call sites use `self.client.chat.completions.create()` - need wrapper:**
```python
# New wrapper pattern
class AuditedOpenAIClient:
    def chat_completion(self, **kwargs):
        call_record = LLMCallRecord(...)  # Capture inputs
        response = self.client.chat.completions.create(**kwargs)
        call_record.complete(response)    # Capture output
        self.log_call(call_record)        # Write to llm_calls.jsonl
        return response
```

---

### Priority 5: Version Bundle Snapshots

**Current run.py manifest** - Partial versioning:

The manifest currently captures some versions but not a complete bundle:
```python
# manifest.json includes:
"pipeline_versions": {
    "contextbuilder_version": "1.0.0",
    "extractor_version": "v1.0.0",
    "templates_hash": "...",
    "model_name": "gpt-4o"
}
```

**Missing from manifest:**
- Prompt template contents (only hash)
- Full config snapshot
- Business rules snapshot
- Knowledge base version

**Files to modify:**

| File | Line | Change |
|------|------|--------|
| `pipeline/run.py` | manifest creation | Add full version bundle |
| `extraction/extractors/generic.py` | 66-71 | Pass version bundle to extraction |
| NEW | - | Create `storage/version_bundles.py` |

**Need to capture at run start:**
```python
def create_version_bundle(run_id: str) -> VersionBundle:
    bundle = VersionBundle(
        code_version=get_git_sha(),
        model_id=config.model,
        prompt_templates=snapshot_prompts(),  # Copy actual templates
        extraction_config=snapshot_config(),  # Copy config files
        rules_version=hash_rules(),
    )
    # Store immutably
    bundle_path = f"output/version_bundles/{run_id}/"
    save_bundle(bundle_path, bundle)
    return bundle
```

---

### Priority 6: Append-Only Storage Pattern

**Current violations:**

| File | Line | Violation | Fix |
|------|------|-----------|-----|
| `truth_store.py` | 51,57 | `latest.json` overwrites | Version: `{timestamp}.json` + `latest` symlink |
| `prompt_config.py` | 92-93 | `_save_all()` overwrites file | Append config versions, never overwrite |
| `api/services/labels.py` | 144 | `save_label()` overwrites | Version labels, keep history |

**truth_store.py:46-61** - Overwrites:
```python
def save_truth_by_file_md5(self, file_md5: str, truth_payload: dict) -> None:
    truth_path = truth_dir / "latest.json"  # PROBLEM: always same file
    tmp_path = truth_dir / "latest.json.tmp"
    # ...
    tmp_path.replace(truth_path)  # OVERWRITES previous version
```

**Should become:**
```python
def save_truth_by_file_md5(self, file_md5: str, truth_payload: dict) -> None:
    timestamp = datetime.utcnow().isoformat().replace(":", "-")
    version_path = truth_dir / f"{timestamp}.json"  # New version
    # ... write to version_path ...
    # Update latest symlink (or latest.txt pointer)
    (truth_dir / "latest.txt").write_text(version_path.name)
```

**prompt_config.py:88-96** - Overwrites:
```python
def _save_all(self, configs: List[PromptConfig]) -> None:
    with open(self.config_file, "w", encoding="utf-8") as f:  # OVERWRITES
        json.dump([asdict(c) for c in configs], f, indent=2)
```

**Should become:**
```python
def _save_all(self, configs: List[PromptConfig]) -> None:
    # Append new version
    version_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "configs": [asdict(c) for c in configs]
    }
    with open(self.config_history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(version_entry) + "\n")
    # Update current pointer
    with open(self.config_file, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in configs], f, indent=2)
```

---

## FILE-BY-FILE CHANGE SUMMARY

| File | Priority | Changes Required |
|------|----------|------------------|
| **api/services/audit.py** | P2 | Add hash chaining (15-20 lines) |
| **api/services/labels.py** | P1, P3 | Add decision logging, PII separation |
| **storage/truth_store.py** | P3, P6 | PII refs, version history |
| **api/services/prompt_config.py** | P6 | Append-only config history |
| **extraction/extractors/generic.py** | P1, P4, P5 | Decision logging, LLM capture, version bundle |
| **classification/openai_classifier.py** | P1, P4 | Decision logging, LLM capture |
| **pipeline/run.py** | P5 | Full version bundle snapshot |
| **NEW: schemas/decision_record.py** | P1 | Decision ledger schema |
| **NEW: services/decision_ledger.py** | P1, P2 | Append-only decision storage with hash chain |
| **NEW: services/llm_audit.py** | P4 | LLM call wrapper and logging |
| **NEW: storage/pii_vault.py** | P3 | Encrypted PII storage |
| **NEW: storage/version_bundles.py** | P5 | Immutable version snapshots |

---

## DEPENDENCY ORDER

```
Week 1: Schema + Storage Foundation
├── decision_record.py (schema only, no integration)
├── decision_ledger.py (append-only with hash chain)
└── pii_vault.py (basic structure)

Week 2: Integrate Decision Logging
├── Modify audit.py (add hashing)
├── Modify labels.py (log decisions, PII refs)
└── Modify truth_store.py (versioning)

Week 3: LLM + Version Capture
├── llm_audit.py (wrapper)
├── Modify generic.py (wrap LLM calls)
├── Modify openai_classifier.py (wrap LLM calls)
└── version_bundles.py + manifest integration

Week 4: Config Append-Only
├── Modify prompt_config.py (history)
└── Verification endpoints
```
