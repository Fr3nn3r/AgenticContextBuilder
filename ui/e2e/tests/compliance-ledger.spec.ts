/**
 * Compliance Ledger (Decision List) Tests
 *
 * Tests the decision ledger functionality:
 * - Table display with proper columns
 * - Decision type badges and color coding
 * - Filtering by type, claim, and document
 * - URL-based filter state management
 * - Empty states and result counts
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
import {
  expectTableHasRows,
  expectCount,
  expectDecisionTypeBadge,
} from "../utils/assertions";
import { ComplianceLedgerPage } from "../pages/compliance.page";
import { config } from "../config/test-config";

test.describe("Compliance Ledger", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
    if (isMockMode()) {
      await setupComplianceMocks(page);
    }
  });

  test.describe("Table Display", () => {
    test("displays decision ledger with table headers", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();
      await ledger.expectLoaded();

      // Check table headers
      await expect(page.getByRole("columnheader", { name: "Type" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Timestamp" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Claim" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Document" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Actor" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Confidence" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Hash Chain" })).toBeVisible();
    });

    test("displays decision records in table", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // In mock mode: exact count, in integrated: at least minimum
      await expectTableHasRows(ledger.resultsTable, {
        exact: isMockMode() ? 6 : undefined,
        min: config.expectations.minDecisionCount,
      });
    });

    test("shows result count footer", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await expect(ledger.resultCount).toBeVisible();
    });
  });

  test.describe("Decision Type Badges", () => {
    test("displays classification badge", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      if (isMockMode()) {
        await expectDecisionTypeBadge(page, "classification");
      }
    });

    test("displays extraction badge", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      if (isMockMode()) {
        await expectDecisionTypeBadge(page, "extraction");
      }
    });

    test("displays human review badge", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      if (isMockMode()) {
        await expectDecisionTypeBadge(page, "human_review");
      }
    });

    test("displays override badge", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      if (isMockMode()) {
        await expectDecisionTypeBadge(page, "override");
      }
    });
  });

  test.describe("Filtering", () => {
    test("filter dropdown contains all decision types", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // Check filter options
      const options = ledger.typeFilter.locator("option");
      await expect(options).toHaveCount(5); // All Types + 4 types

      await expect(options.nth(0)).toHaveText("All Types");
      await expect(options.nth(1)).toHaveText("Classification");
      await expect(options.nth(2)).toHaveText("Extraction");
      await expect(options.nth(3)).toHaveText("Human Review");
      await expect(options.nth(4)).toHaveText("Override");
    });

    test("filters by decision type and updates URL", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await ledger.filterByType("classification");

      // URL should update with filter param
      await expect(page).toHaveURL(/type=classification/);
    });

    test("filters by claim ID and updates URL", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await ledger.filterByClaim("CLM-001");

      await expect(page).toHaveURL(/claim=CLM-001/);
    });

    test("filters by document ID and updates URL", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await ledger.filterByDoc("abc123");

      await expect(page).toHaveURL(/doc=abc123/);
    });

    test("combines multiple filters", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await ledger.filterByType("extraction");
      await ledger.filterByClaim("CLM-001");

      // Both params should be in URL
      await expect(page).toHaveURL(/type=extraction/);
      await expect(page).toHaveURL(/claim=CLM-001/);
    });

    test("loads with URL filter params pre-applied", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.gotoWithFilters({ type: "classification" });

      // Filter should be pre-selected
      await expect(ledger.typeFilter).toHaveValue("classification");
    });

    test("clears type filter when 'All Types' selected", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.gotoWithFilters({ type: "classification" });

      await ledger.filterByType("");

      await expect(page).not.toHaveURL(/type=/);
    });

    test("filtered results show only matching records", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee specific data in integrated mode");

      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // Wait for initial data to load
      await expect(ledger.resultsTable.locator("tbody tr").first()).toBeVisible();

      await ledger.filterByType("classification");

      // Wait for filtered data to load
      await page.waitForTimeout(500); // Allow time for filter to be applied

      // All visible rows should be classification type
      const rows = await ledger.tableRows.all();
      expect(rows.length).toBeGreaterThan(0);

      for (const row of rows) {
        await expect(row.getByText("classification")).toBeVisible();
      }
    });
  });

  test.describe("Actor Display", () => {
    test("displays system actor correctly", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      if (isMockMode()) {
        await expect(page.getByText("System").first()).toBeVisible();
      }
    });

    test("displays human actor with ID", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee human actor data");

      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // Filter to human review to find human actor
      await ledger.filterByType("human_review");

      // Should show actor ID for human actors
      await expect(page.locator("td").filter({ hasText: "reviewer" })).toBeVisible();
    });
  });

  test.describe("Confidence Display", () => {
    test("displays confidence as percentage", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // Should see percentage values
      const percentages = page.locator("td").filter({ hasText: /\d+%/ });
      await expect(percentages.first()).toBeVisible();
    });

    test("high confidence shown in green", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee specific confidence values");

      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // 95% confidence should be green
      const highConfidence = page.locator("td .text-green-500").filter({ hasText: /9\d%/ });
      await expect(highConfidence.first()).toBeVisible();
    });
  });

  test.describe("Empty States", () => {
    test("shows empty state when no decisions match filter", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee empty filter results");

      await setupComplianceMocks(page, { decisions: "empty" });

      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await expect(ledger.emptyState).toBeVisible();
    });

    test("shows empty state with specific filter that has no matches", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      // Filter by non-existent claim
      await ledger.filterByClaim("NONEXISTENT-CLAIM-12345");

      await expect(ledger.emptyState).toBeVisible();
    });
  });

  test.describe("Navigation", () => {
    test("navigates back to overview", async ({ page }) => {
      const ledger = new ComplianceLedgerPage(page);
      await ledger.goto();

      await ledger.navigateBack();
      await expect(page).toHaveURL(/\/compliance$/);
    });
  });
});
