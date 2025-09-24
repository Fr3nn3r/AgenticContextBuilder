## Rename Plan: `intake` → `context_builder`

### Rationale and naming best practice
- **Python package/module**: use `context_builder` (PEP 8: all-lowercase, underscores allowed; hyphens are invalid in imports)
- **Distribution/project name and optional CLI**: use `context-builder`

### Scope and impact
- **Package directory**: rename `intake/` → `context_builder/`
- **Imports across repo**: update all `from intake...` / `import intake...` and any patch targets like `'intake.processors...'`
- **CLI invocation/docs**: change `python -m intake ...` to `python -m context_builder ...` in help text and docs
- **Generated IDs and filenames**: current prefix `"intake-"` and suffix `"_intake.json"` are output conventions; decide whether to keep or rename
- **Exceptions/names**: `IntakeError`, `error_type="intake_error"` optionally align with new name
- **Project metadata**: `pyproject.toml` name currently `contextmanager`; optionally align with the new naming

### Decision points (recommendations)
- **Output conventions (prefix/suffix)**:
  - Recommendation: keep `"intake-"` and `"_intake.json"` for now to avoid broad breakage; rebrand in a separate change
- **Backwards compatibility shim**:
  - Recommended: keep a thin `intake/` package that re-exports from `context_builder` and warns on import; remove later
- **Exceptions naming**:
  - Optional: rename to `ContextBuilderError` and map old → new via shim; can defer
- **Project metadata**:
  - Consider setting distribution name to `context-builder` and updating description; treat as a versioned change

### Step-by-step plan (do not execute yet)
1. Branching and pre-checks
   - Create `rename/intake-to-context_builder`
   - Ensure tests are green before changes

2. Package directory rename
   - Rename directory `intake/` → `context_builder/` preserving structure
   - Ensure `context_builder/__main__.py` imports `.cli.main`

3. Update internal package code
   - Fix any absolute intra-package imports: `intake.` → `context_builder.`
   - Update CLI epilog/examples in `context_builder/cli.py` to use `python -m context_builder ...`

4. Update repository imports
   - Replace all occurrences of `from intake` / `import intake` across:
     - `tests/**` (including `patch('intake....')` targets)
     - `scripts/**`
     - Any top-level files
   - Do not modify tests tied to output naming unless rebranding outputs now

5. Documentation and examples
   - Update `OCR_SETUP.md`, `PROJECT_CONTEXT.md`, and any README snippets to `python -m context_builder`
   - Update printed examples inside `scripts/test_extraction_methods.py`

6. Optional compatibility shim (recommended)
   - Add a top-level `intake/` shim:
     - `__init__.py`: re-export public API from `context_builder` and emit `DeprecationWarning`
     - `__main__.py`: forward to `context_builder.cli:main`

7. Optional naming consistency changes (defer unless required now)
   - If rebranding outputs now:
     - In `context_builder/utils.py`: change prefix `"intake-"` → new prefix (e.g., `"context-"`); update tests
     - In `context_builder/ingest.py`: change file suffix `"_intake.json"` → new suffix; update tests and fixtures
     - In `context_builder/exceptions.py`: rename `IntakeError` and `error_type`

8. Project metadata alignment
   - In `pyproject.toml`:
     - Set `name = "context-builder"`
     - Update description to reflect the new name

9. Testing and validation
   - Run full test suite; fix any missed import paths and patch targets
   - Search for lingering `import intake`/`from intake` (only allowed in the shim)
   - Verify CLI: `python -m context_builder --help`

10. Release and migration
   - If publishing, bump version and update CHANGELOG with rename and deprecation plan
   - Communicate timeline for removing the shim

### Risks and mitigations
- **Widespread import updates**: use consistent search/replace; rely on tests to catch misses
- **CLI/docs drift**: update all usage strings; quick manual CLI validation
- **Output naming changes**: touches many tests; safer to defer

### Effort estimate
- Rename + imports + docs: ~1–2 hours
- Optional shim + metadata: +30–45 minutes
- If rebranding outputs now: +1–2 hours to update tests/fixtures

### Execution checklist
- [ ] Branch created and baseline tests green
- [ ] Package dir renamed to `context_builder`
- [ ] Imports updated across code, tests, scripts
- [ ] CLI epilog/docs updated to `python -m context_builder`
- [ ] Optional shim `intake/` added with deprecation warning
- [ ] Optional output naming changes completed (if chosen) and tests updated
- [ ] Project metadata aligned
- [ ] Tests passing and CLI validated
- [ ] CHANGELOG/deprecation notes updated


