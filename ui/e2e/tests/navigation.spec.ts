import { test, expect } from "@playwright/test";
import { SidebarPage } from "../pages/sidebar.page";
import { BasePage } from "../pages/base.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Sidebar Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("should load app and display sidebar", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = new SidebarPage(page);

    await expect(sidebar.sidebar).toBeVisible();
    await expect(sidebar.dashboardLink).toBeVisible();
    await expect(sidebar.claimsLink).toBeVisible();
    await expect(sidebar.templatesLink).toBeVisible();
  });

  test("should navigate to Claims page via sidebar", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToClaims();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/claims/);
  });

  test("should navigate to Templates page via sidebar", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToTemplates();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/templates/);
  });

  test("should navigate back to Dashboard via sidebar", async ({ page }) => {
    await page.goto("/claims");
    const sidebar = new SidebarPage(page);
    const basePage = new BasePage(page);

    await sidebar.navigateToDashboard();
    await basePage.waitForLoad();

    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("should navigate between all pages in sequence", async ({ page }) => {
    await page.goto("/");
    const sidebar = new SidebarPage(page);

    // Dashboard -> Claims
    await sidebar.navigateToClaims();
    await expect(page).toHaveURL(/\/claims/);

    // Claims -> Templates
    await sidebar.navigateToTemplates();
    await expect(page).toHaveURL(/\/templates/);

    // Templates -> Dashboard
    await sidebar.navigateToDashboard();
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
