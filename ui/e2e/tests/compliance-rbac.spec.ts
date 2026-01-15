/**
 * Compliance RBAC (Role-Based Access Control) Tests
 *
 * Tests that compliance screens are properly protected:
 * - Admin and Auditor roles can access compliance pages
 * - Reviewer and Operator roles are denied access
 * - Sidebar navigation visibility follows role permissions
 *
 * Works in both mock and integrated modes.
 */

import { test, expect } from "@playwright/test";
import { setupTestEnvironment } from "../utils/test-setup";
import { setupComplianceMocks } from "../utils/mock-api";
import { AccessDeniedPage } from "../pages/auth.page";
import { ComplianceOverviewPage } from "../pages/compliance.page";
import { config, isMockMode } from "../config/test-config";

test.describe("Compliance RBAC", () => {
  test.describe("Admin Access", () => {
    test.beforeEach(async ({ page }) => {
      await setupTestEnvironment(page, "admin");
      if (isMockMode()) {
        await setupComplianceMocks(page);
      }
    });

    test("admin can access compliance overview", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();
      await overview.expectLoaded();
    });

    test("admin can access all compliance sub-pages", async ({ page }) => {
      // Overview
      await page.goto("/compliance");
      await page.waitForLoadState("networkidle");
      await expect(page).not.toHaveURL(/\/login/);
      await expect(page.getByRole("heading", { name: "Access Denied" })).not.toBeVisible();

      // Ledger
      await page.goto("/compliance/ledger");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Decision Ledger" })).toBeVisible();

      // Verification
      await page.goto("/compliance/verification");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Verification Center" })).toBeVisible();

      // Version Bundles
      await page.goto("/compliance/version-bundles");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Version Bundles", exact: true })).toBeVisible();

      // Controls
      await page.goto("/compliance/controls");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Control Mapping" })).toBeVisible();
    });

    test("admin sees compliance nav item in sidebar", async ({ page }) => {
      await page.goto("/batches");
      await page.waitForLoadState("networkidle");

      // Compliance nav should be visible for admin
      await expect(page.getByTestId("nav-compliance")).toBeVisible();
    });
  });

  test.describe("Auditor Access", () => {
    test.beforeEach(async ({ page }) => {
      await setupTestEnvironment(page, "auditor");
      if (isMockMode()) {
        await setupComplianceMocks(page);
      }
    });

    test("auditor can access compliance overview", async ({ page }) => {
      const overview = new ComplianceOverviewPage(page);
      await overview.goto();
      await overview.expectLoaded();
    });

    test("auditor can access verification page", async ({ page }) => {
      await page.goto("/compliance/verification");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Verification Center" })).toBeVisible();
    });

    test("auditor can access ledger page", async ({ page }) => {
      await page.goto("/compliance/ledger");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Decision Ledger" })).toBeVisible();
    });

    test("auditor can access version bundles page", async ({ page }) => {
      await page.goto("/compliance/version-bundles");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Version Bundles", exact: true })).toBeVisible();
    });

    test("auditor can access controls page", async ({ page }) => {
      await page.goto("/compliance/controls");
      await page.waitForLoadState("networkidle");
      await expect(page.getByRole("heading", { name: "Control Mapping" })).toBeVisible();
    });

    test("auditor sees compliance nav item in sidebar", async ({ page }) => {
      await page.goto("/batches");
      await page.waitForLoadState("networkidle");
      await expect(page.getByTestId("nav-compliance")).toBeVisible();
    });
  });

  test.describe("Reviewer Access (Denied)", () => {
    test.beforeEach(async ({ page }) => {
      await setupTestEnvironment(page, "reviewer");
    });

    test("reviewer cannot access compliance overview", async ({ page }) => {
      await page.goto("/compliance");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("reviewer cannot access compliance ledger", async ({ page }) => {
      await page.goto("/compliance/ledger");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("reviewer cannot access verification page", async ({ page }) => {
      await page.goto("/compliance/verification");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("reviewer cannot access version bundles page", async ({ page }) => {
      await page.goto("/compliance/version-bundles");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("reviewer cannot access controls page", async ({ page }) => {
      await page.goto("/compliance/controls");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("reviewer does not see compliance nav item in sidebar", async ({ page }) => {
      await page.goto("/batches");
      await page.waitForLoadState("networkidle");
      await expect(page.getByTestId("nav-compliance")).not.toBeVisible();
    });
  });

  test.describe("Operator Access (Denied)", () => {
    test.beforeEach(async ({ page }) => {
      await setupTestEnvironment(page, "operator");
    });

    test("operator cannot access compliance overview", async ({ page }) => {
      await page.goto("/compliance");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("operator cannot access compliance ledger", async ({ page }) => {
      await page.goto("/compliance/ledger");
      await page.waitForLoadState("networkidle");

      const accessDenied = new AccessDeniedPage(page);
      await accessDenied.expectAccessDenied();
    });

    test("operator does not see compliance nav item in sidebar", async ({ page }) => {
      await page.goto("/batches");
      await page.waitForLoadState("networkidle");
      await expect(page.getByTestId("nav-compliance")).not.toBeVisible();
    });
  });
});
