# E2E Testing Guide

## Test Modes

The Playwright test suite supports two distinct modes:

### 1. Standalone (Mock Mode) - Default

**Purpose**: Fast, isolated tests for local development and CI.

**Characteristics**:
- Uses route interception to mock all API responses
- Auto-starts Vite dev server (no backend needed)
- Parallel execution for speed (~4s for 8 tests)
- Deterministic results with fixture data

**Usage**:
```bash
npm run test:e2e              # Run all tests
npm run test:e2e:headed       # Run with visible browser
npm run test:e2e:ui           # Interactive UI mode
npx playwright test smoke     # Run specific test file
npx playwright test -g "nav"  # Run tests matching pattern
```

### 2. Integration Mode

**Purpose**: Tests against a real running development environment.

**Characteristics**:
- Requires both frontend and backend running (`npm run dev` + `uvicorn`)
- Sequential execution to avoid race conditions
- Longer timeouts for real API latency
- Tests actual data flow and authentication

**Usage**:
```bash
# Start servers first:
# Terminal 1: cd ui && npm run dev
# Terminal 2: uvicorn context_builder.api.main:app --reload --port 8000

# Then run tests:
npm run test:e2e:integrated
```

**Environment Variables** (optional):
```bash
TEST_MODE=integrated
TEST_BASE_URL=http://localhost:5173
TEST_ADMIN_USER=su
TEST_ADMIN_PASSWORD=su
```

## Screenshot Capture for Agents

Dedicated tests for capturing UI screenshots that AI agents can analyze.

**Capture all pages**:
```bash
npm run test:e2e:screenshot
```

**Capture specific page**:
```bash
npx playwright test screenshot-test -g "batches overview"
npx playwright test screenshot-test -g "compliance"
npx playwright test screenshot-test -g "admin"
```

**Output location**: `ui/test-screenshots/`

**Available screenshots**:
- `batches-overview.png` - Batch dashboard with metrics
- `batches-documents.png` - Document list in batch
- `batches-classification.png` - Classification review
- `all-claims.png` - Claims table view
- `templates.png` - Extraction templates
- `pipeline.png` - Pipeline runner
- `compliance.png` - Compliance logs
- `admin.png` - Admin settings

## Directory Structure

```
ui/e2e/
├── config/
│   └── test-config.ts       # Mode-aware configuration
├── fixtures/                # Mock API response data
│   ├── claims.json
│   ├── users.json
│   └── ...
├── pages/                   # Page Object Models
│   ├── base.page.ts
│   ├── sidebar.page.ts
│   └── ...
├── tests/                   # Test files
│   ├── smoke.spec.ts        # Basic navigation
│   ├── screenshot-test.spec.ts  # Agent screenshots
│   └── ...
├── utils/
│   ├── mock-api.ts          # Route interception
│   ├── assertions.ts        # Data-agnostic assertions
│   └── test-setup.ts        # Unified setup layer
└── global-teardown.ts       # Cleanup after tests
```

## Writing Tests

### For Mock Mode Only
```typescript
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.beforeEach(async ({ page }) => {
  await setupAuthenticatedMocks(page, "admin");
});
```

### For Both Modes
```typescript
import { setupTestEnvironment, skipInMockMode } from "../utils/test-setup";

test.beforeEach(async ({ page }) => {
  await setupTestEnvironment(page, "admin");
});

test("needs real data", async ({ page }) => {
  skipInMockMode(); // Skip in mock mode
  // Test real API behavior
});
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `npm run test:e2e` | Run all tests (mock mode) |
| `npm run test:e2e:headed` | Run with visible browser |
| `npm run test:e2e:ui` | Interactive test runner |
| `npm run test:e2e:integrated` | Run against real backend |
| `npm run test:e2e:screenshot` | Capture page screenshots |
| `npm run test:e2e:compliance` | Run compliance tests only |
| `npx playwright show-report` | View HTML test report |
