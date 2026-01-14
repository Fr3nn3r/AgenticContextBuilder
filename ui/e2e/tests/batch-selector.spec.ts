import { test, expect } from "@playwright/test";
import { InsightsPage } from "../pages/insights.page";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Batch Selector - Batch Context Bar", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("batch selector exists in context bar", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Batch context bar should be visible
    const batchContextBar = page.getByTestId("batch-context-bar");
    await expect(batchContextBar).toBeVisible();

    // Batch selector should be in context bar
    const batchSelector = page.getByTestId("batch-context-selector");
    await expect(batchSelector).toBeVisible();
  });

  test("switching batch updates selection and URL", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    const batchSelector = page.getByTestId("batch-context-selector");

    // Get initial value
    const initialValue = await batchSelector.inputValue();

    // Select a different batch
    await batchSelector.selectOption("run_002");

    // Value should change
    const newValue = await batchSelector.inputValue();
    expect(newValue).toBe("run_002");
    expect(newValue).not.toBe(initialValue);

    // URL should include new batch ID
    await expect(page).toHaveURL(/\/batches\/run_002/);
  });

  test("batch context persists across tab navigation", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    const batchSelector = page.getByTestId("batch-context-selector");

    // Select a specific batch
    await batchSelector.selectOption("run_002");
    await expect(page).toHaveURL(/\/batches\/run_002/);

    // Navigate to Documents tab
    await page.getByTestId("batch-tab-documents").click();
    await expect(page).toHaveURL(/\/batches\/run_002\/documents/);

    // Batch selector should still show the same batch
    await expect(batchSelector).toHaveValue("run_002");

    // Navigate to Benchmark tab
    await page.getByTestId("batch-tab-metrics").click();
    await expect(page).toHaveURL(/\/batches\/run_002\/metrics/);

    // Batch selector should still show the same batch
    await expect(batchSelector).toHaveValue("run_002");
  });
});

test.describe("Batch Selector - Benchmark Page", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("batch context header shows batch metadata", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // Batch context bar should be visible
    await expect(insights.batchContextBar).toBeVisible();

    // Batch selector should be visible
    await expect(insights.batchSelector).toBeVisible();
  });

  test("switching batch updates display", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // Get initial selected batch
    const initialBatch = await insights.getSelectedBatchId();
    expect(initialBatch).toBe("run_001");

    // Switch to different batch
    await insights.selectBatch("run_002");

    // Selection should update
    const newBatch = await insights.getSelectedBatchId();
    expect(newBatch).toBe("run_002");
  });

  test("KPI cards are visible", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // KPI cards should be visible
    await expect(insights.kpiCards.first()).toBeVisible();

    // Should have multiple KPI cards
    const kpiCount = await insights.kpiCards.count();
    expect(kpiCount).toBeGreaterThan(0);
  });

  test("tabs are visible and clickable", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // All tabs should be visible
    await expect(insights.insightsTab).toBeVisible();
    await expect(insights.historyTab).toBeVisible();
    await expect(insights.compareTab).toBeVisible();

    // Click history tab
    await insights.switchToTab("history");

    // Should show batch history table
    await expect(page.getByText("Batch ID")).toBeVisible();
  });
});
