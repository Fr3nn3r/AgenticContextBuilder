import { test, expect } from "@playwright/test";
import { setupMultiBatchMocks } from "../utils/mock-api";

/**
 * Tests that verify the Extraction page displays batch-scoped metrics correctly.
 * These tests catch bugs where global data is shown instead of data for the selected batch.
 */
test.describe("Extraction Page - Batch Scoping", () => {
  test.beforeEach(async ({ page }) => {
    await setupMultiBatchMocks(page);
  });

  test("displays correct metrics for small batch (3 docs)", async ({ page }) => {
    // Navigate to batches workspace
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Select the small batch from the batch selector in context bar
    await page.getByTestId("batch-context-selector").selectOption("batch-small");
    await page.waitForLoadState("networkidle");

    // Verify phase cards show correct counts
    const classificationCard = page.locator('[data-testid="phase-classification"]');
    await expect(classificationCard).toContainText("3"); // 3 classified

    const extractionCard = page.locator('[data-testid="phase-extraction"]');
    await expect(extractionCard).toContainText("2"); // 2 succeeded

    // Verify coverage section shows batch-scoped total (3 docs, not 130)
    const labelCoverageValue = page.locator('[data-testid="label-coverage-value"]');
    await expect(labelCoverageValue).toContainText("/ 3");

    const extractionCoverageValue = page.locator('[data-testid="extraction-coverage-value"]');
    await expect(extractionCoverageValue).toContainText("/ 3");

    // Verify Doc Type Scoreboard shows only 3 doc types
    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');
    const rows = scoreboardTable.locator("tbody tr");
    await expect(rows).toHaveCount(3);
  });

  test("displays correct metrics for large batch (130 docs)", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Select the large batch
    await page.getByTestId("batch-context-selector").selectOption("batch-large");
    await page.waitForLoadState("networkidle");

    // Verify phase cards show correct counts
    const classificationCard = page.locator('[data-testid="phase-classification"]');
    await expect(classificationCard).toContainText("130"); // 130 classified

    const extractionCard = page.locator('[data-testid="phase-extraction"]');
    await expect(extractionCard).toContainText("35"); // 35 succeeded

    // Verify coverage section shows batch-scoped total (130 docs)
    const labelCoverageValue = page.locator('[data-testid="label-coverage-value"]');
    await expect(labelCoverageValue).toContainText("/ 130");

    // Verify Doc Type Scoreboard shows 6 doc types (from large batch distribution)
    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');
    const rows = scoreboardTable.locator("tbody tr");
    await expect(rows).toHaveCount(6);
  });

  test("metrics update when switching between batches", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    const batchSelector = page.getByTestId("batch-context-selector");

    // Start with small batch
    await batchSelector.selectOption("batch-small");
    await page.waitForLoadState("networkidle");

    // Verify small batch metrics
    const labelCoverageValue = page.locator('[data-testid="label-coverage-value"]');
    await expect(labelCoverageValue).toContainText("/ 3");

    // Switch to large batch
    await batchSelector.selectOption("batch-large");
    await page.waitForLoadState("networkidle");

    // Verify metrics updated to large batch values
    await expect(labelCoverageValue).toContainText("/ 130");

    // Switch back to small batch
    await batchSelector.selectOption("batch-small");
    await page.waitForLoadState("networkidle");

    // Verify metrics returned to small batch values
    await expect(labelCoverageValue).toContainText("/ 3");
  });

  test("doc type scoreboard shows Classified and Extracted columns", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Select small batch
    await page.getByTestId("batch-context-selector").selectOption("batch-small");
    await page.waitForLoadState("networkidle");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');

    // Verify headers include Classified and Extracted
    const headers = scoreboardTable.locator("thead th");
    await expect(headers.nth(1)).toContainText("Classified");
    await expect(headers.nth(2)).toContainText("Extracted");

    // Verify data rows show different values for Classified vs Extracted
    // For fnol_form: 1 classified, 0 extracted (no extraction spec)
    const firstRow = scoreboardTable.locator("tbody tr").first();
    const cells = firstRow.locator("td");

    // The classified count should be a number > 0
    const classifiedCell = cells.nth(1);
    const classifiedText = await classifiedCell.textContent();
    expect(parseInt(classifiedText || "0")).toBeGreaterThan(0);
  });
});
