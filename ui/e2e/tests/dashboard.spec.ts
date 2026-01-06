import { test, expect } from "@playwright/test";
import { DashboardPage } from "../pages/dashboard.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("should display KPI cards", async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // Verify KPI cards are present - use exact text to avoid multiple matches
    await expect(page.getByText("Total Claims", { exact: true })).toBeVisible();
    await expect(page.getByText("Pending Review", { exact: true })).toBeVisible();
    await expect(page.getByText("High Risk", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Total Value", { exact: true })).toBeVisible();
  });

  test("should display correct total claims count", async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    // Fixture has 2 claims
    const totalClaims = await dashboard.getTotalClaimsValue();
    expect(totalClaims).toBe("2");
  });

  test("should display risk overview section", async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.riskOverview).toBeVisible();
  });

  test("should display review progress section", async ({ page }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await expect(dashboard.reviewProgress).toBeVisible();
  });
});
