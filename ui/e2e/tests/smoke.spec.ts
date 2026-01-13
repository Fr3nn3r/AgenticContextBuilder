import { test, expect } from "@playwright/test";
import { SidebarPage } from "../pages/sidebar.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Smoke Tests", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("app loads and displays correct sidebar nav items", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = new SidebarPage(page);

    // Sidebar should be visible
    await expect(sidebar.sidebar).toBeVisible();

    // Should display exactly 4 nav items with correct labels
    await expect(sidebar.dashboardLink).toBeVisible();
    await expect(sidebar.dashboardLink).toContainText("Extraction");

    await expect(sidebar.claimsLink).toBeVisible();
    await expect(sidebar.claimsLink).toContainText("Claims Review");

    await expect(sidebar.insightsLink).toBeVisible();
    await expect(sidebar.insightsLink).toContainText("Benchmark");

    await expect(sidebar.templatesLink).toBeVisible();
    await expect(sidebar.templatesLink).toContainText("Extraction Templates");
  });

  test("navigate to each screen without errors", async ({ page }) => {
    // Track console errors
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto("/dashboard");
    const sidebar = new SidebarPage(page);

    // Navigate to Dashboard (Calibration Home)
    await sidebar.navigateToDashboard();
    await expect(page).toHaveURL(/\/dashboard/);

    // Navigate to Claims (Claim Document Pack)
    await sidebar.navigateToClaims();
    await expect(page).toHaveURL(/\/claims/);

    // Navigate to Insights (Calibration Insights)
    await sidebar.navigateToInsights();
    await expect(page).toHaveURL(/\/insights/);

    // Navigate to Templates (Extraction Templates)
    await sidebar.navigateToTemplates();
    await expect(page).toHaveURL(/\/templates/);

    // No critical console errors should have occurred
    const criticalErrors = consoleErrors.filter(
      (e) => !e.includes("favicon") && !e.includes("404")
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test("logo and branding visible", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = new SidebarPage(page);

    await expect(sidebar.logo).toBeVisible();
    // CB logo appears in sidebar - use first() since it also appears in header
    await expect(page.locator("text=CB").first()).toBeVisible();
  });
});
