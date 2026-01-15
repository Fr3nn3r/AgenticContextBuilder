# Ground Truth Registry Implementation Plan

## User Decisions Summary

| Question | Decision |
|----------|----------|
| Migration | No migration - wipe existing labels, start fresh |
| Confirm workflow | Auto-confirm: click → immediately writes CONFIRMED + truth_value |
| Edit friction | Hidden by default; user clicks to reveal "Edit Truth" button |
| Unverifiable reasons | Fixed enum (see below) |
| Comparison logic | Per-field normalized comparison, show only normalized status |
| Doc-level labels | Keep only `doc_type_correct` (default true), remove `text_readable` and `needs_vision` |
| Schema versioning | Breaking change to `label_v2` |

---

## New Schema Design

### FieldLabel (replaces current)

```python
class FieldLabel(BaseModel):
    field_name: str
    state: Literal["CONFIRMED", "UNVERIFIABLE", "UNLABELED"]
    truth_value: Optional[str] = None          # Required when CONFIRMED
    unverifiable_reason: Optional[str] = None  # Required when UNVERIFIABLE
    updated_at: datetime
```

### UnverifiableReason Enum

```python
UnverifiableReason = Literal[
    "not_present_in_doc",   # Field doesn't exist in this doc type
    "unreadable_text",      # OCR/extraction quality too poor
    "wrong_doc_type",       # Doc was misclassified
    "cannot_verify",        # Catch-all
    "other"                 # Free-text in notes
]
```

### DocLabels (simplified)

```python
class DocLabels(BaseModel):
    doc_type_correct: bool = True  # Default true
    # REMOVED: text_readable
    # REMOVED: needs_vision
```

### LabelResult

```python
class LabelResult(BaseModel):
    schema_version: Literal["label_v2"] = "label_v2"
    doc_id: str
    claim_id: str
    review: ReviewMetadata
    field_labels: List[FieldLabel]
    doc_labels: DocLabels
```

---

## Files to Modify

### Phase 1: Backend Schema & API

| File | Changes |
|------|---------|
| `src/context_builder/schemas/label.py` | Replace FieldLabel, simplify DocLabels, bump to label_v2 |
| `src/context_builder/api/main.py` | Update SaveLabelsRequest, remove text_readable/needs_vision from all endpoints and models |
| `ui/src/types/index.ts` | Mirror schema changes |

### Phase 2: Remove text_readable & needs_vision

**Backend files:**
- `src/context_builder/api/main.py` (lines 78, 80, 443-479, 603-641, 959-1001, 1108)
- `src/context_builder/api/insights.py` (lines 58-59, 76-77, 299-330, 392-407, 508-513, 574, 613-614, 661-662, 789-791)

**Frontend files:**
- `ui/src/types/index.ts` (lines 23, 39, 41, 106-107, 117-120, 133-134, 187, 189)
- `ui/src/components/DocReview.tsx` (lines 24-25, 261, 265)
- `ui/src/components/ClaimsTable.tsx` (lines 82, 188, 323-325, 422)
- `ui/src/components/Dashboard.tsx` (line 125)
- `ui/src/components/InsightsPage.tsx`

**Test files:**
- `tests/contract/test_label_schema.py` (lines 41-43, 180-203)
- `tests/unit/test_metrics.py` (lines 67-68, 238-239, 356)
- E2E fixtures in `ui/e2e/fixtures/`

### Phase 3: Frontend UI Changes

| File | Changes |
|------|---------|
| `ui/src/components/FieldsTable.tsx` | Replace 3-button (correct/wrong/unknown) with new workflow |
| `ui/src/components/DocReview.tsx` | Update state management for new schema |

### Phase 4: Insights Aggregation

| File | Changes |
|------|---------|
| `src/context_builder/api/insights.py` | Update FieldRecord/DocRecord, rewrite outcome classification, update metrics |

---

## Implementation Details

### 1. FieldsTable.tsx New UI Design

**For each field, show:**

```
┌─────────────────────────────────────────────────────────┐
│ Field Name                                    85% conf  │
├─────────────────────────────────────────────────────────┤
│ EXTRACTED (run_2026...)                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Value: "2024-02-08"                                 │ │
│ │ Evidence: "...occurred on February 8, 2024..."      │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ GROUND TRUTH                                            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ State: UNLABELED                                    │ │
│ │                                                     │ │
│ │ [✓ Confirm] [✗ Mark Unverifiable]                   │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**When CONFIRMED:**

```
│ GROUND TRUTH                                            │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 🔒 Truth: "2024-02-08"              [Edit ▼]        │ │
│ │ Result: ✓ MATCH                                     │ │
│ └─────────────────────────────────────────────────────┘ │
```

**Edit button behavior:**
- Hidden by default (collapsed dropdown or hidden button)
- Click to reveal → shows editable text field
- No confirmation modal, just inline edit

### 2. Confirm Action Flow

```
User clicks [✓ Confirm]
  ↓
state = "CONFIRMED"
truth_value = extracted_value (or normalized_value if present)
updated_at = now()
  ↓
Auto-save to backend
```

### 3. Mark Unverifiable Flow

```
User clicks [✗ Mark Unverifiable]
  ↓
Show dropdown: reason selection
  - "Not present in doc"
  - "Unreadable text"
  - "Wrong doc type"
  - "Cannot verify"
  - "Other" (shows notes field)
  ↓
state = "UNVERIFIABLE"
unverifiable_reason = selected
updated_at = now()
  ↓
Auto-save to backend
```

### 4. Comparison Logic

When displaying a run against ground truth:

```python
def compare_field(extracted: str | None, truth: str | None, field_spec: FieldSpec) -> str:
    if truth is None:
        return "unlabeled"

    # Normalize both values using field-specific normalizer
    norm_extracted = normalize(extracted, field_spec.normalize)
    norm_truth = normalize(truth, field_spec.normalize)

    if norm_extracted == norm_truth:
        return "match"
    elif extracted is None:
        return "missing"
    else:
        return "mismatch"
```

### 5. Insights Metrics Updates

**Overview KPIs (updated):**
- `docs_total` - unchanged
- `docs_reviewed` - docs with any field labels
- `docs_doc_type_wrong` - docs where doc_type_correct=False
- ~~`docs_needs_vision`~~ - REMOVED
- `confirmed_fields` - count of CONFIRMED labels
- `unverifiable_fields` - count of UNVERIFIABLE labels
- `match_rate` - % of CONFIRMED fields where extracted matches truth
- `mismatch_rate` - % of CONFIRMED fields where extracted doesn't match

**Priority scoring (updated):**
```python
# Only count CONFIRMED fields for accuracy metrics
# UNVERIFIABLE fields excluded from accuracy denominator
score = (mismatches * 3) + (missing_extractions * 2)
```

---

## Migration Strategy

**No migration.** User will:
1. Delete all existing `labels/latest.json` files
2. Re-run labeling with new UI

---

## Execution Order

1. **Backend schema** (`label.py`) - new FieldLabel, DocLabels
2. **TypeScript types** (`types/index.ts`) - mirror changes
3. **API models** (`main.py`) - update request/response models
4. **Remove text_readable/needs_vision** - all backend files
5. **Remove text_readable/needs_vision** - all frontend files
6. **FieldsTable.tsx** - new labeling UI
7. **DocReview.tsx** - state management updates
8. **Insights aggregator** (`insights.py`) - new metrics logic
9. **Tests** - update fixtures and assertions
10. **Delete existing labels** - clean slate

---

## Key Files (Quick Reference)

**Must modify:**
- `src/context_builder/schemas/label.py`
- `src/context_builder/api/main.py`
- `src/context_builder/api/insights.py`
- `ui/src/types/index.ts`
- `ui/src/components/FieldsTable.tsx`
- `ui/src/components/DocReview.tsx`
- `ui/src/components/ClaimsTable.tsx`
- `ui/src/components/Dashboard.tsx`

**Tests to update:**
- `tests/contract/test_label_schema.py`
- `tests/unit/test_metrics.py`
- `ui/e2e/fixtures/*.json`
