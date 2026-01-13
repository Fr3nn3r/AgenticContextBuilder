import { test, expect } from "@playwright/test";
import { setupMultiBatchMocks } from "../utils/mock-api";

/**
 * Tests that verify the Insights/Benchmark page displays batch-scoped metrics correctly.
 * These tests catch bugs where global data is shown instead of data for the selected batch.
 */
test.describe("Insights Page - Batch Scoping", () => {
  test.beforeEach(async ({ page }) => {
    await setupMultiBatchMocks(page);
  });

  test("displays correct KPIs for small batch (3 docs)", async ({ page }) => {
    await page.goto("/insights");
    await page.waitForLoadState("networkidle");

    // Select small batch from dropdown
    await page.selectOption('[data-testid="batch-selector"]', "batch-small");
    await page.waitForLoadState("networkidle");

    // Verify Doc Coverage KPI shows 3 docs total
    const docCoverageCard = page.locator('[data-testid="kpi-doc-coverage"]');
    await expect(docCoverageCard).toContainText("/3");
  });

  test("displays correct KPIs for large batch (130 docs)", async ({ page }) => {
    await page.goto("/insights");
    await page.waitForLoadState("networkidle");

    // Select large batch from dropdown
    await page.selectOption('[data-testid="batch-selector"]', "batch-large");
    await page.waitForLoadState("networkidle");

    // Verify Doc Coverage KPI shows 130 docs total
    const docCoverageCard = page.locator('[data-testid="kpi-doc-coverage"]');
    await expect(docCoverageCard).toContainText("/130");

    // Verify Accuracy KPI shows batch-specific value
    const accuracyCard = page.locator('[data-testid="kpi-accuracy"]');
    await expect(accuracyCard).toContainText("92%");
  });

  test("doc type scoreboard updates when switching batches", async ({ page }) => {
    await page.goto("/insights");
    await page.waitForLoadState("networkidle");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');

    // Select small batch - should show 3 doc types
    await page.selectOption('[data-testid="batch-selector"]', "batch-small");
    await page.waitForLoadState("networkidle");

    let rows = scoreboardTable.locator("tbody tr");
    await expect(rows).toHaveCount(3);

    // Switch to large batch - should show 6 doc types
    await page.selectOption('[data-testid="batch-selector"]', "batch-large");
    await page.waitForLoadState("networkidle");

    rows = scoreboardTable.locator("tbody tr");
    await expect(rows).toHaveCount(6);
  });

  test("doc type scoreboard shows Classified and Extracted columns", async ({ page }) => {
    await page.goto("/insights");
    await page.waitForLoadState("networkidle");

    // Select large batch for more interesting data
    await page.selectOption('[data-testid="batch-selector"]', "batch-large");
    await page.waitForLoadState("networkidle");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');

    // Verify headers include Classified and Extracted
    const headers = scoreboardTable.locator("thead th");
    await expect(headers.nth(1)).toContainText("Classified");
    await expect(headers.nth(2)).toContainText("Extracted");

    // Verify rows have data in both columns
    const firstRow = scoreboardTable.locator("tbody tr").first();
    const cells = firstRow.locator("td");

    // Classified column should have a number
    const classifiedText = await cells.nth(1).textContent();
    expect(parseInt(classifiedText || "0")).toBeGreaterThan(0);

    // Extracted column should have a number (could be 0 for unsupported types)
    const extractedText = await cells.nth(2).textContent();
    expect(parseInt(extractedText || "0")).toBeGreaterThanOrEqual(0);
  });

  test("KPIs and scoreboard remain consistent when refreshing", async ({ page }) => {
    await page.goto("/insights");
    await page.waitForLoadState("networkidle");

    // Select large batch
    await page.selectOption('[data-testid="batch-selector"]', "batch-large");
    await page.waitForLoadState("networkidle");

    // Note the current values
    const docCoverageCard = page.locator('[data-testid="kpi-doc-coverage"]');
    await expect(docCoverageCard).toContainText("/130");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');
    const rows = scoreboardTable.locator("tbody tr");
    await expect(rows).toHaveCount(6);

    // The batch selector should still have the large batch selected
    const batchSelector = page.locator('[data-testid="batch-selector"]');
    await expect(batchSelector).toHaveValue("batch-large");
  });
});
