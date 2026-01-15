# Testing Reference

## Running Tests

```powershell
# All tests (Windows-compatible)
.\scripts\test.ps1

# Specific path
.\scripts\test.ps1 tests/unit/

# Pattern match
.\scripts\test.ps1 -k "quality"

# E2E tests (Playwright)
cd ui && npx playwright test

# Single E2E test
cd ui && npx playwright test e2e/tests/auth.spec.ts
```

## Test Organization

```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_classifier.py
│   ├── test_extraction.py
│   └── test_quality_gate.py
├── integration/             # Multi-component tests
│   └── test_pipeline_flow.py
└── fixtures/                # Shared test data

ui/e2e/
├── tests/                   # Playwright specs
├── pages/                   # Page objects
├── fixtures/                # Mock data
└── utils/                   # Helpers
```

## Key Test Files

| Test | Coverage |
|------|----------|
| `test_decision_ledger.py` | Hash chain integrity |
| `test_llm_audit.py` | LLM call capture |
| `test_quality_gate.py` | Pass/warn/fail logic |
| `auth.spec.ts` | Login, RBAC |
| `claim-review.spec.ts` | Document review UI |

## Writing Tests

### Backend (pytest)
```python
def test_classification_returns_doc_type(mock_openai):
    classifier = OpenAIClassifier()
    result = classifier.classify(sample_doc)
    assert result.doc_type in VALID_DOC_TYPES
    assert result.confidence > 0.5
```

### Frontend (Playwright)
```typescript
test('displays claim documents', async ({ page }) => {
  await page.goto('/claims/CLM-001');
  await expect(page.getByTestId('doc-list')).toBeVisible();
});
```

## Troubleshooting

**Windows temp dir errors:**
Use `.\scripts\test.ps1` which adds `-p no:tmpdir` automatically.

**Flaky E2E tests:**
Check if mock API is returning expected data in `ui/e2e/utils/mock-api.ts`.
