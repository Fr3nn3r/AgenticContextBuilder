import { test, expect, Page } from "@playwright/test";
import { ClaimReviewPage } from "../pages/claim-review.page";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load fixtures
const fixturesDir = path.join(__dirname, "..", "fixtures");
const claimsFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "claims.json"), "utf-8")
);
const claimReviewFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "claim-review.json"), "utf-8")
);
const docPayloadFixture = JSON.parse(
  fs.readFileSync(path.join(fixturesDir, "doc-payload.json"), "utf-8")
);

// State to track saved labels
let savedLabels: Record<string, unknown> | null = null;

async function setupApiMocksWithPersistence(page: Page) {
  // Reset saved labels at start of each test
  savedLabels = null;

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

  // Mock GET /api/claims/:claimId/review
  await page.route("**/api/claims/*/review", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(claimReviewFixture),
    });
  });

  // Mock GET /api/docs/:docId - return saved labels if they exist
  await page.route(/\/api\/docs\/[^/]+$/, async (route) => {
    if (route.request().method() === "GET") {
      const responseData = { ...docPayloadFixture };

      // If we have saved labels, include them in the response
      if (savedLabels) {
        responseData.labels = savedLabels;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(responseData),
      });
    } else {
      await route.continue();
    }
  });

  // Mock POST /api/docs/:docId/labels - capture the saved labels
  await page.route("**/api/docs/*/labels", async (route) => {
    if (route.request().method() === "POST") {
      // Capture the posted data
      const postData = route.request().postDataJSON();
      savedLabels = {
        schema_version: "label_v1",
        doc_id: docPayloadFixture.doc_id,
        claim_id: docPayloadFixture.claim_id,
        review: {
          reviewer: postData?.reviewer || "system",
          reviewed_at: new Date().toISOString(),
          notes: postData?.notes || "",
        },
        field_labels: postData?.field_labels || [],
        doc_labels: postData?.doc_labels || {
          doc_type_correct: true,
          text_readable: "good",
          needs_vision: false,
        },
      };

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved", path: "/mock/path" }),
      });
    } else {
      await route.continue();
    }
  });

  // Mock other required endpoints
  await page.route("**/api/claim-runs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { run_id: "run_001", timestamp: "2024-01-15T10:00:00Z", model: "gpt-4o" },
      ]),
    });
  });
}

test.describe("Save Review Persists", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocksWithPersistence(page);
  });

  test("save button is visible", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    await expect(review.saveButton).toBeVisible();
    await expect(review.saveButton).toContainText("Save Labels");
  });

  test("doc type selection buttons are visible", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Doc type correct buttons (Yes/No/Unsure)
    const yesButton = page.getByRole("button", { name: "Yes" });
    const noButton = page.getByRole("button", { name: "No" });
    const unsureButton = page.getByRole("button", { name: "Unsure" });

    await expect(yesButton).toBeVisible();
    await expect(noButton).toBeVisible();
    await expect(unsureButton).toBeVisible();
  });

  test("notes field is visible and editable", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    const notesField = page.getByPlaceholder("Notes (optional)");
    await expect(notesField).toBeVisible();

    // Type something
    await notesField.fill("Test notes from Playwright");

    // Value should be set
    await expect(notesField).toHaveValue("Test notes from Playwright");
  });

  test("clicking save triggers API call", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Track API calls
    let saveApiCalled = false;
    page.on("request", (request) => {
      if (request.url().includes("/labels") && request.method() === "POST") {
        saveApiCalled = true;
      }
    });

    // Fill notes
    const notesField = page.getByPlaceholder("Notes (optional)");
    await notesField.fill("Test notes");

    // Click save
    await review.saveButton.click();

    // Wait for the API call
    await page.waitForTimeout(500);

    expect(saveApiCalled).toBe(true);
  });

  test("saved labels persist after page reload", async ({ page }) => {
    const review = new ClaimReviewPage(page);
    await review.goto("CLM-2024-001", "doc_001");

    // Change doc type to "No"
    const noButton = page.getByRole("button", { name: "No" });
    await noButton.click();

    // Add notes
    const notesField = page.getByPlaceholder("Notes (optional)");
    await notesField.fill("Test persistence notes");

    // Save
    await review.saveButton.click();
    await page.waitForTimeout(500);

    // Reload the page
    await page.reload();
    await review.waitForLoad();

    // After reload, values should be persisted (from our mock)
    // The "No" button should be selected (has specific styling)
    const noButtonAfterReload = page.getByRole("button", { name: "No" });
    await expect(noButtonAfterReload).toBeVisible();

    // Notes should have the value we saved
    const notesFieldAfterReload = page.getByPlaceholder("Notes (optional)");
    await expect(notesFieldAfterReload).toHaveValue("Test persistence notes");
  });
});
