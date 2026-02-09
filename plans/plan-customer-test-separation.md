# Plan: Separate Customer Tests from Core Repo

**Status:** Planned
**Priority:** Medium
**Effort:** ~1 day

## Problem

17 of ~116 test files in the core repo have NSA/customer-specific coupling. This violates the core vs customer code separation principle documented in CLAUDE.md.

## Scope

### Phase 1: Move 5 explicitly NSA test files to customer repo (~274 tests)

| File | Tests | Coupling |
|------|-------|----------|
| `test_nsa_cost_estimate_extractor.py` | 35 | Imports NSA extractor, German part names |
| `test_nsa_decision_engine.py` | 44 | NSA denial clauses, CHF/VAT |
| `test_nsa_enricher.py` | 23 | NSA fact patterns, claim data |
| `test_nsa_guarantee_extractor.py` | 52 | NSA guarantee schema, German terms |
| `test_nsa_screener.py` | 120+ | NSA screening logic, brand lists, fuel types |

**Destination:** `C:\Users\fbrun\Documents\GitHub\context-builder-nsa\tests\unit\`

### Phase 2: Defixture 12 gray-zone test files in core repo

Replace NSA YAML fixtures with synthetic/generic ones so these files test the framework without customer coupling:

- `test_screening.py`
- `test_coverage_analyzer.py`
- `test_screening_payout.py`
- `test_coverage_rule_engine.py`
- `test_coverage_keyword_matcher.py`
- `test_decision_dossier_schemas.py`
- `test_explanation_generator.py`
- `test_classification_catalog.py`
- `test_rule_engine.py`
- `test_claim_run_paths.py`
- `test_assessment_response.py`
- `test_text.py` (minor)

**Action:** Replace German component names, NSA YAML references, and customer-specific data with generic fixtures (`"COMPONENT_A"`, `"PART_X"`, inline minimal YAML).

### Phase 3: Create test infrastructure in customer repo

1. Add `pytest.ini` and `conftest.py` to customer repo
2. Set up core dependency via pip install from git tag:
   ```
   context-builder @ git+https://github.com/Fr3nn3r/AgenticContextBuilder.git@v0.3.0
   ```
3. Ensure tests can import both core framework and customer config

### Phase 4: Add lint guard to core repo

Add a CI check (or pre-commit hook) that fails if any new test file imports from `workspaces/`.

### Phase 5: Document SOP

Add to customer repo README:

**On core PR:**
- Run core tests only: `pytest tests/unit/ --no-cov -q`
- Must pass before merge

**On customer PR:**
- Install pinned core version
- Run customer test suite: `pytest tests/ --no-cov -q`
- Optional: smoke pipeline run on 1-3 claims

**On core PR that changes interfaces/schemas:**
- Also run customer test suite to catch breaking changes early

**Before production deploy:**
- Run both: core suite + customer suite against pinned core version

## Decisions

- **Dependency management:** Use `pip install` from git tag (not submodule). Aligns with existing semver + version-bump script.
- **No compatibility matrix yet** — overkill with one customer. Git tag pin is the compatibility record. Add matrix when 2+ customers exist.
- **No complex CI orchestration yet** — start with documented manual steps, automate once pattern is proven.

## Execution Order

1. Create test infrastructure in customer repo (pytest.ini, conftest.py, imports)
2. Move the 5 `test_nsa_*` files to customer repo
3. Defixture the 12 gray-zone files (replace NSA YAML with synthetic data)
4. Add lint guard (grep in CI that fails on `workspaces/` imports in tests)
5. Document the SOP in customer repo README
6. Remove moved test files from core repo
