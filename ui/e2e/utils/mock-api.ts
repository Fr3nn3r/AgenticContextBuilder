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
const runsFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "runs.json"), "utf-8"));
const insightsOverviewFixture = JSON.parse(fs.readFileSync(path.join(fixturesDir, "insights-overview.json"), "utf-8"));

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

  // Mock GET /api/insights/runs
  await page.route("**/api/insights/runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(runsFixture),
    });
  });

  // Mock GET /api/insights/runs/:runId/overview
  await page.route(/\/api\/insights\/runs\/[^/]+\/overview/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(insightsOverviewFixture),
    });
  });

  // Mock GET /api/insights/runs/:runId/doc-types
  await page.route(/\/api\/insights\/runs\/[^/]+\/doc-types/, async (route) => {
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

  // Mock GET /api/claim-runs
  await page.route("**/api/claim-runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(runsFixture),
    });
  });
}
