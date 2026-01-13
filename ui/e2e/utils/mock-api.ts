import { Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load fixtures
const fixturesDir = path.join(__dirname, "..", "fixtures");
const claimsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "claims.json"), "utf-8"));
const claimReviewFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "claim-review.json"), "utf-8"));
const docPayloadFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "doc-payload.json"), "utf-8"));
const templatesFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "templates.json"), "utf-8"));
const batchesFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "runs.json"), "utf-8"));
const insightsOverviewFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "insights-overview.json"), "utf-8"));
const multiBatchFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "multi-run-data.json"), "utf-8"));

export async function setupApiMocks(page: Page) {
  // Mock GET /api/claims
  await page.route("**/api/claims", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(claimsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/claims/:claimId/docs
  await page.route("**/api/claims/*/docs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(claimReviewFixture.docs),
    });
  });

  // Mock GET /api/claims/:claimId/review
  await page.route("**/api/claims/*/review", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(claimReviewFixture),
    });
  });

  // Mock GET /api/docs/:docId (but not /labels or /source)
  await page.route(/\/api\/docs\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(docPayloadFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/docs/:docId/labels
  await page.route("**/api/docs/*/labels", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved", path: "/mock/path" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/templates
  await page.route("**/api/templates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(templatesFixture),
    });
  });

  // Mock GET /api/runs/latest
  await page.route("**/api/runs/latest", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_dir: "runs/latest",
        total_claims: 2,
        total_docs: 5,
        extracted_count: 5,
        labeled_count: 3,
        quality_gate: { pass: 2, warn: 2, fail: 1 },
      }),
    });
  });

  // Mock GET /api/insights/batches (also handles legacy /api/insights/runs)
  await page.route(/\/api\/insights\/(runs|batches)$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(batchesFixture),
    });
  });

  // Mock GET /api/insights/runs/detailed
  await page.route("**/api/insights/runs/detailed", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Mock GET /api/insights/(runs|batch)/:id/overview
  await page.route(/\/api\/insights\/(run|batch)\/[^/]+\/overview/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(insightsOverviewFixture),
    });
  });

  // Mock GET /api/insights/(runs|batch)/:id/doc-types
  await page.route(/\/api\/insights\/(run|batch)\/[^/]+\/doc-types/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          doc_type: "loss_notice",
          docs_reviewed: 2,
          required_field_presence_pct: 90,
          required_field_accuracy_pct: 95,
          evidence_rate_pct: 85,
          top_failing_field: null,
          docs_needs_vision: 0,
        },
        {
          doc_type: "police_report",
          docs_reviewed: 1,
          required_field_presence_pct: 75,
          required_field_accuracy_pct: 80,
          evidence_rate_pct: 70,
          top_failing_field: "badge_number",
          docs_needs_vision: 1,
        },
      ]),
    });
  });

  // Mock GET /api/insights/(run|batch)/:id/priorities
  await page.route(/\/api\/insights\/(run|batch)\/[^/]+\/priorities/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Mock GET /api/insights/baseline
  await page.route("**/api/insights/baseline", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ baseline_run_id: null }),
    });
  });

  // Mock GET /api/claims/batches and /api/claims/runs (legacy)
  await page.route(/\/api\/(claim-runs|claims\/(batches|runs))/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(batchesFixture),
    });
  });
}

/**
 * Setup API mocks for multi-batch testing scenarios.
 * This function mocks APIs with batch-specific data to test that UI
 * correctly displays batch-scoped metrics when switching between batches.
 */
export async function setupMultiBatchMocks(page: Page) {
  // Mock GET /api/claims (same as base)
  await page.route("**/api/claims", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(claimsFixture),
      });
    } else {
      await route.continue();
    }
  });

  // Mock GET /api/insights/batches - return multi-batch data
  await page.route(/\/api\/insights\/(runs|batches)$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(multiBatchFixture.batches),
    });
  });

  // Mock GET /api/insights/batches/detailed
  await page.route(/\/api\/insights\/(runs|batches)\/detailed/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(multiBatchFixture.detailedBatches),
    });
  });

  // Mock GET /api/insights/batch/:batchId/overview - return batch-specific data
  await page.route(/\/api\/insights\/(run|batch)\/([^/]+)\/overview/, async (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/insights\/(?:run|batch)\/([^/]+)\/overview/);
    const batchId = match ? match[1] : "batch-small";

    const overview = multiBatchFixture.overviews[batchId] || multiBatchFixture.overviews["batch-small"];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(overview),
    });
  });

  // Mock GET /api/insights/batch/:batchId/doc-types - return batch-specific data
  await page.route(/\/api\/insights\/(run|batch)\/([^/]+)\/doc-types/, async (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/insights\/(?:run|batch)\/([^/]+)\/doc-types/);
    const batchId = match ? match[1] : "batch-small";

    const docTypes = multiBatchFixture.docTypes[batchId] || multiBatchFixture.docTypes["batch-small"];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(docTypes),
    });
  });

  // Mock GET /api/insights/batch/:batchId/priorities - return empty for simplicity
  await page.route(/\/api\/insights\/(run|batch)\/([^/]+)\/priorities/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  // Mock GET /api/insights/baseline
  await page.route("**/api/insights/baseline", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ baseline_batch_id: null }),
    });
  });

  // Mock GET /api/claims/batches - for Extraction page batch selector
  await page.route(/\/api\/claims\/(runs|batches)/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(multiBatchFixture.batches.map((b: { run_id: string; timestamp: string; model: string; claims_count: number }) => ({
        run_id: b.run_id,
        timestamp: b.timestamp,
        model: b.model,
        claims_count: b.claims_count,
      }))),
    });
  });

  // Mock GET /api/templates
  await page.route("**/api/templates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(templatesFixture),
    });
  });
}

// Legacy alias for backwards compatibility
export const setupMultiRunMocks = setupMultiBatchMocks;
