# Compliance Testing Guide

## Unit Tests

```bash
# Decision ledger tests (hash chain integrity)
python -m pytest tests/unit/test_decision_ledger.py -v

# LLM audit tests
python -m pytest tests/unit/test_llm_audit.py -v

# Version history tests
python -m pytest tests/unit/test_version_history.py -v

# Compliance API tests
python -m pytest tests/unit/test_compliance_api.py -v
```

## Integration Tests

```bash
# Full decision flow integration test
python -m pytest tests/integration/test_compliance_decision_flow.py -v
```

## Manual Verification via API

```bash
# Verify ledger integrity
curl http://localhost:8000/api/compliance/ledger/verify

# Check recent decisions
curl "http://localhost:8000/api/compliance/ledger/decisions?limit=5"

# Check version bundles
curl http://localhost:8000/api/compliance/version-bundles

# Config change history
curl "http://localhost:8000/api/compliance/config-history?limit=50"

# Truth history for a file
curl http://localhost:8000/api/compliance/truth-history/abc123def456

# Label history for a document
curl http://localhost:8000/api/compliance/label-history/DOC-001
```

## API Response Formats

### Decision List Response
```json
[
  {
    "decision_id": "dec_abc123",
    "decision_type": "classification",
    "timestamp": "2026-01-14T12:00:00Z",
    "claim_id": "CLM-001",
    "doc_id": "DOC-001",
    "actor_type": "system",
    "actor_id": "gpt-4o",
    "rationale": {
      "summary": "Classified as invoice",
      "confidence": 0.95
    },
    "prev_hash": "a1b2c3d4e5f6..."
  }
]
```

### History Response
```json
{
  "doc_id": "DOC-001",
  "version_count": 3,
  "versions": [
    {
      "version_number": 1,
      "saved_at": "2026-01-14T10:00:00Z",
      "reviewer": "user1",
      "field_count": 5
    }
  ]
}
```

## Troubleshooting

### Decision Ledger Issues

**Problem**: Hash chain verification fails
- Do NOT modify `decisions.jsonl` manually
- Investigate the break point via: `curl http://localhost:8000/api/compliance/ledger/verify`
- Contact compliance team before any remediation

**Problem**: Missing decisions in ledger
- Check that code path calls `ledger.append()`
- Add logging to trace execution flow
- Verify output/logs directory is writable

### LLM Audit Issues

**Problem**: LLM calls not appearing in log
- Verify using `AuditedOpenAIClient`, not direct OpenAI client
- Check `output/logs/llm_calls.jsonl` exists and is writable

### Version History Issues

**Problem**: History not being recorded
- Ensure using the updated storage classes (TruthStore, FileStorage, PromptConfigService) that include history tracking
- Check that `history.jsonl` files are being created

**Problem**: Version numbers not incrementing
- Check that `_get_next_version()` can read `history.jsonl`
- Verify file permissions allow reading and appending

## Code Review Checklist

When reviewing PRs, verify:

### For Any LLM Usage
- [ ] Uses `AuditedOpenAIClient`, not direct client
- [ ] Passes `decision_context` with identifiers
- [ ] No PII in prompts (use refs)

### For Decision Points
- [ ] Logs `DecisionRecord` with appropriate type
- [ ] Includes meaningful rationale
- [ ] Links to LLM calls via `call_id`
- [ ] Uses IDs not PII for actor_identity

### For Human Interactions
- [ ] Logs human decisions with `actor_type="human"`
- [ ] Records before/after for corrections
- [ ] Uses `override` type for classification changes

### For Data Storage
- [ ] No PII in decision ledger
- [ ] Append-only pattern (no updates/deletes to history)
- [ ] Includes timestamps and version metadata
- [ ] Both `latest.json` and `history.jsonl` updated
