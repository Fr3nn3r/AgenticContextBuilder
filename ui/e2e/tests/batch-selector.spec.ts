import { test, expect } from "@playwright/test";
import { InsightsPage } from "../pages/insights.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Batch Selector - Claim Document Pack", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("batch selector exists", async ({ page }) => {
    await page.goto("/claims");

    const batchSelector = page.getByTestId("batch-selector");
    await expect(batchSelector).toBeVisible();
  });

  test("switching batch updates selection", async ({ page }) => {
    await page.goto("/claims");

    const batchSelector = page.getByTestId("batch-selector");

    // Get initial value
    const initialValue = await batchSelector.inputValue();

    // Select a different batch
    await batchSelector.selectOption("run_002");

    // Value should change
    const newValue = await batchSelector.inputValue();
    expect(newValue).toBe("run_002");
    expect(newValue).not.toBe(initialValue);
  });
});

test.describe("Batch Selector - Calibration Insights", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("batch context header shows batch metadata", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // Batch selector should be visible
    await expect(insights.batchSelector).toBeVisible();

    // Batch metadata should be visible
    await expect(insights.runMetadata).toBeVisible();

    // Metadata should contain model info
    const metadataText = await insights.getRunMetadataText();
    expect(metadataText).toContain("Model:");
    expect(metadataText).toContain("gpt-4o");
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
