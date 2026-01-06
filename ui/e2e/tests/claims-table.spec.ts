import { test, expect } from "@playwright/test";
import { ClaimsTablePage } from "../pages/claims-table.page";
import { setupApiMocks } from "../utils/mock-api";

test.describe("Claims Table", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("should display claims list", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.goto();

    // Should show claims from fixture
    await expect(page.getByText("CLM-2024-001")).toBeVisible();
    await expect(page.getByText("CLM-2024-002")).toBeVisible();
  });

  test("should have search input", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.goto();

    await expect(claimsTable.searchInput).toBeVisible();
  });

  test("should expand claim to show documents", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.goto();

    await claimsTable.expandClaim("CLM-2024-001");
    // Wait for expansion animation
    await page.waitForTimeout(500);

    // After expansion, doc types from fixture should be visible
    await expect(page.getByText("loss_notice").first()).toBeVisible();
  });

  test("should navigate to review when clicking document", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.goto();

    await claimsTable.expandClaim("CLM-2024-001");
    await claimsTable.clickDocument("loss_notice");

    await expect(page).toHaveURL(/\/claims\/CLM-2024-001\/review/);
  });

  test("should filter claims by search", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.goto();

    await claimsTable.searchClaims("CLM-2024-001");

    // Should show matching claim
    await expect(page.getByText("CLM-2024-001")).toBeVisible();
  });
});
