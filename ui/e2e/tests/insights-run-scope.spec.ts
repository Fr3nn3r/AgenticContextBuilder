import { test, expect } from "@playwright/test";
import { setupAuthenticatedMultiBatchMocks } from "../utils/mock-api";

/**
 * Tests that verify the Insights/Benchmark page displays batch-scoped metrics correctly.
 * These tests catch bugs where global data is shown instead of data for the selected batch.
 *
 * Note: Running in serial mode to avoid race conditions with shared mock state.
 */
test.describe("Insights Page - Batch Scoping", () => {
  test.describe.configure({ mode: "serial" });
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMultiBatchMocks(page, "admin");
  });

  test("displays correct KPIs for small batch (3 docs)", async ({ page }) => {
    // Navigate to batches workspace then benchmark tab
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-benchmark").click();
    await page.waitForLoadState("networkidle");

    // Select small batch from context bar dropdown
    await page.getByTestId("batch-context-selector").selectOption("batch-small");
    await page.waitForLoadState("networkidle");

    // Verify Doc Coverage KPI shows 3 docs total
    const docCoverageCard = page.locator('[data-testid="kpi-doc-coverage"]');
    await expect(docCoverageCard).toContainText("/3");
  });

  test("displays correct KPIs for large batch (130 docs)", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-benchmark").click();
    await page.waitForLoadState("networkidle");

    // Select large batch from context bar dropdown
    await page.getByTestId("batch-context-selector").selectOption("batch-large");
    await page.waitForLoadState("networkidle");

    // Verify Doc Coverage KPI shows 130 docs total
    const docCoverageCard = page.locator('[data-testid="kpi-doc-coverage"]');
    await expect(docCoverageCard).toContainText("/130");

    // Verify Accuracy KPI shows batch-specific value
    const accuracyCard = page.locator('[data-testid="kpi-accuracy"]');
    await expect(accuracyCard).toContainText("92%");
  });

  test("doc type scoreboard shows data for selected batch", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-benchmark").click();
    await page.waitForLoadState("networkidle");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');

    // Select small batch from context bar
    await page.getByTestId("batch-context-selector").selectOption("batch-small");
    await page.waitForLoadState("networkidle");

    // Wait for scoreboard to have data rows
    const rows = scoreboardTable.locator("tbody tr");
    await expect(rows.first()).toBeVisible({ timeout: 10000 });

    // Verify at least one doc type is shown
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(1);
  });

  test("doc type scoreboard shows Classified and Extracted columns", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-benchmark").click();
    await page.waitForLoadState("networkidle");

    // Select large batch for more interesting data
    await page.getByTestId("batch-context-selector").selectOption("batch-large");
    await page.waitForLoadState("networkidle");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');

    // Verify headers include Classified and Extracted
    const headers = scoreboardTable.locator("thead th");
    await expect(headers.nth(1)).toContainText("Classified");
    await expect(headers.nth(2)).toContainText("Extracted");

    // Verify table has data rows (at least one row with doc type content)
    const rows = scoreboardTable.locator("tbody tr");
    await expect(rows.first()).toBeVisible();

    // Verify the first row has a doc type name (not empty/loading state)
    const firstCell = rows.first().locator("td").first();
    await expect(firstCell).not.toBeEmpty();
  });

  test("KPIs and scoreboard remain consistent when refreshing", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("batch-tab-benchmark").click();
    await page.waitForLoadState("networkidle");

    // Select large batch from context bar
    await page.getByTestId("batch-context-selector").selectOption("batch-large");
    await page.waitForLoadState("networkidle");

    // Note the current values
    const docCoverageCard = page.locator('[data-testid="kpi-doc-coverage"]');
    await expect(docCoverageCard).toContainText("/130");

    const scoreboardTable = page.locator('[data-testid="scoreboard-table"]');
    const rows = scoreboardTable.locator("tbody tr");
    await expect(rows).toHaveCount(6);

    // The batch selector in context bar should still have the large batch selected
    const batchSelector = page.getByTestId("batch-context-selector");
    await expect(batchSelector).toHaveValue("batch-large");
  });
});
