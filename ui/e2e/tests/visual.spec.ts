import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";

/**
 * Visual Regression Tests
 *
 * These tests capture screenshots of key pages and compare them against baselines.
 * On first run, baseline images will be created in the playwright snapshots directory.
 *
 * To update baselines after intentional UI changes:
 *   npx playwright test --update-snapshots
 */
test.describe("Visual Regression", () => {
  test.beforeEach(async ({ page }) => {
    // Set consistent viewport size for all visual tests
    await page.setViewportSize({ width: 1440, height: 900 });
    await setupAuthenticatedMocks(page, "admin");
  });

  test("Claim Document Pack layout", async ({ page }) => {
    // Navigate to batches workspace then claims tab
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-claims").click();
    await page.waitForLoadState("networkidle");

    // Wait for data to load
    await page.waitForSelector('[data-testid="batch-context-selector"]');
    await page.waitForTimeout(500); // Extra wait for animations

    await expect(page).toHaveScreenshot("claims-table.png", {
      threshold: 0.1, // Allow 10% pixel difference
      maxDiffPixelRatio: 0.05, // Max 5% of pixels can differ
    });
  });

  test("Claim Review layout", async ({ page }) => {
    await page.goto("/claims/CLM-2024-001/review?doc=doc_001");
    await page.waitForLoadState("networkidle");

    // Wait for document content to load
    await page.waitForSelector('[data-testid="doc-strip-item"]');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot("claim-review.png", {
      threshold: 0.1,
      maxDiffPixelRatio: 0.05,
    });
  });

  test("Calibration Insights layout", async ({ page }) => {
    // Navigate to batches workspace then benchmark tab
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-metrics").click();
    await page.waitForLoadState("networkidle");

    // Wait for insights data to load
    await page.waitForSelector('[data-testid="batch-context-selector"]');
    await page.waitForTimeout(500);

    await expect(page).toHaveScreenshot("insights.png", {
      threshold: 0.1,
      maxDiffPixelRatio: 0.05,
    });
  });
});
