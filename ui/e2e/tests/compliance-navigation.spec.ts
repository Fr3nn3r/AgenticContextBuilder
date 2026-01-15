/**
 * Compliance Navigation Tests
 *
 * Tests navigation between compliance screens:
 * - Full navigation flow through all pages
 * - Sidebar compliance link
 * - Auth state persistence across navigation
 * - Direct URL access
 * - Filter-preserving navigation
 *
 * Works in both mock and integrated modes.
 */

import { test, expect } from "@playwright/test";
import { setupTestEnvironment, isMockMode } from "../utils/test-setup";
import { setupComplianceMocks } from "../utils/mock-api";

test.describe("Compliance Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
    if (isMockMode()) {
      await setupComplianceMocks(page);
    }
  });

  test.describe("Full Navigation Flow", () => {
    test("navigates through all compliance pages in sequence", async ({ page }) => {
      // Start at overview
      await page.goto("/compliance");
      await expect(page.getByRole("heading", { name: "Compliance Dashboard" })).toBeVisible();

      // Overview -> Ledger
      await page.getByRole("link", { name: /browse ledger/i }).click();
      await expect(page).toHaveURL(/\/compliance\/ledger/);
      await expect(page.getByRole("heading", { name: "Decision Ledger" })).toBeVisible();

      // Ledger -> Overview (back)
      await page.getByRole("link", { name: /back to overview/i }).click();
      await expect(page).toHaveURL(/\/compliance$/);

      // Overview -> Verification
      await page.getByRole("link", { name: /verification center/i }).click();
      await expect(page).toHaveURL(/\/compliance\/verification/);
      await expect(page.getByRole("heading", { name: "Verification Center" })).toBeVisible();

      // Verification -> Overview (back)
      await page.getByRole("link", { name: /back to overview/i }).click();
      await expect(page).toHaveURL(/\/compliance$/);

      // Overview -> Version Bundles
      await page.getByRole("link", { name: /version bundles/i }).first().click();
      await expect(page).toHaveURL(/\/compliance\/version-bundles/);
      await expect(page.getByRole("heading", { name: "Version Bundles", exact: true })).toBeVisible();

      // Version Bundles -> Overview (back)
      await page.getByRole("link", { name: /back to overview/i }).click();
      await expect(page).toHaveURL(/\/compliance$/);

      // Overview -> Controls
      await page.getByRole("link", { name: /control mapping/i }).click();
      await expect(page).toHaveURL(/\/compliance\/controls/);
      await expect(page.getByRole("heading", { name: "Control Mapping" })).toBeVisible();
    });
  });

  test.describe("Sidebar Navigation", () => {
    test("sidebar compliance link navigates to overview", async ({ page }) => {
      await page.goto("/batches");
      await page.waitForLoadState("networkidle");

      await page.getByTestId("nav-compliance").click();
      await expect(page).toHaveURL(/\/compliance/);
    });

    test("sidebar link works from any page", async ({ page }) => {
      // Start from templates
      await page.goto("/templates");
      await page.waitForLoadState("networkidle");

      await page.getByTestId("nav-compliance").click();
      await expect(page).toHaveURL(/\/compliance/);
    });

    test("sidebar remains accessible from compliance pages", async ({ page }) => {
      await page.goto("/compliance");
      await page.waitForLoadState("networkidle");

      // Sidebar should still be visible
      await expect(page.getByTestId("sidebar")).toBeVisible();

      // Can navigate to other sections
      await page.getByTestId("nav-batches").click();
      await expect(page).toHaveURL(/\/batches/);
    });
  });

  test.describe("Auth Persistence", () => {
    test("maintains auth state across compliance navigation", async ({ page }) => {
      await page.goto("/compliance");
      await page.getByRole("link", { name: /ledger/i }).first().click();
      await page.getByRole("link", { name: /back to overview/i }).click();
      await page.getByRole("link", { name: /verification/i }).first().click();

      // Should still be logged in
      await expect(page.getByTestId("sidebar")).toBeVisible();
      await expect(page).not.toHaveURL(/\/login/);
    });

    test("can navigate from compliance to other sections and back", async ({ page }) => {
      await page.goto("/compliance");

      // Go to batches
      await page.getByTestId("nav-batches").click();
      await expect(page).toHaveURL(/\/batches/);

      // Come back to compliance
      await page.getByTestId("nav-compliance").click();
      await expect(page).toHaveURL(/\/compliance/);

      // Should still be authenticated
      await expect(page.getByRole("heading", { name: "Compliance Dashboard" })).toBeVisible();
    });
  });

  test.describe("Direct URL Access", () => {
    test("can access overview directly", async ({ page }) => {
      await page.goto("/compliance");
      await page.waitForLoadState("networkidle");

      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();
      await expect(page.getByRole("heading", { name: "Compliance Dashboard" })).toBeVisible();
    });

    test("can access ledger directly", async ({ page }) => {
      await page.goto("/compliance/ledger");
      await page.waitForLoadState("networkidle");

      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { name: "Decision Ledger" })).toBeVisible();
    });

    test("can access verification directly", async ({ page }) => {
      await page.goto("/compliance/verification");
      await page.waitForLoadState("networkidle");

      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { name: "Verification Center" })).toBeVisible();
    });

    test("can access version-bundles directly", async ({ page }) => {
      await page.goto("/compliance/version-bundles");
      await page.waitForLoadState("networkidle");

      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { name: "Version Bundles", exact: true })).toBeVisible();
    });

    test("can access controls directly", async ({ page }) => {
      await page.goto("/compliance/controls");
      await page.waitForLoadState("networkidle");

      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { name: "Control Mapping" })).toBeVisible();
    });
  });

  test.describe("Filter-Preserving Navigation", () => {
    test("ledger filter links from controls page work", async ({ page }) => {
      await page.goto("/compliance/controls");

      // Click classification decisions 'View' link
      const classificationItem = page.locator("li").filter({ hasText: "Classification decisions" });
      await classificationItem.getByRole("link", { name: "View →" }).click();

      // Should navigate to ledger with filter
      await expect(page).toHaveURL(/\/compliance\/ledger\?type=classification/);

      // Filter should be applied - use main select to avoid sidebar theme select
      const typeFilter = page.locator("main select").first();
      await expect(typeFilter).toHaveValue("classification");
    });

    test("human review link from controls applies correct filter", async ({ page }) => {
      await page.goto("/compliance/controls");

      // Click human reviews 'View' link
      const humanReviewItem = page.locator("li").filter({ hasText: "Human reviews" });
      await humanReviewItem.getByRole("link", { name: "View →" }).click();

      await expect(page).toHaveURL(/\/compliance\/ledger\?type=human_review/);
    });

    test("can clear filters and return to full list", async ({ page }) => {
      // Start with filtered view
      await page.goto("/compliance/ledger?type=classification");

      // Use main select to avoid sidebar theme select
      const typeFilter = page.locator("main select").first();
      await expect(typeFilter).toHaveValue("classification");

      // Clear filter
      await typeFilter.selectOption("");
      await page.waitForLoadState("networkidle");

      // URL should not have filter
      await expect(page).not.toHaveURL(/type=/);
    });
  });

  test.describe("Browser History", () => {
    test("back button works correctly", async ({ page }) => {
      await page.goto("/compliance");

      // Navigate to ledger
      await page.getByRole("link", { name: /browse ledger/i }).click();
      await expect(page).toHaveURL(/\/compliance\/ledger/);

      // Use browser back
      await page.goBack();
      await expect(page).toHaveURL(/\/compliance$/);
    });

    test("forward button works after back", async ({ page }) => {
      await page.goto("/compliance");

      // Navigate to verification
      await page.getByRole("link", { name: /verification/i }).first().click();
      await expect(page).toHaveURL(/\/compliance\/verification/);

      // Go back
      await page.goBack();
      await expect(page).toHaveURL(/\/compliance$/);

      // Go forward
      await page.goForward();
      await expect(page).toHaveURL(/\/compliance\/verification/);
    });
  });
});
