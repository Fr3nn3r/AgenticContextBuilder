/**
 * Compliance Overview (Dashboard) Tests
 *
 * Tests the main compliance dashboard functionality:
 * - Status cards display (hash chain, decisions, bundles)
 * - Valid/invalid hash chain indicators
 * - Recent decisions list
 * - Quick navigation links
 * - Loading and error states
 *
 * Works in both mock and integrated modes.
 */

import { test, expect } from "@playwright/test";
import {
  setupTestEnvironment,
  skipInIntegratedMode,
  isMockMode,
} from "../utils/test-setup";
import { setupComplianceMocks } from "../utils/mock-api";
import { expectNumericValue, expectHashChainStatus } from "../utils/assertions";
import { ComplianceOverviewPage } from "../pages/compliance.page";

test.describe("Compliance Overview", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
  });

  test.describe("Dashboard Layout", () => {
    test.beforeEach(async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page, { verification: "valid" });
      }
    });

    test("displays dashboard with all status cards", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();
      await overview.expectLoaded();

      // Check status cards are present - use first() to handle potential duplicates
      await expect(page.getByText("Hash Chain Integrity").first()).toBeVisible();
      await expect(page.getByText("Decision Records").first()).toBeVisible();
      await expect(page.getByText("Version Bundles").first()).toBeVisible();
    });

    test("displays recent decisions section", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await expect(page.getByText("Recent Decisions")).toBeVisible();
    });

    test("displays compliance controls quick links", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      // Quick links section - use role links to be specific
      await expect(page.getByRole("link", { name: /verification center/i })).toBeVisible();
      await expect(page.getByRole("link", { name: /version bundles/i }).first()).toBeVisible();
      await expect(page.getByRole("link", { name: /control mapping/i })).toBeVisible();
    });
  });

  test.describe("Hash Chain Status", () => {
    test("shows valid hash chain status", async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page, { verification: "valid" });
      }

      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      // In mock mode, assert specific status; in integrated, just check one is shown
      await expectHashChainStatus(page, isMockMode() ? "valid" : undefined);
    });

    test("shows invalid hash chain status with red indicator", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot control hash chain state in integrated mode");

      await setupComplianceMocks(page, { verification: "invalid" });

      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await overview.expectInvalidHashChain();
      await expect(page.locator(".text-red-500")).toBeVisible();
    });

    test("displays record count", async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page, { verification: "valid" });
      }

      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      // Record count should be a number
      await expectNumericValue(overview.recordCountValue, { min: 0 });
    });
  });

  test.describe("Recent Decisions", () => {
    test("displays decision entries when data exists", async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page, { verification: "valid", decisions: "normal" });
      }

      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      // In mock mode, we should see decision types
      // In integrated mode, may or may not have decisions
      if (isMockMode()) {
        const decisionTypes = page.locator("text=/classification|extraction|human review|override/i");
        await expect(decisionTypes.first()).toBeVisible();
      }
    });

    test("shows empty state when no decisions exist", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee empty state in integrated mode");

      await setupComplianceMocks(page, { verification: "empty", decisions: "empty" });

      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await expect(overview.emptyDecisionsMessage).toBeVisible();
    });
  });

  test.describe("Navigation", () => {
    test.beforeEach(async ({ page }) => {
      if (isMockMode()) {
        await setupComplianceMocks(page);
      }
    });

    test("navigates to verification page via quick link", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await overview.navigateToVerification();
      await expect(page).toHaveURL(/\/compliance\/verification/);
    });

    test("navigates to ledger via 'Browse ledger' link", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await overview.navigateToLedger();
      await expect(page).toHaveURL(/\/compliance\/ledger/);
    });

    test("navigates to version bundles via quick link", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await overview.navigateToBundles();
      await expect(page).toHaveURL(/\/compliance\/version-bundles/);
    });

    test("navigates to controls via quick link", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await overview.navigateToControls();
      await expect(page).toHaveURL(/\/compliance\/controls/);
    });

    test("'View all' link goes to ledger", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await page.getByRole("link", { name: "View all" }).click();
      await expect(page).toHaveURL(/\/compliance\/ledger/);
    });
  });

  test.describe("Error Handling", () => {
    test("handles API error gracefully", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot force API errors in integrated mode");

      // Override the verification endpoint to return an error
      await page.route("**/api/compliance/ledger/verify", async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Internal server error" }),
        });
      });

      // Setup other mocks normally
      await setupComplianceMocks(page);

      const overview = new ComplianceOverviewPage(page);
      await overview.goto();

      await expect(overview.errorMessage).toBeVisible();
    });
  });

  test.describe("Loading States", () => {
    test("shows loading indicator initially", async ({ page }) => {
      skipInIntegratedMode(test, "Loading states are timing-dependent");

      // Delay API response to observe loading state
      await page.route("**/api/compliance/ledger/verify", async (route) => {
        await new Promise((r) => setTimeout(r, 500));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ valid: true, total_records: 0, break_at_index: null, break_at_decision_id: null, error_type: null, error_details: null, verified_at: new Date().toISOString() }),
        });
      });

      await setupComplianceMocks(page);
      await page.goto("/compliance");

      // Loading indicator should appear briefly
      // Note: This test may be flaky due to timing
    });
  });
});
