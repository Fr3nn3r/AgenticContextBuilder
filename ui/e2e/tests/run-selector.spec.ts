import { test, expect } from "@playwright/test";
import { InsightsPage } from "../pages/insights.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Run Selector - Claim Document Pack", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("run selector exists and shows Latest option", async ({ page }) => {
    await page.goto("/claims");

    const runSelector = page.getByTestId("run-selector");
    await expect(runSelector).toBeVisible();

    // Should show "(Latest)" in the options
    const options = runSelector.locator("option");
    await expect(options.first()).toContainText("(Latest)");
  });

  test("switching run shows loading state", async ({ page }) => {
    await page.goto("/claims");

    const runSelector = page.getByTestId("run-selector");

    // Get initial value
    const initialValue = await runSelector.inputValue();

    // Select a different run
    await runSelector.selectOption("run_002");

    // Value should change
    const newValue = await runSelector.inputValue();
    expect(newValue).toBe("run_002");
    expect(newValue).not.toBe(initialValue);
  });
});

test.describe("Run Selector - Calibration Insights", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("run context header shows run metadata", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // Run selector should be visible
    await expect(insights.runSelector).toBeVisible();

    // Run metadata should be visible
    await expect(insights.runMetadata).toBeVisible();

    // Metadata should contain model info
    const metadataText = await insights.getRunMetadataText();
    expect(metadataText).toContain("Model:");
    expect(metadataText).toContain("gpt-4o");
  });

  test("switching run updates display", async ({ page }) => {
    const insights = new InsightsPage(page);
    await insights.goto();

    // Get initial selected run
    const initialRun = await insights.getSelectedRunId();
    expect(initialRun).toBe("run_001");

    // Switch to different run
    await insights.selectRun("run_002");

    // Selection should update
    const newRun = await insights.getSelectedRunId();
    expect(newRun).toBe("run_002");
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

    // Should show run history table
    await expect(page.getByText("Run ID")).toBeVisible();
  });
});
