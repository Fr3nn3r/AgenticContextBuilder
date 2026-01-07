# Backend Phase Metrics Requirements

## Current State

The pipeline currently logs per-document records in `claims/{claim_id}/runs/{run_id}/logs/summary.json` with:
- `stats.total`, `stats.success`, `stats.errors`
- `aggregates.discovered`, `aggregates.processed`, `aggregates.skipped`, `aggregates.failed`
- Per-document: `status`, `doc_type_predicted`, `time_ms`, `text_source_used`

**Missing for full phase metrics:**
- Per-phase timings (ingestion vs classification vs extraction)
- Classification confidence scores
- Quality gate breakdown (pass/warn/fail counts)
- Per-phase failure counts with error codes

---

## Required Changes

### 1. Per-Phase Timing

Add phase-level timing to each document record:

```json
{
  "doc_id": "fd1a86a69536",
  "timings": {
    "ingestion_ms": 120,
    "classification_ms": 350,
    "extraction_ms": 3823,
    "total_ms": 4293
  }
}
```

### 2. Classification Confidence

Add confidence score to document record:

```json
{
  "doc_id": "fd1a86a69536",
  "doc_type_predicted": "loss_notice",
  "doc_type_confidence": 0.95,
  "classification_low_confidence": false
}
```

Define threshold (e.g., <0.7 = low confidence).

### 3. Quality Gate Status

Add per-document quality gate result:

```json
{
  "doc_id": "fd1a86a69536",
  "quality_gate": {
    "status": "pass",
    "missing_required_fields": [],
    "evidence_rate": 0.85
  }
}
```

### 4. Per-Phase Error Tracking

When a document fails, record which phase failed:

```json
{
  "doc_id": "abc123",
  "status": "failed",
  "failed_phase": "extraction",
  "error_code": "TIMEOUT",
  "error_message": "LLM request timed out after 60s"
}
```

### 5. Aggregate Phase Metrics in Summary

Add a `phases` section to `summary.json`:

```json
{
  "phases": {
    "ingestion": {
      "discovered": 130,
      "ingested": 128,
      "skipped": 2,
      "failed": 0,
      "duration_ms": 15400
    },
    "classification": {
      "classified": 128,
      "low_confidence": 3,
      "distribution": {
        "loss_notice": 45,
        "police_report": 38,
        "insurance_policy": 25,
        "certificate": 10,
        "other": 10
      },
      "duration_ms": 44800
    },
    "extraction": {
      "attempted": 108,
      "succeeded": 105,
      "failed": 3,
      "skipped_unsupported": 20,
      "duration_ms": 412000
    },
    "quality_gate": {
      "pass": 85,
      "warn": 15,
      "fail": 5
    }
  }
}
```

---

## Implementation Priority

1. **High**: Quality gate breakdown (can be computed from extraction results now)
2. **High**: Classification distribution (can be computed from doc records now)
3. **Medium**: Per-phase error tracking
4. **Low**: Per-phase timings (requires pipeline instrumentation)
5. **Low**: Classification confidence (requires classifier changes)

---

## Temporary Workarounds

For the Extraction page UI, we compute what we can from existing data:

| Metric | Source |
|--------|--------|
| `ingestion.discovered` | `aggregates.discovered` |
| `ingestion.ingested` | `aggregates.processed` |
| `ingestion.skipped` | `aggregates.skipped` |
| `ingestion.failed` | (not available - use 0) |
| `classification.classified` | count of docs with `doc_type_predicted` |
| `classification.distribution` | aggregate `doc_type_predicted` values |
| `classification.low_confidence` | (not available - use 0) |
| `extraction.attempted` | count of docs with `extraction` output path |
| `extraction.succeeded` | `stats.success` |
| `extraction.failed` | `stats.errors` |
| `quality_gate.*` | read from extraction results `quality_gate.status` |

Phase durations will show "—" until instrumented.
