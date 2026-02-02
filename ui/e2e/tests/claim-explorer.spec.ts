import { test, expect } from "@playwright/test";
import { setupAuthenticatedMocks } from "../utils/mock-api";

/**
 * Claim Explorer E2E tests.
 *
 * Tests the /claims/explorer page which shows:
 * - Left sidebar with claims tree (claims → documents)
 * - Right panel with tabs for claim summary and document view
 * - ClaimSummaryTab has sub-tabs: Assessment, Coverages, Data
 */
test.describe("Claim Explorer", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedMocks(page, "admin");

    // Mock assessment endpoint (not in setupApiMocks)
    await page.route(/\/api\/claims\/[^/]+\/assessment$/, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(null),
        });
      } else {
        await route.continue();
      }
    });

    // Mock coverage-analysis endpoint
    await page.route(/\/api\/claims\/[^/]+\/coverage-analysis$/, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(null),
        });
      } else {
        await route.continue();
      }
    });

    // Mock claim facts endpoint
    await page.route(/\/api\/claims\/[^/]+\/facts$/, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(null),
        });
      } else {
        await route.continue();
      }
    });

    // Mock doc source endpoint (returns a small PDF-like response)
    await page.route(/\/api\/docs\/[^/]+\/source/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: Buffer.from("%PDF-1.4 mock"),
      });
    });

    // Mock Azure DI endpoint
    await page.route(/\/api\/docs\/[^/]+\/azure-di/, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Azure DI data not available" }),
      });
    });

    // Mock doc runs endpoint
    await page.route(/\/api\/docs\/[^/]+\/runs/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
  });

  test("should navigate to Claims Explorer via sidebar", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Click on "Claim Explorer" link in sidebar
    const explorerLink = page.getByText("Claim Explorer").first();
    await explorerLink.click();

    await expect(page).toHaveURL(/\/claims\/explorer/);
    await expect(page.getByText("Claim Explorer").first()).toBeVisible();
  });

  test("should load and display claims list", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Header should show "Claim Explorer"
    await expect(page.locator("h1").getByText("Claim Explorer")).toBeVisible();

    // Claims tree should show the fixture claims
    await expect(page.getByText("CLM-2024-001")).toBeVisible();
    await expect(page.getByText("CLM-2024-002")).toBeVisible();

    // Claims count should be visible
    await expect(page.getByText("2 claims")).toBeVisible();
  });

  test("should select a claim and show claim summary tab", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Click a claim in the tree
    await page.getByText("CLM-2024-001").first().click();

    // A tab should appear for this claim
    await expect(page.getByText("CLM-2024-001")).toBeVisible();

    // The claim summary should be visible with sub-tabs
    // Assessment is the default tab
    await expect(page.getByText("Assessment")).toBeVisible();
    await expect(page.getByText("Coverages")).toBeVisible();
    await expect(page.getByText("Data")).toBeVisible();
  });

  test("should expand claim to show documents in tree", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Click a claim to select and expand it
    await page.getByText("CLM-2024-001").first().click();
    await page.waitForLoadState("networkidle");

    // Documents should appear in the tree (from claim-review fixture)
    await expect(page.getByText("loss_notice.pdf")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("police_report.pdf")).toBeVisible();
  });

  test("should open document tab when clicking a document", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Expand claim
    await page.getByText("CLM-2024-001").first().click();
    await page.waitForLoadState("networkidle");

    // Wait for docs to load, then click a document
    await page.getByText("loss_notice.pdf").first().click();

    // Document tab should open with document content
    // The DocumentTab shows filename and doc type
    await expect(page.getByText("Loss Notice")).toBeVisible({ timeout: 5000 });
  });

  test("should switch between claim summary sub-tabs", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Select a claim
    await page.getByText("CLM-2024-001").first().click();
    await page.waitForLoadState("networkidle");

    // Assessment tab should be active by default
    const assessmentTab = page.getByRole("button", { name: /Assessment/i }).first();
    const coveragesTab = page.getByRole("button", { name: /Coverages/i }).first();
    const dataTab = page.getByRole("button", { name: /Data/i }).first();

    // Switch to Coverages
    await coveragesTab.click();
    // Coverages content should be visible (even if empty/loading)
    await expect(coveragesTab).toBeVisible();

    // Switch to Data
    await dataTab.click();
    await expect(dataTab).toBeVisible();

    // Switch back to Assessment
    await assessmentTab.click();
    await expect(assessmentTab).toBeVisible();
  });

  test("should show empty state when no claim is selected", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Should show the empty state prompt
    await expect(page.getByText("Select a Claim")).toBeVisible();
    await expect(
      page.getByText("Choose a claim from the list")
    ).toBeVisible();
  });

  test("should handle document loading error gracefully", async ({ page }) => {
    // Override the doc mock to return an error
    await page.route(/\/api\/docs\/[^/]+$/, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error" }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Expand claim and click a document
    await page.getByText("CLM-2024-001").first().click();
    await page.waitForLoadState("networkidle");
    await page.getByText("loss_notice.pdf").first().click();

    // Should show error message and retry button
    await expect(page.getByText("Try again")).toBeVisible({ timeout: 5000 });
  });

  test("should close a tab", async ({ page }) => {
    await page.goto("/claims/explorer");
    await page.waitForLoadState("networkidle");

    // Open a claim tab
    await page.getByText("CLM-2024-001").first().click();
    await page.waitForLoadState("networkidle");

    // Tab should be visible
    const claimTab = page.locator('[class*="cursor-pointer"]').filter({ hasText: "CLM-2024-001" });
    await expect(claimTab.first()).toBeVisible();

    // Close the tab by clicking the X button inside it
    const closeButton = claimTab.first().locator("button").first();
    await closeButton.click();

    // Should return to empty state
    await expect(page.getByText("Select a Claim")).toBeVisible();
  });
});
