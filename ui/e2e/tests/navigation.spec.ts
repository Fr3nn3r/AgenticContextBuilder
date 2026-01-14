import { test, expect } from "@playwright/test";
import { SidebarPage } from "../pages/sidebar.page";
import { BasePage } from "../pages/base.page";
import { setupAuthenticatedMocks } from "../utils/mock-api";

test.describe("Sidebar Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");
  });

  test("should load app and display sidebar", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);

    await expect(sidebar.sidebar).toBeVisible();
    await expect(sidebar.batchesLink).toBeVisible();
    await expect(sidebar.allClaimsLink).toBeVisible();
    await expect(sidebar.templatesLink).toBeVisible();
    await expect(sidebar.pipelineLink).toBeVisible();
  });

  test("should navigate to All Claims page via sidebar", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToAllClaims();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/claims\/all/);
  });

  test("should navigate to Templates page via sidebar", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToTemplates();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/templates/);
  });

  test("should navigate to Pipeline page via sidebar", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToPipeline();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/pipeline/);
  });

  test("should navigate back to Batches via sidebar", async ({ page }) => {
    await page.goto("/templates");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToBatches();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/batches/);
  });

  test("should navigate between all pages in sequence", async ({ page }) => {
    await page.goto("/batches");
    const sidebar = new SidebarPage(page);

    // Batches -> All Claims
    await sidebar.navigateToAllClaims();
    await expect(page).toHaveURL(/\/claims\/all/);

    // All Claims -> Templates
    await sidebar.navigateToTemplates();
    await expect(page).toHaveURL(/\/templates/);

    // Templates -> Pipeline
    await sidebar.navigateToPipeline();
    await expect(page).toHaveURL(/\/pipeline/);

    // Pipeline -> Batches
    await sidebar.navigateToBatches();
    await expect(page).toHaveURL(/\/batches/);
  });

  test("should navigate between batch workspace tabs", async ({ page }) => {
    await page.goto("/batches");
    await page.waitForLoadState("networkidle");

    // Should start on overview tab (default)
    await expect(page.getByTestId("batch-tab-overview")).toBeVisible();

    // Navigate to Documents tab
    await page.getByTestId("batch-tab-documents").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/documents/);

    // Navigate to Classification tab
    await page.getByTestId("batch-tab-classification").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/classification/);

    // Navigate to Claims tab
    await page.getByTestId("batch-tab-claims").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/claims/);

    // Navigate to Benchmark tab
    await page.getByTestId("batch-tab-benchmark").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+\/benchmark/);

    // Navigate back to Overview tab
    await page.getByTestId("batch-tab-overview").click();
    await expect(page).toHaveURL(/\/batches\/[^/]+$/);
  });
});
