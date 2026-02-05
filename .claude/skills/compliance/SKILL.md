---
name: compliance
description: "Compliance development guide — decision logging, LLM audit, version bundles. Use /compliance when working on audit/compliance features."
allowed-tools: Read, Glob, Grep, Bash(python -m pytest *)
---

# Compliance Developer Guide

**Key Principle**: Every decision the system makes must be traceable, explainable, and verifiable.

## Overview

Our compliance infrastructure provides:
1. **Decision Ledger** — Tamper-evident logging of all system decisions
2. **LLM Audit** — Full capture of all LLM API calls
3. **Version Bundles** — Reproducibility snapshots linked to pipeline runs
4. **Version History** — Append-only history for truth, configs, and labels
5. **Compliance API** — REST endpoints for verification and audit queries
6. **PII Vault** — Separation of PII from audit trails (stub, future implementation)

## Decision Tree: What to Do

```
Writing new feature?
  |
  +-- Uses LLM? --> Use AuditedOpenAIClient (not direct OpenAI)
  |                  Pass decision_context with doc_id/claim_id
  |
  +-- Makes decisions? --> Log DecisionRecord after processing
  |                        Include rationale with evidence
  |                        Link LLM call_id to decision
  |
  +-- Human interaction? --> Log with actor_type="human"
  |                          Use actor IDs (not PII like email)
  |                          Record before/after for corrections
  |
  +-- Stores data? --> Use append-only pattern
                       Include _version_metadata with timestamps
                       Write latest.json + append history.jsonl
```

## Quick Reference

### Import Locations

```python
# Decision logging
from context_builder.services.decision_ledger import DecisionLedger
from context_builder.schemas.decision_record import (
    DecisionRecord, DecisionType, DecisionRationale, DecisionOutcome,
)

# LLM auditing
from context_builder.services.llm_audit import AuditedOpenAIClient

# Version bundles
from context_builder.storage.version_bundles import (
    VersionBundleStore, get_version_bundle_store,
)

# Storage with history
from context_builder.storage.truth_store import TruthStore
from context_builder.storage.filesystem import FileStorage
from context_builder.api.services.prompt_config import PromptConfigService

# PII vault (stub)
from context_builder.storage.pii_vault import PIIVault
```

### File Locations

| Component | File |
|-----------|------|
| Decision Ledger | `{workspace}/logs/decisions.jsonl` |
| LLM Call Log | `{workspace}/logs/llm_calls.jsonl` |
| Version Bundles | `{workspace}/version_bundles/{run_id}/bundle.json` |
| Truth History | `{workspace}/registry/truth/{file_md5}/history.jsonl` |
| Config History | `{workspace}/config/prompt_configs_history.jsonl` |
| Label History | `{workspace}/claims/{claim}/docs/{doc}/labels/history.jsonl` |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/compliance/ledger/verify` | GET | Verify hash chain integrity |
| `/api/compliance/ledger/decisions` | GET | List decisions with filters |
| `/api/compliance/version-bundles` | GET | List version bundles |
| `/api/compliance/version-bundles/{run_id}` | GET | Get bundle details |
| `/api/compliance/config-history` | GET | Config change log |
| `/api/compliance/truth-history/{file_md5}` | GET | Truth version history |
| `/api/compliance/label-history/{doc_id}` | GET | Label version history |

### Decision Types

| Type | Actor | Use Case |
|------|-------|----------|
| `classification` | system | Doc type determination |
| `extraction` | system | Field extraction |
| `quality_gate` | system | Pass/warn/fail |
| `human_review` | human | Label verification |
| `override` | human | Correction of system decision |

## MANDATORY — READ supporting docs when working on compliance code:

- **Detailed patterns**: `.claude/skills/compliance/compliance-patterns.md` — Decision logging examples, LLM auditing setup, version history patterns, PII handling
- **Testing guide**: `.claude/skills/compliance/compliance-testing.md` — Test files, verification commands, troubleshooting

## Code Review Checklist

When reviewing PRs touching compliance:

### For LLM Usage
- [ ] Uses `AuditedOpenAIClient`, not direct client
- [ ] Passes `decision_context` with identifiers
- [ ] No PII in prompts (use refs)

### For Decision Points
- [ ] Logs `DecisionRecord` with appropriate type
- [ ] Includes meaningful rationale
- [ ] Links to LLM calls via `call_id`
- [ ] Uses IDs not PII for actor_identity

### For Data Storage
- [ ] Append-only pattern (no updates/deletes to history)
- [ ] Includes timestamps and version metadata
- [ ] Both `latest.json` and `history.jsonl` updated

## Existing Implementations (Reference)

Already wrapped with compliance:
- `src/context_builder/classification/openai_classifier.py` — Classification decisions
- `src/context_builder/extraction/extractors/generic.py` — Extraction decisions
- `src/context_builder/api/services/labels.py` — Human review + override decisions
- `src/context_builder/storage/truth_store.py` — Truth version history
- `src/context_builder/storage/filesystem.py` — Label version history

## Test Commands

```bash
python -m pytest tests/unit/test_decision_ledger.py -v
python -m pytest tests/unit/test_llm_audit.py -v
python -m pytest tests/unit/test_version_history.py -v
python -m pytest tests/unit/test_compliance_api.py -v
```
