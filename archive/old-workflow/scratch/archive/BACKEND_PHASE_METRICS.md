# Backend Phase Metrics Requirements

## Implementation Status

### Implemented ✅

The pipeline now includes full phase metrics in `claims/{claim_id}/runs/{run_id}/logs/summary.json`:

**Per-document fields:**
- `timings.ingestion_ms`, `timings.classification_ms`, `timings.extraction_ms`, `timings.total_ms`
- `doc_type_confidence` - classification confidence score
- `quality_gate_status` - "pass", "warn", or "fail"
- `failed_phase` - "ingestion", "classification", or "extraction" (when error occurs)

**Aggregate phases section:**
- `phases.ingestion` - discovered, ingested, skipped, failed, duration_ms
- `phases.classification` - classified, low_confidence, distribution, duration_ms
- `phases.extraction` - attempted, succeeded, failed, skipped_unsupported, duration_ms
- `phases.quality_gate` - pass, warn, fail counts

### Not Implemented (Deferred)
- Classification confidence threshold for "low confidence" detection (currently always 0)
  - Would require classifier to return calibrated confidence scores

---

## Current State

The pipeline logs per-document records in `claims/{claim_id}/runs/{run_id}/logs/summary.json` with:
- `stats.total`, `stats.success`, `stats.errors`
- `aggregates.discovered`, `aggregates.processed`, `aggregates.skipped`, `aggregates.failed`
- Per-document: `status`, `doc_type_predicted`, `doc_type_confidence`, `time_ms`, `timings`, `quality_gate_status`, `failed_phase`
- Aggregate: `phases` object with ingestion, classification, extraction, quality_gate sub-objects

---

## Data Schema

### Per-Document Record

```json
{
  "doc_id": "fd1a86a69536",
  "doc_type_predicted": "loss_notice",
  "doc_type_confidence": 0.95,
  "status": "processed",
  "failed_phase": null,
  "error_code": null,
  "error_message": null,
  "timings": {
    "ingestion_ms": 120,
    "classification_ms": 350,
    "extraction_ms": 3823,
    "total_ms": 4293
  },
  "quality_gate_status": "pass"
}
```

### Aggregate Phases Section

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
      "low_confidence": 0,
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

## Future Enhancements

### Classification Confidence Threshold

To populate `classification.low_confidence`:
1. Define threshold (e.g., <0.7 = low confidence)
2. Update classifier to return calibrated confidence scores
3. Update `_compute_phase_aggregates` to count docs below threshold

### Additional Error Codes

The `failed_phase` field indicates where failure occurred. Additional error codes can be added to `error_code` field for more granular failure analysis.
