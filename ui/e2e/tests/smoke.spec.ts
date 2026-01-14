import { test, expect } from "@playwright/test";
import { SidebarPage } from "../pages/sidebar.page";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Smoke Tests", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("app loads and displays correct sidebar nav items", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);

    // Sidebar should be visible
    await expect(sidebar.sidebar).toBeVisible();

    // Should display nav items with correct labels
    await expect(sidebar.batchesLink).toBeVisible();
    await expect(sidebar.batchesLink).toContainText("Batches");

    await expect(sidebar.allClaimsLink).toBeVisible();
    await expect(sidebar.allClaimsLink).toContainText("All Claims");

    await expect(sidebar.templatesLink).toBeVisible();
    await expect(sidebar.templatesLink).toContainText("Templates");

    await expect(sidebar.pipelineLink).toBeVisible();
    await expect(sidebar.pipelineLink).toContainText("Pipeline");
  });

  test("batch workspace displays context bar and tabs", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Batch context bar should be visible
    await expect(page.getByTestId("batch-context-bar")).toBeVisible();

    // Batch selector should be in context bar
    await expect(page.getByTestId("batch-context-selector")).toBeVisible();

    // Batch sub-navigation tabs should be visible
    await expect(page.getByTestId("batch-sub-nav")).toBeVisible();
    await expect(page.getByTestId("batch-tab-overview")).toBeVisible();
    await expect(page.getByTestId("batch-tab-documents")).toBeVisible();
    await expect(page.getByTestId("batch-tab-classification")).toBeVisible();
    await expect(page.getByTestId("batch-tab-claims")).toBeVisible();
    await expect(page.getByTestId("batch-tab-metrics")).toBeVisible();
  });

  test("navigate to each screen without errors", async ({ page }) => {
    // Track console errors
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/batches");
    const sidebar = new SidebarPage(page);

    // Navigate to Batches (default landing)
    await sidebar.navigateToBatches();
    await expect(page).toHaveURL(/\/batches/);

    // Navigate to All Claims
    await sidebar.navigateToAllClaims();
    await expect(page).toHaveURL(/\/claims\/all/);

    // Navigate to Templates
    await sidebar.navigateToTemplates();
    await expect(page).toHaveURL(/\/templates/);

    // Navigate to Pipeline
    await sidebar.navigateToPipeline();
    await expect(page).toHaveURL(/\/pipeline/);

    // No critical console errors should have occurred
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("404")
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test("logo and branding visible", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);

    await expect(sidebar.logo).toBeVisible();
    // CB logo appears in sidebar
    await expect(page.locator("text=CB").first()).toBeVisible();
  });

  test("batch workspace tabs navigate correctly", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Click Documents tab
    await page.getByTestId("batch-tab-documents").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/documents/);

    // Click Benchmark tab
    await page.getByTestId("batch-tab-metrics").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/metrics/);

    // Click Overview tab to return
    await page.getByTestId("batch-tab-overview").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+$/);
  });
});
