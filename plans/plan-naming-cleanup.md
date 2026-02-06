# Plan: Naming Cleanup & Code Placement Fixes

**Status: COMPLETED**

## Scope
Fix naming confusions and misplaced code identified in code review. LOB-specific code stays (claims-focused system).

## Changes

### 1. Rename `AssessmentService` → `AssessmentStorageService`
**Why:** Current name implies orchestration, but it only handles file I/O for assessments.

**Files to change:**
- `src/context_builder/api/services/assessment.py` — rename class
- `src/context_builder/api/services/__init__.py` — update export
- `src/context_builder/api/routers/claims.py` — update import/usage
- Any other imports (search for `AssessmentService`)

**Risk:** Low — straightforward rename with IDE support.

---

### 2. Rename `TruthStore` → `GroundTruthStore`
**Why:** "Truth" is ambiguous. "Ground truth" is the standard ML/data term for labeled reference data.

**Files to change:**
- `src/context_builder/storage/truth_store.py` — rename class
- `src/context_builder/storage/__init__.py` — update export
- All imports of `TruthStore`

**Risk:** Low — straightforward rename.

---

### 3. Rename `GenericFieldExtractor` → `LLMFieldExtractor`
**Why:** "Generic" is vague. It actually uses LLM for extraction.

**Files to change:**
- `src/context_builder/extraction/extractors/generic.py` — rename class
- `src/context_builder/extraction/extractors/__init__.py` — update export
- `src/context_builder/extraction/base.py` — update factory reference
- All imports

**Risk:** Low — straightforward rename.

---

### 4. Remove duplicate `TenantConfig`
**Why:** Defined in both `config/` and `services/`. Keep one source of truth.

**Action:**
- Check which is the canonical version (likely `services/tenant_config.py`)
- Remove the duplicate from `config/`
- Update imports to use single location

**Files to check:**
- `src/context_builder/config/__init__.py`
- `src/context_builder/services/tenant_config.py`

**Risk:** Low — just removing duplication.

---

### 5. Extract `parse_european_number()` to `utils/`
**Why:** 120-line utility function doesn't belong in a Pydantic schema file.

**Action:**
- Create `src/context_builder/utils/number_parsing.py`
- Move `parse_european_number()` from `schemas/claim_facts.py`
- Update import in `claim_facts.py`
- Check for other usages

**Risk:** Low — pure function with no side effects.

---

### 6. Move `HARD_FAIL_CHECK_IDS` and `SCREENING_CHECK_IDS` to config
**Why:** Business logic constants don't belong in schema definitions.

**Action:**
- Move to workspace config or a dedicated `screening_config.py`
- Or keep in `schemas/screening.py` but document as "default values, overridable"

**Decision needed:** Full externalization or just better documentation?

**Risk:** Medium — may have validation dependencies.

---

## Execution Order

```
1. Extract parse_european_number() to utils/  [isolated, no deps]
2. Rename GenericFieldExtractor → LLMFieldExtractor  [isolated]
3. Rename TruthStore → GroundTruthStore  [isolated]
4. Remove duplicate TenantConfig  [isolated]
5. Rename AssessmentService → AssessmentStorageService  [most imports]
6. (Optional) Move screening constants  [needs decision]
```

## Test Strategy
- Run `python -m pytest tests/unit/ --no-cov -q` after each rename
- Grep for old names to ensure no orphaned references

## Estimated Effort
- Items 1-5: ~30 min each (find-replace + test)
- Item 6: Defer or quick doc fix

## Not in Scope
- LOB-specific code (keeping for now)
- `api/services/` vs `services/` consolidation (larger refactor)
- StorageFacade clarification (needs investigation)
