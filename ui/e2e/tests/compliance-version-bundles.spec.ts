/**
 * Compliance Version Bundles Tests
 *
 * Tests the version bundle tracking functionality:
 * - Bundle list display
 * - Bundle selection and detail view
 * - Git commit and dirty state display
 * - Version metadata (model, extractor, hashes)
 * - Empty states
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
import { expectMinimumCount } from "../utils/assertions";
import { ComplianceVersionBundlesPage } from "../pages/compliance.page";
import { config } from "../config/test-config";

test.describe("Compliance Version Bundles", () => {
  test.beforeEach(async ({ page }) => {
    await setupTestEnvironment(page, "admin");
    if (isMockMode()) {
      await setupComplianceMocks(page);
    }
  });

  test.describe("Bundle List", () => {
    test("displays version bundles page", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();
      await bundles.expectLoaded();
    });

    test("shows pipeline runs section", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(page.getByText("Pipeline Runs")).toBeVisible();
    });

    test("displays snapshot count", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(bundles.snapshotCount).toBeVisible();
    });

    test("shows bundle list with run IDs", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await expect(page.getByText("run-2026-01-15-001")).toBeVisible();
        await expect(page.getByText("run-2026-01-14-001")).toBeVisible();
      } else {
        // In integrated mode, just check we have at least expected count
        const count = await bundles.getBundleCount();
        expect(count).toBeGreaterThanOrEqual(config.expectations.minBundleCount);
      }
    });

    test("displays model name and extractor version in list", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await expect(page.getByText(/gpt-4o.*1\.2\.0/)).toBeVisible();
      }
    });

    test("shows dirty badge for uncommitted changes", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.expectDirtyBadge();
      }
    });

    test("displays creation timestamp", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      // Timestamps should be formatted dates
      if (isMockMode()) {
        // Check for date-like text in list items
        const datePattern = /\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2}/;
        const listText = await bundles.bundleListSection.textContent();
        expect(listText).toMatch(datePattern);
      }
    });
  });

  test.describe("Bundle Selection", () => {
    test("shows select prompt when no bundle selected", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(bundles.selectPrompt).toBeVisible();
    });

    test("loads bundle details when clicked", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      const bundleCount = await bundles.getBundleCount();
      if (bundleCount > 0) {
        await bundles.selectFirstBundle();
        await bundles.expectBundleSelected();
      }
    });

    test("highlights selected bundle in list", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.selectBundle("run-2026-01-15-001");

        // Selected item should have highlight class
        const selectedButton = page.locator("button").filter({ hasText: "run-2026-01-15-001" });
        await expect(selectedButton).toHaveClass(/bg-muted/);
      }
    });
  });

  test.describe("Bundle Details", () => {
    test("displays bundle ID", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      const bundleCount = await bundles.getBundleCount();
      if (bundleCount > 0) {
        await bundles.selectFirstBundle();
        await bundles.expectDetailField("Bundle ID");
      }
    });

    test("displays run ID", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      const bundleCount = await bundles.getBundleCount();
      if (bundleCount > 0) {
        await bundles.selectFirstBundle();
        await bundles.expectDetailField("Run ID");
      }
    });

    test("displays git commit hash", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.selectBundle("run-2026-01-15-001");
        await bundles.expectDetailField("Commit");
      }
    });

    test("displays working tree status (clean)", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.selectBundle("run-2026-01-15-001");
        await bundles.expectCleanStatus();
      }
    });

    test("displays working tree status (dirty)", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.selectBundle("run-2026-01-14-001");
        await bundles.expectDirtyStatus();
      }
    });

    test("displays model name", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      const bundleCount = await bundles.getBundleCount();
      if (bundleCount > 0) {
        await bundles.selectFirstBundle();
        await bundles.expectDetailField("Model");
      }
    });

    test("displays model version", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      const bundleCount = await bundles.getBundleCount();
      if (bundleCount > 0) {
        await bundles.selectFirstBundle();
        await bundles.expectDetailField("Model Version");
      }
    });

    test("displays extractor version", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      const bundleCount = await bundles.getBundleCount();
      if (bundleCount > 0) {
        await bundles.selectFirstBundle();
        await bundles.expectDetailField("Extractor");
      }
    });

    test("displays prompt template hash", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.selectBundle("run-2026-01-15-001");
        await expect(page.getByText("Prompt Template Hash")).toBeVisible();
        // Use first() since there are multiple sha256: values on the page
        await expect(page.getByText(/sha256:/).first()).toBeVisible();
      }
    });

    test("displays extraction spec hash", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      if (isMockMode()) {
        await bundles.selectBundle("run-2026-01-15-001");
        await expect(page.getByText("Extraction Spec Hash")).toBeVisible();
      }
    });
  });

  test.describe("Explanation Section", () => {
    test("displays 'Why Version Bundles Matter' section", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(bundles.explanationSection).toBeVisible();
    });

    test("shows reproducibility explanation", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(page.getByText("Reproducibility")).toBeVisible();
    });

    test("shows accountability explanation", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(page.getByText("Accountability")).toBeVisible();
    });

    test("shows compliance explanation", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(
        page.locator(".bg-muted\\/30").filter({ hasText: "Compliance" })
      ).toBeVisible();
    });
  });

  test.describe("Empty State", () => {
    test("shows empty state when no bundles exist", async ({ page }) => {
      skipInIntegratedMode(test, "Cannot guarantee empty state in integrated mode");

      await page.route("**/api/compliance/version-bundles", async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      });

      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await expect(bundles.emptyState).toBeVisible();
    });
  });

  test.describe("Loading State", () => {
    test("shows loading indicator while fetching", async ({ page }) => {
      skipInIntegratedMode(test, "Loading states are timing-dependent");

      await page.route("**/api/compliance/version-bundles", async (route) => {
        await new Promise((r) => setTimeout(r, 500));
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      });

      await page.goto("/compliance/version-bundles");

      await expect(page.getByText("Loading version bundles...")).toBeVisible();
    });
  });

  test.describe("Navigation", () => {
    test("navigates back to overview", async ({ page }) => {
      const bundles = new ComplianceVersionBundlesPage(page);
      await bundles.goto();

      await bundles.navigateBack();
      await expect(page).toHaveURL(/\/compliance$/);
    });
  });
});
