import { test, expect } from "@playwright/test";
import { ClaimsTablePage } from "../pages/claims-table.page";
import { setupApiMocks } from "../utils/mock-api";

// TODO: These tests are skipped because Vite's proxy forwards /api requests to a real backend,
// bypassing Playwright's route interception. To fix, either:
// 1. Run tests without a backend (mock all API calls)
// 2. Use a test-specific Vite config without the proxy
// 3. Seed the backend with test data before running these tests
test.describe.skip("Claims Table", () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  test("should display claims list", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    // Use All Claims page (no batch filtering)
    await claimsTable.gotoAllClaims();

    // Should show claims from fixture
    await expect(page.getByText("CLM-2024-001")).toBeVisible();
    await expect(page.getByText("CLM-2024-002")).toBeVisible();
  });

  test("should have search input", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.gotoAllClaims();

    await expect(claimsTable.searchInput).toBeVisible();
  });

  test("should expand claim to show documents", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.gotoAllClaims();

    await claimsTable.expandClaim("CLM-2024-001");

    // Wait for Document Pack content to load - look for the heading and a doc filename
    await expect(page.getByText("Document Pack")).toBeVisible();
    await expect(page.getByText("loss_notice.pdf")).toBeVisible();
  });

  test("should navigate to review when clicking document", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.gotoAllClaims();

    await claimsTable.expandClaim("CLM-2024-001");
    await claimsTable.clickDocument("loss_notice");

    await expect(page).toHaveURL(/\/claims\/CLM-2024-001\/review/);
  });

  test("should filter claims by search", async ({ page }) => {
    const claimsTable = new ClaimsTablePage(page);
    await claimsTable.gotoAllClaims();

    await claimsTable.searchClaims("CLM-2024-001");

    // Should show matching claim
    await expect(page.getByText("CLM-2024-001")).toBeVisible();
  });
});
